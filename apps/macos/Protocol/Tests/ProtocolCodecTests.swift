import XCTest
@testable import BridgeProtocol

final class ProtocolCodecTests: XCTestCase {
    func testLengthPrefixedRoundTrip() throws {
        let codec = ProtocolCodec()
        let envelope = ProtocolEnvelope(type: MessageType.modelsList)

        let decoded = try codec.decodeFrame(try codec.encodeFrame(envelope))

        XCTAssertEqual(decoded.type, MessageType.modelsList)
        XCTAssertEqual(decoded.requestID, envelope.requestID)
    }

    func testRelayPlaintextFrameCeilingReservesAuthenticationTag() throws {
        let codec = ProtocolCodec()

        func envelope(encodedBodyLength: Int) throws -> ProtocolEnvelope {
            var envelope = ProtocolEnvelope(
                type: MessageType.modelsList,
                requestID: "relay-plaintext-boundary",
                timestamp: Date(timeIntervalSince1970: 0),
                payload: ["padding": .string("")]
            )
            let emptyLength = try codec.encodeEnvelopeBody(envelope).count
            XCTAssertGreaterThanOrEqual(encodedBodyLength, emptyLength)
            envelope.payload["padding"] = .string(
                String(repeating: "x", count: encodedBodyLength - emptyLength)
            )
            XCTAssertEqual(try codec.encodeEnvelopeBody(envelope).count, encodedBodyLength)
            return envelope
        }

        XCTAssertEqual(RelayFrameCipher.authenticationTagBytes, 16)
        XCTAssertEqual(
            ProtocolCodec.maxRelayPlaintextFrameBytes
                + RelayFrameCipher.authenticationTagBytes,
            ProtocolCodec.maxFrameBytes
        )
        XCTAssertNoThrow(try codec.validateFrameBodyLength(
            ProtocolCodec.maxRelayPlaintextFrameBytes
                + RelayFrameCipher.authenticationTagBytes
        ))
        XCTAssertThrowsError(try codec.validateFrameBodyLength(
            ProtocolCodec.maxRelayPlaintextFrameBytes
                + RelayFrameCipher.authenticationTagBytes + 1
        ))

        let exactEnvelope = try envelope(
            encodedBodyLength: ProtocolCodec.maxRelayPlaintextFrameBytes
        )
        let exactBody = try codec.encodeEnvelopeBody(exactEnvelope)
        XCTAssertNoThrow(try codec.validateRelayPlaintextBodyLength(exactBody.count))

        let oversizedEnvelope = try envelope(
            encodedBodyLength: ProtocolCodec.maxRelayPlaintextFrameBytes + 1
        )
        let oversizedBody = try codec.encodeEnvelopeBody(oversizedEnvelope)
        XCTAssertThrowsError(try codec.validateRelayPlaintextBodyLength(oversizedBody.count))
    }

    func testSemanticDuplicateThresholdPreservesExactIntegerWireKind() throws {
        let codec = ProtocolCodec()
        let prefix = """
        {"version":1,"type":"memory.semantic_duplicate_suggestions.list","request_id":"request","timestamp":"2026-07-14T00:00:00Z","payload":{"embedding_model_id":"ollama:nomic-embed-text","minimum_similarity_basis_points":
        """
        let suffix = "}}"

        let exact = try codec.decodeEnvelope(Data((prefix + "9400" + suffix).utf8))
        let integralFloat = try codec.decodeEnvelope(Data((prefix + "9400.0" + suffix).utf8))
        let exponent = try codec.decodeEnvelope(Data((prefix + "9.4e3" + suffix).utf8))

        XCTAssertEqual(exact.payload["minimum_similarity_basis_points"], .integer(9_400))
        XCTAssertEqual(integralFloat.payload["minimum_similarity_basis_points"], .number(9_400))
        XCTAssertEqual(exponent.payload["minimum_similarity_basis_points"], .number(9_400))
    }

