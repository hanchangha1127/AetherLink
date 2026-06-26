import CompanionCore
import SwiftUI

@MainActor
func shouldShowRouteDiagnosticsPanel(model: CompanionAppModel) -> Bool {
    model.hasDevelopmentRelayRoute
        || !model.canPrepareRemoteRelayRouteAutomatically
        || model.remoteRoutePreparationIssue != nil
}

struct RemoteRelayRoutePanel: View {
    @ObservedObject var model: CompanionAppModel
    var onGenerateRelayQRCode: (() -> Void)?
    @State private var host = ""
    @State private var port = "43171"
    @State private var relaySecret = ""
    @State private var allowsPrivateOverlay = false
    @State private var message: String?
    @State private var messageTone = StatusTone.neutral
    @State private var diagnosticMessage: String?
    @State private var isAdvancedRouteSettingsExpanded = false
    @State private var isDisableConnectionConfirmationPresented = false

    var body: some View {
        CompanionPanel(title: NSLocalizedString("Advanced Connection Setup", comment: ""), systemImage: "point.3.connected.trianglepath.dotted") {
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
                }

                if let diagnosticMessage {
                    DiagnosticDisclosure(
                        title: NSLocalizedString("Technical Details", comment: ""),
                        text: diagnosticMessage
                    )
                }
            }
        }
        .onAppear(perform: syncFromModel)
        .onChange(of: model.developmentRelaySettings) { _, _ in
            syncFromModel()
        }
        .confirmationDialog(
            NSLocalizedString("Disable saved connection details?", comment: ""),
            isPresented: $isDisableConnectionConfirmationPresented,
            titleVisibility: .visible
        ) {
            Button(NSLocalizedString("Disable Connection", comment: ""), role: .destructive) {
                model.clearDevelopmentRelay()
                syncFromModel()
                message = NSLocalizedString("Advanced connection disabled.", comment: "")
                messageTone = .neutral
            }
            Button(NSLocalizedString("Cancel", comment: ""), role: .cancel) {}
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
                Button {
                    generateRelayQRCode()
                } label: {
                    Label(NSLocalizedString("Generate Latest QR", comment: ""), systemImage: "qrcode")
                }
                .buttonStyle(.bordered)
                .disabled(!model.isDevelopmentRelayRouteEligibleForQRCode || onGenerateRelayQRCode == nil)

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

                    HStack(spacing: 8) {
                        TextField(NSLocalizedString("Connection address", comment: ""), text: $host)
                            .textFieldStyle(.roundedBorder)
                        TextField(NSLocalizedString("Port", comment: ""), text: $port)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 86)
                    }

                    SecureField(NSLocalizedString("Connection setup secret", comment: ""), text: $relaySecret, prompt: Text(NSLocalizedString("Generated automatically if blank", comment: "")))
                        .textFieldStyle(.roundedBorder)

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
                    }

                    HStack(spacing: 8) {
                        Button {
                            saveRelay()
                        } label: {
                            Label(NSLocalizedString("Save Connection", comment: ""), systemImage: "externaldrive.badge.checkmark")
                        }
                        .buttonStyle(.bordered)

                        Button {
                            model.regenerateDevelopmentRelaySecret()
                            syncFromModel()
                            message = NSLocalizedString("Connection setup secret regenerated.", comment: "")
                            messageTone = .ready
                        } label: {
                            Label(NSLocalizedString("Rotate Secret", comment: ""), systemImage: "key")
                        }
                        .buttonStyle(.bordered)

                        if settings.isEnabled {
                            Button(role: .destructive) {
                                isDisableConnectionConfirmationPresented = true
                            } label: {
                                Label(NSLocalizedString("Disable Connection", comment: ""), systemImage: "xmark.circle")
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                }
                .padding(.top, 4)
            } label: {
                Label(NSLocalizedString("Advanced Connection Setup", comment: ""), systemImage: "wrench.and.screwdriver")
                    .font(.caption.weight(.medium))
            }
            .tint(.secondary)

            relayHostWarning(settings: settings)
        }
    }

    @ViewBuilder
    private func relayHostWarning(settings: CompanionDevelopmentRelaySettings) -> some View {
        if let warning = settings.hostReachabilityWarning {
            Label(relayHostWarningText(warning), systemImage: "exclamationmark.triangle")
                .font(.caption)
                .foregroundStyle(StatusTone.warning.color)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    @ViewBuilder
    private var relayStatus: some View {
        let settings = model.developmentRelaySettings
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                StatusPill(
                    text: settings.isEnabled
                        ? NSLocalizedString("Connection details saved", comment: "")
                        : NSLocalizedString("No connection details", comment: ""),
                    tone: settings.isEnabled ? (settings.frameEncryptionEnabled ? .ready : .warning) : .inactive
                )
                Text(relayStatusText(settings: settings))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack(alignment: .firstTextBaseline, spacing: 8) {
                StatusPill(
                    text: relayConnectionLabel(model.developmentRelayConnectionStatus),
                    tone: relayConnectionTone(model.developmentRelayConnectionStatus, isEnabled: settings.isEnabled)
                )
                Text(relayConnectionDetail(status: model.developmentRelayConnectionStatus, settings: settings))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let diagnostic = relayConnectionDiagnostic(status: model.developmentRelayConnectionStatus) {
                DiagnosticDisclosure(
                    title: NSLocalizedString("Technical Details", comment: ""),
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
                        text: diagnostic
                    )
                }
            }
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
            return String(
                format: NSLocalizedString("Connection through %@ failed. Check Advanced Connection Setup, then try again.", comment: ""),
                endpoint
            )
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
            message = NSLocalizedString("Enter only a connection address. Put the port in the port field.", comment: "")
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
        let result = model.configureDevelopmentRelay(
            host: normalizedHost,
            port: relayPort,
            relaySecret: relaySecret.trimmingCharacters(in: .whitespacesAndNewlines),
            attemptAllocation: true,
            allowsPrivateOverlay: allowsPrivateOverlay
        )
        syncFromModel()
        message = relaySaveMessage(
            for: result,
            fallback: NSLocalizedString("Connection details saved. Generate the latest QR and scan it in AetherLink to pair or refresh connectivity.", comment: "")
        )
        messageTone = relaySaveTone(for: result)
        diagnosticMessage = relaySaveDiagnostic(for: result)
    }

    private func generateRelayQRCode() {
        guard let onGenerateRelayQRCode else { return }
        onGenerateRelayQRCode()
        diagnosticMessage = nil
        if model.pairingSession != nil {
            message = NSLocalizedString("Latest connection QR generated. Scan it in AetherLink to pair or refresh connectivity.", comment: "")
            messageTone = .ready
        } else if model.isDevelopmentRelayRouteEligibleForQRCode {
            message = NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
            messageTone = .neutral
        } else {
            message = NSLocalizedString("Connection details cannot be included in QR. Advanced Connection Setup needs an address reachable by both devices.", comment: "")
            messageTone = .warning
        }
    }

    private func syncFromModel() {
        let settings = model.developmentRelaySettings
        host = settings.host
        port = settings.isEnabled ? String(settings.port) : "43171"
        relaySecret = settings.relaySecret ?? ""
        allowsPrivateOverlay = settings.allowsPrivateOverlay
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
            return NSLocalizedString("Advanced connection disabled.", comment: "")
        case .savedStatic:
            return fallback
        case .allocated:
            return NSLocalizedString("Connection details prepared and saved. Generate the latest QR and scan it in AetherLink to pair or refresh connectivity.", comment: "")
        case .allocationFailed:
            return NSLocalizedString("Connection details saved, but preparation failed. Check Advanced Connection Setup, then generate the latest QR again or save the connection again.", comment: "")
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

private struct DiagnosticDisclosure: View {
    let title: String
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
    }
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
