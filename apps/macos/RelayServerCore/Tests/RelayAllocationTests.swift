import BridgeProtocol
import CryptoKit
import XCTest
@testable import RelayServerCore

final class RelayAllocationTests: XCTestCase {
    func testRelayServerConfigurationUsesShortDefaultAllocationTTL() {
        let configuration = RelayServerConfiguration()

        XCTAssertEqual(configuration.allocationTTLSeconds, 15 * 60)
        XCTAssertTrue(configuration.requiresAllocation)
        XCTAssertEqual(configuration.probePolicy, .loopbackOnly)
        XCTAssertEqual(configuration.controlLineReadTimeoutSeconds, 10)
        XCTAssertEqual(configuration.maximumConcurrentConnections, 256)
        XCTAssertEqual(configuration.sourceQuotaConfiguration, RelaySourceQuotaConfiguration())
        XCTAssertEqual(
            configuration.sourceRateLimitConfiguration,
            RelaySourceRateLimitConfiguration()
        )
    }

    func testRelayServerConfigurationCanExplicitlyAllowLegacyUnallocatedRelays() {
        let configuration = RelayServerConfiguration(requiresAllocation: false)

        XCTAssertFalse(configuration.requiresAllocation)
    }

    func testRelayBindExposureAllowsOnlyLoopbackWithoutAllocationToken() throws {
        let hosts = ["127.0.0.1", "127.0.0.2", "::1", "[::1]", "localhost", "LOCALHOST"]

        for host in hosts {
            XCTAssertFalse(RelayBindExposure.requiresAllocationToken(host: host), host)
            XCTAssertNoThrow(try RelayServerConfiguration(host: host).validate(), host)
        }
    }

    func testRelayBindExposureRequiresTokenForWildcardAndNonLoopbackBinds() {
        let hosts = [
            "",
            "0.0.0.0",
            "::",
            "192.168.1.10",
            "100.64.1.10",
            "8.8.8.8",
            "relay.example.test"
        ]

        for host in hosts {
            XCTAssertTrue(RelayBindExposure.requiresAllocationToken(host: host), host)
            XCTAssertThrowsError(try RelayServerConfiguration(host: host).validate(), host) { error in
                XCTAssertEqual(
                    error as? RelayServerError,
                    .allocationTokenRequiredForExposedBind(RelayBindExposure.normalizedHost(host))
                )
            }
        }
    }

    func testRelayBindExposureAllowsWildcardAndNonLoopbackBindsWithAllocationToken() {
        let hosts = ["0.0.0.0", "::", "192.168.1.10", "relay.example.test"]

        for host in hosts {
            XCTAssertNoThrow(
                try RelayServerConfiguration(
                    host: host,
                    allocationStoreURL: URL(fileURLWithPath: "/tmp/aetherlink-relay-test-store.json"),
                    allocationToken: "allocation-token-1"
                ).validate(),
                host
            )
        }
    }

    func testStrictNonLoopbackRelayRejectsEphemeralAllocationStore() {
        for host in ["0.0.0.0", "::", "192.168.1.10", "relay.example.test"] {
            XCTAssertThrowsError(
                try RelayServerConfiguration(
                    host: host,
                    requiresAllocation: true,
                    allocationStoreURL: nil,
                    allocationToken: "allocation-token-1"
                ).validate(),
                host
            ) { error in
                XCTAssertEqual(
                    error as? RelayServerError,
                    .durableAllocationStoreRequired(RelayBindExposure.normalizedHost(host))
                )
            }
        }
    }

    func testRelayConfigurationRejectsInvalidAllocationTokens() {
        for token in ["", " ", "token value", "token\nvalue"] {
            XCTAssertThrowsError(
                try RelayServerConfiguration(host: "127.0.0.1", allocationToken: token).validate(),
                token
            ) { error in
                XCTAssertEqual(error as? RelayServerError, .invalidAllocationToken)
            }
        }
    }

