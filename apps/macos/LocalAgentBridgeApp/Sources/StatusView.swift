import CompanionCore
import Foundation
import OllamaBackend
import SwiftUI

struct StatusView: View {
    @ObservedObject var model: CompanionAppModel
    var onGenerateRelayQRCode: (() -> Void)?
    @State private var isRuntimeHistoryInspectorPresented = false
    @State private var isRuntimeMemoryInspectorPresented = false
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
                    StatusCard(
                        title: NSLocalizedString("Runtime History", comment: ""),
                        value: runtimeHistoryValue,
                        detail: runtimeHistoryDetail,
                        systemImage: "text.bubble",
                        tone: runtimeDataTone
                    )
                    StatusCard(
                        title: NSLocalizedString("Runtime Memory", comment: ""),
                        value: runtimeMemoryValue,
                        detail: runtimeMemoryDetail,
                        systemImage: "brain.head.profile",
                        tone: runtimeDataTone
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
                        let canRunPairingQRAction = canGeneratePairingQR && onGenerateRelayQRCode != nil
                        let pairingQRActionHint = pairingQRGenerationActionAccessibilityHint(
                            isAvailable: canGeneratePairingQR,
                            hasAction: onGenerateRelayQRCode != nil
                        )
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
                        .disabled(!canRunPairingQRAction)
                        .help(pairingQRActionHint)
                        .accessibilityValue(
                            Text(
                                pairingQRGenerationActionAccessibilityValue(
                                    isAvailable: canGeneratePairingQR,
                                    hasAction: onGenerateRelayQRCode != nil
                                )
                            )
                        )
                        .accessibilityHint(Text(pairingQRActionHint))

                        Button {
                            Task { await model.refreshBackendStatus() }
                        } label: {
                            Label(NSLocalizedString("Check Model Providers", comment: ""), systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.bordered)
                        .help(modelProviderCheckActionAccessibilityHint())
                        .accessibilityValue(Text(modelProviderCheckActionAccessibilityValue()))
                        .accessibilityHint(Text(modelProviderCheckActionAccessibilityHint()))

                        Button {
                            Task { await model.loadModels() }
                        } label: {
                            Label(NSLocalizedString("Load Models", comment: ""), systemImage: "shippingbox")
                        }
                        .buttonStyle(.bordered)
                        .help(modelListLoadActionAccessibilityHint())
                        .accessibilityValue(Text(modelListLoadActionAccessibilityValue()))
                        .accessibilityHint(Text(modelListLoadActionAccessibilityHint()))

                        Button {
                            model.refreshRuntimeDataSummary()
                        } label: {
                            Label(NSLocalizedString("Refresh Runtime Data", comment: ""), systemImage: "arrow.triangle.2.circlepath")
                        }
                        .buttonStyle(.bordered)
                        .help(refreshRuntimeDataActionAccessibilityHint())
                        .accessibilityValue(Text(refreshRuntimeDataActionAccessibilityValue()))
                        .accessibilityHint(Text(refreshRuntimeDataActionAccessibilityHint()))

                        Button {
                            model.refreshRuntimeChatSessions()
                            isRuntimeHistoryInspectorPresented = true
                        } label: {
                            Label(NSLocalizedString("Inspect Runtime History", comment: ""), systemImage: "text.bubble")
                        }
                        .buttonStyle(.bordered)
                        .help(inspectRuntimeHistoryActionAccessibilityHint())
                        .accessibilityValue(Text(inspectRuntimeHistoryActionAccessibilityValue()))
                        .accessibilityHint(Text(inspectRuntimeHistoryActionAccessibilityHint()))

                        Button {
                            model.refreshRuntimeMemoryEntries()
                            isRuntimeMemoryInspectorPresented = true
                        } label: {
                            Label(NSLocalizedString("Inspect Runtime Memory", comment: ""), systemImage: "list.bullet.rectangle")
                        }
                        .buttonStyle(.bordered)
                        .help(inspectRuntimeMemoryActionAccessibilityHint())
                        .accessibilityValue(Text(inspectRuntimeMemoryActionAccessibilityValue()))
                        .accessibilityHint(Text(inspectRuntimeMemoryActionAccessibilityHint()))
                    }
                    .controlSize(.regular)
                }

                CompanionPanel(title: NSLocalizedString("Model Providers", comment: ""), systemImage: "server.rack") {
                    if providerStatuses.isEmpty {
                        let emptyModelProvidersTitle = NSLocalizedString("No model providers available", comment: "")
                        let emptyModelProvidersDescription = NSLocalizedString("AetherLink Runtime has not reported any model providers yet.", comment: "")
                        ContentUnavailableView(
                            emptyModelProvidersTitle,
                            systemImage: "server.rack",
                            description: Text(emptyModelProvidersDescription)
                        )
                        .frame(maxWidth: .infinity, minHeight: 160)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(
                            Text(
                                companionEmptyStateAccessibilityLabel(
                                    title: emptyModelProvidersTitle,
                                    description: emptyModelProvidersDescription
                                )
                            )
                        )
                    } else {
                        VStack(spacing: 0) {
                            ForEach(providerStatuses) { provider in
                                ProviderStatusRow(status: provider)
                                if provider.id != providerStatuses.last?.id {
                                    Divider()
                                }
                            }
                        }
                    }
                }

