import CompanionCore
import Foundation
import OllamaBackend
import SwiftUI

struct StatusView: View {
    @ObservedObject var model: CompanionAppModel
    var onGenerateRelayQRCode: (() -> Void)?
    private let columns = [GridItem(.adaptive(minimum: 240), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                CompanionPageHeader(
                    title: NSLocalizedString("AetherLink Runtime", comment: ""),
                    subtitle: NSLocalizedString("Bridge trusted client devices through this local runtime to local models.", comment: ""),
                    systemImage: "bolt.horizontal.circle.fill"
                )

                RuntimeOverviewPanel(overview: runtimeOverview)

                LazyVGrid(columns: columns, alignment: .leading, spacing: 12) {
                    StatusCard(
                        title: NSLocalizedString("Runtime", comment: ""),
                        value: localizedTransportStatus(model.transportState),
                        detail: runtimeDetail,
                        systemImage: "antenna.radiowaves.left.and.right",
                        tone: transportTone(for: model.transportState)
                    )
                    StatusCard(
                        title: NSLocalizedString("Connection Routes", comment: ""),
                        value: connectionRouteValue,
                        detail: connectionRouteDetail,
                        systemImage: "point.3.connected.trianglepath.dotted",
                        tone: connectionRouteTone
                    )
                    StatusCard(
                        title: NSLocalizedString("Model Providers", comment: ""),
                        value: backendSummary.value,
                        detail: backendSummary.detail,
                        systemImage: "cpu",
                        tone: backendSummary.tone
                    )
                    StatusCard(
                        title: NSLocalizedString("Trusted Devices", comment: ""),
                        value: trustedDeviceCount,
                        detail: trustedDeviceDetail,
                        systemImage: "lock.shield",
                        tone: model.trustedDevices.isEmpty ? .inactive : .ready
                    )
                    StatusCard(
                        title: NSLocalizedString("Model Residency", comment: ""),
                        value: modelResidencyValue,
                        detail: modelResidencyDetail,
                        systemImage: "memorychip",
                        tone: modelResidencyTone
                    )
                }

                CompanionPanel(title: NSLocalizedString("Readiness", comment: ""), systemImage: "checklist") {
                    VStack(spacing: 0) {
                        ForEach(readinessItems) { item in
                            ReadinessRow(item: item)
                            if item.id != readinessItems.last?.id {
                                Divider()
                            }
                        }
                    }
                }

                CompanionPanel(title: NSLocalizedString("Quick Actions", comment: ""), systemImage: "bolt.horizontal") {
                    HStack(spacing: 10) {
                        Button {
                            onGenerateRelayQRCode?()
                        } label: {
                            if model.pairingSession == nil {
                                Label(NSLocalizedString("Start Pairing", comment: ""), systemImage: "qrcode")
                            } else {
                                Label(NSLocalizedString("Generate New Code", comment: ""), systemImage: "arrow.triangle.2.circlepath")
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(onGenerateRelayQRCode == nil)

                        Button {
                            Task { await model.refreshBackendStatus() }
                        } label: {
                            Label(NSLocalizedString("Check Model Providers", comment: ""), systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.bordered)

                        Button {
                            Task { await model.loadModels() }
                        } label: {
                            Label(NSLocalizedString("Load Local Models", comment: ""), systemImage: "shippingbox")
                        }
                        .buttonStyle(.bordered)
                    }
                    .controlSize(.regular)
                }

                CompanionPanel(title: NSLocalizedString("Model Providers", comment: ""), systemImage: "server.rack") {
                    VStack(spacing: 0) {
                        ForEach(providerStatuses) { provider in
                            ProviderStatusRow(status: provider)
                            if provider.id != providerStatuses.last?.id {
                                Divider()
                            }
                        }
                    }
                }

                CompanionPanel(title: NSLocalizedString("Local Models", comment: ""), systemImage: "shippingbox") {
                    if model.models.isEmpty {
                        ContentUnavailableView(
                            NSLocalizedString("No local models loaded", comment: ""),
                            systemImage: "shippingbox",
                            description: Text(NSLocalizedString("Load models to confirm what client devices can request through this local runtime.", comment: ""))
                        )
                        .frame(maxWidth: .infinity, minHeight: 180)
                    } else {
                        VStack(spacing: 0) {
                            ForEach(modelGroups) { group in
                                ModelGroupSection(group: group)
                                if group.id != modelGroups.last?.id {
                                    Divider()
                                }
                            }
                        }
                    }
                }

                DevelopmentRelayPanel(
                    model: model,
                    onGenerateRelayQRCode: onGenerateRelayQRCode
                )
            }
            .padding(24)
            .frame(maxWidth: 920, alignment: .leading)
        }
    }

    private var runtimeDetail: String {
        switch model.transportState.state {
        case .advertising:
            return NSLocalizedString("Trusted devices can resolve the current local route after pairing.", comment: "")
        case .failed:
            return model.transportState.failureMessage
                ?? NSLocalizedString("Runtime listener could not start.", comment: "")
        case .stopped:
            return NSLocalizedString("The local runtime listener is not active.", comment: "")
        }
    }

    private var connectionRouteValue: String {
        guard model.transportState.state == .advertising else {
            return NSLocalizedString("Not ready", comment: "")
        }
        return model.hasDevelopmentRelayRoute
            ? NSLocalizedString("Local + development relay", comment: "")
            : NSLocalizedString("Local route", comment: "")
    }

    private var connectionRouteDetail: String {
        guard model.transportState.state == .advertising else {
            return NSLocalizedString("Start the runtime listener before resolving routes.", comment: "")
        }
        if model.hasDevelopmentRelayRoute {
            let endpoint = model.developmentRelayEndpoint ?? NSLocalizedString("configured relay", comment: "")
            if model.relayFrameEncryptionEnabled {
                return String(
                    format: NSLocalizedString("Development relay %@ is configured; relay frame bodies are encrypted, but production P2P remains roadmap.", comment: ""),
                    endpoint
                )
            }
            return String(
                format: NSLocalizedString("Development relay %@ is configured without relay_secret; use only for testing until encrypted session setup is complete.", comment: ""),
                endpoint
            )
        }
        return NSLocalizedString("Local discovery/direct routes are available after pairing. Different-network production P2P remains roadmap.", comment: "")
    }

    private var connectionRouteTone: StatusTone {
        guard model.transportState.state == .advertising else {
            return transportTone(for: model.transportState)
        }
        if model.hasDevelopmentRelayRoute {
            switch model.developmentRelayConnectionStatus.status {
            case .ready:
                return model.relayFrameEncryptionEnabled ? .ready : .warning
            case .failed:
                return .warning
            case .connecting, .waitingForPeer, .reconnecting:
                return .neutral
            case .stopped:
                return .inactive
            }
        }
        return .neutral
    }

    private var backendSummary: BackendSummary {
        let statuses = providerStatuses
        if statuses.allSatisfy({ $0.rawStatus == .notChecked }) {
            return BackendSummary(
                value: NSLocalizedString("Not checked", comment: ""),
                detail: NSLocalizedString("Model provider status has not been checked yet.", comment: ""),
                tone: .inactive
            )
        }

        let availableCount = statuses.filter { $0.rawStatus == .available }.count
        if availableCount > 0 {
            return BackendSummary(
                value: String(format: NSLocalizedString("%d of %d available", comment: ""), availableCount, statuses.count),
                detail: NSLocalizedString("At least one model provider is responding.", comment: ""),
                tone: .ready
            )
        }

        return BackendSummary(
            value: NSLocalizedString("Unavailable", comment: ""),
            detail: NSLocalizedString("No model provider is responding.", comment: ""),
            tone: .warning
        )
    }

    private var providerStatuses: [ProviderStatus] {
        model.providerStatuses.map(ProviderStatus.init(status:))
    }

    private var modelGroups: [ModelGroup] {
        let chatModels = model.models.filter { $0.kind == .chat }
        let embeddingModels = model.models.filter { $0.kind == .embedding }

        return [
            ModelGroup(kind: .chat, models: chatModels),
            ModelGroup(kind: .embedding, models: embeddingModels)
        ].filter { !$0.models.isEmpty }
    }

    private var trustedDeviceCount: String {
        String(
            format: NSLocalizedString("%d trusted device(s)", comment: ""),
            model.trustedDevices.count
        )
    }

    private var trustedDeviceDetail: String {
        model.trustedDevices.isEmpty
            ? NSLocalizedString("Pair a client device before allowing runtime requests.", comment: "")
            : NSLocalizedString("Authenticated devices can request runtime sessions.", comment: "")
    }

    private var modelResidencyValue: String {
        guard model.modelResidency.supported else {
            return NSLocalizedString("Not managed", comment: "")
        }
        return model.modelResidency.activeModelID == nil
            ? NSLocalizedString("Idle", comment: "")
            : NSLocalizedString("Active", comment: "")
    }

    private var modelResidencyDetail: String {
        guard model.modelResidency.supported else {
            return NSLocalizedString("Model residency is not managed by this provider.", comment: "")
        }
        if let activeModelID = model.modelResidency.activeModelID,
           let activeProvider = model.modelResidency.activeProvider {
            let minutes = max(1, model.modelResidency.idleUnloadDelaySeconds / 60)
            return String(
                format: NSLocalizedString("%@ %@ active. Idle unload after %d minute(s).", comment: ""),
                localizedProviderName(activeProvider),
                activeModelID,
                minutes
            )
        }
        return model.modelResidency.lastEvent
            ?? NSLocalizedString("No active model is resident through the runtime policy.", comment: "")
    }

    private var modelResidencyTone: StatusTone {
        guard model.modelResidency.supported else {
            return .inactive
        }
        return model.modelResidency.activeModelID == nil ? .neutral : .ready
    }

    private func localizedProviderName(_ provider: ModelProvider) -> String {
        switch provider {
        case .ollama:
            return NSLocalizedString("Ollama", comment: "")
        case .lmStudio:
            return NSLocalizedString("LM Studio", comment: "")
        case .aggregate:
            return NSLocalizedString("Local runtime", comment: "")
        }
    }

    private var readinessItems: [ReadinessItem] {
        [
            ReadinessItem(
                id: "runtime-listener",
                title: NSLocalizedString("Runtime listener", comment: ""),
                detail: runtimeReadinessDetail,
                tone: transportTone(for: model.transportState)
            ),
            ReadinessItem(
                id: "backend-availability",
                title: NSLocalizedString("Model provider availability", comment: ""),
                detail: backendSummary.detail,
                tone: backendSummary.tone
            ),
            ReadinessItem(
                id: "trusted-device-pairing",
                title: NSLocalizedString("Trusted device pairing", comment: ""),
                detail: trustedDeviceDetail,
                tone: model.trustedDevices.isEmpty ? .inactive : .ready
            ),
            ReadinessItem(
                id: "model-list-loaded",
                title: NSLocalizedString("Model list loaded", comment: ""),
                detail: model.models.isEmpty
                    ? NSLocalizedString("Load models to show what this local runtime can offer.", comment: "")
                    : String(format: NSLocalizedString("%d model(s) loaded", comment: ""), model.models.count),
                tone: model.models.isEmpty ? .inactive : .ready
            )
        ]
    }

    private var runtimeReadinessDetail: String {
        switch model.transportState.state {
        case .advertising:
            return NSLocalizedString("Accepting authenticated runtime sessions.", comment: "")
        case .failed:
            return model.transportState.failureMessage
                ?? NSLocalizedString("Runtime listener could not start.", comment: "")
        case .stopped:
            return NSLocalizedString("Start AetherLink Runtime listener.", comment: "")
        }
    }

    private var runtimeOverview: RuntimeOverview {
        if model.transportState.state != .advertising {
            return RuntimeOverview(
                title: NSLocalizedString("Setup needed", comment: ""),
                detail: NSLocalizedString("Start AetherLink Runtime before client devices can connect.", comment: ""),
                footnote: NSLocalizedString("Client requests stay mediated by this local runtime. Ollama and LM Studio are never exposed directly to client devices.", comment: ""),
                tone: transportTone(for: model.transportState)
            )
        }

        if backendSummary.tone != .ready {
            return RuntimeOverview(
                title: NSLocalizedString("Model service needs attention", comment: ""),
                detail: NSLocalizedString("Start Ollama or LM Studio here, then check model providers.", comment: ""),
                footnote: NSLocalizedString("Client requests stay mediated by this local runtime. Ollama and LM Studio are never exposed directly to client devices.", comment: ""),
                tone: backendSummary.tone
            )
        }

        if model.trustedDevices.isEmpty {
            return RuntimeOverview(
                title: NSLocalizedString("Pair a Client Device to Continue", comment: ""),
                detail: NSLocalizedString("Generate a QR pairing code and scan it from the AetherLink client app.", comment: ""),
                footnote: NSLocalizedString("Pairing creates a trusted-device record so the client device can reconnect without entering backend URLs.", comment: ""),
                tone: .inactive
            )
        }

        if model.models.isEmpty {
            return RuntimeOverview(
                title: NSLocalizedString("Load local models", comment: ""),
                detail: NSLocalizedString("Load models so client devices can choose an installed chat model through this local runtime.", comment: ""),
                footnote: NSLocalizedString("Chat and embedding model choices are managed separately so each workflow uses the right model.", comment: ""),
                tone: .neutral
            )
        }

        if model.hasDevelopmentRelayRoute && !model.isDevelopmentRelayQRCodeReady {
            return RuntimeOverview(
                title: NSLocalizedString("Remote route unavailable for QR", comment: ""),
                detail: NSLocalizedString("Use a public, VPN, or tunnel relay address before generating a remote QR.", comment: ""),
                footnote: NSLocalizedString("The client device remains a controller; all model access stays on the runtime host.", comment: ""),
                tone: .neutral
            )
        }

        return RuntimeOverview(
            title: NSLocalizedString("Ready for Client Devices", comment: ""),
            detail: NSLocalizedString("Route ready, model provider responding, trusted devices can chat.", comment: ""),
            footnote: NSLocalizedString("The client device remains a controller; all model access stays on the runtime host.", comment: ""),
            tone: .ready
        )
    }
}

private struct DevelopmentRelayPanel: View {
    @ObservedObject var model: CompanionAppModel
    var onGenerateRelayQRCode: (() -> Void)?
    @State private var host = ""
    @State private var port = "43171"
    @State private var relaySecret = ""
    @State private var message: String?
    @State private var messageTone = StatusTone.neutral
    @State private var isAdvancedSettingsExpanded = false

    var body: some View {
        CompanionPanel(title: NSLocalizedString("Remote Relay", comment: ""), systemImage: "point.3.connected.trianglepath.dotted") {
            VStack(alignment: .leading, spacing: 12) {
                relayStatus

                DisclosureGroup(isExpanded: $isAdvancedSettingsExpanded) {
                    advancedRouteSettings
                        .padding(.top, 8)
                } label: {
                    Label(NSLocalizedString("Advanced Route Settings", comment: ""), systemImage: "slider.horizontal.3")
                        .font(.subheadline.weight(.semibold))
                }

                if let message {
                    Label(message, systemImage: messageTone.systemImage)
                        .font(.caption)
                        .foregroundStyle(messageTone.color)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .onAppear(perform: syncFromModel)
    }

    @ViewBuilder
    private var advancedRouteSettings: some View {
        let settings = model.developmentRelaySettings
        VStack(alignment: .leading, spacing: 12) {
            Text(NSLocalizedString("Use a relay host both devices can reach when they are not on the same network. The relay forwards AetherLink frames only; model providers stay private on this runtime host.", comment: ""))
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 8) {
                TextField(NSLocalizedString("Relay host", comment: ""), text: $host)
                    .textFieldStyle(.roundedBorder)
                TextField(NSLocalizedString("Port", comment: ""), text: $port)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 86)
            }

            SecureField(NSLocalizedString("Relay frame secret", comment: ""), text: $relaySecret, prompt: Text(NSLocalizedString("Generated automatically if blank", comment: "")))
                .textFieldStyle(.roundedBorder)

            HStack(spacing: 8) {
                Button {
                    saveRelay()
                } label: {
                    Label(NSLocalizedString("Save Relay", comment: ""), systemImage: "externaldrive.badge.checkmark")
                }
                .buttonStyle(.bordered)

                Button {
                    model.regenerateDevelopmentRelaySecret()
                    syncFromModel()
                    message = NSLocalizedString("Relay frame secret regenerated.", comment: "")
                    messageTone = .ready
                } label: {
                    Label(NSLocalizedString("Generate Secret", comment: ""), systemImage: "key")
                }
                .buttonStyle(.bordered)

                if settings.isEnabled {
                    Button(role: .destructive) {
                        model.clearDevelopmentRelay()
                        syncFromModel()
                        message = NSLocalizedString("Relay route disabled.", comment: "")
                        messageTone = .neutral
                    } label: {
                        Label(NSLocalizedString("Disable Relay", comment: ""), systemImage: "xmark.circle")
                    }
                    .buttonStyle(.bordered)
                }
            }

            if settings.isEnabled {
                Button {
                    guard let onGenerateRelayQRCode else { return }
                    onGenerateRelayQRCode()
                    message = NSLocalizedString("Latest route QR generated. Scan it from the client app to pair or refresh connectivity.", comment: "")
                    messageTone = .ready
                } label: {
                    Label(NSLocalizedString("Generate Relay QR", comment: ""), systemImage: "qrcode")
                }
                .buttonStyle(.bordered)
                .disabled(!model.shouldIncludeDevelopmentRelayInPairingQRCode || onGenerateRelayQRCode == nil)

                if !model.isDevelopmentRelayQRCodeReady {
                    Label(NSLocalizedString("Use a public, VPN, or tunnel relay address to include it in QR.", comment: ""), systemImage: "info.circle")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

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
                        ? NSLocalizedString("Relay enabled", comment: "")
                        : NSLocalizedString("Relay disabled", comment: ""),
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
        }
    }

    private func relayConnectionLabel(_ status: CompanionDevelopmentRelayStatus) -> String {
        switch status.status {
        case .stopped:
            return NSLocalizedString("Relay not connected", comment: "")
        case .connecting:
            return NSLocalizedString("Relay connecting", comment: "")
        case .waitingForPeer:
            return NSLocalizedString("Relay waiting", comment: "")
        case .ready:
            return NSLocalizedString("Relay connected", comment: "")
        case .reconnecting:
            return NSLocalizedString("Relay reconnecting", comment: "")
        case .failed:
            return NSLocalizedString("Relay failed", comment: "")
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
            return NSLocalizedString("The relay client is off; local discovery remains the active route.", comment: "")
        }
        let endpoint = status.endpoint ?? settings.endpointLabel ?? NSLocalizedString("configured relay", comment: "")
        switch status.status {
        case .stopped:
            return NSLocalizedString("Start the runtime to connect this runtime host to the relay.", comment: "")
        case .connecting:
            return String(format: NSLocalizedString("Connecting to relay %@.", comment: ""), endpoint)
        case .waitingForPeer:
            return String(format: NSLocalizedString("Registered with relay %@ and waiting for the client device to join.", comment: ""), endpoint)
        case .ready:
            return String(format: NSLocalizedString("Runtime host and client device are matched through relay %@. Model requests still run only through this local runtime.", comment: ""), endpoint)
        case .reconnecting(let message):
            let base = String(format: NSLocalizedString("Reconnecting to relay %@.", comment: ""), endpoint)
            guard let message, !message.isEmpty else { return base }
            return [base, message].joined(separator: "\n")
        case .failed(let message):
            return String(
                format: NSLocalizedString("Relay %@ failed: %@", comment: ""),
                endpoint,
                message
            )
        }
    }

    private func relayStatusText(settings: CompanionDevelopmentRelaySettings) -> String {
        guard settings.isEnabled else {
            return NSLocalizedString("Different-network pairing needs a reachable relay or future P2P route.", comment: "")
        }
        let endpoint = settings.endpointLabel ?? NSLocalizedString("configured relay", comment: "")
        if settings.isEnvironmentOverride {
            return String(
                format: NSLocalizedString("Using %@ from environment variables. Generate the latest QR after changing route settings.", comment: ""),
                endpoint
            )
        }
        return String(
            format: NSLocalizedString("New QR codes include %@ as the remote route. The client retries until the relay is reachable.", comment: ""),
            endpoint
        )
    }

    private func saveRelay() {
        let trimmedHost = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedHost.isEmpty else {
            message = NSLocalizedString("Enter a relay host.", comment: "")
            messageTone = .warning
            return
        }
        guard let relayPort = UInt16(port.trimmingCharacters(in: .whitespacesAndNewlines)), relayPort > 0 else {
            message = NSLocalizedString("Enter a valid relay port.", comment: "")
            messageTone = .warning
            return
        }
        if let warning = CompanionDevelopmentRelaySettings.hostReachabilityWarning(for: trimmedHost) {
            switch warning {
            case .loopback, .localName:
                message = relayHostWarningText(warning)
                messageTone = .warning
                return
            case .privateNetwork:
                model.configureDevelopmentRelay(
                    host: trimmedHost,
                    port: relayPort,
                    relaySecret: relaySecret.trimmingCharacters(in: .whitespacesAndNewlines)
                )
                syncFromModel()
                message = [
                    NSLocalizedString("Relay route saved with warning. Verify this address is reachable from both devices before generating the latest QR.", comment: ""),
                    relayHostWarningText(warning)
                ].joined(separator: "\n")
                messageTone = .warning
                return
            }
        }
        model.configureDevelopmentRelay(
            host: trimmedHost,
            port: relayPort,
            relaySecret: relaySecret.trimmingCharacters(in: .whitespacesAndNewlines)
        )
        syncFromModel()
        message = NSLocalizedString("Remote route saved. Generate the latest QR and scan it from the client app to pair or refresh connectivity.", comment: "")
        messageTone = .ready
    }

    private func syncFromModel() {
        let settings = model.developmentRelaySettings
        host = settings.host
        port = settings.isEnabled ? String(settings.port) : "43171"
        relaySecret = settings.relaySecret ?? ""
    }

    private func relayHostWarningText(_ warning: CompanionDevelopmentRelaySettings.HostReachabilityWarning) -> String {
        switch warning {
        case .loopback:
            return NSLocalizedString("This relay host points back to this machine. A client on another network cannot reach it.", comment: "")
        case .privateNetwork:
            return NSLocalizedString("This relay host is a private network address. Use a public, VPN, or tunnel address reachable from both devices.", comment: "")
        case .localName:
            return NSLocalizedString("This relay host is local-network only. Use a public, VPN, or tunnel address for different networks.", comment: "")
        }
    }
}

private struct RuntimeOverviewPanel: View {
    let overview: RuntimeOverview

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: overview.tone.systemImage)
                .font(.system(size: 26, weight: .semibold))
                .foregroundStyle(overview.tone.color)
                .frame(width: 44, height: 44)
                .background(overview.tone.color.opacity(0.14), in: RoundedRectangle(cornerRadius: 8))

            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(overview.title)
                        .font(.title3.weight(.semibold))
                    StatusPill(text: overview.statusText, tone: overview.tone)
                }

                Text(overview.detail)
                    .font(.callout)
                    .foregroundStyle(.primary)
                    .fixedSize(horizontal: false, vertical: true)

                Text(overview.footnote)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)
        }
        .padding(18)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(overview.tone.color.opacity(0.22), lineWidth: 1)
        }
    }
}

