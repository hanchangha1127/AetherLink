import Foundation
import XCTest
@testable import P2PNATContracts

final class P2PNATSharedVectorTests: XCTestCase {
    func testAllSevenObjectsMatchSharedCanonicalVectors() throws {
        let fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: fixtureURL()))

        let candidateInput = fixture.objects.candidateBatch.input
        let batch = try CandidateBatch(
            sessionId: candidateInput.sessionId,
            generation: candidateInput.generation,
            sequence: candidateInput.sequence,
            expires: candidateInput.expiresAtMillis,
            role: role(candidateInput.senderRole),
            candidates: try candidateInput.candidates.map { item in
                try P2PNATCandidate(
                    kind: candidateKind(item.kind),
                    family: candidateFamily(item.family),
                    port: item.port,
                    priority: item.priority,
                    foundation: try Data(strictHex: item.foundationHex),
                    address: try Data(strictHex: item.addressHex)
                )
            }
        )
        try assertVector(fixture.objects.candidateBatch, actual: batch.canonicalBytes(), decode: CandidateBatch.init(canonicalBytes:), encode: { $0.canonicalBytes() })

        let sealedInput = fixture.objects.sealedRouteRecord.input
        let sealed = try SealedRouteRecord(
            sessionId: sealedInput.sessionId,
            pairDigest: sealedInput.pairBindingDigest,
            role: role(sealedInput.senderRole),
            generation: sealedInput.generation,
            sequence: sealedInput.sequence,
            expires: sealedInput.expiresAtMillis,
            nonce: sealedInput.antiReplayNonce,
            ephemeralKey: try Data(strictHex: sealedInput.ephemeralPublicKeyHex),
            sealNonce: try Data(strictHex: sealedInput.sealNonceHex),
            ciphertext: try Data(strictHex: sealedInput.ciphertextHex)
        )
        try assertVector(fixture.objects.sealedRouteRecord, actual: sealed.canonicalBytes(), decode: SealedRouteRecord.init(canonicalBytes:), encode: { $0.canonicalBytes() })

        let relayInput = fixture.objects.relayCapability.input
        let relay = try RelayCapability(
            sessionId: relayInput.sessionId,
            pairDigest: relayInput.pairBindingDigest,
            clientFingerprint: relayInput.clientFingerprint,
            runtimeFingerprint: relayInput.runtimeFingerprint,
            relayServiceDigest: relayInput.relayServiceDigest,
            expires: relayInput.expiresAtMillis,
            quotaBytes: relayInput.quotaBytes,
            nonce: relayInput.capabilityNonce
        )
        try assertVector(fixture.objects.relayCapability, actual: relay.canonicalBytes(), decode: RelayCapability.init(canonicalBytes:), encode: { $0.canonicalBytes() })

        let transcriptInput = fixture.objects.identitySessionTranscript.input
        let transcript = try IdentitySessionTranscript(
            sessionId: transcriptInput.sessionId,
            pairDigest: transcriptInput.pairBindingDigest,
            clientFingerprint: transcriptInput.clientFingerprint,
            runtimeFingerprint: transcriptInput.runtimeFingerprint,
            clientKey: try Data(strictHex: transcriptInput.clientEphemeralKeyHex),
            runtimeKey: try Data(strictHex: transcriptInput.runtimeEphemeralKeyHex),
            generation: transcriptInput.generation,
            pathReceiptDigest: transcriptInput.pathReceiptDigest,
            transport: transport(transcriptInput.transportContext),
            fallback: fallback(transcriptInput.fallbackReason),
            protocolFloor: transcriptInput.protocolFloor
        )
        try assertVector(fixture.objects.identitySessionTranscript, actual: transcript.canonicalBytes(), decode: IdentitySessionTranscript.init(canonicalBytes:), encode: { $0.canonicalBytes() })

        let relayTranscriptVector = fixture.objects.relayIdentitySessionTranscript
        let relayTranscript = try makeTranscript(relayTranscriptVector.input)
        let relayTranscriptBytes = relayTranscript.canonicalBytes()
        XCTAssertEqual(relayTranscriptBytes.count, relayTranscriptVector.expectedCanonicalByteCount)
        try assertVector(relayTranscriptVector, actual: relayTranscriptBytes, decode: IdentitySessionTranscript.init(canonicalBytes:), encode: { $0.canonicalBytes() })

        let maximumTranscriptVector = fixture.objects.maximumIdentitySessionTranscript
        let maximumTranscript = try makeTranscript(maximumTranscriptVector.input)
        let maximumTranscriptBytes = maximumTranscript.canonicalBytes()
        XCTAssertEqual(maximumTranscriptBytes.count, maximumTranscriptVector.expectedCanonicalByteCount)
        try assertVector(maximumTranscriptVector, actual: maximumTranscriptBytes, decode: IdentitySessionTranscript.init(canonicalBytes:), encode: { $0.canonicalBytes() })

        let receiptInput = fixture.objects.pathValidationReceipt.input
        let receipt = try PathValidationReceipt(
            sessionId: receiptInput.sessionId,
            generation: receiptInput.generation,
            candidatePairDigest: receiptInput.candidatePairDigest,
            transport: transport(receiptInput.transportContext),
            clientObserved: receiptInput.clientObservedPathDigest,
            runtimeObserved: receiptInput.runtimeObservedPathDigest,
            validatedAt: receiptInput.validatedAtMillis,
            expires: receiptInput.expiresAtMillis
        )
        try assertVector(fixture.objects.pathValidationReceipt, actual: receipt.canonicalBytes(), decode: PathValidationReceipt.init(canonicalBytes:), encode: { $0.canonicalBytes() })

        try assertTranscriptChecks(transcript, checks: fixture.transcriptChecks.identitySessionTranscript)
        try assertTranscriptChecks(relayTranscript, checks: fixture.transcriptChecks.relayIdentitySessionTranscript)
        try assertTranscriptChecks(maximumTranscript, checks: fixture.transcriptChecks.maximumIdentitySessionTranscript)
    }

    func testSharedNegativeCanonicalVectorsAreRejectedByProductionDecoders() throws {
        for vector in try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: fixtureURL())).negativeCanonicalVectors {
            let encoded = try Data(strictHex: vector.canonicalHex)
            XCTAssertThrowsError(try decodeNegative(vector, encoded: encoded), "vector \(vector.id) must be rejected") { error in
                guard let actual = error as? P2PNATContractError else {
                    return XCTFail("vector \(vector.id) threw unexpected error type: \(error)")
                }
                XCTAssertEqual(actual, rejectionClass(vector.expectedRejectionClass), "vector \(vector.id)")
            }
        }
    }

    private func makeTranscript(_ input: IdentitySessionTranscriptInput) throws -> IdentitySessionTranscript {
        try IdentitySessionTranscript(
            sessionId: input.sessionId,
            pairDigest: input.pairBindingDigest,
            clientFingerprint: input.clientFingerprint,
            runtimeFingerprint: input.runtimeFingerprint,
            clientKey: Data(strictHex: input.clientEphemeralKeyHex),
            runtimeKey: Data(strictHex: input.runtimeEphemeralKeyHex),
            generation: input.generation,
            pathReceiptDigest: input.pathReceiptDigest,
            transport: transport(input.transportContext),
            fallback: fallback(input.fallbackReason),
            protocolFloor: input.protocolFloor
        )
    }

    private func assertTranscriptChecks(_ transcript: IdentitySessionTranscript, checks: TranscriptCheck) throws {
        XCTAssertEqual(transcript.digest, try Data(strictHex: checks.expectedSha256Hex))
        let confirmationKey = try Data(strictHex: checks.confirmationKeyHex)
        XCTAssertEqual(try transcript.keyConfirmation(key: confirmationKey, role: .client), try Data(strictHex: checks.expectedHmacSha256.client))
        XCTAssertEqual(try transcript.keyConfirmation(key: confirmationKey, role: .runtime), try Data(strictHex: checks.expectedHmacSha256.runtime))
    }

    private func decodeNegative(_ vector: NegativeCanonicalVector, encoded: Data) throws {
        switch vector.operation {
        case "decodeCandidateBatch": _ = try CandidateBatch(canonicalBytes: encoded)
        case "decodeSealedRouteRecord": _ = try SealedRouteRecord(canonicalBytes: encoded)
        case "decodeIdentitySessionTranscript": _ = try IdentitySessionTranscript(canonicalBytes: encoded)
        case "decodePathValidationReceipt": _ = try PathValidationReceipt(canonicalBytes: encoded)
        case "decodeFreshPathValidationReceipt":
            guard let now = vector.nowMillis else { throw FixtureError.missingNow }
            _ = try PathValidationReceipt(freshCanonicalBytes: encoded, now: now)
        default: throw FixtureError.unsupportedOperation
        }
    }

    private func rejectionClass(_ value: String) -> P2PNATContractError {
        switch value {
        case "invalidValue": return .invalidValue
        case "duplicateField": return .duplicateField
        case "invalidFieldOrder": return .invalidFieldOrder
        case "trailingBytes": return .trailingBytes
        case "limitExceeded": return .limitExceeded
        default: preconditionFailure("unknown rejection class")
        }
    }

    private func assertVector<Input, Decoded>(_ vector: Vector<Input>, actual: Data, decode: (Data) throws -> Decoded, encode: (Decoded) -> Data) throws {
        let expected = try Data(strictHex: vector.expectedCanonicalHex)
        XCTAssertEqual(actual, expected)
        XCTAssertEqual(encode(try decode(expected)), expected)
    }

    private func fixtureURL() throws -> URL {
        let relative = "shared/protocol/fixtures/production-p2p-nat-v1-vectors.json"
        let starts = [URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true), URL(fileURLWithPath: #filePath).deletingLastPathComponent()]
        for start in starts {
            var directory = start.standardizedFileURL
            while true {
                let candidate = directory.appendingPathComponent(relative)
                if FileManager.default.fileExists(atPath: candidate.path) { return candidate }
                let parent = directory.deletingLastPathComponent()
                if parent.path == directory.path { break }
                directory = parent
            }
        }
        throw FixtureError.notFound
    }

    private func role(_ value: String) -> P2PNATRole { P2PNATRole(rawValue: value)! }
    private func transport(_ value: String) -> P2PNATTransport { P2PNATTransport(rawValue: value)! }
    private func fallback(_ value: String) -> P2PNATFallback { P2PNATFallback(rawValue: value)! }
    private func candidateKind(_ value: String) -> CandidateKind {
        switch value { case "host": return .host; case "server_reflexive": return .srflx; case "peer_reflexive": return .prflx; case "relay": return .relay; default: preconditionFailure("unknown candidate kind") }
    }
    private func candidateFamily(_ value: String) -> CandidateFamily {
        switch value { case "ipv4": return .ipv4; case "ipv6": return .ipv6; default: preconditionFailure("unknown candidate family") }
    }
}

