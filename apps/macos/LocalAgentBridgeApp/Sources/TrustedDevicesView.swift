import CompanionCore
import CryptoKit
import Foundation
import SwiftUI
import TrustedDevices

struct TrustedDevicesView: View {
    @ObservedObject var model: CompanionAppModel
    @State private var pendingRemovalDevice: TrustedDevice?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
                CompanionPageHeader(
                    title: NSLocalizedString("Trusted Devices", comment: ""),
                    subtitle: NSLocalizedString("Manage pairing trust and remove devices allowed to use AetherLink Runtime.", comment: ""),
                    systemImage: "lock.shield.fill"
                )

            HStack(spacing: 10) {
                StatusPill(text: deviceCountText, tone: model.trustedDevices.isEmpty ? .inactive : .ready)

                Spacer()

                Button {
                    Task { await model.refreshTrustedDevices() }
                } label: {
                    Label(NSLocalizedString("Refresh Devices", comment: ""), systemImage: "arrow.clockwise")
                }
                .buttonStyle(.bordered)
            }

            CompanionPanel(title: NSLocalizedString("Allowed Devices", comment: ""), systemImage: "person.badge.key.fill") {
                if model.trustedDevices.isEmpty {
                    ContentUnavailableView(
                        NSLocalizedString("No trusted devices", comment: ""),
                        systemImage: "lock.slash",
                        description: Text(NSLocalizedString("Pair a device before allowing runtime commands.", comment: ""))
                    )
                    .frame(maxWidth: .infinity, minHeight: 280)
                } else {
                    List(model.trustedDevices) { device in
                        TrustedDeviceRow(
                            name: device.name,
                            id: device.id,
                            keyFingerprint: trustedDeviceKeyFingerprint(device.publicKeyBase64),
                            pairedAt: device.pairedAt
                        ) {
                            pendingRemovalDevice = device
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
        .confirmationDialog(
            NSLocalizedString("Remove trusted device?", comment: ""),
            isPresented: Binding(
                get: { pendingRemovalDevice != nil },
                set: { isPresented in
                    if !isPresented {
                        pendingRemovalDevice = nil
                    }
                }
            ),
            titleVisibility: .visible
        ) {
            Button(NSLocalizedString("Remove Trust", comment: ""), role: .destructive) {
                if let device = pendingRemovalDevice {
                    pendingRemovalDevice = nil
                    Task { await model.removeTrustedDevice(device) }
                }
            }
            Button(NSLocalizedString("Cancel", comment: ""), role: .cancel) {}
        } message: {
            Text(trustedDeviceRemovalMessage(for: pendingRemovalDevice))
        }
    }

    private var deviceCountText: String {
        localizedTrustedDeviceCount(model.trustedDevices.count)
    }
}

private struct TrustedDeviceRow: View {
    let name: String
    let id: String
    let keyFingerprint: String
    let pairedAt: Date
    let onRemove: () -> Void

    var body: some View {
        let pairedSummary = String(
            format: NSLocalizedString("Paired %@ · ID ending %@", comment: ""),
            localizedCompanionDateString(from: pairedAt),
            shortIdentifier(id)
        )
        HStack(alignment: .center, spacing: 12) {
            Image(systemName: "person.crop.circle.badge.checkmark")
                .font(.title3)
                .foregroundStyle(.tint)
                .frame(width: 28)
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 4) {
                Text(name)
                    .font(.headline)
                    .lineLimit(1)
                Text(pairedSummary)
                    .foregroundStyle(.secondary)
                    .font(.caption)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Text(
                    String(
                        format: NSLocalizedString("Key fingerprint %@", comment: ""),
                        keyFingerprint
                    )
                )
                .foregroundStyle(.secondary)
                .font(.caption)
                .lineLimit(1)
                .truncationMode(.middle)
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(
                Text(
                    trustedDeviceRowAccessibilityLabel(
                        name: name,
                        pairedSummary: pairedSummary,
                        keyFingerprint: keyFingerprint
                    )
                )
            )

            Spacer(minLength: 12)

            Button(role: .destructive, action: onRemove) {
                Label(NSLocalizedString("Remove Trust", comment: ""), systemImage: "trash")
            }
            .labelStyle(.titleAndIcon)
            .buttonStyle(.bordered)
            .controlSize(.small)
            .accessibilityLabel(Text(trustedDeviceRemoveAccessibilityLabel(name: name, keyFingerprint: keyFingerprint)))
        }
    }
}

func trustedDeviceKeyFingerprint(_ publicKeyBase64: String) -> String {
    let trimmedKey = publicKeyBase64.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmedKey.isEmpty else {
        return NSLocalizedString("Unavailable", comment: "")
    }

    let keyData = Data(base64Encoded: trimmedKey) ?? Data(trimmedKey.utf8)
    let digest = SHA256.hash(data: keyData)
    return digest.prefix(6)
        .map { String(format: "%02X", $0) }
        .joined(separator: ":")
}

func trustedDeviceRemovalMessage(for device: TrustedDevice?) -> String {
    let trimmedName = device?.name.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    let name = trimmedName.isEmpty
        ? NSLocalizedString("Selected device", comment: "")
        : trimmedName
    let keyFingerprint = trustedDeviceKeyFingerprint(device?.publicKeyBase64 ?? "")
    return String(
        format: NSLocalizedString("%@ will need to pair again before it can use AetherLink Runtime. Key fingerprint %@", comment: ""),
        name,
        keyFingerprint
    )
}

func trustedDeviceRowAccessibilityLabel(name: String, pairedSummary: String, keyFingerprint: String) -> String {
    let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
    let deviceName = trimmedName.isEmpty
        ? NSLocalizedString("Selected device", comment: "")
        : trimmedName
    let trimmedPairedSummary = pairedSummary.trimmingCharacters(in: .whitespacesAndNewlines)
    let resolvedPairedSummary = trimmedPairedSummary.isEmpty
        ? NSLocalizedString("Pairing details unavailable.", comment: "")
        : trimmedPairedSummary
    let pairedSentence = resolvedPairedSummary
        .trimmingCharacters(in: .whitespacesAndNewlines)
        .trimmingCharacters(in: CharacterSet(charactersIn: ".。"))
    let trimmedFingerprint = keyFingerprint.trimmingCharacters(in: .whitespacesAndNewlines)
    let fingerprint = trimmedFingerprint.isEmpty
        ? NSLocalizedString("Unavailable", comment: "")
        : trimmedFingerprint
    return String(
        format: NSLocalizedString("Trusted device %@. %@. Key fingerprint %@", comment: ""),
        deviceName,
        pairedSentence,
        fingerprint
    )
}

func trustedDeviceRemoveAccessibilityLabel(name: String, keyFingerprint: String) -> String {
    let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
    let deviceName = trimmedName.isEmpty
        ? NSLocalizedString("Selected device", comment: "")
        : trimmedName
    let trimmedFingerprint = keyFingerprint.trimmingCharacters(in: .whitespacesAndNewlines)
    let fingerprint = trimmedFingerprint.isEmpty
        ? NSLocalizedString("Unavailable", comment: "")
        : trimmedFingerprint
    return String(
        format: NSLocalizedString("Remove trust for %@. Key fingerprint %@", comment: ""),
        deviceName,
        fingerprint
    )
}
