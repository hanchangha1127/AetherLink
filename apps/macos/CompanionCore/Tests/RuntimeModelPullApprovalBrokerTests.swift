import Foundation
@testable import CompanionCore
import CryptoKit
import OllamaBackend
import XCTest

final class RuntimeModelPullApprovalBrokerTests: XCTestCase {
    func testEnqueueCreatesPendingWithoutDispatchAndPersistsRequestedAudit() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)

        let operationID = try await broker.enqueue(intake(digest: digest("a")))

        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 0)
        let reviews = await broker.pendingReviews()
        XCTAssertEqual(reviews.count, 1)
        XCTAssertEqual(reviews.first?.operationID, operationID)
        XCTAssertEqual(reviews.first?.model, "private-model")
        XCTAssertEqual(reviews.first?.provider, .ollama)
        XCTAssertEqual(reviews.first?.requestingDeviceName, "Paired Mac")
        XCTAssertEqual(reviews.first?.requestingDeviceKeyFingerprint, "43:A4:6F:1D:08:1D")
        XCTAssertEqual(reviews.first?.isDispatching, false)
        XCTAssertEqual(
            try fixture.store.recentEvents(limit: 10).map(\.event),
            [.requested]
        )
        let auditEvents = try await broker.recentAuditEvents().map(\.event)
        XCTAssertEqual(auditEvents, [RuntimeModelPullApprovalEvent.requested.rawValue])
    }

    func testAdapterCanonicalizesAndBoundsUnicodeDeviceDisplayNameBeforeCoordinator()
        async throws
    {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let decomposedCluster = "e\u{301}👨‍👩‍👧‍👦"
        let unsafeDisplayName = "\u{202E}\u{2066}\u{200B}"
            + String(repeating: decomposedCluster, count: 128)
            + "\u{2069}\u{2060}"

        _ = try await broker.enqueue(intake(
            digest: digest("0"),
            requestingDeviceName: unsafeDisplayName
        ))

        let pendingReviews = await broker.pendingReviews()
        let review = try XCTUnwrap(pendingReviews.first)
        XCTAssertFalse(review.requestingDeviceName.isEmpty)
        XCTAssertLessThanOrEqual(review.requestingDeviceName.utf8.count, 512)
        XCTAssertEqual(
            review.requestingDeviceName,
            review.requestingDeviceName.precomposedStringWithCanonicalMapping
        )
        XCTAssertFalse(review.requestingDeviceName.unicodeScalars.contains {
            CharacterSet.controlCharacters.contains($0)
                && ![0x200C, 0x200D].contains($0.value)
        })
        XCTAssertTrue(review.requestingDeviceName.contains("é👨‍👩‍👧‍👦"))
        XCTAssertFalse(review.requestingDeviceName.unicodeScalars.contains {
            [0x202E, 0x2066, 0x2069, 0x200B, 0x2060].contains($0.value)
        })
        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 0)
    }

    func testAdapterProjectionIsIdempotentAfterFilteringNormalizationAndBounding() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let source = "e\u{200B}\u{301}"
            + String(repeating: "a", count: 509)
            + " é"

        _ = try await broker.enqueue(intake(
            digest: digest("2"),
            requestingDeviceName: source
        ))

        let reviews = await broker.pendingReviews()
        let projected = try XCTUnwrap(reviews.first?.requestingDeviceName)
        XCTAssertEqual(projected, projected.precomposedStringWithCanonicalMapping)
        XCTAssertEqual(projected, projected.trimmingCharacters(in: .whitespacesAndNewlines))
        XCTAssertLessThanOrEqual(projected.utf8.count, 512)
        XCTAssertEqual(RuntimeApprovalReviewText.canonicalDeviceName(projected), projected)
        XCTAssertTrue(RuntimeApprovalReviewText.isCanonicalDisplayString(projected))

        let joinerBoundarySource = "x"
            + String(repeating: "\u{0300}", count: 253)
            + "aA\u{200D}B"
        let joinerBoundaryProjection = RuntimeApprovalReviewText.canonicalDeviceName(
            joinerBoundarySource
        )
        XCTAssertEqual(joinerBoundarySource.utf8.count, 513)
        XCTAssertLessThanOrEqual(joinerBoundaryProjection.utf8.count, 512)
        XCTAssertFalse(joinerBoundaryProjection.unicodeScalars.contains { $0.value == 0x200D })
        XCTAssertEqual(
            RuntimeApprovalReviewText.canonicalDeviceName(joinerBoundaryProjection),
            joinerBoundaryProjection
        )
        XCTAssertTrue(RuntimeApprovalReviewText.isCanonicalDisplayString(joinerBoundaryProjection))

        let nonRGITagRun = "🏴"
            + String(repeating: "\u{E0061}", count: 10_000)
            + "\u{E007F}"
        let tagRunStartedAt = ProcessInfo.processInfo.systemUptime
        let tagRunProjection = RuntimeApprovalReviewText.canonicalDeviceName(nonRGITagRun)
        let tagRunDuration = ProcessInfo.processInfo.systemUptime - tagRunStartedAt
        XCTAssertEqual(tagRunProjection, "🏴")
        XCTAssertLessThan(tagRunDuration, 2.0)
        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 0)
    }

    func testAdapterPreservesContextualUnicodeAndDropsNoncontextualSuffixes() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let persian = "می\u{200C}خواهم"
        let emoji = "👨‍👩‍👧‍👦 ❤️"
        let indicZWNJ = "क्\u{200C}ष"
        let indicZWJ = "क्\u{200D}ष"
        let ideographicVariation = "漢\u{E0100}"
        let subdivisionFlags = [
            "🏴\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}",
            "🏴\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}",
            "🏴\u{E0067}\u{E0062}\u{E0077}\u{E006C}\u{E0073}\u{E007F}",
        ]
        let invalidEmojiTag = "😀\u{E0061}\u{E007F}"
        let source = "\(persian) \(emoji) \(indicZWNJ) \(indicZWJ)"
            + " \(ideographicVariation) \(subdivisionFlags.joined(separator: " "))"
            + " A\u{200D}B C\u{200C}D \(invalidEmojiTag)"
            + " Mac\u{200D} PC\u{200C} Text\u{FE0F}"

        _ = try await broker.enqueue(intake(
            digest: digest("3"),
            requestingDeviceName: source
        ))

        let reviews = await broker.pendingReviews()
        let projected = try XCTUnwrap(reviews.first?.requestingDeviceName)
        XCTAssertTrue(projected.contains(persian))
        XCTAssertTrue(projected.contains(emoji))
        XCTAssertTrue(projected.contains(indicZWNJ))
        XCTAssertTrue(projected.contains(indicZWJ))
        XCTAssertTrue(projected.contains(ideographicVariation))
        for subdivisionFlag in subdivisionFlags {
            XCTAssertTrue(projected.contains(subdivisionFlag))
        }
        XCTAssertTrue(projected.contains("AB CD 😀"))
        XCTAssertFalse(projected.unicodeScalars.contains { $0.value == 0xE0061 })
        XCTAssertTrue(projected.contains("Mac PC Text"))
        XCTAssertFalse(projected.contains("Mac\u{200D}"))
        XCTAssertFalse(projected.contains("PC\u{200C}"))
        XCTAssertFalse(projected.contains("Text\u{FE0F}"))
        XCTAssertEqual(RuntimeApprovalReviewText.canonicalDeviceName(projected), projected)
        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 0)
    }

    func testAdapterFallsBackForInvisibleOnlyDeviceDisplayNameBeforeCoordinator() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)

        _ = try await broker.enqueue(intake(
            digest: digest("1"),
            requestingDeviceName: "\u{200B}\u{2060}\u{FEFF}\u{2800}"
        ))

        let pendingReviews = await broker.pendingReviews()
        let review = try XCTUnwrap(pendingReviews.first)
        XCTAssertEqual(review.requestingDeviceName, "Trusted device")
        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 0)
    }

    func testApproveAuthorizesAndReservesBeforeSingleProviderDispatchThenPublishesSuccess() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let order = LockedRecorder<String>()
        let outcomes = LockedRecorder<RuntimeModelPullDispatchOutcome>()
        let dispatcher = MockModelPullDispatcher { model in
            order.append("provider")
            return ModelPullResult(model: model, status: "downloaded", installed: true)
        }
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let request = intake(
            digest: digest("b"),
            authorizeAndClaimDispatch: { reservation in
                order.append("authorize")
                let receipt = try reservation()
                order.append("reserved")
                return receipt
            },
            prepareOutcomePublication: { outcome in
                return { terminalCommit in
                    try terminalCommit()
                    order.append("terminal")
                    order.append("publish")
                    outcomes.append(outcome)
                }
            }
        )
        let operationID = try await broker.enqueue(request)

        try await broker.approve(operationID: operationID)

        XCTAssertEqual(
            order.values,
            ["authorize", "reserved", "provider", "terminal", "publish"]
        )
        let dispatchCallCount = await dispatcher.callCount()
        let pulledModels = await dispatcher.pulledModels()
        XCTAssertEqual(dispatchCallCount, 1)
        XCTAssertEqual(pulledModels, ["private-model"])
        XCTAssertEqual(
            outcomes.values,
            [.success]
        )
        XCTAssertEqual(
            try fixture.store.recentEvents(limit: 10).map(\.event),
            [.success, .dispatchReserved, .requested]
        )
        let remainingReviews = await broker.pendingReviews()
        XCTAssertTrue(remainingReviews.isEmpty)
    }

    func testConcurrentApproveDispatchesProviderExactlyOnce() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let gate = AsyncGate()
        let dispatcher = MockModelPullDispatcher { model in
            await gate.wait()
            return ModelPullResult(model: model, status: "downloaded", installed: true)
        }
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let operationID = try await broker.enqueue(intake(digest: digest("c")))

        let firstApproval = Task {
            try await broker.approve(operationID: operationID)
        }
        try await waitForCallCount(1, dispatcher: dispatcher)

        do {
            try await broker.approve(operationID: operationID)
            XCTFail("A concurrent approval should be rejected")
        } catch {
            assertBrokerError(error, is: .decisionInFlight)
        }

        await gate.open()
        try await firstApproval.value
        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 1)
        XCTAssertEqual(
            try fixture.store.recentEvents(limit: 10).map(\.event),
            [.success, .dispatchReserved, .requested]
        )
    }

    func testReservationAndAuthenticationFailuresNeverDispatchAndAuthenticationChangeTerminalizes() async throws {
        let reservationFixture = try StoreFixture()
        defer { reservationFixture.remove() }
        let reservationDispatcher = MockModelPullDispatcher()
        let reservationBroker = makeBroker(
            dispatcher: reservationDispatcher,
            store: reservationFixture.store
        )
        let reservationDigest = digest("d")
        let reservationIntake = intake(digest: reservationDigest)
        let reservationOperationID = try await reservationBroker.enqueue(
            reservationIntake
        )
        _ = try reservationFixture.store.reserveDispatch(
            operationID: reservationOperationID,
            requestBindingDigest: reservationIntake.permissionClaim.requestBindingDigest,
            at: date(100)
        )

        do {
            try await reservationBroker.approve(operationID: reservationOperationID)
            XCTFail("A failed durable reservation should reject approval")
        } catch {
            assertBrokerError(error, is: .storageUnavailable)
        }
        let reservationDispatchCallCount = await reservationDispatcher.callCount()
        XCTAssertEqual(reservationDispatchCallCount, 0)
        XCTAssertEqual(
            try reservationFixture.store.recentEvents(limit: 10).map(\.event),
            [.dispatchReserved, .requested]
        )
        let reservationReviews = await reservationBroker.pendingReviews()
        XCTAssertTrue(reservationReviews.isEmpty)
        do {
            _ = try await reservationBroker.enqueue(intake(digest: digest("u")))
            XCTFail("An ambiguous reservation failure must block new intake")
        } catch {
            assertBrokerError(error, is: .storageUnavailable)
        }
        try await reservationBroker.recoverUnfinished()
        XCTAssertEqual(
            try reservationFixture.store.record(
                operationID: reservationOperationID
            )?.currentEvent,
            .resultSuppressed
        )

        let authenticationFixture = try StoreFixture()
        defer { authenticationFixture.remove() }
        let authenticationDispatcher = MockModelPullDispatcher()
        let authenticationBroker = makeBroker(
            dispatcher: authenticationDispatcher,
            store: authenticationFixture.store
        )
        let authenticationOperationID = try await authenticationBroker.enqueue(intake(
            digest: digest("e"),
            authorizeAndClaimDispatch: { _ in
                throw RuntimeModelPullApprovalAuthorityError.authenticationChanged
            }
        ))

        do {
            try await authenticationBroker.approve(operationID: authenticationOperationID)
            XCTFail("Changed authentication should reject approval")
        } catch {
            assertBrokerError(error, is: .authenticationChanged)
        }
        let authenticationDispatchCallCount = await authenticationDispatcher.callCount()
        XCTAssertEqual(authenticationDispatchCallCount, 0)
        XCTAssertEqual(
            try authenticationFixture.store.recentEvents(limit: 10).map(\.event),
            [.authenticationChanged, .requested]
        )
        let authenticationReviews = await authenticationBroker.pendingReviews()
        XCTAssertTrue(authenticationReviews.isEmpty)
    }

    func testDismissExpiryAndConnectionCancellationNeverDispatchAndPersistTerminalEvents() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let clock = TestClock(date(100))
        let dispatcher = MockModelPullDispatcher()
        let dismissedPublication = LockedRecorder<Bool>()
        let expiredPublication = LockedRecorder<Bool>()
        let cancelledPublication = LockedRecorder<Bool>()
        let broker = makeBroker(
            dispatcher: dispatcher,
            store: fixture.store,
            approvalTTL: 10,
            now: { clock.now() }
        )
        let dismissedID = try await broker.enqueue(intake(
            digest: digest("f"),
            publishApprovalRequired: {
                dismissedPublication.append(true)
                return true
            }
        ))
        let cancelledConnectionID = UUID()
        let cancelledID = try await broker.enqueue(intake(
            digest: digest("1"),
            connectionID: cancelledConnectionID,
            publishApprovalRequired: {
                cancelledPublication.append(true)
                return true
            }
        ))
        let expiredID = try await broker.enqueue(intake(
            digest: digest("2"),
            publishApprovalRequired: {
                expiredPublication.append(true)
                return true
            }
        ))

        try await broker.dismiss(operationID: dismissedID)
        await broker.cancel(connectionID: cancelledConnectionID)
        clock.set(date(110))
        do {
            try await broker.approve(operationID: expiredID)
            XCTFail("An expired review should not dispatch")
        } catch {
            assertBrokerError(error, is: .reviewNotFound)
        }

        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 0)
        XCTAssertEqual(try fixture.store.record(operationID: dismissedID)?.currentEvent, .dismissal)
        XCTAssertEqual(try fixture.store.record(operationID: cancelledID)?.currentEvent, .connectionClosed)
        XCTAssertEqual(try fixture.store.record(operationID: expiredID)?.currentEvent, .expiry)
        XCTAssertEqual(dismissedPublication.values, [true])
        XCTAssertEqual(expiredPublication.values, [true])
        XCTAssertTrue(cancelledPublication.values.isEmpty)
        let remainingReviews = await broker.pendingReviews()
        XCTAssertTrue(remainingReviews.isEmpty)
    }

    func testProviderFailurePublishesOnlyRedactedWireFailureAndPersistsFailure() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let secret = "provider-secret-stack-detail"
        let outcomes = LockedRecorder<RuntimeModelPullDispatchOutcome>()
        let dispatcher = MockModelPullDispatcher { _ in
            throw SecretProviderFailure(detail: secret)
        }
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let operationID = try await broker.enqueue(intake(
            digest: digest("3"),
            prepareOutcomePublication: { outcome in
                return { terminalCommit in
                    try terminalCommit()
                    outcomes.append(outcome)
                }
            }
        ))

        try await broker.approve(operationID: operationID)

        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 1)
        guard case .failure(let failure) = try XCTUnwrap(outcomes.values.first) else {
            return XCTFail("Expected a redacted failure outcome")
        }
        XCTAssertEqual(failure.code, "backend_unavailable")
        XCTAssertEqual(failure.message, "The runtime host could not download the requested model.")
        XCTAssertTrue(failure.retryable)
        XCTAssertFalse(failure.message.contains(secret))
        XCTAssertEqual(try fixture.store.record(operationID: operationID)?.currentEvent, .failure)
    }

    func testPublicationAuthorityLossPersistsResultSuppressed() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let outcomes = LockedRecorder<RuntimeModelPullDispatchOutcome>()
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let operationID = try await broker.enqueue(intake(
            digest: digest("4"),
            prepareOutcomePublication: { outcome in
                outcomes.append(outcome)
                throw RuntimeModelPullApprovalAuthorityError.authenticationChanged
            }
        ))

        try await broker.approve(operationID: operationID)

        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 1)
        XCTAssertEqual(outcomes.values.count, 1)
        XCTAssertEqual(
            try fixture.store.recentEvents(limit: 10).map(\.event),
            [.resultSuppressed, .dispatchReserved, .requested]
        )
    }

    func testTerminalWriteFailurePreventsWirePublicationAndRecordsSuppression() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let persistence = RecordingRuntimeModelPullBrokerPersistence(
            store: fixture.store,
            failingTerminalEvents: [.dispatchSucceeded]
        )
        let dispatcher = MockModelPullDispatcher()
        let publications = LockedRecorder<RuntimeModelPullDispatchOutcome>()
        let broker = RuntimeModelPullApprovalBroker(
            dispatcher: dispatcher,
            persistence: persistence,
            now: { self.date(100) }
        )
        let operationID = try await broker.enqueue(intake(
            digest: digest("7"),
            prepareOutcomePublication: { outcome in
                return { terminalCommit in
                    try terminalCommit()
                    publications.append(outcome)
                }
            }
        ))

        do {
            try await broker.approve(operationID: operationID)
            XCTFail("A terminal audit failure must suppress wire publication")
        } catch {
            assertBrokerError(error, is: .storageUnavailable)
        }

        let dispatchCallCount = await dispatcher.callCount()
        let pendingReviews = await broker.pendingReviews()
        XCTAssertEqual(dispatchCallCount, 1)
        XCTAssertTrue(publications.values.isEmpty)
        XCTAssertEqual(
            try fixture.store.recentEvents(limit: 10).map(\.event),
            [.resultSuppressed, .dispatchReserved, .requested]
        )
        XCTAssertTrue(pendingReviews.isEmpty)
    }

    func testTerminalAndSuppressionAuditFailureBlocksIntakeUntilRecovery() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let persistence = RecordingRuntimeModelPullBrokerPersistence(
            store: fixture.store,
            failingTerminalEvents: [.dispatchSucceeded, .resultSuppressed]
        )
        let dispatcher = MockModelPullDispatcher()
        let publications = LockedRecorder<RuntimeModelPullDispatchOutcome>()
        let broker = RuntimeModelPullApprovalBroker(
            dispatcher: dispatcher,
            persistence: persistence,
            now: { self.date(100) }
        )
        let operationID = try await broker.enqueue(intake(
            digest: digest("u"),
            prepareOutcomePublication: { outcome in
                return { terminalCommit in
                    try terminalCommit()
                    publications.append(outcome)
                }
            }
        ))

        do {
            try await broker.approve(operationID: operationID)
            XCTFail("Ambiguous terminal audit state must fail closed")
        } catch {
            assertBrokerError(error, is: .storageUnavailable)
        }
        XCTAssertTrue(publications.values.isEmpty)
        XCTAssertEqual(
            try fixture.store.record(operationID: operationID)?.currentEvent,
            .dispatchReserved
        )
        do {
            _ = try await broker.enqueue(intake(digest: digest("v")))
            XCTFail("Storage-degraded broker must block new intake")
        } catch {
            assertBrokerError(error, is: .storageUnavailable)
        }

        try await broker.recoverUnfinished()
        XCTAssertEqual(
            try fixture.store.record(operationID: operationID)?.currentEvent,
            .resultSuppressed
        )
        _ = try await broker.enqueue(intake(digest: digest("w")))
    }

    func testSuccessfulInitializationRecoveryIsNotRepeatedAfterNewIntake() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let persistence = RecordingRuntimeModelPullBrokerPersistence(store: fixture.store)
        let dispatcher = MockModelPullDispatcher()
        let broker = RuntimeModelPullApprovalBroker(
            dispatcher: dispatcher,
            persistence: persistence,
            now: { self.date(100) }
        )
        let operationID = try await broker.enqueue(intake(digest: digest("8")))

        try await broker.recoverUnfinished()

        XCTAssertEqual(persistence.recoveryCallCount, 1)
        XCTAssertEqual(
            try fixture.store.record(operationID: operationID)?.currentEvent,
            .requested
        )
        let pendingOperationIDs = await broker.pendingReviews().map(\.operationID)
        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(pendingOperationIDs, [operationID])
        XCTAssertEqual(dispatchCallCount, 0)
    }

    func testApprovalCrossingExpiryTerminalizesWithoutDispatchOrPendingLeak() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let clock = TestClock(date(100))
        let dispatcher = MockModelPullDispatcher()
        let approvalRequiredPublications = LockedRecorder<Bool>()
        let broker = makeBroker(
            dispatcher: dispatcher,
            store: fixture.store,
            approvalTTL: 10,
            now: { clock.now() }
        )
        let operationID = try await broker.enqueue(intake(
            digest: digest("9"),
            authorizeAndClaimDispatch: { reservation in
                clock.set(self.date(110))
                return try reservation()
            },
            publishApprovalRequired: {
                approvalRequiredPublications.append(true)
                return true
            }
        ))

        do {
            try await broker.approve(operationID: operationID)
            XCTFail("A review that expires during authorization must not dispatch")
        } catch {
            assertBrokerError(error, is: .reviewNotFound)
        }

        let dispatchCallCount = await dispatcher.callCount()
        let pendingReviews = await broker.pendingReviews()
        XCTAssertEqual(dispatchCallCount, 0)
        XCTAssertTrue(pendingReviews.isEmpty)
        XCTAssertEqual(approvalRequiredPublications.values, [true])
        XCTAssertEqual(try fixture.store.record(operationID: operationID)?.currentEvent, .expiry)
    }

    func testAuthorityDelayCrossingMonotonicTTLWithWallRollbackExpiresBeforeDispatch() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let wallClock = TestClock(date(100))
        let monotonicClock = TestMonotonicClock(100)
        let dispatcher = MockModelPullDispatcher()
        let broker = RuntimeModelPullApprovalBroker(
            dispatcher: dispatcher,
            persistence: fixture.store,
            approvalTTL: 10,
            now: { wallClock.now() },
            monotonicNow: { monotonicClock.now() }
        )
        let operationID = try await broker.enqueue(intake(
            digest: digest("m"),
            authorizeAndClaimDispatch: { reservation in
                wallClock.set(self.date(50))
                monotonicClock.set(110)
                return try reservation()
            }
        ))

        do {
            try await broker.approve(operationID: operationID)
            XCTFail("Monotonic expiry during authority validation must prevent dispatch")
        } catch {
            assertBrokerError(error, is: .reviewNotFound)
        }

        let dispatchCount = await dispatcher.callCount()
        let pendingReviews = await broker.pendingReviews()
        XCTAssertEqual(dispatchCount, 0)
        XCTAssertTrue(pendingReviews.isEmpty)
        XCTAssertEqual(
            try fixture.store.record(operationID: operationID)?.currentEvent,
            .expiry
        )
    }

    func testDuplicateRequestBindingRejectsReplayWithoutPoisoningBroker() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let connectionID = UUID()

        let firstOperationID = try await broker.enqueue(intake(
            digest: digest("n"),
            connectionID: connectionID
        ))
        do {
            _ = try await broker.enqueue(intake(
                digest: digest("n"),
                connectionID: connectionID
            ))
            XCTFail("An authenticated request binding replay must be rejected")
        } catch {
            assertBrokerError(error, is: .unavailable)
        }
        let laterOperationID = try await broker.enqueue(intake(
            digest: digest("o"),
            connectionID: connectionID
        ))

        let pendingOperationIDs = Set(await broker.pendingReviews().map(\.operationID))
        let dispatchCount = await dispatcher.callCount()
        XCTAssertEqual(pendingOperationIDs, [firstOperationID, laterOperationID])
        XCTAssertEqual(dispatchCount, 0)
    }

    func testRecoveryTerminalizesPendingAndReservedWithoutProviderRetry() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let pendingID = "00000000-0000-0000-0000-000000000001"
        let reservedID = "00000000-0000-0000-0000-000000000002"
        _ = try fixture.store.createRequest(
            operationID: pendingID,
            requestBindingDigest: digest("5"),
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(200)
        )
        _ = try fixture.store.createRequest(
            operationID: reservedID,
            requestBindingDigest: digest("6"),
            provider: .ollama,
            requestedAt: date(100),
            expiresAt: date(200)
        )
        _ = try fixture.store.reserveDispatch(
            operationID: reservedID,
            requestBindingDigest: digest("6"),
            at: date(110)
        )
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(
            dispatcher: dispatcher,
            store: fixture.store,
            now: { self.date(120) }
        )

        try await broker.recoverUnfinished()

        let dispatchCallCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCallCount, 0)
        XCTAssertEqual(try fixture.store.record(operationID: pendingID)?.currentEvent, .hostRestarted)
        XCTAssertEqual(try fixture.store.record(operationID: reservedID)?.currentEvent, .resultSuppressed)
        XCTAssertEqual(
            try fixture.store.recentEvents(limit: 10).filter {
                $0.operationID == pendingID
            }.map(\.event),
            [.hostRestarted, .requested]
        )
        XCTAssertEqual(
            try fixture.store.recentEvents(limit: 10).filter {
                $0.operationID == reservedID
            }.map(\.event),
            [.resultSuppressed, .dispatchReserved, .requested]
        )
    }

    func testBrokerRejectsUnregisteredPermissionClaimBeforeAuditOrDispatch() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let alternateManifest = permissionManifest(actionID: "alternate_install_v1")
        let alternateRegistry = try RuntimePermissionPolicyRegistry(
            manifests: [alternateManifest]
        )
        let claim = try alternateRegistry.claim(
            actionID: alternateManifest.actionID,
            expectedRevision: alternateManifest.revision,
            authority: permissionAuthority(requestID: "alternate-request"),
            resourceKind: "ollama_model",
            resourceValue: "private-model"
        )
        let request = RuntimeModelPullApprovalIntake(
            permissionClaim: claim,
            connectionID: UUID(),
            model: "private-model",
            provider: .ollama,
            requestingDeviceName: "Paired Mac",
            authorizeAndClaimDispatch: { reservation in try reservation() },
            prepareOutcomePublication: { _ in
                { terminalCommit in try terminalCommit() }
            },
            publishApprovalRequired: { true }
        )

        do {
            _ = try await broker.enqueue(request)
            XCTFail("An unregistered permission action must be rejected")
        } catch {
            assertBrokerError(error, is: .unavailable)
        }
        XCTAssertTrue(try fixture.store.recentEvents(limit: 10).isEmpty)
        let dispatchCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCount, 0)
    }

    func testBrokerRejectsClaimWhoseConnectionOrModelDiffersFromIntake() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)

        let claimedConnectionID = UUID()
        var connectionMismatch = intake(
            digest: digest("x"),
            connectionID: claimedConnectionID
        )
        connectionMismatch.connectionID = UUID()
        do {
            _ = try await broker.enqueue(connectionMismatch)
            XCTFail("A claim bound to another connection must be rejected")
        } catch {
            assertBrokerError(error, is: .unavailable)
        }

        let modelConnectionID = UUID()
        let modelAuthority = RuntimePermissionAuthorityBinding(
            connectionID: modelConnectionID,
            requestID: "model-parity-request",
            authenticationGeneration: 1,
            deviceID: "device-1",
            publicKeyBase64: "cHVibGljLWtleQ==",
            transportBinding: String(repeating: "a", count: 64)
        )
        var modelMismatch = intake(
            digest: digest("y"),
            connectionID: modelConnectionID
        )
        modelMismatch.permissionClaim = try RuntimePermissionPolicyRegistry.bundled.claim(
            actionID: RuntimePermissionPolicyRegistry.modelPullActionID,
            expectedRevision: RuntimePermissionPolicyRegistry.modelPullRevision,
            authority: modelAuthority,
            resourceKind: RuntimePermissionPolicyRegistry.modelPullResourceKind,
            resourceValue: "approved-model"
        )
        modelMismatch.model = "different-model"
        do {
            _ = try await broker.enqueue(modelMismatch)
            XCTFail("A claim bound to another model must be rejected")
        } catch {
            assertBrokerError(error, is: .unavailable)
        }

        XCTAssertTrue(try fixture.store.recentEvents(limit: 10).isEmpty)
        let dispatchCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCount, 0)
    }

    func testPermissionChangeDuringApprovalTerminalizesWithoutDispatch() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let dispatcher = MockModelPullDispatcher()
        let broker = makeBroker(dispatcher: dispatcher, store: fixture.store)
        let operationID = try await broker.enqueue(intake(
            digest: digest("p"),
            authorizeAndClaimDispatch: { _ in
                throw RuntimeModelPullApprovalAuthorityError.permissionChanged
            }
        ))

        do {
            try await broker.approve(operationID: operationID)
            XCTFail("A changed permission policy must reject approval")
        } catch {
            assertBrokerError(error, is: .permissionChanged)
        }
        let dispatchCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCount, 0)
        XCTAssertEqual(
            try fixture.store.recentEvents(limit: 10).map(\.event),
            [.permissionChanged, .requested]
        )
        let pendingReviews = await broker.pendingReviews()
        XCTAssertTrue(pendingReviews.isEmpty)
    }

    func testCancellationAuditFailureBlocksIntakeUntilRecovery() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let persistence = RecordingRuntimeModelPullBrokerPersistence(
            store: fixture.store,
            failingTerminalEvents: [.connectionClosed]
        )
        let dispatcher = MockModelPullDispatcher()
        let broker = RuntimeModelPullApprovalBroker(
            dispatcher: dispatcher,
            persistence: persistence,
            now: { self.date(100) },
            monotonicNow: { 100 }
        )
        let connectionID = UUID()
        let operationID = try await broker.enqueue(intake(
            digest: digest("q"),
            connectionID: connectionID
        ))

        await broker.cancel(connectionID: connectionID)
        let pendingReviews = await broker.pendingReviews()
        XCTAssertTrue(pendingReviews.isEmpty)
        XCTAssertEqual(
            try fixture.store.record(operationID: operationID)?.currentEvent,
            .requested
        )
        do {
            _ = try await broker.enqueue(intake(digest: digest("r")))
            XCTFail("Storage-degraded broker must block new intake")
        } catch {
            assertBrokerError(error, is: .storageUnavailable)
        }

        try await broker.recoverUnfinished()
        XCTAssertEqual(
            try fixture.store.record(operationID: operationID)?.currentEvent,
            .hostRestarted
        )
        _ = try await broker.enqueue(intake(digest: digest("s")))
        let dispatchCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCount, 0)
    }

    func testWallClockRollbackCannotExtendMonotonicApprovalTTL() async throws {
        let fixture = try StoreFixture()
        defer { fixture.remove() }
        let wallClock = TestClock(date(100))
        let monotonicClock = TestMonotonicClock(100)
        let dispatcher = MockModelPullDispatcher()
        let broker = RuntimeModelPullApprovalBroker(
            dispatcher: dispatcher,
            persistence: fixture.store,
            approvalTTL: 10,
            now: { wallClock.now() },
            monotonicNow: { monotonicClock.now() }
        )
        let operationID = try await broker.enqueue(intake(digest: digest("t")))
        wallClock.set(date(50))
        monotonicClock.set(110)

        do {
            try await broker.approve(operationID: operationID)
            XCTFail("Monotonic expiry must win over a rolled-back wall clock")
        } catch {
            assertBrokerError(error, is: .reviewNotFound)
        }
        let dispatchCount = await dispatcher.callCount()
        XCTAssertEqual(dispatchCount, 0)
        XCTAssertEqual(
            try fixture.store.record(operationID: operationID)?.currentEvent,
            .expiry
        )
    }

    private func makeBroker(
        dispatcher: any ModelPullDispatching,
        store: SQLiteRuntimeModelPullApprovalStore,
        approvalTTL: TimeInterval = 60,
        now: @escaping @Sendable () -> Date = { Date(timeIntervalSince1970: 100) }
    ) -> RuntimeModelPullApprovalBroker {
        RuntimeModelPullApprovalBroker(
            dispatcher: dispatcher,
            persistence: store,
            approvalTTL: approvalTTL,
            now: now
        )
    }

    private func intake(
        digest: String,
        connectionID: UUID = UUID(),
        requestingDeviceName: String = "Paired Mac",
        authorizeAndClaimDispatch: @escaping @Sendable (
            @escaping RuntimeModelPullReservation
        ) async throws -> RuntimeModelPullReservationReceipt = { reservation in
            try reservation()
        },
        prepareOutcomePublication: @escaping @Sendable (
            RuntimeModelPullDispatchOutcome
        ) async throws -> RuntimeModelPullOutcomePublication = { _ in
            { terminalCommit in try terminalCommit() }
        },
        publishApprovalRequired: @escaping @Sendable () async -> Bool = { true }
    ) -> RuntimeModelPullApprovalIntake {
        let permissionClaim = try! RuntimePermissionPolicyRegistry.bundled.claim(
            actionID: RuntimePermissionPolicyRegistry.modelPullActionID,
            expectedRevision: RuntimePermissionPolicyRegistry.modelPullRevision,
            authority: RuntimePermissionAuthorityBinding(
                connectionID: connectionID,
                requestID: digest,
                authenticationGeneration: 1,
                deviceID: "device-1",
                publicKeyBase64: "cHVibGljLWtleQ==",
                transportBinding: String(repeating: "a", count: 64)
            ),
            resourceKind: "ollama_model",
            resourceValue: "private-model"
        )
        return RuntimeModelPullApprovalIntake(
            permissionClaim: permissionClaim,
            connectionID: connectionID,
            model: "private-model",
            provider: .ollama,
            requestingDeviceName: requestingDeviceName,
            authorizeAndClaimDispatch: authorizeAndClaimDispatch,
            prepareOutcomePublication: prepareOutcomePublication,
            publishApprovalRequired: publishApprovalRequired
        )
    }

    private func digest(_ character: Character) -> String {
        SQLiteRuntimeModelPullApprovalStore.requestBindingDigestPrefix
            + String(repeating: String(character), count: 64)
    }

    private func permissionManifest(actionID: String) -> RuntimePermissionPolicyManifest {
        RuntimePermissionPolicyManifest(
            actionID: actionID,
            revision: RuntimePermissionPolicyRegistry.computedRevision(
                actionID: actionID,
                effect: .providerArtifactInstall,
                decision: .hostExplicitApproval,
                audit: .durableRedactedRequired
            ),
            effect: RuntimePermissionEffect.providerArtifactInstall.rawValue,
            decision: RuntimePermissionDecision.hostExplicitApproval.rawValue,
            audit: RuntimePermissionAuditRequirement.durableRedactedRequired.rawValue
        )
    }

    private func permissionAuthority(
        requestID: String
    ) -> RuntimePermissionAuthorityBinding {
        RuntimePermissionAuthorityBinding(
            connectionID: UUID(),
            requestID: requestID,
            authenticationGeneration: 1,
            deviceID: "device-1",
            publicKeyBase64: "cHVibGljLWtleQ==",
            transportBinding: String(repeating: "a", count: 64)
        )
    }

    private func date(_ seconds: TimeInterval) -> Date {
        Date(timeIntervalSince1970: seconds)
    }

    private func waitForCallCount(
        _ expected: Int,
        dispatcher: MockModelPullDispatcher
    ) async throws {
        for _ in 0..<10_000 {
            if await dispatcher.callCount() == expected {
                return
            }
            await Task.yield()
        }
        throw TestFailure.timedOut
    }

    private func assertBrokerError(
        _ error: Error,
        is expected: RuntimeModelPullApprovalBrokerError,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        guard let actual = error as? RuntimeModelPullApprovalBrokerError else {
            return XCTFail("Unexpected error: \(error)", file: file, line: line)
        }
        let matches: Bool
        switch (actual, expected) {
        case (.unavailable, .unavailable),
             (.queueFull, .queueFull),
             (.reviewNotFound, .reviewNotFound),
             (.decisionInFlight, .decisionInFlight),
             (.storageUnavailable, .storageUnavailable),
             (.authenticationChanged, .authenticationChanged),
             (.permissionChanged, .permissionChanged):
            matches = true
        default:
            matches = false
        }
        XCTAssertTrue(matches, "Expected \(expected), got \(actual)", file: file, line: line)
    }
}

