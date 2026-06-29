import CompanionCore
import Foundation
import SwiftUI

struct LogsView: View {
    @ObservedObject var model: CompanionAppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            CompanionPageHeader(
                title: NSLocalizedString("Activity", comment: ""),
                subtitle: NSLocalizedString("Summarized runtime activity with technical details available when needed.", comment: ""),
                systemImage: "list.bullet.rectangle.fill"
            )

            CompanionPanel(title: NSLocalizedString("Activity", comment: ""), systemImage: "clock.arrow.circlepath") {
                if model.logs.isEmpty {
                    let emptyActivityTitle = NSLocalizedString("No activity yet", comment: "")
                    let emptyActivityDescription = NSLocalizedString("Activity appears here after AetherLink Runtime starts receiving requests.", comment: "")
                    ContentUnavailableView(
                        emptyActivityTitle,
                        systemImage: "list.bullet.rectangle",
                        description: Text(emptyActivityDescription)
                    )
                    .frame(maxWidth: .infinity, minHeight: 300)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel(
                        Text(
                            companionEmptyStateAccessibilityLabel(
                                title: emptyActivityTitle,
                                description: emptyActivityDescription
                            )
                        )
                    )
                } else {
                    List {
                        ForEach(Array(model.logs.enumerated()), id: \.offset) { index, line in
                            LogRow(
                                display: localizedLogDisplay(line),
                                tone: logTone(line),
                                position: index + 1,
                                totalCount: model.logs.count
                            )
                            .padding(.vertical, 4)
                        }
                    }
                    .listStyle(.inset)
                    .frame(minHeight: 300)
                    .accessibilityLabel(Text(activityLogListAccessibilityLabel()))
                    .accessibilityValue(Text(activityLogListAccessibilityValue(count: model.logs.count)))
                }
            }

            Spacer(minLength: 0)
        }
        .padding(24)
    }
}

private struct LogRow: View {
    let display: LogDisplay
    let tone: StatusTone
    let position: Int
    let totalCount: Int
    @State private var diagnosticsExpanded = false

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Image(systemName: tone.systemImage)
                .font(.caption)
                .foregroundStyle(tone.color)
                .frame(width: 16)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                Text(display.summary)
                    .font(.body)
                    .lineLimit(3)
                    .textSelection(.enabled)
                    .accessibilityLabel(
                        Text(
                            logRowAccessibilityLabel(
                                summary: display.summary,
                                tone: tone,
                                position: position,
                                totalCount: totalCount
                            )
                        )
                    )
                if let diagnostic = display.diagnostic {
                    DisclosureGroup(isExpanded: $diagnosticsExpanded) {
                        Text(diagnostic)
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, 4)
                    } label: {
                        Text(NSLocalizedString("Technical Details", comment: ""))
                            .font(.caption.weight(.medium))
                    }
                    .accessibilityLabel(Text(logTechnicalDetailsAccessibilityLabel(summary: display.summary)))
                    .accessibilityValue(Text(logTechnicalDetailsAccessibilityValue(isExpanded: diagnosticsExpanded)))
                    .accessibilityHint(Text(logTechnicalDetailsAccessibilityHint(isExpanded: diagnosticsExpanded)))
                    .tint(.secondary)
                }
            }
        }
    }
}

struct LogDisplay {
    let summary: String
    let diagnostic: String?

    init(summary: String, diagnostic: String? = nil) {
        self.summary = summary
        self.diagnostic = sanitizedTechnicalDiagnostic(diagnostic)
    }
}

private func logTone(_ line: String) -> StatusTone {
    if line.contains("failed") || line.contains("not reachable") || line.contains("not generated") || line.contains("error") {
        return .warning
    }
    if line.contains("stopped") || line == "Companion stopped" {
        return .inactive
    }
    if line.contains("passed") ||
        line.contains("Trusted ") ||
        line.contains("Loaded ") ||
        line == "Route secret regenerated" ||
        line.hasPrefix("Remote route enabled:") ||
        line.hasPrefix("Remote route configured:") ||
        line.hasPrefix("Remote route allocated:") ||
        line.hasPrefix("Remote route bootstrap allocated route ") ||
        line.hasPrefix("Remote route ready:") ||
        line.hasPrefix("Remote route lease refreshed:")
    {
        return .ready
    }
    return .neutral
}

