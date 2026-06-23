import Foundation
import SwiftUI

struct CompanionPageHeader: View {
    let title: LocalizedStringKey
    let subtitle: LocalizedStringKey
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
    let title: LocalizedStringKey
    let systemImage: String
    let content: Content

    init(
        title: LocalizedStringKey,
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

func localizedStatus(_ value: String) -> String {
    if value == "Not checked" {
        return NSLocalizedString("Not checked", comment: "")
    }
    if value == "Stopped" {
        return NSLocalizedString("Stopped", comment: "")
    }
    if value == "Ollama available" || value == "Available" {
        return NSLocalizedString("Ollama available", comment: "")
    }
    if value == "LM Studio available" {
        return NSLocalizedString("LM Studio available", comment: "")
    }
    if value.contains(" | ") {
        let availableCount = value
            .split(separator: "|")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { $0.hasSuffix(" available") }
            .count
        if availableCount > 0 {
            return String(format: NSLocalizedString("%d local backend(s) available", comment: ""), availableCount)
        }
        return NSLocalizedString("No local model backend is responding.", comment: "")
    }

    let advertisingPrefix = "Advertising _aetherlink._tcp.local. on port "
    if value.hasPrefix(advertisingPrefix) {
        let port = String(value.dropFirst(advertisingPrefix.count))
        return String(format: NSLocalizedString("Listening on port %@", comment: ""), port)
    }

    if value.hasPrefix("Ollama is not reachable") {
        return NSLocalizedString("Ollama unavailable", comment: "")
    }
    if value.hasPrefix("Ollama returned HTTP") {
        return NSLocalizedString("Ollama returned an error", comment: "")
    }
    if value.hasPrefix("Could not decode Ollama response") {
        return NSLocalizedString("Ollama response could not be read", comment: "")
    }
    if value.hasPrefix("Ollama transport error") {
        return NSLocalizedString("Ollama connection error", comment: "")
    }
    if value.hasPrefix("LM Studio is not reachable") {
        return NSLocalizedString("LM Studio unavailable", comment: "")
    }
    if value.hasPrefix("LM Studio returned HTTP") {
        return NSLocalizedString("LM Studio returned an error", comment: "")
    }
    if value.hasPrefix("Could not decode LM Studio response") {
        return NSLocalizedString("LM Studio response could not be read", comment: "")
    }
    if value.hasPrefix("LM Studio transport error") {
        return NSLocalizedString("LM Studio connection error", comment: "")
    }

    return value
}

func transportTone(for value: String) -> StatusTone {
    if value.hasPrefix("Advertising ") {
        return .ready
    }
    if value == "Stopped" {
        return .inactive
    }
    return .neutral
}

func backendTone(for value: String) -> StatusTone {
    if value == "Ollama available" || value == "LM Studio available" || value == "Available" {
        return .ready
    }
    if value == "Not checked" {
        return .inactive
    }
    if value.contains(" available") {
        return .ready
    }
    return .warning
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
