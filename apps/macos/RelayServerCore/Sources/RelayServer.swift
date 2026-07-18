import Darwin
import BridgeProtocol
import Foundation

public enum RelayProbePolicy: String, Equatable, Sendable {
    case disabled
    case loopbackOnly = "loopback-only"
    case legacyUnauthenticated = "legacy-unauthenticated"

    func allowsProbe(host: String) -> Bool {
        switch self {
        case .disabled:
            return false
        case .loopbackOnly:
            return !RelayBindExposure.requiresAllocationToken(host: host)
        case .legacyUnauthenticated:
            return true
        }
    }
}

public struct RelayServerConfiguration: Equatable, Sendable {
    public static let defaultHost = "127.0.0.1"
    public static let defaultAllocationTTLSeconds: TimeInterval = 15 * 60
    public static let defaultControlLineReadTimeoutSeconds: TimeInterval = 10
    public static let defaultMaximumConcurrentConnections = 256

    public var host: String
    public var port: UInt16
    public var allocationTTLSeconds: TimeInterval
    public var requiresAllocation: Bool
    public var allocationStoreURL: URL?
    public var allocationToken: String?
    public var probePolicy: RelayProbePolicy
    public var controlLineReadTimeoutSeconds: TimeInterval
    public var maximumConcurrentConnections: Int
    public var sourceQuotaConfiguration: RelaySourceQuotaConfiguration
    public var waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration
    public var sourceRateLimitConfiguration: RelaySourceRateLimitConfiguration

    public init(
        host: String = Self.defaultHost,
        port: UInt16 = 43171,
        allocationTTLSeconds: TimeInterval = Self.defaultAllocationTTLSeconds,
        requiresAllocation: Bool = true,
        allocationStoreURL: URL? = nil,
        allocationToken: String? = nil,
        probePolicy: RelayProbePolicy = .loopbackOnly,
        controlLineReadTimeoutSeconds: TimeInterval = Self.defaultControlLineReadTimeoutSeconds,
        maximumConcurrentConnections: Int = Self.defaultMaximumConcurrentConnections,
        sourceQuotaConfiguration: RelaySourceQuotaConfiguration = .init(),
        waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration = .init(),
        sourceRateLimitConfiguration: RelaySourceRateLimitConfiguration = .init()
    ) {
        self.host = host
        self.port = port
        self.allocationTTLSeconds = allocationTTLSeconds
        self.requiresAllocation = requiresAllocation
        self.allocationStoreURL = allocationStoreURL
        self.allocationToken = allocationToken
        self.probePolicy = probePolicy
        self.controlLineReadTimeoutSeconds = controlLineReadTimeoutSeconds
        self.maximumConcurrentConnections = maximumConcurrentConnections
        self.sourceQuotaConfiguration = sourceQuotaConfiguration
        self.waitingPeerPolicyConfiguration = waitingPeerPolicyConfiguration
        self.sourceRateLimitConfiguration = sourceRateLimitConfiguration
    }

    public func validate() throws {
        try sourceQuotaConfiguration.validate()
        try waitingPeerPolicyConfiguration.validate()
        try sourceRateLimitConfiguration.validate()
        guard controlLineReadTimeoutSeconds.isFinite,
              controlLineReadTimeoutSeconds > 0,
              controlLineReadTimeoutSeconds <= 300
        else {
            throw RelayServerError.invalidControlLineReadTimeout
        }
        guard maximumConcurrentConnections > 0,
              maximumConcurrentConnections <= 65_536
        else {
            throw RelayServerError.invalidMaximumConcurrentConnections
        }
        if let allocationToken {
            guard !allocationToken.isEmpty,
                  allocationToken.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
            else {
                throw RelayServerError.invalidAllocationToken
            }
        }
        guard RelayBindExposure.requiresAllocationToken(host: host) else { return }
        guard requiresAllocation else {
            throw RelayServerError.legacyRelayRequiresLoopback(
                RelayBindExposure.normalizedHost(host)
            )
        }
        guard allocationToken != nil else {
            throw RelayServerError.allocationTokenRequiredForExposedBind(
                RelayBindExposure.normalizedHost(host)
            )
        }
        guard !requiresAllocation || allocationStoreURL != nil else {
            throw RelayServerError.durableAllocationStoreRequired(
                RelayBindExposure.normalizedHost(host)
            )
        }
    }
}

public enum RelayBindExposure: Sendable {
    public static func requiresAllocationToken(host: String) -> Bool {
        let normalized = normalizedHost(host)
        guard !normalized.isEmpty else { return true }
        if normalized == "localhost" || normalized == "localhost." {
            return false
        }
        if normalized == "::1" {
            return false
        }
        return !isIPv4Loopback(normalized)
    }

    public static func normalizedHost(_ host: String) -> String {
        var value = host.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if value.hasPrefix("[") && value.hasSuffix("]") {
            value.removeFirst()
            value.removeLast()
        }
        return value.isEmpty ? "<empty>" : value
    }

    private static func isIPv4Loopback(_ host: String) -> Bool {
        let pieces = host.split(separator: ".", omittingEmptySubsequences: false)
        guard pieces.count == 4 else { return false }
        let octets = pieces.compactMap { UInt8($0) }
        guard octets.count == 4 else { return false }
        return octets[0] == 127
    }
}

public final class RelayServer: @unchecked Sendable {
    private static let defaultIdentityChallengeTTL: TimeInterval = 30

    private let configuration: RelayServerConfiguration
    private let matcher: RelayMatcher
    private let allocationRegistry: RelayAllocationRegistry
    private let identityChallengeTTL: TimeInterval
    private let runState = RelayServerRunState()
    private let connectionLimiter: RelayConnectionLimiter
    private let socketRegistry = RelaySocketRegistry()
    private let sourceRateLimiter: RelaySourceRateLimiter
    private let sourceRateLimitLog: @Sendable (String) -> Void
    private let sourceQuotaLimiter: RelaySourceQuotaLimiter
    private let waitingPeerLimiter: RelayWaitingPeerLimiter

    public init(configuration: RelayServerConfiguration) {
        let sourceQuotaLimiter = RelaySourceQuotaLimiter(
            maximumConnections: configuration.maximumConcurrentConnections,
            configuration: configuration.sourceQuotaConfiguration,
            rejectionLog: { message in log(message) }
        )
        let waitingPeerLimiter = RelayWaitingPeerLimiter(
            configuration: configuration.waitingPeerPolicyConfiguration,
            rejectionLog: { message in log(message) }
        )
        self.configuration = configuration
        self.sourceQuotaLimiter = sourceQuotaLimiter
        self.waitingPeerLimiter = waitingPeerLimiter
        self.matcher = RelayMatcher(
            sourceQuotaLimiter: sourceQuotaLimiter,
            waitingPeerLimiter: waitingPeerLimiter,
            maximumWaitingDurationSeconds:
                configuration.waitingPeerPolicyConfiguration.maximumDurationSeconds
        )
        self.allocationRegistry = RelayAllocationRegistry(persistenceURL: configuration.allocationStoreURL)
        self.identityChallengeTTL = Self.defaultIdentityChallengeTTL
        self.connectionLimiter = RelayConnectionLimiter(sourceQuotaLimiter: sourceQuotaLimiter)
        self.sourceRateLimiter = RelaySourceRateLimiter(
            configuration: configuration.sourceRateLimitConfiguration
        )
        self.sourceRateLimitLog = { message in log(message) }
    }

