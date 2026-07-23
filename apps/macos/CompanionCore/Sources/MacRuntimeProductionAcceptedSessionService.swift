import Foundation
@_spi(AuthorityLifecycle) import P2PNATContracts
import Transport
@_spi(ProductionTransport) import TrustedDevices

private enum MacRuntimeProductionExpectedRouteDescriptorError: Error,
    Equatable,
    Sendable
{
    case invalidBinding
}

struct MacRuntimeProductionExpectedRouteDescriptor: Equatable, Sendable {
    let sessionID: String
    let object7And26BindingDigest: String
    let routeKind: String
    let pairBindingDigest: String
    let pairEpoch: UInt64
    let generation: UInt64
    let clientIdentityFingerprint: String
    let runtimeIdentityFingerprint: String
    let connectorInputCommitmentDigest: String
    let effectiveNotBeforeMs: UInt64
    let expiresAtMs: UInt64

    init(
        token: ProductionC1EndpointGrantCompoundCommitToken,
        verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding
    ) throws {
        let transcript = verifiedBinding.transcript
        let keyScheduleBinding = verifiedBinding.runtimeKeyScheduleBinding
        let authorization = keyScheduleBinding.grantAuthorization.authorization
        guard transcript.routeKind == .p2pDirect,
              keyScheduleBinding.transcript == transcript,
              keyScheduleBinding.securityContext == verifiedBinding.securityContext,
              transcript.sessionId == token.sessionID,
              transcript.routeAuthDigest == token.routeAuthorizationDigest,
              keyScheduleBinding.grantAuthorization.digestHex
                == token.grantAuthorizationDigest,
              verifiedBinding.connectorInput.commitmentDigest
                == token.connectorInputCommitmentDigest,
              authorization.sessionId == token.sessionID,
              authorization.pairBindingDigest == transcript.pairBindingDigest,
              authorization.pairEpoch == transcript.pairEpoch,
              authorization.generation == transcript.generation,
              authorization.clientIdentityFingerprint
                == transcript.clientIdentityFingerprint,
              authorization.runtimeIdentityFingerprint
                == transcript.runtimeIdentityFingerprint,
              authorization.effectiveNotBeforeMs == token.effectiveNotBeforeMs,
              authorization.expiresAtMs == token.expiresAtMs,
              token.effectiveNotBeforeMs < token.expiresAtMs else {
            throw MacRuntimeProductionExpectedRouteDescriptorError.invalidBinding
        }
        sessionID = transcript.sessionId
        object7And26BindingDigest = try ProductionSecureSessionCrypto
            .exactBindingDigestHex(keyScheduleBinding)
        routeKind = transcript.routeKind.wireName
        pairBindingDigest = transcript.pairBindingDigest
        pairEpoch = transcript.pairEpoch
        generation = transcript.generation
        clientIdentityFingerprint = transcript.clientIdentityFingerprint
        runtimeIdentityFingerprint = transcript.runtimeIdentityFingerprint
        connectorInputCommitmentDigest = token.connectorInputCommitmentDigest
        effectiveNotBeforeMs = token.effectiveNotBeforeMs
        expiresAtMs = token.expiresAtMs
    }

    #if DEBUG
    init(testing descriptor: RuntimeAcceptedRawRouteDescriptor) {
        sessionID = descriptor.sessionID
        object7And26BindingDigest = descriptor.object7And26BindingDigest
        routeKind = descriptor.routeKind
        pairBindingDigest = descriptor.pairBindingDigest
        pairEpoch = descriptor.pairEpoch
        generation = descriptor.generation
        clientIdentityFingerprint = descriptor.clientIdentityFingerprint
        runtimeIdentityFingerprint = descriptor.runtimeIdentityFingerprint
        connectorInputCommitmentDigest = descriptor.connectorInputCommitmentDigest
        effectiveNotBeforeMs = descriptor.effectiveNotBeforeMs
        expiresAtMs = descriptor.expiresAtMs
    }
    #endif

    func matches(_ descriptor: RuntimeAcceptedRawRouteDescriptor) -> Bool {
        descriptor.sessionID == sessionID
            && descriptor.object7And26BindingDigest
                == object7And26BindingDigest
            && descriptor.routeKind == routeKind
            && descriptor.pairBindingDigest == pairBindingDigest
            && descriptor.pairEpoch == pairEpoch
            && descriptor.generation == generation
            && descriptor.clientIdentityFingerprint
                == clientIdentityFingerprint
            && descriptor.runtimeIdentityFingerprint
                == runtimeIdentityFingerprint
            && descriptor.connectorInputCommitmentDigest
                == connectorInputCommitmentDigest
            && descriptor.effectiveNotBeforeMs == effectiveNotBeforeMs
            && descriptor.expiresAtMs == expiresAtMs
    }
}

