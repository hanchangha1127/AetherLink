import BridgeProtocol
import XCTest

final class ProtocolCodecTests: XCTestCase {
    func testLengthPrefixedRoundTrip() throws {
        let codec = ProtocolCodec()
        let envelope = ProtocolEnvelope(type: MessageType.modelsList)

        let decoded = try codec.decodeFrame(try codec.encodeFrame(envelope))

        XCTAssertEqual(decoded.type, MessageType.modelsList)
        XCTAssertEqual(decoded.requestID, envelope.requestID)
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

    func testRelayFrameCipherRoundTripUsesCiphertextBody() throws {
        let codec = ProtocolCodec()
        let envelope = ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "health-1",
            payload: ["relay": .bool(true)]
        )
        let plaintextBody = try codec.encodeEnvelopeBody(envelope)
        var clientCipher = RelayFrameCipher(relaySecret: "test relay secret")
        var runtimeCipher = RelayFrameCipher(relaySecret: "test relay secret")

        let encryptedBody = try clientCipher.encryptClientBody(plaintextBody)
        XCTAssertNotEqual(encryptedBody, plaintextBody)

        let decryptedBody = try runtimeCipher.decryptClientBody(encryptedBody)
        let decoded = try codec.decodeEnvelope(decryptedBody)

        XCTAssertEqual(decoded.type, envelope.type)
        XCTAssertEqual(decoded.requestID, envelope.requestID)
        XCTAssertEqual(decoded.payload, envelope.payload)

        let runtimeResponseBody = try codec.encodeEnvelopeBody(ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "health-response-1",
            payload: ["ok": .bool(true)]
        ))
        let encryptedResponseBody = try runtimeCipher.encryptRuntimeBody(runtimeResponseBody)
        let decryptedResponseBody = try clientCipher.decryptRuntimeBody(encryptedResponseBody)

        XCTAssertEqual(decryptedResponseBody, runtimeResponseBody)
    }

    func testRelayFrameCipherRejectsWrongDirectionCounter() throws {
        let body = Data("{}".utf8)
        var clientCipher = RelayFrameCipher(relaySecret: "test relay secret")
        var runtimeCipher = RelayFrameCipher(relaySecret: "test relay secret")

        let encryptedBody = try clientCipher.encryptClientBody(body)

        XCTAssertThrowsError(try runtimeCipher.decryptRuntimeBody(encryptedBody))
    }

    func testRelayFrameCipherBindsRouteNonceIntoKey() throws {
        let body = envelopeBody(type: "models.list", requestID: "request-1")
        var clientCipher = RelayFrameCipher(relaySecret: "test relay secret", routeNonce: "relay-nonce-1")
        var runtimeCipher = RelayFrameCipher(relaySecret: "test relay secret", routeNonce: "relay-nonce-1")
        var wrongNonceRuntimeCipher = RelayFrameCipher(relaySecret: "test relay secret", routeNonce: "relay-nonce-2")

        let encryptedBody = try clientCipher.encryptClientBody(body)

        XCTAssertEqual(try runtimeCipher.decryptClientBody(encryptedBody), body)
        XCTAssertThrowsError(try wrongNonceRuntimeCipher.decryptClientBody(encryptedBody))
    }

    func testRelayFrameCipherMatchesSharedCiphertextVectors() throws {
        var clientCipher = RelayFrameCipher(relaySecret: "relay-secret-vector")
        var runtimeCipher = RelayFrameCipher(relaySecret: "relay-secret-vector")
        let clientBody = envelopeBody(type: "models.list", requestID: "vector-1")
        let runtimeBody = envelopeBody(type: "runtime.health", requestID: "vector-2")

        XCTAssertEqual(
            try clientCipher.encryptClientBody(clientBody).hexString,
            "4457302b6e0e70e258f180ee79190c41c14adf2d39607afcbc1f5f8ad354dddada75b39f5ef97814d51175e757669a651fda7fa386b53e9a1957608bec1ee575f365fee212e8ccde9e5a23e7cf47de8158f69db5fb2abe3cd20cfed775ef7f1464a2657fdc0a920e2fe563addbd472c93730fb106d9d48b51b4e"
        )
        XCTAssertEqual(
            try runtimeCipher.encryptRuntimeBody(runtimeBody).hexString,
            "ec6f7a31b099afb0f0da44a2c4c25d1943b7abb5e8bb00729b0001f9903b5f60925dee392ac4fd6ebeb307d719073662d89e8d1c198f754d732bb2afa58dc0278b69ce81c6d3e87f48caf26707488d0f3b980bd0a8ab21809e13dec4ab8867a0eeee4166d732d39bb932b3ed437e8908e61fbb33d83a59089f217505da"
        )
    }

    func testRelayFrameCipherMatchesNonceBoundSharedCiphertextVectors() throws {
        var clientCipher = RelayFrameCipher(relaySecret: "relay-secret-vector", routeNonce: "relay-nonce-vector")
        var runtimeCipher = RelayFrameCipher(relaySecret: "relay-secret-vector", routeNonce: "relay-nonce-vector")
        let clientBody = envelopeBody(type: "models.list", requestID: "vector-1")
        let runtimeBody = envelopeBody(type: "runtime.health", requestID: "vector-2")

        XCTAssertEqual(
            try clientCipher.encryptClientBody(clientBody).hexString,
            "74f168f9702f3ad65c2315b5dfdcc27e5b570d3fa6e71e471766b7cf8990f55750b50b36a967f9797d4b0074adc986356f329444776df3365208f9de7d25aa1387c574d3c7beb9e4e339ef3f974686d67dfc2c19d3abf398af4c4867b2ccfe44b54f80647e18a4e64f9b15c76989a56f23d99d30b227fc9ea2a2"
        )
        XCTAssertEqual(
            try runtimeCipher.encryptRuntimeBody(runtimeBody).hexString,
            "aae3d6418242e599b7b0e00107da8af0461fee8c8ccb32d80efbf7e592fef9832005892f4ea46f0d2e6615adfa278c68dc8df3a7236817784d9dfbe22ab6da43ae564e34c2d41df80a866ebbc7f60e3258f50af91235842f92a56137c6e48d83be96821c54f8c37e9c801c29419047e1296e5b48ea12b32e56426f4abf"
        )
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