func activityLogTone(for line: String) -> StatusTone {
    logTone(line)
}

func logToneAccessibilityStatus(_ tone: StatusTone) -> String {
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

func activityLogListAccessibilityLabel() -> String {
    NSLocalizedString("Activity log", comment: "")
}

func activityLogListAccessibilityValue(count: Int) -> String {
    if count == 1 {
        return NSLocalizedString("1 activity item", comment: "")
    }
    return String(
        format: NSLocalizedString("%d activity items", comment: ""),
        count
    )
}

func logRowAccessibilityLabel(summary: String, tone: StatusTone) -> String {
    let eventSummary = normalizedLogAccessibilitySummary(summary)
    return String(
        format: NSLocalizedString("Activity item %@. Status %@.", comment: ""),
        eventSummary,
        logToneAccessibilityStatus(tone)
    )
}

func logRowAccessibilityLabel(summary: String, tone: StatusTone, position: Int, totalCount: Int) -> String {
    let eventSummary = normalizedLogAccessibilitySummary(summary)
    let safePosition = max(1, position)
    let safeTotalCount = max(safePosition, totalCount)
    return String(
        format: NSLocalizedString("Activity item %d of %d. %@. Status %@.", comment: ""),
        safePosition,
        safeTotalCount,
        eventSummary,
        logToneAccessibilityStatus(tone)
    )
}

func localizedLogDisplay(_ line: String) -> LogDisplay {
    switch line {
    case "Companion started", "AetherLink runtime started":
        return LogDisplay(summary: NSLocalizedString("AetherLink runtime started", comment: ""))
    case "Companion stopped", "AetherLink runtime stopped":
        return LogDisplay(summary: NSLocalizedString("AetherLink runtime stopped", comment: ""))
    case "Ollama health check passed":
        return LogDisplay(summary: NSLocalizedString("Model provider health check passed", comment: ""))
    case "Pairing code generated":
        return LogDisplay(summary: NSLocalizedString("Pairing QR generated", comment: ""))
    case "Remote route disabled":
        return LogDisplay(summary: NSLocalizedString("Saved connection details removed.", comment: ""))
    case "Route secret regenerated":
        return LogDisplay(summary: NSLocalizedString("Connection setup secret regenerated.", comment: ""))
    case "Remote pairing QR not generated: configure a reachable relay route first",
         "Remote pairing QR not generated: configure a reachable remote route first":
        return LogDisplay(summary: NSLocalizedString("Pairing QR is waiting for connection details.", comment: ""))
    default:
        if line.hasPrefix("Runtime listener failed: ") {
            return LogDisplay(
                summary: NSLocalizedString("AetherLink Runtime needs attention.", comment: ""),
                diagnostic: line
            )
        }
        if line.contains(" unavailable: ") {
            return LogDisplay(
                summary: NSLocalizedString("Model provider needs attention.", comment: ""),
                diagnostic: line
            )
        }
        if line.hasSuffix(" available") {
            return LogDisplay(
                summary: NSLocalizedString("Model provider is available.", comment: ""),
                diagnostic: line
            )
        }
        if let endpoint = remotePairingEndpoint(
            in: line,
            oldPrefix: "Remote pairing QR not generated: relay route ",
            newPrefix: "Remote pairing QR not generated: remote route ",
            suffix: " cannot be included in QR"
        ) {
            return LogDisplay(
                summary: String(
                    format: NSLocalizedString("Connection details for %@ cannot be included in this QR. Connection Recovery needs an address both devices can reach.", comment: ""),
                    endpoint
                ),
                diagnostic: line
            )
        }
        if let endpoint = remotePairingEndpoint(
            in: line,
            oldPrefix: "Remote pairing QR not generated: relay route ",
            newPrefix: "Remote pairing QR not generated: remote route ",
            suffix: " is not ready"
        ) {
            return LogDisplay(
                summary: String(
                    format: NSLocalizedString("Connection details for %@ are not ready yet. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: ""),
                    endpoint
                ),
                diagnostic: line
            )
        }
        if line.hasPrefix("Trusted ") {
            return LogDisplay(
                summary: String(
                    format: NSLocalizedString("Trusted device %@", comment: ""),
                    trustedDeviceAuditLogName(String(line.dropFirst("Trusted ".count)))
                )
            )
        }
        if line.hasPrefix("Removed ") {
            return LogDisplay(
                summary: String(
                    format: NSLocalizedString("Removed trust for %@", comment: ""),
                    trustedDeviceAuditLogName(String(line.dropFirst("Removed ".count)))
                )
            )
        }
        if line.hasPrefix("Received ") {
            return LogDisplay(summary: NSLocalizedString("Received device runtime request", comment: ""))
        }
        if line.hasPrefix("Relay received ") {
            return LogDisplay(
                summary: NSLocalizedString("Received device runtime request", comment: ""),
                diagnostic: line
            )
        }
        if line.hasPrefix("Loaded "), line.hasSuffix(" local model(s)") {
            let count = String(line.dropFirst("Loaded ".count).dropLast(" local model(s)".count))
            return LogDisplay(
                summary: localizedLoadedLocalModelLogCount(count)
            )
        }
        if line.hasPrefix("Loaded "), line.hasSuffix(" Ollama model(s)") {
            let count = String(line.dropFirst("Loaded ".count).dropLast(" Ollama model(s)".count))
            return LogDisplay(
                summary: localizedLoadedLocalModelLogCount(count)
            )
        }
        if let detail = detail(after: "Model list failed: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Could not load models.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remove trusted device failed: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Could not remove trusted device.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Trusted device load failed: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Could not load trusted devices.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route enabled: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection details saved.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route configured: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection details saved.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route allocated: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection details saved.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route bootstrap allocated route ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection details saved.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route ready: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection details are ready.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route allocation failed: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection Recovery needs attention.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route bootstrap failed: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection Recovery needs attention.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route lease refresh failed: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection Recovery needs attention.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route bootstrap rejected unreachable connection address ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection Recovery needs attention.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route lease refresh rejected unreachable connection address ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection Recovery needs attention.", comment: ""),
                diagnostic: detail
            )
        }
        if line == "Remote route lease refresh skipped: route secret is missing" {
            return LogDisplay(
                summary: NSLocalizedString("Connection Recovery needs attention.", comment: ""),
                diagnostic: line
            )
        }
        if let detail = detail(after: "Remote route lease refreshed: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection details saved.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route failed: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Connection details need attention.", comment: ""),
                diagnostic: detail
            )
        }
        if let detail = detail(after: "Remote route reconnecting: ", in: line) {
            return LogDisplay(
                summary: NSLocalizedString("Reconnecting with saved connection details.", comment: ""),
                diagnostic: detail
            )
        }
        if line.hasPrefix("Model residency active: ") ||
            line.hasPrefix("Model unload requested: ") ||
            line.hasPrefix("Model unloaded: ") ||
            line.hasPrefix("Model unload failed: ") {
            return LogDisplay(
                summary: NSLocalizedString("Model residency updated.", comment: ""),
                diagnostic: line
            )
        }
        return LogDisplay(
            summary: NSLocalizedString("Runtime event recorded.", comment: ""),
            diagnostic: line
        )
    }
}