                CompanionPanel(title: NSLocalizedString("Models", comment: ""), systemImage: "shippingbox") {
                    if model.models.isEmpty {
                        let emptyModelsTitle = NSLocalizedString("No models loaded", comment: "")
                        let emptyModelsDescription = NSLocalizedString("Load models available through AetherLink Runtime.", comment: "")
                        ContentUnavailableView(
                            emptyModelsTitle,
                            systemImage: "shippingbox",
                            description: Text(emptyModelsDescription)
                        )
                        .frame(maxWidth: .infinity, minHeight: 180)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(
                            Text(
                                companionEmptyStateAccessibilityLabel(
                                    title: emptyModelsTitle,
                                    description: emptyModelsDescription
                                )
                            )
                        )
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
        .sheet(isPresented: $isRuntimeHistoryInspectorPresented) {
            RuntimeHistoryInspectorSheet(
                sessions: model.runtimeChatSessions,
                transcriptMessages: model.runtimeChatTranscriptMessages,
                transcriptErrors: model.runtimeChatTranscriptErrors,
                errorMessage: model.runtimeChatSessionsError,
                onRefresh: model.refreshRuntimeChatSessions,
                onLoadTranscriptPreview: { sessionID in
                    model.refreshRuntimeChatTranscriptPreview(sessionID: sessionID)
                }
            )
        }
        .sheet(isPresented: $isRuntimeMemoryInspectorPresented) {
            RuntimeMemoryInspectorSheet(
                entries: model.runtimeMemoryEntries,
                errorMessage: model.runtimeMemoryEntriesError,
                onRefresh: model.refreshRuntimeMemoryEntries
            )
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
        return NSLocalizedString("No cross-network connection details are saved yet. Nearby pairing still works. For another network, use a reachable relay, VPN, or tunnel before generating the latest QR.", comment: "")
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
                format: NSLocalizedString("Connection through %@ failed. Check Connection Recovery, then try again.", comment: ""),
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
        visibleModelGroups(for: model.models)
    }

    private var visibleModelCount: Int {
        modelGroups.reduce(0) { count, group in count + group.models.count }
    }

    private var trustedDeviceCount: String {
        localizedTrustedDeviceCount(model.trustedDevices.count)
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
            return localizedModelResidencyActiveDetail(
                providerName: localizedProviderName(activeProvider),
                modelID: activeModelID,
                idleUnloadMinutes: minutes
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

    private var runtimeHistoryValue: String {
        guard !model.runtimeDataSummary.hasError else {
            return NSLocalizedString("Needs attention", comment: "")
        }
        return localizedRuntimeActiveChatSessionCount(model.runtimeDataSummary.activeChatSessionCount)
    }

    private var runtimeHistoryDetail: String {
        guard !model.runtimeDataSummary.hasError else {
            return NSLocalizedString("Runtime chat history could not be read. Check Activity.", comment: "")
        }
        let archivedCount = model.runtimeDataSummary.archivedChatSessionCount
        if archivedCount == 0 {
            return NSLocalizedString("No archived chats are stored on AetherLink Runtime.", comment: "")
        }
        return String(
            format: NSLocalizedString("%@ stored separately from active memory context.", comment: ""),
            localizedRuntimeArchivedChatSessionCount(archivedCount)
        )
    }

    private var runtimeMemoryValue: String {
        guard !model.runtimeDataSummary.hasError else {
            return NSLocalizedString("Needs attention", comment: "")
        }
        return localizedRuntimeEnabledMemoryCount(model.runtimeDataSummary.enabledMemoryCount)
    }

    private var runtimeMemoryDetail: String {
        guard !model.runtimeDataSummary.hasError else {
            return NSLocalizedString("Runtime memory could not be read. Check Activity.", comment: "")
        }
        let pausedCount = model.runtimeDataSummary.pausedMemoryCount
        if pausedCount == 0 {
            return NSLocalizedString("No paused memory notes are stored on AetherLink Runtime.", comment: "")
        }
        return String(
            format: NSLocalizedString("%@ kept out of runtime context until re-enabled.", comment: ""),
            localizedRuntimePausedMemoryCount(pausedCount)
        )
    }

    private var runtimeDataTone: StatusTone {
        if model.runtimeDataSummary.hasError {
            return .warning
        }
        let totalCount = model.runtimeDataSummary.activeChatSessionCount +
            model.runtimeDataSummary.archivedChatSessionCount +
            model.runtimeDataSummary.enabledMemoryCount +
            model.runtimeDataSummary.pausedMemoryCount
        return totalCount == 0 ? .inactive : .ready
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
                detail: visibleModelCount == 0
                    ? NSLocalizedString("Load models to show what AetherLink Runtime can offer.", comment: "")
                    : localizedLoadedModelCount(visibleModelCount),
                tone: visibleModelCount == 0 ? .inactive : .ready
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
            hasLoadedModels: visibleModelCount > 0,
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
        return NSLocalizedString("Generate a pairing QR when connection preparation is available. Use Connection Recovery only when automatic preparation is unavailable.", comment: "")
    }

    private var canGeneratePairingQR: Bool {
        pairingQRGenerationAvailable(
            canPrepareAutomatically: model.canPrepareRemoteRelayRouteAutomatically,
            isRouteEligibleForQRCode: model.isDevelopmentRelayRouteEligibleForQRCode
        )
    }

    private var pairingQRGenerationHelpText: String {
        pairingQRGenerationActionAccessibilityHint(isAvailable: canGeneratePairingQR)
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
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            Text(
                runtimeOverviewAccessibilityLabel(
                    title: overview.title,
                    status: overview.statusText,
                    detail: overview.detail,
                    footnote: overview.footnote
                )
            )
        )
    }
}

func runtimeOverviewAccessibilityLabel(title: String, status: String, detail: String, footnote: String) -> String {
    let normalizedTitle = trimmedNonEmpty(title)
        ?? NSLocalizedString("Runtime overview", comment: "")
    let normalizedStatus = trimmedNonEmpty(status)
        ?? NSLocalizedString("Unknown status", comment: "")
    let normalizedDetail = trimmedNonEmpty(detail)
        ?? NSLocalizedString("No overview details", comment: "")
    let normalizedFootnote = trimmedNonEmpty(footnote)
        ?? NSLocalizedString("No additional guidance", comment: "")
    return String(
        format: NSLocalizedString("Runtime overview %@. Status %@. %@ %@", comment: ""),
        normalizedTitle,
        normalizedStatus,
        normalizedDetail,
        normalizedFootnote
    )
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
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            Text(statusCardAccessibilityLabel(title: title, value: value, detail: detail))
        )
    }
}

func statusCardAccessibilityLabel(title: String, value: String, detail: String) -> String {
    let normalizedTitle = trimmedNonEmpty(title)
        ?? NSLocalizedString("Status item", comment: "")
    let normalizedValue = trimmedNonEmpty(value)
        ?? NSLocalizedString("Unknown status", comment: "")
    let normalizedDetail = trimmedNonEmpty(detail)
        ?? NSLocalizedString("No status details", comment: "")
    return String(
        format: NSLocalizedString("Status %@. Current state %@. %@", comment: ""),
        normalizedTitle,
        normalizedValue,
        normalizedDetail
    )
}

struct RuntimeHistoryInspectorSheet: View {
    let sessions: [RuntimeChatStoredSession]
    let transcriptMessages: [String: [RuntimeChatStoredMessage]]
    let transcriptErrors: [String: String]
    let errorMessage: String?
    let onRefresh: () -> Void
    let onLoadTranscriptPreview: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var selectedSessionID: String?