    init(
        configuration: RelayServerConfiguration,
        identityChallengeTTL: TimeInterval
    ) {
        let sourceQuotaLimiter = RelaySourceQuotaLimiter(
            maximumConnections: configuration.maximumConcurrentConnections,
            configuration: configuration.sourceQuotaConfiguration,
            rejectionLog: { message in log(message) }
        )
        let waitingPeerLimiter = RelayWaitingPeerLimiter(
            configuration: configuration.waitingPeerPolicyConfiguration,
            rejectionLog: { message in log(message) }
        )
        self.configuration = configuration
        self.sourceQuotaLimiter = sourceQuotaLimiter
        self.waitingPeerLimiter = waitingPeerLimiter
        self.matcher = RelayMatcher(
            sourceQuotaLimiter: sourceQuotaLimiter,
            waitingPeerLimiter: waitingPeerLimiter,
            maximumWaitingDurationSeconds:
                configuration.waitingPeerPolicyConfiguration.maximumDurationSeconds
        )
        self.allocationRegistry = RelayAllocationRegistry(persistenceURL: configuration.allocationStoreURL)
        self.identityChallengeTTL = identityChallengeTTL
        self.connectionLimiter = RelayConnectionLimiter(sourceQuotaLimiter: sourceQuotaLimiter)
        self.sourceRateLimiter = RelaySourceRateLimiter(
            configuration: configuration.sourceRateLimitConfiguration
        )
        self.sourceRateLimitLog = { message in log(message) }
    }

    init(
        configuration: RelayServerConfiguration,
        identityChallengeTTL: TimeInterval,
        sourceRateLimitClock: @escaping @Sendable () -> TimeInterval,
        sourceRateLimitLog: @escaping @Sendable (String) -> Void,
        sourceQuotaLog: @escaping @Sendable (String) -> Void = { _ in },
        waitingPeerPolicyLog: @escaping @Sendable (String) -> Void = { _ in }
    ) {
        let sourceQuotaLimiter = RelaySourceQuotaLimiter(
            maximumConnections: configuration.maximumConcurrentConnections,
            configuration: configuration.sourceQuotaConfiguration,
            rejectionLog: sourceQuotaLog
        )
        let waitingPeerLimiter = RelayWaitingPeerLimiter(
            configuration: configuration.waitingPeerPolicyConfiguration,
            rejectionLog: waitingPeerPolicyLog
        )
        self.configuration = configuration
        self.sourceQuotaLimiter = sourceQuotaLimiter
        self.waitingPeerLimiter = waitingPeerLimiter
        self.matcher = RelayMatcher(
            sourceQuotaLimiter: sourceQuotaLimiter,
            waitingPeerLimiter: waitingPeerLimiter,
            maximumWaitingDurationSeconds:
                configuration.waitingPeerPolicyConfiguration.maximumDurationSeconds
        )
        self.allocationRegistry = RelayAllocationRegistry(persistenceURL: configuration.allocationStoreURL)
        self.identityChallengeTTL = identityChallengeTTL
        self.connectionLimiter = RelayConnectionLimiter(sourceQuotaLimiter: sourceQuotaLimiter)
        self.sourceRateLimiter = RelaySourceRateLimiter(
            configuration: configuration.sourceRateLimitConfiguration,
            monotonicNow: sourceRateLimitClock
        )
        self.sourceRateLimitLog = sourceRateLimitLog
    }

    public func sourceRateLimitMetricsSnapshot() -> RelaySourceRateLimitMetricsSnapshot {
        sourceRateLimiter.metricsSnapshot()
    }

    public func sourceQuotaMetricsSnapshot() -> RelaySourceQuotaMetricsSnapshot {
        sourceQuotaLimiter.metricsSnapshot()
    }

    public func waitingPeerPolicyMetricsSnapshot() -> RelayWaitingPeerPolicyMetricsSnapshot {
        waitingPeerLimiter.metricsSnapshot()
    }

