import CompanionCore
import Foundation
import OllamaBackend
import SwiftUI

struct CompanionPageHeader: View {
    let title: String
    let subtitle: String
    let systemImage: String

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            Image(systemName: systemImage)
                .font(.system(size: 24, weight: .semibold))
                .foregroundStyle(.tint)
                .frame(width: 40, height: 40)
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8))
                .overlay {
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(.separator.opacity(0.45), lineWidth: 1)
                }

            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.title2.weight(.semibold))
                    .lineLimit(1)
                Text(subtitle)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.bottom, 2)
    }
}

struct CompanionPanel<Content: View>: View {
    let title: String
    let systemImage: String
    let content: Content

    init(
        title: String,
        systemImage: String,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.systemImage = systemImage
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: systemImage)
                .font(.headline)
                .foregroundStyle(.primary)

            content
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(.separator.opacity(0.5), lineWidth: 1)
        }
    }
}

struct StatusPill: View {
    let text: String
    let tone: StatusTone

    var body: some View {
        Label {
            Text(text)
                .lineLimit(1)
        } icon: {
            Image(systemName: tone.systemImage)
                .foregroundStyle(tone.color)
        }
        .font(.callout.weight(.medium))
        .padding(.horizontal, 9)
        .padding(.vertical, 5)
        .background(tone.color.opacity(0.14), in: Capsule())
        .overlay {
            Capsule()
                .strokeBorder(tone.color.opacity(0.24), lineWidth: 1)
        }
    }
}

enum StatusTone {
    case ready
    case warning
    case inactive
    case neutral

    var color: Color {
        switch self {
        case .ready:
            return .green
        case .warning:
            return .orange
        case .inactive:
            return .secondary
        case .neutral:
            return .blue
        }
    }

    var systemImage: String {
        switch self {
        case .ready:
            return "checkmark.circle.fill"
        case .warning:
            return "exclamationmark.triangle.fill"
        case .inactive:
            return "pause.circle.fill"
        case .neutral:
            return "circle.fill"
        }
    }
}

func localizedTransportStatus(_ status: CompanionTransportStatus) -> String {
    switch status.state {
    case .stopped:
        return NSLocalizedString("Stopped", comment: "")
    case .advertising:
        return NSLocalizedString("Route ready", comment: "")
    case .failed:
        return NSLocalizedString("Runtime listener failed", comment: "")
    }
}

func transportTone(for status: CompanionTransportStatus) -> StatusTone {
    switch status.state {
    case .advertising:
        return .ready
    case .failed:
        return .warning
    case .stopped:
        return .inactive
    }
}

func localizedBackendStatus(_ statuses: [CompanionProviderStatus]) -> String {
    if statuses.isEmpty || statuses.allSatisfy({ $0.availability == .notChecked }) {
        return NSLocalizedString("Not checked", comment: "")
    }

    if statuses.count == 1, let status = statuses.first {
        switch status.availability {
        case .notChecked:
            return NSLocalizedString("Not checked", comment: "")
        case .available:
            return localizedProviderAvailableStatus(status.provider)
        case .unavailable:
            return localizedProviderUnavailableStatus(status.provider)
        }
    }

    let availableCount = statuses.filter { $0.availability == .available }.count
    if availableCount > 0 {
        return String(format: NSLocalizedString("%d local backend(s) available", comment: ""), availableCount)
    }

    return NSLocalizedString("No local model backend is responding.", comment: "")
}

private func localizedProviderAvailableStatus(_ provider: ModelProvider) -> String {
    switch provider {
    case .ollama:
        return NSLocalizedString("Ollama available", comment: "")
    case .lmStudio:
        return NSLocalizedString("LM Studio available", comment: "")
    case .aggregate:
        return NSLocalizedString("Available", comment: "")
    }
}

private func localizedProviderUnavailableStatus(_ provider: ModelProvider) -> String {
    switch provider {
    case .ollama:
        return NSLocalizedString("Ollama unavailable", comment: "")
    case .lmStudio:
        return NSLocalizedString("LM Studio unavailable", comment: "")
    case .aggregate:
        return NSLocalizedString("Unavailable", comment: "")
    }
}

func shortIdentifier(_ value: String) -> String {
    let suffix = value.suffix(8)
    return suffix.isEmpty ? value : String(suffix)
}

func groupedPairingCode(_ code: String) -> String {
    guard code.count > 3 else { return code }
    let splitIndex = code.index(code.startIndex, offsetBy: code.count - 3)
    return "\(code[..<splitIndex]) \(code[splitIndex...])"
}

let companionDateFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.dateStyle = .medium
    formatter.timeStyle = .short
    return formatter
}()

let companionByteFormatter: ByteCountFormatter = {
    let formatter = ByteCountFormatter()
    formatter.countStyle = .file
    formatter.allowedUnits = [.useGB, .useMB, .useKB]
    return formatter
}()