    private var selectedSession: RuntimeChatStoredSession? {
        guard let selectedSessionID else { return nil }
        return sessions.first { $0.sessionID == selectedSessionID }
    }

    private var selectedMessages: [RuntimeChatStoredMessage]? {
        guard let selectedSessionID else { return nil }
        return transcriptMessages[selectedSessionID]
    }

    private var selectedError: String? {
        guard let selectedSessionID else { return nil }
        return transcriptErrors[selectedSessionID]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .center, spacing: 12) {
                Label(NSLocalizedString("Runtime History Inspector", comment: ""), systemImage: "text.bubble")
                    .font(.title2.weight(.semibold))
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 0)
                Button {
                    onRefresh()
                } label: {
                    Label(NSLocalizedString("Refresh", comment: ""), systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
                .help(NSLocalizedString("Refresh runtime-owned chat sessions from AetherLink Runtime.", comment: ""))
                .accessibilityLabel(Text(NSLocalizedString("Refresh Runtime History Inspector", comment: "")))
                .accessibilityHint(Text(NSLocalizedString("Refresh runtime-owned chat sessions from AetherLink Runtime.", comment: "")))

                Button {
                    dismiss()
                } label: {
                    Text(NSLocalizedString("Close", comment: ""))
                }
                .keyboardShortcut(.cancelAction)
                .accessibilityLabel(Text(NSLocalizedString("Close Runtime History Inspector", comment: "")))
            }

            Text(NSLocalizedString("Review runtime-owned chat sessions stored on this runtime host.", comment: ""))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            if let cleanError = trimmedNonEmpty(errorMessage ?? "") {
                Label(cleanError, systemImage: "exclamationmark.triangle.fill")
                    .font(.callout)
                    .foregroundStyle(.orange)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 8))
                    .accessibilityLabel(
                        Text(
                            String(
                                format: NSLocalizedString("Runtime history inspector warning. %@", comment: ""),
                                cleanError
                            )
                        )
                    )
            }

            if sessions.isEmpty {
                let emptyTitle = NSLocalizedString("No runtime chat sessions", comment: "")
                let emptyDescription = NSLocalizedString("AetherLink Runtime has not stored chat sessions yet.", comment: "")
                ContentUnavailableView(
                    emptyTitle,
                    systemImage: "text.bubble",
                    description: Text(emptyDescription)
                )
                .frame(maxWidth: .infinity, minHeight: 220)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(
                    Text(
                        companionEmptyStateAccessibilityLabel(
                            title: emptyTitle,
                            description: emptyDescription
                        )
                    )
                )
            } else {
                HStack(alignment: .top, spacing: 14) {
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 10) {
                            ForEach(sessions, id: \.sessionID) { session in
                                Button {
                                    selectedSessionID = session.sessionID
                                    onLoadTranscriptPreview(session.sessionID)
                                } label: {
                                    RuntimeHistoryInspectorRow(
                                        session: session,
                                        isSelected: selectedSessionID == session.sessionID
                                    )
                                }
                                .buttonStyle(.plain)
                                .help(NSLocalizedString("Load transcript preview", comment: ""))
                                .accessibilityLabel(
                                    Text(runtimeTranscriptPreviewLoadAccessibilityLabel(title: session.title))
                                )
                            }
                        }
                        .padding(.vertical, 2)
                    }
                    .frame(minWidth: 300, maxWidth: 360)

