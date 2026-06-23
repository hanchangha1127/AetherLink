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
                    title: "AetherLink Companion",
                    subtitle: "Bridge trusted Android devices through this Mac runtime to local models.",
                    systemImage: "bolt.horizontal.circle.fill"
                )

                LazyVGrid(columns: columns, alignment: .leading, spacing: 12) {
                    StatusCard(
                        title: "Runtime",
                        value: localizedStatus(model.transportStatus),
                        detail: runtimeDetail,
                        systemImage: "antenna.radiowaves.left.and.right",
                        tone: transportTone(for: model.transportStatus)
                    )
                    StatusCard(
                        title: "Local Backends",
                        value: backendSummary.value,
                        detail: backendSummary.detail,
                        systemImage: "cpu",
                        tone: backendSummary.tone
                    )
                    StatusCard(
                        title: "Trusted Devices",
                        value: trustedDeviceCount,
                        detail: trustedDeviceDetail,
                        systemImage: "lock.shield",
                        tone: model.trustedDevices.isEmpty ? .inactive : .ready
                    )
                }

                CompanionPanel(title: "Quick Actions", systemImage: "bolt.horizontal") {
                    HStack(spacing: 10) {
                        Button {
                            Task { await model.refreshOllamaStatus() }
                        } label: {
                            Label("Refresh Backend Status", systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.borderedProminent)

                        Button {
                            Task { await model.loadModels() }
                        } label: {
                            Label("Load Local Models", systemImage: "shippingbox")
                        }
                        .buttonStyle(.bordered)
                    }
                    .controlSize(.regular)
                }

                CompanionPanel(title: "Local Backends", systemImage: "server.rack") {
                    VStack(spacing: 0) {
                        ForEach(providerStatuses) { provider in
                            ProviderStatusRow(status: provider)
                            if provider.id != providerStatuses.last?.id {
                                Divider()
                            }
                        }
                    }
                }

                CompanionPanel(title: "Local Models", systemImage: "shippingbox") {
                    if model.models.isEmpty {
                        ContentUnavailableView(
                            "No local models loaded",
                            systemImage: "shippingbox",
                            description: Text("Load models to confirm what Android can request through this Mac runtime.")
                        )
                        .frame(maxWidth: .infinity, minHeight: 180)
                    } else {
                        VStack(spacing: 0) {
                            ForEach(model.models) { item in
                                ModelRow(model: item)
                                if item.id != model.models.last?.id {
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
        if model.transportStatus.hasPrefix("Advertising ") {
            return NSLocalizedString("Ready for trusted Android clients.", comment: "")
        }
        return NSLocalizedString("The local runtime listener is not active.", comment: "")
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
        ProviderStatus.parse(model.backendStatus)
    }

    private var trustedDeviceCount: String {
        String(
            format: NSLocalizedString("%d trusted device(s)", comment: ""),
            model.trustedDevices.count
        )
    }

    private var trustedDeviceDetail: String {
        model.trustedDevices.isEmpty
            ? NSLocalizedString("Pair a phone before allowing runtime requests.", comment: "")
            : NSLocalizedString("Authenticated devices can request runtime sessions.", comment: "")
    }
}

private struct StatusCard: View {
    let title: LocalizedStringKey
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
                    .lineLimit(2)
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

    static func parse(_ backendStatus: String) -> [ProviderStatus] {
        if backendStatus == "Not checked" {
            return [
                ProviderStatus(
                    id: "ollama",
                    name: NSLocalizedString("Ollama", comment: ""),
                    rawStatus: .notChecked,
                    detail: NSLocalizedString("Ollama and LM Studio are checked from this Mac.", comment: "")
                ),
                ProviderStatus(
                    id: "lm-studio",
                    name: NSLocalizedString("LM Studio", comment: ""),
                    rawStatus: .notChecked,
                    detail: NSLocalizedString("Ollama and LM Studio are checked from this Mac.", comment: "")
                )
            ]
        }

        let components = backendStatus
            .split(separator: "|")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }

        let parsed = components.compactMap(parseComponent(_:))
        if parsed.isEmpty {
            return [
                ProviderStatus(
                    id: "backend",
                    name: NSLocalizedString("Local runtime", comment: ""),
                    rawStatus: backendStatus == "Available" ? .available : .unavailable,
                    detail: localizedStatus(backendStatus)
                )
            ]
        }
        return parsed
    }

    private static func parseComponent(_ component: String) -> ProviderStatus? {
        parseProviderComponent(component, providerName: "Ollama", id: "ollama")
            ?? parseProviderComponent(component, providerName: "LM Studio", id: "lm-studio")
    }

    private static func parseProviderComponent(
        _ component: String,
        providerName: String,
        id: String
    ) -> ProviderStatus? {
        if component == "\(providerName) available" {
            return ProviderStatus(
                id: id,
                name: NSLocalizedString(providerName, comment: ""),
                rawStatus: .available,
                detail: NSLocalizedString("Local backend is responding.", comment: "")
            )
        }

        let unavailablePrefix = "\(providerName) unavailable:"
        if component.hasPrefix(unavailablePrefix) {
            return ProviderStatus(
                id: id,
                name: NSLocalizedString(providerName, comment: ""),
                rawStatus: .unavailable,
                detail: String(
                    format: NSLocalizedString("%@ is not responding from this Mac.", comment: ""),
                    NSLocalizedString(providerName, comment: "")
                )
            )
        }

        return nil
    }
}
