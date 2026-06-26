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
            return NSLocalizedString("English", comment: "")
        case .korean:
            return NSLocalizedString("Korean", comment: "")
        case .japanese:
            return NSLocalizedString("Japanese", comment: "")
        case .simplifiedChinese:
            return NSLocalizedString("Simplified Chinese", comment: "")
        case .french:
            return NSLocalizedString("French", comment: "")
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
        return allCases.first { $0.rawValue.caseInsensitiveCompare(normalized) == .orderedSame }
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
    if let localizedBundleURL = Bundle.module.url(
        forResource: language.localeIdentifier,
        withExtension: "lproj"
    ),
       let localizedBundle = Bundle(url: localizedBundleURL) {
        return localizedBundle.localizedString(forKey: key, value: key, table: nil)
    }
    return Bundle.module.localizedString(forKey: key, value: key, table: nil)
}