private struct RuntimeOverview {
    let title: String
    let detail: String
    let footnote: String
    let tone: StatusTone

    var statusText: String {
        switch tone {
        case .ready:
            return NSLocalizedString("Ready", comment: "")
        case .warning:
            return NSLocalizedString("Needs attention", comment: "")
        case .inactive:
            return NSLocalizedString("Not ready", comment: "")
        case .neutral:
            return NSLocalizedString("Pending", comment: "")
        }
    }
}

private struct StatusCard: View {
    let title: String
    let value: String
    let detail: String
    let systemImage: String
    let tone: StatusTone

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .center, spacing: 8) {
                Label(title, systemImage: systemImage)
                    .font(.headline)
                    .foregroundStyle(.primary)
                Spacer(minLength: 8)
            }
            StatusPill(text: value, tone: tone)
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, minHeight: 118, alignment: .topLeading)
        .padding(14)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(.separator.opacity(0.5), lineWidth: 1)
        }
    }
}

private struct ModelGroupSection: View {
    let group: ModelGroup

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Label(group.title, systemImage: group.systemImage)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.primary)
                Text(group.countText)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer(minLength: 0)
            }
            .padding(.top, 12)
            .padding(.bottom, 4)

            ForEach(group.models) { item in
                ModelRow(model: item)
                if item.id != group.models.last?.id {
                    Divider()
                }
            }
        }
    }
}

