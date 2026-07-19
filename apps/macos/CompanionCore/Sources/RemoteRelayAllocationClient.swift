import BridgeProtocol
import CryptoKit
import Foundation
import Network
import Transport

public final class RelayRouteAllocationCancellation: @unchecked Sendable {
    private let condition = NSCondition()
    private var cancellationHandlers: [UUID: @Sendable () -> Void] = [:]
    private var cancelled = false
    public let deadline: Date

    public init(timeout: TimeInterval) {
        precondition(timeout > 0, "Relay route allocation timeout must be positive")
        deadline = Date().addingTimeInterval(timeout)
    }

    public var isCancelled: Bool {
        condition.withLock { cancelled }
    }

    public var isExpired: Bool {
        Date() >= deadline
    }

    public func cancel() {
        let handlers = condition.withLock { () -> [@Sendable () -> Void] in
            guard !cancelled else { return [] }
            cancelled = true
            let handlers = Array(cancellationHandlers.values)
            cancellationHandlers.removeAll()
            condition.broadcast()
            return handlers
        }
        handlers.forEach { $0() }
    }

    public func throwIfCancelledOrExpired() throws {
        if isCancelled {
            throw RelayServiceRouteAllocationError.allocationCancelled
        }
        if isExpired {
            throw RelayServiceRouteAllocationError.allocationTimedOut
        }
    }

    @discardableResult
    public func addCancellationHandler(_ handler: @escaping @Sendable () -> Void) -> UUID? {
        let identifier = UUID()
        let shouldInvoke = condition.withLock { () -> Bool in
            guard !cancelled else { return true }
            cancellationHandlers[identifier] = handler
            return false
        }
        if shouldInvoke {
            handler()
            return nil
        }
        return identifier
    }

    public func removeCancellationHandler(_ identifier: UUID?) {
        guard let identifier else { return }
        _ = condition.withLock {
            cancellationHandlers.removeValue(forKey: identifier)
        }
    }
}

public protocol RelayServiceRouteAllocating: Sendable {
    func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        allocationToken: String?,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        timeout: TimeInterval,
        cancellation: RelayRouteAllocationCancellation
    ) throws -> RelayServiceRouteAllocation

    func renewPairedRelayRoute(
        currentRouteToken: String,
        currentConfiguration: RelayPeerConfiguration,
        currentLease: CompanionRemoteRouteLease,
        runtimeIdentity: RelayRuntimeIdentity,
        authorizationSigner: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning,
        authorizationContext: RuntimePairedRelayAuthorizationContext,
        allocationToken: String?,
        timeout: TimeInterval
    ) async throws -> RelayServiceRouteAllocation
}

public extension RelayServiceRouteAllocating {
    func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        allocationToken: String? = nil,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        timeout: TimeInterval = 5
    ) throws -> RelayServiceRouteAllocation {
        try allocateRelayRoute(
            host: host,
            port: port,
            routeToken: routeToken,
            allocationToken: allocationToken,
            runtimeIdentity: runtimeIdentity,
            identityAuthorizationSigner: identityAuthorizationSigner,
            timeout: timeout,
            cancellation: RelayRouteAllocationCancellation(timeout: timeout)
        )
    }

    func renewPairedRelayRoute(
        currentRouteToken: String,
        currentConfiguration: RelayPeerConfiguration,
        currentLease: CompanionRemoteRouteLease,
        runtimeIdentity: RelayRuntimeIdentity,
        authorizationSigner: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning,
        authorizationContext: RuntimePairedRelayAuthorizationContext,
        allocationToken: String? = nil,
        timeout: TimeInterval = 5
    ) async throws -> RelayServiceRouteAllocation {
        throw RelayServiceRouteAllocationError.pairedRenewalUnavailable
    }
}

public struct RelayServiceRouteAllocation: Equatable, Sendable {
    public let host: String
    public let port: UInt16
    public let relayID: String
    public let relayExpiresAtEpochMillis: Int64
    public let relayNonce: String
    public let runtimeKeyFingerprint: String
    public let ticketGeneration: Int64
    public let cryptoVersion: Int

    public init(
        host: String,
        port: UInt16,
        relayID: String,
        relayExpiresAtEpochMillis: Int64,
        relayNonce: String,
        runtimeKeyFingerprint: String,
        ticketGeneration: Int64,
        cryptoVersion: Int = 2
    ) {
        self.host = host
        self.port = port
        self.relayID = relayID
        self.relayExpiresAtEpochMillis = relayExpiresAtEpochMillis
        self.relayNonce = relayNonce
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.ticketGeneration = ticketGeneration
        self.cryptoVersion = cryptoVersion
    }

    public func attachingEndpointSecret(
        _ relaySecret: String,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning
    ) throws -> CompanionRemoteRelayRouteAllocation {
        guard cryptoVersion == relayIdentityAuthorizationCryptoVersion,
              runtimeKeyFingerprint == runtimeIdentity.fingerprint,
              try identityAuthorizationSigner.relayRuntimeIdentity() == runtimeIdentity
        else {
            throw RelayServiceRouteAllocationError.signingIdentityMismatch
        }
        return CompanionRemoteRelayRouteAllocation(
            configuration: RelayPeerConfiguration(
                host: host,
                port: port,
                relayID: relayID,
                relaySecret: relaySecret,
                relayNonce: relayNonce,
                runtimeIdentity: runtimeIdentity,
                identityAuthorizationSigner: identityAuthorizationSigner
            ),
            lease: CompanionRemoteRouteLease(
                expiresAtEpochMillis: relayExpiresAtEpochMillis,
                nonce: relayNonce,
                ticketGeneration: ticketGeneration
            )
        )
    }
}