    func testSemanticDuplicateClusterThresholdPreservesExactIntegerWireKind() throws {
        let codec = ProtocolCodec()
        let prefix = """
        {"version":1,"type":"memory.semantic_duplicate_clusters.list","request_id":"request","timestamp":"2026-07-14T00:00:00Z","payload":{"embedding_model_id":"ollama:nomic-embed-text","minimum_similarity_basis_points":
        """
        let suffix = "}}"

        let exact = try codec.decodeEnvelope(Data((prefix + "9400" + suffix).utf8))
        let integralFloat = try codec.decodeEnvelope(Data((prefix + "9400.0" + suffix).utf8))
        let exponent = try codec.decodeEnvelope(Data((prefix + "9.4e3" + suffix).utf8))

        XCTAssertEqual(MessageType.memorySemanticDuplicateClustersList, "memory.semantic_duplicate_clusters.list")
        XCTAssertEqual(exact.payload["minimum_similarity_basis_points"], .integer(9_400))
        XCTAssertEqual(integralFloat.payload["minimum_similarity_basis_points"], .number(9_400))
        XCTAssertEqual(exponent.payload["minimum_similarity_basis_points"], .number(9_400))
    }

    func testRelayAllocationChallengePayloadRoundTripsExactWireShape() throws {
        let payload = try relayAllocationChallengePayload()
        let encoded = try JSONEncoder().encode(payload)
        let object = try jsonObject(encoded)
        let decoded = try JSONDecoder().decode(RelayAllocationChallengePayload.self, from: encoded)

        XCTAssertEqual(decoded, payload)
        XCTAssertEqual(
            Set(object.keys),
            [
                "proof_scheme", "protocol_version", "operation", "authorization_id",
                "current_relay_id", "next_relay_id", "route_token_hash",
                "runtime_key_fingerprint",
                "client_key_fingerprint", "current_ticket_generation",
                "next_ticket_generation", "current_relay_expires_at",
                "current_relay_nonce", "next_relay_expires_at", "next_relay_nonce",
                "challenge", "challenge_expires_at", "transport_binding",
            ]
        )
        XCTAssertNil(object["request_id"])
        XCTAssertEqual(MessageType.relayAllocationChallenge, "relay.allocation.challenge")
        XCTAssertEqual(MessageType.relayAllocationAuthorization, "relay.allocation.authorization")
    }

    func testRelayAllocationChallengePayloadRejectsMalformedAndSecretBearingSamples() throws {
        let decoder = JSONDecoder()
        let base = try jsonObject(JSONEncoder().encode(relayAllocationChallengePayload()))
        var invalidSamples: [(String, [String: Any])] = [
            ("missing field", removing("authorization_id", from: base)),
            ("unknown field", replacing("unknown", with: "metadata", in: base)),
            ("route token secret", replacing("route_token", with: "secret", in: base)),
            ("relay secret", replacing("relay_secret", with: "secret", in: base)),
            ("wrong scheme", replacing("proof_scheme", with: "runtime-p256-v1", in: base)),
            ("wrong version", replacing("protocol_version", with: 1, in: base)),
            ("wrong operation", replacing("operation", with: "create", in: base)),
            ("blank authorization id", replacing("authorization_id", with: "   ", in: base)),
            ("oversized authorization id", replacing("authorization_id", with: String(repeating: "a", count: 513), in: base)),
            ("legacy relay id", replacing("relay_id", with: "rt2-\(Self.hexA)", in: base)),
            ("malformed current relay id", replacing("current_relay_id", with: Self.hexA, in: base)),
            ("malformed next relay id", replacing("next_relay_id", with: Self.hexB, in: base)),
            ("equal claim relay ids", replacing("next_relay_id", with: "rt2-\(Self.hexA)", in: base)),
            ("malformed route token hash", replacing("route_token_hash", with: Self.hexA.uppercased(), in: base)),
            ("malformed runtime fingerprint", replacing("runtime_key_fingerprint", with: String(Self.hexA.dropLast()), in: base)),
            ("malformed client fingerprint", replacing("client_key_fingerprint", with: Self.hexB.uppercased(), in: base)),
            ("malformed challenge", replacing("challenge", with: String(Self.hexA.dropLast()), in: base)),
            ("malformed binding", replacing("transport_binding", with: Self.hexB.uppercased(), in: base)),
            ("whitespace current nonce", replacing("current_relay_nonce", with: "current nonce", in: base)),
            ("oversized next nonce", replacing("next_relay_nonce", with: String(repeating: "n", count: 513), in: base)),
            ("noninteger generation", replacing("current_ticket_generation", with: 1.5, in: base)),
        ]
        for field in [
            "current_ticket_generation",
            "next_ticket_generation",
            "current_relay_expires_at",
            "next_relay_expires_at",
            "challenge_expires_at",
        ] {
            invalidSamples.append(("nonpositive \(field)", replacing(field, with: 0, in: base)))
        }

        for (label, sample) in invalidSamples {
            XCTAssertThrowsError(
                try decoder.decode(
                    RelayAllocationChallengePayload.self,
                    from: JSONSerialization.data(withJSONObject: sample)
                ),
                label
            )
        }
    }

