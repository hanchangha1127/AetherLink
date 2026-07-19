import CompanionCore
import Foundation
import SwiftUI

@MainActor
func shouldShowRouteDiagnosticsPanel(model: CompanionAppModel) -> Bool {
    model.hasDevelopmentRelayRoute
        || model.bootstrapRelaySettings.isEnabled
        || model.remoteRoutePreparationIssue != nil
}

@MainActor
func shouldShowPairingRouteSetupPanel(model: CompanionAppModel) -> Bool {
    shouldShowRouteDiagnosticsPanel(model: model) || !model.hasDevelopmentRelayRoute
}

@MainActor
func shouldExpandPairingRouteSetupByDefault(model: CompanionAppModel) -> Bool {
    !model.hasDevelopmentRelayRoute &&
        !model.bootstrapRelaySettings.isEnabled &&
        !model.canPrepareRemoteRelayRouteAutomatically
}

enum ConnectionRecoveryConfigurationRequestResolution: Equatable {
    case unchanged
    case pending(CompanionRelayConfigurationRequestContext)
    case completed(CompanionRelayConfigurationRequestCompletion)
}

func connectionRecoveryConfigurationRequestResolution(
    state: CompanionRelayConfigurationRequestState?
) -> ConnectionRecoveryConfigurationRequestResolution {
    guard let state else { return .unchanged }
    switch state {
    case .active(let context):
        return .pending(context)
    case .completed(let completion):
        return .completed(completion)
    }
}

struct PendingConnectionRecoveryPairingRefresh: Equatable {
    let previousSessionID: String?
}

enum ConnectionRecoveryPairingRefreshResolution: Equatable {
    case pending
    case succeeded
    case failed
}

func connectionRecoveryPairingRefreshResolution(
    request: PendingConnectionRecoveryPairingRefresh,
    currentSessionID: String?,
    isPreparationInFlight: Bool
) -> ConnectionRecoveryPairingRefreshResolution {
    if let currentSessionID, currentSessionID != request.previousSessionID {
        return .succeeded
    }
    return isPreparationInFlight ? .pending : .failed
}

struct ConnectionRecoveryBootstrapDraft: Equatable {
    var endpoints: String
    var allocationToken: String
    var allowsPrivateOverlay: Bool

    init(
        endpoints: String = "",
        allocationToken: String = "",
        allowsPrivateOverlay: Bool = false
    ) {
        self.endpoints = endpoints
        self.allocationToken = allocationToken
        self.allowsPrivateOverlay = allowsPrivateOverlay
    }

    init(settings: CompanionBootstrapRelaySettings) {
        self.init(
            endpoints: settings.endpoints,
            allocationToken: settings.allocationToken ?? "",
            allowsPrivateOverlay: settings.allowsPrivateOverlay
        )
    }
}

struct ConnectionRecoveryDevelopmentDraft: Equatable {
    var host: String
    var port: String
    var relaySecret: String
    var allowsPrivateOverlay: Bool

    init(
        host: String = "",
        port: String = "43171",
        relaySecret: String = "",
        allowsPrivateOverlay: Bool = false
    ) {
        self.host = host
        self.port = port
        self.relaySecret = relaySecret
        self.allowsPrivateOverlay = allowsPrivateOverlay
    }

    init(settings: CompanionDevelopmentRelaySettings) {
        self.init(
            host: settings.host,
            port: settings.isEnabled ? String(settings.port) : "43171",
            relaySecret: settings.relaySecret ?? "",
            allowsPrivateOverlay: settings.allowsPrivateOverlay
        )
    }
}

struct ConnectionRecoveryDraftRevision<Value: Equatable>: Equatable {
    var modelValue: Value
}

struct ConnectionRecoveryDraftReconciliation<Value: Equatable>: Equatable {
    var draft: Value
    var revision: ConnectionRecoveryDraftRevision<Value>
}

func reconcileConnectionRecoveryDraft<Value: Equatable>(
    current: Value,
    revision: ConnectionRecoveryDraftRevision<Value>,
    incomingModelValue: Value,
    force: Bool = false
) -> ConnectionRecoveryDraftReconciliation<Value> {
    ConnectionRecoveryDraftReconciliation(
        draft: force || current == revision.modelValue ? incomingModelValue : current,
        revision: ConnectionRecoveryDraftRevision(modelValue: incomingModelValue)
    )
}

func connectionRecoveryResultAllowsDraftResync(_ result: CompanionRelayConfigurationResult) -> Bool {
    switch result {
    case .disabled, .savedStatic, .allocated:
        return true
    case .allocationFailed:
        return false
    }
}

struct RemoteRelayRoutePanel: View {
    @ObservedObject var model: CompanionAppModel
    var onGenerateRemotePairingQRCode: (() -> Void)?
    @State private var bootstrapEndpoints = ""
    @State private var bootstrapAllocationToken = ""
    @State private var bootstrapAllowsPrivateOverlay = false
    @State private var host = ""
    @State private var port = "43171"
    @State private var relaySecret = ""
    @State private var allowsPrivateOverlay = false
    @State private var message: String?
    @State private var messageTone = StatusTone.neutral
    @State private var diagnosticMessage: String?
    @State private var isAdvancedRouteSettingsExpanded = false
    @State private var isRemoveBootstrapRelayConfirmationPresented = false
    @State private var isRemoveSavedConnectionDetailsConfirmationPresented = false
    @State private var pendingOperation: CompanionRelayConfigurationOperation?
    @State private var pendingRequestID: UUID?
    @State private var pendingPairingRefresh: PendingConnectionRecoveryPairingRefresh?
    @State private var bootstrapDraftRevision: ConnectionRecoveryDraftRevision<ConnectionRecoveryBootstrapDraft>
    @State private var developmentDraftRevision: ConnectionRecoveryDraftRevision<ConnectionRecoveryDevelopmentDraft>

    init(model: CompanionAppModel, onGenerateRemotePairingQRCode: (() -> Void)? = nil) {
        let bootstrapDraft = ConnectionRecoveryBootstrapDraft(settings: model.bootstrapRelaySettings)
        let developmentDraft = ConnectionRecoveryDevelopmentDraft(settings: model.developmentRelaySettings)
        self.model = model
        self.onGenerateRemotePairingQRCode = onGenerateRemotePairingQRCode
        _bootstrapEndpoints = State(initialValue: bootstrapDraft.endpoints)
        _bootstrapAllocationToken = State(initialValue: bootstrapDraft.allocationToken)
        _bootstrapAllowsPrivateOverlay = State(initialValue: bootstrapDraft.allowsPrivateOverlay)
        _host = State(initialValue: developmentDraft.host)
        _port = State(initialValue: developmentDraft.port)
        _relaySecret = State(initialValue: developmentDraft.relaySecret)
        _allowsPrivateOverlay = State(initialValue: developmentDraft.allowsPrivateOverlay)
        _bootstrapDraftRevision = State(
            initialValue: ConnectionRecoveryDraftRevision(modelValue: bootstrapDraft)
        )
        _developmentDraftRevision = State(
            initialValue: ConnectionRecoveryDraftRevision(modelValue: developmentDraft)
        )
        _isAdvancedRouteSettingsExpanded = State(
            initialValue: shouldExpandPairingRouteSetupByDefault(model: model)
        )
    }