private struct ModelGroup: Identifiable {
    let kind: ModelKind
    let models: [ModelInfo]

    var id: String {
        kind.rawValue
    }

    var title: String {
        switch kind {
        case .chat:
            return NSLocalizedString("Chat Models", comment: "")
        case .embedding:
            return NSLocalizedString("Embedding Models", comment: "")
        }
    }

    var countText: String {
        String(format: NSLocalizedString("%d model(s)", comment: ""), models.count)
    }

    var systemImage: String {
        switch kind {
        case .chat:
            return "bubble.left.and.bubble.right"
        case .embedding:
            return "text.magnifyingglass"
        }
    }
}

private struct ModelRow: View {
    let model: ModelInfo

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(model.name)
                    .font(.headline)
                    .lineLimit(1)
                    .truncationMode(.middle)
                HStack(spacing: 6) {
                    Text(model.id)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .textSelection(.enabled)
                    ModelBadge(text: kindName(model.kind), systemImage: kindSystemImage(model.kind))
                    ModelBadge(text: providerName(model.provider), systemImage: "server.rack")
                    ModelBadge(text: sourceName(model.source), systemImage: sourceSystemImage(model.source))
                    if model.running {
                        ModelBadge(text: NSLocalizedString("Running", comment: ""), systemImage: "play.circle.fill")
                    }
                }
            }

            Spacer(minLength: 12)

            if let sizeBytes = model.sizeBytes {
                Text(companionByteFormatter.string(fromByteCount: sizeBytes))
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 10)
    }

    private func kindName(_ kind: ModelKind) -> String {
        switch kind {
        case .chat:
            return NSLocalizedString("Chat", comment: "")
        case .embedding:
            return NSLocalizedString("Embedding", comment: "")
        }
    }

    private func kindSystemImage(_ kind: ModelKind) -> String {
        switch kind {
        case .chat:
            return "bubble.left.and.bubble.right"
        case .embedding:
            return "text.magnifyingglass"
        }
    }

    private func providerName(_ provider: ModelProvider) -> String {
        switch provider {
        case .ollama:
            return NSLocalizedString("Ollama", comment: "")
        case .lmStudio:
            return NSLocalizedString("LM Studio", comment: "")
        case .aggregate:
            return NSLocalizedString("Local runtime", comment: "")
        }
    }

    private func sourceName(_ source: ModelSource) -> String {
        switch source {
        case .local:
            return NSLocalizedString("Local", comment: "")
        case .cloud:
            return NSLocalizedString("Cloud", comment: "")
        }
    }

    private func sourceSystemImage(_ source: ModelSource) -> String {
        switch source {
        case .local:
            return "internaldrive"
        case .cloud:
            return "icloud"
        }
    }
}