    public func run() throws -> Never {
        let acquisition = try runState.acquire()
        do {
            try configuration.validate()
            if let allocationStoreURL = configuration.allocationStoreURL,
               !allocationRegistry.isPersistenceReady {
                throw RelayServerError.allocationStoreLockFailed(allocationStoreURL.path)
            }
            try runState.acquireAllocationStoreOwnershipIfNeeded(
                storeURL: configuration.allocationStoreURL,
                for: acquisition
            )
            let listenSocket = try makeListenSocket(
                host: configuration.host,
                port: configuration.port
            )
            log("AetherLink Swift development relay listening on \(configuration.host):\(configuration.port)")

            while true {
                var storage = sockaddr_storage()
                var length = socklen_t(MemoryLayout<sockaddr_storage>.size)
                let clientSocket = withUnsafeMutablePointer(to: &storage) { pointer in
                    pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                        Darwin.accept(listenSocket, sockaddrPointer, &length)
                    }
                }

                if clientSocket >= 0 {
                    let sourceIdentity = RelaySourceIdentity(storage: storage, length: length)
                    guard configureAcceptedSocket(clientSocket) else {
                        shutdown(clientSocket, SHUT_RDWR)
                        Darwin.close(clientSocket)
                        continue
                    }
                    if let connection = connectionLimiter.accept(
                        socket: clientSocket,
                        sourceIdentity: sourceIdentity
                    ) {
                        DispatchQueue.global(qos: .userInitiated).async { [self] in
                            handleClient(connection: connection)
                        }
                    } else {
                        shutdown(clientSocket, SHUT_RDWR)
                        Darwin.close(clientSocket)
                    }
                } else if errno != EINTR {
                    usleep(10_000)
                }
            }
        } catch {
            runState.release(acquisition)
            throw error
        }
    }

    private func handleClient(connection: RelayAcceptedConnection) {
        let socket = connection.socket
        do {
            let line = try readControlLine(socket: socket)
            if RelayPairedAllocationRenewalRequest.isRenewalLine(line) {
                guard !connection.requiresImmediateCounterpart else {
                    connection.close()
                    return
                }
                guard sourceRateLimitAllows(
                    .allocationMutation,
                    sourceIdentity: connection.sourceIdentity
                ) else {
                    connection.close()
                    return
                }
                try handlePairedAllocationRenewal(
                    line: line,
                    socket: socket
                )
                connection.close()
                return
            }
            if RelayAllocationRequest.isAllocationLine(line) {
                guard !connection.requiresImmediateCounterpart else {
                    connection.close()
                    return
                }
                guard sourceRateLimitAllows(
                    sourceRateLimitRequestKind(forAllocationLine: line),
                    sourceIdentity: connection.sourceIdentity
                ) else {
                    connection.close()
                    return
                }
                try handleAllocationRequest(
                    line: line,
                    socket: socket
                )
                connection.close()
                return
            }
            if RelayProbeRequest.isProbeLine(line) {
                guard !connection.requiresImmediateCounterpart else {
                    connection.close()
                    return
                }
                try handleProbeRequest(line: line, socket: socket)
                connection.close()
                return
            }
            let handshake = try RelayHandshake.parse(line)
            let allocationBinding = configuration.requiresAllocation
                ? allocationRegistry.binding(relayID: handshake.relayID)
                : nil
            guard !configuration.requiresAllocation || allocationBinding != nil else {
                log("rejected unallocated relay_id=\(shortID(handshake.relayID))")
                connection.close()
                return
            }
            guard handshake.usesCryptoV2 == configuration.requiresAllocation else {
                log("rejected incompatible relay crypto role=\(handshake.role.rawValue) relay_id=\(shortID(handshake.relayID))")
                connection.close()
                return
            }
            if handshake.role == .runtime, let allocationBinding {
                try authorizeRuntimeRegistration(
                    handshake: handshake,
                    binding: allocationBinding,
                    socket: socket
                )
            } else if handshake.role == .client,
                      let allocationBinding,
                      allocationBinding.authorizationMode == .pairedDeviceP256V1 {
                try authorizePairedClientRegistration(
                    handshake: handshake,
                    binding: allocationBinding,
                    socket: socket
                )
            }
            let authenticatedIdentity = RelayAuthenticatedPeerIdentity(
                role: handshake.role,
                fingerprint: handshake.role == .runtime
                    ? allocationBinding?.runtimeKeyFingerprint
                    : allocationBinding?.pairedClientKeyFingerprint
            )
            let registration: RelayPeerRegistration
            if let sessionNonce = handshake.sessionNonce,
               let ephemeralKey = handshake.ephemeralKey {
                registration = RelayPeerRegistration(
                    role: handshake.role,
                    relayID: handshake.relayID,
                    roomBinding: allocationBinding.map(RelayRoomBinding.init),
                    sessionNonce: sessionNonce,
                    ephemeralKey: ephemeralKey,
                    runtimeKeyFingerprint: handshake.runtimeKeyFingerprint,
                    authenticatedIdentity: authenticatedIdentity
                )
            } else {
                registration = RelayPeerRegistration(
                    role: handshake.role,
                    relayID: handshake.relayID,
                    roomBinding: allocationBinding.map(RelayRoomBinding.init)
                )
            }
            let peer = RelaySocketPeer(
                registration: registration,
                connection: connection
            )
            let maximumWaitingDeadlineUptime = allocationBinding.map { binding in
                let remainingLeaseSeconds = max(
                    0,
                    TimeInterval(
                        binding.relayExpiresAtEpochMillis - epochMillis(Date())
                    ) / 1_000
                )
                return ProcessInfo.processInfo.systemUptime + remainingLeaseSeconds
            }
            socketRegistry.store(peer)
            let registrationAttempt: RelayRegistrationAttempt
            do {
                if let allocationBinding {
                    registrationAttempt = try allocationRegistry.withRevalidatedBinding(allocationBinding) {
                        matcher.registerWithExpiredWaitingPeers(
                            peer.registration,
                            sourceIdentity: connection.sourceIdentity,
                            requiresImmediateMatch: connection.requiresImmediateCounterpart,
                            requiresSameSourceCounterpart:
                                connection.requiresSameSourceCounterpart,
                            maximumWaitingDeadlineUptime: maximumWaitingDeadlineUptime
                        )
                    }
                } else {
                    registrationAttempt = matcher.registerWithExpiredWaitingPeers(
                        peer.registration,
                        sourceIdentity: connection.sourceIdentity,
                        requiresImmediateMatch: connection.requiresImmediateCounterpart,
                        requiresSameSourceCounterpart: connection.requiresSameSourceCounterpart,
                        maximumWaitingDeadlineUptime: maximumWaitingDeadlineUptime
                    )
                }
            } catch {
                socketRegistry.close(peerID: peer.registration.id)
                throw error
            }
            for expiredPeer in registrationAttempt.expiredWaitingPeers {
                socketRegistry.close(peerID: expiredPeer.id)
            }
            switch registrationAttempt.result {
            case .waiting(let replaced):
                if let replaced {
                    connection.confirmCounterpartCandidateIfNeeded()
                    socketRegistry.close(peerID: replaced.id)
                }
                log("accepted role=\(handshake.role.rawValue) relay_id=\(shortID(handshake.relayID))")
                let registeredLine = handshake.usesCryptoV2
                    ? RelayHandshake.cryptoV2RegisteredLine
                    : RelayHandshake.registeredLine
                if handshake.role == .runtime,
                   !writeAll(socket: socket, data: registeredLine) {
                    _ = matcher.unregisterWaiting(peerID: peer.registration.id)
                    socketRegistry.close(peerID: peer.registration.id)
                    return
                }
                let peerID = peer.registration.id
                guard let waitingDeadlineUptime = registrationAttempt.waitingDeadlineUptime else {
                    socketRegistry.close(peerID: peerID)
                    return
                }
                connection.beginWaitingMonitor(
                    timeoutSeconds: max(
                        0,
                        waitingDeadlineUptime - ProcessInfo.processInfo.systemUptime
                    )
                ) { [weak self] timedOut in
                    guard let self else { return }
                    let removedWaitingPeer = self.matcher.unregisterWaiting(peerID: peerID) != nil
                    if timedOut && removedWaitingPeer {
                        self.waitingPeerLimiter.recordWaitingPeerTimeout()
                    }
                    self.socketRegistry.close(peerID: peerID)
                }
                log("waiting relay_id=\(shortID(handshake.relayID)) role=\(handshake.role.rawValue)")
            case .matched(let runtime, let client, let matchToken):
                connection.confirmCounterpartCandidateIfNeeded()
                log("accepted role=\(handshake.role.rawValue) relay_id=\(shortID(handshake.relayID))")
                let runtimePeer = socketRegistry.remove(peerID: runtime.id)
                let clientPeer = socketRegistry.remove(peerID: client.id)
                guard let runtimePeer,
                      let clientPeer,
                      runtimePeer.connection.activate(),
                      clientPeer.connection.activate() else {
                    _ = matcher.release(matchToken: matchToken)
                    runtimePeer?.connection.close()
                    clientPeer?.connection.close()
                    socketRegistry.close(peerID: peer.registration.id)
                    return
                }
                bridge(
                    runtime: runtimePeer,
                    client: clientPeer,
                    matchToken: matchToken
                )
            case .rejected(let reason):
                if reason != .sourceWaitingPeerQuota,
                   reason != .authenticatedIdentityWaitingQuota,
                   reason != .counterpartRequired,
                   !connection.requiresImmediateCounterpart {
                    log(
                        "rejected room registration role=\(handshake.role.rawValue) " +
                            "relay_id=\(shortID(handshake.relayID)) reason=\(reason)"
                    )
                }
                _ = socketRegistry.remove(peerID: peer.registration.id)
                connection.close()
            }
        } catch {
            connection.close()
        }
    }

    private func handleProbeRequest(line: String, socket: Int32) throws {
        let request = try RelayProbeRequest.parse(line)
        guard configuration.probePolicy.allowsProbe(host: configuration.host) else {
            return
        }
        let known = isRelayIDAllowed(request.relayID)
        let waitingStatus = matcher.waitingRuntimeStatus(relayID: request.relayID)
        for expiredPeer in waitingStatus.expiredWaitingPeers {
            socketRegistry.close(peerID: expiredPeer.id)
        }
        let runtimeWaiting = known && waitingStatus.hasWaitingRuntime
        let response = RelayProbeResponse(known: known, runtimeWaiting: runtimeWaiting)
        guard writeAll(socket: socket, data: response.responseLine()) else {
            throw RelayServerError.probeWriteFailed
        }
    }

    private func handleAllocationRequest(
        line: String,
        socket: Int32
    ) throws {
        let request = try configuration.requiresAllocation
            ? RelayAllocationRequest.parseStrictCryptoV2(line)
            : RelayAllocationRequest.parse(line)
        guard isAllocationAuthorized(request) else {
            log("rejected allocation request")
            throw RelayAllocationError.unauthorizedAllocation
        }
        if request.isPreflight && configuration.requiresAllocation {
            guard writeAll(socket: socket, data: try RelayAllocationPreflightResponse().responseLine()) else {
                throw RelayServerError.allocationWriteFailed
            }
            log("preflight allocation contract accepted")
            return
        }
        if request.usesEndpointOwnedSecret {
            guard let runtimeIdentity = request.runtimeIdentity else {
                throw RelayAllocationError.invalidRuntimeIdentity
            }
            let relayID = RelayAllocationIdentityChallenge.relayID(
                routeToken: request.routeToken,
                runtimeKeyFingerprint: runtimeIdentity.fingerprint
            )
            let proposal = try allocationRegistry.proposedGeneration(
                relayID: relayID,
                runtimeIdentity: runtimeIdentity
            )
            let challenge = try RelayAllocationIdentityChallenge(
                operation: proposal.operation,
                relayID: relayID,
                routeTokenHash: RelayAllocationIdentityChallenge.routeTokenHash(request.routeToken),
                runtimeKeyFingerprint: runtimeIdentity.fingerprint,
                ticketGeneration: proposal.generation,
                challenge: secureRandomHex(byteCount: 32),
                challengeExpiresAtEpochMillis: epochMillis(
                    Date().addingTimeInterval(identityChallengeTTL)
                )
            )
            guard writeAll(
                socket: socket,
                data: try RelayAllocationChallengeResponse(challenge: challenge).responseLine()
            ) else {
                throw RelayServerError.allocationWriteFailed
            }
            let proof = try RelayAllocationProofRequest.parse(
                readControlLine(socket: socket),
                runtimeIdentity: runtimeIdentity
            )
            guard challenge.challengeExpiresAtEpochMillis > epochMillis(Date()),
                  proof.challenge == challenge.challenge,
                  challenge.relayID == relayID,
                  challenge.routeTokenHash == RelayAllocationIdentityChallenge.routeTokenHash(request.routeToken),
                  challenge.runtimeKeyFingerprint == runtimeIdentity.fingerprint,
                  relayID == RelayAllocationIdentityChallenge.relayID(
                    routeToken: request.routeToken,
                    runtimeKeyFingerprint: runtimeIdentity.fingerprint
                  ),
                  RelayIdentityAuthorization.verify(
                    signatureBase64: proof.signatureBase64,
                    messageData: challenge.signedMessageData(),
                    runtimeIdentity: runtimeIdentity
                  )
            else {
                throw RelayAllocationError.unauthorizedAllocation
            }
            let allocation = try RelayAllocationV2.make(
                routeToken: request.routeToken,
                runtimeIdentity: runtimeIdentity,
                ticketGeneration: proposal.generation,
                validFor: configuration.allocationTTLSeconds
            )
            let binding = try RelayAllocationBinding(
                relayID: allocation.relayID,
                relayExpiresAtEpochMillis: allocation.relayExpiresAtEpochMillis,
                relayNonce: allocation.relayNonce,
                runtimeIdentity: runtimeIdentity,
                ticketGeneration: allocation.ticketGeneration
            )
            try allocationRegistry.commit(
                binding,
                replacingGeneration: proposal.operation == .create ? nil : proposal.generation - 1
            )
            closeInvalidatedWaitingPeers(relayID: binding.relayID, keeping: binding)
            guard writeAll(socket: socket, data: try allocation.responseLine()) else {
                throw RelayServerError.allocationWriteFailed
            }
            logAllocationResult(relayID: allocation.relayID, isPreflight: false)
            return
        }
        guard !configuration.requiresAllocation else {
            throw RelayAllocationError.invalidFormat
        }
        let allocation = try RelayAllocation.make(
            routeToken: request.routeToken,
            requestedRelaySecret: request.requestedRelaySecret,
            validFor: configuration.allocationTTLSeconds
        )
        guard writeAll(socket: socket, data: try allocation.responseLine()) else {
            throw RelayServerError.allocationWriteFailed
        }
        logAllocationResult(relayID: allocation.relayID, isPreflight: request.isPreflight)
    }

    private func handlePairedAllocationRenewal(
        line: String,
        socket: Int32
    ) throws {
        guard configuration.requiresAllocation else {
            throw RelayAllocationError.invalidFormat
        }
        let request = try RelayPairedAllocationRenewalRequest.parse(line)
        guard isAllocationAuthorized(allocationToken: request.allocationToken) else {
            log("rejected paired allocation renewal request")
            throw RelayAllocationError.unauthorizedAllocation
        }
        let runtimeIdentity = try request.runtimeIdentity
        let bootstrapRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: request.routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: request.routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: request.clientKeyFingerprint
        )
        let proposal = try allocationRegistry.pairedRenewalProposal(
            bootstrapRelayID: bootstrapRelayID,
            pairedRelayID: pairedRelayID,
            runtimeIdentity: runtimeIdentity,
            clientKeyFingerprint: request.clientKeyFingerprint
        )
        let current = proposal.currentBinding
        guard current.relayExpiresAtEpochMillis < Int64.max else {
            throw RelayAllocationError.invalidExpiration
        }

        let now = Date()
        let nowEpochMillis = epochMillis(now)
        let configuredExpiration = epochMillis(
            now.addingTimeInterval(configuration.allocationTTLSeconds)
        )
        let nextExpiration = max(
            configuredExpiration,
            current.relayExpiresAtEpochMillis + 1
        )
        guard nextExpiration > nowEpochMillis else {
            throw RelayAllocationError.invalidExpiration
        }
        let nextAllocation = try RelayAllocationV2(
            relayID: proposal.nextRelayID,
            relayExpiresAtEpochMillis: nextExpiration,
            relayNonce: "nonce-\(UUID().uuidString)",
            runtimeKeyFingerprint: current.runtimeKeyFingerprint,
            ticketGeneration: current.ticketGeneration + 1
        )
        let challenge = try PairedRelayAllocationAuthorizationChallenge(
            operation: proposal.operation,
            requestID: request.requestID,
            authorizationID: request.authorizationID,
            currentRelayID: current.relayID,
            nextRelayID: nextAllocation.relayID,
            routeTokenHash: PairedRelayAllocationAuthorization.routeTokenHash(
                request.routeToken
            ),
            runtimeKeyFingerprint: current.runtimeKeyFingerprint,
            clientKeyFingerprint: request.clientKeyFingerprint,
            currentTicketGeneration: current.ticketGeneration,
            nextTicketGeneration: nextAllocation.ticketGeneration,
            currentRelayExpiresAtEpochMillis: current.relayExpiresAtEpochMillis,
            currentRelayNonce: current.relayNonce,
            nextRelayExpiresAtEpochMillis: nextAllocation.relayExpiresAtEpochMillis,
            nextRelayNonce: nextAllocation.relayNonce,
            challenge: secureRandomHex(byteCount: 32),
            challengeExpiresAtEpochMillis: epochMillis(
                now.addingTimeInterval(identityChallengeTTL)
            ),
            transportBinding: request.transportBinding
        )
        guard writeAll(
            socket: socket,
            data: try RelayPairedAllocationChallengeResponse(
                challenge: challenge
            ).responseLine()
        ) else {
            throw RelayServerError.allocationWriteFailed
        }

        let proof = try RelayPairedAllocationProofRequest.parse(
            readControlLine(socket: socket),
            renewalRequest: request
        )
        let proofNowEpochMillis = epochMillis(Date())
        guard proof.challenge == challenge.challenge,
              challenge.challengeExpiresAtEpochMillis > proofNowEpochMillis,
              challenge.nextRelayExpiresAtEpochMillis > proofNowEpochMillis,
              challenge.operation == proposal.operation,
              challenge.requestID == request.requestID,
              challenge.authorizationID == request.authorizationID,
              challenge.currentRelayID == current.relayID,
              challenge.nextRelayID == nextAllocation.relayID,
              challenge.nextRelayID == pairedRelayID,
              challenge.routeTokenHash == PairedRelayAllocationAuthorization.routeTokenHash(
                request.routeToken
              ),
              challenge.runtimeKeyFingerprint == request.runtimeKeyFingerprint,
              challenge.clientKeyFingerprint == request.clientKeyFingerprint,
              challenge.runtimeKeyFingerprint != challenge.clientKeyFingerprint,
              challenge.currentTicketGeneration == current.ticketGeneration,
              challenge.nextTicketGeneration == nextAllocation.ticketGeneration,
              challenge.currentRelayExpiresAtEpochMillis == current.relayExpiresAtEpochMillis,
              challenge.currentRelayNonce == current.relayNonce,
              challenge.nextRelayExpiresAtEpochMillis == nextAllocation.relayExpiresAtEpochMillis,
              challenge.nextRelayNonce == nextAllocation.relayNonce,
              challenge.transportBinding == request.transportBinding,
              (try? PairedRelayAllocationAuthorization.validatedRuntimePublicKey(
                base64: request.runtimePublicKey,
                fingerprint: request.runtimeKeyFingerprint
              )) != nil,
              (try? PairedRelayAllocationAuthorization.validatedClientPublicKey(
                base64: request.clientPublicKey,
                fingerprint: request.clientKeyFingerprint
              )) != nil,
              proof.runtimeProof.verify(challenge: challenge),
              proof.clientProof.verify(challenge: challenge)
        else {
            throw RelayAllocationError.unauthorizedAllocation
        }

        let nextBinding = try RelayAllocationBinding(
            relayID: nextAllocation.relayID,
            relayExpiresAtEpochMillis: nextAllocation.relayExpiresAtEpochMillis,
            relayNonce: nextAllocation.relayNonce,
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: nextAllocation.ticketGeneration,
            authorizationMode: .pairedDeviceP256V1,
            pairedClientKeyFingerprint: request.clientKeyFingerprint
        )
        try allocationRegistry.commitPairedRenewal(
            nextBinding,
            replacing: current,
            operation: proposal.operation
        )
        if current.relayID != nextBinding.relayID {
            closeAllWaitingPeers(relayID: current.relayID)
        }
        closeInvalidatedWaitingPeers(relayID: nextBinding.relayID, keeping: nextBinding)
        guard writeAll(socket: socket, data: try nextAllocation.responseLine()) else {
            throw RelayServerError.allocationWriteFailed
        }
        log("\(proposal.operation.rawValue)ed paired relay_id=\(shortID(nextAllocation.relayID))")
    }

    private func sourceRateLimitAllows(
        _ requestKind: RelaySourceRateLimiter.RequestKind,
        sourceIdentity: RelaySourceIdentity
    ) -> Bool {
        let decision = sourceRateLimiter.evaluate(
            source: sourceIdentity,
            kind: requestKind
        )
        guard !decision.allowed, let reason = decision.rejectionReason else {
            return true
        }
        sourceRateLimitLog("reason=\(reason.rawValue) reason_count=\(decision.reasonCount)")
        return false
    }

    private func sourceRateLimitRequestKind(
        forAllocationLine line: String
    ) -> RelaySourceRateLimiter.RequestKind {
        guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else {
            return .allocationMutation
        }
        let body = line.dropLast()
        guard !body.contains("\n"), !body.contains("\r") else {
            return .allocationMutation
        }
        guard body.allSatisfy({ !$0.isWhitespace || $0 == " " }) else {
            return .allocationMutation
        }
        let parts = body.split(separator: " ", omittingEmptySubsequences: false)
        guard (5...6).contains(parts.count),
              parts.allSatisfy({ !$0.isEmpty }),
              parts[0] == Substring(RelayHandshake.prefix),
              parts[1] == Substring(RelayAllocationRequest.action),
              parts[3] == "crypto=2"
        else {
            return .allocationMutation
        }
        if parts.count == 5 {
            return parts[4] == "preflight=1" ? .preflight : .allocationMutation
        }
        let allocationTokenPrefix = "allocation_token="
        return parts[4].hasPrefix(allocationTokenPrefix) &&
            parts[4].count > allocationTokenPrefix.count &&
            parts[5] == "preflight=1"
            ? .preflight
            : .allocationMutation
    }

    private func logAllocationResult(relayID: String, isPreflight: Bool) {
        if isPreflight {
            log("preflight allocation relay_id=\(shortID(relayID))")
        } else {
            log("allocated relay_id=\(shortID(relayID))")
        }
    }

    private func isAllocationAuthorized(_ request: RelayAllocationRequest) -> Bool {
        isAllocationAuthorized(allocationToken: request.allocationToken)
    }

    private func isAllocationAuthorized(allocationToken: String?) -> Bool {
        guard let expectedToken = configuration.allocationToken, !expectedToken.isEmpty else {
            return true
        }
        return allocationToken == expectedToken
    }

    private func isRelayIDAllowed(_ relayID: String) -> Bool {
        guard configuration.requiresAllocation else { return true }
        return allocationRegistry.isValid(relayID: relayID)
    }

    private func closeInvalidatedWaitingPeers(
        relayID: String,
        keeping binding: RelayAllocationBinding
    ) {
        let invalidated = matcher.invalidateWaiting(
            relayID: relayID,
            keeping: RelayRoomBinding(allocationBinding: binding)
        )
        for registration in invalidated {
            socketRegistry.close(peerID: registration.id)
        }
    }

    private func closeAllWaitingPeers(relayID: String) {
        let invalidated = matcher.invalidateWaiting(relayID: relayID, keeping: nil)
        for registration in invalidated {
            socketRegistry.close(peerID: registration.id)
        }
    }

    private func authorizeRuntimeRegistration(
        handshake: RelayHandshake,
        binding: RelayAllocationBinding,
        socket: Int32
    ) throws {
        guard handshake.runtimeKeyFingerprint == binding.runtimeKeyFingerprint,
              let sessionNonce = handshake.sessionNonce,
              let ephemeralKey = handshake.ephemeralKey
        else {
            throw RelayAllocationError.invalidRuntimeIdentity
        }
        let runtimeIdentity = try binding.runtimeIdentity
        let challenge = try RelayRuntimeRegistrationIdentityChallenge(
            relayID: binding.relayID,
            relayExpiresAtEpochMillis: binding.relayExpiresAtEpochMillis,
            relayNonce: binding.relayNonce,
            runtimeKeyFingerprint: binding.runtimeKeyFingerprint,
            ticketGeneration: binding.ticketGeneration,
            sessionNonce: sessionNonce,
            ephemeralKey: ephemeralKey,
            challenge: secureRandomHex(byteCount: 32),
            challengeExpiresAtEpochMillis: epochMillis(
                Date().addingTimeInterval(identityChallengeTTL)
            )
        )
        guard writeAll(
            socket: socket,
            data: try RelayRuntimeRegistrationChallengeResponse(challenge: challenge).responseLine()
        ) else {
            throw RelayServerError.registrationChallengeWriteFailed
        }
        let proof = try RelayRuntimeRegistrationProofRequest.parse(
            readControlLine(socket: socket),
            runtimeIdentity: runtimeIdentity
        )
        guard challenge.challengeExpiresAtEpochMillis > epochMillis(Date()),
              proof.challenge == challenge.challenge,
              challenge.relayID == binding.relayID,
              challenge.relayExpiresAtEpochMillis == binding.relayExpiresAtEpochMillis,
              challenge.relayNonce == binding.relayNonce,
              challenge.runtimeKeyFingerprint == binding.runtimeKeyFingerprint,
              challenge.ticketGeneration == binding.ticketGeneration,
              challenge.sessionNonce == sessionNonce,
              challenge.ephemeralKey == ephemeralKey,
              RelayIdentityAuthorization.verify(
                signatureBase64: proof.signatureBase64,
                messageData: challenge.signedMessageData(),
                runtimeIdentity: runtimeIdentity
              )
        else {
            throw RelayAllocationError.unauthorizedAllocation
        }
    }

    private func authorizePairedClientRegistration(
        handshake: RelayHandshake,
        binding: RelayAllocationBinding,
        socket: Int32
    ) throws {
        guard handshake.role == .client,
              handshake.relayID == binding.relayID,
              handshake.runtimeKeyFingerprint == nil,
              let sessionNonce = handshake.sessionNonce,
              let ephemeralKey = handshake.ephemeralKey,
              binding.authorizationMode == .pairedDeviceP256V1,
              let clientKeyFingerprint = binding.pairedClientKeyFingerprint
        else {
            throw RelayAllocationError.unauthorizedAllocation
        }
        let challenge = try PairedClientRelayRegistrationChallenge(
            relayID: binding.relayID,
            relayExpiresAtEpochMillis: binding.relayExpiresAtEpochMillis,
            relayNonce: binding.relayNonce,
            runtimeKeyFingerprint: binding.runtimeKeyFingerprint,
            clientKeyFingerprint: clientKeyFingerprint,
            ticketGeneration: binding.ticketGeneration,
            sessionNonce: sessionNonce,
            ephemeralKey: ephemeralKey,
            challenge: secureRandomHex(byteCount: 32),
            challengeExpiresAtEpochMillis: epochMillis(
                Date().addingTimeInterval(identityChallengeTTL)
            )
        )
        guard writeAll(
            socket: socket,
            data: try RelayPairedClientRegistrationChallengeResponse(
                challenge: challenge
            ).responseLine()
        ) else {
            throw RelayServerError.registrationChallengeWriteFailed
        }
        let request = try RelayPairedClientRegistrationProofRequest.parse(
            readControlLine(socket: socket)
        )
        let nowEpochMillis = epochMillis(Date())
        guard request.challenge == challenge.challenge,
              challenge.isFresh(atEpochMillis: nowEpochMillis),
              challenge.relayID == binding.relayID,
              challenge.relayExpiresAtEpochMillis == binding.relayExpiresAtEpochMillis,
              challenge.relayNonce == binding.relayNonce,
              challenge.runtimeKeyFingerprint == binding.runtimeKeyFingerprint,
              challenge.clientKeyFingerprint == clientKeyFingerprint,
              challenge.ticketGeneration == binding.ticketGeneration,
              challenge.sessionNonce == sessionNonce,
              challenge.ephemeralKey == ephemeralKey,
              request.proof.verify(challenge: challenge)
        else {
            throw RelayAllocationError.unauthorizedAllocation
        }
    }

    private func readControlLine(socket: Int32) throws -> String {
        try RelayServerControlLineReader.read(
            socket: socket,
            timeoutSeconds: configuration.controlLineReadTimeoutSeconds
        )
    }

    private func bridge(
        runtime: RelaySocketPeer,
        client: RelaySocketPeer,
        matchToken: RelayMatchToken
    ) {
        let termination = RelayActiveBridgeTermination(
            runtime: runtime.connection,
            client: client.connection,
            matcher: matcher,
            matchToken: matchToken
        )
        defer { termination.finish() }
        log("matched relay_id=\(shortID(runtime.registration.relayID)) runtime<->client")
        let readyLines: (runtime: Data, client: Data)
        switch (
            runtime.registration.sessionNonce,
            runtime.registration.ephemeralKey,
            client.registration.sessionNonce,
            client.registration.ephemeralKey
        ) {
        case let (runtimeNonce?, runtimeKey?, clientNonce?, clientKey?) where configuration.requiresAllocation:
            readyLines = (
                runtime: RelayHandshake.cryptoV2ReadyLine(
                    peerSessionNonce: clientNonce,
                    peerEphemeralKey: clientKey
                ),
                client: RelayHandshake.cryptoV2ReadyLine(
                    peerSessionNonce: runtimeNonce,
                    peerEphemeralKey: runtimeKey
                )
            )
        case (nil, nil, nil, nil) where !configuration.requiresAllocation:
            readyLines = (runtime: RelayHandshake.readyLine, client: RelayHandshake.readyLine)
        default:
            return
        }

        guard writeAll(socket: runtime.connection.socket, data: readyLines.runtime),
              writeAll(socket: client.connection.socket, data: readyLines.client)
        else {
            return
        }

        let group = DispatchGroup()
        group.enter()
        DispatchQueue.global(qos: .userInitiated).async {
            defer {
                termination.shutdownBoth()
                group.leave()
            }
            forwardBytes(from: runtime.connection.socket, to: client.connection.socket)
        }
        group.enter()
        DispatchQueue.global(qos: .userInitiated).async {
            defer {
                termination.shutdownBoth()
                group.leave()
            }
            forwardBytes(from: client.connection.socket, to: runtime.connection.socket)
        }
        group.wait()
    }
}

