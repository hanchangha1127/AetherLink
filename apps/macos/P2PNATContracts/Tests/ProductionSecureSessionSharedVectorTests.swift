import Foundation
import XCTest
@testable import P2PNATContracts

final class ProductionSecureSessionSharedVectorTests: XCTestCase {
    func testAllSixRouteAuthorizationsMatchSharedCanonicalVectors() throws {
        let fixture = try loadFixture()
        XCTAssertEqual(fixture.schema, "aetherlink-production-secure-session-route-binding-v1-vectors")
        XCTAssertEqual(fixture.version, 1)
        XCTAssertEqual(fixture.magic, "ALS1")
        XCTAssertEqual(fixture.suite, ProductionSecureSessionContract.suite)
        XCTAssertEqual(fixture.routes.count, 6)

        for vector in fixture.routes {
            let authorization = try makeRoute(vector)
            let encoded = try ProductionSecureSessionCodec.encode(authorization)
            XCTAssertEqual(encoded.count, vector.expectedCanonicalByteCount, vector.id)
            XCTAssertEqual(encoded.hex, vector.expectedCanonicalHex, vector.id)
            XCTAssertEqual(
                try ProductionSecureSessionCodec.digest(authorization).hex,
                vector.expectedSha256Hex,
                vector.id
            )

            let decoded = try ProductionSecureSessionCodec.decodeRouteAuthorization(encoded)
            XCTAssertEqual(decoded, authorization, vector.id)
            XCTAssertEqual(try ProductionSecureSessionCodec.encode(decoded), encoded, vector.id)
        }
    }

    func testAllSixTranscriptsMatchSharedCanonicalVectorsAndRouteBindings() throws {
        let fixture = try loadFixture()
        XCTAssertEqual(fixture.transcripts.count, 6)
        let routesByKind = try Dictionary(
            uniqueKeysWithValues: fixture.routes.map { vector in
                let route = try makeRoute(vector)
                return (route.kind, route)
            }
        )

        for vector in fixture.transcripts {
            let transcript = try makeTranscript(vector.input)
            let encoded = ProductionSecureSessionCodec.encode(transcript)
            XCTAssertEqual(encoded.count, vector.expectedCanonicalByteCount, vector.id)
            XCTAssertEqual(encoded.hex, vector.expectedCanonicalHex, vector.id)
            XCTAssertEqual(
                ProductionSecureSessionCodec.digest(transcript).hex,
                vector.expectedSha256Hex,
                vector.id
            )

            let decoded = try ProductionSecureSessionCodec.decodeTranscript(encoded)
            XCTAssertEqual(decoded, transcript, vector.id)
            XCTAssertEqual(ProductionSecureSessionCodec.encode(decoded), encoded, vector.id)

            let route = try XCTUnwrap(routesByKind[transcript.routeKind], vector.id)
            XCTAssertTrue(
                ProductionSecureSessionCodec.matches(
                    transcript: transcript,
                    routeAuthorization: route
                ),
                vector.id
            )
            XCTAssertTrue(route.matches(transcript), vector.id)
        }
    }

    func testRouteBindingRejectsEveryMismatchAndLocalDirectIgnoresGeneration() throws {
        let fixture = try loadFixture()
        let directRoute = try makeRoute(try routeVector("p2p-direct", in: fixture))
        let direct = try makeTranscript(
            try transcriptVector("p2p-direct-transcript", in: fixture).input
        )
        XCTAssertTrue(direct.matches(directRoute))

        let wrongKind: ProductionRouteAuthorizationKind = direct.routeKind == .localDirect
            ? .p2pDirect
            : .localDirect
        XCTAssertFalse(try replacing(direct, routeKind: wrongKind).matches(directRoute))
        XCTAssertFalse(
            try replacing(direct, routeAuthDigest: flippedHex(direct.routeAuthDigest))
                .matches(directRoute)
        )
        XCTAssertFalse(
            try replacing(direct, pairBindingDigest: flippedHex(direct.pairBindingDigest))
                .matches(directRoute)
        )
        XCTAssertFalse(try replacing(direct, pairEpoch: direct.pairEpoch + 1).matches(directRoute))
        XCTAssertFalse(try replacing(direct, generation: direct.generation + 1).matches(directRoute))

        let localRoute = try makeRoute(try routeVector("local-direct", in: fixture))
        let local = try makeTranscript(
            try transcriptVector("local-direct-transcript", in: fixture).input
        )
        XCTAssertTrue(local.matches(localRoute))
        XCTAssertTrue(
            try replacing(local, generation: local.generation + 1).matches(localRoute),
            "local_direct has no generation in its authorization context"
        )
    }