    func testRelayAllocationChallengePayloadRenewAllowsEqualOrDifferentRelayIDs() throws {
        let decoder = JSONDecoder()
        let base = try jsonObject(JSONEncoder().encode(relayAllocationChallengePayload()))
        let renew = replacing("operation", with: "renew", in: base)

        XCTAssertNoThrow(try decoder.decode(
            RelayAllocationChallengePayload.self,
            from: JSONSerialization.data(withJSONObject: renew)
        ))
        XCTAssertNoThrow(try decoder.decode(
            RelayAllocationChallengePayload.self,
            from: JSONSerialization.data(withJSONObject: replacing(
                "next_relay_id",
                with: "rt2-\(Self.hexA)",
                in: renew
            ))
        ))
    }

    func testRelayAllocationAuthorizationPayloadRoundTripsExactWireShape() throws {
        let payload = try RelayAllocationAuthorizationPayload(
            proofScheme: relayAllocationProofScheme,
            authorizationID: "authorization-1",
            challenge: Self.hexA,
            clientKeyFingerprint: Self.hexB,
            transportBinding: Self.hexA,
            clientSignature: "MEUCIQ=="
        )
        let encoded = try JSONEncoder().encode(payload)
        let object = try jsonObject(encoded)

        XCTAssertEqual(try JSONDecoder().decode(RelayAllocationAuthorizationPayload.self, from: encoded), payload)
        XCTAssertEqual(
            Set(object.keys),
            [
                "proof_scheme", "authorization_id", "challenge",
                "client_key_fingerprint", "transport_binding", "client_signature",
            ]
        )
        XCTAssertNil(object["request_id"])
    }

    func testRelayAllocationAuthorizationPayloadRejectsMalformedAndSecretBearingSamples() throws {
        let valid = try RelayAllocationAuthorizationPayload(
            proofScheme: relayAllocationProofScheme,
            authorizationID: "authorization-1",
            challenge: Self.hexA,
            clientKeyFingerprint: Self.hexB,
            transportBinding: Self.hexA,
            clientSignature: "MEUCIQ=="
        )
        let base = try jsonObject(JSONEncoder().encode(valid))
        let invalidSamples: [(String, [String: Any])] = [
            ("missing field", removing("client_signature", from: base)),
            ("unknown field", replacing("unknown", with: "metadata", in: base)),
            ("route token secret", replacing("route_token", with: "secret", in: base)),
            ("relay secret", replacing("relay_secret", with: "secret", in: base)),
            ("wrong scheme", replacing("proof_scheme", with: "runtime-p256-v1", in: base)),
            ("blank authorization id", replacing("authorization_id", with: "\t", in: base)),
            ("oversized authorization id", replacing("authorization_id", with: String(repeating: "a", count: 513), in: base)),
            ("malformed challenge", replacing("challenge", with: String(Self.hexA.dropLast()), in: base)),
            ("malformed client fingerprint", replacing("client_key_fingerprint", with: Self.hexB.uppercased(), in: base)),
            ("malformed binding", replacing("transport_binding", with: Self.hexA.uppercased(), in: base)),
            ("blank signature", replacing("client_signature", with: "", in: base)),
            ("noncanonical signature", replacing("client_signature", with: "TQ=", in: base)),
            ("oversized signature", replacing("client_signature", with: String(repeating: "A", count: 516), in: base)),
        ]

        for (label, sample) in invalidSamples {
            XCTAssertThrowsError(
                try JSONDecoder().decode(
                    RelayAllocationAuthorizationPayload.self,
                    from: JSONSerialization.data(withJSONObject: sample)
                ),
                label
            )
        }
    }