                    Divider()

                    RuntimeTranscriptPreviewPane(
                        session: selectedSession,
                        messages: selectedMessages,
                        errorMessage: selectedError,
                        onLoad: {
                            if let sessionID = selectedSession?.sessionID {
                                onLoadTranscriptPreview(sessionID)
                            }
                        }
                    )
                    .frame(minWidth: 320, maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                }
                .onAppear {
                    if selectedSessionID == nil, let firstSession = sessions.first {
                        selectedSessionID = firstSession.sessionID
                        onLoadTranscriptPreview(firstSession.sessionID)
                    }
                }
                .onChange(of: sessions.map(\.sessionID)) { _, sessionIDs in
                    guard !sessionIDs.isEmpty else {
                        selectedSessionID = nil
                        return
                    }
                    if selectedSessionID.map({ !sessionIDs.contains($0) }) != false {
                        selectedSessionID = sessionIDs[0]
                        onLoadTranscriptPreview(sessionIDs[0])
                    }
                }
            }
        }
        .padding(24)
        .frame(minWidth: 760, minHeight: 500)
    }
}

private struct RuntimeHistoryInspectorRow: View {
    let session: RuntimeChatStoredSession
    let isSelected: Bool

    private var statusText: String {
        localizedRuntimeChatSessionStatus(session.status)
    }

    private var tone: StatusTone {
        session.status == "archived" ? .inactive : .ready
    }

    private var titleText: String {
        trimmedNonEmpty(session.title) ?? NSLocalizedString("Untitled chat", comment: "")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                StatusPill(text: statusText, tone: tone)
                Text(titleText)
                    .font(.headline)
                    .lineLimit(1)
                Spacer(minLength: 0)
                Text(String(format: NSLocalizedString("Updated %@", comment: ""), localizedCompanionDateString(from: session.lastActivityAt)))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 12) {
                Label(session.model, systemImage: "cpu")
                Label(localizedRuntimeChatMessageCount(session.messageCount), systemImage: "bubble.left.and.bubble.right")
                if let lastEvent = session.lastEvent.flatMap(trimmedNonEmpty) {
                    Label(runtimeHistoryEventDisplayName(lastEvent), systemImage: "clock.arrow.circlepath")
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .lineLimit(1)

            if let errorCode = session.lastErrorCode.flatMap(trimmedNonEmpty) {
                Label(
                    String(format: NSLocalizedString("Last error %@", comment: ""), errorCode),
                    systemImage: "exclamationmark.triangle.fill"
                )
                .font(.caption)
                .foregroundStyle(.orange)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
        .background(
            isSelected ? Color.accentColor.opacity(0.14) : Color.clear,
            in: RoundedRectangle(cornerRadius: 8)
        )
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(
                    isSelected ? Color.accentColor.opacity(0.7) : Color.secondary.opacity(0.22),
                    lineWidth: 1
                )
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            Text(
                runtimeChatSessionAccessibilityLabel(
                    title: titleText,
                    status: statusText,
                    model: session.model,
                    messageCount: localizedRuntimeChatMessageCount(session.messageCount),
                    updatedAt: localizedCompanionDateString(from: session.lastActivityAt)
                )
            )
        )
    }
}

private struct RuntimeTranscriptPreviewPane: View {
    let session: RuntimeChatStoredSession?
    let messages: [RuntimeChatStoredMessage]?
    let errorMessage: String?
    let onLoad: () -> Void

    private var titleText: String {
        trimmedNonEmpty(session?.title ?? "") ?? NSLocalizedString("Untitled chat", comment: "")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 10) {
                Label(NSLocalizedString("Transcript Preview", comment: ""), systemImage: "doc.text.magnifyingglass")
                    .font(.headline)
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 0)
                Button {
                    onLoad()
                } label: {
                    Label(NSLocalizedString("Load transcript preview", comment: ""), systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
                .disabled(session == nil)
                .accessibilityLabel(
                    Text(runtimeTranscriptPreviewLoadAccessibilityLabel(title: titleText))
                )
            }

            if session != nil {
                Text(titleText)
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)

                if let cleanError = trimmedNonEmpty(errorMessage ?? "") {
                    Label(cleanError, systemImage: "exclamationmark.triangle.fill")
                        .font(.callout)
                        .foregroundStyle(.orange)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 8))
                        .accessibilityLabel(
                            Text(
                                String(
                                    format: NSLocalizedString("Runtime transcript preview warning. %@", comment: ""),
                                    cleanError
                                )
                            )
                        )
                }

