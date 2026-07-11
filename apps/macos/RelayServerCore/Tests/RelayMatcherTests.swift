import Darwin
import XCTest
@testable import RelayServerCore

final class RelayMatcherTests: XCTestCase {
    func testWaitingDeadlinePersistsAcrossSameRoleReplacement() throws {
        let sourceA = try sourceIdentity("192.0.2.63")
        let sourceB = try sourceIdentity("192.0.2.64")
        let sourceQuotaLimiter = RelaySourceQuotaLimiter(
            maximumConnections: 8,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 4,
                maximumWaitingPeersPerSource: 2
            )
        )
        let clock = MatcherPolicyClock(now: 100)
        let matcher = RelayMatcher(
            sourceQuotaLimiter: sourceQuotaLimiter,
            maximumWaitingDurationSeconds: 60,
            monotonicNow: { clock.value }
        )
        let binding = makeBinding(relayID: "deadline-replacement")
        let runtime = registration(.runtime, binding: binding)
        let replacement = registration(.runtime, binding: binding)

        XCTAssertTrue(sourceQuotaLimiter.acquireConnection(source: sourceA).allowed)
        XCTAssertEqual(
            matcher.register(runtime, sourceIdentity: sourceA),
            .waiting(replaced: nil)
        )
        XCTAssertEqual(
            matcher.waitingDeadlineUptime(relayID: binding.relayID, peerID: runtime.id),
            160
        )

        clock.value = 150
        XCTAssertTrue(sourceQuotaLimiter.acquireConnection(source: sourceB).allowed)
        XCTAssertEqual(
            matcher.register(replacement, sourceIdentity: sourceB),
            .waiting(replaced: runtime)
        )
        XCTAssertNil(
            matcher.waitingDeadlineUptime(relayID: binding.relayID, peerID: runtime.id)
        )
        XCTAssertEqual(
            matcher.waitingDeadlineUptime(
                relayID: binding.relayID,
                peerID: replacement.id
            ),
            160
        )

