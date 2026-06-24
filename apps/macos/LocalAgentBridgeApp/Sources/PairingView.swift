import CompanionCore
import CoreImage.CIFilterBuiltins
import SwiftUI

struct PairingView: View {
    @ObservedObject var model: CompanionAppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                CompanionPageHeader(
                    title: NSLocalizedString("Pair a Client Device", comment: ""),
                    subtitle: NSLocalizedString("Scan once from the AetherLink client app to trust this runtime identity.", comment: ""),
                    systemImage: "qrcode"
                )

                CompanionPanel(title: NSLocalizedString("Pairing Code", comment: ""), systemImage: "qrcode") {
                    if let session = model.pairingSession {
                        ActivePairingCard(
                            qrPayload: session.qrPayload,
                            expiresAt: session.expiresAt,
                            routeNotice: pairingRouteNotice
                        )
                        .id(session.id)
                    } else {
                        ContentUnavailableView(
                            NSLocalizedString("No active pairing code", comment: ""),
                            systemImage: "qrcode",
                            description: Text(NSLocalizedString("Start pairing when the client app is ready to scan.", comment: ""))
                        )
                        .frame(maxWidth: .infinity, minHeight: 240)
                    }
                }

                HStack {
                    Button {
                        model.beginPairing()
                    } label: {
                        if model.pairingSession == nil {
                            Label(NSLocalizedString("Start Pairing", comment: ""), systemImage: "qrcode")
                        } else {
                            Label(NSLocalizedString("Generate New Code", comment: ""), systemImage: "arrow.clockwise")
                        }
                    }
                    .buttonStyle(.borderedProminent)

                    Text(NSLocalizedString("Client devices connect to this local runtime, not directly to Ollama or LM Studio.", comment: ""))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(24)
            .frame(maxWidth: 920, alignment: .leading)
        }
    }

    private var pairingRouteNotice: PairingRouteNotice {
        guard model.hasDevelopmentRelayRoute else {
            return PairingRouteNotice(
                text: NSLocalizedString("This QR uses runtime identity first. Configure Remote Relay before generating a QR for different networks.", comment: ""),
                systemImage: "network",
                tone: .neutral
            )
        }

        let endpoint = model.developmentRelayEndpoint ?? NSLocalizedString("configured relay", comment: "")
        if model.relayFrameEncryptionEnabled {
            return PairingRouteNotice(
                text: String(
                    format: NSLocalizedString("This QR includes remote relay route %@. Already trusted clients can scan it to update their saved route.", comment: ""),
                    endpoint
                ),
                systemImage: "point.3.connected.trianglepath.dotted",
                tone: .ready
            )
        }
        return PairingRouteNotice(
            text: String(
                format: NSLocalizedString("This QR includes remote relay route %@ without a relay frame secret; use only for testing.", comment: ""),
                endpoint
            ),
            systemImage: "exclamationmark.triangle",
            tone: .warning
        )
    }
}

private struct ActivePairingCard: View {
    let qrPayload: String
    let expiresAt: Date
    let routeNotice: PairingRouteNotice
    @State private var sessionStartedAt = Date()