                if let messages {
                    if messages.isEmpty {
                        let emptyTitle = NSLocalizedString("No transcript messages", comment: "")
                        let emptyDescription = NSLocalizedString("AetherLink Runtime has not stored visible messages for this session.", comment: "")
                        ContentUnavailableView(
                            emptyTitle,
                            systemImage: "doc.text",
                            description: Text(emptyDescription)
                        )
                        .frame(maxWidth: .infinity, minHeight: 180)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(
                            Text(
                                companionEmptyStateAccessibilityLabel(
                                    title: emptyTitle,
                                    description: emptyDescription
                                )
                            )
                        )
                    } else {
                        ScrollView {
                            LazyVStack(alignment: .leading, spacing: 10) {
                                ForEach(Array(messages.enumerated()), id: \.offset) { _, message in
                                    RuntimeTranscriptPreviewMessageRow(message: message)
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }
                } else {
                    let emptyTitle = NSLocalizedString("Select a chat session", comment: "")
                    let emptyDescription = NSLocalizedString("Choose a runtime-owned chat session to preview stored messages.", comment: "")
                    ContentUnavailableView(
                        emptyTitle,
                        systemImage: "text.bubble",
                        description: Text(emptyDescription)
                    )
                    .frame(maxWidth: .infinity, minHeight: 180)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel(
                        Text(
                            companionEmptyStateAccessibilityLabel(
                                title: emptyTitle,
                                description: emptyDescription
                            )
                        )
                    )
                }
            } else {
                let emptyTitle = NSLocalizedString("Select a chat session", comment: "")
                let emptyDescription = NSLocalizedString("Choose a runtime-owned chat session to preview stored messages.", comment: "")
                ContentUnavailableView(
                    emptyTitle,
                    systemImage: "text.bubble",
                    description: Text(emptyDescription)
                )
                .frame(maxWidth: .infinity, minHeight: 220)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(
                    Text(
                        companionEmptyStateAccessibilityLabel(
                            title: emptyTitle,
                            description: emptyDescription
                        )
                    )
                )
            }
        }
        .padding(.leading, 2)
    }
}

private struct RuntimeTranscriptPreviewMessageRow: View {
    let message: RuntimeChatStoredMessage

    private var roleText: String {
        runtimeTranscriptRoleDisplayName(message.role)
    }

    private var contentText: String {
        trimmedNonEmpty(message.content) ?? NSLocalizedString("Empty message", comment: "")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(roleText)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer(minLength: 0)
                if let createdAt = message.createdAt {
                    Text(localizedCompanionDateString(from: createdAt))
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }

            Text(contentText)
                .font(.callout)
                .foregroundStyle(.primary)
                .lineLimit(4)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)

            if let reasoning = trimmedNonEmpty(message.reasoning ?? "") {
                RuntimeTranscriptReasoningBlock(reasoning: reasoning)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .contain)
    }
}

private struct RuntimeTranscriptReasoningBlock: View {
    let reasoning: String
    @State private var isExpanded = false

    var body: some View {
        let policy = runtimeTranscriptReasoningDisplayPolicy(
            reasoning: reasoning,
            expanded: isExpanded
        )

        VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(NSLocalizedString("Reasoning", comment: ""))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)

                Spacer(minLength: 0)

                if policy.expandable {
                    Button {
                        isExpanded.toggle()
                    } label: {
                        Text(runtimeTranscriptReasoningToggleTitle(isExpanded: policy.isExpanded))
                    }
                    .buttonStyle(.plain)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .accessibilityLabel(Text(runtimeTranscriptReasoningToggleTitle(isExpanded: policy.isExpanded)))
                    .accessibilityValue(Text(runtimeTranscriptReasoningToggleAccessibilityValue(isExpanded: policy.isExpanded)))
                    .accessibilityHint(Text(runtimeTranscriptReasoningToggleAccessibilityHint(isExpanded: policy.isExpanded)))
                }
            }

            Text(policy.text)
                .font(.caption)
                .foregroundStyle(.secondary)
                .opacity(policy.contentOpacity)
                .lineLimit(policy.maxLines)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)
        }
        .padding(.top, 2)
    }
}

struct RuntimeTranscriptReasoningDisplayPolicy: Equatable {
    let text: String
    let maxLines: Int?
    let contentOpacity: Double
    let expandable: Bool
    let isExpanded: Bool
}

let runtimeTranscriptReasoningPreviewMaxLines = 3
let runtimeTranscriptReasoningCollapsedOpacity = 0.58
let runtimeTranscriptReasoningExpandedOpacity = 0.86

func runtimeTranscriptReasoningDisplayPolicy(
    reasoning: String,
    expanded: Bool
) -> RuntimeTranscriptReasoningDisplayPolicy {
    let expandable = runtimeTranscriptReasoningNeedsExpansion(reasoning)
    let isExpanded = expanded && expandable
    return RuntimeTranscriptReasoningDisplayPolicy(
        text: isExpanded ? reasoning.trimmingCharacters(in: .whitespacesAndNewlines) : runtimeTranscriptReasoningPreview(reasoning),
        maxLines: isExpanded ? nil : runtimeTranscriptReasoningPreviewMaxLines,
        contentOpacity: isExpanded ? runtimeTranscriptReasoningExpandedOpacity : runtimeTranscriptReasoningCollapsedOpacity,
        expandable: expandable,
        isExpanded: isExpanded
    )
}

func runtimeTranscriptReasoningPreview(
    _ reasoning: String,
    maxLines: Int = runtimeTranscriptReasoningPreviewMaxLines
) -> String {
    let lines = reasoning
        .components(separatedBy: .newlines)
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
    let linePreview = lines.prefix(maxLines).joined(separator: "\n")
    if !linePreview.isEmpty {
        return linePreview
    }

    let singleLine = reasoning.trimmingCharacters(in: .whitespacesAndNewlines)
        .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
    guard singleLine.count > 180 else {
        return singleLine
    }
    let endIndex = singleLine.index(singleLine.startIndex, offsetBy: 180)
    return "\(singleLine[..<endIndex])..."
}

