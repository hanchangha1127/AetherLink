import Darwin
import BridgeProtocol
import CryptoKit
import Foundation
import XCTest
@testable import RelayServerCore


final class RelayIdentityBoundSocketTests: XCTestCase {
    private static let runtimeNonce = "0123456789abcdef0123456789abcdef"
    private static let clientNonce = "fedcba9876543210fedcba9876543210"
    private static let runtimeEphemeralKey =
        "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296" +
        "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
    private static let clientEphemeralKey =
        "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc47669978" +
        "07775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1"

    func testControlLineReaderUsesAbsoluteDeadlineAndPreserves4096ByteLimit() throws {
        var sockets = [Int32](repeating: -1, count: 2)
        XCTAssertEqual(Darwin.socketpair(AF_UNIX, SOCK_STREAM, 0, &sockets), 0)
        defer {
            Darwin.close(sockets[0])
            Darwin.close(sockets[1])
        }

        let exactLine = String(repeating: "a", count: 4095) + "\n"
        try write(exactLine, socket: sockets[0])
        XCTAssertEqual(
            try RelayServerControlLineReader.read(
                socket: sockets[1],
                timeoutSeconds: 1
            ),
            exactLine
        )

        let overlongLine = String(repeating: "b", count: 4096) + "\n"
        try write(overlongLine, socket: sockets[0])
        XCTAssertThrowsError(
            try RelayServerControlLineReader.read(
                socket: sockets[1],
                timeoutSeconds: 1
            )
        ) { error in
            XCTAssertEqual(error as? RelayServerError, .handshakeReadFailed)
        }

        var trickleSockets = [Int32](repeating: -1, count: 2)
        XCTAssertEqual(Darwin.socketpair(AF_UNIX, SOCK_STREAM, 0, &trickleSockets), 0)
        defer {
            Darwin.close(trickleSockets[0])
            Darwin.close(trickleSockets[1])
        }
        DispatchQueue.global(qos: .userInitiated).async {
            var first = UInt8(ascii: "a")
            _ = Darwin.send(trickleSockets[0], &first, 1, 0)
            usleep(80_000)
            var second = UInt8(ascii: "b")
            _ = Darwin.send(trickleSockets[0], &second, 1, 0)
        }
        let startedAt = Date()
        XCTAssertThrowsError(
            try RelayServerControlLineReader.read(
                socket: trickleSockets[1],
                timeoutSeconds: 0.12
            )
        ) { error in
            XCTAssertEqual(error as? RelayServerError, .controlLineReadTimedOut)
        }
        XCTAssertLessThan(Date().timeIntervalSince(startedAt), 0.5)
    }

    func testControlLineReaderRecomputesDeadlineAfterEveryPollAndReceiveInterrupt() throws {
        var pollClock: [UInt64] = [
            1_000_000_000,
            1_050_000_000,
            1_200_000_000,
            1_300_000_000
        ]
        var pollTimeouts: [Int32] = []
        let interruptedPollOperations = RelayServerControlLineOperations(
            monotonicNow: { pollClock.removeFirst() },
            pollSocket: { _, timeoutMilliseconds in
                pollTimeouts.append(timeoutMilliseconds)
                return .interrupted
            },
            receiveByte: { _ in
                XCTFail("recv must not run while poll is repeatedly interrupted")
                return .failed
            }
        )

        XCTAssertThrowsError(
            try RelayServerControlLineReader.read(
                socket: -1,
                timeoutSeconds: 0.3,
                operations: interruptedPollOperations
            )
        ) { error in
            XCTAssertEqual(error as? RelayServerError, .controlLineReadTimedOut)
        }
        XCTAssertEqual(pollTimeouts, [250, 100])

        var receiveClock: [UInt64] = [
            1_000_000_000,
            1_010_000_000,
            1_020_000_000,
            1_300_000_000
        ]
        var receiveAttempts = 0
        let interruptedReceiveOperations = RelayServerControlLineOperations(
            monotonicNow: { receiveClock.removeFirst() },
            pollSocket: { _, timeoutMilliseconds in
                XCTAssertEqual(timeoutMilliseconds, 290)
                return .ready(events: Int16(POLLIN))
            },
            receiveByte: { _ in
                receiveAttempts += 1
                return .interrupted
            }
        )

        XCTAssertThrowsError(
            try RelayServerControlLineReader.read(
                socket: -1,
                timeoutSeconds: 0.3,
                operations: interruptedReceiveOperations
            )
        ) { error in
            XCTAssertEqual(error as? RelayServerError, .controlLineReadTimedOut)
        }
        XCTAssertEqual(receiveAttempts, 1)
    }

    func testRawBufferWriterPreservesPartialSendAndInterruptSemantics() {
        let payload = (0..<17).map { UInt8($0) }
        var attempts = 0
        var requestedByteCounts: [Int] = []
        var acceptedBytes: [UInt8] = []

        let wroteAll = payload.withUnsafeBytes { rawBuffer in
            relayWriteAll(rawBuffer: rawBuffer) { baseAddress, byteCount in
                attempts += 1
                requestedByteCounts.append(byteCount)
                if attempts == 1 {
                    errno = EINTR
                    return -1
                }
                let acceptedByteCount = min(byteCount, attempts == 2 ? 3 : 5)
                acceptedBytes.append(contentsOf: UnsafeRawBufferPointer(
                    start: baseAddress,
                    count: acceptedByteCount
                ))
                return acceptedByteCount
            }
        }

        XCTAssertTrue(wroteAll)
        XCTAssertEqual(requestedByteCounts, [17, 17, 14, 9, 4])
        XCTAssertEqual(acceptedBytes, payload)
    }

    func testRawBufferWriterPreservesBrokenPipeAndConnectionResetSemantics() {
        let payload: [UInt8] = [0x41]
        for expectedError in [EPIPE, ECONNRESET] {
            var attempts = 0
            let wroteAll = payload.withUnsafeBytes { rawBuffer in
                relayWriteAll(rawBuffer: rawBuffer) { _, _ in
                    attempts += 1
                    errno = expectedError
                    return -1
                }
            }

            XCTAssertFalse(wroteAll)
            XCTAssertEqual(attempts, 1)
        }
    }

    func testLoopbackPreflightRateLimitSilentlyClosesWithStableSourceFreeObservability() throws {
        let logCapture = SocketReasonLogCapture()
        var inspectedServer: RelayServer?
        let port = try startServer(
            sourceRateLimitConfiguration: RelaySourceRateLimitConfiguration(
                preflightRequestsPerMinute: 1,
                preflightBurst: 2,
                allocationMutationRequestsPerMinute: 1,
                allocationMutationBurst: 1
            ),
            startedServer: { inspectedServer = $0 },
            sourceRateLimitLog: { logCapture.append($0) }
        )
        let expectedResponse = String(
            decoding: try RelayAllocationPreflightResponse().responseLine(),
            as: UTF8.self
        )

        XCTAssertEqual(try sendPreflight(routeToken: "socket-preflight-0", port: port), expectedResponse)
        XCTAssertEqual(try sendPreflight(routeToken: "socket-preflight-1", port: port), expectedResponse)
        XCTAssertNil(try sendPreflight(routeToken: "socket-preflight-secret", port: port))

        let metrics = try XCTUnwrap(inspectedServer).sourceRateLimitMetricsSnapshot()
        XCTAssertEqual(metrics.allocationPreflightRequestsTotal, 3)
        XCTAssertEqual(metrics.allocationMutationRequestsTotal, 0)
        XCTAssertEqual(metrics.allocationPreflightSourceRateLimitedTotal, 1)
        XCTAssertEqual(metrics.allocationMutationSourceRateLimitedTotal, 0)
        XCTAssertEqual(metrics.rateLimitSourceEvictionsTotal, 0)
        XCTAssertEqual(metrics.trackedSourceCount, 1)
        XCTAssertEqual(
            logCapture.messages,
            ["reason=allocation_preflight_source_rate_limited reason_count=1"]
        )
        let observableText = String(describing: metrics.valuesByName) + logCapture.messages.joined()
        XCTAssertFalse(observableText.contains("127.0.0.1"))
        XCTAssertFalse(observableText.contains("socket-preflight-secret"))
    }

    func testMalformedAllocationControlRecordsConsumeClassifiedSourceBudgets() throws {
        var inspectedServer: RelayServer?
        let port = try startServer(
            sourceRateLimitConfiguration: RelaySourceRateLimitConfiguration(
                preflightRequestsPerMinute: 1,
                preflightBurst: 10,
                allocationMutationRequestsPerMinute: 1,
                allocationMutationBurst: 6
            ),
            startedServer: { inspectedServer = $0 }
        )

        let malformedPreflight = try connect(port: port)
        try write(
            "AETHERLINK_RELAY allocate malformed-preflight crypto=2 preflight=1 unexpected=1\n",
            socket: malformedPreflight
        )
        XCTAssertNil(try readLine(socket: malformedPreflight))
        Darwin.close(malformedPreflight)

        let duplicatedPreflight = try connect(port: port)
        try write(
            "AETHERLINK_RELAY allocate duplicated-preflight crypto=2 preflight=1 preflight=1\n",
            socket: duplicatedPreflight
        )
        XCTAssertNil(try readLine(socket: duplicatedPreflight))
        Darwin.close(duplicatedPreflight)

        let tabbedRouteToken = try connect(port: port)
        try write(
            "AETHERLINK_RELAY allocate tabbed\troute crypto=2 preflight=1\n",
            socket: tabbedRouteToken
        )
        XCTAssertNil(try readLine(socket: tabbedRouteToken))
        Darwin.close(tabbedRouteToken)

        let tabbedAllocationToken = try connect(port: port)
        try write(
            "AETHERLINK_RELAY allocate tabbed-token crypto=2 " +
                "allocation_token=bad\ttoken preflight=1\n",
            socket: tabbedAllocationToken
        )
        XCTAssertNil(try readLine(socket: tabbedAllocationToken))
        Darwin.close(tabbedAllocationToken)

        let nonASCIIWhitespaceRouteToken = try connect(port: port)
        try write(
            "AETHERLINK_RELAY allocate nonbreaking\u{00A0}space crypto=2 preflight=1\n",
            socket: nonASCIIWhitespaceRouteToken
        )
        XCTAssertNil(try readLine(socket: nonASCIIWhitespaceRouteToken))
        Darwin.close(nonASCIIWhitespaceRouteToken)

        let malformedRenewal = try connect(port: port)
        try write("AETHERLINK_RELAY renew malformed\n", socket: malformedRenewal)
        XCTAssertNil(try readLine(socket: malformedRenewal))
        Darwin.close(malformedRenewal)

        let expectedPreflightResponse = String(
            decoding: try RelayAllocationPreflightResponse().responseLine(),
            as: UTF8.self
        )
        XCTAssertEqual(
            try sendPreflight(routeToken: "preflight-after-malformed", port: port),
            expectedPreflightResponse
        )

        let signer = try SocketIdentitySigner()
        let identity = signer.identity
        let rejectedAllocation = try connect(port: port)
        try write(
            "AETHERLINK_RELAY allocate mutation-after-malformed crypto=2 " +
                "allocation_auth=runtime-p256-v1 runtime_key_fingerprint=\(identity.fingerprint) " +
                "runtime_public_key=\(identity.publicKeyBase64)\n",
            socket: rejectedAllocation
        )
        XCTAssertNil(try readLine(socket: rejectedAllocation))
        Darwin.close(rejectedAllocation)

        let metrics = try XCTUnwrap(inspectedServer).sourceRateLimitMetricsSnapshot()
        XCTAssertEqual(metrics.allocationPreflightRequestsTotal, 1)
        XCTAssertEqual(metrics.allocationMutationRequestsTotal, 7)
        XCTAssertEqual(metrics.allocationPreflightSourceRateLimitedTotal, 0)
        XCTAssertEqual(metrics.allocationMutationSourceRateLimitedTotal, 1)
    }

    func testAllocationMutationBucketIsSeparateFromPreflightBucket() throws {
        var inspectedServer: RelayServer?
        let port = try startServer(
            sourceRateLimitConfiguration: RelaySourceRateLimitConfiguration(
                preflightRequestsPerMinute: 1,
                preflightBurst: 1,
                allocationMutationRequestsPerMinute: 1,
                allocationMutationBurst: 1
            ),
            startedServer: { inspectedServer = $0 }
        )
        XCTAssertNotNil(try sendPreflight(routeToken: "separate-preflight-allowed", port: port))
        XCTAssertNil(try sendPreflight(routeToken: "separate-preflight-rejected", port: port))

        let signer = try SocketIdentitySigner()
        let pending = try beginAllocation(
            routeToken: "separate-mutation-allowed",
            signer: signer,
            port: port
        )
        Darwin.close(pending.socket)

        let rejected = try connect(port: port)
        let identity = signer.identity
        try write(
            "AETHERLINK_RELAY allocate separate-mutation-rejected crypto=2 " +
                "allocation_auth=runtime-p256-v1 runtime_key_fingerprint=\(identity.fingerprint) " +
                "runtime_public_key=\(identity.publicKeyBase64)\n",
            socket: rejected
        )
        XCTAssertNil(try readLine(socket: rejected))
        Darwin.close(rejected)

        let metrics = try XCTUnwrap(inspectedServer).sourceRateLimitMetricsSnapshot()
        XCTAssertEqual(metrics.allocationPreflightRequestsTotal, 2)
        XCTAssertEqual(metrics.allocationMutationRequestsTotal, 2)
        XCTAssertEqual(metrics.allocationPreflightSourceRateLimitedTotal, 1)
        XCTAssertEqual(metrics.allocationMutationSourceRateLimitedTotal, 1)
    }