public struct TCPRelayServiceRouteAllocator: RelayServiceRouteAllocating {
    private let authorizationIDProvider: @Sendable () -> String

    public init() {
        authorizationIDProvider = { UUID().uuidString }
    }

    init(authorizationIDProvider: @escaping @Sendable () -> String) {
        self.authorizationIDProvider = authorizationIDProvider
    }

    public func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        allocationToken: String? = nil,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        timeout: TimeInterval = 5
    ) throws -> RelayServiceRouteAllocation {
        try allocateRelayRoute(
            host: host,
            port: port,
            routeToken: routeToken,
            allocationToken: allocationToken,
            runtimeIdentity: runtimeIdentity,
            identityAuthorizationSigner: identityAuthorizationSigner,
            timeout: timeout,
            cancellation: RelayRouteAllocationCancellation(timeout: timeout)
        )
    }

    public func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        allocationToken: String? = nil,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        timeout: TimeInterval = 5,
        cancellation: RelayRouteAllocationCancellation
    ) throws -> RelayServiceRouteAllocation {
        guard try identityAuthorizationSigner.relayRuntimeIdentity() == runtimeIdentity else {
            throw RelayServiceRouteAllocationError.signingIdentityMismatch
        }
        let connection = try RelayAllocationConnection(
            host: host,
            port: port,
            timeout: timeout,
            cancellation: cancellation
        )

        let requestLine = try Self.allocationRequestLine(
            routeToken: routeToken,
            allocationToken: allocationToken,
            runtimeIdentity: runtimeIdentity
        )
        try connection.write(Data(requestLine.utf8))
        let challenge = try Self.parseAllocationChallengeLine(
            connection.readLine(),
            routeToken: routeToken,
            runtimeIdentity: runtimeIdentity
        )
        let proof = try identityAuthorizationSigner.signRelayAllocationChallenge(challenge)
        guard proof.runtimeIdentity == runtimeIdentity,
              RelayIdentityAuthorization.verify(
                signatureBase64: proof.signatureBase64,
                messageData: challenge.signedMessageData(),
                runtimeIdentity: runtimeIdentity
              )
        else {
            throw RelayServiceRouteAllocationError.signingIdentityMismatch
        }
        try connection.write(
            Data(try Self.allocationProofLine(
                challenge: challenge.challenge,
                signatureBase64: proof.signatureBase64
            ).utf8)
        )
        let response = try Self.parseAllocationResponseLine(
            connection.readLine(),
            challenge: challenge,
            runtimeIdentity: runtimeIdentity
        )
        return RelayServiceRouteAllocation(
            host: host,
            port: port,
            relayID: response.relayID,
            relayExpiresAtEpochMillis: response.relayExpiresAtEpochMillis,
            relayNonce: response.relayNonce,
            runtimeKeyFingerprint: response.runtimeKeyFingerprint,
            ticketGeneration: response.ticketGeneration,
            cryptoVersion: response.cryptoVersion
        )
    }

    public func renewPairedRelayRoute(
        currentRouteToken: String,
        currentConfiguration: RelayPeerConfiguration,
        currentLease: CompanionRemoteRouteLease,
        runtimeIdentity: RelayRuntimeIdentity,
        authorizationSigner: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning,
        authorizationContext: RuntimePairedRelayAuthorizationContext,
        allocationToken: String? = nil,
        timeout: TimeInterval = 5
    ) async throws -> RelayServiceRouteAllocation {
        let authorizationID = authorizationIDProvider()
        let snapshot = try Self.validatePairedRenewalInputs(
            currentRouteToken: currentRouteToken,
            currentConfiguration: currentConfiguration,
            currentLease: currentLease,
            runtimeIdentity: runtimeIdentity,
            authorizationSigner: authorizationSigner,
            authorizationContext: authorizationContext,
            authorizationID: authorizationID,
            allocationToken: allocationToken,
            timeout: timeout
        )
        let cancellation = RelayRouteAllocationCancellation(timeout: timeout)
        let operation = Task.detached(priority: .userInitiated) {
            try Task.checkCancellation()
            let connection = try RelayAllocationConnection(
                host: currentConfiguration.host,
                port: currentConfiguration.port,
                timeout: timeout,
                cancellation: cancellation
            )

            let requestLine = try Self.pairedRenewalRequestLine(
                currentRouteToken: currentRouteToken,
                runtimeIdentity: runtimeIdentity,
                authorizationContext: authorizationContext,
                authorizationID: authorizationID,
                allocationToken: allocationToken
            )
            try connection.write(Data(requestLine.utf8))

            let challenge = try Self.parsePairedAllocationChallengeLine(
                connection.readLine(),
                snapshot: snapshot
            )
            let runtimeProof = try authorizationSigner.signPairedRelayAllocationAuthorization(
                challenge
            )
            guard runtimeProof.publicKeyBase64 == runtimeIdentity.publicKeyBase64,
                  runtimeProof.verify(challenge: challenge)
            else {
                throw RelayServiceRouteAllocationError.signingIdentityMismatch
            }

            let nowEpochMillis = currentEpochMillis()
            let challengeSeconds = TimeInterval(
                challenge.challengeExpiresAtEpochMillis - nowEpochMillis
            ) / 1_000
            guard challengeSeconds > 0 else {
                throw RelayServiceRouteAllocationError.invalidChallenge
            }
            let clientProof = try await awaitPairedClientAuthorization(
                timeout: min(timeout, challengeSeconds),
                provider: authorizationContext.clientAuthorizationProvider,
                challenge: challenge
            )
            guard clientProof.publicKeyBase64 == authorizationContext.trustedClientPublicKeyBase64,
                  clientProof.verify(challenge: challenge)
            else {
                throw RelayServiceRouteAllocationError.clientAuthorizationRejected
            }
            try Task.checkCancellation()
            try cancellation.throwIfCancelledOrExpired()

            let proofLine = try Self.pairedAllocationProofLine(
                challenge: challenge,
                runtimeProof: runtimeProof,
                clientProof: clientProof
            )
            try connection.write(Data(proofLine.utf8))
            let response = try Self.parsePairedAllocationResponseLine(
                connection.readLine(),
                challenge: challenge,
                runtimeIdentity: runtimeIdentity
            )
            return RelayServiceRouteAllocation(
                host: currentConfiguration.host,
                port: currentConfiguration.port,
                relayID: response.relayID,
                relayExpiresAtEpochMillis: response.relayExpiresAtEpochMillis,
                relayNonce: response.relayNonce,
                runtimeKeyFingerprint: response.runtimeKeyFingerprint,
                ticketGeneration: response.ticketGeneration,
                cryptoVersion: response.cryptoVersion
            )
        }
        return try await withTaskCancellationHandler {
            try await operation.value
        } onCancel: {
            cancellation.cancel()
            operation.cancel()
        }
    }

    static func allocationRequestLine(
        routeToken: String,
        allocationToken: String? = nil,
        runtimeIdentity: RelayRuntimeIdentity
    ) throws -> String {
        try validateRelayToken(routeToken)
        if let allocationToken {
            try validateAllocationToken(allocationToken)
        }
        var requestParts = [
            "AETHERLINK_RELAY",
            "allocate",
            routeToken,
            "crypto=2",
            "allocation_auth=\(relayIdentityAuthorizationScheme)",
            "runtime_key_fingerprint=\(runtimeIdentity.fingerprint)",
            "runtime_public_key=\(runtimeIdentity.publicKeyBase64)"
        ]
        if let allocationToken {
            requestParts.append("allocation_token=\(allocationToken)")
        }
        return requestParts.joined(separator: " ") + "\n"
    }

    static func allocationProofLine(
        challenge: String,
        signatureBase64: String
    ) throws -> String {
        guard challenge.utf8.count == 64,
              challenge.utf8.allSatisfy({
                (UInt8(ascii: "0")...UInt8(ascii: "9")).contains($0) ||
                    (UInt8(ascii: "a")...UInt8(ascii: "f")).contains($0)
              }),
              let signatureData = Data(base64Encoded: signatureBase64),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: signatureData),
              signature.derRepresentation == signatureData
        else {
            throw RelayServiceRouteAllocationError.signingIdentityMismatch
        }
        return "AETHERLINK_RELAY allocation_proof crypto=2 challenge=\(challenge) " +
            "signature=\(signatureBase64)\n"
    }

    static func parseAllocationChallengeLine(
        _ line: String,
        routeToken: String,
        runtimeIdentity: RelayRuntimeIdentity,
        now: Date = Date()
    ) throws -> RelayAllocationIdentityChallenge {
        let challenge = try RelayServiceAllocationChallenge.parse(line)
        let nowEpochMillis = Int64((now.timeIntervalSince1970 * 1_000).rounded())
        let expectedRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint
        )
        guard challenge.operation != .preflight,
              challenge.relayID == expectedRelayID,
              challenge.relayID.hasPrefix("rt2-"),
              challenge.routeTokenHash == RelayAllocationIdentityChallenge.routeTokenHash(routeToken),
              challenge.runtimeKeyFingerprint == runtimeIdentity.fingerprint,
              challenge.challengeExpiresAtEpochMillis > nowEpochMillis
        else {
            throw RelayServiceRouteAllocationError.invalidChallenge
        }
        return challenge
    }

    static func parseAllocationResponseLine(
        _ line: String,
        challenge: RelayAllocationIdentityChallenge,
        runtimeIdentity: RelayRuntimeIdentity,
        now: Date = Date()
    ) throws -> RelayServiceAllocationResponse {
        let response = try RelayServiceAllocationResponse.parse(line)
        let nowEpochMillis = Int64((now.timeIntervalSince1970 * 1_000).rounded())
        guard response.relayID == challenge.relayID,
              response.relayExpiresAtEpochMillis > nowEpochMillis,
              response.runtimeKeyFingerprint == runtimeIdentity.fingerprint,
              response.runtimeKeyFingerprint == challenge.runtimeKeyFingerprint,
              response.ticketGeneration == challenge.ticketGeneration
        else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }
        return response
    }

    static func pairedRenewalRequestLine(
        currentRouteToken: String,
        runtimeIdentity: RelayRuntimeIdentity,
        authorizationContext: RuntimePairedRelayAuthorizationContext,
        authorizationID: String,
        allocationToken: String? = nil
    ) throws -> String {
        try validateRelayToken(currentRouteToken)
        guard PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(
            authorizationContext.requestID
        ), PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(authorizationID),
            PairedRelayAllocationAuthorization.isCanonicalDigest(
                authorizationContext.transportBinding
            )
        else {
            throw RelayServiceRouteAllocationError.invalidPairedRenewalRequest
        }
        if let allocationToken {
            try validateAllocationToken(allocationToken)
        }
        var parts = [
            "AETHERLINK_RELAY",
            "renew",
            currentRouteToken,
            "crypto=2",
            "allocation_auth=\(PairedRelayAllocationAuthorization.scheme)",
            "runtime_key_fingerprint=\(runtimeIdentity.fingerprint)",
            "runtime_public_key=\(runtimeIdentity.publicKeyBase64)",
            "client_key_fingerprint=\(authorizationContext.trustedClientKeyFingerprint)",
            "client_public_key=\(authorizationContext.trustedClientPublicKeyBase64)",
            "request_id=\(authorizationContext.requestID)",
            "authorization_id=\(authorizationID)",
            "transport_binding=\(authorizationContext.transportBinding)",
        ]
        if let allocationToken {
            parts.append("allocation_token=\(allocationToken)")
        }
        return parts.joined(separator: " ") + "\n"
    }

    static func pairedAllocationProofLine(
        challenge: PairedRelayAllocationAuthorizationChallenge,
        runtimeProof: PairedRelayAllocationRuntimeProof,
        clientProof: PairedRelayAllocationClientProof
    ) throws -> String {
        guard runtimeProof.verify(challenge: challenge),
              clientProof.verify(challenge: challenge)
        else {
            throw RelayServiceRouteAllocationError.clientAuthorizationRejected
        }
        return "AETHERLINK_RELAY paired_allocation_proof crypto=2 " +
            "challenge=\(challenge.challenge) " +
            "runtime_signature=\(runtimeProof.signatureBase64) " +
            "client_signature=\(clientProof.signatureBase64)\n"
    }

    private static func validatePairedRenewalInputs(
        currentRouteToken: String,
        currentConfiguration: RelayPeerConfiguration,
        currentLease: CompanionRemoteRouteLease,
        runtimeIdentity: RelayRuntimeIdentity,
        authorizationSigner: any RelayIdentityAuthorizationSigning & PairedRelayAllocationRuntimeSigning,
        authorizationContext: RuntimePairedRelayAuthorizationContext,
        authorizationID: String,
        allocationToken: String?,
        timeout: TimeInterval,
        now: Date = Date()
    ) throws -> PairedRelayRenewalSnapshot {
        _ = try pairedRenewalRequestLine(
            currentRouteToken: currentRouteToken,
            runtimeIdentity: runtimeIdentity,
            authorizationContext: authorizationContext,
            authorizationID: authorizationID,
            allocationToken: allocationToken
        )
        let bootstrapRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: currentRouteToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: currentRouteToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: authorizationContext.trustedClientKeyFingerprint
        )
        guard timeout.isFinite, timeout > 0,
              currentConfiguration.port > 0,
              currentConfiguration.relayNonce == currentLease.nonce,
              let currentTicketGeneration = currentLease.ticketGeneration,
              currentTicketGeneration > 0,
              !currentLease.isExpired(at: now),
              currentConfiguration.relayID == bootstrapRelayID ||
                currentConfiguration.relayID == pairedRelayID,
              currentConfiguration.runtimeIdentity.map({ $0 == runtimeIdentity }) ?? true,
              try authorizationSigner.relayRuntimeIdentity() == runtimeIdentity,
              authorizationContext.trustedClientKeyFingerprint != runtimeIdentity.fingerprint
        else {
            throw RelayServiceRouteAllocationError.invalidPairedRenewalRequest
        }
        do {
            _ = try PairedRelayAllocationAuthorization.validatedRuntimePublicKey(
                base64: runtimeIdentity.publicKeyBase64,
                fingerprint: runtimeIdentity.fingerprint
            )
            _ = try PairedRelayAllocationAuthorization.validatedClientPublicKey(
                base64: authorizationContext.trustedClientPublicKeyBase64,
                fingerprint: authorizationContext.trustedClientKeyFingerprint
            )
        } catch {
            throw RelayServiceRouteAllocationError.invalidPairedRenewalRequest
        }
        return PairedRelayRenewalSnapshot(
            requestID: authorizationContext.requestID,
            authorizationID: authorizationID,
            currentRelayID: currentConfiguration.relayID,
            nextRelayID: pairedRelayID,
            routeTokenHash: PairedRelayAllocationAuthorization.routeTokenHash(
                currentRouteToken
            ),
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: authorizationContext.trustedClientKeyFingerprint,
            currentTicketGeneration: currentTicketGeneration,
            currentRelayExpiresAtEpochMillis: currentLease.expiresAtEpochMillis,
            currentRelayNonce: currentLease.nonce,
            transportBinding: authorizationContext.transportBinding
        )
    }

    private static func parsePairedAllocationChallengeLine(
        _ line: String,
        snapshot: PairedRelayRenewalSnapshot,
        now: Date = Date()
    ) throws -> PairedRelayAllocationAuthorizationChallenge {
        let data = try exactControlLineJSON(
            line,
            prefix: pairedAllocationChallengePrefix,
            allowedFieldNames: pairedAllocationChallengeFieldNames,
            error: .invalidChallenge
        )
        let challenge: PairedRelayAllocationAuthorizationChallenge
        do {
            challenge = try JSONDecoder().decode(
                PairedRelayAllocationAuthorizationChallenge.self,
                from: data
            )
        } catch {
            throw RelayServiceRouteAllocationError.invalidChallenge
        }
        let canonicalEncoder = JSONEncoder()
        canonicalEncoder.outputFormatting = [.sortedKeys]
        guard (try? canonicalEncoder.encode(challenge)) == data else {
            throw RelayServiceRouteAllocationError.invalidChallenge
        }
        let nowEpochMillis = Int64((now.timeIntervalSince1970 * 1_000).rounded())
        guard challenge.requestID == snapshot.requestID,
              challenge.authorizationID == snapshot.authorizationID,
              challenge.currentRelayID == snapshot.currentRelayID,
              challenge.nextRelayID == snapshot.nextRelayID,
              challenge.routeTokenHash == snapshot.routeTokenHash,
              challenge.runtimeKeyFingerprint == snapshot.runtimeKeyFingerprint,
              challenge.clientKeyFingerprint == snapshot.clientKeyFingerprint,
              challenge.currentTicketGeneration == snapshot.currentTicketGeneration,
              challenge.currentRelayExpiresAtEpochMillis == snapshot.currentRelayExpiresAtEpochMillis,
              challenge.currentRelayNonce == snapshot.currentRelayNonce,
              challenge.transportBinding == snapshot.transportBinding,
              challenge.isFresh(atEpochMillis: nowEpochMillis)
        else {
            throw RelayServiceRouteAllocationError.invalidChallenge
        }
        return challenge
    }

    private static func parsePairedAllocationResponseLine(
        _ line: String,
        challenge: PairedRelayAllocationAuthorizationChallenge,
        runtimeIdentity: RelayRuntimeIdentity,
        now: Date = Date()
    ) throws -> RelayServiceAllocationResponse {
        let response = try RelayServiceAllocationResponse.parse(line)
        let nowEpochMillis = Int64((now.timeIntervalSince1970 * 1_000).rounded())
        guard response.relayID == challenge.nextRelayID,
              response.relayExpiresAtEpochMillis == challenge.nextRelayExpiresAtEpochMillis,
              response.relayExpiresAtEpochMillis > nowEpochMillis,
              response.relayNonce == challenge.nextRelayNonce,
              response.runtimeKeyFingerprint == runtimeIdentity.fingerprint,
              response.runtimeKeyFingerprint == challenge.runtimeKeyFingerprint,
              response.ticketGeneration == challenge.nextTicketGeneration,
              response.cryptoVersion == 2
        else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }
        return response
    }

    private static let pairedAllocationChallengePrefix =
        "AETHERLINK_RELAY paired_allocation_challenge "

    private static let pairedAllocationChallengeFieldNames: Set<String> = [
        "scheme",
        "protocol_version",
        "operation",
        "request_id",
        "authorization_id",
        "current_relay_id",
        "next_relay_id",
        "route_token_hash",
        "runtime_key_fingerprint",
        "client_key_fingerprint",
        "current_ticket_generation",
        "next_ticket_generation",
        "current_relay_expires_at",
        "current_relay_nonce",
        "next_relay_expires_at",
        "next_relay_nonce",
        "challenge",
        "challenge_expires_at",
        "transport_binding",
    ]

}