func runtimeTranscriptReasoningNeedsExpansion(_ reasoning: String) -> Bool {
    let full = reasoning.trimmingCharacters(in: .whitespacesAndNewlines)
        .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
    let preview = runtimeTranscriptReasoningPreview(reasoning)
        .replacingOccurrences(of: "...", with: "")
        .trimmingCharacters(in: .whitespacesAndNewlines)
        .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
    return !full.isEmpty && preview != full
}

func runtimeTranscriptReasoningToggleTitle(isExpanded: Bool) -> String {
    isExpanded
        ? NSLocalizedString("Hide reasoning", comment: "")
        : NSLocalizedString("Show reasoning", comment: "")
}

func runtimeTranscriptReasoningToggleAccessibilityValue(isExpanded: Bool) -> String {
    isExpanded
        ? NSLocalizedString("Reasoning expanded", comment: "")
        : NSLocalizedString("Reasoning collapsed", comment: "")
}

func runtimeTranscriptReasoningToggleAccessibilityHint(isExpanded: Bool) -> String {
    isExpanded
        ? NSLocalizedString("Collapse to keep reasoning preview short.", comment: "")
        : NSLocalizedString("Expand to show full reasoning.", comment: "")
}

func localizedRuntimeChatSessionStatus(_ status: String) -> String {
    switch status.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
    case "archived":
        return NSLocalizedString("Archived", comment: "")
    case "active":
        return NSLocalizedString("Active", comment: "")
    default:
        return NSLocalizedString("Unknown status", comment: "")
    }
}

func runtimeTranscriptRoleDisplayName(_ role: String) -> String {
    switch role.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
    case "user":
        return NSLocalizedString("User", comment: "")
    case "assistant":
        return NSLocalizedString("Assistant", comment: "")
    case "system":
        return NSLocalizedString("System message", comment: "")
    default:
        return NSLocalizedString("Message", comment: "")
    }
}

func runtimeHistoryEventDisplayName(_ event: String) -> String {
    switch event.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
    case "done":
        return NSLocalizedString("Completed", comment: "")
    case "cancelled":
        return NSLocalizedString("Cancelled", comment: "")
    case "error":
        return NSLocalizedString("Failed", comment: "")
    case "request":
        return NSLocalizedString("In progress", comment: "")
    case "archived":
        return NSLocalizedString("Archived", comment: "")
    case "restored":
        return NSLocalizedString("Restored", comment: "")
    default:
        return NSLocalizedString("Updated", comment: "")
    }
}

func runtimeChatSessionAccessibilityLabel(
    title: String,
    status: String,
    model: String,
    messageCount: String,
    updatedAt: String
) -> String {
    let normalizedTitle = trimmedNonEmpty(title)
        ?? NSLocalizedString("Untitled chat", comment: "")
    let normalizedStatus = trimmedNonEmpty(status)
        ?? NSLocalizedString("Unknown status", comment: "")
    let normalizedModel = trimmedNonEmpty(model)
        ?? NSLocalizedString("Unknown model", comment: "")
    let normalizedMessageCount = trimmedNonEmpty(messageCount)
        ?? localizedRuntimeChatMessageCount(0)
    let normalizedUpdatedAt = trimmedNonEmpty(updatedAt)
        ?? NSLocalizedString("Unknown update time", comment: "")
    return String(
        format: NSLocalizedString("Chat session %@. Status %@. Model %@. %@. Updated %@.", comment: ""),
        normalizedTitle,
        normalizedStatus,
        normalizedModel,
        normalizedMessageCount,
        normalizedUpdatedAt
    )
}

func runtimeTranscriptPreviewLoadAccessibilityLabel(title: String) -> String {
    let normalizedTitle = trimmedNonEmpty(title)
        ?? NSLocalizedString("Untitled chat", comment: "")
    return String(
        format: NSLocalizedString("Load transcript preview for %@", comment: ""),
        normalizedTitle
    )
}