    func testProtocolEnvelopeDecodeRejectsMalformedRequiredFields() throws {
        let codec = ProtocolCodec()
        let cases: [(name: String, json: String)] = [
            (
                "missing version",
                #"{"type":"runtime.health","request_id":"missing-version","timestamp":"2026-07-07T00:00:00Z","payload":{}}"#
            ),
            (
                "non-integer version",
                #"{"version":"1","type":"runtime.health","request_id":"non-integer-version","timestamp":"2026-07-07T00:00:00Z","payload":{}}"#
            ),
            (
                "missing request_id",
                #"{"version":1,"type":"runtime.health","timestamp":"2026-07-07T00:00:00Z","payload":{}}"#
            ),
            (
                "non-string request_id",
                #"{"version":1,"type":"runtime.health","request_id":7,"timestamp":"2026-07-07T00:00:00Z","payload":{}}"#
            ),
            (
                "missing timestamp",
                #"{"version":1,"type":"runtime.health","request_id":"missing-timestamp","payload":{}}"#
            ),
            (
                "non-string timestamp",
                #"{"version":1,"type":"runtime.health","request_id":"non-string-timestamp","timestamp":123,"payload":{}}"#
            ),
            (
                "malformed timestamp",
                #"{"version":1,"type":"runtime.health","request_id":"malformed-timestamp","timestamp":"not-a-date","payload":{}}"#
            ),
            (
                "missing type",
                #"{"version":1,"request_id":"missing-type","timestamp":"2026-07-07T00:00:00Z","payload":{}}"#
            ),
            (
                "non-string type",
                #"{"version":1,"type":42,"request_id":"non-string-type","timestamp":"2026-07-07T00:00:00Z","payload":{}}"#
            ),
            (
                "missing payload",
                #"{"version":1,"type":"runtime.health","request_id":"missing-payload","timestamp":"2026-07-07T00:00:00Z"}"#
            ),
            (
                "non-object payload",
                #"{"version":1,"type":"runtime.health","request_id":"non-object-payload","timestamp":"2026-07-07T00:00:00Z","payload":[]}"#
            ),
        ]

        for testCase in cases {
            XCTAssertThrowsError(
                try codec.decodeEnvelope(Data(testCase.json.utf8)),
                testCase.name
            )
        }
    }

    func testProtocolEnvelopeDecodeRejectsUnknownTopLevelFields() throws {
        let codec = ProtocolCodec()
        let json = """
        {
          "version": 1,
          "type": "runtime.health",
          "request_id": "unknown-top-level-envelope-field",
          "timestamp": "2026-07-07T00:00:00Z",
          "payload": {},
          "backend_url": "http://127.0.0.1:11434",
          "route_token": "client-supplied-route-token"
        }
        """

        XCTAssertThrowsError(try codec.decodeEnvelope(Data(json.utf8)))
    }

    func testProtocolEnvelopeDecodeRejectsDuplicateObjectKeysAtEveryDepth() throws {
        let codec = ProtocolCodec()
        let samples: [(label: String, key: String, json: String)] = [
            (
                "top-level type",
                "type",
                #"{"version":1,"type":"runtime.health","type":"research.brief.create","request_id":"duplicate-type","timestamp":"2026-07-14T00:00:00Z","payload":{}}"#
            ),
            (
                "research authority grants",
                "trusted_source_grant_ids",
                #"{"version":1,"type":"research.brief.create","request_id":"duplicate-grants","timestamp":"2026-07-14T00:00:00Z","payload":{"notebook_id":"research_notebook_0123456789abcdef0123456789abcdef","session_id":"session-1","topic":"Topic","model":"model-1","trusted_source_grant_ids":["trusted_source_0123456789abcdef0123456789abcdef"],"trusted_source_grant_ids":["trusted_source_abcdef0123456789abcdef0123456789"]}}"#
            ),
            (
                "nested authority field",
                "grant_id",
                #"{"version":1,"type":"research.brief.create","request_id":"duplicate-authority","timestamp":"2026-07-14T00:00:00Z","payload":{"authority":{"grant_id":"first","grant_\u0069d":"second"}}}"#
            ),
        ]

        for sample in samples {
            XCTAssertThrowsError(try codec.decodeEnvelope(Data(sample.json.utf8)), sample.label) { error in
                XCTAssertEqual(error as? ProtocolCodecError, .duplicateJSONObjectKey(sample.key))
            }
        }
    }