    func testPairedRenewalSharesAllocationMutationBucket() throws {
        var inspectedServer: RelayServer?
        let port = try startServer(
            sourceRateLimitConfiguration: RelaySourceRateLimitConfiguration(
                preflightRequestsPerMinute: 1,
                preflightBurst: 1,
                allocationMutationRequestsPerMinute: 1,
                allocationMutationBurst: 2
            ),
            startedServer: { inspectedServer = $0 }
        )
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let routeToken = "paired-shared-mutation-bucket"
        _ = try allocate(routeToken: routeToken, signer: runtimeSigner, port: port)

        let claim = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port
        )
        _ = try completePairedRenewal(
            claim,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(claim.socket)

        let rejected = try openPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            requestID: "rate-limited-renewal",
            authorizationID: "rate-limited-renewal-authorization"
        )
        XCTAssertNil(try readLine(socket: rejected.socket))
        Darwin.close(rejected.socket)

        let metrics = try XCTUnwrap(inspectedServer).sourceRateLimitMetricsSnapshot()
        XCTAssertEqual(metrics.allocationMutationRequestsTotal, 3)
        XCTAssertEqual(metrics.allocationMutationSourceRateLimitedTotal, 1)
    }

    func testRateLimitedSourceStillUsesPeerAdmissionAndBridgeTraffic() throws {
        let port = try startServer(
            sourceRateLimitConfiguration: RelaySourceRateLimitConfiguration(
                preflightRequestsPerMinute: 1,
                preflightBurst: 1,
                allocationMutationRequestsPerMinute: 1,
                allocationMutationBurst: 2
            )
        )
        let signer = try SocketIdentitySigner()
        let allocation = try allocate(
            routeToken: "rate-limit-does-not-throttle-bridge",
            signer: signer,
            port: port
        )
        XCTAssertNotNil(try sendPreflight(routeToken: "bridge-preflight-allowed", port: port))
        XCTAssertNil(try sendPreflight(routeToken: "bridge-preflight-rejected", port: port))

        let runtime = try connect(port: port)
        let client = try connect(port: port)
        defer {
            Darwin.close(runtime)
            Darwin.close(client)
        }
        try authorizeRuntime(socket: runtime, allocation: allocation, signer: signer)
        XCTAssertEqual(try readLine(socket: runtime), "AETHERLINK_RELAY registered crypto=2\n")
        try write(clientHandshake(relayID: allocation.relayID), socket: client)
        try assertReadyPair(runtime: runtime, client: client)

        try write("runtime-frame-after-rate-limit\n", socket: runtime)
        XCTAssertEqual(try readLine(socket: client), "runtime-frame-after-rate-limit\n")
        try write("client-frame-after-rate-limit\n", socket: client)
        XCTAssertEqual(try readLine(socket: runtime), "client-frame-after-rate-limit\n")
    }

    func testWaitingTimeoutReleasesSourceAndIdentityCapacityAndAllowsRetry() throws {
        let logCapture = SocketReasonLogCapture()
        var inspectedServer: RelayServer?
        let port = try startServer(
            waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration(
                maximumDurationSeconds: 0.05,
                maximumPeersPerAuthenticatedIdentity: 1
            ),
            startedServer: { inspectedServer = $0 },
            waitingPeerPolicyLog: { logCapture.append($0) }
        )
        let signer = try SocketIdentitySigner()
        let allocation = try allocate(
            routeToken: "waiting-timeout-retry",
            signer: signer,
            port: port
        )
        let server = try XCTUnwrap(inspectedServer)
        _ = try waitForSourceQuotaMetrics(server) { $0.activeConnections == 0 }

        let runtime = try connect(port: port)
        try authorizeRuntime(socket: runtime, allocation: allocation, signer: signer)
        XCTAssertEqual(try readLine(socket: runtime), "AETHERLINK_RELAY registered crypto=2\n")
        _ = try waitForWaitingPeerPolicyMetrics(server) {
            $0.authenticatedIdentityWaitingPeers == 1
        }
        XCTAssertNil(try readLine(socket: runtime))
        Darwin.close(runtime)

        let expiredMetrics = try waitForWaitingPeerPolicyMetrics(server) {
            $0.waitingPeerTimeoutsTotal == 1 &&
                $0.authenticatedIdentityWaitingPeers == 0
        }
        XCTAssertEqual(expiredMetrics.authenticatedIdentitiesWithWaiters, 0)
        _ = try waitForSourceQuotaMetrics(server) {
            $0.waitingPeers == 0 && $0.activeConnections == 0
        }

        let retry = try connect(port: port)
        try authorizeRuntime(socket: retry, allocation: allocation, signer: signer)
        XCTAssertEqual(try readLine(socket: retry), "AETHERLINK_RELAY registered crypto=2\n")
        Darwin.close(retry)
        _ = try waitForWaitingPeerPolicyMetrics(server) {
            $0.authenticatedIdentityWaitingPeers == 0
        }

        XCTAssertEqual(
            logCapture.messages,
            ["reason=waiting_peer_timed_out reason_count=1"]
        )
        XCTAssertFalse(logCapture.messages.joined().contains(allocation.relayID))
        XCTAssertFalse(logCapture.messages.joined().contains(signer.identity.fingerprint))
    }

    func testMatchedBridgeCancelsWaitingTimeoutAndContinuesForwarding() throws {
        var inspectedServer: RelayServer?
        let port = try startServer(
            waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration(
                maximumDurationSeconds: 0.05,
                maximumPeersPerAuthenticatedIdentity: 1
            ),
            startedServer: { inspectedServer = $0 }
        )
        let signer = try SocketIdentitySigner()
        let allocation = try allocate(
            routeToken: "waiting-timeout-cancel-on-match",
            signer: signer,
            port: port
        )
        let server = try XCTUnwrap(inspectedServer)
        _ = try waitForSourceQuotaMetrics(server) { $0.activeConnections == 0 }

        let runtime = try connect(port: port)
        try authorizeRuntime(socket: runtime, allocation: allocation, signer: signer)
        XCTAssertEqual(try readLine(socket: runtime), "AETHERLINK_RELAY registered crypto=2\n")
        let client = try connect(port: port)
        defer {
            Darwin.close(runtime)
            Darwin.close(client)
        }
        try write(clientHandshake(relayID: allocation.relayID), socket: client)
        try assertReadyPair(runtime: runtime, client: client)

        Thread.sleep(forTimeInterval: 0.15)
        XCTAssertEqual(server.waitingPeerPolicyMetricsSnapshot().waitingPeerTimeoutsTotal, 0)
        XCTAssertEqual(
            server.waitingPeerPolicyMetricsSnapshot().authenticatedIdentityWaitingPeers,
            0
        )
        try write("runtime-frame-after-waiting-timeout\n", socket: runtime)
        XCTAssertEqual(
            try readLine(socket: client),
            "runtime-frame-after-waiting-timeout\n"
        )
        try write("client-frame-after-waiting-timeout\n", socket: client)
        XCTAssertEqual(
            try readLine(socket: runtime),
            "client-frame-after-waiting-timeout\n"
        )
    }

    func testAuthenticatedIdentityWaitingQuotaRejectsOnlySameIdentity() throws {
        let logCapture = SocketReasonLogCapture()
        var inspectedServer: RelayServer?
        let port = try startServer(
            waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration(
                maximumDurationSeconds: 5,
                maximumPeersPerAuthenticatedIdentity: 1
            ),
            startedServer: { inspectedServer = $0 },
            waitingPeerPolicyLog: { logCapture.append($0) }
        )
        let signerA = try SocketIdentitySigner()
        let signerB = try SocketIdentitySigner()
        let firstA = try allocate(
            routeToken: "identity-waiting-a-first",
            signer: signerA,
            port: port
        )
        let secondA = try allocate(
            routeToken: "identity-waiting-a-second",
            signer: signerA,
            port: port
        )
        let firstB = try allocate(
            routeToken: "identity-waiting-b-first",
            signer: signerB,
            port: port
        )
        let server = try XCTUnwrap(inspectedServer)
        _ = try waitForSourceQuotaMetrics(server) { $0.activeConnections == 0 }

        let runtimeA = try connect(port: port)
        try authorizeRuntime(socket: runtimeA, allocation: firstA, signer: signerA)
        XCTAssertEqual(try readLine(socket: runtimeA), "AETHERLINK_RELAY registered crypto=2\n")

        let rejectedA = try connect(port: port)
        try authorizeRuntime(socket: rejectedA, allocation: secondA, signer: signerA)
        XCTAssertNil(try readLine(socket: rejectedA))
        Darwin.close(rejectedA)

        let runtimeB = try connect(port: port)
        try authorizeRuntime(socket: runtimeB, allocation: firstB, signer: signerB)
        XCTAssertEqual(try readLine(socket: runtimeB), "AETHERLINK_RELAY registered crypto=2\n")
        let saturatedMetrics = try waitForWaitingPeerPolicyMetrics(server) {
            $0.identityWaitingQuotaRejectionsTotal == 1 &&
                $0.authenticatedIdentityWaitingPeers == 2
        }
        XCTAssertEqual(saturatedMetrics.authenticatedIdentitiesWithWaiters, 2)
        XCTAssertEqual(
            logCapture.messages,
            ["reason=authenticated_identity_waiting_quota_reached reason_count=1"]
        )
        XCTAssertFalse(logCapture.messages.joined().contains(signerA.identity.fingerprint))
        XCTAssertFalse(logCapture.messages.joined().contains(firstA.relayID))

        Darwin.close(runtimeA)
        Darwin.close(runtimeB)
        _ = try waitForWaitingPeerPolicyMetrics(server) {
            $0.authenticatedIdentityWaitingPeers == 0
        }

        let retryA = try connect(port: port)
        try authorizeRuntime(socket: retryA, allocation: secondA, signer: signerA)
        XCTAssertEqual(try readLine(socket: retryA), "AETHERLINK_RELAY registered crypto=2\n")
        Darwin.close(retryA)
    }

    func testPairedClientIdentityWaitingQuotaRequiresVerifiedClientProof() throws {
        let logCapture = SocketReasonLogCapture()
        var inspectedServer: RelayServer?
        let port = try startServer(
            waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration(
                maximumDurationSeconds: 5,
                maximumPeersPerAuthenticatedIdentity: 1
            ),
            startedServer: { inspectedServer = $0 },
            waitingPeerPolicyLog: { logCapture.append($0) }
        )
        let runtimeSignerA = try SocketIdentitySigner()
        let runtimeSignerB = try SocketIdentitySigner()
        let runtimeSignerC = try SocketIdentitySigner()
        let clientSignerA = try SocketIdentitySigner()
        let clientSignerB = try SocketIdentitySigner()

        _ = try allocate(
            routeToken: "paired-client-identity-a-first",
            signer: runtimeSignerA,
            port: port
        )
        let claimAFirst = try beginPairedRenewal(
            routeToken: "paired-client-identity-a-first",
            runtimeSigner: runtimeSignerA,
            clientSigner: clientSignerA,
            port: port
        )
        let allocationAFirst = try completePairedRenewal(
            claimAFirst,
            runtimeSigner: runtimeSignerA,
            clientSigner: clientSignerA
        )
        Darwin.close(claimAFirst.socket)

        _ = try allocate(
            routeToken: "paired-client-identity-a-second",
            signer: runtimeSignerB,
            port: port
        )
        let claimASecond = try beginPairedRenewal(
            routeToken: "paired-client-identity-a-second",
            runtimeSigner: runtimeSignerB,
            clientSigner: clientSignerA,
            port: port
        )
        let allocationASecond = try completePairedRenewal(
            claimASecond,
            runtimeSigner: runtimeSignerB,
            clientSigner: clientSignerA
        )
        Darwin.close(claimASecond.socket)

        _ = try allocate(
            routeToken: "paired-client-identity-b-first",
            signer: runtimeSignerC,
            port: port
        )
        let claimBFirst = try beginPairedRenewal(
            routeToken: "paired-client-identity-b-first",
            runtimeSigner: runtimeSignerC,
            clientSigner: clientSignerB,
            port: port
        )
        let allocationBFirst = try completePairedRenewal(
            claimBFirst,
            runtimeSigner: runtimeSignerC,
            clientSigner: clientSignerB
        )
        Darwin.close(claimBFirst.socket)

        let server = try XCTUnwrap(inspectedServer)
        _ = try waitForSourceQuotaMetrics(server) { $0.activeConnections == 0 }
        let clientAFirst = try connect(port: port)
        try authorizePairedClient(
            socket: clientAFirst,
            allocation: allocationAFirst,
            signer: clientSignerA
        )
        _ = try waitForWaitingPeerPolicyMetrics(server) {
            $0.authenticatedIdentityWaitingPeers == 1
        }

        let rejectedClientA = try connect(port: port)
        try authorizePairedClient(
            socket: rejectedClientA,
            allocation: allocationASecond,
            signer: clientSignerA
        )
        XCTAssertNil(try readLine(socket: rejectedClientA))
        Darwin.close(rejectedClientA)

        let clientBFirst = try connect(port: port)
        try authorizePairedClient(
            socket: clientBFirst,
            allocation: allocationBFirst,
            signer: clientSignerB
        )
        let metrics = try waitForWaitingPeerPolicyMetrics(server) {
            $0.identityWaitingQuotaRejectionsTotal == 1 &&
                $0.authenticatedIdentityWaitingPeers == 2
        }
        XCTAssertEqual(metrics.authenticatedIdentitiesWithWaiters, 2)
        XCTAssertEqual(
            logCapture.messages,
            ["reason=authenticated_identity_waiting_quota_reached reason_count=1"]
        )
        XCTAssertFalse(logCapture.messages.joined().contains(clientSignerA.identity.fingerprint))

        Darwin.close(clientAFirst)
        Darwin.close(clientBFirst)
        _ = try waitForWaitingPeerPolicyMetrics(server) {
            $0.authenticatedIdentityWaitingPeers == 0
        }

        let retryClientA = try connect(port: port)
        try authorizePairedClient(
            socket: retryClientA,
            allocation: allocationASecond,
            signer: clientSignerA
        )
        _ = try waitForWaitingPeerPolicyMetrics(server) {
            $0.authenticatedIdentityWaitingPeers == 1
        }
        Darwin.close(retryClientA)
    }

    func testSourceConnectionQuotaRejectsExcessWhileActiveBridgeStillForwards() throws {
        let logCapture = SocketReasonLogCapture()
        var inspectedServer: RelayServer?
        let port = try startServer(
            maximumConcurrentConnections: 8,
            sourceQuotaConfiguration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 2,
                maximumWaitingPeersPerSource: 1
            ),
            startedServer: { inspectedServer = $0 },
            sourceQuotaLog: { logCapture.append($0) }
        )
        let signer = try SocketIdentitySigner()
        let allocation = try allocate(
            routeToken: "source-connection-quota-bridge",
            signer: signer,
            port: port
        )
        let server = try XCTUnwrap(inspectedServer)
        _ = try waitForSourceQuotaMetrics(server) { $0.activeConnections == 0 }

        let runtime = try connect(port: port)
        defer {
            Darwin.close(runtime)
        }
        try authorizeRuntime(socket: runtime, allocation: allocation, signer: signer)
        XCTAssertEqual(try readLine(socket: runtime), "AETHERLINK_RELAY registered crypto=2\n")

        let client = try connect(port: port)
        defer {
            Darwin.close(client)
        }
        try write(clientHandshake(relayID: allocation.relayID), socket: client)
        try assertReadyPair(runtime: runtime, client: client)

        let excess = try connect(port: port)
        XCTAssertNil(try readLine(socket: excess))
        Darwin.close(excess)

        try write("runtime-frame-after-source-quota\n", socket: runtime)
        XCTAssertEqual(try readLine(socket: client), "runtime-frame-after-source-quota\n")
        try write("client-frame-after-source-quota\n", socket: client)
        XCTAssertEqual(try readLine(socket: runtime), "client-frame-after-source-quota\n")

        let metrics = try waitForSourceQuotaMetrics(server) {
            $0.sourceConnectionQuotaRejectionsTotal == 1 && $0.activeConnections == 2
        }
        XCTAssertEqual(metrics.activeConnectionSources, 1)
        XCTAssertEqual(
            logCapture.messages,
            ["reason=source_connection_quota_reached reason_count=1"]
        )
        XCTAssertFalse(logCapture.messages.joined().contains("127.0.0.1"))
        XCTAssertFalse(logCapture.messages.joined().contains(allocation.relayID))
    }

    func testSourceWaitingQuotaRejectsOnlyNewWaiterAndAllowsImmediateCounterpart() throws {
        let logCapture = SocketReasonLogCapture()
        var inspectedServer: RelayServer?
        let port = try startServer(
            maximumConcurrentConnections: 8,
            sourceQuotaConfiguration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 4,
                maximumWaitingPeersPerSource: 1
            ),
            startedServer: { inspectedServer = $0 },
            sourceQuotaLog: { logCapture.append($0) }
        )
        let signer = try SocketIdentitySigner()
        let first = try allocate(
            routeToken: "source-waiting-quota-first",
            signer: signer,
            port: port
        )
        let second = try allocate(
            routeToken: "source-waiting-quota-second",
            signer: signer,
            port: port
        )
        let server = try XCTUnwrap(inspectedServer)
        _ = try waitForSourceQuotaMetrics(server) { $0.activeConnections == 0 }

        let waitingRuntime = try connectWaitingRuntime(
            allocation: first,
            signer: signer,
            port: port
        )
        let rejectedRuntime = try connect(port: port)
        try authorizeRuntime(socket: rejectedRuntime, allocation: second, signer: signer)
        XCTAssertNil(try readLine(socket: rejectedRuntime))
        Darwin.close(rejectedRuntime)

        let client = try connect(port: port)
        defer {
            Darwin.close(waitingRuntime)
            Darwin.close(client)
        }
        try write(clientHandshake(relayID: first.relayID), socket: client)
        try assertReadyPair(runtime: waitingRuntime, client: client)
        try write("matched-at-waiting-quota\n", socket: client)
        XCTAssertEqual(try readLine(socket: waitingRuntime), "matched-at-waiting-quota\n")

        var metrics = try waitForSourceQuotaMetrics(server) {
            $0.sourceWaitingPeerQuotaRejectionsTotal == 1 && $0.waitingPeers == 0
        }
        XCTAssertEqual(metrics.activeConnections, 2)

        let retryRuntime = try connectWaitingRuntime(
            allocation: second,
            signer: signer,
            port: port
        )
        defer { Darwin.close(retryRuntime) }
        metrics = try waitForSourceQuotaMetrics(server) { $0.waitingPeers == 1 }
        XCTAssertEqual(metrics.waitingPeerSources, 1)
        XCTAssertEqual(
            logCapture.messages,
            ["reason=source_waiting_peer_quota_reached reason_count=1"]
        )
        XCTAssertFalse(logCapture.messages.joined().contains(second.relayID))
    }

    func testWaitingDisconnectReleasesSourceQuotaBeforeConnectionPermit() throws {
        var inspectedServer: RelayServer?
        let port = try startServer(
            maximumConcurrentConnections: 4,
            sourceQuotaConfiguration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 2,
                maximumWaitingPeersPerSource: 1
            ),
            startedServer: { inspectedServer = $0 }
        )
        let signer = try SocketIdentitySigner()
        let first = try allocate(
            routeToken: "source-waiting-disconnect-first",
            signer: signer,
            port: port
        )
        let second = try allocate(
            routeToken: "source-waiting-disconnect-second",
            signer: signer,
            port: port
        )
        let server = try XCTUnwrap(inspectedServer)
        _ = try waitForSourceQuotaMetrics(server) { $0.activeConnections == 0 }

        let disconnected = try connectWaitingRuntime(
            allocation: first,
            signer: signer,
            port: port
        )
        Darwin.close(disconnected)
        _ = try waitForSourceQuotaMetrics(server) {
            $0.waitingPeers == 0 && $0.activeConnections == 0
        }

        let replacement = try connectWaitingRuntime(
            allocation: second,
            signer: signer,
            port: port
        )
        defer { Darwin.close(replacement) }
        let metrics = try waitForSourceQuotaMetrics(server) { $0.waitingPeers == 1 }
        XCTAssertEqual(metrics.sourceWaitingPeerQuotaRejectionsTotal, 0)
    }

    func testCounterpartReserveSurvivesActiveBridgeAndRejectsNonmatchingCandidate() throws {
        let logCapture = SocketReasonLogCapture()
        var inspectedServer: RelayServer?
        let port = try startServer(
            maximumConcurrentConnections: 4,
            sourceQuotaConfiguration: RelaySourceQuotaConfiguration(
                maximumConnectionsPerSource: 4,
                maximumWaitingPeersPerSource: 1
            ),
            startedServer: { inspectedServer = $0 },
            sourceQuotaLog: { logCapture.append($0) }
        )
        let signer = try SocketIdentitySigner()
        let first = try allocate(
            routeToken: "counterpart-reserve-active-first",
            signer: signer,
            port: port
        )
        let second = try allocate(
            routeToken: "counterpart-reserve-active-second",
            signer: signer,
            port: port
        )
        let server = try XCTUnwrap(inspectedServer)
        _ = try waitForSourceQuotaMetrics(server) { $0.activeConnections == 0 }

        let firstRuntime = try connectWaitingRuntime(
            allocation: first,
            signer: signer,
            port: port
        )
        let firstClient = try connect(port: port)
        try write(clientHandshake(relayID: first.relayID), socket: firstClient)
        try assertReadyPair(runtime: firstRuntime, client: firstClient)

        let secondRuntime = try connectWaitingRuntime(
            allocation: second,
            signer: signer,
            port: port
        )
        let nonmatchingCandidate = try connect(port: port)
        try write("AETHERLINK_RELAY probe reserved-candidate\n", socket: nonmatchingCandidate)
        XCTAssertNil(try readLine(socket: nonmatchingCandidate))
        Darwin.close(nonmatchingCandidate)
        _ = try waitForSourceQuotaMetrics(server) {
            $0.counterpartCandidatesRejectedTotal == 1 &&
                $0.counterpartCandidatesCurrent == 0 &&
                $0.waitingPeers == 1
        }

        let secondClient = try connect(port: port)
        defer {
            Darwin.close(firstRuntime)
            Darwin.close(firstClient)
            Darwin.close(secondRuntime)
            Darwin.close(secondClient)
        }
        try write(clientHandshake(relayID: second.relayID), socket: secondClient)
        try assertReadyPair(runtime: secondRuntime, client: secondClient)

        try assertRelayPayloads(
            from: firstRuntime,
            to: firstClient,
            seed: 0x11,
            label: "runtime-to-client"
        )
        try assertRelayPayloads(
            from: secondClient,
            to: secondRuntime,
            seed: 0xa7,
            label: "client-to-runtime"
        )

        let metrics = try waitForSourceQuotaMetrics(server) {
            $0.counterpartCandidatesConfirmedTotal == 1 &&
                $0.counterpartCandidatesCurrent == 0 &&
                $0.waitingPeers == 0 &&
                $0.activeConnections == 4
        }
        XCTAssertEqual(metrics.counterpartCandidatesAdmittedTotal, 2)
        XCTAssertEqual(
            logCapture.messages,
            ["reason=counterpart_candidate_not_matched reason_count=1"]
        )
        XCTAssertFalse(logCapture.messages.joined().contains(second.relayID))
    }

    func testIdleControlTimeoutReclaimsConnectionPermit() throws {
        let port = try startServer(
            controlLineReadTimeout: 0.1,
            maximumConcurrentConnections: 1
        )
        let idle = try connect(port: port)
        try write("A", socket: idle)
        Thread.sleep(forTimeInterval: 0.2)
        XCTAssertNil(try readLine(socket: idle))
        Darwin.close(idle)

        XCTAssertEqual(
            try waitForProbe(relayID: "timeout-reclaimed", port: port),
            "AETHERLINK_RELAY probe known=0 runtime_waiting=0\n"
        )
    }

    func testWaitingPeerDisconnectReclaimsConnectionPermit() throws {
        let signer = try SocketIdentitySigner()
        let port = try startServer(maximumConcurrentConnections: 2)
        let allocation = try allocate(
            routeToken: "waiting-permit",
            signer: signer,
            port: port
        )
        let runtime = try connect(port: port)
        try authorizeRuntime(socket: runtime, allocation: allocation, signer: signer)
        XCTAssertEqual(try readLine(socket: runtime), "AETHERLINK_RELAY registered crypto=2\n")

        let nonmatchingCandidate = try connect(port: port)
        try write("AETHERLINK_RELAY probe nonmatching-candidate\n", socket: nonmatchingCandidate)
        XCTAssertNil(try readLine(socket: nonmatchingCandidate))
        Darwin.close(nonmatchingCandidate)
        Darwin.close(runtime)

        XCTAssertEqual(
            try waitForProbe(relayID: allocation.relayID, port: port),
            "AETHERLINK_RELAY probe known=1 runtime_waiting=0\n"
        )
    }

    func testAcceptedSocketResetDuringResponseDoesNotTerminateServer() throws {
        let port = try startServer(maximumConcurrentConnections: 1)
        let resetSocket = try connect(port: port)
        try write("AETHERLINK_RELAY probe reset-response\n", socket: resetSocket)
        try closeWithReset(resetSocket)

        XCTAssertEqual(
            try waitForProbe(relayID: "reset-survived", port: port),
            "AETHERLINK_RELAY probe known=0 runtime_waiting=0\n"
        )
    }

    func testSinglePeerCloseReclaimsBothBridgePermitsAndActiveRoom() throws {
        let signer = try SocketIdentitySigner()
        let port = try startServer(maximumConcurrentConnections: 2)
        let allocation = try allocate(
            routeToken: "active-permits",
            signer: signer,
            port: port
        )
        let runtime = try connect(port: port)
        try authorizeRuntime(socket: runtime, allocation: allocation, signer: signer)
        XCTAssertEqual(try readLine(socket: runtime), "AETHERLINK_RELAY registered crypto=2\n")

        let client = try connect(port: port)
        defer { Darwin.close(client) }
        try write(clientHandshake(relayID: allocation.relayID), socket: client)
        try assertReadyPair(runtime: runtime, client: client)

        let excess = try connect(port: port)
        XCTAssertNil(try readLine(socket: excess))
        Darwin.close(excess)
        Darwin.close(runtime)
        XCTAssertTrue(try peerReachedEOF(socket: client))

        XCTAssertEqual(
            try waitForProbe(relayID: allocation.relayID, port: port),
            "AETHERLINK_RELAY probe known=1 runtime_waiting=0\n"
        )

        let reconnectedRuntime = try connectWaitingRuntime(
            allocation: allocation,
            signer: signer,
            port: port
        )
        let reconnectedClient = try connect(port: port)
        defer {
            Darwin.close(reconnectedRuntime)
            Darwin.close(reconnectedClient)
        }
        try write(clientHandshake(relayID: allocation.relayID), socket: reconnectedClient)
        try assertReadyPair(runtime: reconnectedRuntime, client: reconnectedClient)

        let excessAfterReuse = try connect(port: port)
        defer { Darwin.close(excessAfterReuse) }
        try? write("AETHERLINK_RELAY probe over-release-check\n", socket: excessAfterReuse)
        XCTAssertNil(try readLine(socket: excessAfterReuse))
    }

    func testExposedBindDisablesProbeUnlessLegacyDiagnosticPolicyIsExplicit() throws {
        let token = "exposed-probe-token"
        let signer = try SocketIdentitySigner()
        let disabledPort = try startServer(
            host: "0.0.0.0",
            storeURL: try temporaryStoreURL(),
            allocationToken: token
        )
        let disabledAllocation = try allocate(
            routeToken: "disabled-exposed-probe",
            signer: signer,
            port: disabledPort,
            allocationToken: token
        )
        let disabledProbe = try connect(port: disabledPort)
        try write("AETHERLINK_RELAY probe \(disabledAllocation.relayID)\n", socket: disabledProbe)
        XCTAssertNil(try readLine(socket: disabledProbe))
        Darwin.close(disabledProbe)

        let legacyPort = try startServer(
            host: "0.0.0.0",
            storeURL: try temporaryStoreURL(),
            allocationToken: token,
            probePolicy: .legacyUnauthenticated
        )
        let legacyAllocation = try allocate(
            routeToken: "explicit-exposed-probe",
            signer: signer,
            port: legacyPort,
            allocationToken: token
        )
        let legacyProbe = try connect(port: legacyPort)
        try write("AETHERLINK_RELAY probe \(legacyAllocation.relayID)\n", socket: legacyProbe)
        XCTAssertEqual(
            try readLine(socket: legacyProbe),
            "AETHERLINK_RELAY probe known=1 runtime_waiting=0\n"
        )
        Darwin.close(legacyProbe)
    }

    func testUnsignedPreflightReturnsExactClosedResponseAndNoUsableRoute() throws {
        let port = try startServer()
        let socket = try connect(port: port)
        defer { Darwin.close(socket) }
        try write(
            "AETHERLINK_RELAY allocate preflight-route crypto=2 preflight=1\n",
            socket: socket
        )
        XCTAssertEqual(
            try readLine(socket: socket),
            "AETHERLINK_RELAY preflight {\"allocation_auth\":\"runtime-p256-v1\",\"crypto_version\":2,\"preflight\":true}\n"
        )
        XCTAssertNil(try readLine(socket: socket))
    }

    func testChallengeAllocationAndRuntimeAdmissionSucceeds() throws {
        let signer = try SocketIdentitySigner()
        let port = try startServer()
        let allocation = try allocate(routeToken: "socket-success", signer: signer, port: port)
        let runtime = try connect(port: port)
        defer { Darwin.close(runtime) }

        try authorizeRuntime(socket: runtime, allocation: allocation, signer: signer)
        XCTAssertEqual(try readLine(socket: runtime), "AETHERLINK_RELAY registered crypto=2\n")
    }

    func testBootstrapInitialClientCanWaitWithoutProofBeforeAuthenticatedRuntime() throws {
        let signer = try SocketIdentitySigner()
        let port = try startServer()
        let allocation = try allocate(routeToken: "client-first", signer: signer, port: port)
        let client = try connect(port: port)
        let runtime = try connect(port: port)
        defer {
            Darwin.close(client)
            Darwin.close(runtime)
        }

        try write(clientHandshake(relayID: allocation.relayID), socket: client)
        try authorizeRuntime(socket: runtime, allocation: allocation, signer: signer)

        XCTAssertEqual(
            try readLine(socket: runtime),
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=\(Self.clientNonce) " +
                "peer_ephemeral_key=\(Self.clientEphemeralKey)\n"
        )
        XCTAssertEqual(
            try readLine(socket: client),
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=\(Self.runtimeNonce) " +
                "peer_ephemeral_key=\(Self.runtimeEphemeralKey)\n"
        )
    }

    func testAllocationProofReplayAndFieldMutationFailClosed() throws {
        let signer = try SocketIdentitySigner()
        let port = try startServer()
        let first = try beginAllocation(routeToken: "replay-route", signer: signer, port: port)
        let firstSignature = try signer.sign(first.challenge.signedMessageData())
        try write(
            String(decoding: try RelayAllocationProofRequest(
                challenge: first.challenge.challenge,
                signatureBase64: firstSignature,
                runtimeIdentity: signer.identity
            ).requestLine(), as: UTF8.self),
            socket: first.socket
        )
        _ = try XCTUnwrap(readLine(socket: first.socket))
        Darwin.close(first.socket)

        let renewal = try beginAllocation(routeToken: "replay-route", signer: signer, port: port)
        defer { Darwin.close(renewal.socket) }
        XCTAssertEqual(renewal.challenge.ticketGeneration, 2)
        try write(
            String(decoding: try RelayAllocationProofRequest(
                challenge: first.challenge.challenge,
                signatureBase64: firstSignature,
                runtimeIdentity: signer.identity
            ).requestLine(), as: UTF8.self),
            socket: renewal.socket
        )
        XCTAssertNil(try readLine(socket: renewal.socket))

        let mutation = try beginAllocation(routeToken: "mutation-route", signer: signer, port: port)
        defer { Darwin.close(mutation.socket) }
        let mutated = try RelayAllocationIdentityChallenge(
            operation: mutation.challenge.operation,
            relayID: mutation.challenge.relayID,
            routeTokenHash: String(repeating: "a", count: 64),
            runtimeKeyFingerprint: mutation.challenge.runtimeKeyFingerprint,
            ticketGeneration: mutation.challenge.ticketGeneration,
            challenge: mutation.challenge.challenge,
            challengeExpiresAtEpochMillis: mutation.challenge.challengeExpiresAtEpochMillis
        )
        let mutatedSignature = try signer.sign(mutated.signedMessageData())
        try write(
            String(decoding: try RelayAllocationProofRequest(
                challenge: mutation.challenge.challenge,
                signatureBase64: mutatedSignature,
                runtimeIdentity: signer.identity
            ).requestLine(), as: UTF8.self),
            socket: mutation.socket
        )
        XCTAssertNil(try readLine(socket: mutation.socket))
    }

    func testWrongKeyAndRegistrationProofReplayCannotReplaceWaitingRuntime() throws {
        let signer = try SocketIdentitySigner()
        let wrongSigner = try SocketIdentitySigner()
        var inspectedServer: RelayServer?
        let port = try startServer(
            waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration(
                maximumDurationSeconds: 5,
                maximumPeersPerAuthenticatedIdentity: 1
            ),
            startedServer: { inspectedServer = $0 }
        )
        let allocation = try allocate(routeToken: "wrong-key", signer: signer, port: port)
        let server = try XCTUnwrap(inspectedServer)
        _ = try waitForSourceQuotaMetrics(server) { $0.activeConnections == 0 }

        let wrong = try connect(port: port)
        try write(runtimeHandshake(relayID: allocation.relayID, identity: wrongSigner.identity), socket: wrong)
        XCTAssertNil(try readLine(socket: wrong))
        Darwin.close(wrong)
        XCTAssertEqual(
            server.waitingPeerPolicyMetricsSnapshot().identityWaitingAdmissionRequestsTotal,
            0
        )

        let first = try connect(port: port)
        try write(runtimeHandshake(relayID: allocation.relayID, identity: signer.identity), socket: first)
        let firstChallenge = try registrationChallenge(socket: first)
        let firstSignature = try signer.sign(firstChallenge.signedMessageData())
        try write(registrationProof(challenge: firstChallenge.challenge, signature: firstSignature), socket: first)
        XCTAssertEqual(try readLine(socket: first), "AETHERLINK_RELAY registered crypto=2\n")
        XCTAssertEqual(
            server.waitingPeerPolicyMetricsSnapshot().identityWaitingPeersAdmittedTotal,
            1
        )

        let replay = try connect(port: port)
        defer {
            Darwin.close(first)
            Darwin.close(replay)
        }
        try write(runtimeHandshake(relayID: allocation.relayID, identity: signer.identity), socket: replay)
        _ = try registrationChallenge(socket: replay)
        try write(registrationProof(challenge: firstChallenge.challenge, signature: firstSignature), socket: replay)
        XCTAssertNil(try readLine(socket: replay))
        XCTAssertEqual(
            server.waitingPeerPolicyMetricsSnapshot().identityWaitingAdmissionRequestsTotal,
            1
        )

        let client = try connect(port: port)
        defer { Darwin.close(client) }
        try write(clientHandshake(relayID: allocation.relayID), socket: client)
        XCTAssertNotNil(try readLine(socket: first))
        XCTAssertEqual(
            server.waitingPeerPolicyMetricsSnapshot().authenticatedIdentityWaitingPeers,
            0
        )
    }

    func testRegistrationChallengeFieldMutationFailsBeforeMatcherInsertion() throws {
        let signer = try SocketIdentitySigner()
        let port = try startServer()
        let allocation = try allocate(routeToken: "registration-mutation", signer: signer, port: port)
        let runtime = try connect(port: port)
        defer { Darwin.close(runtime) }
        try write(runtimeHandshake(relayID: allocation.relayID, identity: signer.identity), socket: runtime)
        let challenge = try registrationChallenge(socket: runtime)
        let mutated = try RelayRuntimeRegistrationIdentityChallenge(
            relayID: challenge.relayID,
            relayExpiresAtEpochMillis: challenge.relayExpiresAtEpochMillis,
            relayNonce: challenge.relayNonce,
            runtimeKeyFingerprint: challenge.runtimeKeyFingerprint,
            ticketGeneration: challenge.ticketGeneration,
            sessionNonce: String(repeating: "f", count: 32),
            ephemeralKey: challenge.ephemeralKey,
            challenge: challenge.challenge,
            challengeExpiresAtEpochMillis: challenge.challengeExpiresAtEpochMillis
        )
        try write(
            registrationProof(
                challenge: challenge.challenge,
                signature: try signer.sign(mutated.signedMessageData())
            ),
            socket: runtime
        )
        XCTAssertNil(try readLine(socket: runtime))

        let probe = try connect(port: port)
        defer { Darwin.close(probe) }
        try write("AETHERLINK_RELAY probe \(allocation.relayID)\n", socket: probe)
        XCTAssertEqual(
            try readLine(socket: probe),
            "AETHERLINK_RELAY probe known=1 runtime_waiting=0\n"
        )
    }

    func testInvalidDurableStoreParentFailsBeforeRelayListens() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("RelayWriteFailure-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        let blockingFile = directory.appendingPathComponent("not-a-directory")
        try Data("block".utf8).write(to: blockingFile)
        let storeURL = blockingFile.appendingPathComponent("allocations.json")
        let server = RelayServer(
            configuration: RelayServerConfiguration(
                host: "127.0.0.1",
                port: try Self.freePort(),
                allocationStoreURL: storeURL
            )
        )
        XCTAssertThrowsError(try server.run()) { error in
            XCTAssertEqual(
                error as? RelayServerError,
                .allocationStoreLockFailed(storeURL.path)
            )
        }
    }

    func testConcurrentServerWithSameDurableAllocationStoreThrowsAlreadyOwned() throws {
        let storeURL = try temporaryStoreURL()
        let firstPort = try startServer(storeURL: storeURL)
        let connection = try connect(port: firstPort)
        Darwin.close(connection)

        let secondServer = RelayServer(
            configuration: RelayServerConfiguration(
                host: "127.0.0.1",
                port: try Self.freePort(),
                allocationStoreURL: storeURL
            )
        )
        XCTAssertThrowsError(try secondServer.run()) { error in
            XCTAssertEqual(
                error as? RelayServerError,
                .allocationStoreAlreadyOwned(storeURL.path)
            )
        }
    }

    func testSecondRunOnSameServerThrowsAlreadyRunningAndOriginalListenerStillWorks() throws {
        let storeURL = try temporaryStoreURL()
        let port = try Self.freePort()
        let server = RelayServer(
            configuration: RelayServerConfiguration(
                host: "127.0.0.1",
                port: port,
                allocationStoreURL: storeURL
            )
        )
        DispatchQueue.global(qos: .userInitiated).async { try! server.run() }

        let initialConnection = try connect(port: port)
        Darwin.close(initialConnection)

        XCTAssertThrowsError(try server.run()) { error in
            XCTAssertEqual(error as? RelayServerError, .serverAlreadyRunning)
        }

        let competingServer = RelayServer(
            configuration: RelayServerConfiguration(
                host: "127.0.0.1",
                port: try Self.freePort(),
                allocationStoreURL: storeURL
            )
        )
        XCTAssertThrowsError(try competingServer.run()) { error in
            XCTAssertEqual(
                error as? RelayServerError,
                .allocationStoreAlreadyOwned(storeURL.path)
            )
        }

        let probe = try connect(port: port)
        defer { Darwin.close(probe) }
        try write(
            "AETHERLINK_RELAY allocate same-instance-run crypto=2 preflight=1\n",
            socket: probe
        )
        XCTAssertEqual(
            try readLine(socket: probe),
            "AETHERLINK_RELAY preflight {\"allocation_auth\":\"runtime-p256-v1\",\"crypto_version\":2,\"preflight\":true}\n"
        )
        XCTAssertNil(try readLine(socket: probe))
    }

    func testBindFailureReleasesAllocationStoreOwnershipForRetainedServer() throws {
        let storeURL = try temporaryStoreURL()
        let occupied = try Self.makeListeningSocket()
        defer { Darwin.close(occupied.socket) }
        let configuration = RelayServerConfiguration(
            host: "127.0.0.1",
            port: occupied.port,
            allocationStoreURL: storeURL
        )
        let retainedServer = RelayServer(configuration: configuration)

        XCTAssertThrowsError(try retainedServer.run()) { error in
            guard let relayError = error as? RelayServerError,
                  case .bindFailed = relayError
            else {
                return XCTFail("Expected bind failure, got \(error)")
            }
        }

        XCTAssertThrowsError(try retainedServer.run()) { error in
            guard let relayError = error as? RelayServerError,
                  case .bindFailed = relayError
            else {
                return XCTFail("Expected retained-server bind retry failure, got \(error)")
            }
        }

        let reacquiringServer = RelayServer(configuration: configuration)
        XCTAssertThrowsError(try reacquiringServer.run()) { error in
            guard let relayError = error as? RelayServerError,
                  case .bindFailed = relayError
            else {
                return XCTFail("Expected bind failure after ownership reacquisition, got \(error)")
            }
        }
        withExtendedLifetime(retainedServer) {}
    }

    func testPairedClaimThenRenewSucceedsAndPersistsPinnedClient() throws {
        let storeURL = try temporaryStoreURL()
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let routeToken = "paired-success"
        let port = try startServer(storeURL: storeURL)
        let bootstrap = try allocate(
            routeToken: routeToken,
            signer: runtimeSigner,
            port: port
        )

        let claim = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            requestID: "claim-request",
            authorizationID: "claim-authorization"
        )
        XCTAssertEqual(claim.challenge.operation, .claim)
        XCTAssertEqual(claim.challenge.currentTicketGeneration, bootstrap.ticketGeneration)
        XCTAssertEqual(claim.challenge.currentRelayExpiresAtEpochMillis, bootstrap.relayExpiresAtEpochMillis)
        XCTAssertEqual(claim.challenge.currentRelayNonce, bootstrap.relayNonce)
        XCTAssertEqual(claim.challenge.nextTicketGeneration, bootstrap.ticketGeneration + 1)
        XCTAssertGreaterThan(
            claim.challenge.nextRelayExpiresAtEpochMillis,
            claim.challenge.currentRelayExpiresAtEpochMillis
        )
        XCTAssertNotEqual(claim.challenge.nextRelayNonce, claim.challenge.currentRelayNonce)
        let claimed = try completePairedRenewal(
            claim,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(claim.socket)
        XCTAssertEqual(claimed.ticketGeneration, 2)

        let renewal = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            requestID: "renew-request",
            authorizationID: "renew-authorization"
        )
        XCTAssertEqual(renewal.challenge.operation, .renew)
        XCTAssertEqual(renewal.challenge.currentTicketGeneration, claimed.ticketGeneration)
        XCTAssertEqual(renewal.challenge.currentRelayNonce, claimed.relayNonce)
        let renewed = try completePairedRenewal(
            renewal,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(renewal.socket)
        XCTAssertEqual(renewed.ticketGeneration, 3)

        let envelope = try XCTUnwrap(
            try JSONSerialization.jsonObject(
                with: Data(contentsOf: storeURL)
            ) as? [String: Any]
        )
        let tickets = try XCTUnwrap(envelope["allocations"] as? [[String: Any]])
        XCTAssertEqual(tickets.first?["authorization_mode"] as? String, "paired_device_p256_v1")
        XCTAssertEqual(
            tickets.first?["paired_client_key_fingerprint"] as? String,
            clientSigner.identity.fingerprint
        )
    }

    func testPairedClaimChallengesClientAndAdmitsValidPinnedProof() throws {
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let port = try startServer()
        let bootstrap = try allocate(
            routeToken: "paired-client-admission",
            signer: runtimeSigner,
            port: port
        )
        let claim = try beginPairedRenewal(
            routeToken: "paired-client-admission",
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port
        )
        let allocation = try completePairedRenewal(
            claim,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(claim.socket)
        XCTAssertNotEqual(allocation.relayID, bootstrap.relayID)

        let runtime = try connect(port: port)
        let client = try connect(port: port)
        defer {
            Darwin.close(runtime)
            Darwin.close(client)
        }
        try authorizeRuntime(socket: runtime, allocation: allocation, signer: runtimeSigner)
        XCTAssertEqual(try readLine(socket: runtime), "AETHERLINK_RELAY registered crypto=2\n")

        try write(clientHandshake(relayID: allocation.relayID), socket: client)
        let challenge = try pairedClientRegistrationChallenge(socket: client)
        XCTAssertEqual(challenge.relayID, allocation.relayID)
        XCTAssertEqual(challenge.ticketGeneration, allocation.ticketGeneration)
        XCTAssertEqual(challenge.relayNonce, allocation.relayNonce)
        XCTAssertEqual(challenge.runtimeKeyFingerprint, runtimeSigner.identity.fingerprint)
        XCTAssertEqual(challenge.clientKeyFingerprint, clientSigner.identity.fingerprint)
        try submitPairedClientProof(
            challenge: challenge,
            signer: clientSigner,
            socket: client
        )

        try assertReadyPair(runtime: runtime, client: client)
    }

    func testRejectedClientProofsCannotDisplaceVerifiedWaitingRuntime() throws {
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let wrongSigner = try SocketIdentitySigner()
        let routeToken = "paired-client-proof-failures"
        let port = try startServer()
        _ = try allocate(routeToken: routeToken, signer: runtimeSigner, port: port)
        let claim = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port
        )
        let allocation = try completePairedRenewal(
            claim,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(claim.socket)

        let runtime = try connect(port: port)
        defer { Darwin.close(runtime) }
        try authorizeRuntime(socket: runtime, allocation: allocation, signer: runtimeSigner)
        XCTAssertEqual(try readLine(socket: runtime), "AETHERLINK_RELAY registered crypto=2\n")

        let missing = try beginPairedClientRegistration(allocation: allocation, port: port)
        try write(
            "AETHERLINK_RELAY client_registration_proof crypto=2 " +
                "challenge=\(missing.challenge.challenge) " +
                "client_public_key=\(clientSigner.identity.publicKeyBase64)\n",
            socket: missing.socket
        )
        XCTAssertNil(try readLine(socket: missing.socket))
        Darwin.close(missing.socket)
        try assertRuntimeStillWaiting(relayID: allocation.relayID, port: port)

        let wrong = try beginPairedClientRegistration(allocation: allocation, port: port)
        let wrongRequest = try RelayPairedClientRegistrationProofRequest(
            challenge: wrong.challenge.challenge,
            clientPublicKeyBase64: wrongSigner.identity.publicKeyBase64,
            clientSignatureBase64: wrongSigner.sign(wrong.challenge.transcriptData())
        )
        try write(String(decoding: wrongRequest.requestLine(), as: UTF8.self), socket: wrong.socket)
        XCTAssertNil(try readLine(socket: wrong.socket))
        Darwin.close(wrong.socket)
        try assertRuntimeStillWaiting(relayID: allocation.relayID, port: port)

        let abandoned = try beginPairedClientRegistration(allocation: allocation, port: port)
        let replayedRequest = try pairedClientProofRequest(
            challenge: abandoned.challenge,
            signer: clientSigner
        )
        Darwin.close(abandoned.socket)
        let replay = try beginPairedClientRegistration(allocation: allocation, port: port)
        XCTAssertNotEqual(replay.challenge.challenge, abandoned.challenge.challenge)
        try write(String(decoding: replayedRequest.requestLine(), as: UTF8.self), socket: replay.socket)
        XCTAssertNil(try readLine(socket: replay.socket))
        Darwin.close(replay.socket)
        try assertRuntimeStillWaiting(relayID: allocation.relayID, port: port)

        let mutation = try beginPairedClientRegistration(allocation: allocation, port: port)
        let mutatedChallenge = try pairedClientChallenge(
            copying: mutation.challenge,
            sessionNonce: String(repeating: "a", count: 32)
        )
        let mutatedRequest = try RelayPairedClientRegistrationProofRequest(
            challenge: mutation.challenge.challenge,
            clientPublicKeyBase64: clientSigner.identity.publicKeyBase64,
            clientSignatureBase64: clientSigner.sign(mutatedChallenge.transcriptData())
        )
        try write(String(decoding: mutatedRequest.requestLine(), as: UTF8.self), socket: mutation.socket)
        XCTAssertNil(try readLine(socket: mutation.socket))
        Darwin.close(mutation.socket)
        try assertRuntimeStillWaiting(relayID: allocation.relayID, port: port)

        let validClient = try connect(port: port)
        defer { Darwin.close(validClient) }
        try authorizePairedClient(
            socket: validClient,
            allocation: allocation,
            signer: clientSigner
        )
        try assertReadyPair(runtime: runtime, client: validClient)
    }

    func testActiveRoomRejectsSecondPairUntilBridgeClosesThenReconnects() throws {
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let routeToken = "paired-active-room"
        let port = try startServer()
        _ = try allocate(routeToken: routeToken, signer: runtimeSigner, port: port)
        let claim = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port
        )
        let allocation = try completePairedRenewal(
            claim,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(claim.socket)

        let firstRuntime = try connect(port: port)
        let firstClient = try connect(port: port)
        try authorizeRuntime(socket: firstRuntime, allocation: allocation, signer: runtimeSigner)
        XCTAssertEqual(try readLine(socket: firstRuntime), "AETHERLINK_RELAY registered crypto=2\n")
        try authorizePairedClient(
            socket: firstClient,
            allocation: allocation,
            signer: clientSigner
        )
        try assertReadyPair(runtime: firstRuntime, client: firstClient)

        let rejectedRuntime = try connect(port: port)
        try authorizeRuntime(socket: rejectedRuntime, allocation: allocation, signer: runtimeSigner)
        XCTAssertNil(try readLine(socket: rejectedRuntime))
        Darwin.close(rejectedRuntime)

        let rejectedClient = try connect(port: port)
        try authorizePairedClient(
            socket: rejectedClient,
            allocation: allocation,
            signer: clientSigner
        )
        XCTAssertNil(try readLine(socket: rejectedClient))
        Darwin.close(rejectedClient)

        Darwin.shutdown(firstRuntime, SHUT_RDWR)
        Darwin.shutdown(firstClient, SHUT_RDWR)
        Darwin.close(firstRuntime)
        Darwin.close(firstClient)

        let reconnectedRuntime = try connectWaitingRuntime(
            allocation: allocation,
            signer: runtimeSigner,
            port: port
        )
        let reconnectedClient = try connect(port: port)
        defer {
            Darwin.close(reconnectedRuntime)
            Darwin.close(reconnectedClient)
        }
        try authorizePairedClient(
            socket: reconnectedClient,
            allocation: allocation,
            signer: clientSigner
        )
        try assertReadyPair(runtime: reconnectedRuntime, client: reconnectedClient)
    }

    func testPairedRenewalInvalidatesStaleWaitingGeneration() throws {
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let routeToken = "paired-stale-waiting-generation"
        let port = try startServer()
        _ = try allocate(routeToken: routeToken, signer: runtimeSigner, port: port)
        let claim = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port
        )
        let claimed = try completePairedRenewal(
            claim,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(claim.socket)

        let staleRuntime = try connect(port: port)
        defer { Darwin.close(staleRuntime) }
        try authorizeRuntime(socket: staleRuntime, allocation: claimed, signer: runtimeSigner)
        XCTAssertEqual(try readLine(socket: staleRuntime), "AETHERLINK_RELAY registered crypto=2\n")
        try assertRuntimeStillWaiting(relayID: claimed.relayID, port: port)

        let renewal = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            requestID: "stale-waiting-renewal",
            authorizationID: "stale-waiting-authorization"
        )
        let renewed = try completePairedRenewal(
            renewal,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(renewal.socket)
        XCTAssertEqual(renewed.ticketGeneration, claimed.ticketGeneration + 1)
        XCTAssertNil(try readLine(socket: staleRuntime))

        let probe = try connect(port: port)
        defer { Darwin.close(probe) }
        try write("AETHERLINK_RELAY probe \(renewed.relayID)\n", socket: probe)
        XCTAssertEqual(
            try readLine(socket: probe),
            "AETHERLINK_RELAY probe known=1 runtime_waiting=0\n"
        )

        let currentRuntime = try connect(port: port)
        defer { Darwin.close(currentRuntime) }
        try authorizeRuntime(socket: currentRuntime, allocation: renewed, signer: runtimeSigner)
        XCTAssertEqual(try readLine(socket: currentRuntime), "AETHERLINK_RELAY registered crypto=2\n")
    }

    func testTwoPairScopedRoomsBridgeConcurrentlyWithoutCrossTalk() throws {
        let runtimeSigner = try SocketIdentitySigner()
        let firstClientSigner = try SocketIdentitySigner()
        let secondClientSigner = try SocketIdentitySigner()
        let port = try startServer()
        let firstRouteToken = "pair-room-concurrent-a"
        let secondRouteToken = "pair-room-concurrent-b"

        _ = try allocate(routeToken: firstRouteToken, signer: runtimeSigner, port: port)
        let firstClaim = try beginPairedRenewal(
            routeToken: firstRouteToken,
            runtimeSigner: runtimeSigner,
            clientSigner: firstClientSigner,
            port: port
        )
        let firstAllocation = try completePairedRenewal(
            firstClaim,
            runtimeSigner: runtimeSigner,
            clientSigner: firstClientSigner
        )
        Darwin.close(firstClaim.socket)

        _ = try allocate(routeToken: secondRouteToken, signer: runtimeSigner, port: port)
        let secondClaim = try beginPairedRenewal(
            routeToken: secondRouteToken,
            runtimeSigner: runtimeSigner,
            clientSigner: secondClientSigner,
            port: port
        )
        let secondAllocation = try completePairedRenewal(
            secondClaim,
            runtimeSigner: runtimeSigner,
            clientSigner: secondClientSigner
        )
        Darwin.close(secondClaim.socket)
        XCTAssertNotEqual(firstAllocation.relayID, secondAllocation.relayID)

        let firstRuntime = try connect(port: port)
        let firstClient = try connect(port: port)
        let secondRuntime = try connect(port: port)
        let secondClient = try connect(port: port)
        defer {
            Darwin.close(firstRuntime)
            Darwin.close(firstClient)
            Darwin.close(secondRuntime)
            Darwin.close(secondClient)
        }

        try authorizeRuntime(
            socket: firstRuntime,
            allocation: firstAllocation,
            signer: runtimeSigner
        )
        XCTAssertEqual(try readLine(socket: firstRuntime), "AETHERLINK_RELAY registered crypto=2\n")
        try authorizePairedClient(
            socket: firstClient,
            allocation: firstAllocation,
            signer: firstClientSigner
        )
        try assertReadyPair(runtime: firstRuntime, client: firstClient)

        try authorizeRuntime(
            socket: secondRuntime,
            allocation: secondAllocation,
            signer: runtimeSigner
        )
        XCTAssertEqual(try readLine(socket: secondRuntime), "AETHERLINK_RELAY registered crypto=2\n")
        try authorizePairedClient(
            socket: secondClient,
            allocation: secondAllocation,
            signer: secondClientSigner
        )
        try assertReadyPair(runtime: secondRuntime, client: secondClient)

        var shortTimeout = timeval(tv_sec: 0, tv_usec: 100_000)
        setsockopt(
            secondRuntime,
            SOL_SOCKET,
            SO_RCVTIMEO,
            &shortTimeout,
            socklen_t(MemoryLayout<timeval>.size)
        )
        try write("first-room-frame\n", socket: firstClient)
        XCTAssertEqual(try readLine(socket: firstRuntime), "first-room-frame\n")
        XCTAssertNil(try readLine(socket: secondRuntime))

        try write("second-room-frame\n", socket: secondClient)
        XCTAssertEqual(try readLine(socket: secondRuntime), "second-room-frame\n")
    }

    func testPairedProofRejectsMissingWrongAndSwappedRoleSignatures() throws {
        enum FailureCase: String, CaseIterable {
            case missingClient
            case wrongRuntime
            case wrongClient
            case swappedRoles
        }

        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let wrongRuntimeSigner = try SocketIdentitySigner()
        let wrongClientSigner = try SocketIdentitySigner()
        let port = try startServer(
            sourceRateLimitConfiguration: RelaySourceRateLimitConfiguration(
                allocationMutationBurst: 16
            )
        )

        for failure in FailureCase.allCases {
            let routeToken = "paired-proof-\(failure.rawValue)"
            _ = try allocate(routeToken: routeToken, signer: runtimeSigner, port: port)
            let pending = try beginPairedRenewal(
                routeToken: routeToken,
                runtimeSigner: runtimeSigner,
                clientSigner: clientSigner,
                port: port,
                requestID: "request-\(failure.rawValue)",
                authorizationID: "authorization-\(failure.rawValue)"
            )
            let validRuntime = try runtimeSigner.runtimeProof(
                challenge: pending.challenge
            ).signatureBase64
            let validClient = try clientSigner.clientProof(
                challenge: pending.challenge
            ).signatureBase64
            let line: String
            switch failure {
            case .missingClient:
                line = "AETHERLINK_RELAY paired_allocation_proof crypto=2 " +
                    "challenge=\(pending.challenge.challenge) " +
                    "runtime_signature=\(validRuntime)\n"
            case .wrongRuntime:
                let proof = try RelayPairedAllocationProofRequest(
                    challenge: pending.challenge.challenge,
                    runtimeSignatureBase64: wrongRuntimeSigner.sign(
                        pending.challenge.runtimeSignedMessageData()
                    ),
                    clientSignatureBase64: validClient,
                    renewalRequest: pending.request
                )
                line = String(decoding: proof.requestLine(), as: UTF8.self)
            case .wrongClient:
                let proof = try RelayPairedAllocationProofRequest(
                    challenge: pending.challenge.challenge,
                    runtimeSignatureBase64: validRuntime,
                    clientSignatureBase64: wrongClientSigner.sign(
                        pending.challenge.clientSignedMessageData()
                    ),
                    renewalRequest: pending.request
                )
                line = String(decoding: proof.requestLine(), as: UTF8.self)
            case .swappedRoles:
                let proof = try RelayPairedAllocationProofRequest(
                    challenge: pending.challenge.challenge,
                    runtimeSignatureBase64: validClient,
                    clientSignatureBase64: validRuntime,
                    renewalRequest: pending.request
                )
                line = String(decoding: proof.requestLine(), as: UTF8.self)
            }
            try write(line, socket: pending.socket)
            XCTAssertNil(try readLine(socket: pending.socket), failure.rawValue)
            Darwin.close(pending.socket)

            let retry = try beginPairedRenewal(
                routeToken: routeToken,
                runtimeSigner: runtimeSigner,
                clientSigner: clientSigner,
                port: port,
                requestID: "retry-\(failure.rawValue)",
                authorizationID: "retry-authorization-\(failure.rawValue)"
            )
            XCTAssertEqual(retry.challenge.operation, .claim, failure.rawValue)
            Darwin.close(retry.socket)
        }
    }

    func testPairedChallengeMutationAndExpiryFailWithoutCommit() throws {
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let port = try startServer()
        let routeToken = "paired-mutation"
        _ = try allocate(routeToken: routeToken, signer: runtimeSigner, port: port)
        let pending = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port
        )
        let mutated = try PairedRelayAllocationAuthorizationChallenge(
            operation: pending.challenge.operation,
            requestID: pending.challenge.requestID,
            authorizationID: pending.challenge.authorizationID,
            currentRelayID: pending.challenge.currentRelayID,
            nextRelayID: pending.challenge.nextRelayID,
            routeTokenHash: pending.challenge.routeTokenHash,
            runtimeKeyFingerprint: pending.challenge.runtimeKeyFingerprint,
            clientKeyFingerprint: pending.challenge.clientKeyFingerprint,
            currentTicketGeneration: pending.challenge.currentTicketGeneration,
            nextTicketGeneration: pending.challenge.nextTicketGeneration,
            currentRelayExpiresAtEpochMillis: pending.challenge.currentRelayExpiresAtEpochMillis,
            currentRelayNonce: pending.challenge.currentRelayNonce,
            nextRelayExpiresAtEpochMillis: pending.challenge.nextRelayExpiresAtEpochMillis,
            nextRelayNonce: "\(pending.challenge.nextRelayNonce)-mutated",
            challenge: pending.challenge.challenge,
            challengeExpiresAtEpochMillis: pending.challenge.challengeExpiresAtEpochMillis,
            transportBinding: pending.challenge.transportBinding
        )
        let mutatedProof = try RelayPairedAllocationProofRequest(
            challenge: pending.challenge.challenge,
            runtimeSignatureBase64: runtimeSigner.runtimeProof(
                challenge: mutated
            ).signatureBase64,
            clientSignatureBase64: clientSigner.clientProof(
                challenge: mutated
            ).signatureBase64,
            renewalRequest: pending.request
        )
        try write(
            String(decoding: mutatedProof.requestLine(), as: UTF8.self),
            socket: pending.socket
        )
        XCTAssertNil(try readLine(socket: pending.socket))
        Darwin.close(pending.socket)

        let retry = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            requestID: "mutation-retry",
            authorizationID: "mutation-retry-authorization"
        )
        XCTAssertEqual(retry.challenge.operation, .claim)
        Darwin.close(retry.socket)

        let expiringPort = try startServer(identityChallengeTTL: 0.01)
        let expiringRoute = "paired-expiry"
        _ = try allocate(
            routeToken: expiringRoute,
            signer: runtimeSigner,
            port: expiringPort
        )
        let expiring = try beginPairedRenewal(
            routeToken: expiringRoute,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: expiringPort
        )
        Thread.sleep(forTimeInterval: 0.03)
        let expiredProof = try pairedProof(
            expiring,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        try write(
            String(decoding: expiredProof.requestLine(), as: UTF8.self),
            socket: expiring.socket
        )
        XCTAssertNil(try readLine(socket: expiring.socket))
        Darwin.close(expiring.socket)
    }

    func testPairedProofReplayAndConcurrentGenerationRaceFailCAS() throws {
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let port = try startServer()
        let routeToken = "paired-race"
        _ = try allocate(routeToken: routeToken, signer: runtimeSigner, port: port)
        let first = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            requestID: "race-first",
            authorizationID: "race-first-authorization"
        )
        let second = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            requestID: "race-second",
            authorizationID: "race-second-authorization"
        )
        XCTAssertEqual(first.challenge.currentTicketGeneration, second.challenge.currentTicketGeneration)
        let firstProof = try pairedProof(
            first,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        try write(String(decoding: firstProof.requestLine(), as: UTF8.self), socket: first.socket)
        _ = try RelayAllocationV2.parseResponseLine(try XCTUnwrap(readLine(socket: first.socket)))
        Darwin.close(first.socket)

        let secondProof = try pairedProof(
            second,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        try write(String(decoding: secondProof.requestLine(), as: UTF8.self), socket: second.socket)
        XCTAssertNil(try readLine(socket: second.socket))
        Darwin.close(second.socket)

        let renewal = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            requestID: "replay-target",
            authorizationID: "replay-target-authorization"
        )
        XCTAssertEqual(renewal.challenge.operation, .renew)
        try write(String(decoding: firstProof.requestLine(), as: UTF8.self), socket: renewal.socket)
        XCTAssertNil(try readLine(socket: renewal.socket))
        Darwin.close(renewal.socket)
    }

    func testPairedRenewalRejectsTokenSubstitutionDowngradeAndAbsentTicketBeforeChallenge() throws {
        let token = "paired-allocation-token"
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let substituteClient = try SocketIdentitySigner()
        let port = try startServer(allocationToken: token)
        let routeToken = "paired-policy"
        _ = try allocate(
            routeToken: routeToken,
            signer: runtimeSigner,
            port: port,
            allocationToken: token
        )

        for suppliedToken in [nil, "wrong-token"] as [String?] {
            let rejected = try openPairedRenewal(
                routeToken: routeToken,
                runtimeSigner: runtimeSigner,
                clientSigner: clientSigner,
                port: port,
                allocationToken: suppliedToken
            )
            XCTAssertNil(try readLine(socket: rejected.socket))
            Darwin.close(rejected.socket)
        }

        let claim = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            allocationToken: token
        )
        _ = try completePairedRenewal(
            claim,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(claim.socket)

        let substitution = try openPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: substituteClient,
            port: port,
            allocationToken: token
        )
        XCTAssertNil(try readLine(socket: substitution.socket))
        Darwin.close(substitution.socket)

        let downgrade = try connect(port: port)
        let identity = runtimeSigner.identity
        try write(
            "AETHERLINK_RELAY allocate \(routeToken) crypto=2 " +
                "allocation_auth=runtime-p256-v1 runtime_key_fingerprint=\(identity.fingerprint) " +
                "runtime_public_key=\(identity.publicKeyBase64) allocation_token=\(token)\n",
            socket: downgrade
        )
        XCTAssertNil(try readLine(socket: downgrade))
        Darwin.close(downgrade)

        let absent = try openPairedRenewal(
            routeToken: "paired-absent",
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            allocationToken: token
        )
        XCTAssertNil(try readLine(socket: absent.socket))
        Darwin.close(absent.socket)
    }

    func testPairedClaimCanRecoverExpiredPersistedTombstone() throws {
        let runtimeSigner = try SocketIdentitySigner()
        let clientSigner = try SocketIdentitySigner()
        let routeToken = "paired-expired-tombstone"
        let port = try startServer(allocationTTL: 0.01)
        let bootstrap = try allocate(
            routeToken: routeToken,
            signer: runtimeSigner,
            port: port
        )
        Thread.sleep(forTimeInterval: 0.03)
        XCTAssertLessThanOrEqual(
            bootstrap.relayExpiresAtEpochMillis,
            Int64((Date().timeIntervalSince1970 * 1_000).rounded())
        )

        let claim = try beginPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port
        )
        XCTAssertEqual(claim.challenge.operation, .claim)
        let recovered = try completePairedRenewal(
            claim,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        Darwin.close(claim.socket)
        XCTAssertEqual(recovered.ticketGeneration, bootstrap.ticketGeneration + 1)
        XCTAssertGreaterThan(
            recovered.relayExpiresAtEpochMillis,
            bootstrap.relayExpiresAtEpochMillis
        )
    }

    private func allocate(
        routeToken: String,
        signer: SocketIdentitySigner,
        port: UInt16,
        allocationToken: String? = nil
    ) throws -> RelayAllocationV2 {
        let pending = try beginAllocation(
            routeToken: routeToken,
            signer: signer,
            port: port,
            allocationToken: allocationToken
        )
        defer { Darwin.close(pending.socket) }
        let signature = try signer.sign(pending.challenge.signedMessageData())
        let proof = try RelayAllocationProofRequest(
            challenge: pending.challenge.challenge,
            signatureBase64: signature,
            runtimeIdentity: signer.identity
        )
        try write(String(decoding: proof.requestLine(), as: UTF8.self), socket: pending.socket)
        return try RelayAllocationV2.parseResponseLine(try XCTUnwrap(readLine(socket: pending.socket)))
    }

    private func sendPreflight(routeToken: String, port: UInt16) throws -> String? {
        let socket = try connect(port: port)
        defer { Darwin.close(socket) }
        try write(
            "AETHERLINK_RELAY allocate \(routeToken) crypto=2 preflight=1\n",
            socket: socket
        )
        return try readLine(socket: socket)
    }

    private func beginAllocation(
        routeToken: String,
        signer: SocketIdentitySigner,
        port: UInt16,
        allocationToken: String? = nil
    ) throws -> (socket: Int32, challenge: RelayAllocationIdentityChallenge) {
        let socket = try connect(port: port)
        let identity = signer.identity
        var line =
            "AETHERLINK_RELAY allocate \(routeToken) crypto=2 " +
            "allocation_auth=runtime-p256-v1 runtime_key_fingerprint=\(identity.fingerprint) " +
            "runtime_public_key=\(identity.publicKeyBase64)"
        if let allocationToken {
            line += " allocation_token=\(allocationToken)"
        }
        try write(
            "\(line)\n",
            socket: socket
        )
        let response = try RelayAllocationChallengeResponse.parseResponseLine(
            try XCTUnwrap(readLine(socket: socket))
        )
        return (socket, response.challenge)
    }

    private func beginPairedRenewal(
        routeToken: String,
        runtimeSigner: SocketIdentitySigner,
        clientSigner: SocketIdentitySigner,
        port: UInt16,
        allocationToken: String? = nil,
        requestID: String = "socket-request",
        authorizationID: String = "socket-authorization",
        transportBinding: String = String(repeating: "d", count: 64)
    ) throws -> (
        socket: Int32,
        request: RelayPairedAllocationRenewalRequest,
        challenge: PairedRelayAllocationAuthorizationChallenge
    ) {
        let opened = try openPairedRenewal(
            routeToken: routeToken,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner,
            port: port,
            allocationToken: allocationToken,
            requestID: requestID,
            authorizationID: authorizationID,
            transportBinding: transportBinding
        )
        let challenge = try RelayPairedAllocationChallengeResponse.parseResponseLine(
            try XCTUnwrap(readLine(socket: opened.socket))
        ).challenge
        return (opened.socket, opened.request, challenge)
    }

    private func openPairedRenewal(
        routeToken: String,
        runtimeSigner: SocketIdentitySigner,
        clientSigner: SocketIdentitySigner,
        port: UInt16,
        allocationToken: String? = nil,
        requestID: String = "socket-request",
        authorizationID: String = "socket-authorization",
        transportBinding: String = String(repeating: "d", count: 64)
    ) throws -> (socket: Int32, request: RelayPairedAllocationRenewalRequest) {
        let request = try RelayPairedAllocationRenewalRequest(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeSigner.identity.fingerprint,
            runtimePublicKey: runtimeSigner.identity.publicKeyBase64,
            clientKeyFingerprint: clientSigner.identity.fingerprint,
            clientPublicKey: clientSigner.identity.publicKeyBase64,
            requestID: requestID,
            authorizationID: authorizationID,
            transportBinding: transportBinding,
            allocationToken: allocationToken
        )
        let socket = try connect(port: port)
        try write(String(decoding: request.requestLine(), as: UTF8.self), socket: socket)
        return (socket, request)
    }

    private func completePairedRenewal(
        _ pending: (
            socket: Int32,
            request: RelayPairedAllocationRenewalRequest,
            challenge: PairedRelayAllocationAuthorizationChallenge
        ),
        runtimeSigner: SocketIdentitySigner,
        clientSigner: SocketIdentitySigner
    ) throws -> RelayAllocationV2 {
        let proof = try pairedProof(
            pending,
            runtimeSigner: runtimeSigner,
            clientSigner: clientSigner
        )
        try write(String(decoding: proof.requestLine(), as: UTF8.self), socket: pending.socket)
        return try RelayAllocationV2.parseResponseLine(
            try XCTUnwrap(readLine(socket: pending.socket))
        )
    }

    private func pairedProof(
        _ pending: (
            socket: Int32,
            request: RelayPairedAllocationRenewalRequest,
            challenge: PairedRelayAllocationAuthorizationChallenge
        ),
        runtimeSigner: SocketIdentitySigner,
        clientSigner: SocketIdentitySigner
    ) throws -> RelayPairedAllocationProofRequest {
        let runtimeProof = try runtimeSigner.runtimeProof(challenge: pending.challenge)
        let clientProof = try clientSigner.clientProof(challenge: pending.challenge)
        return try RelayPairedAllocationProofRequest(
            challenge: pending.challenge.challenge,
            runtimeSignatureBase64: runtimeProof.signatureBase64,
            clientSignatureBase64: clientProof.signatureBase64,
            renewalRequest: pending.request
        )
    }

    private func beginPairedClientRegistration(
        allocation: RelayAllocationV2,
        port: UInt16
    ) throws -> (socket: Int32, challenge: PairedClientRelayRegistrationChallenge) {
        let socket = try connect(port: port)
        try write(clientHandshake(relayID: allocation.relayID), socket: socket)
        return (socket, try pairedClientRegistrationChallenge(socket: socket))
    }

    private func pairedClientRegistrationChallenge(
        socket: Int32
    ) throws -> PairedClientRelayRegistrationChallenge {
        try RelayPairedClientRegistrationChallengeResponse.parseResponseLine(
            try XCTUnwrap(readLine(socket: socket))
        ).challenge
    }

    private func pairedClientProofRequest(
        challenge: PairedClientRelayRegistrationChallenge,
        signer: SocketIdentitySigner
    ) throws -> RelayPairedClientRegistrationProofRequest {
        let proof = try signer.clientRegistrationProof(challenge: challenge)
        return try RelayPairedClientRegistrationProofRequest(
            challenge: challenge.challenge,
            clientPublicKeyBase64: proof.clientPublicKeyBase64,
            clientSignatureBase64: proof.clientSignatureBase64
        )
    }

    private func submitPairedClientProof(
        challenge: PairedClientRelayRegistrationChallenge,
        signer: SocketIdentitySigner,
        socket: Int32
    ) throws {
        let request = try pairedClientProofRequest(challenge: challenge, signer: signer)
        try write(String(decoding: request.requestLine(), as: UTF8.self), socket: socket)
    }

    private func authorizePairedClient(
        socket: Int32,
        allocation: RelayAllocationV2,
        signer: SocketIdentitySigner
    ) throws {
        try write(clientHandshake(relayID: allocation.relayID), socket: socket)
        try submitPairedClientProof(
            challenge: pairedClientRegistrationChallenge(socket: socket),
            signer: signer,
            socket: socket
        )
    }

    private func pairedClientChallenge(
        copying challenge: PairedClientRelayRegistrationChallenge,
        sessionNonce: String
    ) throws -> PairedClientRelayRegistrationChallenge {
        try PairedClientRelayRegistrationChallenge(
            scheme: challenge.scheme,
            protocolVersion: challenge.protocolVersion,
            role: challenge.role,
            relayID: challenge.relayID,
            relayExpiresAtEpochMillis: challenge.relayExpiresAtEpochMillis,
            relayNonce: challenge.relayNonce,
            runtimeKeyFingerprint: challenge.runtimeKeyFingerprint,
            clientKeyFingerprint: challenge.clientKeyFingerprint,
            ticketGeneration: challenge.ticketGeneration,
            sessionNonce: sessionNonce,
            ephemeralKey: challenge.ephemeralKey,
            challenge: challenge.challenge,
            challengeExpiresAtEpochMillis: challenge.challengeExpiresAtEpochMillis
        )
    }

    private func assertRuntimeStillWaiting(relayID: String, port: UInt16) throws {
        let probe = try connect(port: port)
        defer { Darwin.close(probe) }
        try write("AETHERLINK_RELAY probe \(relayID)\n", socket: probe)
        XCTAssertEqual(
            try readLine(socket: probe),
            "AETHERLINK_RELAY probe known=1 runtime_waiting=1\n"
        )
    }

    private func assertReadyPair(runtime: Int32, client: Int32) throws {
        XCTAssertEqual(
            try readLine(socket: runtime),
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=\(Self.clientNonce) " +
                "peer_ephemeral_key=\(Self.clientEphemeralKey)\n"
        )
        XCTAssertEqual(
            try readLine(socket: client),
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=\(Self.runtimeNonce) " +
                "peer_ephemeral_key=\(Self.runtimeEphemeralKey)\n"
        )
    }

    private func connectWaitingRuntime(
        allocation: RelayAllocationV2,
        signer: SocketIdentitySigner,
        port: UInt16
    ) throws -> Int32 {
        for _ in 0..<50 {
            let socket = try connect(port: port)
            try authorizeRuntime(socket: socket, allocation: allocation, signer: signer)
            if try readLine(socket: socket) == "AETHERLINK_RELAY registered crypto=2\n" {
                return socket
            }
            Darwin.close(socket)
            Thread.sleep(forTimeInterval: 0.01)
        }
        XCTFail("Active relay room did not release after the bridge closed")
        throw SocketTestError.io
    }

    private func authorizeRuntime(
        socket: Int32,
        allocation: RelayAllocationV2,
        signer: SocketIdentitySigner
    ) throws {
        try write(runtimeHandshake(relayID: allocation.relayID, identity: signer.identity), socket: socket)
        let challenge = try registrationChallenge(socket: socket)
        let signature = try signer.sign(challenge.signedMessageData())
        try write(registrationProof(challenge: challenge.challenge, signature: signature), socket: socket)
    }

    private func registrationChallenge(socket: Int32) throws -> RelayRuntimeRegistrationIdentityChallenge {
        try RelayRuntimeRegistrationChallengeResponse.parseResponseLine(
            try XCTUnwrap(readLine(socket: socket))
        ).challenge
    }

    private func runtimeHandshake(relayID: String, identity: RelayRuntimeIdentity) -> String {
        "AETHERLINK_RELAY runtime \(relayID) crypto=2 session_nonce=\(Self.runtimeNonce) " +
            "ephemeral_key=\(Self.runtimeEphemeralKey) runtime_key_fingerprint=\(identity.fingerprint)\n"
    }

    private func clientHandshake(relayID: String) -> String {
        "AETHERLINK_RELAY client \(relayID) crypto=2 session_nonce=\(Self.clientNonce) " +
            "ephemeral_key=\(Self.clientEphemeralKey)\n"
    }

    private func registrationProof(challenge: String, signature: String) -> String {
        "AETHERLINK_RELAY registration_proof crypto=2 challenge=\(challenge) signature=\(signature)\n"
    }

    private func waitForProbe(relayID: String, port: UInt16) throws -> String {
        for _ in 0..<80 {
            let socket = try connect(port: port)
            do {
                try write("AETHERLINK_RELAY probe \(relayID)\n", socket: socket)
                if let response = try readLine(socket: socket) {
                    Darwin.close(socket)
                    return response
                }
            } catch {
                // The previous connection may still own the final permit.
            }
            Darwin.close(socket)
            Thread.sleep(forTimeInterval: 0.025)
        }
        throw SocketTestError.io
    }

    private func startServer(
        host: String = "127.0.0.1",
        storeURL: URL? = nil,
        allocationToken: String? = nil,
        allocationTTL: TimeInterval = RelayServerConfiguration.defaultAllocationTTLSeconds,
        identityChallengeTTL: TimeInterval = 30,
        probePolicy: RelayProbePolicy = .loopbackOnly,
        controlLineReadTimeout: TimeInterval = RelayServerConfiguration.defaultControlLineReadTimeoutSeconds,
        maximumConcurrentConnections: Int = RelayServerConfiguration.defaultMaximumConcurrentConnections,
        sourceQuotaConfiguration: RelaySourceQuotaConfiguration = .init(),
        waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration = .init(),
        sourceRateLimitConfiguration: RelaySourceRateLimitConfiguration = .init(),
        startedServer: ((RelayServer) -> Void)? = nil,
        sourceRateLimitLog: @escaping @Sendable (String) -> Void = { _ in },
        sourceQuotaLog: @escaping @Sendable (String) -> Void = { _ in },
        waitingPeerPolicyLog: @escaping @Sendable (String) -> Void = { _ in }
    ) throws -> UInt16 {
        let port = try Self.freePort()
        let server = RelayServer(
            configuration: RelayServerConfiguration(
                host: host,
                port: port,
                allocationTTLSeconds: allocationTTL,
                allocationStoreURL: storeURL,
                allocationToken: allocationToken,
                probePolicy: probePolicy,
                controlLineReadTimeoutSeconds: controlLineReadTimeout,
                maximumConcurrentConnections: maximumConcurrentConnections,
                sourceQuotaConfiguration: sourceQuotaConfiguration,
                waitingPeerPolicyConfiguration: waitingPeerPolicyConfiguration,
                sourceRateLimitConfiguration: sourceRateLimitConfiguration
            ),
            identityChallengeTTL: identityChallengeTTL,
            sourceRateLimitClock: { ProcessInfo.processInfo.systemUptime },
            sourceRateLimitLog: sourceRateLimitLog,
            sourceQuotaLog: sourceQuotaLog,
            waitingPeerPolicyLog: waitingPeerPolicyLog
        )
        startedServer?(server)
        DispatchQueue.global(qos: .userInitiated).async { try! server.run() }
        return port
    }

    private func temporaryStoreURL() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("RelayIdentitySocketTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        return directory.appendingPathComponent("allocations.json")
    }

    private static func freePort() throws -> UInt16 {
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else { throw SocketTestError.io }
        defer { Darwin.close(socket) }
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let result = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(socket, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard result == 0 else { throw SocketTestError.io }
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        guard withUnsafeMutablePointer(to: &address, {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.getsockname(socket, $0, &length)
            }
        }) == 0 else { throw SocketTestError.io }
        return UInt16(bigEndian: address.sin_port)
    }

    private static func makeListeningSocket() throws -> (socket: Int32, port: UInt16) {
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else { throw SocketTestError.io }
        do {
            var address = sockaddr_in()
            address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            address.sin_family = sa_family_t(AF_INET)
            address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
            guard withUnsafePointer(to: &address, {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    Darwin.bind(socket, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }) == 0,
                Darwin.listen(socket, SOMAXCONN) == 0
            else {
                throw SocketTestError.io
            }
            var length = socklen_t(MemoryLayout<sockaddr_in>.size)
            guard withUnsafeMutablePointer(to: &address, {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    Darwin.getsockname(socket, $0, &length)
                }
            }) == 0 else {
                throw SocketTestError.io
            }
            return (socket, UInt16(bigEndian: address.sin_port))
        } catch {
            Darwin.close(socket)
            throw error
        }
    }

    private func connect(port: UInt16) throws -> Int32 {
        for _ in 0..<80 {
            let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
            guard socket >= 0 else { throw SocketTestError.io }
            var address = sockaddr_in()
            address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            address.sin_family = sa_family_t(AF_INET)
            address.sin_port = port.bigEndian
            address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
            let connected = withUnsafePointer(to: &address) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    Darwin.connect(socket, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }
            if connected == 0 {
                var noSignal: Int32 = 1
                setsockopt(
                    socket,
                    SOL_SOCKET,
                    SO_NOSIGPIPE,
                    &noSignal,
                    socklen_t(MemoryLayout<Int32>.size)
                )
                var timeout = timeval(tv_sec: 2, tv_usec: 0)
                setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))
                return socket
            }
            Darwin.close(socket)
            Thread.sleep(forTimeInterval: 0.025)
        }
        throw SocketTestError.io
    }

    private func waitForSourceQuotaMetrics(
        _ server: RelayServer,
        matching predicate: (RelaySourceQuotaMetricsSnapshot) -> Bool
    ) throws -> RelaySourceQuotaMetricsSnapshot {
        for _ in 0..<80 {
            let snapshot = server.sourceQuotaMetricsSnapshot()
            if predicate(snapshot) {
                return snapshot
            }
            Thread.sleep(forTimeInterval: 0.025)
        }
        throw SocketTestError.io
    }

    private func waitForWaitingPeerPolicyMetrics(
        _ server: RelayServer,
        matching predicate: (RelayWaitingPeerPolicyMetricsSnapshot) -> Bool
    ) throws -> RelayWaitingPeerPolicyMetricsSnapshot {
        for _ in 0..<80 {
            let snapshot = server.waitingPeerPolicyMetricsSnapshot()
            if predicate(snapshot) {
                return snapshot
            }
            Thread.sleep(forTimeInterval: 0.025)
        }
        throw SocketTestError.io
    }

    private func closeWithReset(_ socket: Int32) throws {
        var abortiveClose = linger(l_onoff: 1, l_linger: 0)
        guard setsockopt(
            socket,
            SOL_SOCKET,
            SO_LINGER,
            &abortiveClose,
            socklen_t(MemoryLayout<linger>.size)
        ) == 0 else {
            Darwin.close(socket)
            throw SocketTestError.io
        }
        Darwin.close(socket)
    }

    private func write(_ line: String, socket: Int32) throws {
        let data = Data(line.utf8)
        var offset = 0
        while offset < data.count {
            let sent = data.withUnsafeBytes {
                Darwin.send(socket, $0.baseAddress?.advanced(by: offset), data.count - offset, 0)
            }
            guard sent > 0 else { throw SocketTestError.io }
            offset += sent
        }
    }

    private func write(_ bytes: [UInt8], socket: Int32) throws {
        try bytes.withUnsafeBytes { rawBuffer in
            guard let baseAddress = rawBuffer.baseAddress else { return }
            var offset = 0
            while offset < rawBuffer.count {
                let sent = Darwin.send(
                    socket,
                    baseAddress.advanced(by: offset),
                    rawBuffer.count - offset,
                    0
                )
                if sent < 0 && errno == EINTR {
                    continue
                }
                guard sent > 0 else { throw SocketTestError.io }
                offset += sent
            }
        }
    }

    private func readExactly(byteCount: Int, socket: Int32) throws -> [UInt8] {
        var bytes = [UInt8](repeating: 0, count: byteCount)
        var offset = 0
        while offset < byteCount {
            let received = bytes.withUnsafeMutableBytes { rawBuffer in
                Darwin.recv(
                    socket,
                    rawBuffer.baseAddress?.advanced(by: offset),
                    byteCount - offset,
                    0
                )
            }
            if received < 0 && errno == EINTR {
                continue
            }
            guard received > 0 else { throw SocketTestError.io }
            offset += received
        }
        return bytes
    }

    private func assertRelayPayloads(
        from source: Int32,
        to destination: Int32,
        seed: UInt8,
        label: String
    ) throws {
        for byteCount in [1, 64 * 1024, 64 * 1024 + 1] {
            let payload = (0..<byteCount).map { index in
                UInt8(truncatingIfNeeded: Int(seed) + index * 31)
            }
            try write(payload, socket: source)
            let received = try readExactly(byteCount: byteCount, socket: destination)

            XCTAssertEqual(received, payload, "\(label) byte_count=\(byteCount)")
            XCTAssertEqual(
                Data(SHA256.hash(data: Data(received))),
                Data(SHA256.hash(data: Data(payload))),
                "\(label) digest byte_count=\(byteCount)"
            )
        }
    }

    private func readLine(socket: Int32) throws -> String? {
        var bytes: [UInt8] = []
        while true {
            var byte: UInt8 = 0
            let count = Darwin.recv(socket, &byte, 1, 0)
            if count == 0 { return bytes.isEmpty ? nil : String(decoding: bytes, as: UTF8.self) }
            if count < 0 {
                if errno == EAGAIN || errno == EWOULDBLOCK { return nil }
                if errno == ECONNRESET { return nil }
                throw SocketTestError.io
            }
            bytes.append(byte)
            if byte == UInt8(ascii: "\n") { return String(decoding: bytes, as: UTF8.self) }
        }
    }

    private func peerReachedEOF(socket: Int32) throws -> Bool {
        var byte: UInt8 = 0
        let count = Darwin.recv(socket, &byte, 1, MSG_PEEK)
        if count == 0 {
            return true
        }
        if count < 0 && errno == ECONNRESET {
            return true
        }
        if count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK) {
            return false
        }
        if count < 0 {
            throw SocketTestError.io
        }
        return false
    }
}