    var body: some View {
        CompanionPanel(title: NSLocalizedString("Connection Recovery", comment: ""), systemImage: "point.3.connected.trianglepath.dotted") {
            VStack(alignment: .leading, spacing: 12) {
                relayStatus

                Label(NSLocalizedString("Connection Setup", comment: ""), systemImage: "point.3.connected.trianglepath.dotted")
                    .font(.subheadline.weight(.semibold))

                advancedRouteSettings

                if let message {
                    Label(message, systemImage: messageTone.systemImage)
                        .font(.caption)
                        .foregroundStyle(messageTone.color)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(
                            Text(connectionRecoveryResultAccessibilityLabel(message: message, tone: messageTone))
                        )
                }

                if let diagnosticMessage {
                    DiagnosticDisclosure(
                        title: NSLocalizedString("Technical Details", comment: ""),
                        accessibilityContext: NSLocalizedString("Connection Recovery result", comment: ""),
                        text: diagnosticMessage
                    )
                }
            }
        }
        .onAppear {
            syncFromModel()
            reconcileConfigurationRequestState()
        }
        .onChange(of: model.developmentRelaySettings) { _, _ in
            syncDevelopmentDraftFromModel()
        }
        .onChange(of: model.bootstrapRelaySettings) { _, _ in
            syncBootstrapDraftFromModel()
        }
        .onChange(of: model.isRemoteRoutePreparationInFlight) { _, _ in
            resolvePendingPairingRefresh()
        }
        .onChange(of: model.relayConfigurationRequestState) { _, _ in
            reconcileConfigurationRequestState()
        }
        .onChange(of: model.pairingSession?.id) { _, _ in
            resolvePendingPairingRefresh()
        }
        .confirmationDialog(
            NSLocalizedString("Remove saved bootstrap relay?", comment: ""),
            isPresented: $isRemoveBootstrapRelayConfirmationPresented,
            titleVisibility: .visible
        ) {
            Button(NSLocalizedString("Remove Bootstrap Relay", comment: ""), role: .destructive) {
                guard model.requestClearBootstrapRelayForUserInterface() else {
                    diagnosticMessage = nil
                    message = NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
                    messageTone = .neutral
                    return
                }
                pendingOperation = nil
                pendingRequestID = nil
                syncBootstrapDraftFromModel(force: true)
                diagnosticMessage = nil
                message = NSLocalizedString("Saved bootstrap relay removed.", comment: "")
                messageTone = .neutral
            }
            .disabled(model.isRemoteRoutePreparationInFlight)
            .accessibilityLabel(
                Text(
                    removeSavedBootstrapRelayAccessibilityLabel(
                        endpoints: model.bootstrapRelaySettings.endpointLabel
                    )
                )
            )
            .accessibilityHint(Text(removeSavedBootstrapRelayAccessibilityHint()))
            Button(NSLocalizedString("Cancel", comment: ""), role: .cancel) {}
                .accessibilityLabel(
                    Text(
                        cancelRemoveSavedBootstrapRelayAccessibilityLabel(
                            endpoints: model.bootstrapRelaySettings.endpointLabel
                        )
                    )
                )
        } message: {
            Text(NSLocalizedString("Saved bootstrap relay settings will be removed. Devices on another network may need a fresh pairing QR before route preparation can run again.", comment: ""))
        }
        .confirmationDialog(
            NSLocalizedString("Remove saved connection details?", comment: ""),
            isPresented: $isRemoveSavedConnectionDetailsConfirmationPresented,
            titleVisibility: .visible
        ) {
            Button(NSLocalizedString("Remove Saved Connection Details", comment: ""), role: .destructive) {
                guard model.requestClearDevelopmentRelayForUserInterface() else {
                    diagnosticMessage = nil
                    message = NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
                    messageTone = .neutral
                    return
                }
                pendingOperation = nil
                pendingRequestID = nil
                syncDevelopmentDraftFromModel(force: true)
                diagnosticMessage = nil
                message = NSLocalizedString("Saved connection details removed.", comment: "")
                messageTone = .neutral
            }
            .disabled(model.isRemoteRoutePreparationInFlight)
            .accessibilityLabel(
                Text(
                    removeSavedConnectionDetailsAccessibilityLabel(
                        endpoint: model.developmentRelaySettings.endpointLabel
                    )
                )
            )
            .accessibilityHint(Text(removeSavedConnectionDetailsAccessibilityHint()))
            Button(NSLocalizedString("Cancel", comment: ""), role: .cancel) {}
                .accessibilityLabel(
                    Text(
                        cancelRemoveSavedConnectionDetailsAccessibilityLabel(
                            endpoint: model.developmentRelaySettings.endpointLabel
                        )
                    )
                )
        } message: {
            Text(NSLocalizedString("Saved connection details will be removed. Devices on another network may need a fresh pairing QR before they can reconnect.", comment: ""))
        }
    }