/// Service-owned lifetime for the gap between claiming a raw endpoint and the
/// manager atomically reserving its attachment generation. The attempt stays
/// registered across authority creation and attachment, so stop can always
/// reach either this owner, the manager registry, or both during handoff.
private final class MacRuntimeProductionPreAttachmentAttempt:
    @unchecked Sendable
{
    let connectionID: UUID
    let generationID: UUID
    let serviceEpoch: UUID

    private let preparedSession: MacRuntimePreparedProductionRawSession
    private let localEphemeralKey: P2PNATSessionEphemeralKey?
    private let lock = NSLock()
    private var active = true

    init(
        connectionID: UUID,
        serviceEpoch: UUID,
        preparedSession: MacRuntimePreparedProductionRawSession,
        localEphemeralKey: P2PNATSessionEphemeralKey?
    ) {
        self.connectionID = connectionID
        generationID = UUID()
        self.serviceEpoch = serviceEpoch
        self.preparedSession = preparedSession
        self.localEphemeralKey = localEphemeralKey
    }

    var isActive: Bool {
        lock.lock()
        defer { lock.unlock() }
        return active
    }

    func invalidate() {
        lock.lock()
        active = false
        lock.unlock()

        // Both resources are independently one-shot. Repeating these calls is
        // intentional: if cancellation and stop race, whichever caller returns
        // has synchronously observed both cleanup operations complete.
        preparedSession.close()
        localEphemeralKey?.close()
    }
}

/// Production activation boundary for an already accepted raw transport.
///
/// This service does not open a listener or manufacture route authority. Its
/// caller must supply the verifier-minted exact binding and the matching
/// durable commit token. One exact `TrustedDeviceStore` instance is fixed for
/// the service lifetime so every accepted session shares its publication gate
/// and coordinator graph. The accepted endpoint first enters a service-owned
/// generation, then transfers to the manager-owned one-use attachment
/// registry. Every failure or stop closes whichever side currently owns it;
/// the flow never falls back to the envelope/plaintext transport path.
@MainActor
public final class MacRuntimeProductionAcceptedSessionService {
    private let connectionManager: MacRuntimeConnectionManager
    private let trustedDeviceStore: TrustedDeviceStore
    private var preAttachmentEpoch = UUID()
    private var preAttachmentAttempts:
        [UUID: MacRuntimeProductionPreAttachmentAttempt] = [:]

    public init(
        connectionManager: MacRuntimeConnectionManager,
        trustedDeviceStore: TrustedDeviceStore
    ) {
        self.connectionManager = connectionManager
        self.trustedDeviceStore = trustedDeviceStore
    }

    public func accept(
        _ acceptedSession: any RuntimeAcceptedRawSession,
        deviceID: String,
        expectedPublicKeyBase64: String,
        token: ProductionC1EndpointGrantCompoundCommitToken,
        verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        onMessage: @escaping LocalPeerMessageHandler
    ) async throws {
        // Caller ownership ends at service entry. Store handoff consumes or
        // closes the key; this outer defer covers descriptor/route failures
        // before that handoff and is intentionally safe to repeat.
        defer { localEphemeralKey.close() }
        let expectedDescriptor: MacRuntimeProductionExpectedRouteDescriptor
        do {
            expectedDescriptor = try MacRuntimeProductionExpectedRouteDescriptor(
                token: token,
                verifiedBinding: verifiedBinding
            )
        } catch {
            connectionManager.rejectAcceptedProductionRawSession(acceptedSession)
            throw error
        }

        let preparedSession = try connectionManager
            .prepareAcceptedProductionRawSession(
                acceptedSession,
                matchesExpectedDescriptor: expectedDescriptor.matches
            )
        let attempt = try registerPreAttachmentAttempt(
            connectionID: acceptedSession.connectionID,
            preparedSession: preparedSession,
            localEphemeralKey: localEphemeralKey
        )
        try await attach(
            attempt,
            preparedSession: preparedSession,
            localEphemeralKey: localEphemeralKey,
            beginAuthority: {
                let secureSession = try await self.trustedDeviceStore
                    .beginProductionC1TransportSecureSession(
                        deviceID: deviceID,
                        expectedPublicKeyBase64: expectedPublicKeyBase64,
                        token: token,
                        verifiedBinding: verifiedBinding,
                        localEphemeralKey: localEphemeralKey
                    )
                do {
                    return try MacRuntimeProductionChannelAuthorityCapability
                        .issue(exactBoundSession: secureSession)
                } catch {
                    await secureSession.close()
                    throw error
                }
            },
            composer: MacRuntimeProductionChannelComposer(),
            onMessage: onMessage
        )
    }

    /// Claims both pre-attachment and manager-registry ownership
    /// synchronously. Asynchronous secure-session abandon runs only after the
    /// manager lock is released, so a replacement generation may be admitted
    /// as soon as this method returns.
    public func stop(connectionID: UUID) {
        if let attempt = preAttachmentAttempts.removeValue(
            forKey: connectionID
        ) {
            attempt.invalidate()
        }
        connectionManager.stopAcceptedProductionRawSession(
            connectionID: connectionID
        )
    }

    /// Invalidates every service-owned pre-attachment generation before
    /// closing the manager registry. Rotating the epoch prevents a late return
    /// from an older stop-all generation from matching any fresh attempt.
    public func stopAll() {
        let attempts = Array(preAttachmentAttempts.values)
        preAttachmentAttempts.removeAll(keepingCapacity: false)
        preAttachmentEpoch = UUID()
        attempts.forEach { $0.invalidate() }
        connectionManager.stopAll()
    }