public enum RelayServiceRouteAllocationError: Error, Equatable, LocalizedError, Sendable {
    case invalidRouteToken
    case resolveFailed(String)
    case connectFailed(String)
    case writeFailed
    case readFailed
    case invalidResponse
    case invalidChallenge
    case signingIdentityUnavailable
    case signingIdentityMismatch
    case incompleteStaticBootstrapRoute
    case invalidAllocationToken
    case invalidPairedRenewalRequest
    case pairedRenewalUnavailable
    case clientAuthorizationTimedOut
    case clientAuthorizationRejected
    case allocationCancelled
    case allocationTimedOut

    public var errorDescription: String? {
        switch self {
        case .invalidRouteToken:
            return "Remote route token is invalid."
        case .resolveFailed(let message):
            return "AetherLink Runtime connection address could not be resolved: \(message)"
        case .connectFailed(let message):
            return "Remote route allocation connection failed: \(message)"
        case .writeFailed:
            return "Remote route allocation request could not be sent."
        case .readFailed:
            return "Remote route allocation response could not be read."
        case .invalidResponse:
            return "Remote route allocation response was invalid."
        case .invalidChallenge:
            return "Remote route allocation challenge was invalid or expired."
        case .signingIdentityUnavailable:
            return "Runtime signing identity is unavailable."
        case .signingIdentityMismatch:
            return "Runtime signing identity was unavailable or changed."
        case .incompleteStaticBootstrapRoute:
            return "Bootstrap route override must include both route id and route secret."
        case .invalidAllocationToken:
            return "Route allocation token is invalid."
        case .invalidPairedRenewalRequest:
            return "The paired relay renewal request is invalid or stale."
        case .pairedRenewalUnavailable:
            return "Paired relay renewal is unavailable."
        case .clientAuthorizationTimedOut:
            return "Paired client relay authorization timed out."
        case .clientAuthorizationRejected:
            return "Paired client relay authorization was rejected."
        case .allocationCancelled:
            return "Remote route allocation was cancelled."
        case .allocationTimedOut:
            return "Remote route allocation timed out."
        }
    }
}