    @ViewBuilder
    private var advancedRouteSettings: some View {
        let settings = model.developmentRelaySettings
        VStack(alignment: .leading, spacing: 12) {
            Text(NSLocalizedString("Pair trusted devices with a QR. When devices are on different networks, AetherLink adds protected connection details while model providers stay private inside AetherLink Runtime.", comment: ""))
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            if settings.isEnabled {
                let canGenerateLatestQRCode = connectionRecoveryGenerateLatestQRActionAvailable(
                    canRequestRemotePairing: model.canRequestRemotePairingForUserInterface,
                    hasAction: onGenerateRemotePairingQRCode != nil
                )
                let generateLatestQRHint = connectionRecoveryGenerateLatestQRActionAccessibilityHint(
                    isRouteReadyForQRCode: model.isDevelopmentRelayQRCodeReady,
                    canPrepareRoute: canGenerateLatestQRCode,
                    hasAction: onGenerateRemotePairingQRCode != nil,
                    isPreparing: model.isRemoteRoutePreparationInFlight
                )
                Button {
                    generateRelayQRCode()
                } label: {
                    Label(NSLocalizedString("Generate Latest QR", comment: ""), systemImage: "qrcode")
                }
                .buttonStyle(.bordered)
                .disabled(!canGenerateLatestQRCode)
                .help(generateLatestQRHint)
                .accessibilityValue(
                    Text(
                        connectionRecoveryGenerateLatestQRActionAccessibilityValue(
                            isRouteReadyForQRCode: model.isDevelopmentRelayQRCodeReady,
                            canPrepareRoute: canGenerateLatestQRCode,
                            hasAction: onGenerateRemotePairingQRCode != nil,
                            isPreparing: model.isRemoteRoutePreparationInFlight
                        )
                    )
                )
                .accessibilityHint(Text(generateLatestQRHint))

                if !model.isDevelopmentRelayQRCodeReady {
                    Label(relayQRCodeReadinessText(settings: settings), systemImage: "info.circle")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            DisclosureGroup(isExpanded: $isAdvancedRouteSettingsExpanded) {
                VStack(alignment: .leading, spacing: 12) {
                    Text(NSLocalizedString("Use this only when AetherLink cannot prepare connection details automatically.", comment: ""))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)

                    VStack(alignment: .leading, spacing: 8) {
                        Label(NSLocalizedString("Bootstrap Relay", comment: ""), systemImage: "point.3.connected.trianglepath.dotted")
                            .font(.caption.weight(.semibold))
                        Text(NSLocalizedString("Use a reachable bootstrap relay to prepare QR connection details without putting a local network address in the QR.", comment: ""))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                        TextField(NSLocalizedString("Bootstrap relay endpoints", comment: ""), text: $bootstrapEndpoints)
                            .textFieldStyle(.roundedBorder)
                            .accessibilityLabel(Text(NSLocalizedString("Bootstrap relay endpoints", comment: "")))
                            .accessibilityValue(Text(connectionRecoveryTextFieldAccessibilityValue(bootstrapEndpoints)))
                        SecureField(NSLocalizedString("Bootstrap allocation token", comment: ""), text: $bootstrapAllocationToken, prompt: Text(NSLocalizedString("Optional", comment: "")))
                            .textFieldStyle(.roundedBorder)
                            .accessibilityLabel(Text(NSLocalizedString("Bootstrap allocation token", comment: "")))
                            .accessibilityValue(
                                Text(
                                    connectionRecoveryBootstrapAllocationTokenAccessibilityValue(
                                        endpoints: bootstrapEndpoints,
                                        allocationToken: bootstrapAllocationToken
                                    )
                                )
                            )
                        if let allocationTokenWarning = connectionRecoveryBootstrapAllocationTokenWarning(
                            endpoints: bootstrapEndpoints,
                            allocationToken: bootstrapAllocationToken
                        ) {
                            Label(allocationTokenWarning, systemImage: "exclamationmark.triangle")
                                .font(.caption)
                                .foregroundStyle(.orange)
                                .fixedSize(horizontal: false, vertical: true)
                                .accessibilityLabel(Text(allocationTokenWarning))
                        }
                        Toggle(isOn: $bootstrapAllowsPrivateOverlay) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(NSLocalizedString("Use Private Overlay Route", comment: ""))
                                Text(NSLocalizedString("Enable only when this bootstrap relay is reachable through a VPN, tunnel, or private overlay shared by both devices.", comment: ""))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        .toggleStyle(.checkbox)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(Text(connectionRecoveryBootstrapPrivateOverlayRouteAccessibilityLabel()))
                        .accessibilityValue(Text(connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled: bootstrapAllowsPrivateOverlay)))
                        .accessibilityHint(Text(NSLocalizedString("Enable only when this bootstrap relay is reachable through a VPN, tunnel, or private overlay shared by both devices.", comment: "")))
                        Button {
                            saveBootstrapRelay()
                        } label: {
                            Label(NSLocalizedString("Save Bootstrap Relay", comment: ""), systemImage: "externaldrive.badge.checkmark")
                        }
                        .buttonStyle(.bordered)
                        .disabled(model.isRemoteRoutePreparationInFlight)
                        .help(connectionRecoverySaveBootstrapRelayActionAccessibilityHint())
                        .accessibilityValue(
                            Text(
                                connectionRecoverySaveBootstrapRelayActionAccessibilityValue(
                                    endpoints: bootstrapEndpoints,
                                    allocationToken: bootstrapAllocationToken
                                )
                            )
                        )
                        .accessibilityHint(Text(connectionRecoverySaveBootstrapRelayActionAccessibilityHint()))
                        if model.bootstrapRelaySettings.isEnabled {
                            Button(role: .destructive) {
                                isRemoveBootstrapRelayConfirmationPresented = true
                            } label: {
                                Label(NSLocalizedString("Remove Bootstrap Relay", comment: ""), systemImage: "xmark.circle")
                            }
                            .buttonStyle(.bordered)
                            .disabled(model.isRemoteRoutePreparationInFlight)
                            .accessibilityLabel(
                                Text(
                                    removeSavedBootstrapRelayAccessibilityLabel(
                                        endpoints: model.bootstrapRelaySettings.endpointLabel
                                    )
                                )
                            )
                            .help(removeSavedBootstrapRelayAccessibilityHint())
                            .accessibilityHint(Text(removeSavedBootstrapRelayAccessibilityHint()))
                        }
                    }

                    Divider()

                    HStack(spacing: 8) {
                        TextField(NSLocalizedString("Connection address", comment: ""), text: $host)
                            .textFieldStyle(.roundedBorder)
                            .accessibilityLabel(Text(NSLocalizedString("Connection address", comment: "")))
                            .accessibilityValue(Text(connectionRecoveryTextFieldAccessibilityValue(host)))
                        TextField(NSLocalizedString("Port", comment: ""), text: $port)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 86)
                            .accessibilityLabel(Text(NSLocalizedString("Port", comment: "")))
                            .accessibilityValue(Text(connectionRecoveryTextFieldAccessibilityValue(port)))
                    }

                    SecureField(NSLocalizedString("Connection setup secret", comment: ""), text: $relaySecret, prompt: Text(NSLocalizedString("Generated automatically if blank", comment: "")))
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel(Text(NSLocalizedString("Connection setup secret", comment: "")))
                        .accessibilityValue(Text(connectionRecoveryGeneratedSecretAccessibilityValue(relaySecret)))

                    if shouldShowPrivateOverlayToggle {
                        Toggle(isOn: $allowsPrivateOverlay) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(NSLocalizedString("Use Private Overlay Route", comment: ""))
                                Text(NSLocalizedString("Enable only when this private address is reachable through a VPN, tunnel, or private overlay shared by both devices.", comment: ""))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        .toggleStyle(.checkbox)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(Text(connectionRecoveryFallbackPrivateOverlayRouteAccessibilityLabel()))
                        .accessibilityValue(Text(connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled: allowsPrivateOverlay)))
                        .accessibilityHint(Text(NSLocalizedString("Enable only when this private address is reachable through a VPN, tunnel, or private overlay shared by both devices.", comment: "")))
                    }

                    HStack(spacing: 8) {
                        let saveConnectionActionValue = connectionRecoverySaveConnectionActionAccessibilityValue(
                            host: host,
                            port: port
                        )
                        Button {
                            saveRelay()
                        } label: {
                            Label(NSLocalizedString("Save Connection", comment: ""), systemImage: "externaldrive.badge.checkmark")
                        }
                        .buttonStyle(.bordered)
                        .disabled(model.isRemoteRoutePreparationInFlight)
                        .help(connectionRecoverySaveConnectionActionAccessibilityHint())
                        .accessibilityValue(Text(saveConnectionActionValue))
                        .accessibilityHint(Text(connectionRecoverySaveConnectionActionAccessibilityHint()))

                        Button {
                            model.regenerateDevelopmentRelaySecret()
                            syncDevelopmentDraftFromModel(force: true)
                            message = NSLocalizedString("Connection setup secret regenerated.", comment: "")
                            messageTone = .ready
                        } label: {
                            Label(NSLocalizedString("Rotate Secret", comment: ""), systemImage: "key")
                        }
                        .buttonStyle(.bordered)
                        .disabled(model.isRemoteRoutePreparationInFlight)
                        .help(connectionRecoveryRotateSecretActionAccessibilityHint())
                        .accessibilityValue(Text(NSLocalizedString("Ready", comment: "")))
                        .accessibilityHint(Text(connectionRecoveryRotateSecretActionAccessibilityHint()))

                        if settings.isEnabled {
                            Button(role: .destructive) {
                                isRemoveSavedConnectionDetailsConfirmationPresented = true
                            } label: {
                                Label(NSLocalizedString("Remove Saved Connection Details", comment: ""), systemImage: "xmark.circle")
                            }
                            .buttonStyle(.bordered)
                            .disabled(model.isRemoteRoutePreparationInFlight)
                            .accessibilityLabel(Text(removeSavedConnectionDetailsAccessibilityLabel(endpoint: settings.endpointLabel)))
                            .help(removeSavedConnectionDetailsAccessibilityHint())
                            .accessibilityHint(Text(removeSavedConnectionDetailsAccessibilityHint()))
                        }
                    }
                }
                .padding(.top, 4)
            } label: {
                Label(NSLocalizedString("Connection Recovery", comment: ""), systemImage: "wrench.and.screwdriver")
                    .font(.caption.weight(.medium))
            }
            .tint(.secondary)
            .accessibilityLabel(Text(connectionRecoveryDisclosureAccessibilityLabel()))
            .accessibilityValue(
                Text(connectionRecoveryDisclosureAccessibilityValue(isExpanded: isAdvancedRouteSettingsExpanded))
            )
            .accessibilityHint(Text(connectionRecoveryDisclosureAccessibilityHint()))

