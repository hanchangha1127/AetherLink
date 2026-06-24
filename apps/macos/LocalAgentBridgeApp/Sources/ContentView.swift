import CompanionCore
import SwiftUI

struct ContentView: View {
    @ObservedObject var model: CompanionAppModel
    @SceneStorage("selectedSection") private var selectedSection = CompanionSection.status

    var body: some View {
        NavigationSplitView {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    Image(systemName: "bolt.horizontal.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.tint)
                        .frame(width: 30, height: 30)
                        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8))

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

                List(CompanionSection.allCases, selection: $selectedSection) { section in
                    Label(section.title, systemImage: section.systemImage)
                        .tag(section)
                }
                .listStyle(.sidebar)
            }
            .background(.bar)
            .navigationSplitViewColumnWidth(min: 180, ideal: 220)
        } detail: {
            switch selectedSection {
            case .status:
                StatusView(
                    model: model,
                    onGenerateRelayQRCode: {
                        model.beginPairing()
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
                Button {
                    Task { await model.refreshBackendStatus() }
                } label: {
                    Label(NSLocalizedString("Check Model Providers", comment: ""), systemImage: "arrow.clockwise")
                }

                Button {
                    Task { await model.loadModels() }
                } label: {
                    Label(NSLocalizedString("Load Local Models", comment: ""), systemImage: "shippingbox")
                }

                Button {
                    model.beginPairing()
                    selectedSection = .pairing
                } label: {
                    if model.pairingSession == nil {
                        Label(NSLocalizedString("Start Pairing", comment: ""), systemImage: "qrcode")
                    } else {
                        Label(NSLocalizedString("Generate New Code", comment: ""), systemImage: "arrow.triangle.2.circlepath")
                    }
                }
            }
        }
    }
}

private enum CompanionSection: String, CaseIterable, Identifiable {
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
            return NSLocalizedString("Logs", comment: "")
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