    var body: some View {
        TimelineView(.periodic(from: Date(), by: 1)) { timeline in
            let isExpired = expiresAt <= timeline.date

            ViewThatFits(in: .horizontal) {
                content(axis: .horizontal, at: timeline.date, isExpired: isExpired)
                content(axis: .vertical, at: timeline.date, isExpired: isExpired)
            }
            .padding(16)
            .background(expirationTint(at: timeline.date), in: RoundedRectangle(cornerRadius: 12))
            .overlay {
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(expirationBorderColor(at: timeline.date), lineWidth: isExpired ? 1.5 : 1)
            }
            .animation(.easeInOut(duration: 0.2), value: isExpired)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func content(axis: Axis, at date: Date, isExpired: Bool) -> some View {
        let spacing: CGFloat = axis == .horizontal ? 22 : 16
        if axis == .horizontal {
            HStack(alignment: .center, spacing: spacing) {
                qrCode(isExpired: isExpired)
                instructions(at: date)
            }
        } else {
            VStack(alignment: .leading, spacing: spacing) {
                qrCode(isExpired: isExpired)
                instructions(at: date)
            }
        }
    }

    private func qrCode(isExpired: Bool) -> some View {
        QRCodeView(text: qrPayload)
            .frame(width: 198, height: 198)
            .padding(14)
            .background(Color.white, in: RoundedRectangle(cornerRadius: 8))
            .opacity(isExpired ? 0.28 : 1)
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(.black.opacity(0.12), lineWidth: 1)
            }
            .overlay {
                if isExpired {
                    Label(
                        NSLocalizedString("Pairing code expired. Generate a new code.", comment: ""),
                        systemImage: "exclamationmark.triangle.fill"
                    )
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(.orange)
                    .multilineTextAlignment(.center)
                    .padding(12)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
                    .padding(18)
                }
            }
            .shadow(color: .black.opacity(0.08), radius: 10, y: 4)
            .accessibilityLabel(Text(NSLocalizedString("Pairing QR code", comment: "")))
    }

    private func instructions(at date: Date) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 7) {
                Label(NSLocalizedString("Scan this QR code from the AetherLink client app.", comment: ""), systemImage: "qrcode.viewfinder")
                Label(NSLocalizedString("The QR code identifies this runtime; client apps resolve the current route after scanning.", comment: ""), systemImage: "point.3.connected.trianglepath.dotted")
                Label(routeNotice.text, systemImage: routeNotice.systemImage)
                    .foregroundStyle(routeNotice.tone.color)
                Label(NSLocalizedString("After pairing, manage or remove trusted devices in Trusted Devices.", comment: ""), systemImage: "lock.shield")
                Label(NSLocalizedString("Local Network permission enables the current local discovery path; pairing trust stays tied to this runtime identity.", comment: ""), systemImage: "network")
                Label(expirationText(at: date), systemImage: expirationSystemImage(at: date))
                    .foregroundStyle(expiresAt <= date ? .orange : .secondary)
                expirationProgress(at: date)
                Label(NSLocalizedString("Keep this runtime host awake until pairing completes.", comment: ""), systemImage: "display")
            }
            .font(.callout)
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func expirationProgress(at date: Date) -> some View {
        GeometryReader { geometry in
            let progress = expirationProgressValue(at: date)
            let width = max(0, geometry.size.width * progress)

            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Color.secondary.opacity(0.16))
                Capsule()
                    .fill(expiresAt <= date ? Color.orange : Color.accentColor)
                    .frame(width: width)
            }
        }
        .frame(height: 6)
        .frame(maxWidth: 360)
        .accessibilityLabel(Text(expirationText(at: date)))
    }

    private func expirationProgressValue(at date: Date) -> Double {
        let totalSeconds = max(1, expiresAt.timeIntervalSince(sessionStartedAt))
        let remainingSeconds = max(0, expiresAt.timeIntervalSince(date))
        return min(1, remainingSeconds / totalSeconds)
    }

    private func expirationTint(at date: Date) -> Color {
        expiresAt <= date ? Color.orange.opacity(0.08) : Color.accentColor.opacity(0.05)
    }

    private func expirationBorderColor(at date: Date) -> Color {
        expiresAt <= date ? Color.orange.opacity(0.55) : Color.primary.opacity(0.08)
    }

    private func expirationText(at date: Date) -> String {
        if expiresAt <= date {
            return NSLocalizedString("Pairing code expired. Generate a new code.", comment: "")
        }
        let remainingSeconds = max(1, Int(ceil(expiresAt.timeIntervalSince(date))))
        let minutes = remainingSeconds / 60
        let seconds = remainingSeconds % 60
        if minutes > 0 {
            return String(
                format: NSLocalizedString("Expires in %d min %02d sec", comment: ""),
                minutes,
                seconds
            )
        }
        return String(
            format: NSLocalizedString("Expires in %d sec", comment: ""),
            seconds
        )
    }

    private func expirationSystemImage(at date: Date) -> String {
        expiresAt <= date ? "exclamationmark.triangle.fill" : "timer"
    }

}

private struct PairingRouteNotice {
    let text: String
    let systemImage: String
    let tone: StatusTone
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
                .accessibilityLabel(Text(NSLocalizedString("Pairing QR code unavailable", comment: "")))
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