            relayHostWarning(settings: settings)
        }
    }

    @ViewBuilder
    private func relayHostWarning(settings: CompanionDevelopmentRelaySettings) -> some View {
        if let warning = settings.hostReachabilityWarning {
            let warningText = relayHostWarningText(warning)
            Label(warningText, systemImage: "exclamationmark.triangle")
                .font(.caption)
                .foregroundStyle(StatusTone.warning.color)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(Text(connectionRecoveryHostWarningAccessibilityLabel(message: warningText)))
        }
    }

    @ViewBuilder
    private var relayStatus: some View {
        let settings = model.developmentRelaySettings
        let savedConnectionStatus = settings.isEnabled
            ? NSLocalizedString("Connection details saved", comment: "")
            : NSLocalizedString("No connection details", comment: "")
        let routeScopeStatus = remoteRouteScopeLabel(
            settings: settings,
            bootstrapSettings: model.bootstrapRelaySettings,
            canPrepareAutomatically: model.canPrepareRemoteRelayRouteAutomatically
        )
        let routeScopeDetail = remoteRouteScopeDetail(
            settings: settings,
            bootstrapSettings: model.bootstrapRelaySettings,
            canPrepareAutomatically: model.canPrepareRemoteRelayRouteAutomatically
        )
        let connectionStatus = relayConnectionLabel(model.developmentRelayConnectionStatus)
        let connectionDetail = relayConnectionDetail(status: model.developmentRelayConnectionStatus, settings: settings)
        VStack(alignment: .leading, spacing: 8) {
            RelayStatusRow(
                title: NSLocalizedString("Connection Setup", comment: ""),
                value: savedConnectionStatus,
                detail: relayStatusText(settings: settings),
                tone: settings.isEnabled ? (settings.frameEncryptionEnabled ? .ready : .warning) : .inactive
            )

            RelayStatusRow(
                title: NSLocalizedString("Connection route", comment: ""),
                value: routeScopeStatus,
                detail: routeScopeDetail,
                tone: relayRouteScopeTone(settings: settings)
            )

            RelayStatusRow(
                title: NSLocalizedString("Connection health", comment: ""),
                value: connectionStatus,
                detail: connectionDetail,
                tone: relayConnectionTone(model.developmentRelayConnectionStatus, isEnabled: settings.isEnabled)
            )

            if let diagnostic = relayConnectionDiagnostic(status: model.developmentRelayConnectionStatus) {
                DiagnosticDisclosure(
                    title: NSLocalizedString("Technical Details", comment: ""),
                    accessibilityContext: NSLocalizedString("Connection health", comment: ""),
                    text: diagnostic
                )
            }

            if let issue = model.remoteRoutePreparationIssue {
                Label(remoteRoutePreparationIssueText(issue), systemImage: "exclamationmark.triangle")
                    .font(.caption)
                    .foregroundStyle(StatusTone.warning.color)
                    .fixedSize(horizontal: false, vertical: true)
                if let diagnostic = issue.message.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty {
                    DiagnosticDisclosure(
                        title: NSLocalizedString("Technical Details", comment: ""),
                        accessibilityContext: NSLocalizedString("Connection preparation", comment: ""),
                        text: diagnostic
                    )
                }
            }
        }
    }

    private func relayRouteScopeTone(settings: CompanionDevelopmentRelaySettings) -> StatusTone {
        guard settings.isEnabled else {
            return (model.bootstrapRelaySettings.isEnabled || model.canPrepareRemoteRelayRouteAutomatically)
                ? .neutral
                : .inactive
        }
        switch settings.hostReachabilityWarning {
        case .none:
            return .ready
        case .privateNetwork:
            return settings.allowsPrivateOverlay ? .neutral : .warning
        case .invalidFormat, .loopback, .localName:
            return .warning
        }
    }

    private func relayConnectionLabel(_ status: CompanionDevelopmentRelayStatus) -> String {
        switch status.status {
        case .stopped:
            return NSLocalizedString("Not connected", comment: "")
        case .connecting:
            return NSLocalizedString("Connecting", comment: "")
        case .waitingForPeer:
            return NSLocalizedString("Waiting for device", comment: "")
        case .ready:
            return NSLocalizedString("Connected", comment: "")
        case .reconnecting:
            return NSLocalizedString("Reconnecting", comment: "")
        case .failed:
            return NSLocalizedString("Connection failed", comment: "")
        }
    }

    private func relayConnectionTone(_ status: CompanionDevelopmentRelayStatus, isEnabled: Bool) -> StatusTone {
        guard isEnabled else { return .inactive }
        switch status.status {
        case .ready:
            return .ready
        case .failed:
            return .warning
        case .connecting, .waitingForPeer, .reconnecting:
            return .neutral
        case .stopped:
            return .inactive
        }
    }

    private func relayConnectionDetail(
        status: CompanionDevelopmentRelayStatus,
        settings: CompanionDevelopmentRelaySettings
    ) -> String {
        guard settings.isEnabled else {
            return NSLocalizedString("Connection details are off. Add details only when QR pairing cannot connect from another network.", comment: "")
        }
        let endpoint = status.endpoint ?? settings.endpointLabel ?? NSLocalizedString("saved connection", comment: "")
        switch status.status {
        case .stopped:
            return NSLocalizedString("Start AetherLink Runtime to use these connection details.", comment: "")
        case .connecting:
            return String(format: NSLocalizedString("Connecting through %@.", comment: ""), endpoint)
        case .waitingForPeer:
            return String(format: NSLocalizedString("%@ is ready and waiting for a trusted device.", comment: ""), endpoint)
        case .ready:
            return String(format: NSLocalizedString("AetherLink Runtime and the trusted device are connected through %@. Model requests still run only through AetherLink Runtime.", comment: ""), endpoint)
        case .reconnecting:
            return String(format: NSLocalizedString("Reconnecting through %@.", comment: ""), endpoint)
        case .failed:
            return remoteRelayConnectionFailureRecoveryText(endpoint: endpoint)
        }
    }

    private func relayConnectionDiagnostic(status: CompanionDevelopmentRelayStatus) -> String? {
        switch status.status {
        case .reconnecting(let message):
            return message?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        case .failed(let message):
            return message.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        case .stopped, .connecting, .waitingForPeer, .ready:
            return nil
        }
    }

    private func relayStatusText(settings: CompanionDevelopmentRelaySettings) -> String {
        guard settings.isEnabled else {
            if model.canPrepareRemoteRelayRouteAutomatically {
                return NSLocalizedString("AetherLink can prepare connection details automatically when you generate a pairing QR.", comment: "")
            }
            return NSLocalizedString("Pairing from another network needs connection details inside the pairing QR.", comment: "")
        }
        let endpoint = settings.endpointLabel ?? NSLocalizedString("saved connection", comment: "")
        if settings.isEnvironmentOverride {
            return String(
                format: NSLocalizedString("Saved connection details use %@. Generate a fresh QR after updating the connection.", comment: ""),
                endpoint
            )
        }
        return String(
                format: NSLocalizedString("New QR codes include %@ after AetherLink Runtime is ready.", comment: ""),
            endpoint
        )
    }

    private func relayQRCodeReadinessText(settings: CompanionDevelopmentRelaySettings) -> String {
        return LocalAgentBridge.relayQRCodeReadinessText(
            settings: settings,
            isEligibleForQRCode: model.isDevelopmentRelayRouteEligibleForQRCode,
            isPreparedForQRCode: model.isDevelopmentRelayRoutePreparedForQRCode,
            connectionStatus: model.developmentRelayConnectionStatus
        )
    }

    private func saveRelay() {
        let trimmedHost = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedHost.isEmpty else {
            message = NSLocalizedString("Enter a connection address.", comment: "")
            messageTone = .warning
            diagnosticMessage = nil
            return
        }
        guard let normalizedHost = normalizedRelayHost(trimmedHost) else {
            message = NSLocalizedString("Enter only the connection address. Put the port in the Port field.", comment: "")
            messageTone = .warning
            diagnosticMessage = nil
            return
        }
        guard let relayPort = UInt16(port.trimmingCharacters(in: .whitespacesAndNewlines)), relayPort > 0 else {
            message = NSLocalizedString("Enter a valid connection port.", comment: "")
            messageTone = .warning
            diagnosticMessage = nil
            return
        }
        if let warning = CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: normalizedHost) {
            switch warning {
            case .invalidFormat:
                message = relayHostWarningText(warning)
                messageTone = .warning
                diagnosticMessage = nil
                return
            case .loopback, .localName:
                message = relayHostWarningText(warning)
                messageTone = .warning
                diagnosticMessage = nil
                return
            case .privateNetwork:
                guard allowsPrivateOverlay else {
                    message = relayHostWarningText(warning)
                    messageTone = .warning
                    diagnosticMessage = nil
                    return
                }
            }
        }
        let requestResult = model.requestConfigureDevelopmentRelayForUserInterface(
            host: normalizedHost,
            port: relayPort,
            relaySecret: relaySecret.trimmingCharacters(in: .whitespacesAndNewlines),
            attemptAllocation: true,
            allowsPrivateOverlay: allowsPrivateOverlay
        )
        switch requestResult {
        case .started(let requestID):
            syncDevelopmentDraftFromModel()
            pendingOperation = .developmentRelay
            pendingRequestID = requestID
            message = NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
            messageTone = .neutral
            diagnosticMessage = nil
        case .completed(let result):
            applyConfigurationResult(result, operation: .developmentRelay)
        }
    }

    private func generateRelayQRCode() {
        guard let onGenerateRemotePairingQRCode else { return }
        pendingPairingRefresh = PendingConnectionRecoveryPairingRefresh(
            previousSessionID: model.pairingSession?.id
        )
        message = NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
        messageTone = .neutral
        diagnosticMessage = nil
        onGenerateRemotePairingQRCode()
        resolvePendingPairingRefresh()
    }

    private func resolvePendingPairingRefresh() {
        guard let pendingPairingRefresh else { return }
        switch connectionRecoveryPairingRefreshResolution(
            request: pendingPairingRefresh,
            currentSessionID: model.pairingSession?.id,
            isPreparationInFlight: model.isRemoteRoutePreparationInFlight
        ) {
        case .pending:
            message = NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
            messageTone = .neutral
            diagnosticMessage = nil
        case .succeeded:
            self.pendingPairingRefresh = nil
            message = NSLocalizedString("Latest connection QR generated. Scan it in AetherLink to pair or refresh connectivity.", comment: "")
            messageTone = .ready
            diagnosticMessage = nil
        case .failed:
            self.pendingPairingRefresh = nil
            if let issue = model.remoteRoutePreparationIssue {
                message = remoteRoutePreparationIssueText(issue)
                diagnosticMessage = issue.message.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
            } else {
                message = NSLocalizedString("Connection details could not be prepared automatically. Check Connection Recovery, then generate a fresh QR.", comment: "")
                diagnosticMessage = nil
            }
            messageTone = .warning
        }
    }

    private func syncFromModel(force: Bool = false) {
        syncBootstrapDraftFromModel(force: force)
        syncDevelopmentDraftFromModel(force: force)
    }

    private func reconcileConfigurationRequestState() {
        switch connectionRecoveryConfigurationRequestResolution(
            state: model.relayConfigurationRequestState
        ) {
        case .unchanged:
            return
        case .pending(let context):
            pendingOperation = context.operation
            pendingRequestID = context.requestID
            message = NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
            messageTone = .neutral
            diagnosticMessage = nil
        case .completed(let completion):
            pendingOperation = completion.operation
            pendingRequestID = completion.requestID
            applyConfigurationResult(completion.result, operation: completion.operation)
            model.acknowledgeRelayConfigurationRequestCompletion(
                requestID: completion.requestID
            )
        }
    }

    private func syncBootstrapDraftFromModel(force: Bool = false) {
        let current = ConnectionRecoveryBootstrapDraft(
            endpoints: bootstrapEndpoints,
            allocationToken: bootstrapAllocationToken,
            allowsPrivateOverlay: bootstrapAllowsPrivateOverlay
        )
        let reconciliation = reconcileConnectionRecoveryDraft(
            current: current,
            revision: bootstrapDraftRevision,
            incomingModelValue: ConnectionRecoveryBootstrapDraft(settings: model.bootstrapRelaySettings),
            force: force
        )
        bootstrapEndpoints = reconciliation.draft.endpoints
        bootstrapAllocationToken = reconciliation.draft.allocationToken
        bootstrapAllowsPrivateOverlay = reconciliation.draft.allowsPrivateOverlay
        bootstrapDraftRevision = reconciliation.revision
    }

    private func syncDevelopmentDraftFromModel(force: Bool = false) {
        let current = ConnectionRecoveryDevelopmentDraft(
            host: host,
            port: port,
            relaySecret: relaySecret,
            allowsPrivateOverlay: allowsPrivateOverlay
        )
        let reconciliation = reconcileConnectionRecoveryDraft(
            current: current,
            revision: developmentDraftRevision,
            incomingModelValue: ConnectionRecoveryDevelopmentDraft(settings: model.developmentRelaySettings),
            force: force
        )
        host = reconciliation.draft.host
        port = reconciliation.draft.port
        relaySecret = reconciliation.draft.relaySecret
        allowsPrivateOverlay = reconciliation.draft.allowsPrivateOverlay
        developmentDraftRevision = reconciliation.revision
    }

    private func saveBootstrapRelay() {
        let requestResult = model.requestConfigureBootstrapRelayForUserInterface(
            endpoints: bootstrapEndpoints,
            allocationToken: bootstrapAllocationToken,
            allowsPrivateOverlay: bootstrapAllowsPrivateOverlay
        )
        switch requestResult {
        case .started(let requestID):
            syncBootstrapDraftFromModel()
            pendingOperation = .bootstrapRelay
            pendingRequestID = requestID
            message = NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
            messageTone = .neutral
            diagnosticMessage = nil
        case .completed(let result):
            applyConfigurationResult(result, operation: .bootstrapRelay)
        }
    }

    private func applyConfigurationResult(
        _ result: CompanionRelayConfigurationResult,
        operation: CompanionRelayConfigurationOperation,
        fallback: String? = nil
    ) {
        pendingOperation = nil
        pendingRequestID = nil
        let forceDraftResync = connectionRecoveryResultAllowsDraftResync(result)
        switch operation {
        case .bootstrapRelay:
            syncBootstrapDraftFromModel(force: forceDraftResync)
        case .developmentRelay:
            syncDevelopmentDraftFromModel(force: forceDraftResync)
        }
        if operation == .bootstrapRelay, result == .disabled {
            message = NSLocalizedString("Saved bootstrap relay removed.", comment: "")
            messageTone = .ready
            diagnosticMessage = nil
            return
        }
        let resolvedFallback = fallback ?? (operation == .bootstrapRelay
            ? NSLocalizedString("Bootstrap relay saved. Generate the latest QR and scan it in AetherLink to pair or refresh connectivity.", comment: "")
            : NSLocalizedString("Connection details saved. Generate the latest QR and scan it in AetherLink to pair or refresh connectivity.", comment: ""))
        message = relaySaveMessage(for: result, fallback: resolvedFallback)
        messageTone = relaySaveTone(for: result)
        diagnosticMessage = relaySaveDiagnostic(for: result)
    }

    private func relayHostWarningText(_ warning: CompanionDevelopmentRelaySettings.HostReachabilityWarning) -> String {
        switch warning {
        case .invalidFormat:
            return NSLocalizedString("Enter only the connection address. Put the port in the Port field.", comment: "")
        case .loopback:
            return NSLocalizedString("This connection address points back to AetherLink Runtime. A device on another network cannot reach it.", comment: "")
        case .privateNetwork:
            return NSLocalizedString("This connection address is private. Use a public address, or enable Private Overlay Route only when a VPN or tunnel makes it reachable from both devices.", comment: "")
        case .localName:
            return NSLocalizedString("This connection address is local-network only. Use a public, VPN, or tunnel address for different networks.", comment: "")
        }
    }

    private func relaySaveMessage(for result: CompanionRelayConfigurationResult, fallback: String) -> String {
        switch result {
        case .disabled:
            return NSLocalizedString("Saved connection details removed.", comment: "")
        case .savedStatic:
            return fallback
        case .allocated:
            return NSLocalizedString("Connection details prepared and saved. Generate the latest QR and scan it in AetherLink to pair or refresh connectivity.", comment: "")
        case .allocationFailed:
            return NSLocalizedString("Connection details saved, but preparation failed. Check Connection Recovery, then generate the latest QR again or save the connection again.", comment: "")
        }
    }

    private func relaySaveDiagnostic(for result: CompanionRelayConfigurationResult) -> String? {
        switch result {
        case .allocationFailed(_, let detail):
            return detail.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        case .disabled, .savedStatic, .allocated:
            return nil
        }
    }

    private func relaySaveTone(for result: CompanionRelayConfigurationResult) -> StatusTone {
        switch result {
        case .disabled, .savedStatic, .allocated:
            return .ready
        case .allocationFailed:
            return .warning
        }
    }

    private var shouldShowPrivateOverlayToggle: Bool {
        guard let normalizedHost = normalizedRelayHost(host.trimmingCharacters(in: .whitespacesAndNewlines)) else {
            return allowsPrivateOverlay
        }
        return allowsPrivateOverlay ||
            CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: normalizedHost) == .privateNetwork
    }
}