private func trustedDeviceAuditLogName(_ rawName: String) -> String {
    let trimmedName = rawName.trimmingCharacters(in: .whitespacesAndNewlines)
    return trimmedName.isEmpty
        ? NSLocalizedString("Selected device", comment: "")
        : trimmedName
}

func logTechnicalDetailsAccessibilityLabel(summary: String) -> String {
    let normalizedSummary = normalizedLogAccessibilitySummary(summary)
    return String(
        format: NSLocalizedString("Technical details for %@", comment: ""),
        normalizedSummary
    )
}

private func normalizedLogAccessibilitySummary(_ summary: String) -> String {
    let normalizedSummary = summary.normalizedLogAccessibilitySummaryFragment
    return normalizedSummary.nilIfEmpty
        ?? NSLocalizedString("Runtime event recorded.", comment: "").normalizedLogAccessibilitySummaryFragment
}

func logTechnicalDetailsAccessibilityValue(isExpanded: Bool) -> String {
    isExpanded
        ? NSLocalizedString("Activity technical details expanded", comment: "")
        : NSLocalizedString("Activity technical details collapsed", comment: "")
}

func logTechnicalDetailsAccessibilityHint(isExpanded: Bool) -> String {
    isExpanded
        ? NSLocalizedString("Collapse to hide activity technical details.", comment: "")
        : NSLocalizedString("Expand to show activity technical details.", comment: "")
}