private final class RelayAllocationConnection: @unchecked Sendable {
    private enum State {
        case preparing
        case ready
        case failed(String)
        case cancelled
    }

    private let connection: NWConnection
    private let queue = DispatchQueue(label: "dev.aetherlink.relay-route-allocation.connection")
    private let condition = NSCondition()
    private let cancellation: RelayRouteAllocationCancellation
    private let deadline: Date
    private var cancellationHandlerID: UUID?
    private var state = State.preparing
    private var sendSequence: UInt64 = 0
    private var completedSendSequence: UInt64 = 0
    private var sendFailed = false
    private var receiveBuffer = Data()
    private var receiveInFlight = false
    private var receiveFailed = false
    private var receiveComplete = false

    init(
        host: String,
        port: UInt16,
        timeout: TimeInterval,
        cancellation: RelayRouteAllocationCancellation
    ) throws {
        guard timeout.isFinite, timeout > 0 else {
            throw RelayServiceRouteAllocationError.allocationTimedOut
        }
        self.cancellation = cancellation
        deadline = min(cancellation.deadline, Date().addingTimeInterval(timeout))
        connection = NWConnection(
            host: NWEndpoint.Host(host),
            port: NWEndpoint.Port(rawValue: port)!,
            using: .tcp
        )
        connection.stateUpdateHandler = { [weak self] nextState in
            self?.handleStateUpdate(nextState)
        }
        cancellationHandlerID = cancellation.addCancellationHandler { [weak self] in
            self?.cancel()
        }
        try cancellation.throwIfCancelledOrExpired()
        connection.start(queue: queue)
        try waitUntilReady()
    }