private struct RelayStatusRow: View {
    let title: String
    let value: String
    let detail: String
    let tone: StatusTone

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            StatusPill(text: value, tone: tone)
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text(relayStatusRowAccessibilityLabel(title: title, value: value, detail: detail)))
    }
}

private struct DiagnosticDisclosure: View {
    let title: String
    let accessibilityContext: String
    let text: String
    @State private var isExpanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            Text(sanitizedRouteDiagnosticDisclosureText(text))
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 4)
        } label: {
            Text(title)
                .font(.caption.weight(.medium))
        }
        .tint(.secondary)
        .accessibilityLabel(Text(routeDiagnosticDisclosureAccessibilityLabel(context: accessibilityContext)))
        .accessibilityValue(Text(routeDiagnosticDisclosureAccessibilityValue(isExpanded: isExpanded)))
        .accessibilityHint(Text(routeDiagnosticDisclosureAccessibilityHint()))
    }
}

func connectionRecoveryDisclosureAccessibilityLabel() -> String {
    NSLocalizedString("Connection Recovery settings", comment: "")
}

func connectionRecoveryDisclosureAccessibilityValue(isExpanded: Bool) -> String {
    isExpanded
        ? NSLocalizedString("Connection Recovery settings expanded", comment: "")
        : NSLocalizedString("Connection Recovery settings collapsed", comment: "")
}

