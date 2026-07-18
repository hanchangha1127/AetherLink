import CompanionCore
import CoreImage.CIFilterBuiltins
import SwiftUI

struct PairingView: View {
    @ObservedObject var model: CompanionAppModel
    let layoutObserver: PairingTaskLayoutObserver?

    init(model: CompanionAppModel, layoutObserver: PairingTaskLayoutObserver? = nil) {
        self.model = model
        self.layoutObserver = layoutObserver
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                CompanionPageHeader(
                    title: NSLocalizedString("Pair a Device", comment: ""),
                    subtitle: NSLocalizedString("Scan once from AetherLink to trust this AetherLink Runtime.", comment: ""),
                    systemImage: "qrcode"
                )

                CompanionPanel(title: NSLocalizedString("Pairing QR", comment: ""), systemImage: "qrcode") {
                    if let session = model.pairingSession {
                        ActivePairingCard(
                            qrPayload: session.compactQRCodePayload,
                            expiresAt: session.expiresAt,
                            remoteRouteExpiresAt: session.relayExpiresAtEpochMillis.map {
                                Date(timeIntervalSince1970: TimeInterval($0) / 1000)
                            },
                            routeNotice: pairingRouteNotice,
                            onGenerateNewQR: generatePairingQR
                        )
                        .id(session.id)
                    } else {
                        VStack(alignment: .leading, spacing: 14) {
                            let emptyPairingTitle = NSLocalizedString("No pairing QR ready", comment: "")
                            let emptyPairingDescription = emptyPairingQRDescription
                            ContentUnavailableView(
                                emptyPairingTitle,
                                systemImage: "qrcode",
                                description: Text(emptyPairingDescription)
                            )
                            .frame(maxWidth: .infinity, minHeight: 180)
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel(
                                Text(
                                    companionEmptyStateAccessibilityLabel(
                                        title: emptyPairingTitle,
                                        description: emptyPairingDescription
                                    )
                                )
                            )

                            Button {
                                generatePairingQR()
                            } label: {
                                Label(NSLocalizedString("Generate Pairing QR", comment: ""), systemImage: "qrcode")
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(!canGeneratePairingQR)
                            .help(pairingQRGenerationHelpText)
                            .accessibilityValue(Text(pairingQRGenerationActionAccessibilityValue(isAvailable: canGeneratePairingQR)))
                            .accessibilityHint(Text(pairingQRGenerationActionAccessibilityHint(isAvailable: canGeneratePairingQR)))

                            PairingRouteSetupNotice(routeNotice: pairingRouteNotice)
                        }
                    }
                }

                if shouldShowPairingRouteSetupPanel(model: model) {
                    RemoteRelayRoutePanel(model: model) {
                        generatePairingQR()
                    }
                }

                Text(NSLocalizedString("Paired devices connect to AetherLink Runtime, not directly to model providers.", comment: ""))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(24)
            .frame(maxWidth: 920, alignment: .leading)
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .coordinateSpace(name: PairingTaskLayoutCoordinateSpace.name)
        .onPreferenceChange(PairingTaskFramePreferenceKey.self) { frames in
            layoutObserver?.update(frames)
        }
    }

    private var pairingRouteNotice: PairingRouteNotice {
        if let issue = model.remoteRoutePreparationIssue {
            return PairingRouteNotice(
                text: remoteRoutePreparationIssueText(issue),
                systemImage: "exclamationmark.triangle",
                tone: .warning
            )
        }

        guard model.hasDevelopmentRelayRoute else {
            if model.canPrepareRemoteRelayRouteAutomatically {
                return PairingRouteNotice(
                    text: NSLocalizedString("Generate a pairing QR. AetherLink prepares connection details automatically when available.", comment: ""),
                    systemImage: "point.3.connected.trianglepath.dotted",
                    tone: .neutral
                )
            }
            return PairingRouteNotice(
                text: NSLocalizedString("Pairing QR is waiting for connection details.", comment: ""),
                systemImage: "network",
                tone: .neutral
            )
        }

        guard model.isDevelopmentRelayQRCodeReady else {
            let endpoint = model.developmentRelayEndpoint ?? NSLocalizedString("saved connection", comment: "")
            let text: String
            if !model.isDevelopmentRelayRouteEligibleForQRCode {
                text = String(
                    format: NSLocalizedString("Connection details for %@ cannot be included in this QR. Connection Recovery needs an address both devices can reach.", comment: ""),
                    endpoint
                )
            } else if !model.isDevelopmentRelayRoutePreparedForQRCode {
                text = NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
            } else {
                text = String(
                    format: NSLocalizedString("Connection details for %@ are not ready yet. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: ""),
                    endpoint
                )
            }
            return PairingRouteNotice(
                text: text,
                systemImage: "exclamationmark.triangle",
                tone: .warning
            )
        }

        let endpoint = model.developmentRelayEndpoint ?? NSLocalizedString("saved connection", comment: "")
        if model.relayFrameEncryptionEnabled {
            return PairingRouteNotice(
                text: String(
                    format: NSLocalizedString("This QR includes connection details for %@. Pairing or refresh still requires the scanning device to reach that route.", comment: ""),
                    endpoint
                ),
                systemImage: "point.3.connected.trianglepath.dotted",
                tone: .ready
            )
        }
        return PairingRouteNotice(
            text: String(
                format: NSLocalizedString("This QR includes connection details for %@, but the secure connection secret is missing.", comment: ""),
                endpoint
            ),
            systemImage: "exclamationmark.triangle",
            tone: .warning
        )
    }

    private var emptyPairingQRDescription: String {
        if let issue = model.remoteRoutePreparationIssue {
            return remoteRoutePreparationIssueText(issue)
        }
        if model.canPrepareRemoteRelayRouteAutomatically {
            return NSLocalizedString("Generate a pairing QR. AetherLink prepares connection details automatically and shows the QR when ready.", comment: "")
        }
        return NSLocalizedString("Pairing from another network needs connection details inside the pairing QR.", comment: "")
    }

    private var canGeneratePairingQR: Bool {
        pairingQRGenerationAvailable(
            canPrepareAutomatically: model.canPrepareRemoteRelayRouteAutomatically,
            isRouteEligibleForQRCode: model.isDevelopmentRelayRouteEligibleForQRCode
        )
    }

    private var pairingQRGenerationHelpText: String {
        pairingQRGenerationActionAccessibilityHint(isAvailable: canGeneratePairingQR)
    }

    private func generatePairingQR() {
        model.beginPairing(routePolicy: .remoteRequired)
    }
}

func pairingQRGenerationAvailable(
    canPrepareAutomatically: Bool,
    isRouteEligibleForQRCode: Bool
) -> Bool {
    canPrepareAutomatically || isRouteEligibleForQRCode
}

final class PairingQRCodeImageCache: ObservableObject {
    private let renderer: (String) -> NSImage?
    private var cachedPayload: String?
    private var cachedImage: NSImage?

    init(renderer: @escaping (String) -> NSImage? = pairingQRCodeImage) {
        self.renderer = renderer
    }

    func image(for payload: String) -> NSImage? {
        if cachedPayload == payload, let cachedImage {
            return cachedImage
        }
        guard let image = renderer(payload) else {
            cachedPayload = nil
            cachedImage = nil
            return nil
        }
        cachedPayload = payload
        cachedImage = image
        return image
    }
}

enum PairingTaskLayoutElement: Hashable {
    case qrCode
    case renewalAction
}

final class PairingTaskLayoutObserver {
    private(set) var frames: [PairingTaskLayoutElement: CGRect] = [:]

    func update(_ frames: [PairingTaskLayoutElement: CGRect]) {
        self.frames = frames
    }
}

private enum PairingTaskLayoutCoordinateSpace {
    static let name = "aetherlink-pairing-task-layout"
}

private struct PairingTaskFramePreferenceKey: PreferenceKey {
    static let defaultValue: [PairingTaskLayoutElement: CGRect] = [:]

    static func reduce(
        value: inout [PairingTaskLayoutElement: CGRect],
        nextValue: () -> [PairingTaskLayoutElement: CGRect]
    ) {
        value.merge(nextValue(), uniquingKeysWith: { _, next in next })
    }
}

private extension View {
    func reportPairingTaskFrame(_ element: PairingTaskLayoutElement) -> some View {
        background {
            GeometryReader { geometry in
                Color.clear.preference(
                    key: PairingTaskFramePreferenceKey.self,
                    value: [
                        element: geometry.frame(
                            in: .named(PairingTaskLayoutCoordinateSpace.name)
                        ),
                    ]
                )
            }
        }
    }
}

private struct ActivePairingCard: View {
    let qrPayload: String
    let expiresAt: Date
    let remoteRouteExpiresAt: Date?
    let routeNotice: PairingRouteNotice
    let onGenerateNewQR: () -> Void
    @State private var sessionStartedAt = Date()
    @StateObject private var qrImageCache = PairingQRCodeImageCache()

    var body: some View {
        TimelineView(.periodic(from: Date(), by: 1)) { timeline in
            let isExpired = expiresAt <= timeline.date

            ViewThatFits(in: .horizontal) {
                regularContent(at: timeline.date, isExpired: isExpired)
                compactContent(at: timeline.date, isExpired: isExpired)
                stackedContent(at: timeline.date, isExpired: isExpired)
            }
            .animation(.easeInOut(duration: 0.2), value: isExpired)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func regularContent(at date: Date, isExpired: Bool) -> some View {
        HStack(alignment: .center, spacing: 22) {
            qrCode(dimension: 252, isExpired: isExpired)
            instructions(at: date, compact: false)
        }
    }

    private func compactContent(at date: Date, isExpired: Bool) -> some View {
        HStack(alignment: .top, spacing: 16) {
            qrCode(dimension: 184, isExpired: isExpired)
            instructions(at: date, compact: true)
                .frame(minWidth: 180, maxWidth: .infinity, alignment: .leading)
                .layoutPriority(1)
        }
    }

    private func stackedContent(at date: Date, isExpired: Bool) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            qrCode(dimension: 220, isExpired: isExpired)
            instructions(at: date, compact: true)
        }
    }

    private func qrCode(dimension: CGFloat, isExpired: Bool) -> some View {
        let qrImage = qrImageCache.image(for: qrPayload)
        let isAvailable = qrImage != nil
        return QRCodeView(image: qrImage)
            .frame(width: dimension, height: dimension)
            .padding(dimension < 220 ? 10 : 14)
            .background(Color.white, in: RoundedRectangle(cornerRadius: 8))
            .opacity(isExpired ? 0.28 : 1)
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(.black.opacity(0.12), lineWidth: 1)
            }
            .overlay {
                if isExpired {
                    Label(
                        NSLocalizedString("Pairing QR expired. Generate a new QR.", comment: ""),
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
            .shadow(color: .black.opacity(0.06), radius: 6, y: 2)
            .reportPairingTaskFrame(.qrCode)
            .accessibilityElement(children: .ignore)
            .accessibilityIdentifier("pairing-active-qr")
            .accessibilityAddTraits(.isImage)
            .accessibilityLabel(Text(pairingQRCodeAccessibilityLabel()))
            .accessibilityValue(Text(pairingQRCodeAccessibilityValue(isExpired: isExpired, isAvailable: isAvailable)))
            .accessibilityHint(Text(pairingQRCodeAccessibilityHint(remoteRouteExpiresAt: remoteRouteExpiresAt)))
    }

    private func instructions(at date: Date, compact: Bool) -> some View {
        VStack(alignment: .leading, spacing: compact ? 10 : 14) {
            Label(NSLocalizedString("Scan this QR from AetherLink.", comment: ""), systemImage: "qrcode.viewfinder")
                .font(.title3.weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)

            if !compact {
                Text(NSLocalizedString("This QR verifies AetherLink Runtime and includes connection details for pairing or refresh.", comment: ""))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            VStack(alignment: .leading, spacing: 7) {
                PairingRouteNoticeLabel(routeNotice: routeNotice)
                if let remoteRouteExpiresAt {
                    Label(remoteRouteExpirationText(remoteRouteExpiresAt), systemImage: "timer")
                        .foregroundStyle(routeNotice.tone.color)
                }
                Label(expirationText(at: date), systemImage: expirationSystemImage(at: date))
                    .foregroundStyle(expiresAt <= date ? .orange : .secondary)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel(Text(pairingQRExpirationAccessibilityLabel()))
                    .accessibilityValue(Text(expirationText(at: date)))
                expirationProgress(at: date)
                    .accessibilityHidden(true)
            }
            .font(.callout)
            .fixedSize(horizontal: false, vertical: true)

            Button {
                onGenerateNewQR()
            } label: {
                Label(NSLocalizedString("Generate New QR", comment: ""), systemImage: "arrow.triangle.2.circlepath")
            }
            .buttonStyle(.bordered)
            .reportPairingTaskFrame(.renewalAction)
            .accessibilityIdentifier("pairing-renew-action")
            .help(activePairingQRRenewalActionAccessibilityHint())
            .accessibilityValue(Text(pairingQRGenerationActionAccessibilityValue(isAvailable: true)))
            .accessibilityHint(Text(activePairingQRRenewalActionAccessibilityHint()))

            if !compact {
                Label(NSLocalizedString("Keep AetherLink Runtime open until pairing completes.", comment: ""), systemImage: "display")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
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
    }

    private func expirationProgressValue(at date: Date) -> Double {
        let totalSeconds = max(1, expiresAt.timeIntervalSince(sessionStartedAt))
        let remainingSeconds = max(0, expiresAt.timeIntervalSince(date))
        return min(1, remainingSeconds / totalSeconds)
    }

    private func expirationText(at date: Date) -> String {
        pairingQRExpirationText(expiresAt: expiresAt, at: date)
    }

    private func expirationSystemImage(at date: Date) -> String {
        expiresAt <= date ? "exclamationmark.triangle.fill" : "timer"
    }

    private func remoteRouteExpirationText(_ date: Date) -> String {
        pairingQRRemoteRouteExpirationText(date)
    }

}

private struct PairingRouteNotice {
    let text: String
    let systemImage: String
    let tone: StatusTone
}

private struct PairingRouteSetupNotice: View {
    let routeNotice: PairingRouteNotice

    var body: some View {
        PairingRouteNoticeLabel(routeNotice: routeNotice)
            .font(.callout)
            .fixedSize(horizontal: false, vertical: true)
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(routeNotice.tone.color.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(routeNotice.tone.color.opacity(0.22), lineWidth: 1)
            }
    }
}

private struct PairingRouteNoticeLabel: View {
    let routeNotice: PairingRouteNotice

    var body: some View {
        Label(routeNotice.text, systemImage: routeNotice.systemImage)
            .foregroundStyle(routeNotice.tone.color)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(Text(pairingRouteNoticeAccessibilityLabel()))
            .accessibilityValue(Text(routeNotice.text))
    }
}

private struct QRCodeView: View {
    let image: NSImage?

    var body: some View {
        if let image {
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
}

func pairingQRCodeImage(from text: String) -> NSImage? {
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

func pairingQRCodeAccessibilityLabel() -> String {
    NSLocalizedString("Pairing QR code", comment: "")
}

func pairingQRCodeAccessibilityValue(isExpired: Bool, isAvailable: Bool = true) -> String {
    if !isAvailable {
        return NSLocalizedString("Pairing QR code unavailable", comment: "")
    }
    if isExpired {
        return NSLocalizedString("Pairing QR expired. Generate a new QR.", comment: "")
    }
    return NSLocalizedString("Scan this QR from AetherLink.", comment: "")
}

func pairingRouteNoticeAccessibilityLabel() -> String {
    NSLocalizedString("Pairing QR status", comment: "")
}

func pairingQRCodeAccessibilityHint(remoteRouteExpiresAt: Date? = nil) -> String {
    let baseHint = NSLocalizedString(
        "This QR verifies AetherLink Runtime and includes connection details for pairing or refresh.",
        comment: ""
    )
    guard let remoteRouteExpiresAt else { return baseHint }
    return [baseHint, pairingQRRemoteRouteExpirationText(remoteRouteExpiresAt)].joined(separator: " ")
}

func pairingQRRemoteRouteExpirationText(_ date: Date) -> String {
    String(
        format: NSLocalizedString("Connection details from this QR expire at %@. Generate a new QR if a device scans later.", comment: ""),
        localizedCompanionDateString(from: date)
    )
}

func pairingQRExpirationText(expiresAt: Date, at date: Date) -> String {
    if expiresAt <= date {
        return NSLocalizedString("Pairing QR expired. Generate a new QR.", comment: "")
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

func pairingQRExpirationAccessibilityLabel() -> String {
    NSLocalizedString("Pairing QR time remaining", comment: "")
}