    func testMalformedTLVAndInvalidTranscriptValuesFailClosed() throws {
        let fixture = try loadFixture()
        let route = try makeRoute(try routeVector("p2p-direct", in: fixture))
        let canonicalRoute = try ProductionSecureSessionCodec.encode(route)
        let tagOffsets = try tlvTagOffsets(canonicalRoute)
        XCTAssertEqual(tagOffsets.count, 8)

        var duplicate = canonicalRoute
        duplicate[tagOffsets[1]] = duplicate[tagOffsets[0]]
        assertContractError(.duplicateField) {
            _ = try ProductionSecureSessionCodec.decodeRouteAuthorization(duplicate)
        }

        var reordered = canonicalRoute
        let firstTag = reordered[tagOffsets[0]]
        reordered[tagOffsets[0]] = reordered[tagOffsets[1]]
        reordered[tagOffsets[1]] = firstTag
        assertContractError(.invalidFieldOrder) {
            _ = try ProductionSecureSessionCodec.decodeRouteAuthorization(reordered)
        }

        var unknown = canonicalRoute
        unknown[tagOffsets[0]] = 0x7f
        assertContractError(.unknownField) {
            _ = try ProductionSecureSessionCodec.decodeRouteAuthorization(unknown)
        }

        var trailing = canonicalRoute
        trailing.append(0)
        assertContractError(.trailingBytes) {
            _ = try ProductionSecureSessionCodec.decodeRouteAuthorization(trailing)
        }

        assertContractError(.limitExceeded) {
            _ = try ProductionSecureSessionCodec.decodeRouteAuthorization(
                Data(repeating: 0, count: ProductionSecureSessionContract.maxRouteBytes + 1)
            )
        }
        assertContractError(.limitExceeded) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(
                Data(repeating: 0, count: ProductionSecureSessionContract.maxTranscriptBytes + 1)
            )
        }

        let valid = try makeTranscript(
            try transcriptVector("p2p-direct-transcript", in: fixture).input
        )
        let canonicalTranscript = ProductionSecureSessionCodec.encode(valid)
        let transcriptTagOffsets = try tlvTagOffsets(canonicalTranscript)
        XCTAssertEqual(transcriptTagOffsets.count, 21)