func connectionRecoveryDisclosureAccessibilityHint() -> String {
    NSLocalizedString("Show or hide advanced connection recovery fields.", comment: "")
}

func routeDiagnosticDisclosureAccessibilityLabel(context: String) -> String {
    let trimmedContext = context.trimmingCharacters(in: .whitespacesAndNewlines)
    let resolvedContext = trimmedContext.isEmpty
        ? NSLocalizedString("Connection diagnostics", comment: "")
        : trimmedContext
    return String(
        format: NSLocalizedString("Technical details for %@", comment: ""),
        resolvedContext
    )
}

func routeDiagnosticDisclosureAccessibilityValue(isExpanded: Bool) -> String {
    isExpanded
        ? NSLocalizedString("Connection diagnostics expanded", comment: "")
        : NSLocalizedString("Connection diagnostics collapsed", comment: "")
}

func routeDiagnosticDisclosureAccessibilityHint() -> String {
    NSLocalizedString("Show or hide connection diagnostic details.", comment: "")
}

func connectionRecoveryResultAccessibilityLabel(message: String, tone: StatusTone) -> String {
    let resolvedMessage = message.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        ?? NSLocalizedString("No details available.", comment: "")
    let status: String
    switch tone {
    case .ready:
        status = NSLocalizedString("Ready", comment: "")
    case .warning:
        status = NSLocalizedString("Needs attention", comment: "")
    case .inactive:
        status = NSLocalizedString("Not ready", comment: "")
    case .neutral:
        status = NSLocalizedString("Pending", comment: "")
    }
    return String(
        format: NSLocalizedString("%@. Status %@. %@", comment: ""),
        NSLocalizedString("Connection Recovery result", comment: ""),
        status,
        resolvedMessage
    )
}

