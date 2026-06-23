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
                        Text("AetherLink")
                            .font(.headline.weight(.semibold))
                        Text("Mac Companion")
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
                StatusView(model: model)
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
                    Label("Refresh Backend Status", systemImage: "arrow.clockwise")
                }

                Button {
                    Task { await model.loadModels() }
                } label: {
                    Label("Load Local Models", systemImage: "shippingbox")
                }

                Button {
                    model.beginPairing()
                    selectedSection = .pairing
                } label: {
                    if model.pairingSession == nil {
                        Label("Start Pairing", systemImage: "qrcode")
                    } else {
                        Label("Generate New Code", systemImage: "arrow.triangle.2.circlepath")
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

    var title: LocalizedStringKey {
        switch self {
        case .status: "Status"
        case .pairing: "Pairing"
        case .trustedDevices: "Trusted Devices"
        case .logs: "Logs"
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