    #if DEBUG
    /// No-network seam for service-orchestration tests. Production callers
    /// cannot inject or manufacture an authority capability.
    func acceptForTesting(
        _ acceptedSession: any RuntimeAcceptedRawSession,
        expectedRouteDescriptor: RuntimeAcceptedRawRouteDescriptor? = nil,
        localEphemeralKey: P2PNATSessionEphemeralKey? = nil,
        beginAuthority: @escaping @Sendable () async throws
            -> MacRuntimeProductionChannelAuthorityCapability,
        composer: any MacRuntimeProductionChannelComposing =
            MacRuntimeProductionChannelComposer(),
        onMessage: @escaping LocalPeerMessageHandler
    ) async throws {
        defer { localEphemeralKey?.close() }
        let expectedRouteDescriptor = expectedRouteDescriptor
            ?? acceptedSession.routeDescriptor
        let expectedDescriptor = MacRuntimeProductionExpectedRouteDescriptor(
            testing: expectedRouteDescriptor
        )
        let preparedSession = try connectionManager
            .prepareAcceptedProductionRawSession(
                acceptedSession,
                matchesExpectedDescriptor: expectedDescriptor.matches
            )
        let attempt = try registerPreAttachmentAttempt(
            connectionID: acceptedSession.connectionID,
            preparedSession: preparedSession,
            localEphemeralKey: localEphemeralKey
        )
        try await attach(
            attempt,
            preparedSession: preparedSession,
            localEphemeralKey: localEphemeralKey,
            beginAuthority: beginAuthority,
            composer: composer,
            onMessage: onMessage
        )
    }
    #endif

    private func attach(
        _ attempt: MacRuntimeProductionPreAttachmentAttempt,
        preparedSession: MacRuntimePreparedProductionRawSession,
        localEphemeralKey: P2PNATSessionEphemeralKey?,
        beginAuthority: @escaping @Sendable () async throws
            -> MacRuntimeProductionChannelAuthorityCapability,
        composer: any MacRuntimeProductionChannelComposing,
        onMessage: @escaping LocalPeerMessageHandler
    ) async throws {
        defer { unregisterPreAttachmentAttempt(attempt) }
        defer { localEphemeralKey?.close() }
        let authorityCapability: MacRuntimeProductionChannelAuthorityCapability
        do {
            authorityCapability = try await withTaskCancellationHandler {
                try await beginAuthority()
            } onCancel: {
                attempt.invalidate()
                Task { @MainActor [weak self] in
                    self?.unregisterPreAttachmentAttempt(attempt)
                }
            }
        } catch {
            attempt.invalidate()
            throw error
        }

        do {
            try Task.checkCancellation()
        } catch {
            attempt.invalidate()
            await authorityCapability.invalidate()
            throw error
        }

        guard isCurrentPreAttachmentAttempt(attempt) else {
            attempt.invalidate()
            await authorityCapability.invalidate()
            throw MacRuntimeProductionChannelCompositionError
                .attachmentCancelled
        }

        // From reservation onward the manager owns exactly-once terminal
        // cleanup, including duplicate rejection. Do not issue a second close
        // or abandon from this layer.
        try await connectionManager.attachPreparedProductionRawSession(
            preparedSession,
            authorityCapability: authorityCapability,
            composer: composer,
            onMessage: onMessage
        )
    }

    private func registerPreAttachmentAttempt(
        connectionID: UUID,
        preparedSession: MacRuntimePreparedProductionRawSession,
        localEphemeralKey: P2PNATSessionEphemeralKey?
    ) throws -> MacRuntimeProductionPreAttachmentAttempt {
        if let existing = preAttachmentAttempts[connectionID] {
            if existing.isActive {
                preparedSession.close()
                localEphemeralKey?.close()
                throw MacRuntimeProductionChannelCompositionError
                    .duplicateAcceptedSession
            }
            preAttachmentAttempts.removeValue(forKey: connectionID)
        }

        let attempt = MacRuntimeProductionPreAttachmentAttempt(
            connectionID: connectionID,
            serviceEpoch: preAttachmentEpoch,
            preparedSession: preparedSession,
            localEphemeralKey: localEphemeralKey
        )
        preAttachmentAttempts[connectionID] = attempt
        return attempt
    }

    private func isCurrentPreAttachmentAttempt(
        _ attempt: MacRuntimeProductionPreAttachmentAttempt
    ) -> Bool {
        guard attempt.serviceEpoch == preAttachmentEpoch,
              let current = preAttachmentAttempts[attempt.connectionID],
              current === attempt,
              current.generationID == attempt.generationID else {
            return false
        }
        return attempt.isActive
    }

    private func unregisterPreAttachmentAttempt(
        _ attempt: MacRuntimeProductionPreAttachmentAttempt
    ) {
        guard let current = preAttachmentAttempts[attempt.connectionID],
              current === attempt,
              current.generationID == attempt.generationID else {
            return
        }
        preAttachmentAttempts.removeValue(forKey: attempt.connectionID)
    }
}