private struct StoreFixture {
    let directoryURL: URL
    let store: SQLiteRuntimeModelPullApprovalStore

    init() throws {
        directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("RuntimeModelPullApprovalBrokerTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(
            at: directoryURL,
            withIntermediateDirectories: true
        )
        store = SQLiteRuntimeModelPullApprovalStore(
            databaseURL: directoryURL.appendingPathComponent("approvals.sqlite")
        )
    }

    func remove() {
        try? FileManager.default.removeItem(at: directoryURL)
    }
}

private final class RecordingRuntimeModelPullBrokerPersistence:
    RuntimeModelPullBrokerPersistence,
    @unchecked Sendable
{
    private let store: SQLiteRuntimeModelPullApprovalStore
    private let failingTerminalEvents: [RuntimeModelPullPersistenceEventKind]
    private let lock = NSLock()
    private var storedRecoveryCallCount = 0

    init(
        store: SQLiteRuntimeModelPullApprovalStore,
        failingTerminalEvents: [RuntimeModelPullPersistenceEventKind] = []
    ) {
        self.store = store
        self.failingTerminalEvents = failingTerminalEvents
    }

    var recoveryCallCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return storedRecoveryCallCount
    }

    func createPending(
        operationID: String,
        requestBindingDigest: String,
        provider: ModelProvider,
        actionID: String,
        policyRevision: String,
        requestedAt: Date,
        expiresAt: Date
    ) throws {
        try store.createPending(
            operationID: operationID,
            requestBindingDigest: requestBindingDigest,
            provider: provider,
            actionID: actionID,
            policyRevision: policyRevision,
            requestedAt: requestedAt,
            expiresAt: expiresAt
        )
    }

    func reserveDispatchBeforeProvider(
        operationID: String,
        requestBindingDigest: String,
        at: Date
    ) throws -> RuntimeModelPullReservationPersistenceResult {
        try store.reserveDispatchBeforeProvider(
            operationID: operationID,
            requestBindingDigest: requestBindingDigest,
            at: at
        )
    }

    func recordTerminal(
        operationID: String,
        event: RuntimeModelPullPersistenceEventKind,
        at: Date
    ) throws -> RuntimeModelPullTerminalPersistenceResult {
        if failingTerminalEvents.contains(event) {
            throw SecretProviderFailure(detail: "injected terminal write failure")
        }
        return try store.recordTerminal(operationID: operationID, event: event, at: at)
    }

    func recoverUnfinishedApprovals(at: Date) throws {
        lock.lock()
        storedRecoveryCallCount += 1
        lock.unlock()
        try store.recoverUnfinishedApprovals(at: at)
    }

    func recentAuditEvents(limit: Int) throws -> [RuntimeModelPullAuditSummary] {
        try store.recentAuditEvents(limit: limit)
    }
}