        XCTAssertEqual(matcher.unregisterWaiting(peerID: replacement.id), replacement)
        clock.value = 200
        let leaseCappedBinding = makeBinding(relayID: "lease-capped-deadline")
        let leaseCappedRuntime = registration(.runtime, binding: leaseCappedBinding)
        XCTAssertTrue(sourceQuotaLimiter.acquireConnection(source: sourceA).allowed)
        XCTAssertEqual(
            matcher.register(
                leaseCappedRuntime,
                sourceIdentity: sourceA,
                maximumWaitingDeadlineUptime: 230
            ),
            .waiting(replaced: nil)
        )
        XCTAssertEqual(
            matcher.waitingDeadlineUptime(
                relayID: leaseCappedBinding.relayID,
                peerID: leaseCappedRuntime.id
            ),
            230
        )
        XCTAssertEqual(
            matcher.unregisterWaiting(peerID: leaseCappedRuntime.id),
            leaseCappedRuntime
        )
        sourceQuotaLimiter.releaseConnection(source: sourceA)
        sourceQuotaLimiter.releaseConnection(source: sourceA)
        sourceQuotaLimiter.releaseConnection(source: sourceB)
    }

    func testAuthenticatedIdentityQuotaIsCrossSourceAndReleasesEveryWaitingPath() throws {
        let sourceA = try sourceIdentity("192.0.2.61")
        let sourceB = try sourceIdentity("192.0.2.62")
        let sourceQuotaLimiter = RelaySourceQuotaLimiter(
            maximumConnections: 16,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 8,
                maximumWaitingPeersPerSource: 4
            )
        )
        let log = MatcherWaitingPolicyLogCapture()
        let waitingPeerLimiter = RelayWaitingPeerLimiter(
            configuration: RelayWaitingPeerPolicyConfiguration(
                maximumDurationSeconds: 30,
                maximumPeersPerAuthenticatedIdentity: 1
            ),
            rejectionLog: { log.append($0) }
        )
        let matcher = RelayMatcher(
            sourceQuotaLimiter: sourceQuotaLimiter,
            waitingPeerLimiter: waitingPeerLimiter
        )
        let identityA = try XCTUnwrap(authenticatedIdentity(.runtime, digit: "a"))
        let identityB = try XCTUnwrap(authenticatedIdentity(.runtime, digit: "b"))
        let clientIdentity = try XCTUnwrap(authenticatedIdentity(.client, digit: "c"))
        let bindingA = makeBinding(relayID: "identity-a")
        let bindingASecond = makeBinding(relayID: "identity-a-second")
        let bindingB = makeBinding(relayID: "identity-b")
        let runtimeA = registration(.runtime, binding: bindingA, identity: identityA)
        let rejectedRuntimeA = registration(
            .runtime,
            binding: bindingASecond,
            identity: identityA
        )
        let runtimeB = registration(.runtime, binding: bindingB, identity: identityB)

        XCTAssertTrue(sourceQuotaLimiter.acquireConnection(source: sourceA).allowed)
        XCTAssertEqual(
            matcher.register(runtimeA, sourceIdentity: sourceA),
            .waiting(replaced: nil)
        )
        XCTAssertTrue(sourceQuotaLimiter.acquireConnection(source: sourceB).allowed)
        XCTAssertEqual(
            matcher.register(rejectedRuntimeA, sourceIdentity: sourceB),
            .rejected(.authenticatedIdentityWaitingQuota)
        )
        sourceQuotaLimiter.releaseConnection(source: sourceB)
        XCTAssertEqual(sourceQuotaLimiter.metricsSnapshot().waitingPeers, 1)

        XCTAssertTrue(sourceQuotaLimiter.acquireConnection(source: sourceB).allowed)
        XCTAssertEqual(
            matcher.register(runtimeB, sourceIdentity: sourceB),
            .waiting(replaced: nil)
        )
        XCTAssertTrue(sourceQuotaLimiter.acquireConnection(source: sourceA).allowed)
        let clientA = registration(.client, binding: bindingA, identity: clientIdentity)
        let matchToken = try matchToken(
            from: matcher.register(clientA, sourceIdentity: sourceA),
            runtime: runtimeA,
            client: clientA
        )
        XCTAssertNotNil(matcher.release(matchToken: matchToken))

        XCTAssertTrue(sourceQuotaLimiter.acquireConnection(source: sourceA).allowed)
        XCTAssertEqual(
            matcher.register(rejectedRuntimeA, sourceIdentity: sourceA),
            .waiting(replaced: nil)
        )
        XCTAssertTrue(sourceQuotaLimiter.acquireConnection(source: sourceB).allowed)
        let replacementA = registration(
            .runtime,
            binding: bindingASecond,
            identity: identityA
        )
        XCTAssertEqual(
            matcher.register(replacementA, sourceIdentity: sourceB),
            .waiting(replaced: rejectedRuntimeA)
        )
        sourceQuotaLimiter.releaseConnection(source: sourceA)
        XCTAssertEqual(
            matcher.invalidateWaiting(
                relayID: bindingASecond.relayID,
                keeping: makeBinding(relayID: bindingASecond.relayID, generation: 8)
            ),
            [replacementA]
        )
        XCTAssertEqual(matcher.unregisterWaiting(peerID: runtimeB.id), runtimeB)

        let metrics = waitingPeerLimiter.metricsSnapshot()
        XCTAssertEqual(metrics.identityWaitingAdmissionRequestsTotal, 4)
        XCTAssertEqual(metrics.identityWaitingPeersAdmittedTotal, 3)
        XCTAssertEqual(metrics.identityWaitingQuotaRejectionsTotal, 1)
        XCTAssertEqual(metrics.authenticatedIdentityWaitingPeers, 0)
        XCTAssertEqual(metrics.authenticatedIdentitiesWithWaiters, 0)
        XCTAssertEqual(
            log.messages,
            ["reason=authenticated_identity_waiting_quota_reached reason_count=1"]
        )
        XCTAssertEqual(sourceQuotaLimiter.metricsSnapshot().waitingPeers, 0)

        sourceQuotaLimiter.releaseConnection(source: sourceA)
        sourceQuotaLimiter.releaseConnection(source: sourceA)
        sourceQuotaLimiter.releaseConnection(source: sourceB)
        sourceQuotaLimiter.releaseConnection(source: sourceB)
        XCTAssertEqual(sourceQuotaLimiter.metricsSnapshot().activeConnections, 0)
    }

    func testSourceWaitingQuotaRejectsOnlyNewWaitersAndAllowsImmediateMatch() throws {
        let source = try sourceIdentity("192.0.2.40")
        let quotaLimiter = RelaySourceQuotaLimiter(
            maximumConnections: 4,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 4,
                maximumWaitingPeersPerSource: 1
            )
        )
        for _ in 0..<3 {
            XCTAssertTrue(quotaLimiter.acquireConnection(source: source).allowed)
        }
        let matcher = RelayMatcher(sourceQuotaLimiter: quotaLimiter)
        let firstBinding = makeBinding(relayID: "quota-first")
        let secondBinding = makeBinding(relayID: "quota-second")
        let runtime = registration(.runtime, binding: firstBinding)
        let rejectedRuntime = registration(.runtime, binding: secondBinding)
        let client = registration(.client, binding: firstBinding)

        XCTAssertEqual(
            matcher.register(runtime, sourceIdentity: source),
            .waiting(replaced: nil)
        )
        XCTAssertEqual(
            matcher.register(rejectedRuntime, sourceIdentity: source),
            .rejected(.sourceWaitingPeerQuota)
        )
        _ = try matchToken(
            from: matcher.register(client, sourceIdentity: source),
            runtime: runtime,
            client: client
        )
        let metrics = quotaLimiter.metricsSnapshot()
        XCTAssertEqual(metrics.waitingPeers, 0)
        XCTAssertEqual(metrics.sourceWaitingPeerQuotaRejectionsTotal, 1)

        for _ in 0..<3 {
            quotaLimiter.releaseConnection(source: source)
        }
    }

    func testCrossSourceReplacementRejectionPreservesOriginalWaiter() throws {
        let sourceA = try sourceIdentity("198.51.100.40")
        let sourceB = try sourceIdentity("198.51.100.41")
        let quotaLimiter = RelaySourceQuotaLimiter(
            maximumConnections: 8,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 4,
                maximumWaitingPeersPerSource: 1
            )
        )
        for source in [sourceA, sourceA, sourceB, sourceB] {
            XCTAssertTrue(quotaLimiter.acquireConnection(source: source).allowed)
        }
        let matcher = RelayMatcher(sourceQuotaLimiter: quotaLimiter)
        let replaced = registration(.runtime, binding: makeBinding(relayID: "replace-room"))
        let replacement = registration(.runtime, binding: replaced.roomBinding!)
        let otherSourceWaiter = registration(
            .runtime,
            binding: makeBinding(relayID: "source-b-full")
        )

        XCTAssertEqual(
            matcher.register(replaced, sourceIdentity: sourceA),
            .waiting(replaced: nil)
        )
        XCTAssertEqual(
            matcher.register(otherSourceWaiter, sourceIdentity: sourceB),
            .waiting(replaced: nil)
        )
        XCTAssertEqual(
            matcher.register(replacement, sourceIdentity: sourceB),
            .rejected(.sourceWaitingPeerQuota)
        )
        XCTAssertEqual(matcher.waitingRegistrations(relayID: replaced.relayID), [replaced])

        XCTAssertEqual(matcher.unregisterWaiting(peerID: otherSourceWaiter.id), otherSourceWaiter)
        XCTAssertEqual(
            matcher.register(replacement, sourceIdentity: sourceB),
            .waiting(replaced: replaced)
        )
        XCTAssertEqual(matcher.waitingRegistrations(relayID: replaced.relayID), [replacement])
        XCTAssertEqual(quotaLimiter.metricsSnapshot().waitingPeers, 1)

        XCTAssertEqual(matcher.unregisterWaiting(peerID: replacement.id), replacement)
        for source in [sourceA, sourceA, sourceB, sourceB] {
            quotaLimiter.releaseConnection(source: source)
        }
    }

    func testWaitingQuotaReleasesOnInvalidation() throws {
        let source = try sourceIdentity("203.0.113.40")
        let quotaLimiter = RelaySourceQuotaLimiter(
            maximumConnections: 4,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 4,
                maximumWaitingPeersPerSource: 1
            )
        )
        XCTAssertTrue(quotaLimiter.acquireConnection(source: source).allowed)
        XCTAssertTrue(quotaLimiter.acquireConnection(source: source).allowed)
        let matcher = RelayMatcher(sourceQuotaLimiter: quotaLimiter)
        let oldBinding = makeBinding(relayID: "invalidate-quota", generation: 1)
        let currentBinding = makeBinding(relayID: "invalidate-quota", generation: 2)
        let oldRuntime = registration(.runtime, binding: oldBinding)
        let nextRuntime = registration(.runtime, binding: currentBinding)

        XCTAssertEqual(
            matcher.register(oldRuntime, sourceIdentity: source),
            .waiting(replaced: nil)
        )
        XCTAssertEqual(
            matcher.invalidateWaiting(relayID: oldRuntime.relayID, keeping: currentBinding),
            [oldRuntime]
        )
        XCTAssertEqual(quotaLimiter.metricsSnapshot().waitingPeers, 0)
        XCTAssertEqual(
            matcher.register(nextRuntime, sourceIdentity: source),
            .waiting(replaced: nil)
        )
        XCTAssertEqual(matcher.unregisterWaiting(peerID: nextRuntime.id), nextRuntime)

        quotaLimiter.releaseConnection(source: source)
        quotaLimiter.releaseConnection(source: source)
    }

    func testCounterpartOnlyRegistrationAllowsMatchOrSameSourceReplacement() throws {
        let source = try sourceIdentity("203.0.113.41")
        let binding = makeBinding(relayID: "counterpart-only")

        do {
            let quotaLimiter = RelaySourceQuotaLimiter(
                maximumConnections: 2,
                configuration: RelaySourceQuotaConfiguration(
                    maximumConnectionsPerSource: 2,
                    maximumWaitingPeersPerSource: 1
                )
            )
            let matcher = RelayMatcher(sourceQuotaLimiter: quotaLimiter)
            let runtime = registration(.runtime, binding: binding)
            let client = registration(.client, binding: binding)
            XCTAssertTrue(quotaLimiter.acquireConnection(source: source).allowed)
            XCTAssertEqual(
                matcher.register(runtime, sourceIdentity: source),
                .waiting(replaced: nil)
            )
            let candidate = quotaLimiter.acquireConnection(source: source)
            XCTAssertTrue(candidate.usesCounterpartReserve)
            _ = try matchToken(
                from: matcher.register(
                    client,
                    sourceIdentity: source,
                    requiresImmediateMatch: true
                ),
                runtime: runtime,
                client: client
            )
            quotaLimiter.confirmCounterpartCandidate(source: source)
            XCTAssertEqual(quotaLimiter.metricsSnapshot().waitingPeers, 0)
            quotaLimiter.releaseConnection(source: source)
            quotaLimiter.releaseConnection(source: source)
        }

        do {
            let quotaLimiter = RelaySourceQuotaLimiter(
                maximumConnections: 2,
                configuration: RelaySourceQuotaConfiguration(
                    maximumConnectionsPerSource: 2,
                    maximumWaitingPeersPerSource: 1
                )
            )
            let matcher = RelayMatcher(sourceQuotaLimiter: quotaLimiter)
            let runtime = registration(.runtime, binding: binding)
            let replacement = registration(.runtime, binding: binding)
            XCTAssertTrue(quotaLimiter.acquireConnection(source: source).allowed)
            XCTAssertEqual(
                matcher.register(runtime, sourceIdentity: source),
                .waiting(replaced: nil)
            )
            let candidate = quotaLimiter.acquireConnection(source: source)
            XCTAssertTrue(candidate.usesCounterpartReserve)
            XCTAssertEqual(
                matcher.register(
                    replacement,
                    sourceIdentity: source,
                    requiresImmediateMatch: true
                ),
                .waiting(replaced: runtime)
            )
            quotaLimiter.confirmCounterpartCandidate(source: source)
            quotaLimiter.releaseConnection(source: source)
            XCTAssertEqual(
                matcher.waitingRegistrations(relayID: binding.relayID),
                [replacement]
            )
            XCTAssertEqual(matcher.unregisterWaiting(peerID: replacement.id), replacement)
            quotaLimiter.releaseConnection(source: source)
            let metrics = quotaLimiter.metricsSnapshot()
            XCTAssertEqual(metrics.counterpartCandidatesConfirmedTotal, 1)
            XCTAssertEqual(metrics.counterpartCandidatesRejectedTotal, 0)
            XCTAssertEqual(metrics.activeConnections, 0)
            XCTAssertEqual(metrics.waitingPeers, 0)
        }

        do {
            let sourceB = try sourceIdentity("203.0.113.42")
            let quotaLimiter = RelaySourceQuotaLimiter(
                maximumConnections: 3,
                configuration: RelaySourceQuotaConfiguration(
                    maximumConnectionsPerSource: 4,
                    maximumWaitingPeersPerSource: 1
                )
            )
            let matcher = RelayMatcher(sourceQuotaLimiter: quotaLimiter)
            let runtime = registration(.runtime, binding: binding)
            let replacement = registration(.runtime, binding: binding)
            XCTAssertTrue(quotaLimiter.acquireConnection(source: source).allowed)
            XCTAssertEqual(
                matcher.register(runtime, sourceIdentity: source),
                .waiting(replaced: nil)
            )
            XCTAssertTrue(quotaLimiter.acquireConnection(source: sourceB).allowed)
            let candidate = quotaLimiter.acquireConnection(source: sourceB)
            XCTAssertTrue(candidate.usesCounterpartReserve)
            XCTAssertTrue(candidate.usesGlobalCounterpartReserve)
            XCTAssertFalse(candidate.usesSourceCounterpartReserve)
            XCTAssertEqual(
                matcher.register(
                    replacement,
                    sourceIdentity: sourceB,
                    requiresImmediateMatch: true
                ),
                .rejected(.counterpartRequired)
            )
            XCTAssertEqual(matcher.waitingRegistrations(relayID: binding.relayID), [runtime])
            quotaLimiter.releaseConnection(source: sourceB, wasCounterpartCandidate: true)
            XCTAssertEqual(matcher.unregisterWaiting(peerID: runtime.id), runtime)
            quotaLimiter.releaseConnection(source: source)
            quotaLimiter.releaseConnection(source: sourceB)
            let metrics = quotaLimiter.metricsSnapshot()
            XCTAssertEqual(metrics.counterpartCandidatesConfirmedTotal, 0)
            XCTAssertEqual(metrics.counterpartCandidatesRejectedTotal, 1)
            XCTAssertEqual(metrics.activeConnections, 0)
            XCTAssertEqual(metrics.waitingPeers, 0)
        }
    }

    func testSourceReserveCandidateCannotDischargeAnotherSourcesWaiter() throws {
        let sourceA = try sourceIdentity("203.0.113.51")
        let sourceB = try sourceIdentity("203.0.113.52")
        let quotaLimiter = RelaySourceQuotaLimiter(
            maximumConnections: 8,
            configuration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 4,
                maximumWaitingPeersPerSource: 1
            )
        )
        let matcher = RelayMatcher(sourceQuotaLimiter: quotaLimiter)
        let bindingA = makeBinding(relayID: "source-reserve-a")
        let bindingB = makeBinding(relayID: "source-reserve-b")
        let runtimeA = registration(.runtime, binding: bindingA)
        let runtimeB = registration(.runtime, binding: bindingB)

        for _ in 0..<3 {
            XCTAssertTrue(quotaLimiter.acquireConnection(source: sourceA).allowed)
        }
        XCTAssertEqual(
            matcher.register(runtimeA, sourceIdentity: sourceA),
            .waiting(replaced: nil)
        )
        XCTAssertTrue(quotaLimiter.acquireConnection(source: sourceB).allowed)
        XCTAssertEqual(
            matcher.register(runtimeB, sourceIdentity: sourceB),
            .waiting(replaced: nil)
        )

        let crossSourceCandidate = quotaLimiter.acquireConnection(source: sourceA)
        XCTAssertTrue(crossSourceCandidate.usesCounterpartReserve)
        XCTAssertFalse(crossSourceCandidate.usesGlobalCounterpartReserve)
        XCTAssertTrue(crossSourceCandidate.usesSourceCounterpartReserve)
        let clientB = registration(.client, binding: bindingB)
        XCTAssertEqual(
            matcher.register(
                clientB,
                sourceIdentity: sourceA,
                requiresImmediateMatch: true,
                requiresSameSourceCounterpart: true
            ),
            .rejected(.counterpartRequired)
        )
        XCTAssertEqual(matcher.waitingRegistrations(relayID: bindingA.relayID), [runtimeA])
        XCTAssertEqual(matcher.waitingRegistrations(relayID: bindingB.relayID), [runtimeB])
        quotaLimiter.releaseConnection(source: sourceA, wasCounterpartCandidate: true)

        let sameSourceCandidate = quotaLimiter.acquireConnection(source: sourceA)
        XCTAssertTrue(sameSourceCandidate.usesSourceCounterpartReserve)
        let clientA = registration(.client, binding: bindingA)
        let token = try matchToken(
            from: matcher.register(
                clientA,
                sourceIdentity: sourceA,
                requiresImmediateMatch: true,
                requiresSameSourceCounterpart: true
            ),
            runtime: runtimeA,
            client: clientA
        )
        quotaLimiter.confirmCounterpartCandidate(source: sourceA)
        XCTAssertNotNil(matcher.release(matchToken: token))
        XCTAssertEqual(matcher.unregisterWaiting(peerID: runtimeB.id), runtimeB)

        for _ in 0..<4 {
            quotaLimiter.releaseConnection(source: sourceA)
        }
        quotaLimiter.releaseConnection(source: sourceB)
        let metrics = quotaLimiter.metricsSnapshot()
        XCTAssertEqual(metrics.counterpartCandidatesConfirmedTotal, 1)
        XCTAssertEqual(metrics.counterpartCandidatesRejectedTotal, 1)
        XCTAssertEqual(metrics.activeConnections, 0)
        XCTAssertEqual(metrics.waitingPeers, 0)
    }

    func testExactBindingMatchCreatesActiveRoomAndRejectsDuplicates() throws {
        let matcher = RelayMatcher()
        let binding = makeBinding()
        let runtime = registration(.runtime, binding: binding)
        let client = registration(.client, binding: binding)

        XCTAssertEqual(matcher.register(runtime), .waiting(replaced: nil))
        let token = try matchToken(from: matcher.register(client), runtime: runtime, client: client)

        XCTAssertEqual(matcher.pendingCount(), 0)
        XCTAssertEqual(matcher.activeCount(), 1)
        XCTAssertEqual(matcher.activeCount(relayID: binding.relayID), 1)
        XCTAssertFalse(matcher.hasWaitingRuntime(relayID: binding.relayID))
        XCTAssertEqual(
            matcher.register(registration(.runtime, binding: binding)),
            .rejected(.activeRoom)
        )
        XCTAssertNil(matcher.unregisterWaiting(peerID: runtime.id))
        XCTAssertEqual(
            matcher.invalidateWaiting(
                relayID: binding.relayID,
                keeping: makeBinding(generation: binding.ticketGeneration + 1)
            ),
            []
        )
        XCTAssertEqual(matcher.activeCount(), 1)
        XCTAssertEqual(matcher.activeRoom(relayID: binding.relayID)?.matchToken, token)
    }

    func testReleaseAllowsRoomToReconnect() throws {
        let matcher = RelayMatcher()
        let binding = makeBinding()
        let runtime = registration(.runtime, binding: binding)
        let client = registration(.client, binding: binding)
        XCTAssertEqual(matcher.register(runtime), .waiting(replaced: nil))
        let token = try matchToken(from: matcher.register(client), runtime: runtime, client: client)

        let released = try XCTUnwrap(matcher.release(matchToken: token))
        XCTAssertEqual(released.runtime, runtime)
        XCTAssertEqual(released.client, client)
        XCTAssertEqual(matcher.activeCount(), 0)
        XCTAssertNil(matcher.release(matchToken: token))

        let reconnectedRuntime = registration(.runtime, binding: binding)
        XCTAssertEqual(matcher.register(reconnectedRuntime), .waiting(replaced: nil))
        XCTAssertEqual(matcher.waitingRegistrations(relayID: binding.relayID), [reconnectedRuntime])
    }

    func testReconnectReplacementRequiresExactVerifiedBinding() {
        let matcher = RelayMatcher()
        let binding = makeBinding()
        let firstRuntime = registration(.runtime, binding: binding)
        let secondRuntime = registration(.runtime, binding: binding)

        XCTAssertEqual(matcher.register(firstRuntime), .waiting(replaced: nil))
        XCTAssertEqual(matcher.register(secondRuntime), .waiting(replaced: firstRuntime))
        XCTAssertEqual(matcher.waitingRegistrations(relayID: binding.relayID), [secondRuntime])
    }

    func testStaleGenerationNonceAndOwnerAreRejectedWithoutMutation() throws {
        let baseline = makeBinding()
        let mismatches = [
            makeBinding(generation: baseline.ticketGeneration + 1),
            makeBinding(relayNonce: "new-relay-nonce"),
            makeBinding(runtimeFingerprint: "runtime-owner-b"),
            makeBinding(pairedClientFingerprint: "client-owner-b"),
            makeBinding(pairedClientFingerprint: nil)
        ]

        for mismatch in mismatches {
            let matcher = RelayMatcher()
            let waitingRuntime = registration(.runtime, binding: baseline)
            XCTAssertEqual(matcher.register(waitingRuntime), .waiting(replaced: nil))

            XCTAssertEqual(
                matcher.register(registration(.runtime, binding: mismatch)),
                .rejected(.roomBindingMismatch)
            )
            XCTAssertEqual(
                matcher.register(registration(.client, binding: mismatch)),
                .rejected(.roomBindingMismatch)
            )
            XCTAssertEqual(matcher.pendingCount(relayID: baseline.relayID), 1)
            XCTAssertEqual(matcher.waitingRegistrations(relayID: baseline.relayID), [waitingRuntime])
            XCTAssertEqual(matcher.activeCount(), 0)

            let validClient = registration(.client, binding: baseline)
            _ = try matchToken(
                from: matcher.register(validClient),
                runtime: waitingRuntime,
                client: validClient
            )
        }
    }

    func testBindingWithDifferentRelayIDIsRejectedWithoutCreatingRoom() {
        let matcher = RelayMatcher()
        let peer = RelayPeerRegistration(
            role: .runtime,
            relayID: "room-a",
            roomBinding: makeBinding(relayID: "room-b")
        )

        XCTAssertEqual(matcher.register(peer), .rejected(.roomBindingMismatch))
        XCTAssertEqual(matcher.pendingCount(), 0)
        XCTAssertEqual(matcher.activeCount(), 0)
    }

    func testUnregisterWaitingReturnsRemovedRegistration() {
        let matcher = RelayMatcher()
        let runtime = registration(.runtime, binding: makeBinding())
        XCTAssertEqual(matcher.register(runtime), .waiting(replaced: nil))

        XCTAssertEqual(matcher.unregisterWaiting(peerID: runtime.id), runtime)
        XCTAssertNil(matcher.unregisterWaiting(peerID: runtime.id))
        XCTAssertEqual(matcher.pendingCount(), 0)
        XCTAssertFalse(matcher.hasWaitingRuntime(relayID: runtime.relayID))
    }

    func testInvalidatesOnlyWaitingRoomWhoseBindingIsNotKept() {
        let matcher = RelayMatcher()
        let oldBinding = makeBinding(generation: 1)
        let currentBinding = makeBinding(generation: 2)
        let runtime = registration(.runtime, binding: oldBinding)
        XCTAssertEqual(matcher.register(runtime), .waiting(replaced: nil))

        XCTAssertEqual(
            matcher.invalidateWaiting(relayID: oldBinding.relayID, keeping: oldBinding),
            []
        )
        XCTAssertEqual(matcher.pendingCount(), 1)
        XCTAssertEqual(
            matcher.invalidateWaiting(relayID: oldBinding.relayID, keeping: currentBinding),
            [runtime]
        )
        XCTAssertEqual(matcher.pendingCount(), 0)
        XCTAssertEqual(
            matcher.invalidateWaiting(relayID: oldBinding.relayID, keeping: currentBinding),
            []
        )
    }

    func testLegacyUnallocatedRegistrationsStillMatchAndReplace() throws {
        let matcher = RelayMatcher()
        let firstRuntime = RelayPeerRegistration(role: .runtime, relayID: "legacy")
        let secondRuntime = RelayPeerRegistration(role: .runtime, relayID: "legacy")
        let allocatedClient = registration(.client, binding: makeBinding(relayID: "legacy"))
        let legacyClient = RelayPeerRegistration(role: .client, relayID: "legacy")

        XCTAssertEqual(matcher.register(firstRuntime), .waiting(replaced: nil))
        XCTAssertEqual(matcher.register(secondRuntime), .waiting(replaced: firstRuntime))
        XCTAssertEqual(matcher.register(allocatedClient), .rejected(.roomBindingMismatch))
        XCTAssertEqual(matcher.waitingRegistrations(relayID: "legacy"), [secondRuntime])
        _ = try matchToken(
            from: matcher.register(legacyClient),
            runtime: secondRuntime,
            client: legacyClient
        )
    }

    func testRuntimeWaitingProbeIgnoresClientsAndActiveRooms() throws {
        let matcher = RelayMatcher()
        let binding = makeBinding()
        let clientOnlyBinding = makeBinding(relayID: "client-only")
        let runtime = registration(.runtime, binding: binding)
        let client = registration(.client, binding: binding)

        XCTAssertEqual(
            matcher.register(registration(.client, binding: clientOnlyBinding)),
            .waiting(replaced: nil)
        )
        XCTAssertFalse(matcher.hasWaitingRuntime(relayID: clientOnlyBinding.relayID))
        XCTAssertEqual(matcher.register(runtime), .waiting(replaced: nil))
        XCTAssertTrue(matcher.hasWaitingRuntime(relayID: binding.relayID))
        _ = try matchToken(from: matcher.register(client), runtime: runtime, client: client)
        XCTAssertFalse(matcher.hasWaitingRuntime(relayID: binding.relayID))
        XCTAssertEqual(matcher.pendingCount(), 1)
        XCTAssertEqual(matcher.activeCount(), 1)
    }

    func testMatchedRegistrationsPreserveCryptoV2Metadata() throws {
        let matcher = RelayMatcher()
        let binding = makeBinding()
        let runtimeNonce = "0123456789abcdef0123456789abcdef"
        let clientNonce = "fedcba9876543210fedcba9876543210"
        let runtimeKey = "04" + String(repeating: "1", count: 128)
        let clientKey = "04" + String(repeating: "2", count: 128)
        let runtime = RelayPeerRegistration(
            role: .runtime,
            relayID: binding.relayID,
            roomBinding: binding,
            sessionNonce: runtimeNonce,
            ephemeralKey: runtimeKey,
            runtimeKeyFingerprint: binding.runtimeKeyFingerprint
        )
        let client = RelayPeerRegistration(
            role: .client,
            relayID: binding.relayID,
            roomBinding: binding,
            sessionNonce: clientNonce,
            ephemeralKey: clientKey
        )

        XCTAssertEqual(matcher.register(runtime), .waiting(replaced: nil))
        let token = try matchToken(from: matcher.register(client), runtime: runtime, client: client)
        let active = try XCTUnwrap(matcher.activeRoom(relayID: binding.relayID))
        XCTAssertEqual(active.matchToken, token)
        XCTAssertEqual(active.roomBinding, binding)
        XCTAssertEqual(active.runtime.sessionNonce, runtimeNonce)
        XCTAssertEqual(active.client.sessionNonce, clientNonce)
        XCTAssertEqual(active.runtime.ephemeralKey, runtimeKey)
        XCTAssertEqual(active.client.ephemeralKey, clientKey)
        XCTAssertEqual(active.runtime.runtimeKeyFingerprint, binding.runtimeKeyFingerprint)
    }

    func testConcurrentRegistrationsMaintainConsistentCounts() {
        let matcher = RelayMatcher()
        let count = 100
        DispatchQueue.concurrentPerform(iterations: count) { index in
            let binding = RelayRoomBinding(
                relayID: "room-\(index)",
                ticketGeneration: 7,
                relayNonce: "relay-nonce",
                runtimeKeyFingerprint: "runtime-owner-a",
                pairedClientKeyFingerprint: "client-owner-a"
            )
            _ = matcher.register(
                RelayPeerRegistration(
                    role: .runtime,
                    relayID: binding.relayID,
                    roomBinding: binding
                )
            )
        }
        XCTAssertEqual(matcher.pendingCount(), count)
        XCTAssertEqual(matcher.activeCount(), 0)

        DispatchQueue.concurrentPerform(iterations: count) { index in
            let binding = RelayRoomBinding(
                relayID: "room-\(index)",
                ticketGeneration: 7,
                relayNonce: "relay-nonce",
                runtimeKeyFingerprint: "runtime-owner-a",
                pairedClientKeyFingerprint: "client-owner-a"
            )
            _ = matcher.register(
                RelayPeerRegistration(
                    role: .client,
                    relayID: binding.relayID,
                    roomBinding: binding
                )
            )
        }
        XCTAssertEqual(matcher.pendingCount(), 0)
        XCTAssertEqual(matcher.activeCount(), count)
    }

    private func makeBinding(
        relayID: String = "shared",
        generation: Int64 = 7,
        relayNonce: String = "relay-nonce",
        runtimeFingerprint: String = "runtime-owner-a",
        pairedClientFingerprint: String? = "client-owner-a"
    ) -> RelayRoomBinding {
        RelayRoomBinding(
            relayID: relayID,
            ticketGeneration: generation,
            relayNonce: relayNonce,
            runtimeKeyFingerprint: runtimeFingerprint,
            pairedClientKeyFingerprint: pairedClientFingerprint
        )
    }

    private func registration(
        _ role: RelayRole,
        binding: RelayRoomBinding,
        identity: RelayAuthenticatedPeerIdentity? = nil
    ) -> RelayPeerRegistration {
        RelayPeerRegistration(
            role: role,
            relayID: binding.relayID,
            roomBinding: binding,
            authenticatedIdentity: identity
        )
    }

    private func authenticatedIdentity(
        _ role: RelayRole,
        digit: Character
    ) -> RelayAuthenticatedPeerIdentity? {
        RelayAuthenticatedPeerIdentity(
            role: role,
            fingerprint: String(repeating: String(digit), count: 64)
        )
    }

    private func sourceIdentity(_ addressText: String) throws -> RelaySourceIdentity {
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        guard inet_pton(AF_INET, addressText, &address.sin_addr) == 1 else {
            throw MatchAssertionError.invalidAddress
        }
        return withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                RelaySourceIdentity(
                    sockaddr: $0,
                    length: socklen_t(MemoryLayout<sockaddr_in>.size)
                )
            }
        }
    }

    private func matchToken(
        from result: RelayRegistrationResult,
        runtime: RelayPeerRegistration,
        client: RelayPeerRegistration,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws -> RelayMatchToken {
        guard case let .matched(matchedRuntime, matchedClient, matchToken) = result else {
            XCTFail("Expected matched result, got \(result)", file: file, line: line)
            throw MatchAssertionError.notMatched
        }
        XCTAssertEqual(matchedRuntime, runtime, file: file, line: line)
        XCTAssertEqual(matchedClient, client, file: file, line: line)
        return matchToken
    }
}

private enum MatchAssertionError: Error {
    case notMatched
    case invalidAddress
}

private final class MatcherWaitingPolicyLogCapture: @unchecked Sendable {
    private let lock = NSLock()
    private var storedMessages: [String] = []

    var messages: [String] {
        lock.lock()
        defer { lock.unlock() }
        return storedMessages
    }

    func append(_ message: String) {
        lock.lock()
        storedMessages.append(message)
        lock.unlock()
    }
}

private final class MatcherPolicyClock: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValue: TimeInterval

    init(now: TimeInterval) {
        storedValue = now
    }

    var value: TimeInterval {
        get {
            lock.lock()
            defer { lock.unlock() }
            return storedValue
        }
        set {
            lock.lock()
            storedValue = newValue
            lock.unlock()
        }
    }
}
