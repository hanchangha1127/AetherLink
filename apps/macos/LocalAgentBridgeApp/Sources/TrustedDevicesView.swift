import CompanionCore
import SwiftUI

struct TrustedDevicesView: View {
    @ObservedObject var model: CompanionAppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            CompanionPageHeader(
                title: "Trusted Devices",
                subtitle: "Manage Android devices allowed to use this Mac runtime.",
                systemImage: "lock.shield.fill"
            )

            HStack(spacing: 10) {
                StatusPill(text: deviceCountText, tone: model.trustedDevices.isEmpty ? .inactive : .ready)

                Spacer()

                Button {
                    Task { await model.refreshTrustedDevices() }
                } label: {
                    Label("Refresh Devices", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
            }

            CompanionPanel(title: "Allowed Devices", systemImage: "iphone") {
                if model.trustedDevices.isEmpty {
                    ContentUnavailableView(
                        "No trusted Android devices",
                        systemImage: "lock.slash",
                        description: Text("Pair an Android device before allowing runtime commands.")
                    )
                    .frame(maxWidth: .infinity, minHeight: 280)
                } else {
                    List(model.trustedDevices) { device in
                        TrustedDeviceRow(
                            name: device.name,
                            id: device.id,
                            pairedAt: device.pairedAt
                        ) {
                            Task { await model.removeTrustedDevice(device) }
                        }
                        .padding(.vertical, 6)
                    }
                    .listStyle(.inset)
                    .frame(minHeight: 280)
                }
            }

            Spacer(minLength: 0)
        }
        .padding(24)
        .task {
            await model.refreshTrustedDevices()
        }
    }

    private var deviceCountText: String {
        String(
            format: NSLocalizedString("%d trusted device(s)", comment: ""),
            model.trustedDevices.count
        )
    }
}

private struct TrustedDeviceRow: View {
    let name: String
    let id: String
    let pairedAt: Date
    let onRemove: () -> Void

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            Image(systemName: "iphone")
                .font(.title3)
                .foregroundStyle(.tint)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 4) {
                Text(name)
                    .font(.headline)
                    .lineLimit(1)
                Text(
                    String(
                        format: NSLocalizedString("Paired %@ · ID ending %@", comment: ""),
                        companionDateFormatter.string(from: pairedAt),
                        shortIdentifier(id)
                    )
                )
                .foregroundStyle(.secondary)
                .font(.caption)
                .lineLimit(1)
                .truncationMode(.middle)
            }

            Spacer(minLength: 12)

            Button(role: .destructive, action: onRemove) {
                Label("Remove Trust", systemImage: "trash")
            }
            .labelStyle(.titleAndIcon)
            .buttonStyle(.bordered)
            .controlSize(.small)
        }
    }
}