private enum FixtureError: Error { case notFound, invalidHex, missingNow, unsupportedOperation }

private struct Fixture: Decodable {
    let objects: Objects
    let transcriptChecks: TranscriptChecks
    let negativeCanonicalVectors: [NegativeCanonicalVector]
}

private struct Objects: Decodable {
    let candidateBatch: Vector<CandidateBatchInput>
    let sealedRouteRecord: Vector<SealedRouteRecordInput>
    let relayCapability: Vector<RelayCapabilityInput>
    let identitySessionTranscript: Vector<IdentitySessionTranscriptInput>
    let relayIdentitySessionTranscript: Vector<IdentitySessionTranscriptInput>
    let maximumIdentitySessionTranscript: Vector<IdentitySessionTranscriptInput>
    let pathValidationReceipt: Vector<PathValidationReceiptInput>
}

private struct Vector<Input: Decodable>: Decodable {
    let input: Input
    let expectedCanonicalByteCount: Int?
    let expectedCanonicalHex: String
}

private struct CandidateBatchInput: Decodable {
    let sessionId: String
    let generation: UInt64
    let sequence: UInt64
    let expiresAtMillis: UInt64
    let senderRole: String
    let candidates: [CandidateInput]
}

private struct CandidateInput: Decodable {
    let kind: String
    let family: String
    let port: UInt16
    let priority: UInt32
    let foundationHex: String
    let addressHex: String
}