    func testRelayConfigurationRejectsInvalidAbuseControlLimits() {
        for timeout in [0, -1, 301, .infinity, .nan] {
            XCTAssertThrowsError(
                try RelayServerConfiguration(
                    controlLineReadTimeoutSeconds: timeout
                ).validate()
            ) { error in
                XCTAssertEqual(error as? RelayServerError, .invalidControlLineReadTimeout)
            }
        }
        for maximum in [0, -1, 65_537] {
            XCTAssertThrowsError(
                try RelayServerConfiguration(
                    maximumConcurrentConnections: maximum
                ).validate()
            ) { error in
                XCTAssertEqual(error as? RelayServerError, .invalidMaximumConcurrentConnections)
            }
        }
        XCTAssertThrowsError(
            try RelayServerConfiguration(
                waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration(
                    maximumDurationSeconds: 0,
                    maximumPeersPerAuthenticatedIdentity: 8
                )
            ).validate()
        ) { error in
            XCTAssertEqual(
                error as? RelayWaitingPeerPolicyConfigurationError,
                .invalidMaximumDuration
            )
        }
        XCTAssertThrowsError(
            try RelayServerConfiguration(
                waitingPeerPolicyConfiguration: RelayWaitingPeerPolicyConfiguration(
                    maximumDurationSeconds: 120,
                    maximumPeersPerAuthenticatedIdentity: 0
                )
            ).validate()
        ) { error in
            XCTAssertEqual(
                error as? RelayWaitingPeerPolicyConfigurationError,
                .invalidAuthenticatedIdentityQuota
            )
        }

        XCTAssertThrowsError(
            try RelayServerConfiguration(
                sourceQuotaConfiguration: RelaySourceQuotaConfiguration(
                    maximumConnectionsPerSource: 63,
                    maximumWaitingPeersPerSource: 32
                )
            ).validate()
        ) { error in
            XCTAssertEqual(
                error as? RelaySourceQuotaConfigurationError,
                .insufficientCounterpartConnectionCapacity
            )
        }

        var invalidRateLimits = RelaySourceRateLimitConfiguration()
        invalidRateLimits.allocationMutationBurst = 0
        XCTAssertThrowsError(
            try RelayServerConfiguration(
                sourceRateLimitConfiguration: invalidRateLimits
            ).validate()
        ) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .invalidAllocationMutationBurst
            )
        }
        invalidRateLimits = RelaySourceRateLimitConfiguration(
            preflightRequestsPerMinute: 1,
            preflightBurst: 16
        )
        XCTAssertThrowsError(
            try RelayServerConfiguration(
                sourceRateLimitConfiguration: invalidRateLimits
            ).validate()
        ) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .idleRetentionTooShortForBurstRefill
            )
        }
        invalidRateLimits = RelaySourceRateLimitConfiguration(
            allocationMutationRequestsPerMinute: 1,
            allocationMutationBurst: 16
        )
        XCTAssertThrowsError(
            try RelayServerConfiguration(
                sourceRateLimitConfiguration: invalidRateLimits
            ).validate()
        ) { error in
            XCTAssertEqual(
                error as? RelaySourceRateLimitConfigurationError,
                .idleRetentionTooShortForBurstRefill
            )
        }
    }

    func testLegacyUnallocatedRelayModeIsLoopbackOnly() {
        XCTAssertNoThrow(
            try RelayServerConfiguration(
                host: "127.0.0.1",
                requiresAllocation: false
            ).validate()
        )
        XCTAssertThrowsError(
            try RelayServerConfiguration(
                host: "0.0.0.0",
                requiresAllocation: false,
                allocationToken: "diagnostic-token"
            ).validate()
        ) { error in
            XCTAssertEqual(
                error as? RelayServerError,
                .legacyRelayRequiresLoopback("0.0.0.0")
            )
        }
    }

    func testProbePolicyDefaultsToLoopbackOnlyAndRequiresExplicitExposedOptIn() {
        XCTAssertTrue(RelayProbePolicy.loopbackOnly.allowsProbe(host: "127.0.0.1"))
        XCTAssertFalse(RelayProbePolicy.loopbackOnly.allowsProbe(host: "0.0.0.0"))
        XCTAssertFalse(RelayProbePolicy.disabled.allowsProbe(host: "127.0.0.1"))
        XCTAssertTrue(RelayProbePolicy.legacyUnauthenticated.allowsProbe(host: "0.0.0.0"))
    }

    func testParsesAllocationRequest() throws {
        let request = try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token-1\n")

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertNil(request.requestedRelaySecret)
        XCTAssertNil(request.cryptoVersion)
        XCTAssertNil(request.allocationToken)
        XCTAssertTrue(RelayAllocationRequest.isAllocationLine("AETHERLINK_RELAY allocate route-token-1\n"))
    }

    func testParsesAllocationRequestWithRequestedRelaySecret() throws {
        let request = try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token-1 secret-1\n")

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertEqual(request.requestedRelaySecret, "secret-1")
        XCTAssertNil(request.allocationToken)
    }

    func testParsesAllocationRequestWithBase64RequestedRelaySecret() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 secret+with/symbols= allocation_token=allocation-token-1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertEqual(request.requestedRelaySecret, "secret+with/symbols=")
        XCTAssertEqual(request.allocationToken, "allocation-token-1")

        let paddedRequest = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 dGVzdA== allocation_token=allocation-token-1\n"
        )
        XCTAssertEqual(paddedRequest.routeToken, "route-token-1")
        XCTAssertEqual(paddedRequest.requestedRelaySecret, "dGVzdA==")
        XCTAssertEqual(paddedRequest.allocationToken, "allocation-token-1")
    }

    func testParsesAllocationRequestWithAllocationToken() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 secret-1 allocation_token=allocation-token-1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertEqual(request.requestedRelaySecret, "secret-1")
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
    }

    func testParsesAllocationRequestWithAllocationTokenOnly() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 allocation_token=allocation-token-1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertNil(request.requestedRelaySecret)
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
        XCTAssertFalse(request.isPreflight)
        XCTAssertTrue(request.shouldPersistAllocation)
    }

    func testParsesAllocationRequestWithAuthAlias() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 auth=allocation-token-1 preflight=1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertNil(request.requestedRelaySecret)
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
        XCTAssertTrue(request.isPreflight)
        XCTAssertFalse(request.shouldPersistAllocation)
    }

    func testParsesPreflightAllocationRequest() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 allocation_token=allocation-token-1 preflight=1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertNil(request.requestedRelaySecret)
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
        XCTAssertTrue(request.isPreflight)
        XCTAssertFalse(request.shouldPersistAllocation)
    }

    func testParsesPreflightAllocationRequestWithRequestedSecret() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 secret-1 preflight=true allocation_token=allocation-token-1\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertEqual(request.requestedRelaySecret, "secret-1")
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
        XCTAssertTrue(request.isPreflight)
        XCTAssertFalse(request.shouldPersistAllocation)
    }

    func testParsesCryptoV2AllocationWithExistingOptions() throws {
        let request = try RelayAllocationRequest.parse(
            "AETHERLINK_RELAY allocate route-token-1 crypto=2 allocation_token=allocation-token-1 preflight=true\n"
        )

        XCTAssertEqual(request.routeToken, "route-token-1")
        XCTAssertNil(request.requestedRelaySecret)
        XCTAssertEqual(request.cryptoVersion, 2)
        XCTAssertTrue(request.usesEndpointOwnedSecret)
        XCTAssertEqual(request.allocationToken, "allocation-token-1")
        XCTAssertTrue(request.isPreflight)
        XCTAssertFalse(request.shouldPersistAllocation)
    }

    func testStrictCryptoV2ParserAcceptsOnlyCanonicalOptions() throws {
        let identity = try makeIdentity()
        let normal = "AETHERLINK_RELAY allocate strict-base crypto=2 " +
            "allocation_auth=runtime-p256-v1 runtime_key_fingerprint=\(identity.fingerprint) " +
            "runtime_public_key=\(identity.publicKeyBase64)"
        let requests = try [
            RelayAllocationRequest.parseStrictCryptoV2(
                normal + "\n"
            ),
            RelayAllocationRequest.parseStrictCryptoV2(
                normal + " allocation_token=token-1\n"
            ),
            RelayAllocationRequest.parseStrictCryptoV2(
                "AETHERLINK_RELAY allocate strict-preflight crypto=2 preflight=1\n"
            ),
            RelayAllocationRequest.parseStrictCryptoV2(
                "AETHERLINK_RELAY allocate strict-all crypto=2 allocation_token=token-1 preflight=1\n"
            )
        ]

        XCTAssertTrue(requests.allSatisfy(\.usesEndpointOwnedSecret))
        XCTAssertEqual(requests[1].allocationToken, "token-1")
        XCTAssertEqual(requests[0].runtimeIdentity, identity)
        XCTAssertTrue(requests[2].isPreflight)
        XCTAssertEqual(requests[3].allocationToken, "token-1")
        XCTAssertTrue(requests[3].isPreflight)
    }

    func testStrictCryptoV2ParserRejectsLegacyAndBypassShapes() {
        for line in [
            "AETHERLINK_RELAY allocate strict-versionless\n",
            "AETHERLINK_RELAY allocate strict-secret secret-1\n",
            "AETHERLINK_RELAY allocate strict-v1 crypto=1\n",
            "AETHERLINK_RELAY allocate strict-secret-v2 crypto=2 secret-1\n",
            "AETHERLINK_RELAY allocate strict-duplicate crypto=2 crypto=2\n",
            "AETHERLINK_RELAY allocate strict-auth crypto=2 auth=token-1\n",
            "AETHERLINK_RELAY allocate strict-preflight-alias crypto=2 preflight=true\n",
            "AETHERLINK_RELAY allocate strict-order crypto=2 preflight=1 allocation_token=token-1\n",
            "AETHERLINK_RELAY allocate strict-extra crypto=2 debug=1\n"
        ] {
            XCTAssertThrowsError(try RelayAllocationRequest.parseStrictCryptoV2(line), line)
        }
    }

    func testRejectsUnsupportedAndDuplicateAllocationCryptoVersions() {
        for line in [
            "AETHERLINK_RELAY allocate route-token-1 crypto=1\n",
            "AETHERLINK_RELAY allocate route-token-1 crypto=3\n",
            "AETHERLINK_RELAY allocate route-token-1 crypto=two\n",
            "AETHERLINK_RELAY allocate route-token-1 crypto=\n"
        ] {
            XCTAssertThrowsError(try RelayAllocationRequest.parse(line), line) { error in
                XCTAssertEqual(error as? RelayAllocationError, .unsupportedCryptoVersion)
            }
        }

        XCTAssertThrowsError(
            try RelayAllocationRequest.parse(
                "AETHERLINK_RELAY allocate route-token-1 crypto=2 crypto=2\n"
            )
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidFormat)
        }
    }

    func testRejectsRequestedRelaySecretCombinedWithCryptoV2() {
        for line in [
            "AETHERLINK_RELAY allocate route-token-1 secret-1 crypto=2\n",
            "AETHERLINK_RELAY allocate route-token-1 crypto=2 secret-1\n",
            "AETHERLINK_RELAY allocate route-token-1 dGVzdA== crypto=2 allocation_token=token-1\n"
        ] {
            XCTAssertThrowsError(try RelayAllocationRequest.parse(line), line) { error in
                XCTAssertEqual(error as? RelayAllocationError, .relaySecretNotAllowedForCryptoV2)
            }
        }
    }

    func testRejectsMalformedAllocationRequest() {
        XCTAssertThrowsError(try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate\n"))
        XCTAssertThrowsError(try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route token extra\n"))
        XCTAssertThrowsError(try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token secret-1 allocation_token=one allocation_token=two\n"))
        XCTAssertThrowsError(try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token preflight=1 preflight=true\n"))
        XCTAssertFalse(RelayAllocationRequest.isAllocationLine("AETHERLINK_RELAY runtime relay-1\n"))
    }

    func testRejectsBlankAllocationTokenAndRelaySecret() {
        XCTAssertThrowsError(
            try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token-1 allocation_token=\n")
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidAllocationToken)
        }
        XCTAssertThrowsError(
            try RelayAllocationRequest.parse("AETHERLINK_RELAY allocate route-token-1 auth=\n")
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidAllocationToken)
        }
        XCTAssertThrowsError(
            try RelayAllocationRequest(routeToken: "route-token-1", requestedRelaySecret: "")
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidRelaySecret)
        }
        XCTAssertThrowsError(
            try RelayAllocationRequest(routeToken: "route-token-1", requestedRelaySecret: "secret value")
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidRelaySecret)
        }
    }

    func testRejectsUnexpectedAllocationRequestMetadata() {
        for line in [
            "AETHERLINK_RELAY allocate route-token-1 backend_url=http://127.0.0.1:11434/api/tags allocation_token=allocation-token-1\n",
            "AETHERLINK_RELAY allocate route-token-1 provider_url=https://provider.example.test/v1/models allocation_token=allocation-token-1\n",
            "AETHERLINK_RELAY allocate route-token-1 requested_route_token=leaked-route-token allocation_token=allocation-token-1\n",
            "AETHERLINK_RELAY allocate route-token-1 relay_secret_debug=leaked-relay-secret allocation_token=allocation-token-1\n",
            "AETHERLINK_RELAY allocate route-token-1 debug=leaked-relay-secret allocation_token=allocation-token-1\n",
            "AETHERLINK_RELAY allocate route-token-1 preflight=false allocation_token=allocation-token-1\n",
            "AETHERLINK_RELAY allocate route-token-1 relay-debug=enabled allocation_token=allocation-token-1\n"
        ] {
            XCTAssertThrowsError(
                try RelayAllocationRequest.parse(line)
            ) { error in
                XCTAssertEqual(error as? RelayAllocationError, .invalidFormat)
            }
        }
    }

    func testAllocationResponseRoundTripsAsLine() throws {
        let allocation = try RelayAllocation(
            relayID: "relay-1",
            relaySecret: "secret-1",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "nonce-1"
        )

        let line = String(decoding: try allocation.responseLine(), as: UTF8.self)
        let parsed = try RelayAllocation.parseResponseLine(line)

        XCTAssertEqual(parsed, allocation)
        XCTAssertTrue(line.contains("\"relay_secret\":\"secret-1\""))
        XCTAssertFalse(line.contains("crypto_version"))
    }

    func testCryptoV2AllocationResponseUsesExactSecretFreeFields() throws {
        let identity = try makeIdentity()
        let allocation = try RelayAllocationV2(
            relayID: RelayAllocationIdentityChallenge.relayID(
                routeToken: "route-v2",
                runtimeKeyFingerprint: identity.fingerprint
            ),
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "nonce-v2",
            runtimeKeyFingerprint: identity.fingerprint,
            ticketGeneration: 1
        )

        let line = String(decoding: try allocation.responseLine(), as: UTF8.self)
        let parsed = try RelayAllocationV2.parseResponseLine(line)
        let json = String(line.dropFirst(RelayAllocationV2.responsePrefix.count))
        let payload = try XCTUnwrap(
            try JSONSerialization.jsonObject(with: Data(json.utf8)) as? [String: Any]
        )

        XCTAssertEqual(parsed, allocation)
        XCTAssertEqual(
            Set(payload.keys),
            [
                "relay_id", "relay_expires_at", "relay_nonce",
                "runtime_key_fingerprint", "ticket_generation", "crypto_version"
            ]
        )
        XCTAssertEqual(payload["crypto_version"] as? Int, 2)
        XCTAssertNil(payload["relay_secret"])
    }

    func testCryptoV2AllocationResponseRejectsNonExactFieldsAndVersion() {
        for line in [
            "\(RelayAllocationV2.responsePrefix){\"relay_id\":\"relay-v2\",\"relay_expires_at\":4102444800000,\"relay_nonce\":\"nonce-v2\"}\n",
            "\(RelayAllocationV2.responsePrefix){\"relay_id\":\"relay-v2\",\"relay_expires_at\":4102444800000,\"relay_nonce\":\"nonce-v2\",\"crypto_version\":2,\"relay_secret\":\"secret-1\"}\n"
        ] {
            XCTAssertThrowsError(try RelayAllocationV2.parseResponseLine(line), line) { error in
                XCTAssertEqual(error as? RelayAllocationError, .unexpectedResponseMetadata)
            }
        }

        XCTAssertThrowsError(
            try RelayAllocationV2.parseResponseLine(
                "\(RelayAllocationV2.responsePrefix){\"relay_id\":\"rt2-\(String(repeating: "a", count: 64))\",\"relay_expires_at\":4102444800000,\"relay_nonce\":\"nonce-v2\",\"runtime_key_fingerprint\":\"\(String(repeating: "b", count: 64))\",\"ticket_generation\":1,\"crypto_version\":1}\n"
            )
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .unsupportedCryptoVersion)
        }
    }

    func testRejectsInvalidAllocationResponseLineFields() {
        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(allocationResponseLine(relayID: "relay 1"))
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidRelayID)
        }
        for relayID in nonCanonicalAllocationResponseRelayIDs {
            XCTAssertThrowsError(
                try RelayAllocation.parseResponseLine(allocationResponseLine(relayID: relayID)),
                relayID
            ) { error in
                XCTAssertEqual(error as? RelayAllocationError, .invalidRelayID)
            }
        }
        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(allocationResponseLine(relaySecret: "secret value"))
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidRelaySecret)
        }
        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(allocationResponseLine(relayExpiresAtEpochMillis: 0))
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidExpiration)
        }
        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(allocationResponseLine(relayNonce: "nonce value"))
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .invalidNonce)
        }
    }

    func testRejectsUnexpectedAllocationResponseLineMetadata() {
        let line = """
        \(RelayAllocation.responsePrefix){"relay_id":"rt1-response","relay_secret":"secret-1","relay_expires_at":4102444800000,"relay_nonce":"nonce-1","requested_route_token":"leaked-route-token","backend_url":"http://127.0.0.1:11434/api/tags","provider_url":"https://provider.example.test/v1/models","allocation_token":"leaked-allocation-token","relay_secret_debug":"leaked-relay-secret"}
        """

        XCTAssertThrowsError(
            try RelayAllocation.parseResponseLine(line)
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .unexpectedResponseMetadata)
        }
    }

    func testAllocationDerivesOpaqueStableRelayIDFromRouteTokenAndRequestedSecret() throws {
        let allocation = try RelayAllocation.make(
            routeToken: "route-token-1",
            requestedRelaySecret: "secret-1",
            now: Date(timeIntervalSince1970: 1),
            validFor: 60
        )
        let second = try RelayAllocation.make(
            routeToken: "route-token-1",
            requestedRelaySecret: "secret-2",
            now: Date(timeIntervalSince1970: 2),
            validFor: 60
        )
        let differentRoute = try RelayAllocation.make(
            routeToken: "route-token-2",
            requestedRelaySecret: "secret-1",
            now: Date(timeIntervalSince1970: 1),
            validFor: 60
        )

        XCTAssertEqual(allocation.relayID, try RelayAllocation.relayID(forRouteToken: "route-token-1"))
        XCTAssertEqual(second.relayID, allocation.relayID)
        XCTAssertNotEqual(differentRoute.relayID, allocation.relayID)
        XCTAssertTrue(allocation.relayID.hasPrefix("rt1-"))
        XCTAssertFalse(allocation.relayID.contains("route-token-1"))
        XCTAssertEqual(allocation.relaySecret, "secret-1")
        XCTAssertEqual(allocation.relayExpiresAtEpochMillis, 61_000)
        XCTAssertFalse(allocation.relayNonce.isEmpty)
    }


    func testStrictPreflightResponseIsClosedAndContainsNoRouteMaterial() throws {
        let line = String(
            decoding: try RelayAllocationPreflightResponse().responseLine(),
            as: UTF8.self
        )
        let payload = try XCTUnwrap(
            try JSONSerialization.jsonObject(
                with: Data(line.dropFirst(RelayAllocationPreflightResponse.responsePrefix.count).utf8)
            ) as? [String: Any]
        )

        XCTAssertEqual(
            line,
            "AETHERLINK_RELAY preflight {\"allocation_auth\":\"runtime-p256-v1\",\"crypto_version\":2,\"preflight\":true}\n"
        )
        XCTAssertEqual(Set(payload.keys), ["preflight", "crypto_version", "allocation_auth"])
        XCTAssertNoThrow(try RelayAllocationPreflightResponse.parseResponseLine(line))
        for forbidden in ["relay_id", "relay_expires_at", "relay_nonce", "runtime_public_key", "ticket_generation"] {
            XCTAssertNil(payload[forbidden])
        }
    }

    func testIdentityProofParsersRequireExactChallengeEchoShape() throws {
        let privateKey = P256.Signing.PrivateKey()
        let publicKey = privateKey.publicKey.derRepresentation
        let identity = try RelayRuntimeIdentity(
            publicKeyBase64: publicKey.base64EncodedString(),
            fingerprint: SHA256.hash(data: publicKey).map { String(format: "%02x", $0) }.joined()
        )
        let challenge = String(repeating: "a", count: 64)
        let signature = try privateKey.signature(for: Data("proof".utf8))
            .derRepresentation.base64EncodedString()
        let allocationLine = "AETHERLINK_RELAY allocation_proof crypto=2 " +
            "challenge=\(challenge) signature=\(signature)\n"
        let registrationLine = "AETHERLINK_RELAY registration_proof crypto=2 " +
            "challenge=\(challenge) signature=\(signature)\n"

        XCTAssertEqual(
            try RelayAllocationProofRequest.parse(allocationLine, runtimeIdentity: identity).challenge,
            challenge
        )
        XCTAssertEqual(
            try RelayRuntimeRegistrationProofRequest.parse(
                registrationLine,
                runtimeIdentity: identity
            ).challenge,
            challenge
        )
        for malformed in [
            allocationLine.replacingOccurrences(of: "crypto=2 ", with: ""),
            allocationLine.replacingOccurrences(of: "challenge=", with: "challenge ="),
            allocationLine.replacingOccurrences(of: " signature=", with: "  signature="),
            allocationLine.replacingOccurrences(of: "\n", with: "\r\n"),
            "AETHERLINK_RELAY allocation_proof crypto=2 challenge=abc signature=\(signature)\n"
        ] {
            XCTAssertThrowsError(
                try RelayAllocationProofRequest.parse(malformed, runtimeIdentity: identity),
                malformed
            )
        }
    }

    func testStrictNormalRequestRejectsWhitespaceOrderAndIdentityMutation() throws {
        let identity = try makeIdentity()
        let canonical = "AETHERLINK_RELAY allocate route crypto=2 " +
            "allocation_auth=runtime-p256-v1 runtime_key_fingerprint=\(identity.fingerprint) " +
            "runtime_public_key=\(identity.publicKeyBase64)\n"
        XCTAssertNoThrow(try RelayAllocationRequest.parseStrictCryptoV2(canonical))

        for malformed in [
            canonical.replacingOccurrences(of: "allocate route", with: "allocate  route"),
            canonical.replacingOccurrences(
                of: "allocation_auth=runtime-p256-v1 runtime_key_fingerprint=\(identity.fingerprint)",
                with: "runtime_key_fingerprint=\(identity.fingerprint) allocation_auth=runtime-p256-v1"
            ),
            canonical.replacingOccurrences(of: "\n", with: "\r\n"),
            String(canonical.dropLast()),
            canonical.replacingOccurrences(of: "runtime-p256-v1", with: "runtime-p256-v2"),
            canonical.replacingOccurrences(of: identity.fingerprint, with: identity.fingerprint.uppercased())
        ] {
            XCTAssertThrowsError(try RelayAllocationRequest.parseStrictCryptoV2(malformed), malformed)
        }
    }

    func testPairedRenewalRequestRequiresExactOrderedSecretFreeFields() throws {
        let runtimeKey = P256.Signing.PrivateKey()
        let clientKey = P256.Signing.PrivateKey()
        let runtimeIdentity = try makeIdentity(privateKey: runtimeKey)
        let clientIdentity = try makeIdentity(privateKey: clientKey)
        let request = try RelayPairedAllocationRenewalRequest(
            routeToken: "paired-route",
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            runtimePublicKey: runtimeIdentity.publicKeyBase64,
            clientKeyFingerprint: clientIdentity.fingerprint,
            clientPublicKey: clientIdentity.publicKeyBase64,
            requestID: "request-1",
            authorizationID: "authorization-1",
            transportBinding: String(repeating: "a", count: 64),
            allocationToken: "token-1"
        )
        let canonical = String(decoding: request.requestLine(), as: UTF8.self)

        XCTAssertEqual(try RelayPairedAllocationRenewalRequest.parse(canonical), request)
        XCTAssertEqual(
            canonical,
            "AETHERLINK_RELAY renew paired-route crypto=2 " +
                "allocation_auth=runtime-client-p256-v2 " +
                "runtime_key_fingerprint=\(runtimeIdentity.fingerprint) " +
                "runtime_public_key=\(runtimeIdentity.publicKeyBase64) " +
                "client_key_fingerprint=\(clientIdentity.fingerprint) " +
                "client_public_key=\(clientIdentity.publicKeyBase64) " +
                "request_id=request-1 authorization_id=authorization-1 " +
                "transport_binding=\(String(repeating: "a", count: 64)) " +
                "allocation_token=token-1\n"
        )

        for malformed in [
            canonical.replacingOccurrences(of: "renew paired-route", with: "renew  paired-route"),
            canonical.replacingOccurrences(
                of: "request_id=request-1 authorization_id=authorization-1",
                with: "authorization_id=authorization-1 request_id=request-1"
            ),
            canonical.replacingOccurrences(
                of: "allocation_auth=runtime-client-p256-v2",
                with: "allocation_auth=runtime-p256-v1"
            ),
            canonical.replacingOccurrences(of: "allocation_token=", with: "auth="),
            canonical.replacingOccurrences(
                of: " crypto=2",
                with: " leaked-secret crypto=2"
            ),
            canonical.replacingOccurrences(of: "\n", with: " debug=1\n"),
            canonical.replacingOccurrences(of: "transport_binding=", with: "binding="),
            String(canonical.dropLast()),
            canonical.replacingOccurrences(of: "\n", with: "\r\n")
        ] {
            XCTAssertThrowsError(
                try RelayPairedAllocationRenewalRequest.parse(malformed),
                malformed
            )
        }
    }

    func testPairedChallengeAndDualProofUseExactControlLines() throws {
        let runtimeKey = P256.Signing.PrivateKey()
        let clientKey = P256.Signing.PrivateKey()
        let runtimeIdentity = try makeIdentity(privateKey: runtimeKey)
        let clientIdentity = try makeIdentity(privateKey: clientKey)
        let request = try RelayPairedAllocationRenewalRequest(
            routeToken: "proof-route",
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            runtimePublicKey: runtimeIdentity.publicKeyBase64,
            clientKeyFingerprint: clientIdentity.fingerprint,
            clientPublicKey: clientIdentity.publicKeyBase64,
            requestID: "request-proof",
            authorizationID: "authorization-proof",
            transportBinding: String(repeating: "b", count: 64)
        )
        let challenge = try PairedRelayAllocationAuthorizationChallenge(
            operation: .claim,
            requestID: request.requestID,
            authorizationID: request.authorizationID,
            currentRelayID: RelayAllocationIdentityChallenge.relayID(
                routeToken: request.routeToken,
                runtimeKeyFingerprint: request.runtimeKeyFingerprint
            ),
            nextRelayID: RelayAllocationIdentityChallenge.pairedRelayID(
                routeToken: request.routeToken,
                runtimeKeyFingerprint: request.runtimeKeyFingerprint,
                clientKeyFingerprint: request.clientKeyFingerprint
            ),
            routeTokenHash: PairedRelayAllocationAuthorization.routeTokenHash(
                request.routeToken
            ),
            runtimeKeyFingerprint: request.runtimeKeyFingerprint,
            clientKeyFingerprint: request.clientKeyFingerprint,
            currentTicketGeneration: 1,
            nextTicketGeneration: 2,
            currentRelayExpiresAtEpochMillis: 4_102_444_800_000,
            currentRelayNonce: "nonce-current",
            nextRelayExpiresAtEpochMillis: 4_102_444_900_000,
            nextRelayNonce: "nonce-next",
            challenge: String(repeating: "c", count: 64),
            challengeExpiresAtEpochMillis: 4_102_444_810_000,
            transportBinding: request.transportBinding
        )
        let challengeLine = String(
            decoding: try RelayPairedAllocationChallengeResponse(
                challenge: challenge
            ).responseLine(),
            as: UTF8.self
        )
        XCTAssertEqual(
            try RelayPairedAllocationChallengeResponse.parseResponseLine(
                challengeLine
            ).challenge,
            challenge
        )

        let runtimeProof = try PairedRelayAllocationRuntimeProof.sign(
            challenge: challenge,
            using: runtimeKey
        )
        let clientProof = try PairedRelayAllocationClientProof.sign(
            challenge: challenge,
            using: clientKey
        )
        let proof = try RelayPairedAllocationProofRequest(
            challenge: challenge.challenge,
            runtimeSignatureBase64: runtimeProof.signatureBase64,
            clientSignatureBase64: clientProof.signatureBase64,
            renewalRequest: request
        )
        let proofLine = String(decoding: proof.requestLine(), as: UTF8.self)
        XCTAssertEqual(
            try RelayPairedAllocationProofRequest.parse(
                proofLine,
                renewalRequest: request
            ),
            proof
        )
        for malformed in [
            proofLine.replacingOccurrences(of: " runtime_signature=", with: " signature="),
            proofLine.replacingOccurrences(of: " client_signature=", with: ""),
            proofLine.replacingOccurrences(
                of: "runtime_signature=\(runtimeProof.signatureBase64) " +
                    "client_signature=\(clientProof.signatureBase64)",
                with: "client_signature=\(clientProof.signatureBase64) " +
                    "runtime_signature=\(runtimeProof.signatureBase64)"
            ),
            proofLine.replacingOccurrences(of: "\n", with: " extra=1\n")
        ] {
            XCTAssertThrowsError(
                try RelayPairedAllocationProofRequest.parse(
                    malformed,
                    renewalRequest: request
                ),
                malformed
            )
        }
    }

    func testSchemaV4StorePersistsAuthorizationModeAndConsumptionEnvelope() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let routeToken = "route-token-that-must-not-persist"
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: identity.fingerprint
        )
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "nonce-public-lease",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        let registry = RelayAllocationRegistry(persistenceURL: storeURL)

        try registry.commit(binding, replacingGeneration: nil)

        let data = try Data(contentsOf: storeURL)
        let envelope = try XCTUnwrap(
            try JSONSerialization.jsonObject(with: data) as? [String: Any]
        )
        XCTAssertEqual(
            Set(envelope.keys),
            [
                "schema_version", "coordination_token", "allocations",
                "consumed_bootstrap_allocations"
            ]
        )
        XCTAssertEqual(envelope["schema_version"] as? Int, 4)
        let coordinationToken = try XCTUnwrap(envelope["coordination_token"] as? String)
        XCTAssertEqual(coordinationToken.count, 64)
        let lockText = try String(
            contentsOf: RelayAllocationStoreCoordination.transactionLockURL(for: storeURL),
            encoding: .utf8
        )
        XCTAssertTrue(lockText.contains("state=E\n"))
        XCTAssertTrue(lockText.contains("token=\(coordinationToken)\n"))
        XCTAssertEqual(
            try XCTUnwrap(envelope["consumed_bootstrap_allocations"] as? [Any]).count,
            0
        )
        let tickets = try XCTUnwrap(envelope["allocations"] as? [[String: Any]])
        XCTAssertEqual(
            Set(try XCTUnwrap(tickets.first).keys),
            [
                "relay_id", "relay_expires_at", "relay_nonce", "runtime_key_fingerprint",
                "runtime_public_key", "ticket_generation", "authorization_mode",
                "paired_client_key_fingerprint"
            ]
        )
        XCTAssertEqual(tickets.first?["authorization_mode"] as? String, "bootstrap_runtime_only")
        XCTAssertTrue(tickets.first?["paired_client_key_fingerprint"] is NSNull)
        let text = String(decoding: data, as: UTF8.self)
        for forbidden in [routeToken, "allocation_token", "relay_secret", "signature", "challenge"] {
            XCTAssertFalse(text.contains(forbidden), forbidden)
        }
    }

    func testStoreReloadsActiveBindingAndRetainsExpiredTombstone() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "restart-route",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 2_000,
            relayNonce: "restart-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        try RelayAllocationRegistry(persistenceURL: storeURL).commit(binding, replacingGeneration: nil)

        let restarted = RelayAllocationRegistry(persistenceURL: storeURL)
        XCTAssertEqual(restarted.binding(relayID: relayID, now: Date(timeIntervalSince1970: 1)), binding)
        XCTAssertNil(restarted.binding(relayID: relayID, now: Date(timeIntervalSince1970: 3)))
        XCTAssertEqual(restarted.tombstone(relayID: relayID), binding)
        XCTAssertEqual(
            try restarted.proposedGeneration(relayID: relayID, runtimeIdentity: identity).generation,
            2
        )
    }

    func testSchemaV2StoreMigratesAtomicallyToBootstrapV4BeforeUse() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "migration-route",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let legacy: [String: Any] = [
            "schema_version": 2,
            "allocations": [[
                "relay_id": relayID,
                "relay_expires_at": 4_102_444_800_000 as Int64,
                "relay_nonce": "migration-nonce",
                "runtime_key_fingerprint": identity.fingerprint,
                "runtime_public_key": identity.publicKeyBase64,
                "ticket_generation": 7,
            ]],
        ]
        try JSONSerialization.data(
            withJSONObject: legacy,
            options: [.sortedKeys]
        ).write(to: storeURL)

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)
        let migrated = try XCTUnwrap(registry.tombstone(relayID: relayID))
        XCTAssertEqual(migrated.authorizationMode, .bootstrapRuntimeOnly)
        XCTAssertNil(migrated.pairedClientKeyFingerprint)
        XCTAssertEqual(migrated.ticketGeneration, 7)
        XCTAssertEqual(migrated.runtimeKeyFingerprint, identity.fingerprint)

        let persisted = try XCTUnwrap(
            try JSONSerialization.jsonObject(
                with: Data(contentsOf: storeURL)
            ) as? [String: Any]
        )
        XCTAssertEqual(persisted["schema_version"] as? Int, 4)
        XCTAssertEqual(
            try XCTUnwrap(persisted["consumed_bootstrap_allocations"] as? [Any]).count,
            0
        )
        let tickets = try XCTUnwrap(persisted["allocations"] as? [[String: Any]])
        XCTAssertEqual(tickets.first?["authorization_mode"] as? String, "bootstrap_runtime_only")
        XCTAssertTrue(tickets.first?["paired_client_key_fingerprint"] is NSNull)
    }

    func testSchemaV2MigrationPersistenceFailureFailsClosed() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "migration-failure-route",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let legacy: [String: Any] = [
            "schema_version": 2,
            "allocations": [[
                "relay_id": relayID,
                "relay_expires_at": 4_102_444_800_000 as Int64,
                "relay_nonce": "migration-failure-nonce",
                "runtime_key_fingerprint": identity.fingerprint,
                "runtime_public_key": identity.publicKeyBase64,
                "ticket_generation": 1,
            ]],
        ]
        try JSONSerialization.data(withJSONObject: legacy).write(to: storeURL)
        let transactionLock = try RelayAllocationStoreTransactionLock(storeURL: storeURL)
        defer { withExtendedLifetime(transactionLock) {} }
        let directory = storeURL.deletingLastPathComponent()
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o500],
            ofItemAtPath: directory.path
        )
        defer {
            try? FileManager.default.setAttributes(
                [.posixPermissions: 0o700],
                ofItemAtPath: directory.path
            )
        }

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)
        XCTAssertNil(registry.tombstone(relayID: relayID))
        XCTAssertThrowsError(
            try registry.proposedGeneration(relayID: relayID, runtimeIdentity: identity)
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .persistenceFailed)
        }
    }

    func testSchemaV3PairedBindingRotatesToPairScopedRoomAndPersistsTombstone() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let runtimeIdentity = try makeIdentity()
        let clientIdentity = try makeIdentity()
        let routeToken = "legacy-paired-route"
        let bootstrapRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: clientIdentity.fingerprint
        )
        let legacy: [String: Any] = [
            "schema_version": 3,
            "allocations": [[
                "relay_id": bootstrapRelayID,
                "relay_expires_at": 4_102_444_800_000 as Int64,
                "relay_nonce": "legacy-paired-nonce",
                "runtime_key_fingerprint": runtimeIdentity.fingerprint,
                "runtime_public_key": runtimeIdentity.publicKeyBase64,
                "ticket_generation": 7,
                "authorization_mode": "paired_device_p256_v1",
                "paired_client_key_fingerprint": clientIdentity.fingerprint,
            ]],
        ]
        try JSONSerialization.data(withJSONObject: legacy, options: [.sortedKeys]).write(to: storeURL)

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)
        let proposal = try registry.pairedRenewalProposal(
            bootstrapRelayID: bootstrapRelayID,
            pairedRelayID: pairedRelayID,
            runtimeIdentity: runtimeIdentity,
            clientKeyFingerprint: clientIdentity.fingerprint
        )
        XCTAssertEqual(proposal.operation, .renew)
        XCTAssertEqual(proposal.currentBinding.relayID, bootstrapRelayID)
        XCTAssertEqual(proposal.nextRelayID, pairedRelayID)

        let rotated = try RelayAllocationBinding(
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: 4_102_444_800_001,
            relayNonce: "pair-scoped-nonce",
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: 8,
            authorizationMode: .pairedDeviceP256V1,
            pairedClientKeyFingerprint: clientIdentity.fingerprint
        )
        try registry.commitPairedRenewal(
            rotated,
            replacing: proposal.currentBinding,
            operation: proposal.operation
        )

        let restarted = RelayAllocationRegistry(persistenceURL: storeURL)
        XCTAssertNil(restarted.tombstone(relayID: bootstrapRelayID))
        XCTAssertEqual(restarted.tombstone(relayID: pairedRelayID), rotated)
        XCTAssertEqual(
            restarted.consumedBootstrapTombstone(relayID: bootstrapRelayID)?.pairedRelayID,
            pairedRelayID
        )
        XCTAssertThrowsError(
            try restarted.proposedGeneration(
                relayID: bootstrapRelayID,
                runtimeIdentity: runtimeIdentity
            )
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .authorizationDowngrade)
        }
        let envelope = try XCTUnwrap(
            try JSONSerialization.jsonObject(with: Data(contentsOf: storeURL)) as? [String: Any]
        )
        XCTAssertEqual(envelope["schema_version"] as? Int, 4)
        XCTAssertEqual(
            try XCTUnwrap(envelope["consumed_bootstrap_allocations"] as? [[String: Any]]).count,
            1
        )
    }

    func testPairedClaimRenewalPinsClientAndUsesFullBindingCAS() throws {
        let runtimeIdentity = try makeIdentity()
        let clientIdentity = try makeIdentity()
        let substituteClient = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "paired-cas-route",
            runtimeKeyFingerprint: runtimeIdentity.fingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: "paired-cas-route",
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: clientIdentity.fingerprint
        )
        let current = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 2_000,
            relayNonce: "claim-current",
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: 1
        )
        let claimed = try RelayAllocationBinding(
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: 4_000,
            relayNonce: "claim-next",
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: 2,
            authorizationMode: .pairedDeviceP256V1,
            pairedClientKeyFingerprint: clientIdentity.fingerprint
        )
        let renewed = try RelayAllocationBinding(
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: 6_000,
            relayNonce: "renew-next",
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: 3,
            authorizationMode: .pairedDeviceP256V1,
            pairedClientKeyFingerprint: clientIdentity.fingerprint
        )
        let competingRenewal = try RelayAllocationBinding(
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: 7_000,
            relayNonce: "renew-race",
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: 3,
            authorizationMode: .pairedDeviceP256V1,
            pairedClientKeyFingerprint: clientIdentity.fingerprint
        )
        let registry = RelayAllocationRegistry()
        try registry.commit(current, replacingGeneration: nil)

        let claim = try registry.pairedRenewalProposal(
            bootstrapRelayID: relayID,
            pairedRelayID: pairedRelayID,
            runtimeIdentity: runtimeIdentity,
            clientKeyFingerprint: clientIdentity.fingerprint
        )
        XCTAssertEqual(claim.operation, .claim)
        XCTAssertEqual(claim.currentBinding, current)
        XCTAssertEqual(claim.nextRelayID, pairedRelayID)
        try registry.commitPairedRenewal(
            claimed,
            replacing: claim.currentBinding,
            operation: claim.operation
        )

        XCTAssertThrowsError(
            try registry.proposedGeneration(
                relayID: relayID,
                runtimeIdentity: runtimeIdentity
            )
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .authorizationDowngrade)
        }
        XCTAssertThrowsError(
            try registry.pairedRenewalProposal(
                bootstrapRelayID: relayID,
                pairedRelayID: pairedRelayID,
                runtimeIdentity: runtimeIdentity,
                clientKeyFingerprint: substituteClient.fingerprint
            )
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .unauthorizedAllocation)
        }

        let renewal = try registry.pairedRenewalProposal(
            bootstrapRelayID: relayID,
            pairedRelayID: pairedRelayID,
            runtimeIdentity: runtimeIdentity,
            clientKeyFingerprint: clientIdentity.fingerprint
        )
        XCTAssertEqual(renewal.operation, .renew)
        try registry.commitPairedRenewal(
            renewed,
            replacing: renewal.currentBinding,
            operation: renewal.operation
        )
        XCTAssertThrowsError(
            try registry.commitPairedRenewal(
                competingRenewal,
                replacing: renewal.currentBinding,
                operation: renewal.operation
            )
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .allocationConflict)
        }
        XCTAssertNil(registry.tombstone(relayID: relayID))
        XCTAssertEqual(registry.tombstone(relayID: pairedRelayID), renewed)
        let consumed = try XCTUnwrap(registry.consumedBootstrapTombstone(relayID: relayID))
        XCTAssertEqual(consumed.pairedRelayID, pairedRelayID)
        XCTAssertEqual(consumed.pairedClientKeyFingerprint, clientIdentity.fingerprint)
        XCTAssertEqual(consumed.consumedTicketGeneration, current.ticketGeneration)
    }

    func testPairedRenewalRequiresExistingTicketButAllowsExpiredTombstone() throws {
        let runtimeIdentity = try makeIdentity()
        let clientIdentity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "paired-tombstone-route",
            runtimeKeyFingerprint: runtimeIdentity.fingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: "paired-tombstone-route",
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: clientIdentity.fingerprint
        )
        let registry = RelayAllocationRegistry()
        XCTAssertThrowsError(
            try registry.pairedRenewalProposal(
                bootstrapRelayID: relayID,
                pairedRelayID: pairedRelayID,
                runtimeIdentity: runtimeIdentity,
                clientKeyFingerprint: clientIdentity.fingerprint
            )
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .allocationNotFound)
        }

        let expired = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 1,
            relayNonce: "expired-nonce",
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: 1
        )
        try registry.commit(expired, replacingGeneration: nil)
        XCTAssertNil(registry.binding(relayID: relayID, now: Date(timeIntervalSince1970: 1)))
        XCTAssertEqual(
            try registry.pairedRenewalProposal(
                bootstrapRelayID: relayID,
                pairedRelayID: pairedRelayID,
                runtimeIdentity: runtimeIdentity,
                clientKeyFingerprint: clientIdentity.fingerprint
            ).operation,
            .claim
        )
    }

    func testRenewalRequiresSameKeyAndGenerationCAS() throws {
        let identity = try makeIdentity()
        let otherIdentity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "cas-route",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let current = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 2_000,
            relayNonce: "nonce-1",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        let renewed = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_000,
            relayNonce: "nonce-2",
            runtimeIdentity: identity,
            ticketGeneration: 2
        )
        let registry = RelayAllocationRegistry()
        try registry.commit(current, replacingGeneration: nil)

        XCTAssertThrowsError(
            try registry.proposedGeneration(relayID: relayID, runtimeIdentity: otherIdentity)
        )
        try registry.commit(renewed, replacingGeneration: 1)
        XCTAssertThrowsError(try registry.commit(renewed, replacingGeneration: 1)) { error in
            XCTAssertEqual(error as? RelayAllocationError, .allocationConflict)
        }
    }

    func testPreCreatedDurableRegistriesMergeDifferentRelayCommits() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let firstIdentity = try makeIdentity()
        let secondIdentity = try makeIdentity()
        let firstRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "durable-merge-first",
            runtimeKeyFingerprint: firstIdentity.fingerprint
        )
        let secondRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "durable-merge-second",
            runtimeKeyFingerprint: secondIdentity.fingerprint
        )
        let firstRegistry = RelayAllocationRegistry(persistenceURL: storeURL)
        let secondRegistry = RelayAllocationRegistry(persistenceURL: storeURL)
        let firstProposal = try firstRegistry.proposedGeneration(
            relayID: firstRelayID,
            runtimeIdentity: firstIdentity
        )
        let secondProposal = try secondRegistry.proposedGeneration(
            relayID: secondRelayID,
            runtimeIdentity: secondIdentity
        )
        let firstBinding = try RelayAllocationBinding(
            relayID: firstRelayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "durable-merge-first-nonce",
            runtimeIdentity: firstIdentity,
            ticketGeneration: firstProposal.generation
        )
        let secondBinding = try RelayAllocationBinding(
            relayID: secondRelayID,
            relayExpiresAtEpochMillis: 4_102_444_800_001,
            relayNonce: "durable-merge-second-nonce",
            runtimeIdentity: secondIdentity,
            ticketGeneration: secondProposal.generation
        )

        try firstRegistry.commit(firstBinding, replacingGeneration: nil)
        try secondRegistry.commit(secondBinding, replacingGeneration: nil)

        let persisted = RelayAllocationRegistry(persistenceURL: storeURL)
        XCTAssertEqual(persisted.tombstone(relayID: firstRelayID), firstBinding)
        XCTAssertEqual(persisted.tombstone(relayID: secondRelayID), secondBinding)
    }

    func testStaleDurableCreateProposalsProduceOneCommitAndOneConflict() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "durable-create-conflict",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let registries = [
            RelayAllocationRegistry(persistenceURL: storeURL),
            RelayAllocationRegistry(persistenceURL: storeURL),
        ]
        let proposals = try registries.map {
            try $0.proposedGeneration(relayID: relayID, runtimeIdentity: identity)
        }
        XCTAssertTrue(proposals.allSatisfy { $0.operation == .create && $0.generation == 1 })
        let candidates = try [
            RelayAllocationBinding(
                relayID: relayID,
                relayExpiresAtEpochMillis: 4_102_444_800_000,
                relayNonce: "durable-create-first",
                runtimeIdentity: identity,
                ticketGeneration: proposals[0].generation
            ),
            RelayAllocationBinding(
                relayID: relayID,
                relayExpiresAtEpochMillis: 4_102_444_800_001,
                relayNonce: "durable-create-second",
                runtimeIdentity: identity,
                ticketGeneration: proposals[1].generation
            ),
        ]
        var commitCount = 0
        var conflictCount = 0

        for (registry, candidate) in zip(registries, candidates) {
            do {
                try registry.commit(candidate, replacingGeneration: nil)
                commitCount += 1
            } catch RelayAllocationError.allocationConflict {
                conflictCount += 1
            } catch {
                XCTFail("Unexpected commit error: \(error)")
            }
        }

        XCTAssertEqual(commitCount, 1)
        XCTAssertEqual(conflictCount, 1)
        XCTAssertEqual(
            RelayAllocationRegistry(persistenceURL: storeURL).tombstone(relayID: relayID),
            candidates[0]
        )
    }

    func testStaleDurablePairedClaimsProduceOneBindingOneTombstoneAndOneConflict() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let runtimeIdentity = try makeIdentity()
        let clientIdentity = try makeIdentity()
        let routeToken = "durable-paired-claim-conflict"
        let bootstrapRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: clientIdentity.fingerprint
        )
        let bootstrap = try RelayAllocationBinding(
            relayID: bootstrapRelayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "durable-bootstrap",
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: 1
        )
        try RelayAllocationRegistry(persistenceURL: storeURL).commit(
            bootstrap,
            replacingGeneration: nil
        )
        let registries = [
            RelayAllocationRegistry(persistenceURL: storeURL),
            RelayAllocationRegistry(persistenceURL: storeURL),
        ]
        let proposals = try registries.map {
            try $0.pairedRenewalProposal(
                bootstrapRelayID: bootstrapRelayID,
                pairedRelayID: pairedRelayID,
                runtimeIdentity: runtimeIdentity,
                clientKeyFingerprint: clientIdentity.fingerprint
            )
        }
        XCTAssertTrue(proposals.allSatisfy { $0.operation == .claim })
        let candidates = try [
            RelayAllocationBinding(
                relayID: pairedRelayID,
                relayExpiresAtEpochMillis: 4_102_444_800_001,
                relayNonce: "durable-paired-first",
                runtimeIdentity: runtimeIdentity,
                ticketGeneration: 2,
                authorizationMode: .pairedDeviceP256V1,
                pairedClientKeyFingerprint: clientIdentity.fingerprint
            ),
            RelayAllocationBinding(
                relayID: pairedRelayID,
                relayExpiresAtEpochMillis: 4_102_444_800_002,
                relayNonce: "durable-paired-second",
                runtimeIdentity: runtimeIdentity,
                ticketGeneration: 2,
                authorizationMode: .pairedDeviceP256V1,
                pairedClientKeyFingerprint: clientIdentity.fingerprint
            ),
        ]
        var commitCount = 0
        var conflictCount = 0

        for index in registries.indices {
            do {
                try registries[index].commitPairedRenewal(
                    candidates[index],
                    replacing: proposals[index].currentBinding,
                    operation: proposals[index].operation
                )
                commitCount += 1
            } catch RelayAllocationError.allocationConflict {
                conflictCount += 1
            } catch {
                XCTFail("Unexpected paired commit error: \(error)")
            }
        }

        XCTAssertEqual(commitCount, 1)
        XCTAssertEqual(conflictCount, 1)
        let persisted = RelayAllocationRegistry(persistenceURL: storeURL)
        XCTAssertNil(persisted.tombstone(relayID: bootstrapRelayID))
        XCTAssertEqual(persisted.tombstone(relayID: pairedRelayID), candidates[0])
        let consumed = try XCTUnwrap(
            persisted.consumedBootstrapTombstone(relayID: bootstrapRelayID)
        )
        XCTAssertEqual(consumed.pairedRelayID, pairedRelayID)
        XCTAssertEqual(consumed.pairedClientKeyFingerprint, clientIdentity.fingerprint)
        XCTAssertEqual(consumed.consumedTicketGeneration, bootstrap.ticketGeneration)
    }

    func testStaleBootstrapCreateCannotRecreateConsumedPairClaim() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let runtimeIdentity = try makeIdentity()
        let clientIdentity = try makeIdentity()
        let routeToken = "stale-create-after-pair-claim"
        let bootstrapRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: clientIdentity.fingerprint
        )
        let staleRegistry = RelayAllocationRegistry(persistenceURL: storeURL)
        let staleProposal = try staleRegistry.proposedGeneration(
            relayID: bootstrapRelayID,
            runtimeIdentity: runtimeIdentity
        )
        let bootstrap = try RelayAllocationBinding(
            relayID: bootstrapRelayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "stale-create-bootstrap",
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: staleProposal.generation
        )
        let authoritativeRegistry = RelayAllocationRegistry(persistenceURL: storeURL)
        try authoritativeRegistry.commit(bootstrap, replacingGeneration: nil)
        let claim = try authoritativeRegistry.pairedRenewalProposal(
            bootstrapRelayID: bootstrapRelayID,
            pairedRelayID: pairedRelayID,
            runtimeIdentity: runtimeIdentity,
            clientKeyFingerprint: clientIdentity.fingerprint
        )
        let paired = try RelayAllocationBinding(
            relayID: pairedRelayID,
            relayExpiresAtEpochMillis: 4_102_444_800_001,
            relayNonce: "stale-create-paired",
            runtimeIdentity: runtimeIdentity,
            ticketGeneration: bootstrap.ticketGeneration + 1,
            authorizationMode: .pairedDeviceP256V1,
            pairedClientKeyFingerprint: clientIdentity.fingerprint
        )
        try authoritativeRegistry.commitPairedRenewal(
            paired,
            replacing: claim.currentBinding,
            operation: claim.operation
        )

        XCTAssertThrowsError(
            try staleRegistry.commit(bootstrap, replacingGeneration: nil)
        ) { error in
            XCTAssertEqual(error as? RelayAllocationError, .authorizationDowngrade)
        }

        let restarted = RelayAllocationRegistry(persistenceURL: storeURL)
        XCTAssertTrue(restarted.isPersistenceReady)
        XCTAssertNil(restarted.tombstone(relayID: bootstrapRelayID))
        XCTAssertEqual(restarted.tombstone(relayID: pairedRelayID), paired)
        XCTAssertEqual(
            restarted.consumedBootstrapTombstone(relayID: bootstrapRelayID)?.pairedRelayID,
            pairedRelayID
        )
    }

    func testPreCreatedDurableReaderObservesLaterCommit() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "durable-reader-refresh",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let reader = RelayAllocationRegistry(persistenceURL: storeURL)
        let writer = RelayAllocationRegistry(persistenceURL: storeURL)
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "durable-reader-refresh-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )

        XCTAssertNil(reader.tombstone(relayID: relayID))
        try writer.commit(binding, replacingGeneration: nil)

        XCTAssertEqual(reader.tombstone(relayID: relayID), binding)
    }

    func testDurableStoreAndCoordinationFilesUseOwnerOnlyPermissions() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "durable-file-permissions",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let registry = RelayAllocationRegistry(persistenceURL: storeURL)
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "durable-file-permissions-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        try registry.commit(binding, replacingGeneration: nil)
        let ownership = try RelayAllocationStoreOwnership.acquire(storeURL: storeURL)
        defer { withExtendedLifetime(ownership) {} }

        XCTAssertEqual(try posixPermissions(at: storeURL), 0o600)
        XCTAssertEqual(
            try posixPermissions(
                at: RelayAllocationStoreCoordination.transactionLockURL(for: storeURL)
            ),
            0o600
        )
    }

    func testStoreOwnershipIsExclusiveInProcessAndReacquirableAfterRelease() throws {
        let storeURL = try temporaryAllocationStoreURL()
        XCTAssertTrue(RelayAllocationRegistry(persistenceURL: storeURL).isPersistenceReady)
        var firstOwnership: RelayAllocationStoreOwnership? = try .acquire(storeURL: storeURL)

        XCTAssertThrowsError(try RelayAllocationStoreOwnership.acquire(storeURL: storeURL)) {
            XCTAssertEqual(
                $0 as? RelayAllocationStoreCoordinationError,
                .storeAlreadyOwned
            )
        }

        withExtendedLifetime(firstOwnership) {}
        firstOwnership = nil
        let reacquired = try RelayAllocationStoreOwnership.acquire(storeURL: storeURL)
        withExtendedLifetime(reacquired) {}
    }

    func testRepeatedRegistryCreationReusesPooledLockDescriptor() throws {
        let storeURL = try temporaryAllocationStoreURL()
        XCTAssertTrue(RelayAllocationRegistry(persistenceURL: storeURL).isPersistenceReady)
        let retainedBefore = RelayAllocationStoreCoordination
            .retainedLockDescriptorCountForTesting()

        for _ in 0..<100 {
            XCTAssertTrue(RelayAllocationRegistry(persistenceURL: storeURL).isPersistenceReady)
        }

        XCTAssertEqual(
            RelayAllocationStoreCoordination.retainedLockDescriptorCountForTesting(),
            retainedBefore
        )
    }

    func testClosingSiblingTransactionLockDoesNotReleaseActiveProcessRecordLock() throws {
        let storeURL = try temporaryAllocationStoreURL()
        var siblingLock: RelayAllocationStoreTransactionLock? = try .init(storeURL: storeURL)
        let activeLock = try RelayAllocationStoreTransactionLock(storeURL: storeURL)
        let lockPath = RelayAllocationStoreCoordination
            .transactionLockURL(for: storeURL)
            .path

        try activeLock.withExclusiveLock { _ in
            siblingLock = nil
            let hardLinkURL = storeURL.deletingLastPathComponent()
                .appendingPathComponent("transaction-lock-hard-link")
            try FileManager.default.linkItem(
                at: RelayAllocationStoreCoordination.transactionLockURL(for: storeURL),
                to: hardLinkURL
            )
            XCTAssertThrowsError(
                try RelayAllocationStoreTransactionLock(storeURL: storeURL)
            )
            let contender = Process()
            contender.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            contender.arguments = [
                "-c",
                """
                import fcntl, os, sys
                descriptor = os.open(sys.argv[1], os.O_RDWR)
                try:
                    fcntl.lockf(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    sys.exit(0)
                sys.exit(1)
                """,
                lockPath,
            ]
            try contender.run()
            contender.waitUntilExit()
            XCTAssertEqual(contender.terminationStatus, 0)
            try FileManager.default.removeItem(at: hardLinkURL)
        }
        withExtendedLifetime(siblingLock) {}
    }

    func testStoreOwnershipCanonicalizesSymlinkedParentAliases() throws {
        let storeURL = try temporaryAllocationStoreURL()
        XCTAssertTrue(RelayAllocationRegistry(persistenceURL: storeURL).isPersistenceReady)
        let directoryURL = storeURL.deletingLastPathComponent()
        let aliasDirectoryURL = directoryURL.appendingPathComponent("alias", isDirectory: true)
        try FileManager.default.createSymbolicLink(
            at: aliasDirectoryURL,
            withDestinationURL: directoryURL
        )
        let aliasStoreURL = aliasDirectoryURL.appendingPathComponent(storeURL.lastPathComponent)
        let ownership = try RelayAllocationStoreOwnership.acquire(storeURL: storeURL)
        defer { withExtendedLifetime(ownership) {} }

        XCTAssertThrowsError(
            try RelayAllocationStoreOwnership.acquire(storeURL: aliasStoreURL)
        ) {
            XCTAssertEqual(
                $0 as? RelayAllocationStoreCoordinationError,
                .storeAlreadyOwned
            )
        }
    }

    func testDeletedEstablishedDurableStoreFailsClosedForLiveAndRestartedRegistries() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "deleted-established-store",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "deleted-established-store-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        let liveRegistry = RelayAllocationRegistry(persistenceURL: storeURL)
        try liveRegistry.commit(binding, replacingGeneration: nil)
        try FileManager.default.removeItem(at: storeURL)

        XCTAssertNil(liveRegistry.binding(relayID: relayID))
        XCTAssertThrowsError(
            try liveRegistry.proposedGeneration(relayID: relayID, runtimeIdentity: identity)
        ) {
            XCTAssertEqual($0 as? RelayAllocationError, .persistenceFailed)
        }

        let restartedRegistry = RelayAllocationRegistry(persistenceURL: storeURL)
        XCTAssertNil(restartedRegistry.tombstone(relayID: relayID))
        XCTAssertThrowsError(
            try restartedRegistry.proposedGeneration(relayID: relayID, runtimeIdentity: identity)
        ) {
            XCTAssertEqual($0 as? RelayAllocationError, .persistenceFailed)
        }
    }

    func testGroupOrWorldWritableStoreParentFailsClosed() throws {
        let storeURL = try temporaryAllocationStoreURL()
        try FileManager.default.setAttributes(
            [.posixPermissions: NSNumber(value: 0o777)],
            ofItemAtPath: storeURL.deletingLastPathComponent().path
        )
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "insecure-parent",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let registry = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertThrowsError(
            try registry.proposedGeneration(relayID: relayID, runtimeIdentity: identity)
        ) {
            XCTAssertEqual($0 as? RelayAllocationError, .persistenceFailed)
        }
    }

    func testValidUnversionedV1StoreIsRevokedIntoEmptyTokenBoundV4Store() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let legacyRelayID = "rt1-" + String(repeating: "a", count: 64)
        let legacyJSON = """
        [{"relay_id":"\(legacyRelayID)","relay_expires_at":4102444800000,"relay_nonce":"legacy-nonce-1"}]
        """
        try Data(legacyJSON.utf8).write(to: storeURL)
        try FileManager.default.setAttributes(
            [.posixPermissions: NSNumber(value: 0o644)],
            ofItemAtPath: storeURL.path
        )

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertTrue(registry.isPersistenceReady)
        XCTAssertEqual(registry.count(), 0)
        XCTAssertNil(registry.tombstone(relayID: legacyRelayID))
        let envelope = try XCTUnwrap(
            try JSONSerialization.jsonObject(with: Data(contentsOf: storeURL)) as? [String: Any]
        )
        XCTAssertEqual(envelope["schema_version"] as? Int, 4)
        XCTAssertEqual((envelope["coordination_token"] as? String)?.count, 64)
        XCTAssertEqual((envelope["allocations"] as? [Any])?.count, 0)
        XCTAssertEqual((envelope["consumed_bootstrap_allocations"] as? [Any])?.count, 0)
        XCTAssertEqual(try posixPermissions(at: storeURL), 0o600)
    }

    func testDanglingDurableStoreSymlinkFailsClosed() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let missingTarget = storeURL.deletingLastPathComponent()
            .appendingPathComponent("missing-store-target.json")
        try FileManager.default.createSymbolicLink(
            at: storeURL,
            withDestinationURL: missingTarget
        )

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertFalse(registry.isPersistenceReady)
        let destination = try FileManager.default.destinationOfSymbolicLink(
            atPath: storeURL.path
        )
        XCTAssertTrue(destination.hasSuffix("missing-store-target.json"))
    }

    func testHardLinkedStoreAliasFailsClosedWithoutDivergingAtomicWrites() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "hard-link-store",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "hard-link-store-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        let original = RelayAllocationRegistry(persistenceURL: storeURL)
        try original.commit(binding, replacingGeneration: nil)
        let aliasURL = storeURL.deletingLastPathComponent()
            .appendingPathComponent("allocations-hard-link.json")
        try FileManager.default.linkItem(at: storeURL, to: aliasURL)

        let alias = RelayAllocationRegistry(persistenceURL: aliasURL)

        XCTAssertFalse(alias.isPersistenceReady)
        XCTAssertNil(original.binding(relayID: relayID))
        XCTAssertFalse(original.isPersistenceReady)
    }

    func testPostRenameDirectorySyncFailureReconcilesCommittedEnvelopeBeforeSuccess() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "post-rename-reconciliation",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "post-rename-reconciliation-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        let registry = RelayAllocationRegistry(persistenceURL: storeURL)
        RelayAllocationStoreCoordination.failNextAtomicDirectorySyncForTesting()

        try registry.commit(binding, replacingGeneration: nil)

        XCTAssertTrue(registry.isPersistenceReady)
        XCTAssertEqual(registry.tombstone(relayID: relayID), binding)
        XCTAssertEqual(
            RelayAllocationRegistry(persistenceURL: storeURL).tombstone(relayID: relayID),
            binding
        )
    }

    func testUninitializedMarkerRecoversTokenMatchedDurableStoreAfterInterruptedInitialization() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "interrupted-initialization-recovery",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "interrupted-initialization-recovery-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        let original = RelayAllocationRegistry(persistenceURL: storeURL)
        try original.commit(binding, replacingGeneration: nil)
        let lockURL = RelayAllocationStoreCoordination.transactionLockURL(for: storeURL)
        let establishedMarkerData = try Data(contentsOf: lockURL)
        let establishedMarker = try XCTUnwrap(
            String(data: establishedMarkerData, encoding: .utf8)
        )
        XCTAssertTrue(establishedMarker.contains("\nstate=E\n"))
        let uninitializedMarker = establishedMarker.replacingOccurrences(
            of: "\nstate=E\n",
            with: "\nstate=U\n"
        )
        let handle = try FileHandle(forWritingTo: lockURL)
        try handle.seek(toOffset: 0)
        try handle.write(contentsOf: Data(uninitializedMarker.utf8))
        try handle.truncate(atOffset: UInt64(uninitializedMarker.utf8.count))
        try handle.synchronize()
        try handle.close()

        let recovered = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertTrue(recovered.isPersistenceReady)
        XCTAssertEqual(recovered.tombstone(relayID: relayID), binding)
        let recoveredMarker = try XCTUnwrap(
            String(data: Data(contentsOf: lockURL), encoding: .utf8)
        )
        XCTAssertTrue(recoveredMarker.contains("\nstate=E\n"))
    }

    func testEstablishedLockReplacementQuarantinesLiveAndReplacementRegistries() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "replaced-lock-file",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "replaced-lock-file-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        let liveRegistry = RelayAllocationRegistry(persistenceURL: storeURL)
        try liveRegistry.commit(binding, replacingGeneration: nil)
        let ownership = try RelayAllocationStoreOwnership.acquire(storeURL: storeURL)
        defer { withExtendedLifetime(ownership) {} }
        let lockURL = RelayAllocationStoreCoordination.transactionLockURL(for: storeURL)
        try FileManager.default.removeItem(at: lockURL)

        let replacementRegistry = RelayAllocationRegistry(persistenceURL: storeURL)

        XCTAssertFalse(replacementRegistry.isPersistenceReady)
        XCTAssertNil(liveRegistry.binding(relayID: relayID))
        XCTAssertFalse(liveRegistry.isPersistenceReady)
        XCTAssertThrowsError(try RelayAllocationStoreOwnership.acquire(storeURL: storeURL)) {
            XCTAssertEqual(
                $0 as? RelayAllocationStoreCoordinationError,
                .lockUnavailable
            )
        }
    }

    func testCaseVariantStorePathSharesOneOwnerOnCaseInsensitiveVolumes() throws {
        let rootStoreURL = try temporaryAllocationStoreURL()
        let directoryURL = rootStoreURL.deletingLastPathComponent()
            .appendingPathComponent("CaseSensitiveProbe", isDirectory: true)
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: false)
        let storeURL = directoryURL.appendingPathComponent("Allocations.json")
        XCTAssertTrue(RelayAllocationRegistry(persistenceURL: storeURL).isPersistenceReady)
        let aliasURL = directoryURL.appendingPathComponent("allocations.JSON")
        guard FileManager.default.fileExists(atPath: aliasURL.path) else {
            throw XCTSkip("The test volume is case-sensitive; case variants are distinct paths.")
        }
        let ownership = try RelayAllocationStoreOwnership.acquire(storeURL: storeURL)
        defer { withExtendedLifetime(ownership) {} }

        XCTAssertThrowsError(try RelayAllocationStoreOwnership.acquire(storeURL: aliasURL)) {
            XCTAssertEqual(
                $0 as? RelayAllocationStoreCoordinationError,
                .storeAlreadyOwned
            )
        }
    }

    func testTransactionLockSymlinkAndNonregularTargetsFailClosed() throws {
        for targetKind in ["symlink", "directory"] {
            let storeURL = try temporaryAllocationStoreURL()
            let lockURL = RelayAllocationStoreCoordination.transactionLockURL(for: storeURL)
            if targetKind == "symlink" {
                let targetURL = storeURL.deletingLastPathComponent()
                    .appendingPathComponent("transaction-lock-target")
                XCTAssertTrue(FileManager.default.createFile(atPath: targetURL.path, contents: Data()))
                try FileManager.default.createSymbolicLink(
                    at: lockURL,
                    withDestinationURL: targetURL
                )
            } else {
                try FileManager.default.createDirectory(at: lockURL, withIntermediateDirectories: false)
            }

            let registry = RelayAllocationRegistry(persistenceURL: storeURL)
            let identity = try makeIdentity()
            let relayID = RelayAllocationIdentityChallenge.relayID(
                routeToken: "transaction-lock-\(targetKind)",
                runtimeKeyFingerprint: identity.fingerprint
            )
            XCTAssertThrowsError(
                try registry.proposedGeneration(relayID: relayID, runtimeIdentity: identity),
                targetKind
            ) {
                XCTAssertEqual($0 as? RelayAllocationError, .persistenceFailed)
            }
        }
    }

    func testDurableStoreSymlinkFailsClosed() throws {
        let storeURL = try temporaryAllocationStoreURL()
        let targetURL = storeURL.deletingLastPathComponent()
            .appendingPathComponent("actual-allocations.json")
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "store-symlink",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "store-symlink-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        try RelayAllocationRegistry(persistenceURL: targetURL).commit(
            binding,
            replacingGeneration: nil
        )
        try FileManager.default.createSymbolicLink(at: storeURL, withDestinationURL: targetURL)

        let registry = RelayAllocationRegistry(persistenceURL: storeURL)
        XCTAssertNil(registry.tombstone(relayID: relayID))
        XCTAssertThrowsError(
            try registry.proposedGeneration(relayID: relayID, runtimeIdentity: identity)
        ) {
            XCTAssertEqual($0 as? RelayAllocationError, .persistenceFailed)
        }
    }

    func testLegacyCorruptAndUnknownStoresFailClosed() throws {
        let identity = try makeIdentity()
        let relayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: "load-failure-route",
            runtimeKeyFingerprint: identity.fingerprint
        )
        let binding = try RelayAllocationBinding(
            relayID: relayID,
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "load-failure-nonce",
            runtimeIdentity: identity,
            ticketGeneration: 1
        )
        for object in [
            [["relay_id": "legacy"]],
            ["schema_version": 99, "allocations": []],
            ["schema_version": 2, "allocations": [], "unknown": true]
        ] as [Any] {
            let storeURL = try temporaryAllocationStoreURL()
            try JSONSerialization.data(withJSONObject: object).write(to: storeURL)
            let registry = RelayAllocationRegistry(persistenceURL: storeURL)
            XCTAssertEqual(registry.count(), 0)
            XCTAssertNil(registry.binding(relayID: relayID))
            XCTAssertFalse(registry.isValid(relayID: relayID))
            XCTAssertThrowsError(
                try registry.proposedGeneration(relayID: relayID, runtimeIdentity: identity)
            ) { XCTAssertEqual($0 as? RelayAllocationError, .persistenceFailed) }
            XCTAssertThrowsError(try registry.commit(binding, replacingGeneration: nil)) {
                XCTAssertEqual($0 as? RelayAllocationError, .persistenceFailed)
            }
            XCTAssertThrowsError(try registry.withRevalidatedBinding(binding) {}) {
                XCTAssertEqual($0 as? RelayAllocationError, .persistenceFailed)
            }
        }
        let corruptURL = try temporaryAllocationStoreURL()
        try Data("not-json".utf8).write(to: corruptURL)
        let corrupt = RelayAllocationRegistry(persistenceURL: corruptURL)
        XCTAssertEqual(corrupt.count(), 0)
        XCTAssertThrowsError(
            try corrupt.proposedGeneration(relayID: relayID, runtimeIdentity: identity)
        ) { XCTAssertEqual($0 as? RelayAllocationError, .persistenceFailed) }
    }

    private func temporaryAllocationStoreURL() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("AetherLinkRelayTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock {
            try? FileManager.default.removeItem(at: directory)
        }
        return directory.appendingPathComponent("allocations.json")
    }

    private func allocationResponseLine(
        relayID: String = "relay-1",
        relaySecret: String = "secret-1",
        relayExpiresAtEpochMillis: Int64 = 4_102_444_800_000,
        relayNonce: String = "nonce-1"
    ) -> String {
        """
        \(RelayAllocation.responsePrefix){"relay_id":"\(relayID)","relay_secret":"\(relaySecret)","relay_expires_at":\(relayExpiresAtEpochMillis),"relay_nonce":"\(relayNonce)"}
        """
    }

    private var nonCanonicalAllocationResponseRelayIDs: [String] {
        [
            "",
            " relay-1",
            "relay-1 ",
            "relay 1",
            "https://relay.example.test/room?route_token=secret",
            "relay/id",
            "relay?query",
            "relay#fragment",
            "user@relay-id",
            "relay.example.test:443",
            String(repeating: "r", count: relayControlLineRelayIDMaxCharacters + 1)
        ]
    }

    private func writeAllocationTicketsJSON(_ tickets: [[String: Any]], to url: URL) throws {
        let data = try JSONSerialization.data(withJSONObject: tickets, options: [.prettyPrinted, .sortedKeys])
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try data.write(to: url)
    }

    private func posixPermissions(at url: URL) throws -> Int {
        let attributes = try FileManager.default.attributesOfItem(atPath: url.path)
        return try XCTUnwrap(attributes[.posixPermissions] as? NSNumber).intValue & 0o777
    }

    private func makeIdentity() throws -> RelayRuntimeIdentity {
        try makeIdentity(privateKey: P256.Signing.PrivateKey())
    }

    private func makeIdentity(
        privateKey: P256.Signing.PrivateKey
    ) throws -> RelayRuntimeIdentity {
        let publicKeyData = privateKey.publicKey.derRepresentation
        let fingerprint = SHA256.hash(data: publicKeyData)
            .map { String(format: "%02x", $0) }
            .joined()
        return try RelayRuntimeIdentity(
            publicKeyBase64: publicKeyData.base64EncodedString(),
            fingerprint: fingerprint
        )
    }
}