    func testProtocolEnvelopeDecodeAcceptsNormalResearchEnvelope() throws {
        let codec = ProtocolCodec()
        let json = #"{"version":1,"type":"research.brief.create","request_id":"research-create","timestamp":"2026-07-14T00:00:00Z","payload":{"notebook_id":"research_notebook_0123456789abcdef0123456789abcdef","session_id":"session-1","topic":"Topic","model":"model-1","trusted_source_grant_ids":["trusted_source_0123456789abcdef0123456789abcdef"]}}"#

        let envelope = try codec.decodeEnvelope(Data(json.utf8))

        XCTAssertEqual(envelope.type, MessageType.researchBriefCreate)
        XCTAssertEqual(envelope.payload["session_id"], .string("session-1"))
        XCTAssertEqual(
            envelope.payload["trusted_source_grant_ids"],
            .array([.string("trusted_source_0123456789abcdef0123456789abcdef")])
        )
    }

    func testModelInfoCodablePreservesProviderAndEmbeddingMetadata() throws {
        let modifiedAt = Date(timeIntervalSince1970: 1_720_000_000)
        let model = ModelInfo(
            id: "ollama:nomic-embed-text",
            name: "Nomic Embed Text",
            backend: "ollama",
            provider: "ollama",
            modelKind: "embedding",
            capabilities: ["embedding", "retrieval"],
            providerModelID: "nomic-embed-text",
            qualifiedID: "ollama:nomic-embed-text",
            sizeBytes: 274_000_000,
            modifiedAt: modifiedAt,
            installed: true,
            running: false,
            source: "local",
            remoteModel: "nomic-embed-text",
            contextWindowTokens: 8_192
        )

        let encoded = try JSONEncoder().encode(model)
        let decodedObject = try XCTUnwrap(JSONSerialization.jsonObject(with: encoded) as? [String: Any])

        XCTAssertEqual(decodedObject["backend"] as? String, "ollama")
        XCTAssertEqual(decodedObject["provider"] as? String, "ollama")
        XCTAssertEqual(decodedObject["model_kind"] as? String, "embedding")
        XCTAssertEqual(decodedObject["capabilities"] as? [String], ["embedding", "retrieval"])
        XCTAssertEqual(decodedObject["provider_model_id"] as? String, "nomic-embed-text")
        XCTAssertEqual(decodedObject["qualified_id"] as? String, "ollama:nomic-embed-text")
        XCTAssertEqual(decodedObject["context_window_tokens"] as? Int, 8_192)

        let decoded = try JSONDecoder().decode(ModelInfo.self, from: encoded)

        XCTAssertEqual(decoded, model)
    }

    func testModelInfoCodableDefaultsMissingCapabilitiesToEmptyList() throws {
        let legacyPayload = Data("""
        {
          "id": "legacy-chat",
          "name": "Legacy Chat",
          "installed": true,
          "running": false,
          "source": "local"
        }
        """.utf8)

        let decoded = try JSONDecoder().decode(ModelInfo.self, from: legacyPayload)

        XCTAssertEqual(decoded.id, "legacy-chat")
        XCTAssertEqual(decoded.capabilities, [])
        XCTAssertNil(decoded.modelKind)
        XCTAssertNil(decoded.providerModelID)
        XCTAssertNil(decoded.qualifiedID)
    }

    func testRelaySessionNonceGenerationIsCanonicalAndUnique() {
        let first = RelaySessionNonce.generate()
        let second = RelaySessionNonce.generate()

        XCTAssertTrue(RelaySessionNonce.isCanonical(first))
        XCTAssertTrue(RelaySessionNonce.isCanonical(second))
        XCTAssertNotEqual(first, second)
        XCTAssertFalse(RelaySessionNonce.isCanonical(first.uppercased()))
        XCTAssertFalse(RelaySessionNonce.isCanonical("\(first)0"))
        XCTAssertFalse(RelaySessionNonce.isCanonical(String(repeating: "١", count: 32)))
    }