func connectionRecoveryHostWarningAccessibilityLabel(message: String) -> String {
    let resolvedMessage = message.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        ?? NSLocalizedString("No details available.", comment: "")
    return String(
        format: NSLocalizedString("%@. Status %@. %@", comment: ""),
        NSLocalizedString("Connection Recovery warning", comment: ""),
        NSLocalizedString("Needs attention", comment: ""),
        resolvedMessage
    )
}

func relayStatusRowAccessibilityLabel(title: String, value: String, detail: String) -> String {
    let resolvedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        ?? NSLocalizedString("Connection setting", comment: "")
    let resolvedValue = value.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        ?? NSLocalizedString("Not checked", comment: "")
    let resolvedDetail = detail.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        ?? NSLocalizedString("No details available.", comment: "")
    return String(
        format: NSLocalizedString("Connection setting %@. Status %@. %@", comment: ""),
        resolvedTitle,
        resolvedValue,
        resolvedDetail
    )
}

func removeSavedConnectionDetailsAccessibilityLabel(endpoint: String?) -> String {
    let trimmedEndpoint = endpoint?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    let resolvedEndpoint = trimmedEndpoint.isEmpty
        ? NSLocalizedString("saved connection", comment: "")
        : trimmedEndpoint
    return String(
        format: NSLocalizedString("Remove saved connection details for %@", comment: ""),
        resolvedEndpoint
    )
}

func cancelRemoveSavedConnectionDetailsAccessibilityLabel(endpoint: String?) -> String {
    let trimmedEndpoint = endpoint?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    let resolvedEndpoint = trimmedEndpoint.isEmpty
        ? NSLocalizedString("saved connection", comment: "")
        : trimmedEndpoint
    return String(
        format: NSLocalizedString("Cancel removing saved connection details for %@", comment: ""),
        resolvedEndpoint
    )
}

func removeSavedConnectionDetailsAccessibilityHint() -> String {
    NSLocalizedString("Remove saved fallback connection details used for future pairing QR routes.", comment: "")
}

func removeSavedBootstrapRelayAccessibilityLabel(endpoints: String?) -> String {
    let trimmedEndpoints = endpoints?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    let resolvedEndpoints = trimmedEndpoints.isEmpty
        ? NSLocalizedString("saved bootstrap relay", comment: "")
        : trimmedEndpoints
    return String(
        format: NSLocalizedString("Remove bootstrap relay settings for %@", comment: ""),
        resolvedEndpoints
    )
}

func removeSavedBootstrapRelayAccessibilityHint() -> String {
    NSLocalizedString("Remove saved bootstrap relay settings used to prepare pairing QR connection details.", comment: "")
}

func cancelRemoveSavedBootstrapRelayAccessibilityLabel(endpoints: String?) -> String {
    let trimmedEndpoints = endpoints?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    let resolvedEndpoints = trimmedEndpoints.isEmpty
        ? NSLocalizedString("saved bootstrap relay", comment: "")
        : trimmedEndpoints
    return String(
        format: NSLocalizedString("Cancel removing bootstrap relay settings for %@", comment: ""),
        resolvedEndpoints
    )
}

func connectionRecoveryTextFieldAccessibilityValue(_ value: String) -> String {
    value.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        ?? NSLocalizedString("Empty", comment: "")
}

func connectionRecoveryOptionalSecureFieldAccessibilityValue(_ value: String) -> String {
    connectionRecoverySecureFieldAccessibilityValue(
        value,
        emptyValue: NSLocalizedString("Optional", comment: "")
    )
}

func connectionRecoveryGeneratedSecretAccessibilityValue(_ value: String) -> String {
    connectionRecoverySecureFieldAccessibilityValue(
        value,
        emptyValue: NSLocalizedString("Generated automatically if blank", comment: "")
    )
}

func connectionRecoveryGenerateLatestQRActionAccessibilityValue(
    isRouteReadyForQRCode: Bool,
    canPrepareRoute: Bool = false,
    hasAction: Bool = true,
    isPreparing: Bool = false
) -> String {
    if !hasAction {
        return NSLocalizedString("Unavailable", comment: "")
    }
    if isPreparing {
        return NSLocalizedString("Connection preparation in progress", comment: "")
    }
    if canPrepareRoute && !isRouteReadyForQRCode {
        return NSLocalizedString("Connection preparation available", comment: "")
    }
    if !isRouteReadyForQRCode {
        return NSLocalizedString("Connection details not ready", comment: "")
    }
    return NSLocalizedString("Ready", comment: "")
}

func connectionRecoveryGenerateLatestQRActionAccessibilityHint(
    isRouteReadyForQRCode: Bool,
    canPrepareRoute: Bool = false,
    hasAction: Bool = true,
    isPreparing: Bool = false
) -> String {
    if !hasAction {
        return NSLocalizedString("Latest QR generation is unavailable from this view.", comment: "")
    }
    if isPreparing {
        return NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
    }
    if canPrepareRoute && !isRouteReadyForQRCode {
        return NSLocalizedString("Prepare connection details and generate the latest pairing QR.", comment: "")
    }
    if !isRouteReadyForQRCode {
        return NSLocalizedString("Connection details are not ready for QR generation. Check Connection Recovery settings.", comment: "")
    }
    return NSLocalizedString("Generate the latest pairing QR with saved connection details.", comment: "")
}

func connectionRecoveryGenerateLatestQRActionAvailable(
    canRequestRemotePairing: Bool,
    hasAction: Bool = true
) -> Bool {
    hasAction && canRequestRemotePairing
}

func connectionRecoverySaveBootstrapRelayActionAccessibilityHint() -> String {
    NSLocalizedString("Save bootstrap relay settings for future pairing QR connection details.", comment: "")
}

func connectionRecoveryBootstrapAllocationTokenWarning(endpoints: String, allocationToken: String) -> String? {
    guard allocationToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
        return nil
    }
    guard bootstrapRelayEndpointsNeedAllocationToken(endpoints) else {
        return nil
    }
    return NSLocalizedString("Add an allocation token before using a non-local bootstrap relay.", comment: "")
}