    deinit {
        cancellation.removeCancellationHandler(cancellationHandlerID)
        connection.stateUpdateHandler = nil
        connection.cancel()
    }

    func write(_ data: Data) throws {
        try cancellation.throwIfCancelledOrExpired()
        let sequence = condition.withLock { () -> UInt64 in
            sendSequence += 1
            sendFailed = false
            return sendSequence
        }
        connection.send(content: data, completion: .contentProcessed { [weak self] error in
            guard let self else { return }
            self.condition.withLock {
                self.sendFailed = error != nil
                self.completedSendSequence = max(self.completedSendSequence, sequence)
                self.condition.broadcast()
            }
        })

        try waitUntil {
            self.completedSendSequence >= sequence
        }
        if condition.withLock({ sendFailed }) {
            throw RelayServiceRouteAllocationError.writeFailed
        }
    }

    func readLine(maxBytes: Int = 4096) throws -> String {
        precondition(maxBytes > 0, "Relay control line limit must be positive")
        while true {
            try cancellation.throwIfCancelledOrExpired()
            if let line = try condition.withLock({ try takeLineIfAvailable(maxBytes: maxBytes) }) {
                return line
            }

            let shouldReceive = condition.withLock { () -> Bool in
                guard !receiveInFlight, !receiveFailed, !receiveComplete else { return false }
                receiveInFlight = true
                return true
            }
            if shouldReceive {
                connection.receive(minimumIncompleteLength: 1, maximumLength: maxBytes) { [weak self] data, _, isComplete, error in
                    guard let self else { return }
                    self.condition.withLock {
                        if let data {
                            self.receiveBuffer.append(data)
                        }
                        self.receiveFailed = error != nil
                        self.receiveComplete = isComplete
                        self.receiveInFlight = false
                        self.condition.broadcast()
                    }
                }
            }

            try waitUntil {
                self.receiveBuffer.contains(UInt8(ascii: "\n")) ||
                    self.receiveBuffer.count >= maxBytes ||
                    self.receiveFailed ||
                    self.receiveComplete ||
                    !self.receiveInFlight
            }
            let terminalFailure = condition.withLock {
                (receiveFailed || receiveComplete) && !receiveBuffer.contains(UInt8(ascii: "\n"))
            }
            if terminalFailure {
                throw RelayServiceRouteAllocationError.readFailed
            }
        }
    }

