import CompanionCore
import Foundation
import OllamaBackend
import SwiftUI

struct StatusView: View {
    @ObservedObject var model: CompanionAppModel
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
                        title: NSLocalizedString("Local Backends", comment: ""),
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
                            Task { await model.refreshBackendStatus() }
                        } label: {
                            Label(NSLocalizedString("Refresh Backend Status", comment: ""), systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.borderedProminent)

                        Button {
                            Task { await model.loadModels() }
                        } label: {
                            Label(NSLocalizedString("Load Local Models", comment: ""), systemImage: "shippingbox")
                        }
                        .buttonStyle(.bordered)
                    }
                    .controlSize(.regular)
                }

                CompanionPanel(title: NSLocalizedString("Local Backends", comment: ""), systemImage: "server.rack") {
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

    private var backendSummary: BackendSummary {
        let statuses = providerStatuses
        if statuses.allSatisfy({ $0.rawStatus == .notChecked }) {
            return BackendSummary(
                value: NSLocalizedString("Not checked", comment: ""),
                detail: NSLocalizedString("Backend status has not been checked yet.", comment: ""),
                tone: .inactive
            )
        }

        let availableCount = statuses.filter { $0.rawStatus == .available }.count
        if availableCount > 0 {
            return BackendSummary(
                value: String(format: NSLocalizedString("%d of %d available", comment: ""), availableCount, statuses.count),
                detail: NSLocalizedString("At least one local model backend is responding.", comment: ""),
                tone: .ready
            )
        }

        return BackendSummary(
            value: NSLocalizedString("Unavailable", comment: ""),
            detail: NSLocalizedString("No local model backend is responding.", comment: ""),
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
            return NSLocalizedString("Model residency is not managed by this backend.", comment: "")
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
                title: NSLocalizedString("Local backend availability", comment: ""),
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
            return NSLocalizedString("Start the companion runtime listener.", comment: "")
        }
    }

    private var runtimeOverview: RuntimeOverview {
        if model.transportState.state != .advertising {
            return RuntimeOverview(
                title: NSLocalizedString("Setup needed", comment: ""),
                detail: NSLocalizedString("Start the companion runtime before client devices can connect.", comment: ""),
                footnote: NSLocalizedString("Client requests stay mediated by this local runtime. Ollama and LM Studio are never exposed directly to client devices.", comment: ""),
                tone: transportTone(for: model.transportState)
            )
        }

        if backendSummary.tone != .ready {
            return RuntimeOverview(
                title: NSLocalizedString("Backend needs attention", comment: ""),
                detail: NSLocalizedString("Start Ollama or LM Studio on this runtime host, then refresh backend status.", comment: ""),
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

        return RuntimeOverview(
            title: NSLocalizedString("Ready for Client Devices", comment: ""),
            detail: NSLocalizedString("Runtime route is ready, a local backend is responding, and trusted devices can request chat.", comment: ""),
            footnote: NSLocalizedString("The client device remains a controller; all model access stays on the runtime host.", comment: ""),
            tone: .ready
        )
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
            detail = NSLocalizedString("Local backend is responding.", comment: "")
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