func connectionRecoveryBootstrapAllocationTokenAccessibilityValue(endpoints: String, allocationToken: String) -> String {
    if connectionRecoveryBootstrapAllocationTokenWarning(endpoints: endpoints, allocationToken: allocationToken) != nil {
        return NSLocalizedString("Missing token for non-local bootstrap relay", comment: "")
    }
    return connectionRecoveryOptionalSecureFieldAccessibilityValue(allocationToken)
}

func connectionRecoverySaveBootstrapRelayActionAccessibilityValue(
    endpoints: String,
    allocationToken: String = ""
) -> String {
    if endpoints.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
        return NSLocalizedString("Will remove saved bootstrap relay", comment: "")
    }
    if connectionRecoveryBootstrapAllocationTokenWarning(endpoints: endpoints, allocationToken: allocationToken) != nil {
        return NSLocalizedString("Missing token for non-local bootstrap relay", comment: "")
    }
    return NSLocalizedString("Ready", comment: "")
}

func connectionRecoverySaveConnectionActionAccessibilityHint() -> String {
    NSLocalizedString("Save fallback connection details for future pairing QR routes.", comment: "")
}

func connectionRecoverySaveConnectionActionAccessibilityValue(host: String, port: String) -> String {
    let trimmedHost = host.trimmingCharacters(in: .whitespacesAndNewlines)
    if trimmedHost.isEmpty {
        return NSLocalizedString("Enter a connection address.", comment: "")
    }
    if normalizedRelayHost(trimmedHost) == nil {
        return NSLocalizedString("Enter only the connection address. Put the port in the Port field.", comment: "")
    }
    guard let relayPort = UInt16(port.trimmingCharacters(in: .whitespacesAndNewlines)), relayPort > 0 else {
        return NSLocalizedString("Enter a valid connection port.", comment: "")
    }
    return NSLocalizedString("Ready", comment: "")
}

func connectionRecoveryRotateSecretActionAccessibilityHint() -> String {
    NSLocalizedString("Create a new connection setup secret for future pairing QR connection details.", comment: "")
}

func connectionRecoveryBootstrapPrivateOverlayRouteAccessibilityLabel() -> String {
    NSLocalizedString("Bootstrap relay Private Overlay Route", comment: "")
}

func connectionRecoveryFallbackPrivateOverlayRouteAccessibilityLabel() -> String {
    NSLocalizedString("Fallback connection Private Overlay Route", comment: "")
}

func connectionRecoveryPrivateOverlayRouteAccessibilityValue(isEnabled: Bool) -> String {
    isEnabled
        ? NSLocalizedString("Enabled", comment: "")
        : NSLocalizedString("Disabled", comment: "")
}

private func connectionRecoverySecureFieldAccessibilityValue(
    _ value: String,
    emptyValue: String
) -> String {
    value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        ? emptyValue
        : NSLocalizedString("Entered", comment: "")
}

func sanitizedRouteDiagnosticDisclosureText(_ diagnostic: String) -> String {
    sanitizedTechnicalDiagnostic(diagnostic)
        ?? NSLocalizedString("Sensitive technical detail redacted.", comment: "")
}

private extension String {
    var nilIfEmpty: String? {
        isEmpty ? nil : self
    }
}

private func normalizedRelayHost(_ value: String) -> String? {
    let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { return nil }
    guard trimmed.rangeOfCharacter(from: .whitespacesAndNewlines) == nil else { return nil }
    guard !trimmed.contains("://"),
          !trimmed.contains("/"),
          !trimmed.contains("?"),
          !trimmed.contains("#"),
          !trimmed.contains("@")
    else {
        return nil
    }
    let colonCount = trimmed.reduce(0) { count, character in
        character == ":" ? count + 1 : count
    }
    guard colonCount != 1 else { return nil }
    if trimmed.hasPrefix("[") || trimmed.hasSuffix("]") {
        let unbracketed = trimmed.trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        return unbracketed.isEmpty ? nil : unbracketed
    }
    return trimmed
}

func bootstrapRelayEndpointsNeedAllocationToken(_ endpoints: String) -> Bool {
    bootstrapRelayEndpointCandidates(endpoints).contains { endpoint in
        guard let host = bootstrapRelayHost(from: endpoint) else {
            return true
        }
        return bootstrapRelayHostRequiresAllocationToken(host)
    }
}

private func bootstrapRelayEndpointCandidates(_ endpoints: String) -> [String] {
    endpoints
        .split { character in
            character == "," || character == ";" || character.isNewline
        }
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
}

private func bootstrapRelayHost(from endpoint: String) -> String? {
    let trimmed = endpoint.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { return nil }

    if trimmed.contains("://") {
        return URLComponents(string: trimmed)?.host?.nilIfEmpty
    }

    let endpointWithoutPath = trimmed.split { character in
        character == "/" || character == "?" || character == "#"
    }.first.map(String.init) ?? trimmed
    let endpointWithoutUserInfo = endpointWithoutPath.split(separator: "@").last.map(String.init) ?? endpointWithoutPath

    if endpointWithoutUserInfo.hasPrefix("["),
       let closingBracket = endpointWithoutUserInfo.firstIndex(of: "]") {
        let hostStart = endpointWithoutUserInfo.index(after: endpointWithoutUserInfo.startIndex)
        return String(endpointWithoutUserInfo[hostStart..<closingBracket]).nilIfEmpty
    }

    let colonCount = endpointWithoutUserInfo.reduce(0) { count, character in
        character == ":" ? count + 1 : count
    }
    if colonCount == 1,
       let separator = endpointWithoutUserInfo.firstIndex(of: ":") {
        return String(endpointWithoutUserInfo[..<separator]).nilIfEmpty
    }
    return endpointWithoutUserInfo.nilIfEmpty
}

private func bootstrapRelayHostRequiresAllocationToken(_ host: String) -> Bool {
    let normalizedHost = host
        .trimmingCharacters(in: .whitespacesAndNewlines)
        .trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        .lowercased()
        .split(separator: "%", maxSplits: 1)
        .first
        .map(String.init) ?? ""
    guard !normalizedHost.isEmpty else {
        return false
    }
    if normalizedHost == "localhost"
        || normalizedHost.hasSuffix(".localhost")
        || normalizedHost.hasSuffix(".local") {
        return false
    }
    if let octets = bootstrapRelayIPv4Octets(normalizedHost) {
        if octets == [0, 0, 0, 0] || octets[0] == 127 {
            return false
        }
        if octets[0] == 169 && octets[1] == 254 {
            return false
        }
        return true
    }
    if normalizedHost == "::"
        || normalizedHost == "::1"
        || normalizedHost == "0:0:0:0:0:0:0:1"
        || normalizedHost.hasPrefix("fe80:") {
        return false
    }
    return true
}

private func bootstrapRelayIPv4Octets(_ host: String) -> [Int]? {
    let parts = host.split(separator: ".", omittingEmptySubsequences: false)
    guard parts.count == 4 else {
        return nil
    }
    let octets = parts.compactMap { part -> Int? in
        guard !part.isEmpty, part.allSatisfy(\.isNumber) else {
            return nil
        }
        guard let value = Int(part), (0...255).contains(value) else {
            return nil
        }
        return value
    }
    return octets.count == 4 ? octets : nil
}
