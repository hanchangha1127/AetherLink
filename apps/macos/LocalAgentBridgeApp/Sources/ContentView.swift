import CompanionCore
import SwiftUI

struct ContentView: View {
    @ObservedObject private var model: CompanionAppModel
    @Binding private var requestedSection: CompanionSection?
    @SceneStorage("selectedSection") private var selectedSection = CompanionSection.status
    @AppStorage(AetherLinkAppLanguageStorageKey) private var appLanguageTag = AetherLinkAppLanguage.defaultLanguage.rawValue
    @AppStorage(AetherLinkAppAppearanceStorageKey) private var appAppearance = AetherLinkAppAppearance.defaultAppearance.rawValue

    init(
        model: CompanionAppModel,
        requestedSection: Binding<CompanionSection?> = .constant(nil)
    ) {
        self.model = model
        self._requestedSection = requestedSection
    }

    var body: some View {
        NavigationSplitView {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    Image(systemName: "bolt.horizontal.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.tint)
                        .frame(width: 30, height: 30)
                        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8))
                        .accessibilityHidden(true)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(NSLocalizedString("AetherLink", comment: ""))
                            .font(.headline.weight(.semibold))
                        Text(NSLocalizedString("Runtime", comment: ""))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.horizontal, 14)
                .padding(.top, 12)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(Text(sidebarBrandAccessibilityLabel()))
                .accessibilityAddTraits(.isHeader)

                List(CompanionSection.allCases, selection: $selectedSection) { section in
                    Label(section.title, systemImage: section.systemImage)
                        .tag(section)
                }
                .listStyle(.sidebar)

                Divider()
                    .padding(.horizontal, 12)

