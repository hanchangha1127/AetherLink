import Foundation
import SwiftUI

let AetherLinkAppLanguageStorageKey = "aetherlink.appLanguageTag"
let AetherLinkAppAppearanceStorageKey = "aetherlink.appAppearance"

enum AetherLinkAppLanguage: String, CaseIterable, Identifiable {
    case english = "en"
    case korean = "ko"
    case japanese = "ja"
    case simplifiedChinese = "zh-Hans"
    case french = "fr"

    static let defaultLanguage = AetherLinkAppLanguage.english
    static let pickerOptions: [AetherLinkAppLanguage] = [
        .english,
        .korean,
        .japanese,
        .simplifiedChinese,
        .french,
    ]

    var id: String { rawValue }

    var localeIdentifier: String { rawValue }

    var title: String {
        switch self {
        case .english:
            return "English"
        case .korean:
            return "한국어"
        case .japanese:
            return "日本語"
        case .simplifiedChinese:
            return "简体中文"
        case .french:
            return "Français"
        }
    }

    static func normalized(_ languageTag: String?) -> AetherLinkAppLanguage {
        let normalized = languageTag?
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "_", with: "-")
            ?? ""

        if normalized.isEmpty {
            return defaultLanguage
        }
        if normalized.caseInsensitiveCompare("zh-CN") == .orderedSame ||
            normalized.caseInsensitiveCompare("zh-Hans") == .orderedSame ||
            normalized.caseInsensitiveCompare("zh-rCN") == .orderedSame ||
            normalized.caseInsensitiveCompare("zh-Hans-CN") == .orderedSame {
            return .simplifiedChinese
        }
        let baseLanguage = normalized.split(separator: "-", maxSplits: 1).first.map(String.init) ?? normalized
        return allCases.first { language in
            language.rawValue.caseInsensitiveCompare(normalized) == .orderedSame ||
                language.rawValue.caseInsensitiveCompare(baseLanguage) == .orderedSame
        }
            ?? defaultLanguage
    }

    static var selected: AetherLinkAppLanguage {
        normalized(UserDefaults.standard.string(forKey: AetherLinkAppLanguageStorageKey))
    }
}

enum AetherLinkAppAppearance: String, CaseIterable, Identifiable {
    case system
    case light
    case dark

    static let defaultAppearance = AetherLinkAppAppearance.system
    static let pickerOptions: [AetherLinkAppAppearance] = [
        .system,
        .light,
        .dark,
    ]

    var id: String { rawValue }

    var title: String {
        switch self {
        case .system:
            return NSLocalizedString("System", comment: "")
        case .light:
            return NSLocalizedString("Light", comment: "")
        case .dark:
            return NSLocalizedString("Dark", comment: "")
        }
    }

    var preferredColorScheme: ColorScheme? {
        switch self {
        case .system:
            return nil
        case .light:
            return .light
        case .dark:
            return .dark
        }
    }

    static func normalized(_ rawValue: String?) -> AetherLinkAppAppearance {
        let normalized = rawValue?
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            ?? ""

        return allCases.first { $0.rawValue == normalized } ?? defaultAppearance
    }
}

func NSLocalizedString(_ key: String, comment: String) -> String {
    let language = AetherLinkAppLanguage.selected
    let resourceCandidates = [language.localeIdentifier, language.localeIdentifier.lowercased()]
    for resourceName in resourceCandidates {
        if let localizedBundleURL = Bundle.module.url(
            forResource: resourceName,
            withExtension: "lproj"
        ),
           let localizedBundle = Bundle(url: localizedBundleURL) {
            return localizedBundle.localizedString(forKey: key, value: key, table: nil)
        }
    }
    return Bundle.module.localizedString(forKey: key, value: key, table: nil)
}

func localizedTrustedDeviceCount(_ count: Int) -> String {
    localizedCount(count, singularKey: "1 trusted device", pluralKey: "%d trusted devices")
}

func localizedModelCount(_ count: Int) -> String {
    localizedCount(count, singularKey: "1 model", pluralKey: "%d models")
}

func localizedLoadedModelCount(_ count: Int) -> String {
    localizedCount(count, singularKey: "1 model loaded", pluralKey: "%d models loaded")
}

func localizedAvailableModelProviderCount(_ count: Int) -> String {
    localizedCount(count, singularKey: "1 model provider available", pluralKey: "%d model providers available")
}

func localizedRuntimeActiveChatSessionCount(_ count: Int) -> String {
    localizedCount(max(0, count), singularKey: "1 active chat", pluralKey: "%d active chats")
}

func localizedRuntimeArchivedChatSessionCount(_ count: Int) -> String {
    localizedCount(max(0, count), singularKey: "1 archived chat", pluralKey: "%d archived chats")
}

func localizedRuntimeSavedChatSessionCount(_ count: Int) -> String {
    localizedCount(max(0, count), singularKey: "1 saved chat", pluralKey: "%d saved chats")
}

func localizedRuntimeChatMessageCount(_ count: Int) -> String {
    localizedCount(max(0, count), singularKey: "1 message", pluralKey: "%d messages")
}

func localizedRuntimeDeletedChatCount(_ count: Int) -> String {
    localizedCount(max(0, count), singularKey: "1 deleted chat", pluralKey: "%d deleted chats")
}

func localizedRuntimeSavedMemoryCount(_ count: Int) -> String {
    localizedCount(max(0, count), singularKey: "1 saved memory note", pluralKey: "%d saved memory notes")
}

func localizedRuntimeEnabledMemoryCount(_ count: Int) -> String {
    localizedCount(max(0, count), singularKey: "1 enabled memory note", pluralKey: "%d enabled memory notes")
}

func localizedRuntimePausedMemoryCount(_ count: Int) -> String {
    localizedCount(max(0, count), singularKey: "1 paused memory note", pluralKey: "%d paused memory notes")
}

func localizedLoadedLocalModelLogCount(_ countText: String) -> String {
    if Int(countText.trimmingCharacters(in: .whitespacesAndNewlines)) == 1 {
        return NSLocalizedString("Loaded 1 model", comment: "")
    }
    return String(format: NSLocalizedString("Loaded %@ models", comment: ""), countText)
}

func localizedModelResidencyActiveDetail(
    providerName: String,
    modelID: String,
    idleUnloadMinutes: Int
) -> String {
    if idleUnloadMinutes == 1 {
        return String(
            format: NSLocalizedString("%@ %@ active. Idle unload after 1 minute.", comment: ""),
            providerName,
            modelID
        )
    }
    return String(
        format: NSLocalizedString("%@ %@ active. Idle unload after %d minutes.", comment: ""),
        providerName,
        modelID,
        idleUnloadMinutes
    )
}

private func localizedCount(_ count: Int, singularKey: String, pluralKey: String) -> String {
    if count == 1 {
        return NSLocalizedString(singularKey, comment: "")
    }
    return String(format: NSLocalizedString(pluralKey, comment: ""), count)
}