private struct RelaySocketPeer: Sendable {
    let registration: RelayPeerRegistration
    let connection: RelayAcceptedConnection
}

private final class RelayConnectionLimiter: @unchecked Sendable {
    private let sourceQuotaLimiter: RelaySourceQuotaLimiter

    init(sourceQuotaLimiter: RelaySourceQuotaLimiter) {
        self.sourceQuotaLimiter = sourceQuotaLimiter
    }

    func accept(
        socket: Int32,
        sourceIdentity: RelaySourceIdentity
    ) -> RelayAcceptedConnection? {
        let decision = sourceQuotaLimiter.acquireConnection(source: sourceIdentity)
        guard decision.allowed else { return nil }
        return RelayAcceptedConnection(
            socket: socket,
            sourceIdentity: sourceIdentity,
            limiter: self,
            requiresImmediateCounterpart: decision.usesCounterpartReserve,
            requiresSameSourceCounterpart: decision.usesSourceCounterpartReserve
        )
    }

    fileprivate func confirmCounterpartCandidate(sourceIdentity: RelaySourceIdentity) {
        sourceQuotaLimiter.confirmCounterpartCandidate(source: sourceIdentity)
    }

    fileprivate func release(
        sourceIdentity: RelaySourceIdentity,
        wasCounterpartCandidate: Bool
    ) {
        sourceQuotaLimiter.releaseConnection(
            source: sourceIdentity,
            wasCounterpartCandidate: wasCounterpartCandidate
        )
    }
}