private final class SocketReasonLogCapture: @unchecked Sendable {
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

private final class SocketIdentitySigner {
    let identity: RelayRuntimeIdentity
    private let privateKey: P256.Signing.PrivateKey

    init() throws {
        let key = P256.Signing.PrivateKey()
        let publicKey = key.publicKey.derRepresentation
        privateKey = key
        identity = try RelayRuntimeIdentity(
            publicKeyBase64: publicKey.base64EncodedString(),
            fingerprint: SHA256.hash(data: publicKey).map { String(format: "%02x", $0) }.joined()
        )
    }

    func sign(_ message: Data) throws -> String {
        try privateKey.signature(for: SHA256.hash(data: message))
            .derRepresentation.base64EncodedString()
    }

    func runtimeProof(
        challenge: PairedRelayAllocationAuthorizationChallenge
    ) throws -> PairedRelayAllocationRuntimeProof {
        try PairedRelayAllocationRuntimeProof.sign(
            challenge: challenge,
            using: privateKey
        )
    }

    func clientProof(
        challenge: PairedRelayAllocationAuthorizationChallenge
    ) throws -> PairedRelayAllocationClientProof {
        try PairedRelayAllocationClientProof.sign(
            challenge: challenge,
            using: privateKey
        )
    }

    func clientRegistrationProof(
        challenge: PairedClientRelayRegistrationChallenge
    ) throws -> PairedClientRelayRegistrationProof {
        try PairedClientRelayRegistrationProof.sign(
            challenge: challenge,
            using: privateKey
        )
    }
}

private enum SocketTestError: Error {
    case io
}