    func testRelayEphemeralKeysMatchP256ScalarVectorsAndValidateOnCurve() throws {
        let vector = try relayVector()

        XCTAssertEqual(vector.clientKey.publicKeyHex, Self.clientPublicKey)
        XCTAssertEqual(vector.runtimeKey.publicKeyHex, Self.runtimePublicKey)
        XCTAssertTrue(RelaySessionCrypto.isCanonicalEphemeralKey(Self.clientPublicKey))
        XCTAssertFalse(RelaySessionCrypto.isCanonicalEphemeralKey(Self.clientPublicKey.uppercased()))
        XCTAssertFalse(RelaySessionCrypto.isCanonicalEphemeralKey("04" + String(repeating: "0", count: 128)))
    }

    func testRelaySessionCryptoMatchesBindingHkdfAndConfirmationVectors() throws {
        let vector = try relayVector()

        XCTAssertEqual(vector.clientKeys.bindingID, "44ed84bb0519061c52e320518660a2d0fbc0a29fdc3b7a62a14e151a2c4e6219")
        XCTAssertEqual(vector.clientKeys.bindingDigest.hexString, vector.clientKeys.bindingID)
        XCTAssertEqual(vector.clientKeys.confirmationKey.hexString, "be7a46fc32b5055bd5721007150a707ce7a4ea5d1928e699b1dd0daf15a7191c")
        XCTAssertEqual(vector.clientKeys.clientTrafficSecret.hexString, "44fd2d03a7cd5532d3d15f80b5a244ae196ddc493c7ac2723dc27cedbeed7124")
        XCTAssertEqual(vector.clientKeys.runtimeTrafficSecret.hexString, "cef511632ab211cb0aba20f8a9100fb3d95504246af5abc5c9fbb151e991bd4f")
        XCTAssertEqual(vector.runtimeKeys.bindingID, vector.clientKeys.bindingID)
        XCTAssertEqual(vector.runtimeKeys.confirmationKey, vector.clientKeys.confirmationKey)
        XCTAssertEqual(vector.runtimeKeys.clientTrafficSecret, vector.clientKeys.clientTrafficSecret)
        XCTAssertEqual(vector.runtimeKeys.runtimeTrafficSecret, vector.clientKeys.runtimeTrafficSecret)
        XCTAssertEqual(RelayKeyConfirmation.proof(role: .client, sessionKeys: vector.clientKeys), "dc22099339654d46ec3a06d23183311c7d9e503200bdbeeb969179b02a5e498a")
        XCTAssertEqual(RelayKeyConfirmation.proof(role: .runtime, sessionKeys: vector.clientKeys), "b5742c284b726d42f692e2cbc2bbb0ceb7c7f2183d2c24aebedb48fd102d346c")
    }

    func testRelaySessionCryptoBindsRouteNonceIntoBindingAndTrafficKeys() throws {
        let vector = try relayVector()
        let changedNonceKeys = try RelaySessionCrypto.deriveKeys(
            localRole: .client,
            localEphemeralKey: vector.clientKey,
            relayID: "relay-vector",
            routeNonce: "different-relay-nonce",
            relaySecret: "relay-secret-vector",
            clientSessionNonce: "00112233445566778899aabbccddeeff",
            runtimeSessionNonce: "ffeeddccbbaa99887766554433221100",
            clientEphemeralKey: vector.clientKey.publicKeyHex,
            runtimeEphemeralKey: vector.runtimeKey.publicKeyHex
        )
        var sender = RelayFrameCipher(sessionKeys: vector.clientKeys)
        var wrongNonceReceiver = RelayFrameCipher(sessionKeys: changedNonceKeys)
        let ciphertext = try sender.encryptRuntimeBody(Data("route-bound".utf8))

        XCTAssertNotEqual(vector.clientKeys.bindingID, changedNonceKeys.bindingID)
        XCTAssertThrowsError(try wrongNonceReceiver.decryptRuntimeBody(ciphertext))
    }