private final class RelayAcceptedConnection: @unchecked Sendable {
    enum State {
        case open
        case waiting
        case active
        case closed
    }

    private struct CloseTransition {
        let waitingMonitor: DispatchSourceRead?
        let waitingTimeoutTimer: DispatchSourceTimer?
        let wasCounterpartCandidate: Bool
    }

    let socket: Int32
    let sourceIdentity: RelaySourceIdentity

    private let limiter: RelayConnectionLimiter
    private let lock = NSLock()
    private var state: State = .open
    private var waitingMonitor: DispatchSourceRead?
    private var waitingTimeoutTimer: DispatchSourceTimer?
    private var counterpartCandidate: Bool
    private let counterpartRequiresSameSource: Bool

    init(
        socket: Int32,
        sourceIdentity: RelaySourceIdentity,
        limiter: RelayConnectionLimiter,
        requiresImmediateCounterpart: Bool,
        requiresSameSourceCounterpart: Bool
    ) {
        self.socket = socket
        self.sourceIdentity = sourceIdentity
        self.limiter = limiter
        self.counterpartCandidate = requiresImmediateCounterpart
        self.counterpartRequiresSameSource = requiresSameSourceCounterpart
    }

    var requiresImmediateCounterpart: Bool {
        lock.withLock { counterpartCandidate }
    }