                VStack(alignment: .leading, spacing: 8) {
                    Text(appPreferencesAccessibilityLabel())
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                        .accessibilityAddTraits(.isHeader)
                    AetherLinkAppearancePicker(appearance: appearanceBinding)
                    AetherLinkLanguagePicker(languageTag: languageBinding)
                }
                    .padding(.horizontal, 12)
                    .padding(.bottom, 12)
            }
            .background(.bar)
            .navigationSplitViewColumnWidth(min: 180, ideal: 220)
        } detail: {
            switch selectedSection {
            case .status:
                StatusView(
                    model: model,
                    onGenerateRelayQRCode: {
                        model.requestPairingForUserInterface()
                        selectedSection = .pairing
                    },
                    onGenerateRemoteRelayQRCode: {
                        model.requestRemotePairingForUserInterface()
                        selectedSection = .pairing
                    }
                )
            case .pairing:
                PairingView(model: model)
            case .trustedDevices:
                TrustedDevicesView(model: model)
            case .logs:
                LogsView(model: model)
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                ForEach(companionPrimaryActionOrder(trustedDeviceCount: model.trustedDevices.count)) { action in
                    toolbarPrimaryAction(action)
                }
            }
        }
        .onAppear {
            selectedSection = companionSectionAfterExternalRequest(
                current: selectedSection,
                trustedDeviceCount: model.trustedDevices.count,
                requested: requestedSection
            )
            requestedSection = nil
        }
        .onChange(of: requestedSection) { _, requested in
            guard let requested else { return }
            selectedSection = companionSectionAfterExternalRequest(
                current: selectedSection,
                trustedDeviceCount: model.trustedDevices.count,
                requested: requested
            )
            requestedSection = nil
        }
        .onChange(of: model.trustedDevices.count) { previousTrustedDeviceCount, trustedDeviceCount in
            selectedSection = companionSectionAfterTrustedDeviceCountChange(
                current: selectedSection,
                previousTrustedDeviceCount: previousTrustedDeviceCount,
                trustedDeviceCount: trustedDeviceCount
            )
        }
    }

    private var languageBinding: Binding<String> {
        Binding(
            get: {
                AetherLinkAppLanguage.normalized(appLanguageTag).rawValue
            },
            set: { newValue in
                appLanguageTag = AetherLinkAppLanguage.normalized(newValue).rawValue
            }
        )
    }

    private var appearanceBinding: Binding<String> {
        Binding(
            get: {
                AetherLinkAppAppearance.normalized(appAppearance).rawValue
            },
            set: { newValue in
                appAppearance = AetherLinkAppAppearance.normalized(newValue).rawValue
            }
        )
    }

    private var canGeneratePairingQR: Bool {
        pairingQRGenerationCommandAvailable(
            canRequestPairing: model.canRequestPairingForUserInterface
        )
    }

    @ViewBuilder
    private func toolbarPrimaryAction(_ action: CompanionPrimaryAction) -> some View {
        switch action {
        case .refreshProviders:
            Button {
                Task { await model.refreshBackendStatus() }
            } label: {
                Label(NSLocalizedString("Check Model Providers", comment: ""), systemImage: "arrow.clockwise")
            }
            .help(modelProviderCheckActionAccessibilityHint())
            .accessibilityValue(Text(modelProviderCheckActionAccessibilityValue()))
            .accessibilityHint(Text(modelProviderCheckActionAccessibilityHint()))

        case .loadModels:
            Button {
                Task { await model.loadModels() }
            } label: {
                Label(NSLocalizedString("Load Models", comment: ""), systemImage: "shippingbox")
            }
            .help(modelListLoadActionAccessibilityHint())
            .accessibilityValue(Text(modelListLoadActionAccessibilityValue()))
            .accessibilityHint(Text(modelListLoadActionAccessibilityHint()))

        case .pairingQR:
            Button {
                model.requestPairingForUserInterface()
                selectedSection = .pairing
            } label: {
                if model.pairingSession == nil {
                    Label(NSLocalizedString("Generate Pairing QR", comment: ""), systemImage: "qrcode")
                } else {
                    Label(NSLocalizedString("Generate New QR", comment: ""), systemImage: "arrow.triangle.2.circlepath")
                }
            }
            .disabled(!canGeneratePairingQR)
            .help(
                pairingQRGenerationActionAccessibilityHint(
                    isAvailable: canGeneratePairingQR,
                    isPreparing: model.isRemoteRoutePreparationInFlight
                )
            )
            .accessibilityValue(
                Text(
                    pairingQRGenerationActionAccessibilityValue(
                        isAvailable: canGeneratePairingQR,
                        isPreparing: model.isRemoteRoutePreparationInFlight
                    )
                )
            )
            .accessibilityHint(
                Text(
                    pairingQRGenerationActionAccessibilityHint(
                        isAvailable: canGeneratePairingQR,
                        isPreparing: model.isRemoteRoutePreparationInFlight
                    )
                )
            )
        }
    }
}

func pairingQRGenerationCommandAvailable(
    canRequestPairing: Bool
) -> Bool {
    canRequestPairing
}

func pairingQRGenerationCommandHelpText(isAvailable: Bool) -> String {
    isAvailable
        ? NSLocalizedString("Generate Pairing QR", comment: "")
        : NSLocalizedString("Pairing from another network needs connection details inside the pairing QR.", comment: "")
}

func pairingQRGenerationActionAccessibilityValue(
    isAvailable: Bool,
    hasAction: Bool = true,
    isPreparing: Bool = false
) -> String {
    if hasAction && isPreparing {
        return NSLocalizedString("Connection preparation in progress", comment: "")
    }
    return isAvailable && hasAction
        ? NSLocalizedString("Ready", comment: "")
        : NSLocalizedString("Unavailable", comment: "")
}

func pairingQRGenerationActionAccessibilityHint(
    isAvailable: Bool,
    hasAction: Bool = true,
    isPreparing: Bool = false
) -> String {
    if !hasAction {
        return NSLocalizedString("Pairing QR generation is unavailable from this view.", comment: "")
    }
    if isPreparing {
        return NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
    }
    return pairingQRGenerationCommandHelpText(isAvailable: isAvailable)
}

func activePairingQRRenewalActionAccessibilityHint(
    isAvailable: Bool = true,
    isPreparing: Bool = false
) -> String {
    if isPreparing {
        return NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
    }
    return isAvailable
        ? NSLocalizedString("Generate New QR", comment: "")
        : NSLocalizedString("Restore connection details before generating a new QR.", comment: "")
}