private struct ModelBadge: View {
    let text: String
    let systemImage: String

    var body: some View {
        Label(text, systemImage: systemImage)
            .labelStyle(.titleAndIcon)
            .font(.caption2.weight(.medium))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(.quaternary, in: Capsule())
    }
}

private struct ReadinessRow: View {
    let item: ReadinessItem

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Image(systemName: item.tone.systemImage)
                .font(.body)
                .foregroundStyle(item.tone.color)
                .frame(width: 22)

            VStack(alignment: .leading, spacing: 3) {
                Text(item.title)
                    .font(.headline)
                Text(item.detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 12)

            StatusPill(text: item.statusText, tone: item.tone)
        }
        .padding(.vertical, 10)
    }
}

private struct ReadinessItem: Identifiable {
    let id: String
    let title: String
    let detail: String
    let tone: StatusTone

    var statusText: String {
        switch tone {
        case .ready:
            return NSLocalizedString("Ready", comment: "")
        case .warning:
            return NSLocalizedString("Needs attention", comment: "")
        case .inactive:
            return NSLocalizedString("Not ready", comment: "")
        case .neutral:
            return NSLocalizedString("Pending", comment: "")
        }
    }
}

private struct ProviderStatusRow: View {
    let status: ProviderStatus

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Image(systemName: status.systemImage)
                .font(.body)
                .foregroundStyle(status.tone.color)
                .frame(width: 22)