    var requiresSameSourceCounterpart: Bool {
        counterpartRequiresSameSource
    }

    func confirmCounterpartCandidateIfNeeded() {
        let shouldConfirm = lock.withLock {
            precondition(state != .closed)
            guard counterpartCandidate else { return false }
            counterpartCandidate = false
            return true
        }
        if shouldConfirm {
            limiter.confirmCounterpartCandidate(sourceIdentity: sourceIdentity)
        }
    }

    func beginWaitingMonitor(
        timeoutSeconds: TimeInterval,
        onClosed: @escaping @Sendable (Bool) -> Void
    ) {
        let readSource = DispatchSource.makeReadSource(
            fileDescriptor: socket,
            queue: DispatchQueue.global(qos: .utility)
        )
        let timeoutTimer = DispatchSource.makeTimerSource(
            queue: DispatchQueue.global(qos: .utility)
        )
        readSource.setEventHandler { [weak self] in
            self?.closeIfWaiting(onClosed: onClosed)
        }
        timeoutTimer.setEventHandler { [weak self] in
            self?.expireIfWaiting(onClosed: onClosed)
        }
        timeoutTimer.schedule(deadline: .now() + timeoutSeconds)
        let shouldResume = lock.withLock {
            guard state == .open else { return false }
            state = .waiting
            waitingMonitor = readSource
            waitingTimeoutTimer = timeoutTimer
            return true
        }
        if shouldResume {
            readSource.resume()
            timeoutTimer.resume()
        } else {
            readSource.cancel()
            timeoutTimer.cancel()
            readSource.resume()
            timeoutTimer.resume()
        }
    }