        var wrongMagic = canonicalTranscript
        wrongMagic[0] = UInt8(ascii: "X")
        assertContractError(.invalidHeader) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(wrongMagic)
        }
        var wrongObjectType = canonicalTranscript
        wrongObjectType[4] = 1
        assertContractError(.invalidObjectType) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(wrongObjectType)
        }
        var wrongVersion = canonicalTranscript
        wrongVersion[5] = 2
        assertContractError(.invalidVersion) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(wrongVersion)
        }
        var transcriptDuplicate = canonicalTranscript
        transcriptDuplicate[transcriptTagOffsets[1]] = 1
        assertContractError(.duplicateField) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(transcriptDuplicate)
        }
        var transcriptReordered = canonicalTranscript
        transcriptReordered[transcriptTagOffsets[0]] = 2
        transcriptReordered[transcriptTagOffsets[1]] = 1
        assertContractError(.invalidFieldOrder) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(transcriptReordered)
        }
        var transcriptUnknown = canonicalTranscript
        transcriptUnknown[transcriptTagOffsets[0]] = 0x7f
        assertContractError(.unknownField) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(transcriptUnknown)
        }
        var transcriptTrailing = canonicalTranscript
        transcriptTrailing.append(0)
        assertContractError(.trailingBytes) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(transcriptTrailing)
        }
        var malformedLength = canonicalTranscript
        for index in (transcriptTagOffsets[0] + 1)...(transcriptTagOffsets[0] + 4) {
            malformedLength[index] = 0x7f
        }
        assertContractError(.invalidLength) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(malformedLength)
        }

        assertContractError(.invalidValue) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(
                replacingField(
                    in: canonicalTranscript,
                    number: 6,
                    with: fieldValue(in: canonicalTranscript, number: 5)
                )
            )
        }
        assertContractError(.invalidValue) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(
                replacingField(
                    in: canonicalTranscript,
                    number: 10,
                    with: fieldValue(in: canonicalTranscript, number: 9)
                )
            )
        }
        var offCurveKey = Data(repeating: 0, count: 65)
        offCurveKey[0] = 0x04
        assertContractError(.invalidValue) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(
                replacingField(in: canonicalTranscript, number: 10, with: offCurveKey)
            )
        }
        assertContractError(.invalidValue) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(
                replacingField(
                    in: canonicalTranscript,
                    number: 12,
                    with: fieldValue(in: canonicalTranscript, number: 11)
                )
            )
        }
        var uppercaseNonce = try fieldValue(in: canonicalTranscript, number: 11)
        let lowercaseA = try XCTUnwrap(uppercaseNonce.firstIndex(of: UInt8(ascii: "a")))
        uppercaseNonce[lowercaseA] = UInt8(ascii: "A")
        assertContractError(.invalidValue) {
            _ = try ProductionSecureSessionCodec.decodeTranscript(
                replacingField(in: canonicalTranscript, number: 11, with: uppercaseNonce)
            )
        }

        XCTAssertThrowsError(
            try replacing(valid, runtimeIdentityFingerprint: valid.clientIdentityFingerprint)
        )
        XCTAssertThrowsError(
            try replacing(valid, runtimeEphemeralPublicKey: Data(repeating: 0, count: 65))
        )
        XCTAssertThrowsError(try replacing(valid, runtimeNonce: valid.clientNonce))
    }

    private func makeRoute(_ vector: RouteVector) throws -> ProductionRouteAuthorization {
        let input = vector.input
        guard input.suite == ProductionSecureSessionContract.suite,
              let kind = ProductionRouteAuthorizationKind(wireName: vector.kind) else {
            throw FixtureError.invalidFixture
        }
        switch kind {
        case .localDirect:
            return .localDirect(
                pairBindingDigest: input.pairBindingDigest,
                pairEpoch: input.pairEpoch,
                nominatedPathReceiptDigest: try required(
                    input.nominatedPathReceiptDigest
                )
            )
        case .p2pPublish:
            return .p2pPublish(
                pairBindingDigest: input.pairBindingDigest,
                pairEpoch: input.pairEpoch,
                generation: try required(input.generation),
                candidateBatchDigest: try required(input.candidateBatchDigest),
                publishCapabilityDigest: try required(input.publishCapabilityDigest)
            )
        case .p2pFetch:
            return .p2pFetch(
                pairBindingDigest: input.pairBindingDigest,
                pairEpoch: input.pairEpoch,
                generation: try required(input.generation),
                candidateBatchDigest: try required(input.candidateBatchDigest),
                fetchCapabilityDigest: try required(input.fetchCapabilityDigest)
            )
        case .p2pDirect:
            return .p2pDirect(
                pairBindingDigest: input.pairBindingDigest,
                pairEpoch: input.pairEpoch,
                generation: try required(input.generation),
                candidatePairDigest: try required(input.candidatePairDigest),
                pathValidationReceiptDigest: try required(input.pathValidationReceiptDigest),
                publishCapabilityDigest: try required(input.publishCapabilityDigest),
                fetchCapabilityDigest: try required(input.fetchCapabilityDigest)
            )
        case .turnRelay:
            return .turnRelay(
                pairBindingDigest: input.pairBindingDigest,
                pairEpoch: input.pairEpoch,
                generation: try required(input.generation),
                leaseDigest: try required(input.turnLeaseDigest),
                allocationDigest: try required(input.allocationDigest),
                pathValidationReceiptDigest: try required(input.pathValidationReceiptDigest)
            )
        case .sealedRelay:
            return .sealedRelay(
                pairBindingDigest: input.pairBindingDigest,
                pairEpoch: input.pairEpoch,
                generation: try required(input.generation),
                leaseDigest: try required(input.sealedRelayLeaseDigest),
                allocationDigest: try required(input.allocationDigest),
                pathValidationReceiptDigest: try required(input.pathValidationReceiptDigest)
            )
        }
    }

    private func makeTranscript(_ input: TranscriptInput) throws -> ProductionSecureSessionTranscript {
        guard input.suite == ProductionSecureSessionContract.suite,
              input.clientRole == "client",
              input.runtimeRole == "runtime",
              input.protocolVersion == 1,
              input.minimumProtocolVersion == 1,
              input.cryptographicProfile == ProductionSecureSessionContract.profile,
              let routeKind = ProductionRouteAuthorizationKind(wireName: input.routeKind) else {
            throw FixtureError.invalidFixture
        }
        return try ProductionSecureSessionTranscript(
            sessionId: input.sessionId,
            pairBindingDigest: input.pairBindingDigest,
            pairEpoch: input.pairEpoch,
            clientIdentityFingerprint: input.clientIdentityFingerprint,
            runtimeIdentityFingerprint: input.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: Data(strictHex: input.clientEphemeralPublicKeyHex),
            runtimeEphemeralPublicKey: Data(strictHex: input.runtimeEphemeralPublicKeyHex),
            clientNonce: input.clientNonce,
            runtimeNonce: input.runtimeNonce,
            generation: input.generation,
            serviceConfigVersion: input.serviceConfigVersion,
            keysetVersion: input.keysetVersion,
            revocationCounter: input.revocationCounter,
            routeKind: routeKind,
            routeAuthDigest: input.routeAuthorizationDigest
        )
    }

    private func replacing(
        _ value: ProductionSecureSessionTranscript,
        pairBindingDigest: String? = nil,
        pairEpoch: UInt64? = nil,
        runtimeIdentityFingerprint: String? = nil,
        runtimeEphemeralPublicKey: Data? = nil,
        runtimeNonce: String? = nil,
        generation: UInt64? = nil,
        routeKind: ProductionRouteAuthorizationKind? = nil,
        routeAuthDigest: String? = nil
    ) throws -> ProductionSecureSessionTranscript {
        try ProductionSecureSessionTranscript(
            sessionId: value.sessionId,
            pairBindingDigest: pairBindingDigest ?? value.pairBindingDigest,
            pairEpoch: pairEpoch ?? value.pairEpoch,
            clientIdentityFingerprint: value.clientIdentityFingerprint,
            runtimeIdentityFingerprint: runtimeIdentityFingerprint
                ?? value.runtimeIdentityFingerprint,
            clientEphemeralPublicKey: value.clientEphemeralPublicKey,
            runtimeEphemeralPublicKey: runtimeEphemeralPublicKey
                ?? value.runtimeEphemeralPublicKey,
            clientNonce: value.clientNonce,
            runtimeNonce: runtimeNonce ?? value.runtimeNonce,
            generation: generation ?? value.generation,
            serviceConfigVersion: value.serviceConfigVersion,
            keysetVersion: value.keysetVersion,
            revocationCounter: value.revocationCounter,
            routeKind: routeKind ?? value.routeKind,
            routeAuthDigest: routeAuthDigest ?? value.routeAuthDigest
        )
    }

    private func tlvTagOffsets(_ data: Data) throws -> [Int] {
        guard data.count >= 6 else { throw FixtureError.invalidFixture }
        var offsets: [Int] = []
        var offset = 6
        while offset < data.count {
            guard offset <= data.count - 5 else { throw FixtureError.invalidFixture }
            offsets.append(offset)
            let length = data[(offset + 1)..<(offset + 5)].reduce(0) {
                ($0 << 8) | Int($1)
            }
            offset += 5
            guard length <= data.count - offset else { throw FixtureError.invalidFixture }
            offset += length
        }
        guard offset == data.count else { throw FixtureError.invalidFixture }
        return offsets
    }

    private func fieldValue(in data: Data, number: Int) throws -> Data {
        let offsets = try tlvTagOffsets(data)
        guard number > 0, number <= offsets.count else {
            throw FixtureError.invalidFixture
        }
        let tagOffset = offsets[number - 1]
        let length = data[(tagOffset + 1)..<(tagOffset + 5)].reduce(0) {
            ($0 << 8) | Int($1)
        }
        let start = tagOffset + 5
        guard length <= data.count - start else { throw FixtureError.invalidFixture }
        return data.subdata(in: start..<(start + length))
    }

    private func replacingField(
        in data: Data,
        number: Int,
        with replacement: Data
    ) throws -> Data {
        let offsets = try tlvTagOffsets(data)
        guard number > 0, number <= offsets.count else {
            throw FixtureError.invalidFixture
        }
        let tagOffset = offsets[number - 1]
        let original = try fieldValue(in: data, number: number)
        guard original.count == replacement.count else {
            throw FixtureError.invalidFixture
        }
        var result = data
        result.replaceSubrange(
            (tagOffset + 5)..<(tagOffset + 5 + replacement.count),
            with: replacement
        )
        return result
    }

    private func routeVector(_ id: String, in fixture: Fixture) throws -> RouteVector {
        try required(fixture.routes.first(where: { $0.id == id }))
    }

    private func transcriptVector(_ id: String, in fixture: Fixture) throws -> TranscriptVector {
        try required(fixture.transcripts.first(where: { $0.id == id }))
    }

    private func required<T>(_ value: T?) throws -> T {
        guard let value else { throw FixtureError.invalidFixture }
        return value
    }

    private func flippedHex(_ value: String) -> String {
        let replacement = value.first == "0" ? "1" : "0"
        return replacement + value.dropFirst()
    }

    private func assertContractError(
        _ expected: P2PNATContractError,
        file: StaticString = #filePath,
        line: UInt = #line,
        _ body: () throws -> Void
    ) {
        XCTAssertThrowsError(try body(), file: file, line: line) { error in
            XCTAssertEqual(error as? P2PNATContractError, expected, file: file, line: line)
        }
    }

    private func loadFixture() throws -> Fixture {
        let relative = "shared/protocol/fixtures/production-secure-session-route-binding-v1-vectors.json"
        let starts = [
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true),
            URL(fileURLWithPath: #filePath).deletingLastPathComponent(),
        ]
        for start in starts {
            var directory = start.standardizedFileURL
            while true {
                let candidate = directory.appendingPathComponent(relative)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    return try JSONDecoder().decode(
                        Fixture.self,
                        from: Data(contentsOf: candidate)
                    )
                }
                let parent = directory.deletingLastPathComponent()
                if parent.path == directory.path { break }
                directory = parent
            }
        }
        throw FixtureError.notFound
    }
}