struct RuntimeMemoryInspectorSheet: View {
    let entries: [RuntimeMemoryEntry]
    let errorMessage: String?
    let onRefresh: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .center, spacing: 12) {
                Label(NSLocalizedString("Runtime Memory Inspector", comment: ""), systemImage: "brain.head.profile")
                    .font(.title2.weight(.semibold))
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 0)
                Button {
                    onRefresh()
                } label: {
                    Label(NSLocalizedString("Refresh", comment: ""), systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
                .help(NSLocalizedString("Refresh runtime-owned memory notes from AetherLink Runtime.", comment: ""))
                .accessibilityLabel(Text(NSLocalizedString("Refresh Runtime Memory Inspector", comment: "")))
                .accessibilityHint(Text(NSLocalizedString("Refresh runtime-owned memory notes from AetherLink Runtime.", comment: "")))

                Button {
                    dismiss()
                } label: {
                    Text(NSLocalizedString("Close", comment: ""))
                }
                .keyboardShortcut(.cancelAction)
                .accessibilityLabel(Text(NSLocalizedString("Close Runtime Memory Inspector", comment: "")))
            }

            Text(NSLocalizedString("Review runtime-owned memory notes before trusting them in chat.", comment: ""))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            if let cleanError = trimmedNonEmpty(errorMessage ?? "") {
                Label(cleanError, systemImage: "exclamationmark.triangle.fill")
                    .font(.callout)
                    .foregroundStyle(.orange)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 8))
                    .accessibilityLabel(
                        Text(
                            String(
                                format: NSLocalizedString("Runtime memory inspector warning. %@", comment: ""),
                                cleanError
                            )
                        )
                    )
            }

            if entries.isEmpty {
                let emptyTitle = NSLocalizedString("No runtime memory notes", comment: "")
                let emptyDescription = NSLocalizedString("AetherLink Runtime has not stored memory notes yet.", comment: "")
                ContentUnavailableView(
                    emptyTitle,
                    systemImage: "brain.head.profile",
                    description: Text(emptyDescription)
                )
                .frame(maxWidth: .infinity, minHeight: 220)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(
                    Text(
                        companionEmptyStateAccessibilityLabel(
                            title: emptyTitle,
                            description: emptyDescription
                        )
                    )
                )
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(entries, id: \.id) { entry in
                            RuntimeMemoryInspectorRow(entry: entry)
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
        }
        .padding(24)
        .frame(minWidth: 560, minHeight: 420)
    }
}

private struct RuntimeMemoryInspectorRow: View {
    let entry: RuntimeMemoryEntry

    private var statusText: String {
        NSLocalizedString(entry.enabled ? "Enabled" : "Paused", comment: "")
    }

    private var tone: StatusTone {
        entry.enabled ? .ready : .inactive
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                StatusPill(text: statusText, tone: tone)
                Spacer(minLength: 0)
                Text(String(format: NSLocalizedString("Updated %@", comment: ""), localizedCompanionDateString(from: entry.updatedAt)))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(entry.content)
                .font(.body)
                .foregroundStyle(.primary)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 12) {
                Text(String(format: NSLocalizedString("Created %@", comment: ""), localizedCompanionDateString(from: entry.createdAt)))
                Text(String(format: NSLocalizedString("Updated %@", comment: ""), localizedCompanionDateString(from: entry.updatedAt)))
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(.separator.opacity(0.5), lineWidth: 1)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            Text(
                runtimeMemoryEntryAccessibilityLabel(
                    content: entry.content,
                    status: statusText,
                    updatedAt: localizedCompanionDateString(from: entry.updatedAt)
                )
            )
        )
    }
}

func runtimeMemoryEntryAccessibilityLabel(content: String, status: String, updatedAt: String) -> String {
    let normalizedContent = trimmedNonEmpty(content)
        ?? NSLocalizedString("Untitled memory note", comment: "")
    let normalizedStatus = trimmedNonEmpty(status)
        ?? NSLocalizedString("Unknown status", comment: "")
    let normalizedUpdatedAt = trimmedNonEmpty(updatedAt)
        ?? NSLocalizedString("Unknown update time", comment: "")
    return String(
        format: NSLocalizedString("Memory note %@. Status %@. Updated %@.", comment: ""),
        normalizedContent,
        normalizedStatus,
        normalizedUpdatedAt
    )
}

private func trimmedNonEmpty(_ value: String) -> String? {
    let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
    return trimmed.isEmpty ? nil : trimmed
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
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(
                Text(modelGroupHeaderAccessibilityLabel(title: group.title, count: group.countText))
            )
            .accessibilityAddTraits(.isHeader)

            ForEach(group.models) { item in
                ModelRow(model: item)
                if item.id != group.models.last?.id {
                    Divider()
                }
            }
        }
    }
}

