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
}