private struct SealedRouteRecordInput: Decodable {
    let sessionId: String
    let pairBindingDigest: String
    let senderRole: String
    let generation: UInt64
    let sequence: UInt64
    let expiresAtMillis: UInt64
    let antiReplayNonce: String
    let ephemeralPublicKeyHex: String
    let sealNonceHex: String
    let ciphertextHex: String
}

private struct RelayCapabilityInput: Decodable {
    let sessionId: String
    let pairBindingDigest: String
    let clientFingerprint: String
    let runtimeFingerprint: String
    let relayServiceDigest: String
    let expiresAtMillis: UInt64
    let quotaBytes: UInt64
    let capabilityNonce: String
}

private struct IdentitySessionTranscriptInput: Decodable {
    let sessionId: String
    let pairBindingDigest: String
    let clientFingerprint: String
    let runtimeFingerprint: String
    let clientEphemeralKeyHex: String
    let runtimeEphemeralKeyHex: String
    let generation: UInt64
    let pathReceiptDigest: String
    let transportContext: String
    let fallbackReason: String
    let protocolFloor: UInt32
}

private struct PathValidationReceiptInput: Decodable {
    let sessionId: String
    let generation: UInt64
    let candidatePairDigest: String
    let transportContext: String
    let clientObservedPathDigest: String
    let runtimeObservedPathDigest: String
    let validatedAtMillis: UInt64
    let expiresAtMillis: UInt64
}

private struct TranscriptChecks: Decodable {
    let identitySessionTranscript: TranscriptCheck
    let relayIdentitySessionTranscript: TranscriptCheck
    let maximumIdentitySessionTranscript: TranscriptCheck
}

private struct TranscriptCheck: Decodable {
    let confirmationKeyHex: String
    let expectedSha256Hex: String
    let expectedHmacSha256: ExpectedHMAC
}

private struct ExpectedHMAC: Decodable {
    let client: String
    let runtime: String
}

private struct NegativeCanonicalVector: Decodable {
    let id: String
    let operation: String
    let nowMillis: UInt64?
    let canonicalHex: String
    let expectedRejectionClass: String
}

private extension Data {
    init(strictHex: String) throws {
        guard !strictHex.isEmpty, strictHex.count.isMultiple(of: 2), strictHex.allSatisfy({ $0.isNumber || ("a"..."f").contains(String($0)) }) else {
            throw FixtureError.invalidHex
        }
        self.init()
        reserveCapacity(strictHex.count / 2)
        var index = strictHex.startIndex
        while index < strictHex.endIndex {
            let next = strictHex.index(index, offsetBy: 2)
            guard let byte = UInt8(strictHex[index..<next], radix: 16) else { throw FixtureError.invalidHex }
            append(byte)
            index = next
        }
    }
}