    private func takeLineIfAvailable(maxBytes: Int) throws -> String? {
        if let newlineIndex = receiveBuffer.firstIndex(of: UInt8(ascii: "\n")) {
            let lineLength = receiveBuffer.distance(from: receiveBuffer.startIndex, to: newlineIndex) + 1
            guard lineLength <= maxBytes else {
                throw RelayServiceRouteAllocationError.readFailed
            }
            let lineData = receiveBuffer.prefix(lineLength)
            receiveBuffer.removeFirst(lineLength)
            guard let line = String(data: lineData, encoding: .utf8) else {
                throw RelayServiceRouteAllocationError.readFailed
            }
            return line
        }
        if receiveBuffer.count >= maxBytes {
            throw RelayServiceRouteAllocationError.readFailed
        }
        return nil
    }

    private func waitUntilReady() throws {
        try waitUntil {
            switch self.state {
            case .preparing:
                return false
            case .ready, .failed, .cancelled:
                return true
            }
        }
        switch condition.withLock({ state }) {
        case .ready:
            return
        case .failed(let message):
            throw RelayServiceRouteAllocationError.connectFailed(message)
        case .preparing:
            throw RelayServiceRouteAllocationError.allocationTimedOut
        case .cancelled:
            throw cancellation.isCancelled
                ? RelayServiceRouteAllocationError.allocationCancelled
                : RelayServiceRouteAllocationError.connectFailed("Connection cancelled.")
        }
    }