private func detail(after prefix: String, in line: String) -> String? {
    guard line.hasPrefix(prefix) else { return nil }
    return String(line.dropFirst(prefix.count)).trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
}

func sanitizedTechnicalDiagnostic(_ diagnostic: String?) -> String? {
    guard let diagnostic = diagnostic?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty else {
        return nil
    }
    if diagnostic.containsSensitiveRouteMaterial {
        return NSLocalizedString("Sensitive technical detail redacted.", comment: "")
    }
    if diagnostic.containsProviderEndpointMaterial {
        return NSLocalizedString("Provider endpoint redacted.", comment: "")
    }
    return diagnostic
}

private extension String {
    var containsProviderEndpointMaterial: Bool {
        providerEndpointDiagnosticPatterns.contains { pattern in
            range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil
        }
    }

    var containsSensitiveRouteMaterial: Bool {
        sensitiveRouteDiagnosticPatterns.contains { pattern in
            range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil
        }
    }
}

private let providerEndpointDiagnosticPatterns = [
    #"https?://[^\s,;)]+"#,
    #"\b(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+])(?::)(?:11434|1234)\b"#,
    #"\b(?:Ollama|LM Studio)\s+URL\b"#,
    #"/(?:api/(?:tags|ps|pull|chat|show|v1)|v1/(?:models|chat|chat/completions))\b"#,
]

private let sensitiveRouteDiagnosticPatterns = [
    #"(?:^|[\s?&{,;])["']?(?:relay_secret|relaySecret|route_secret|routeSecret|route_token|routeToken|pairing_secret|pairingSecret|relay_id|relayId|relay_nonce|relayNonce|allocation_token|allocationToken|rs|rt|ri|rrn)["']?\s*(?:=|:|\s)\s*["']?[^"',\s;})]+"#,
    #"\b(?:relay_secret|relaySecret|route_secret|routeSecret|route_token|routeToken|pairing_secret|pairingSecret|relay_id|relayId|relay_nonce|relayNonce|allocation_token|allocationToken)\b"#,
]

private func remotePairingEndpoint(
    in line: String,
    oldPrefix: String,
    newPrefix: String,
    suffix: String
) -> String? {
    guard line.hasSuffix(suffix) else { return nil }
    if line.hasPrefix(newPrefix) {
        return String(line.dropFirst(newPrefix.count).dropLast(suffix.count))
    }
    if line.hasPrefix(oldPrefix) {
        return String(line.dropFirst(oldPrefix.count).dropLast(suffix.count))
    }
    return nil
}

private extension String {
    var normalizedLogAccessibilitySummaryFragment: String {
        trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: logAccessibilityTerminalPunctuation)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var nilIfEmpty: String? {
        isEmpty ? nil : self
    }
}

private let logAccessibilityTerminalPunctuation = CharacterSet(charactersIn: ".。．")