    @discardableResult
    func activate() -> Bool {
        let transition = lock.withLock { () -> (
            activated: Bool,
            source: DispatchSourceRead?,
            timer: DispatchSourceTimer?
        ) in
            guard state == .open || state == .waiting else { return (false, nil, nil) }
            state = .active
            defer {
                waitingMonitor = nil
                waitingTimeoutTimer = nil
            }
            return (true, waitingMonitor, waitingTimeoutTimer)
        }
        transition.source?.cancel()
        transition.timer?.cancel()
        return transition.activated
    }

    func close() {
        guard let transition = transitionToClosed(requiredState: nil) else { return }
        completeClose(transition)
    }

    private func closeIfWaiting(onClosed: @escaping @Sendable (Bool) -> Void) {
        var byte: UInt8 = 0
        let count = Darwin.recv(socket, &byte, 1, MSG_PEEK | MSG_DONTWAIT)
        if count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
            return
        }
        guard let transition = transitionToClosed(requiredState: .waiting) else {
            return
        }
        transition.waitingMonitor?.cancel()
        transition.waitingTimeoutTimer?.cancel()
        onClosed(false)
        completeClose(transition)
    }

    private func expireIfWaiting(onClosed: @escaping @Sendable (Bool) -> Void) {
        guard let transition = transitionToClosed(requiredState: .waiting) else {
            return
        }
        transition.waitingMonitor?.cancel()
        transition.waitingTimeoutTimer?.cancel()
        onClosed(true)
        completeClose(transition)
    }

    private func completeClose(_ transition: CloseTransition) {
        transition.waitingMonitor?.cancel()
        transition.waitingTimeoutTimer?.cancel()
        shutdown(socket, SHUT_RDWR)
        Darwin.close(socket)
        limiter.release(
            sourceIdentity: sourceIdentity,
            wasCounterpartCandidate: transition.wasCounterpartCandidate
        )
    }

    private func transitionToClosed(
        requiredState: State?
    ) -> CloseTransition? {
        lock.withLock {
            guard state != .closed,
                  requiredState == nil || state == requiredState
            else {
                return nil
            }
            state = .closed
            defer {
                waitingMonitor = nil
                waitingTimeoutTimer = nil
                counterpartCandidate = false
            }
            return CloseTransition(
                waitingMonitor: waitingMonitor,
                waitingTimeoutTimer: waitingTimeoutTimer,
                wasCounterpartCandidate: counterpartCandidate
            )
        }
    }

    deinit {
        close()
    }
}

private final class RelayActiveBridgeTermination: @unchecked Sendable {
    private let runtime: RelayAcceptedConnection
    private let client: RelayAcceptedConnection
    private let matcher: RelayMatcher
    private let matchToken: RelayMatchToken
    private let lock = NSLock()
    private var didShutdown = false
    private var finished = false

    init(
        runtime: RelayAcceptedConnection,
        client: RelayAcceptedConnection,
        matcher: RelayMatcher,
        matchToken: RelayMatchToken
    ) {
        self.runtime = runtime
        self.client = client
        self.matcher = matcher
        self.matchToken = matchToken
    }

    func shutdownBoth() {
        lock.lock()
        defer { lock.unlock() }
        guard !didShutdown else { return }
        didShutdown = true
        shutdown(runtime.socket, SHUT_RDWR)
        shutdown(client.socket, SHUT_RDWR)
    }

    func finish() {
        shutdownBoth()
        lock.withLock {
            guard !finished else { return }
            finished = true
            _ = matcher.release(matchToken: matchToken)
            runtime.close()
            client.close()
        }
    }
}

private final class RelaySocketRegistry: @unchecked Sendable {
    private let lock = NSLock()
    private var sockets: [UUID: RelaySocketPeer] = [:]

    func store(_ peer: RelaySocketPeer) {
        lock.withLock {
            sockets[peer.registration.id] = peer
        }
    }

    func remove(peerID: UUID) -> RelaySocketPeer? {
        lock.withLock {
            sockets.removeValue(forKey: peerID)
        }
    }

    func close(peerID: UUID) {
        if let peer = remove(peerID: peerID) {
            peer.connection.close()
        }
    }
}

private func configureAcceptedSocket(_ socket: Int32) -> Bool {
    var noSignal: Int32 = 1
    return setsockopt(
        socket,
        SOL_SOCKET,
        SO_NOSIGPIPE,
        &noSignal,
        socklen_t(MemoryLayout<Int32>.size)
    ) == 0
}

private func makeListenSocket(host: String, port: UInt16) throws -> Int32 {
    var hints = addrinfo(
        ai_flags: AI_PASSIVE,
        ai_family: AF_UNSPEC,
        ai_socktype: SOCK_STREAM,
        ai_protocol: IPPROTO_TCP,
        ai_addrlen: 0,
        ai_canonname: nil,
        ai_addr: nil,
        ai_next: nil
    )
    var result: UnsafeMutablePointer<addrinfo>?
    let status = getaddrinfo(host, String(port), &hints, &result)
    guard status == 0, let first = result else {
        throw RelayServerError.bindFailed(String(cString: gai_strerror(status)))
    }
    defer { freeaddrinfo(first) }

    var cursor: UnsafeMutablePointer<addrinfo>? = first
    while let info = cursor {
        let fd = Darwin.socket(info.pointee.ai_family, info.pointee.ai_socktype, info.pointee.ai_protocol)
        if fd >= 0 {
            var yes: Int32 = 1
            setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))
            if Darwin.bind(fd, info.pointee.ai_addr, info.pointee.ai_addrlen) == 0,
               Darwin.listen(fd, SOMAXCONN) == 0 {
                return fd
            }
            Darwin.close(fd)
        }
        cursor = info.pointee.ai_next
    }

    throw RelayServerError.bindFailed(String(cString: strerror(errno)))
}

enum RelayServerControlLinePollResult: Equatable {
    case ready(events: Int16)
    case timedOut
    case interrupted
    case failed
}

enum RelayServerControlLineReceiveResult: Equatable {
    case byte(UInt8)
    case closed
    case interrupted
    case failed
}

struct RelayServerControlLineOperations {
    let monotonicNow: () -> UInt64
    let pollSocket: (_ socket: Int32, _ timeoutMilliseconds: Int32) -> RelayServerControlLinePollResult
    let receiveByte: (_ socket: Int32) -> RelayServerControlLineReceiveResult

    static let live = RelayServerControlLineOperations(
        monotonicNow: { DispatchTime.now().uptimeNanoseconds },
        pollSocket: { socket, timeoutMilliseconds in
            var descriptor = pollfd(fd: socket, events: Int16(POLLIN), revents: 0)
            let result = Darwin.poll(&descriptor, 1, timeoutMilliseconds)
            if result > 0 {
                return .ready(events: descriptor.revents)
            }
            if result == 0 {
                return .timedOut
            }
            return errno == EINTR ? .interrupted : .failed
        },
        receiveByte: { socket in
            var byte: UInt8 = 0
            let count = Darwin.recv(socket, &byte, 1, 0)
            if count > 0 {
                return .byte(byte)
            }
            if count == 0 {
                return .closed
            }
            return errno == EINTR ? .interrupted : .failed
        }
    )
}

