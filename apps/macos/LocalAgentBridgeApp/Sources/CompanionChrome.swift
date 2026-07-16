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
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text(companionPageHeaderAccessibilityLabel(title: title, subtitle: subtitle)))
        .accessibilityAddTraits(.isHeader)
    }
}

func companionPageHeaderAccessibilityLabel(title: String, subtitle: String) -> String {
    let cleanTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
    let cleanSubtitle = subtitle.trimmingCharacters(in: .whitespacesAndNewlines)

    switch (cleanTitle.isEmpty, cleanSubtitle.isEmpty) {
    case (false, false):
        return String(
            format: NSLocalizedString("%@. %@", comment: "Accessibility label joining a page title and subtitle."),
            cleanTitle,
            cleanSubtitle
        )
    case (false, true):
        return cleanTitle
    case (true, false):
        return cleanSubtitle
    case (true, true):
        return ""
    }
}

func companionEmptyStateAccessibilityLabel(title: String, description: String) -> String {
    companionPageHeaderAccessibilityLabel(title: title, subtitle: description)
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
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(Text(companionPanelHeaderAccessibilityLabel(title: title)))
                .accessibilityAddTraits(.isHeader)

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

func companionPanelHeaderAccessibilityLabel(title: String) -> String {
    title.trimmingCharacters(in: .whitespacesAndNewlines)
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
        return NSLocalizedString("Ready for devices", comment: "")
    case .failed:
        return NSLocalizedString("AetherLink Runtime needs attention", comment: "")
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
        return localizedAvailableModelProviderCount(availableCount)
    }

    return NSLocalizedString("No model provider is responding.", comment: "")
}

struct MenuBarCommandTitles: Equatable {
    let openAetherLink: String
    let refresh: String
    let loadModels: String
    let refreshModelResidency: String
    let unloadResidentModel: String
    let quit: String
}

enum CompanionPrimaryAction: String, CaseIterable, Identifiable {
    case pairingQR
    case refreshProviders
    case loadModels

    var id: String { rawValue }
}

func menuBarRuntimeStatusText(_ status: CompanionTransportStatus) -> String {
    String(
        format: NSLocalizedString("Runtime: %@", comment: ""),
        localizedTransportStatus(status)
    )
}

func menuBarRuntimeStatusAccessibilityLabel(_ status: CompanionTransportStatus) -> String {
    String(
        format: NSLocalizedString("Runtime status: %@", comment: "Accessibility label for menu-bar runtime status."),
        localizedTransportStatus(status)
    )
}

func menuBarModelServiceStatusText(_ statuses: [CompanionProviderStatus]) -> String {
    String(
        format: NSLocalizedString("Model service: %@", comment: ""),
        localizedBackendStatus(statuses)
    )
}

func menuBarModelServiceStatusAccessibilityLabel(_ statuses: [CompanionProviderStatus]) -> String {
    String(
        format: NSLocalizedString("Model service status: %@", comment: "Accessibility label for menu-bar model-service status."),
        localizedBackendStatus(statuses)
    )
}

func menuBarCommandTitles() -> MenuBarCommandTitles {
    MenuBarCommandTitles(
        openAetherLink: NSLocalizedString("Open AetherLink", comment: ""),
        refresh: NSLocalizedString("Refresh", comment: ""),
        loadModels: NSLocalizedString("Load Models", comment: ""),
        refreshModelResidency: NSLocalizedString("Refresh Model Residency", comment: ""),
        unloadResidentModel: NSLocalizedString("Unload Resident Model", comment: ""),
        quit: NSLocalizedString("Quit", comment: "")
    )
}

func menuBarOpenAetherLinkAccessibilityHint() -> String {
    NSLocalizedString("Open the AetherLink window and bring it to the front.", comment: "")
}

func menuBarQuitAccessibilityHint() -> String {
    NSLocalizedString("Quit AetherLink Runtime.", comment: "")
}