struct ModelGroup: Identifiable {
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
        localizedModelCount(models.count)
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

internal func visibleModelGroups(for models: [ModelInfo]) -> [ModelGroup] {
    let chatModels = visibleModels(for: models, kind: .chat)
    let embeddingModels = visibleModels(for: models, kind: .embedding)

    return [
        ModelGroup(kind: .chat, models: chatModels),
        ModelGroup(kind: .embedding, models: embeddingModels)
    ].filter { !$0.models.isEmpty }
}

private func visibleModels(for models: [ModelInfo], kind: ModelKind) -> [ModelInfo] {
    models.filter { model in
        model.kind == kind &&
            model.installed &&
            model.source == .local
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
                Text(localizedCompanionByteCountString(fromByteCount: sizeBytes))
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 10)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            Text(
                modelRowAccessibilityLabel(
                    name: model.name,
                    identifier: model.id,
                    kind: kindName(model.kind),
                    provider: providerName(model.provider),
                    source: sourceName(model.source),
                    running: model.running,
                    size: model.sizeBytes.map { localizedCompanionByteCountString(fromByteCount: $0) }
                )
            )
        )
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

func modelGroupHeaderAccessibilityLabel(title: String, count: String) -> String {
    let normalizedTitle = trimmedNonEmpty(title)
        ?? NSLocalizedString("Model section", comment: "")
    let normalizedCount = trimmedNonEmpty(count)
        ?? NSLocalizedString("No model count", comment: "")
    return String(
        format: NSLocalizedString("Model section %@. %@", comment: ""),
        normalizedTitle,
        normalizedCount
    )
}

func modelRowAccessibilityLabel(
    name: String,
    identifier: String,
    kind: String,
    provider: String,
    source: String,
    running: Bool,
    size: String?
) -> String {
    let normalizedName = trimmedNonEmpty(name)
        ?? NSLocalizedString("Unnamed model", comment: "")
    let normalizedIdentifier = trimmedNonEmpty(identifier)
        ?? NSLocalizedString("Unknown model ID", comment: "")
    let normalizedKind = trimmedNonEmpty(kind)
        ?? NSLocalizedString("Unknown model type", comment: "")
    let normalizedProvider = trimmedNonEmpty(provider)
        ?? NSLocalizedString("Unknown provider", comment: "")
    let normalizedSource = trimmedNonEmpty(source)
        ?? NSLocalizedString("Unknown source", comment: "")
    let normalizedState = running
        ? NSLocalizedString("Running", comment: "")
        : NSLocalizedString("Not running", comment: "")
    let normalizedSize = trimmedNonEmpty(size ?? "")
        ?? NSLocalizedString("Size unknown", comment: "")

    return String(
        format: NSLocalizedString("Model %@. ID %@. Type %@. Provider %@. Source %@. State %@. Size %@", comment: ""),
        normalizedName,
        normalizedIdentifier,
        normalizedKind,
        normalizedProvider,
        normalizedSource,
        normalizedState,
        normalizedSize
    )
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
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            Text(
                readinessRowAccessibilityLabel(
                    title: item.title,
                    status: item.statusText,
                    detail: item.detail
                )
            )
        )
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

func readinessRowAccessibilityLabel(title: String, status: String, detail: String) -> String {
    let normalizedTitle = trimmedNonEmpty(title)
        ?? NSLocalizedString("Readiness item", comment: "")
    let normalizedStatus = trimmedNonEmpty(status)
        ?? NSLocalizedString("Unknown status", comment: "")
    let normalizedDetail = trimmedNonEmpty(detail)
        ?? NSLocalizedString("No readiness details", comment: "")
    return String(
        format: NSLocalizedString("Readiness %@. Status %@. %@", comment: ""),
        normalizedTitle,
        normalizedStatus,
        normalizedDetail
    )
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
                .accessibilityHidden(true)

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
                    .accessibilityLabel(Text(providerStatusTechnicalDetailsAccessibilityLabel(providerName: status.name)))
                    .accessibilityValue(Text(providerStatusTechnicalDetailsAccessibilityValue(isExpanded: diagnosticsExpanded)))
                    .accessibilityHint(Text(providerStatusTechnicalDetailsAccessibilityHint(isExpanded: diagnosticsExpanded)))
                    .tint(.secondary)
                }
            }

            Spacer(minLength: 12)

            StatusPill(text: status.value, tone: status.tone)
                .accessibilityLabel(
                    Text(
                        providerStatusPillAccessibilityLabel(
                            providerName: status.name,
                            status: status.value
                        )
                    )
                )
        }
        .padding(.vertical, 10)
        .accessibilityLabel(
            Text(
                providerStatusRowAccessibilityLabel(
                    providerName: status.name,
                    status: status.value,
                    detail: status.detail
                )
            )
        )
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

func providerStatusTechnicalDetailsAccessibilityLabel(providerName: String) -> String {
    let trimmedProviderName = providerName.trimmingCharacters(in: .whitespacesAndNewlines)
    let normalizedProviderName = trimmedProviderName.isEmpty
        ? NSLocalizedString("Model provider", comment: "")
        : trimmedProviderName
    return String(
        format: NSLocalizedString("Technical details for %@", comment: ""),
        normalizedProviderName
    )
}

func providerStatusTechnicalDetailsAccessibilityValue(isExpanded: Bool) -> String {
    NSLocalizedString(
        isExpanded ? "Provider details expanded" : "Provider details collapsed",
        comment: ""
    )
}

func providerStatusTechnicalDetailsAccessibilityHint(isExpanded: Bool) -> String {
    NSLocalizedString(
        isExpanded ? "Collapse to hide provider details." : "Expand to show provider details.",
        comment: ""
    )
}

func providerStatusPillAccessibilityLabel(providerName: String, status: String) -> String {
    let trimmedProviderName = providerName.trimmingCharacters(in: .whitespacesAndNewlines)
    let normalizedProviderName = trimmedProviderName.isEmpty
        ? NSLocalizedString("Model provider", comment: "")
        : trimmedProviderName
    let trimmedStatus = status.trimmingCharacters(in: .whitespacesAndNewlines)
    let normalizedStatus = trimmedStatus.isEmpty
        ? NSLocalizedString("Not checked", comment: "")
        : trimmedStatus
    return String(
        format: NSLocalizedString("Provider %@ status %@", comment: ""),
        normalizedProviderName,
        normalizedStatus
    )
}

func providerStatusRowAccessibilityLabel(providerName: String, status: String, detail: String) -> String {
    let normalizedProviderName = trimmedNonEmpty(providerName)
        ?? NSLocalizedString("Model provider", comment: "")
    let normalizedStatus = trimmedNonEmpty(status)
        ?? NSLocalizedString("Not checked", comment: "")
    let normalizedDetail = trimmedNonEmpty(detail)
        ?? NSLocalizedString("No provider details", comment: "")
    return String(
        format: NSLocalizedString("Provider %@. Status %@. %@", comment: ""),
        normalizedProviderName,
        normalizedStatus,
        normalizedDetail
    )
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