            VStack(alignment: .leading, spacing: 4) {
                Text(status.name)
                    .font(.headline)
                Text(status.detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(status.rawStatus == .unavailable ? nil : 2)
            }

            Spacer(minLength: 12)

            StatusPill(text: status.value, tone: status.tone)
        }
        .padding(.vertical, 10)
    }
}

private struct BackendSummary {
    let value: String
    let detail: String
    let tone: StatusTone
}

private struct ProviderStatus: Identifiable {
    enum RawStatus: Equatable {
        case notChecked
        case available
        case unavailable
    }

    let id: String
    let name: String
    let rawStatus: RawStatus
    let detail: String

    init(status: CompanionProviderStatus) {
        id = status.id
        name = Self.localizedProviderName(status.provider)
        rawStatus = RawStatus(status.availability)

        switch status.availability {
        case .notChecked:
            detail = NSLocalizedString("Ollama and LM Studio are checked from this runtime host.", comment: "")
        case .available:
            detail = NSLocalizedString("Model provider is responding.", comment: "")
        case .unavailable:
            detail = Self.unavailableDetail(for: status)
        }
    }

    var value: String {
        switch rawStatus {
        case .notChecked:
            return NSLocalizedString("Not checked", comment: "")
        case .available:
            return NSLocalizedString("Available", comment: "")
        case .unavailable:
            return NSLocalizedString("Unavailable", comment: "")
        }
    }