enum RelayServerControlLineReader {
    static func read(
        socket: Int32,
        maxBytes: Int = 4096,
        timeoutSeconds: TimeInterval,
        operations: RelayServerControlLineOperations = .live
    ) throws -> String {
        var bytes: [UInt8] = []
        bytes.reserveCapacity(64)
        let timeoutNanoseconds = UInt64((timeoutSeconds * 1_000_000_000).rounded(.up))
        let start = operations.monotonicNow()
        let (deadline, overflow) = start.addingReportingOverflow(timeoutNanoseconds)
        guard !overflow else {
            throw RelayServerError.invalidControlLineReadTimeout
        }

        func remainingNanoseconds() throws -> UInt64 {
            let now = operations.monotonicNow()
            guard now < deadline else {
                throw RelayServerError.controlLineReadTimedOut
            }
            return deadline - now
        }

        while bytes.count < maxBytes {
            let currentRemainingNanoseconds = try remainingNanoseconds()
            let remainingMilliseconds = max(
                1,
                min(
                    Int(Int32.max),
                    Int((currentRemainingNanoseconds + 999_999) / 1_000_000)
                )
            )
            let pollResult = operations.pollSocket(socket, Int32(remainingMilliseconds))
            switch pollResult {
            case .interrupted:
                continue
            case .timedOut:
                throw RelayServerError.controlLineReadTimedOut
            case .failed:
                throw RelayServerError.handshakeReadFailed
            case .ready(let events):
                guard events & Int16(POLLIN) != 0 else {
                    throw RelayServerError.handshakeReadFailed
                }
            }

            receive: while true {
                _ = try remainingNanoseconds()
                switch operations.receiveByte(socket) {
                case .interrupted:
                    continue
                case .closed, .failed:
                    throw RelayServerError.handshakeReadFailed
                case .byte(let byte):
                    bytes.append(byte)
                    break receive
                }
            }
            if bytes.last == UInt8(ascii: "\n") {
                break
            }
        }

        return try RelayServerLineFraming.decode(bytes)
    }
}

enum RelayServerLineFraming {
    static func decode(_ data: Data) throws -> String {
        try decode(Array(data))
    }

    static func decode(_ bytes: [UInt8]) throws -> String {
        guard bytes.last == UInt8(ascii: "\n"),
              let line = String(bytes: bytes, encoding: .utf8)
        else {
            throw RelayServerError.handshakeReadFailed
        }
        return line
    }
}

func relayWriteAll(
    rawBuffer: UnsafeRawBufferPointer,
    send: (_ baseAddress: UnsafeRawPointer, _ byteCount: Int) -> Int
) -> Bool {
    guard let base = rawBuffer.baseAddress else { return true }
    var sent = 0
    while sent < rawBuffer.count {
        let count = send(base.advanced(by: sent), rawBuffer.count - sent)
        if count > 0 {
            sent += count
            continue
        }
        if count < 0 && errno == EINTR {
            continue
        }
        if count < 0 && (errno == EPIPE || errno == ECONNRESET) {
            return false
        }
        return false
    }
    return true
}

private func writeAll(socket: Int32, rawBuffer: UnsafeRawBufferPointer) -> Bool {
    relayWriteAll(rawBuffer: rawBuffer) { baseAddress, byteCount in
        Darwin.send(socket, baseAddress, byteCount, 0)
    }
}

private func writeAll(socket: Int32, data: Data) -> Bool {
    data.withUnsafeBytes { rawBuffer in
        writeAll(socket: socket, rawBuffer: rawBuffer)
    }
}

private func forwardBytes(from source: Int32, to destination: Int32) {
    var buffer = [UInt8](repeating: 0, count: 64 * 1024)
    while true {
        let count = buffer.withUnsafeMutableBytes { rawBuffer in
            Darwin.recv(source, rawBuffer.baseAddress, rawBuffer.count, 0)
        }
        if count < 0 && errno == EINTR {
            continue
        }
        guard count > 0 else { return }
        let wroteAll = buffer.withUnsafeBytes { rawBuffer in
            let validBuffer = UnsafeRawBufferPointer(
                start: rawBuffer.baseAddress,
                count: count
            )
            return writeAll(socket: destination, rawBuffer: validBuffer)
        }
        guard wroteAll else { return }
    }
}

private func shortID(_ value: String) -> String {
    guard value.count > 12 else { return value }
    return "\(value.prefix(6))...\(value.suffix(6))"
}

private func secureRandomHex(byteCount: Int) -> String {
    var generator = SystemRandomNumberGenerator()
    return (0..<byteCount).map { _ in
        String(format: "%02x", UInt8.random(in: .min ... .max, using: &generator))
    }.joined()
}

private func epochMillis(_ date: Date) -> Int64 {
    Int64((date.timeIntervalSince1970 * 1000).rounded())
}

private func log(_ message: String) {
    print("[relay] \(message)")
    fflush(stdout)
}

public enum RelayServerError: Error, Equatable, Sendable, CustomStringConvertible {
    case serverAlreadyRunning
    case bindFailed(String)
    case handshakeReadFailed
    case controlLineReadTimedOut
    case allocationWriteFailed
    case registrationChallengeWriteFailed
    case probeWriteFailed
    case invalidAllocationToken
    case invalidControlLineReadTimeout
    case invalidMaximumConcurrentConnections
    case legacyRelayRequiresLoopback(String)
    case allocationTokenRequiredForExposedBind(String)
    case durableAllocationStoreRequired(String)
    case allocationStoreAlreadyOwned(String)
    case allocationStoreLockFailed(String)

    public var description: String {
        switch self {
        case .serverAlreadyRunning:
            return "relay server is already running"
        case .bindFailed(let message):
            return "bind failed: \(message)"
        case .handshakeReadFailed:
            return "handshake read failed"
        case .controlLineReadTimedOut:
            return "control line read timed out"
        case .allocationWriteFailed:
            return "allocation response write failed"
        case .registrationChallengeWriteFailed:
            return "registration challenge write failed"
        case .probeWriteFailed:
            return "probe response write failed"
        case .invalidAllocationToken:
            return "allocation token must be non-empty and contain no whitespace"
        case .invalidControlLineReadTimeout:
            return "control line read timeout must be greater than zero and at most 300 seconds"
        case .invalidMaximumConcurrentConnections:
            return "maximum concurrent connections must be between 1 and 65536"
        case .legacyRelayRequiresLoopback(let host):
            return "legacy unallocated relay mode is loopback-only; refusing exposed bind \(host)"
        case .allocationTokenRequiredForExposedBind(let host):
            return "allocation token required for non-loopback relay bind \(host); bind tokenless diagnostics to 127.0.0.1, ::1, or localhost, or set --allocation-token / AETHERLINK_RELAY_ALLOCATION_TOKEN"
        case .durableAllocationStoreRequired(let host):
            return "durable allocation store required for strict non-loopback relay bind \(host); set --allocation-store and do not use --ephemeral-allocations"
        case .allocationStoreAlreadyOwned(let path):
            return "allocation store is already owned by another relay process: \(path)"
        case .allocationStoreLockFailed(let path):
            return "allocation store lock could not be acquired securely: \(path)"
        }
    }
}

private final class RelayServerRunState: @unchecked Sendable {
    struct Acquisition: Equatable, Sendable {
        fileprivate let id: UUID
    }

    private let lock = NSLock()
    private var activeAcquisition: Acquisition?
    private var allocationStoreOwnership: RelayAllocationStoreOwnership?

    func acquire() throws -> Acquisition {
        try lock.withLock {
            guard activeAcquisition == nil else {
                throw RelayServerError.serverAlreadyRunning
            }
            let acquisition = Acquisition(id: UUID())
            activeAcquisition = acquisition
            return acquisition
        }
    }

    func acquireAllocationStoreOwnershipIfNeeded(
        storeURL: URL?,
        for acquisition: Acquisition
    ) throws {
        guard let storeURL else { return }
        try lock.withLock {
            precondition(activeAcquisition == acquisition)
            precondition(allocationStoreOwnership == nil)
            do {
                allocationStoreOwnership = try RelayAllocationStoreOwnership.acquire(
                    storeURL: storeURL
                )
            } catch RelayAllocationStoreCoordinationError.storeAlreadyOwned {
                throw RelayServerError.allocationStoreAlreadyOwned(storeURL.path)
            } catch {
                throw RelayServerError.allocationStoreLockFailed(storeURL.path)
            }
        }
    }

    func release(_ acquisition: Acquisition) {
        lock.withLock {
            guard activeAcquisition == acquisition else { return }
            allocationStoreOwnership = nil
            activeAcquisition = nil
        }
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
