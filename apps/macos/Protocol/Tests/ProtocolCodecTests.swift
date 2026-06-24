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

    func testRelayFrameCipherMatchesSharedCiphertextVectors() throws {
        var clientCipher = RelayFrameCipher(relaySecret: "relay-secret-vector")
        var runtimeCipher = RelayFrameCipher(relaySecret: "relay-secret-vector")
        let clientBody = Data(#"{"type":"models.list","request_id":"vector-1","payload":{}}"#.utf8)
        let runtimeBody = Data(#"{"type":"runtime.health","request_id":"vector-2","payload":{}}"#.utf8)

        XCTAssertEqual(
            try clientCipher.encryptClientBody(clientBody).hexString,
            "445732376c183bb714bed5bb30570b16dd468e63392137eabc0259c1cc49f1c79c7babcf4ded6e05c91707bf1168823708c670b888a3319140063f1900d799afa5ad81bfa7df52c96f88c1"
        )
        XCTAssertEqual(
            try runtimeCipher.encryptRuntimeBody(runtimeBody).hexString,
            "ec6f782db28fe4e5bc8a0bfd9c8944051dbaeceea6bd1d3ec34b1ef9cf265f728a76ef7f24dcad7daaa516cb1f756d24d686df0b05806e436524baf6f4d27f6fb86e25b5eae90f83ccf30718cf68"
        )
    }
}

private extension Data {
    var hexString: String {
        map { String(format: "%02x", $0) }.joined()
    }
}
