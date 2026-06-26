import CompanionCore
import Foundation

func remoteRoutePreparationIssueText(_ issue: CompanionRemoteRoutePreparationIssue) -> String {
    let fallbackEndpoint = displayableRouteIssueEndpoint(issue.endpoint)

    switch issue.kind {
    case .automaticPreparationUnavailable:
        return NSLocalizedString("AetherLink could not get connection details from the route service. Check Advanced Connection Setup, then generate a fresh QR.", comment: "")
    case .automaticPreparationRejected, .routeLeaseRefreshRejected:
        if let endpoint = fallbackEndpoint {
            return String(
                format: NSLocalizedString("Connection details for %@ cannot be used from another network. Use a public, VPN, or relay address, then generate a fresh QR.", comment: ""),
                endpoint
            )
        }
        return NSLocalizedString("Connection details cannot be used from another network. Use a public, VPN, or relay address, then generate a fresh QR.", comment: "")
    case .automaticPreparationFailed, .routeLeaseRefreshFailed:
        if let endpoint = fallbackEndpoint {
            return String(
                format: NSLocalizedString("Connection details for %@ could not be prepared automatically. Check Advanced Connection Setup, then generate a fresh QR.", comment: ""),
                endpoint
            )
        }
        return NSLocalizedString("Connection details could not be prepared automatically. Check Advanced Connection Setup, then generate a fresh QR.", comment: "")
    case .routeLeaseSecretMissing:
        return NSLocalizedString("Connection details need a secure connection secret before they can be included in a QR.", comment: "")
    case .relayConnectionFailed:
        if let endpoint = fallbackEndpoint {
            return String(
                format: NSLocalizedString("Connection through %@ failed. Check Advanced Connection Setup, then generate a fresh QR.", comment: ""),
                endpoint
            )
        }
        return NSLocalizedString("Connection failed. Check Advanced Connection Setup, then generate a fresh QR.", comment: "")
    }
}

func relayQRCodeReadinessText(
    settings: CompanionDevelopmentRelaySettings,
    isEligibleForQRCode: Bool,
    isPreparedForQRCode: Bool,
    connectionStatus: CompanionDevelopmentRelayStatus
) -> String {
    guard settings.isEnabled else {
        return NSLocalizedString("Pairing from another network needs connection details inside the pairing QR.", comment: "")
    }
    guard isEligibleForQRCode else {
        return NSLocalizedString("Advanced Connection Setup needs an address reachable by both devices before it can be included in the QR.", comment: "")
    }
    guard isPreparedForQRCode else {
        return NSLocalizedString("Connection details are being prepared. Keep this window open; the QR appears when AetherLink Runtime is ready.", comment: "")
    }

    switch connectionStatus.status {
    case .stopped:
        return NSLocalizedString("Connection details are prepared, but the connection is stopped. Start AetherLink Runtime, then generate the latest QR.", comment: "")
    case .connecting:
        return NSLocalizedString("Connection details are prepared. AetherLink Runtime is connecting; generate the latest QR after the connection is ready.", comment: "")
    case .reconnecting:
        return NSLocalizedString("Connection details are prepared. AetherLink Runtime is reconnecting; generate the latest QR after the connection is ready.", comment: "")
    case .failed:
        let endpoint = connectionStatus.endpoint?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        if let endpoint {
            return String(
                format: NSLocalizedString("Connection through %@ failed. Check Advanced Connection Setup, then generate a fresh QR.", comment: ""),
                endpoint
            )
        }
        return NSLocalizedString("Connection failed. Check Advanced Connection Setup, then generate a fresh QR.", comment: "")
    case .waitingForPeer, .ready:
        return NSLocalizedString("Connection details are ready. Generate the latest QR to pair this device.", comment: "")
    }
}

func remoteRouteScopeLabel(
    settings: CompanionDevelopmentRelaySettings,
    bootstrapSettings: CompanionBootstrapRelaySettings,
    canPrepareAutomatically: Bool
) -> String {
    if settings.isEnabled {
        switch settings.hostReachabilityWarning {
        case .none:
            return NSLocalizedString("Reachable connection", comment: "")
        case .invalidFormat:
            return NSLocalizedString("Route needs attention", comment: "")
        case .loopback:
            return NSLocalizedString("Local diagnostic", comment: "")
        case .localName:
            return NSLocalizedString("Local network only", comment: "")
        case .privateNetwork:
            return settings.allowsPrivateOverlay
                ? NSLocalizedString("Private overlay", comment: "")
                : NSLocalizedString("Local network only", comment: "")
        }
    }

    if bootstrapSettings.isEnabled || canPrepareAutomatically {
        return NSLocalizedString("Automatic route", comment: "")
    }
    return NSLocalizedString("No route", comment: "")
}

func remoteRouteScopeDetail(
    settings: CompanionDevelopmentRelaySettings,
    bootstrapSettings: CompanionBootstrapRelaySettings,
    canPrepareAutomatically: Bool
) -> String {
    if settings.isEnabled {
        switch settings.hostReachabilityWarning {
        case .none:
            return NSLocalizedString("Connection details can be included in QR for devices outside this local network.", comment: "")
        case .invalidFormat:
            return NSLocalizedString("Enter only the connection address. Put the port in the Port field.", comment: "")
        case .loopback:
            return NSLocalizedString("Loopback routes only work on this runtime host or USB diagnostics, not from another network.", comment: "")
        case .localName:
            return NSLocalizedString(".local names work only on nearby local networks. Use a reachable relay, VPN, or tunnel for another network.", comment: "")
        case .privateNetwork:
            if settings.allowsPrivateOverlay {
                return NSLocalizedString("Use this only when both devices can reach the same VPN, tunnel, or private overlay.", comment: "")
            }
            return NSLocalizedString("Private addresses usually do not cross unrelated networks. Use a reachable relay, VPN, tunnel, or private overlay.", comment: "")
        }
    }

    if bootstrapSettings.isEnabled {
        return NSLocalizedString("AetherLink will request fresh QR connection details from the saved bootstrap relay.", comment: "")
    }
    if canPrepareAutomatically {
        return NSLocalizedString("AetherLink can prepare QR connection details when a pairing QR is generated.", comment: "")
    }
    return NSLocalizedString("Add a reachable route before pairing from another network.", comment: "")
}

private extension String {
    var nilIfEmpty: String? {
        isEmpty ? nil : self
    }
}

private func displayableRouteIssueEndpoint(_ endpoint: String?) -> String? {
    guard let endpoint = endpoint?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty else {
        return nil
    }
    return sanitizedTechnicalDiagnostic(endpoint) == endpoint ? endpoint : nil
}