func companionPrimaryActionOrder(trustedDeviceCount: Int) -> [CompanionPrimaryAction] {
    if trustedDeviceCount <= 0 {
        return [.pairingQR, .refreshProviders, .loadModels]
    }
    return [.refreshProviders, .loadModels, .pairingQR]
}

func pairingQRGenerationCommandTitle(hasActiveSession: Bool) -> String {
    if hasActiveSession {
        return NSLocalizedString("Generate New QR", comment: "")
    }
    return NSLocalizedString("Generate Pairing QR", comment: "")
}

func modelProviderCheckActionAccessibilityValue() -> String {
    NSLocalizedString("Ready", comment: "")
}

func modelProviderCheckActionAccessibilityHint() -> String {
    NSLocalizedString("Check model provider availability through AetherLink Runtime.", comment: "")
}

func modelListLoadActionAccessibilityValue() -> String {
    NSLocalizedString("Ready", comment: "")
}

func modelListLoadActionAccessibilityHint() -> String {
    NSLocalizedString("Load the installed local model list through AetherLink Runtime.", comment: "")
}

func refreshRuntimeDataActionAccessibilityValue() -> String {
    NSLocalizedString("Ready", comment: "")
}

func refreshRuntimeDataActionAccessibilityHint() -> String {
    NSLocalizedString("Refresh runtime-owned chat history and memory counts.", comment: "")
}

func refreshModelResidencyActionAccessibilityValue() -> String {
    NSLocalizedString("Ready", comment: "")
}

func refreshModelResidencyActionAccessibilityHint() -> String {
    NSLocalizedString("Refresh the runtime model residency status.", comment: "")
}

func unloadResidentModelActionAccessibilityValue(
    canUnload: Bool,
    inFlightGenerations: Int,
    isUnloading: Bool = false
) -> String {
    if isUnloading {
        return NSLocalizedString("Model unload in progress", comment: "")
    }
    if inFlightGenerations > 0 {
        return NSLocalizedString("Generation in progress", comment: "")
    }
    return canUnload
        ? NSLocalizedString("Ready", comment: "")
        : NSLocalizedString("No resident model", comment: "")
}

func unloadResidentModelActionAccessibilityHint(
    canUnload: Bool,
    inFlightGenerations: Int,
    isUnloading: Bool = false
) -> String {
    if isUnloading {
        return NSLocalizedString("Wait for the current model unload to finish.", comment: "")
    }
    if inFlightGenerations > 0 {
        return NSLocalizedString("Wait for the active generation to finish before unloading the resident model.", comment: "")
    }
    return canUnload
        ? NSLocalizedString("Unload the active resident model now through AetherLink Runtime.", comment: "")
        : NSLocalizedString("No resident model is active through AetherLink Runtime.", comment: "")
}

func inspectRuntimeHistoryActionAccessibilityValue() -> String {
    NSLocalizedString("Ready", comment: "")
}

func inspectRuntimeHistoryActionAccessibilityHint() -> String {
    NSLocalizedString("Inspect runtime-owned chat sessions stored on AetherLink Runtime.", comment: "")
}

func inspectRuntimeMemoryActionAccessibilityValue() -> String {
    NSLocalizedString("Ready", comment: "")
}

func inspectRuntimeMemoryActionAccessibilityHint() -> String {
    NSLocalizedString("Inspect runtime-owned memory notes stored on AetherLink Runtime.", comment: "")
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

func localizedCompanionDateString(
    from date: Date,
    language: AetherLinkAppLanguage = .selected
) -> String {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: language.localeIdentifier)
    formatter.dateStyle = .medium
    formatter.timeStyle = .short
    return formatter.string(from: date)
}

func localizedCompanionByteCountString(
    fromByteCount byteCount: Int64,
    language: AetherLinkAppLanguage = .selected
) -> String {
    byteCount.formatted(
        .byteCount(style: .file)
            .locale(Locale(identifier: language.localeIdentifier))
    )
}

func localizedCompanionIntegerString(
    _ value: Int,
    language: AetherLinkAppLanguage = .selected
) -> String {
    value.formatted(
        .number.locale(Locale(identifier: language.localeIdentifier))
    )
}
