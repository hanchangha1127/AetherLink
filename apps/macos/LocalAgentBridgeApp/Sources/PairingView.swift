import CompanionCore
import AppKit
import CoreImage.CIFilterBuiltins
import SwiftUI

struct PairingView: View {
    @ObservedObject var model: CompanionAppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                CompanionPageHeader(
                    title: "Pair an Android Device",
                    subtitle: "Create a one-time QR code for AetherLink on Android.",
                    systemImage: "qrcode"
                )

                CompanionPanel(title: "Pairing Code", systemImage: "qrcode") {
                    if let session = model.pairingSession {
                        ActivePairingCard(
                            qrPayload: session.qrPayload,
                            code: session.code,
                            expiresAt: session.expiresAt
                        )
                    } else {
                        ContentUnavailableView(
                            "No active pairing code",
                            systemImage: "qrcode",
                            description: Text("Start pairing when the Android app is ready to scan.")
                        )
                        .frame(maxWidth: .infinity, minHeight: 240)
                    }
                }

                HStack {
                    Button {
                        model.beginPairing()
                    } label: {
                        if model.pairingSession == nil {
                            Label("Start Pairing", systemImage: "qrcode")
                        } else {
                            Label("Generate New Code", systemImage: "arrow.clockwise")
                        }
                    }
                    .buttonStyle(.borderedProminent)

                    Text("Android connects to this Mac runtime, not directly to Ollama or LM Studio.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(24)
            .frame(maxWidth: 920, alignment: .leading)
        }
    }
}

private struct ActivePairingCard: View {
    let qrPayload: String
    let code: String
    let expiresAt: Date

    var body: some View {
        ViewThatFits(in: .horizontal) {
            content(axis: .horizontal)
            content(axis: .vertical)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func content(axis: Axis) -> some View {
        let spacing: CGFloat = axis == .horizontal ? 22 : 16
        if axis == .horizontal {
            HStack(alignment: .center, spacing: spacing) {
                qrCode
                instructions
            }
        } else {
            VStack(alignment: .leading, spacing: spacing) {
                qrCode
                instructions
            }
        }
    }

    private var qrCode: some View {
        QRCodeView(text: qrPayload)
            .frame(width: 198, height: 198)
            .padding(14)
            .background(Color.white, in: RoundedRectangle(cornerRadius: 8))
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(.black.opacity(0.12), lineWidth: 1)
            }
            .shadow(color: .black.opacity(0.08), radius: 10, y: 4)
            .accessibilityLabel(Text("Pairing QR code"))
    }

    private var instructions: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 4) {
                Text("One-Time Code")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(groupedPairingCode(code))
                    .font(.system(size: 48, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .minimumScaleFactor(0.65)
                    .lineLimit(1)
                    .textSelection(.enabled)
            }

            VStack(alignment: .leading, spacing: 7) {
                Label("Scan the QR code or enter the code in AetherLink for Android.", systemImage: "iphone")
                Label("If macOS asks for Local Network access, allow it so Android can discover and pair with this Mac.", systemImage: "network")
                Label(expirationText, systemImage: "timer")
                Label("Keep this Mac awake until pairing completes.", systemImage: "display")
            }
            .font(.callout)
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var expirationText: String {
        String(
            format: NSLocalizedString("Expires %@", comment: ""),
            companionDateFormatter.string(from: expiresAt)
        )
    }
}

private struct QRCodeView: View {
    let text: String

    var body: some View {
        if let image = Self.image(from: text) {
            Image(nsImage: image)
                .interpolation(.none)
                .resizable()
                .scaledToFit()
        } else {
            Image(systemName: "qrcode")
                .resizable()
                .scaledToFit()
                .foregroundStyle(.secondary)
                .accessibilityLabel(Text("Pairing QR code unavailable"))
        }
    }

    private static func image(from text: String) -> NSImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        filter.correctionLevel = "M"

        let colorFilter = CIFilter.falseColor()
        colorFilter.inputImage = filter.outputImage
        colorFilter.color0 = CIColor(red: 0, green: 0, blue: 0)
        colorFilter.color1 = CIColor(red: 1, green: 1, blue: 1)

        guard let outputImage = colorFilter.outputImage else { return nil }
        let scaledImage = outputImage.transformed(by: CGAffineTransform(scaleX: 12, y: 12))
        guard let cgImage = CIContext().createCGImage(scaledImage, from: scaledImage.extent) else {
            return nil
        }
        return NSImage(
            cgImage: cgImage,
            size: NSSize(width: scaledImage.extent.width, height: scaledImage.extent.height)
        )
    }
}