    private func waitUntil(_ predicate: () -> Bool) throws {
        condition.lock()
        while !predicate() {
            if cancellation.isCancelled {
                condition.unlock()
                connection.cancel()
                throw RelayServiceRouteAllocationError.allocationCancelled
            }
            if Date() >= deadline || cancellation.isExpired {
                condition.unlock()
                connection.cancel()
                throw RelayServiceRouteAllocationError.allocationTimedOut
            }
            _ = condition.wait(until: deadline)
        }
        condition.unlock()
        try cancellation.throwIfCancelledOrExpired()
    }

    private func cancel() {
        connection.cancel()
        condition.withLock {
            state = .cancelled
            condition.broadcast()
        }
    }

    private func handleStateUpdate(_ nextState: NWConnection.State) {
        condition.withLock {
            switch nextState {
            case .ready:
                state = .ready
            case .failed(let error):
                state = .failed(error.localizedDescription)
            case .cancelled:
                state = .cancelled
            case .setup, .waiting, .preparing:
                break
            @unknown default:
                state = .failed("Unknown connection state.")
            }
            condition.broadcast()
        }
    }
}

private struct PairedRelayRenewalSnapshot: Sendable {
    let requestID: String
    let authorizationID: String
    let currentRelayID: String
    let nextRelayID: String
    let routeTokenHash: String
    let runtimeKeyFingerprint: String
    let clientKeyFingerprint: String
    let currentTicketGeneration: Int64
    let currentRelayExpiresAtEpochMillis: Int64
    let currentRelayNonce: String
    let transportBinding: String
}

private func currentEpochMillis(_ date: Date = Date()) -> Int64 {
    Int64((date.timeIntervalSince1970 * 1_000).rounded())
}

private func awaitPairedClientAuthorization(
    timeout: TimeInterval,
    provider: @escaping RuntimePairedRelayAuthorizationProvider,
    challenge: PairedRelayAllocationAuthorizationChallenge
) async throws -> PairedRelayAllocationClientProof {
    guard timeout.isFinite, timeout > 0 else {
        throw RelayServiceRouteAllocationError.clientAuthorizationTimedOut
    }
    let gate = PairedClientAuthorizationGate()
    return try await withTaskCancellationHandler {
        try await withCheckedThrowingContinuation { continuation in
            gate.install(continuation)
            let providerTask = Task.detached {
                do {
                    gate.resolve(.success(try await provider(challenge)))
                } catch {
                    gate.resolve(.failure(error))
                }
            }
            let timeoutNanoseconds = UInt64(
                min(timeout * 1_000_000_000, Double(UInt64.max))
            )
            let timeoutTask = Task.detached {
                do {
                    try await Task.sleep(nanoseconds: timeoutNanoseconds)
                } catch {
                    return
                }
                gate.resolve(.failure(
                    RelayServiceRouteAllocationError.clientAuthorizationTimedOut
                ))
            }
            gate.register(providerTask: providerTask, timeoutTask: timeoutTask)
        }
    } onCancel: {
        gate.resolve(.failure(CancellationError()))
    }
}

private final class PairedClientAuthorizationGate: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<PairedRelayAllocationClientProof, any Error>?
    private var pendingResult: Result<PairedRelayAllocationClientProof, any Error>?
    private var providerTask: Task<Void, Never>?
    private var timeoutTask: Task<Void, Never>?

    func install(
        _ continuation: CheckedContinuation<PairedRelayAllocationClientProof, any Error>
    ) {
        let result = lock.withLock { () -> Result<PairedRelayAllocationClientProof, any Error>? in
            if let pendingResult {
                self.pendingResult = nil
                return pendingResult
            }
            self.continuation = continuation
            return nil
        }
        if let result {
            continuation.resume(with: result)
        }
    }

    func register(providerTask: Task<Void, Never>, timeoutTask: Task<Void, Never>) {
        let shouldCancel = lock.withLock { () -> Bool in
            guard continuation != nil else { return true }
            self.providerTask = providerTask
            self.timeoutTask = timeoutTask
            return false
        }
        if shouldCancel {
            providerTask.cancel()
            timeoutTask.cancel()
        }
    }

    func resolve(_ result: Result<PairedRelayAllocationClientProof, any Error>) {
        let resolution = lock.withLock { () -> (
            CheckedContinuation<PairedRelayAllocationClientProof, any Error>?,
            Task<Void, Never>?,
            Task<Void, Never>?
        ) in
            guard pendingResult == nil else { return (nil, nil, nil) }
            guard let continuation else {
                pendingResult = result
                return (nil, nil, nil)
            }
            self.continuation = nil
            let providerTask = self.providerTask
            let timeoutTask = self.timeoutTask
            self.providerTask = nil
            self.timeoutTask = nil
            return (continuation, providerTask, timeoutTask)
        }
        guard let continuation = resolution.0 else { return }
        resolution.1?.cancel()
        resolution.2?.cancel()
        continuation.resume(with: result)
    }
}