    var tone: StatusTone {
        switch rawStatus {
        case .notChecked:
            return .inactive
        case .available:
            return .ready
        case .unavailable:
            return .warning
        }
    }

    var systemImage: String {
        switch rawStatus {
        case .notChecked:
            return "circle.dashed"
        case .available:
            return "checkmark.circle.fill"
        case .unavailable:
            return "exclamationmark.triangle.fill"
        }
    }

    private static func localizedProviderName(_ provider: ModelProvider) -> String {
        switch provider {
        case .ollama:
            return NSLocalizedString("Ollama", comment: "")
        case .lmStudio:
            return NSLocalizedString("LM Studio", comment: "")
        case .aggregate:
            return NSLocalizedString("Local runtime", comment: "")
        }
    }

    private static func unavailableDetail(for status: CompanionProviderStatus) -> String {
        let providerName = localizedProviderName(status.provider)
        let message = status.message?.trimmingCharacters(in: .whitespacesAndNewlines)

        let baseDetail: String
        if let message, !message.isEmpty {
            baseDetail = message
        } else {
            baseDetail = String(
                format: NSLocalizedString("%@ is not responding from this runtime host.", comment: ""),
                providerName
            )
        }

        guard status.retryable == true else {
            return baseDetail
        }
        return [
            baseDetail,
            NSLocalizedString("Open a local model provider on this runtime host, then check again.", comment: "")
        ].joined(separator: "\n")
    }
}

private extension ProviderStatus.RawStatus {
    init(_ availability: CompanionProviderStatus.Availability) {
        switch availability {
        case .notChecked:
            self = .notChecked
        case .available:
            self = .available
        case .unavailable:
            self = .unavailable
        }
    }
}
