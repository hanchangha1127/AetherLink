#if DEBUG
import Foundation
import P2PNATContracts
import Transport
import TrustedDevices

enum MacRuntimeVerifiedProductionRelayStartPlanError: Error, Equatable, Sendable {
    case routeAuthorizationMismatch
    case unsupportedRouteKind
}

/// Opaque future handoff from the verified C1 route-plan adapter to the production coordinator.
/// There is intentionally no non-test factory until C1-specific durable admission is wired.
struct MacRuntimeVerifiedProductionRelayStartPlan: Equatable, Sendable {
    fileprivate let attempt: MacRuntimeProductionPairConnectorAttempt
    fileprivate let configuration: RelayPeerConfiguration

    var clientKeyFingerprint: String { attempt.clientKeyFingerprint }
    var sessionID: String { attempt.transcript.sessionId }
    var transcriptDigest: String { attempt.transcript.digestHex }

    fileprivate init(
        attempt: MacRuntimeProductionPairConnectorAttempt,
        configuration: RelayPeerConfiguration
    ) throws {
        guard attempt.transcript.matches(attempt.routeAuthorization) else {
            throw MacRuntimeVerifiedProductionRelayStartPlanError.routeAuthorizationMismatch
        }
        switch attempt.routeAuthorization.kind {
        case .turnRelay, .sealedRelay:
            break
        case .localDirect, .p2pPublish, .p2pFetch, .p2pDirect:
            throw MacRuntimeVerifiedProductionRelayStartPlanError.unsupportedRouteKind
        }
        self.attempt = attempt
        self.configuration = configuration
    }

    #if DEBUG
    static func testing(
        attempt: MacRuntimeProductionPairConnectorAttempt,
        configuration: RelayPeerConfiguration
    ) throws -> Self {
        try Self(attempt: attempt, configuration: configuration)
    }
    #endif
}

struct MacRuntimeAdmittedProductionPairRelayStart: Sendable {
    fileprivate let plan: MacRuntimeVerifiedProductionRelayStartPlan
    fileprivate let permit: ProductionPairAdmissionPermit

    var clientKeyFingerprint: String { plan.clientKeyFingerprint }
    var configuration: RelayPeerConfiguration { plan.configuration }

    fileprivate init(
        plan: MacRuntimeVerifiedProductionRelayStartPlan,
        permit: ProductionPairAdmissionPermit
    ) {
        self.plan = plan
        self.permit = permit
    }
}

enum MacRuntimeProductionPairCoordinatorState: Equatable, Sendable {
    case pending(generationID: UUID, sessionID: String)
    case active(generationID: UUID, sessionID: String, transcriptDigest: String)
    case blocked(generationID: UUID)
}

@MainActor
final class MacRuntimeProductionPairCoordinator {
    typealias StatusHandler = MacRuntimeConnectionManager.StatusHandler

    private let authorizer: any MacRuntimeProductionPairAuthorizing
    private let connectionManager: MacRuntimeConnectionManager
    private var states: [String: MacRuntimeProductionPairCoordinatorState] = [:]

    init(
        authorizer: any MacRuntimeProductionPairAuthorizing,
        connectionManager: MacRuntimeConnectionManager
    ) {
        self.authorizer = authorizer
        self.connectionManager = connectionManager
    }

    func startRelay(
        plan: MacRuntimeVerifiedProductionRelayStartPlan,
        onStatusChange: StatusHandler? = nil,
        onMessage: @escaping LocalPeerMessageHandler
    ) async throws {
        let fingerprint = plan.clientKeyFingerprint
        let generationID = UUID()
        states[fingerprint] = .pending(
            generationID: generationID,
            sessionID: plan.sessionID
        )
        connectionManager.stopPair(fingerprint: fingerprint)

        let permit: ProductionPairAdmissionPermit
        do {
            permit = try await authorizer.authorizeProductionPairConnector(plan.attempt)
        } catch {
            blockPendingIfCurrent(fingerprint: fingerprint, generationID: generationID)
            throw error
        }

        do {
            try Task.checkCancellation()
            guard states[fingerprint] == .pending(
                generationID: generationID,
                sessionID: plan.sessionID
            ) else {
                throw CancellationError()
            }
        } catch {
            blockPendingIfCurrent(fingerprint: fingerprint, generationID: generationID)
            throw error
        }

        states[fingerprint] = .active(
            generationID: generationID,
            sessionID: plan.sessionID,
            transcriptDigest: plan.transcriptDigest
        )
        connectionManager.startAdmittedProductionPairRelay(
            MacRuntimeAdmittedProductionPairRelayStart(plan: plan, permit: permit),
            onStatusChange: { [weak self] status in
                if status == .stopped {
                    self?.clearActiveIfCurrent(
                        fingerprint: fingerprint,
                        generationID: generationID
                    )
                }
                onStatusChange?(status)
            },
            onMessage: onMessage
        )
    }

    func stopPair(fingerprint: String) {
        states[fingerprint] = .blocked(generationID: UUID())
        connectionManager.stopPair(fingerprint: fingerprint)
    }

    func revokePair(fingerprint: String) {
        stopPair(fingerprint: fingerprint)
    }

    func authorityDidAdvance(fingerprint: String) {
        stopPair(fingerprint: fingerprint)
    }

    func stopAll() {
        for fingerprint in Array(states.keys) {
            states[fingerprint] = .blocked(generationID: UUID())
        }
        connectionManager.stopAll()
    }

    func state(fingerprint: String) -> MacRuntimeProductionPairCoordinatorState? {
        states[fingerprint]
    }

    private func blockPendingIfCurrent(fingerprint: String, generationID: UUID) {
        guard case .pending(let currentGenerationID, _) = states[fingerprint],
              currentGenerationID == generationID else {
            return
        }
        states[fingerprint] = .blocked(generationID: UUID())
    }

    private func clearActiveIfCurrent(fingerprint: String, generationID: UUID) {
        guard case .active(let currentGenerationID, _, _) = states[fingerprint],
              currentGenerationID == generationID else {
            return
        }
        states[fingerprint] = nil
    }
}
#endif
