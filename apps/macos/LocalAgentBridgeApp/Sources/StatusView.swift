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
                    subtitle: NSLocalizedString("Bridge trusted devices through AetherLink Runtime to local models.", comment: ""),
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
                        title: NSLocalizedString("Device Connections", comment: ""),
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
                                Label(NSLocalizedString("Generate Pairing QR", comment: ""), systemImage: "qrcode")
                            } else {
                                Label(NSLocalizedString("Generate New QR", comment: ""), systemImage: "arrow.triangle.2.circlepath")
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(!canGeneratePairingQR || onGenerateRelayQRCode == nil)
                        .help(pairingQRGenerationHelpText)

                        Button {
                            Task { await model.refreshBackendStatus() }
                        } label: {
                            Label(NSLocalizedString("Check Model Providers", comment: ""), systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.bordered)

                        Button {
                            Task { await model.loadModels() }
                        } label: {
                            Label(NSLocalizedString("Load Models", comment: ""), systemImage: "shippingbox")
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

                CompanionPanel(title: NSLocalizedString("Models", comment: ""), systemImage: "shippingbox") {
                    if model.models.isEmpty {
                        ContentUnavailableView(
                            NSLocalizedString("No models loaded", comment: ""),
                            systemImage: "shippingbox",
                            description: Text(NSLocalizedString("Load models available through AetherLink Runtime.", comment: ""))
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

                if shouldShowRouteDiagnosticsPanel(model: model) {
                    RemoteRelayRoutePanel(
                        model: model,
                        onGenerateRelayQRCode: onGenerateRelayQRCode
                    )
                }
            }
            .padding(24)
            .frame(maxWidth: 920, alignment: .leading)
        }
    }

    private var runtimeDetail: String {
        switch model.transportState.state {
        case .advertising:
            return NSLocalizedString("Trusted devices can find this AetherLink Runtime nearby after pairing.", comment: "")
        case .failed:
            return NSLocalizedString("AetherLink Runtime needs attention. Check Activity or restart AetherLink Runtime.", comment: "")
        case .stopped:
            return NSLocalizedString("AetherLink Runtime is not active.", comment: "")
        }
    }

    private var connectionRouteValue: String {
        guard model.transportState.state == .advertising else {
            return NSLocalizedString("Not ready", comment: "")
        }
        return model.hasDevelopmentRelayRoute
            ? NSLocalizedString("Nearby + cross-network", comment: "")
            : NSLocalizedString("Nearby only", comment: "")
    }

    private var connectionRouteDetail: String {
        guard model.transportState.state == .advertising else {
            return NSLocalizedString("Start AetherLink Runtime before devices can connect.", comment: "")
        }
        if model.hasDevelopmentRelayRoute {
            return connectionRouteStatusDetail
        }
        return NSLocalizedString("No cross-network connection details are saved yet. Pairing still works nearby, and QR-based remote connection can be prepared later.", comment: "")
    }

    private var connectionRouteStatusDetail: String {
        let status = model.developmentRelayConnectionStatus
        let endpoint = status.endpoint ?? model.developmentRelayEndpoint ?? NSLocalizedString("saved connection", comment: "")
        switch status.status {
        case .ready:
            if model.relayFrameEncryptionEnabled {
                return String(
                    format: NSLocalizedString("AetherLink Runtime and the trusted device are connected through %@. Model requests still run only through AetherLink Runtime.", comment: ""),
                    endpoint
                )
            }
            return NSLocalizedString("Connection details need a secure connection secret before sharing sensitive content.", comment: "")
        case .waitingForPeer:
            return String(
                format: NSLocalizedString("%@ is ready and waiting for a trusted device.", comment: ""),
                endpoint
            )
        case .connecting:
            return String(format: NSLocalizedString("Connecting through %@.", comment: ""), endpoint)
        case .reconnecting:
            return String(format: NSLocalizedString("Reconnecting through %@.", comment: ""), endpoint)
        case .failed:
            return String(
                format: NSLocalizedString("Connection through %@ failed. Check Advanced Connection Setup, then try again.", comment: ""),
                endpoint
            )
        case .stopped:
            return NSLocalizedString("Start AetherLink Runtime to use these connection details.", comment: "")
        }
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
            ? NSLocalizedString("Pair a device before allowing runtime requests.", comment: "")
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
            .map(localizedModelResidencyEvent)
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
            return NSLocalizedString("AetherLink Runtime", comment: "")
        }
    }

    private func localizedModelResidencyEvent(_ event: String) -> String {
        let normalized = event.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if normalized.hasPrefix("model unload failed:") {
            return NSLocalizedString("Model unload failed. Check Activity.", comment: "")
        }
        if normalized.hasPrefix("model unload requested:") {
            return NSLocalizedString("Model unload requested by runtime policy.", comment: "")
        }
        if normalized.hasPrefix("model unloaded:") {
            return NSLocalizedString("Model unloaded by runtime policy.", comment: "")
        }
        return NSLocalizedString("Model residency updated.", comment: "")
    }

    private var readinessItems: [ReadinessItem] {
        [
            ReadinessItem(
                id: "runtime-listener",
                title: NSLocalizedString("AetherLink Runtime", comment: ""),
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
                    ? NSLocalizedString("Load models to show what AetherLink Runtime can offer.", comment: "")
                    : String(format: NSLocalizedString("%d model(s) loaded", comment: ""), model.models.count),
                tone: model.models.isEmpty ? .inactive : .ready
            )
        ]
    }

    private var runtimeReadinessDetail: String {
        switch model.transportState.state {
        case .advertising:
            return NSLocalizedString("Ready for paired devices.", comment: "")
        case .failed:
            return NSLocalizedString("AetherLink Runtime needs attention. Check Activity or restart AetherLink Runtime.", comment: "")
        case .stopped:
            return NSLocalizedString("Start AetherLink Runtime.", comment: "")
        }
    }

    private var runtimeOverview: RuntimeOverview {
        let focus = statusRuntimeOverviewFocus(
            isRuntimeAdvertising: model.transportState.state == .advertising,
            isBackendReady: backendSummary.tone == .ready,
            hasTrustedDevices: !model.trustedDevices.isEmpty,
            hasLoadedModels: !model.models.isEmpty,
            hasRoutePreparationIssue: model.remoteRoutePreparationIssue != nil,
            hasDevelopmentRelayRoute: model.hasDevelopmentRelayRoute,
            isDevelopmentRelayQRCodeReady: model.isDevelopmentRelayQRCodeReady
        )

        switch focus {
        case .runtimeSetup:
            return RuntimeOverview(
                title: NSLocalizedString("Setup needed", comment: ""),
                detail: NSLocalizedString("Start AetherLink Runtime before devices can connect.", comment: ""),
                footnote: NSLocalizedString("AetherLink Runtime mediates device requests. Model providers stay private.", comment: ""),
                tone: transportTone(for: model.transportState)
            )
        case .pairing:
            return RuntimeOverview(
                title: NSLocalizedString("Pair a Device to Continue", comment: ""),
                detail: pairingOverviewDetail,
                footnote: NSLocalizedString("Pairing saves trust so devices reconnect without provider URLs.", comment: ""),
                tone: .inactive
            )
        case .backend:
            return RuntimeOverview(
                title: NSLocalizedString("Model service needs attention", comment: ""),
                detail: NSLocalizedString("Start a model provider for AetherLink Runtime, then check again.", comment: ""),
                footnote: NSLocalizedString("AetherLink Runtime mediates device requests. Model providers stay private.", comment: ""),
                tone: backendSummary.tone
            )
        case .models:
            return RuntimeOverview(
                title: NSLocalizedString("Load models", comment: ""),
                detail: NSLocalizedString("Load models so devices can choose an installed chat model through AetherLink Runtime.", comment: ""),
                footnote: NSLocalizedString("Chat and embedding model choices are managed separately so each workflow uses the right model.", comment: ""),
                tone: .neutral
            )
        case .routeIssue:
            guard let issue = model.remoteRoutePreparationIssue else {
                break
            }
            return RuntimeOverview(
                title: NSLocalizedString("Connection details need attention", comment: ""),
                detail: remoteRoutePreparationIssueText(issue),
                footnote: NSLocalizedString("Devices control sessions; all model access stays inside AetherLink Runtime.", comment: ""),
                tone: .warning
            )
        case .routeQRCode:
            return RuntimeOverview(
                title: NSLocalizedString("Connection details not ready for QR", comment: ""),
                detail: relayQRCodeReadinessText(
                    settings: model.developmentRelaySettings,
                    isEligibleForQRCode: model.isDevelopmentRelayRouteEligibleForQRCode,
                    isPreparedForQRCode: model.isDevelopmentRelayRoutePreparedForQRCode,
                    connectionStatus: model.developmentRelayConnectionStatus
                ),
                footnote: NSLocalizedString("Devices control sessions; all model access stays inside AetherLink Runtime.", comment: ""),
                tone: .neutral
            )
        case .ready:
            break
        }

        return RuntimeOverview(
            title: NSLocalizedString("Ready for Devices", comment: ""),
            detail: NSLocalizedString("AetherLink Runtime is ready, model providers are responding, and trusted devices can chat.", comment: ""),
            footnote: NSLocalizedString("Devices control sessions; all model access stays inside AetherLink Runtime.", comment: ""),
            tone: .ready
        )
    }

    private var pairingOverviewDetail: String {
        if model.canPrepareRemoteRelayRouteAutomatically {
            return NSLocalizedString("Generate and scan a pairing QR. AetherLink prepares connection details automatically when available.", comment: "")
        }
        return NSLocalizedString("Generate a pairing QR when connection preparation is available. Use Advanced Connection Setup only when automatic preparation is unavailable.", comment: "")
    }

    private var canGeneratePairingQR: Bool {
        pairingQRGenerationAvailable(
            canPrepareAutomatically: model.canPrepareRemoteRelayRouteAutomatically,
            isRouteEligibleForQRCode: model.isDevelopmentRelayRouteEligibleForQRCode
        )
    }

    private var pairingQRGenerationHelpText: String {
        canGeneratePairingQR
            ? NSLocalizedString("Generate Pairing QR", comment: "")
            : NSLocalizedString("Pairing from another network needs connection details inside the pairing QR.", comment: "")
    }
}

enum StatusRuntimeOverviewFocus: Equatable {
    case runtimeSetup
    case pairing
    case backend
    case models
    case routeIssue
    case routeQRCode
    case ready
}

func statusRuntimeOverviewFocus(
    isRuntimeAdvertising: Bool,
    isBackendReady: Bool,
    hasTrustedDevices: Bool,
    hasLoadedModels: Bool,
    hasRoutePreparationIssue: Bool,
    hasDevelopmentRelayRoute: Bool,
    isDevelopmentRelayQRCodeReady: Bool
) -> StatusRuntimeOverviewFocus {
    guard isRuntimeAdvertising else {
        return .runtimeSetup
    }
    guard hasTrustedDevices else {
        return .pairing
    }
    guard isBackendReady else {
        return .backend
    }
    guard hasLoadedModels else {
        return .models
    }
    if hasRoutePreparationIssue {
        return .routeIssue
    }
    if hasDevelopmentRelayRoute && !isDevelopmentRelayQRCodeReady {
        return .routeQRCode
    }
    return .ready
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
            return NSLocalizedString("AetherLink Runtime", comment: "")
        }
    }

    private func sourceName(_ source: ModelSource) -> String {
        switch source {
        case .local:
            return NSLocalizedString("Local", comment: "")
        case .cloud:
            return NSLocalizedString("Provider managed", comment: "")
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
    @State private var diagnosticsExpanded = false

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

                if let diagnosticDetail = status.diagnosticDetail {
                    DisclosureGroup(
                        isExpanded: $diagnosticsExpanded,
                        content: {
                            Text(diagnosticDetail)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(.top, 4)
                        },
                        label: {
                            Text(NSLocalizedString("Technical Details", comment: ""))
                                .font(.caption.weight(.medium))
                        }
                    )
                    .tint(.secondary)
                }
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
    let diagnosticDetail: String?

    init(status: CompanionProviderStatus) {
        id = status.id
        name = Self.localizedProviderName(status.provider)
        rawStatus = RawStatus(status.availability)
        diagnosticDetail = Self.diagnosticDetail(for: status)

        switch status.availability {
        case .notChecked:
            detail = NSLocalizedString("Model providers are checked by AetherLink Runtime.", comment: "")
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
            return NSLocalizedString("AetherLink Runtime", comment: "")
        }
    }

    private static func unavailableDetail(for status: CompanionProviderStatus) -> String {
        let providerName = localizedProviderName(status.provider)
        let baseDetail = String(
                format: NSLocalizedString("%@ is not responding through AetherLink Runtime.", comment: ""),
            providerName
        )

        guard status.retryable == true else {
            return baseDetail
        }
        return [
            baseDetail,
            NSLocalizedString("Open a model provider for AetherLink Runtime, then check again.", comment: "")
        ].joined(separator: "\n")
    }

    private static func diagnosticDetail(for status: CompanionProviderStatus) -> String? {
        providerStatusDiagnosticDetail(
            message: status.message,
            code: status.code,
            retryable: status.retryable
        )
    }
}

func providerStatusDiagnosticDetail(
    message: String?,
    code: String?,
    retryable: Bool?
) -> String? {
    var lines: [String] = []
    if let message = sanitizedTechnicalDiagnostic(message) {
        lines.append(message)
    }
    if let code = sanitizedProviderStatusCode(code) {
        lines.append("code=\(code)")
    }
    if let retryable {
        lines.append("retryable=\(retryable ? "true" : "false")")
    }
    return lines.isEmpty ? nil : lines.joined(separator: "\n")
}

private func sanitizedProviderStatusCode(_ code: String?) -> String? {
    guard let trimmed = code?.trimmingCharacters(in: .whitespacesAndNewlines), !trimmed.isEmpty else {
        return nil
    }
    let allowedCharacters = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
    guard trimmed.unicodeScalars.allSatisfy({ allowedCharacters.contains($0) }) else {
        return NSLocalizedString("Sensitive technical detail redacted.", comment: "")
    }
    return trimmed
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
