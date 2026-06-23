import CompanionCore
import Foundation
import SwiftUI

struct LogsView: View {
    @ObservedObject var model: CompanionAppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            CompanionPageHeader(
                title: "Runtime Logs",
                subtitle: "Recent companion activity from this Mac session.",
                systemImage: "list.bullet.rectangle.fill"
            )

            CompanionPanel(title: "Activity", systemImage: "clock.arrow.circlepath") {
                if model.logs.isEmpty {
                    ContentUnavailableView(
                        "No runtime logs",
                        systemImage: "list.bullet.rectangle",
                        description: Text("Events will appear here after the companion starts receiving activity.")
                    )
                    .frame(maxWidth: .infinity, minHeight: 300)
                } else {
                    List(model.logs, id: \.self) { line in
                        LogRow(line: localizedLogLine(line), tone: logTone(line))
                            .padding(.vertical, 4)
                    }
                    .listStyle(.inset)
                    .frame(minHeight: 300)
                }
            }

            Spacer(minLength: 0)
        }
        .padding(24)
    }
}

private struct LogRow: View {
    let line: String
    let tone: StatusTone

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Image(systemName: tone.systemImage)
                .font(.caption)
                .foregroundStyle(tone.color)
                .frame(width: 16)
            Text(line)
                .font(.system(.body, design: .monospaced))
                .lineLimit(3)
                .textSelection(.enabled)
        }
    }
}

private func logTone(_ line: String) -> StatusTone {
    if line.contains("failed") || line.contains("not reachable") || line.contains("error") {
        return .warning
    }
    if line.contains("stopped") || line == "Companion stopped" {
        return .inactive
    }
    if line.contains("passed") || line.contains("Trusted ") || line.contains("Loaded ") {
        return .ready
    }
    return .neutral
}

private func localizedLogLine(_ line: String) -> String {
    switch line {
    case "Companion started":
        return NSLocalizedString("Companion started", comment: "")
    case "Companion stopped":
        return NSLocalizedString("Companion stopped", comment: "")
    case "Ollama health check passed":
        return NSLocalizedString("Ollama health check passed", comment: "")
    case "Pairing code generated":
        return NSLocalizedString("Pairing code generated", comment: "")
    default:
        if line.hasPrefix("Trusted ") {
            return String(
                format: NSLocalizedString("Trusted %@", comment: ""),
                String(line.dropFirst("Trusted ".count))
            )
        }
        if line.hasPrefix("Removed ") {
            return String(
                format: NSLocalizedString("Removed %@", comment: ""),
                String(line.dropFirst("Removed ".count))
            )
        }
        if line.hasPrefix("Received ") {
            return NSLocalizedString("Received Android runtime request", comment: "")
        }
        if line.hasPrefix("Loaded "), line.hasSuffix(" local model(s)") {
            let count = String(line.dropFirst("Loaded ".count).dropLast(" local model(s)".count))
            return String(
                format: NSLocalizedString("Loaded %@ local model(s)", comment: ""),
                count
            )
        }
        if line.hasPrefix("Loaded "), line.hasSuffix(" Ollama model(s)") {
            let count = String(line.dropFirst("Loaded ".count).dropLast(" Ollama model(s)".count))
            return String(
                format: NSLocalizedString("Loaded %@ local model(s)", comment: ""),
                count
            )
        }
        if line.hasPrefix("Model list failed: ") {
            return String(
                format: NSLocalizedString("Could not load local models: %@", comment: ""),
                String(line.dropFirst("Model list failed: ".count))
            )
        }
        if line.hasPrefix("Remove trusted device failed: ") {
            return String(
                format: NSLocalizedString("Could not remove trusted device: %@", comment: ""),
                String(line.dropFirst("Remove trusted device failed: ".count))
            )
        }
        if line.hasPrefix("Trusted device load failed: ") {
            return String(
                format: NSLocalizedString("Could not load trusted devices: %@", comment: ""),
                String(line.dropFirst("Trusted device load failed: ".count))
            )
        }
        return line
    }
}