private enum FixtureError: Error {
    case notFound
    case invalidFixture
    case invalidHex
}

private struct Fixture: Decodable {
    let schema: String
    let version: Int
    let magic: String
    let suite: String
    let routes: [RouteVector]
    let transcripts: [TranscriptVector]
}

private struct RouteVector: Decodable {
    let id: String
    let kind: String
    let input: RouteInput
    let expectedCanonicalByteCount: Int
    let expectedCanonicalHex: String
    let expectedSha256Hex: String
}

private struct RouteInput: Decodable {
    let suite: String
    let pairBindingDigest: String
    let pairEpoch: UInt64
    let generation: UInt64?
    let nominatedPathReceiptDigest: String?
    let candidateBatchDigest: String?
    let publishCapabilityDigest: String?
    let fetchCapabilityDigest: String?
    let candidatePairDigest: String?
    let pathValidationReceiptDigest: String?
    let turnLeaseDigest: String?
    let sealedRelayLeaseDigest: String?
    let allocationDigest: String?
}

private struct TranscriptVector: Decodable {
    let id: String
    let input: TranscriptInput
    let expectedCanonicalByteCount: Int
    let expectedCanonicalHex: String
    let expectedSha256Hex: String
}

private struct TranscriptInput: Decodable {
    let suite: String
    let sessionId: String
    let pairBindingDigest: String
    let pairEpoch: UInt64
    let clientIdentityFingerprint: String
    let runtimeIdentityFingerprint: String
    let clientRole: String
    let runtimeRole: String
    let clientEphemeralPublicKeyHex: String
    let runtimeEphemeralPublicKeyHex: String
    let clientNonce: String
    let runtimeNonce: String
    let generation: UInt64
    let serviceConfigVersion: UInt64
    let keysetVersion: UInt64
    let revocationCounter: UInt64
    let protocolVersion: UInt32
    let minimumProtocolVersion: UInt32
    let cryptographicProfile: String
    let routeKind: String
    let routeAuthorizationDigest: String
}

private extension Data {
    init(strictHex: String) throws {
        guard !strictHex.isEmpty,
              strictHex.count.isMultiple(of: 2),
              strictHex.allSatisfy({ character in
                  character.isNumber || ("a"..."f").contains(String(character))
              }) else {
            throw FixtureError.invalidHex
        }
        self.init()
        reserveCapacity(strictHex.count / 2)
        var index = strictHex.startIndex
        while index < strictHex.endIndex {
            let next = strictHex.index(index, offsetBy: 2)
            guard let byte = UInt8(strictHex[index..<next], radix: 16) else {
                throw FixtureError.invalidHex
            }
            append(byte)
            index = next
        }
    }

    var hex: String {
        map { String(format: "%02x", $0) }.joined()
    }
}