private struct AetherLinkAppearancePicker: View {
    @Binding var appearance: String

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Picker(selection: $appearance) {
                ForEach(AetherLinkAppAppearance.pickerOptions) { option in
                    Text(option.title)
                        .tag(option.rawValue)
                }
            } label: {
                Label(NSLocalizedString("Appearance", comment: ""), systemImage: "circle.lefthalf.filled")
            }
            .pickerStyle(.menu)
            .controlSize(.small)
            .accessibilityValue(Text(AetherLinkAppAppearance.normalized(appearance).title))
            .accessibilityHint(Text(appAppearancePickerAccessibilityHint()))

            Text(appAppearancePickerDetailText())
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(3)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityHidden(true)
        }
    }
}

private struct AetherLinkLanguagePicker: View {
    @Binding var languageTag: String

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Picker(selection: $languageTag) {
                ForEach(AetherLinkAppLanguage.pickerOptions) { language in
                    Text(language.title)
                        .tag(language.rawValue)
                }
            } label: {
                Label(NSLocalizedString("Language", comment: ""), systemImage: "globe")
            }
            .pickerStyle(.menu)
            .controlSize(.small)
            .accessibilityValue(Text(AetherLinkAppLanguage.normalized(languageTag).title))
            .accessibilityHint(Text(appLanguagePickerAccessibilityHint()))

            Text(appLanguagePickerDetailText())
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(3)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityHidden(true)
        }
    }
}

func appAppearancePickerAccessibilityHint() -> String {
    NSLocalizedString("Choose how AetherLink Runtime appears. This setting is saved for future launches.", comment: "")
}

func appLanguagePickerAccessibilityHint() -> String {
    NSLocalizedString("Choose the app language. This setting is saved for future launches.", comment: "")
}

func appAppearancePickerDetailText() -> String {
    NSLocalizedString("System follows this device's appearance. Saved for future launches.", comment: "")
}

func appLanguagePickerDetailText() -> String {
    NSLocalizedString("Choose one of the supported app languages. Saved for future launches.", comment: "")
}

func appPreferencesAccessibilityLabel() -> String {
    NSLocalizedString("App Preferences", comment: "")
}

enum CompanionSection: String, CaseIterable, Identifiable {
    case status
    case pairing
    case trustedDevices
    case logs

    var id: String { rawValue }

    var title: String {
        switch self {
        case .status:
            return NSLocalizedString("Status", comment: "")
        case .pairing:
            return NSLocalizedString("Pairing", comment: "")
        case .trustedDevices:
            return NSLocalizedString("Trusted Devices", comment: "")
        case .logs:
            return NSLocalizedString("Activity", comment: "")
        }
    }

    var systemImage: String {
        switch self {
        case .status: "bolt.horizontal.circle"
        case .pairing: "qrcode"
        case .trustedDevices: "lock.shield"
        case .logs: "list.bullet.rectangle"
        }
    }
}

func companionOnboardingSection(
    current: CompanionSection,
    trustedDeviceCount: Int
) -> CompanionSection {
    if trustedDeviceCount == 0 {
        return .pairing
    }
    return current
}

func companionSectionAfterExternalRequest(
    current: CompanionSection,
    trustedDeviceCount: Int,
    requested: CompanionSection?
) -> CompanionSection {
    if let requested {
        return requested
    }
    return companionOnboardingSection(
        current: current,
        trustedDeviceCount: trustedDeviceCount
    )
}

func companionSectionAfterTrustedDeviceCountChange(
    current: CompanionSection,
    previousTrustedDeviceCount: Int,
    trustedDeviceCount: Int
) -> CompanionSection {
    if trustedDeviceCount == 0 {
        return .pairing
    }
    if previousTrustedDeviceCount == 0, current == .pairing {
        return .status
    }
    return current
}

func sidebarBrandAccessibilityLabel() -> String {
    NSLocalizedString("AetherLink Runtime", comment: "")
}