struct RelayServiceAllocationResponse: Decodable, Equatable {
    let relayID: String
    let relayExpiresAtEpochMillis: Int64
    let relayNonce: String
    let runtimeKeyFingerprint: String
    let ticketGeneration: Int64
    let cryptoVersion: Int

    static func parse(_ line: String) throws -> RelayServiceAllocationResponse {
        let prefix = "AETHERLINK_RELAY allocation "
        let data = try exactControlLineJSON(
            line,
            prefix: prefix,
            allowedFieldNames: allowedFieldNames,
            error: .invalidResponse
        )
        do {
            let response = try JSONDecoder().decode(RelayServiceAllocationResponse.self, from: data)
            try response.validate()
            return response
        } catch let error as RelayServiceRouteAllocationError {
            throw error
        } catch {
            throw RelayServiceRouteAllocationError.invalidResponse
        }
    }

    private enum CodingKeys: String, CodingKey, CaseIterable {
        case relayID = "relay_id"
        case relayExpiresAtEpochMillis = "relay_expires_at"
        case relayNonce = "relay_nonce"
        case runtimeKeyFingerprint = "runtime_key_fingerprint"
        case ticketGeneration = "ticket_generation"
        case cryptoVersion = "crypto_version"
    }

    private static let allowedFieldNames = Set(CodingKeys.allCases.map(\.stringValue))

    private func validate() throws {
        try validateRelayToken(relayID)
        guard relayExpiresAtEpochMillis > 0,
              !relayNonce.isEmpty,
              relayNonce.rangeOfCharacter(from: .whitespacesAndNewlines) == nil,
              RelayRuntimeIdentity.isCanonicalFingerprint(runtimeKeyFingerprint),
              ticketGeneration > 0,
              cryptoVersion == 2
        else {
            throw RelayServiceRouteAllocationError.invalidResponse
        }
    }
}

private enum RelayServiceAllocationChallenge {
    static func parse(_ line: String) throws -> RelayAllocationIdentityChallenge {
        let data = try exactControlLineJSON(
            line,
            prefix: RelayAllocationIdentityChallenge.responsePrefix,
            allowedFieldNames: allowedFieldNames,
            error: .invalidChallenge
        )
        do {
            let decoded = try JSONDecoder().decode(RelayAllocationIdentityChallenge.self, from: data)
            return try RelayAllocationIdentityChallenge(
                operation: decoded.operation,
                relayID: decoded.relayID,
                routeTokenHash: decoded.routeTokenHash,
                runtimeKeyFingerprint: decoded.runtimeKeyFingerprint,
                ticketGeneration: decoded.ticketGeneration,
                challenge: decoded.challenge,
                challengeExpiresAtEpochMillis: decoded.challengeExpiresAtEpochMillis,
                cryptoVersion: decoded.cryptoVersion,
                allocationAuth: decoded.allocationAuth
            )
        } catch let error as RelayServiceRouteAllocationError {
            throw error
        } catch {
            throw RelayServiceRouteAllocationError.invalidChallenge
        }
    }

    private static let allowedFieldNames: Set<String> = [
        "operation",
        "relay_id",
        "route_token_hash",
        "runtime_key_fingerprint",
        "ticket_generation",
        "challenge",
        "challenge_expires_at",
        "crypto_version",
        "allocation_auth"
    ]
}

private func exactControlLineJSON(
    _ line: String,
    prefix: String,
    allowedFieldNames: Set<String>,
    error: RelayServiceRouteAllocationError
) throws -> Data {
    guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else { throw error }
    let body = String(line.dropLast())
    guard body.hasPrefix(prefix), !body.dropFirst(prefix.count).contains("\n") else { throw error }
    let data = Data(body.dropFirst(prefix.count).utf8)
    guard let object = try? JSONSerialization.jsonObject(with: data),
          let payload = object as? [String: Any],
          Set(payload.keys) == allowedFieldNames
    else {
        throw error
    }
    return data
}

private func validateRelayToken(_ value: String) throws {
    guard !value.isEmpty,
          value.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
    else {
        throw RelayServiceRouteAllocationError.invalidRouteToken
    }
}

private func validateAllocationToken(_ value: String) throws {
    guard !value.isEmpty,
          value.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
    else {
        throw RelayServiceRouteAllocationError.invalidAllocationToken
    }
}