    func testRelayKeyConfirmationRequiresExactRoleBindingProofAndLineFeed() throws {
        let keys = try relayVector().clientKeys
        let line = RelayKeyConfirmation.controlLine(role: .client, sessionKeys: keys)

        XCTAssertEqual(
            line,
            "AETHERLINK_RELAY confirm client binding=\(keys.bindingID) " +
                "proof=dc22099339654d46ec3a06d23183311c7d9e503200bdbeeb969179b02a5e498a\n"
        )
        XCTAssertTrue(RelayKeyConfirmation.validateControlLine(line, expectedRole: .client, sessionKeys: keys))
        XCTAssertFalse(RelayKeyConfirmation.validateControlLine(line, expectedRole: .runtime, sessionKeys: keys))
        XCTAssertFalse(RelayKeyConfirmation.validateControlLine(String(line.dropLast()), expectedRole: .client, sessionKeys: keys))
        XCTAssertFalse(RelayKeyConfirmation.validateControlLine(line.replacingOccurrences(of: "proof=d", with: "proof=0"), expectedRole: .client, sessionKeys: keys))
    }

    func testRelayFrameCipherMatchesDirectionalFrameZeroVectors() throws {
        let keys = try relayVector().clientKeys
        var clientCipher = RelayFrameCipher(sessionKeys: keys)
        var runtimeCipher = RelayFrameCipher(sessionKeys: keys)

        XCTAssertEqual(try clientCipher.encryptClientBody(Data("frame-zero".utf8)).hexString, "c0a6cad42dc9c28451e990b566a3dbbf845435e12640ae5e89d7")
        XCTAssertEqual(try runtimeCipher.encryptRuntimeBody(Data("frame-zero".utf8)).hexString, "48e80b6d79586ee44b567e7b7d00fa246e656c181fe492ebb6a8")
    }

    func testRelayFrameCipherRoundTripsAndRejectsWrongDirection() throws {
        let keys = try relayVector().clientKeys
        let body = envelopeBody(type: "models.list", requestID: "request-1")
        var sender = RelayFrameCipher(sessionKeys: keys)
        var receiver = RelayFrameCipher(sessionKeys: keys)
        let encrypted = try sender.encryptClientBody(body)

        XCTAssertEqual(try receiver.decryptClientBody(encrypted), body)
        var wrongDirection = RelayFrameCipher(sessionKeys: keys)
        XCTAssertThrowsError(try wrongDirection.decryptRuntimeBody(encrypted))
    }

    func testRelayFrameCipherDoesNotAdvanceReceiveCounterAfterAuthenticationFailure() throws {
        let keys = try relayVector().clientKeys
        let body = Data("authenticated".utf8)
        var sender = RelayFrameCipher(sessionKeys: keys)
        var receiver = RelayFrameCipher(sessionKeys: keys)
        let encrypted = try sender.encryptClientBody(body)
        var tampered = encrypted
        tampered[tampered.startIndex] ^= 0x01

        XCTAssertThrowsError(try receiver.decryptClientBody(tampered))
        XCTAssertEqual(try receiver.decryptClientBody(encrypted), body)
        XCTAssertThrowsError(try receiver.decryptClientBody(encrypted))
    }

    func testRelayFrameCipherRotatesAtEpochBoundaryUsingFixedVectors() throws {
        let keys = try relayVector().clientKeys
        var edgeCipher = RelayFrameCipher(sessionKeys: keys, frameIndex: 65_535)
        var nextEpochCipher = RelayFrameCipher(sessionKeys: keys, frameIndex: 65_536)

        XCTAssertEqual(try edgeCipher.encryptClientBody(Data("epoch-edge".utf8)).hexString, "20086e2cf3df35fc8483ee4826ef529dbd223dc39d6df2e1ee92")
        XCTAssertEqual(try nextEpochCipher.encryptClientBody(Data("epoch-edge".utf8)).hexString, "a0cd1619ae98e59b6a7213b109015754312b1bbd1002c962842f")
    }

    func testRelayFrameCipherRejectsCounterAtInt64MaxBeforeCryptography() throws {
        let keys = try relayVector().clientKeys
        var cipher = RelayFrameCipher(sessionKeys: keys, frameIndex: Int64.max)

        XCTAssertThrowsError(try cipher.encryptClientBody(Data("x".utf8))) { error in
            XCTAssertEqual(error as? RelayFrameCipherError, .counterExhausted)
        }
        XCTAssertThrowsError(try cipher.decryptRuntimeBody(Data(repeating: 0, count: 16))) { error in
            XCTAssertEqual(error as? RelayFrameCipherError, .counterExhausted)
        }
    }