private actor MockModelPullDispatcher: ModelPullDispatching {
    typealias Behavior = @Sendable (String) async throws -> ModelPullResult

    private let behavior: Behavior
    private var models: [String] = []

    init(behavior: @escaping Behavior = { model in
        ModelPullResult(model: model, status: "downloaded", installed: true)
    }) {
        self.behavior = behavior
    }

    func pullModel(name: String) async throws -> ModelPullResult {
        models.append(name)
        return try await behavior(name)
    }

    func callCount() -> Int {
        models.count
    }

    func pulledModels() -> [String] {
        models
    }
}

private actor AsyncGate {
    private var isOpen = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    func wait() async {
        guard !isOpen else { return }
        await withCheckedContinuation { continuation in
            waiters.append(continuation)
        }
    }

    func open() {
        isOpen = true
        let continuations = waiters
        waiters.removeAll()
        continuations.forEach { $0.resume() }
    }
}

private final class LockedRecorder<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValues: [Value] = []

    var values: [Value] {
        lock.lock()
        defer { lock.unlock() }
        return storedValues
    }

    func append(_ value: Value) {
        lock.lock()
        storedValues.append(value)
        lock.unlock()
    }
}

private final class TestClock: @unchecked Sendable {
    private let lock = NSLock()
    private var currentDate: Date

    init(_ currentDate: Date) {
        self.currentDate = currentDate
    }

    func now() -> Date {
        lock.lock()
        defer { lock.unlock() }
        return currentDate
    }

    func set(_ date: Date) {
        lock.lock()
        currentDate = date
        lock.unlock()
    }
}

private final class TestMonotonicClock: @unchecked Sendable {
    private let lock = NSLock()
    private var value: TimeInterval

    init(_ value: TimeInterval) {
        self.value = value
    }

    func now() -> TimeInterval {
        lock.withLock { value }
    }

    func set(_ value: TimeInterval) {
        lock.withLock { self.value = value }
    }
}

private struct SecretProviderFailure: Error, Sendable {
    let detail: String
}

private enum TestFailure: Error {
    case timedOut
}