    private static let hexA = String(repeating: "0123456789abcdef", count: 4)
    private static let hexB = String(repeating: "fedcba9876543210", count: 4)
    private static let clientPublicKey = "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c2964fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
    private static let runtimePublicKey = "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1"

    private func relayVector() throws -> (
        clientKey: RelaySessionEphemeralKey,
        runtimeKey: RelaySessionEphemeralKey,
        clientKeys: RelaySessionKeys,
        runtimeKeys: RelaySessionKeys
    ) {
        var clientScalar = Data(repeating: 0, count: 32)
        clientScalar[31] = 1
        var runtimeScalar = Data(repeating: 0, count: 32)
        runtimeScalar[31] = 2
        let clientKey = try RelaySessionEphemeralKey(privateKeyRawRepresentation: clientScalar)
        let runtimeKey = try RelaySessionEphemeralKey(privateKeyRawRepresentation: runtimeScalar)
        let arguments = (
            relayID: "relay-vector",
            routeNonce: "relay-nonce-vector",
            relaySecret: "relay-secret-vector",
            clientSessionNonce: "00112233445566778899aabbccddeeff",
            runtimeSessionNonce: "ffeeddccbbaa99887766554433221100"
        )
        let clientKeys = try RelaySessionCrypto.deriveKeys(
            localRole: .client,
            localEphemeralKey: clientKey,
            relayID: arguments.relayID,
            routeNonce: arguments.routeNonce,
            relaySecret: arguments.relaySecret,
            clientSessionNonce: arguments.clientSessionNonce,
            runtimeSessionNonce: arguments.runtimeSessionNonce,
            clientEphemeralKey: clientKey.publicKeyHex,
            runtimeEphemeralKey: runtimeKey.publicKeyHex
        )
        let runtimeKeys = try RelaySessionCrypto.deriveKeys(
            localRole: .runtime,
            localEphemeralKey: runtimeKey,
            relayID: arguments.relayID,
            routeNonce: arguments.routeNonce,
            relaySecret: arguments.relaySecret,
            clientSessionNonce: arguments.clientSessionNonce,
            runtimeSessionNonce: arguments.runtimeSessionNonce,
            clientEphemeralKey: clientKey.publicKeyHex,
            runtimeEphemeralKey: runtimeKey.publicKeyHex
        )
        return (clientKey, runtimeKey, clientKeys, runtimeKeys)
    }

    private func relayAllocationChallengePayload() throws -> RelayAllocationChallengePayload {
        try RelayAllocationChallengePayload(
            proofScheme: relayAllocationProofScheme,
            protocolVersion: relayAllocationProtocolVersion,
            operation: "claim",
            authorizationID: "authorization-1",
            currentRelayID: "rt2-\(Self.hexA)",
            nextRelayID: "rt2-\(Self.hexB)",
            routeTokenHash: Self.hexB,
            runtimeKeyFingerprint: Self.hexA,
            clientKeyFingerprint: Self.hexB,
            currentTicketGeneration: 1,
            nextTicketGeneration: 2,
            currentRelayExpiresAtEpochMillis: 1,
            currentRelayNonce: "current-nonce",
            nextRelayExpiresAtEpochMillis: Int64.max,
            nextRelayNonce: "next-nonce",
            challenge: Self.hexA,
            challengeExpiresAtEpochMillis: 1,
            transportBinding: Self.hexB
        )
    }

    private func jsonObject(_ data: Data) throws -> [String: Any] {
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw CocoaError(.coderReadCorrupt)
        }
        return object
    }

    private func replacing(
        _ field: String,
        with value: Any,
        in object: [String: Any]
    ) -> [String: Any] {
        var result = object
        result[field] = value
        return result
    }

    private func removing(_ field: String, from object: [String: Any]) -> [String: Any] {
        var result = object
        result.removeValue(forKey: field)
        return result
    }

    private func envelopeBody(type: String, requestID: String) -> Data {
        Data("{\"version\":1,\"type\":\"\(type)\",\"request_id\":\"\(requestID)\",\"timestamp\":\"2026-07-07T00:00:00Z\",\"payload\":{}}".utf8)
    }
}

private extension Data {
    var hexString: String {
        map { String(format: "%02x", $0) }.joined()
    }
}
