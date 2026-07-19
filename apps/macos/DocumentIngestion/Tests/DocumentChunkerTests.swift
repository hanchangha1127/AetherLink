import XCTest
@testable import DocumentIngestion

final class DocumentChunkerTests: XCTestCase {
    func testShortExtractedDocumentReturnsSingleSourceLabeledChunk() throws {
        let document = ExtractedDocument(
            fileName: "brief.md",
            mimeType: "text/markdown",
            text: "AetherLink keeps document ingestion runtime-mediated."
        )

        let chunks = try DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 120,
            overlapCharacters: 10,
            minChunkCharacters: 20
        )).chunks(from: document)

        XCTAssertEqual(chunks, [
            DocumentChunk(
                documentFileName: "brief.md",
                documentMimeType: "text/markdown",
                index: 0,
                startCharacterOffset: 0,
                endCharacterOffset: document.text.count,
                text: document.text
            )
        ])
    }

    func testLongDocumentPrefersSentenceAndWordBoundaries() throws {
        let text = [
            "First paragraph explains runtime mediated files.",
            "Second paragraph keeps chunks readable for retrieval planning.",
            "Third paragraph stays available for the next chunk."
        ].joined(separator: " ")
        let document = ExtractedDocument(fileName: "notes.txt", mimeType: "text/plain", text: text)

        let chunks = try DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 70,
            overlapCharacters: 0,
            minChunkCharacters: 30
        )).chunks(from: document)

        XCTAssertEqual(chunks.count, 3)
        XCTAssertEqual(chunks.map(\.index), [0, 1, 2])
        XCTAssertTrue(chunks.allSatisfy { $0.text.count <= 70 })
        XCTAssertTrue(chunks[0].text.hasSuffix("."))
        XCTAssertFalse(chunks[0].text.contains("Second"))
        XCTAssertFalse(chunks[1].text.hasSuffix(" "))
        XCTAssertFalse(chunks[1].text.hasPrefix(" "))
        XCTAssertEqual(chunks[0].text, substring(text, start: chunks[0].startCharacterOffset, end: chunks[0].endCharacterOffset))
        XCTAssertEqual(chunks[1].text, substring(text, start: chunks[1].startCharacterOffset, end: chunks[1].endCharacterOffset))
        XCTAssertEqual(chunks[2].text, substring(text, start: chunks[2].startCharacterOffset, end: chunks[2].endCharacterOffset))
    }

    func testAppliesBoundedOverlapBetweenAdjacentChunks() throws {
        let text = [
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
            "mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega"
        ].joined(separator: " ")
        let document = ExtractedDocument(fileName: "greek.txt", mimeType: "text/plain", text: text)

        let chunks = try DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 55,
            overlapCharacters: 12,
            minChunkCharacters: 25
        )).chunks(from: document)

        XCTAssertGreaterThan(chunks.count, 1)
        for pair in zip(chunks, chunks.dropFirst()) {
            XCTAssertLessThan(pair.0.startCharacterOffset, pair.0.endCharacterOffset)
            XCTAssertLessThan(pair.1.startCharacterOffset, pair.1.endCharacterOffset)
            XCTAssertLessThan(pair.1.startCharacterOffset, pair.0.endCharacterOffset)
            XCTAssertLessThanOrEqual(pair.0.text.count, 55)
            XCTAssertLessThanOrEqual(pair.1.text.count, 55)
        }
    }

    func testKeepsMultilingualTextAndReturnsNoChunksForWhitespaceOnlyDocuments() throws {
        let document = ExtractedDocument(
            fileName: "한국어.txt",
            mimeType: "text/plain",
            text: "AetherLink 문서 청킹은 런타임 안에서만 수행됩니다. 다음 청크도 한국어 텍스트를 보존합니다."
        )

        let chunks = try DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 34,
            overlapCharacters: 4,
            minChunkCharacters: 12
        )).chunks(from: document)

        XCTAssertGreaterThan(chunks.count, 1)
        XCTAssertTrue(chunks.map(\.text).joined(separator: " ").contains("한국어 텍스트"))
        XCTAssertEqual(
            try DocumentChunker().chunks(from: ExtractedDocument(fileName: "empty.txt", mimeType: "text/plain", text: " \n\t ")),
            []
        )
    }

    func testAppliesStoreOwnedPolicyCeilingsBeforeChunkPlanning() throws {
        let document = ExtractedDocument(
            fileName: "policy-ceiling.txt",
            mimeType: "text/plain",
            text: String(repeating: "Runtime-local chunk policy ceilings keep planning bounded. ", count: 4)
        )
        let boundaryChunks = try DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: documentChunkingPolicyMaxCharactersCeiling,
            overlapCharacters: documentChunkingPolicyOverlapCharactersCeiling,
            minChunkCharacters: documentChunkingPolicyMinChunkCharactersCeiling
        )).chunks(from: document)

        XCTAssertEqual(boundaryChunks.count, 1)
        XCTAssertEqual(boundaryChunks.single?.index, 0)

        let oversizedPolicies: [(DocumentChunkingPolicy, DocumentChunkingError)] = [
            (
                DocumentChunkingPolicy(
                    maxCharacters: documentChunkingPolicyMaxCharactersCeiling + 1,
                    overlapCharacters: 0,
                    minChunkCharacters: 1
                ),
                .invalidPolicy("maxCharacters must be less than or equal to \(documentChunkingPolicyMaxCharactersCeiling)")
            ),
            (
                DocumentChunkingPolicy(
                    maxCharacters: Int.max,
                    overlapCharacters: 0,
                    minChunkCharacters: 1
                ),
                .invalidPolicy("maxCharacters must be less than or equal to \(documentChunkingPolicyMaxCharactersCeiling)")
            ),
            (
                DocumentChunkingPolicy(
                    maxCharacters: documentChunkingPolicyMaxCharactersCeiling,
                    overlapCharacters: documentChunkingPolicyOverlapCharactersCeiling + 1,
                    minChunkCharacters: 1
                ),
                .invalidPolicy("overlapCharacters must be less than or equal to \(documentChunkingPolicyOverlapCharactersCeiling)")
            ),
            (
                DocumentChunkingPolicy(
                    maxCharacters: documentChunkingPolicyMaxCharactersCeiling,
                    overlapCharacters: 0,
                    minChunkCharacters: documentChunkingPolicyMinChunkCharactersCeiling + 1
                ),
                .invalidPolicy("minChunkCharacters must be less than or equal to \(documentChunkingPolicyMinChunkCharactersCeiling)")
            )
        ]

        for (policy, expectedError) in oversizedPolicies {
            XCTAssertThrowsError(try DocumentChunker(policy: policy).chunks(from: document)) { error in
                XCTAssertEqual(error as? DocumentChunkingError, expectedError)
            }
        }
    }

    func testRejectsInvalidChunkingPolicies() {
        let document = ExtractedDocument(fileName: "policy.txt", mimeType: "text/plain", text: "policy")
        let invalidPolicies: [(DocumentChunkingPolicy, DocumentChunkingError)] = [
            (
                DocumentChunkingPolicy(maxCharacters: 0, overlapCharacters: 0, minChunkCharacters: 1),
                .invalidPolicy("maxCharacters must be greater than zero")
            ),
            (
                DocumentChunkingPolicy(maxCharacters: 10, overlapCharacters: -1, minChunkCharacters: 1),
                .invalidPolicy("overlapCharacters must not be negative")
            ),
            (
                DocumentChunkingPolicy(maxCharacters: 10, overlapCharacters: 10, minChunkCharacters: 1),
                .invalidPolicy("overlapCharacters must be less than maxCharacters")
            ),
            (
                DocumentChunkingPolicy(maxCharacters: 10, overlapCharacters: 0, minChunkCharacters: 0),
                .invalidPolicy("minChunkCharacters must be greater than zero")
            ),
            (
                DocumentChunkingPolicy(maxCharacters: 10, overlapCharacters: 0, minChunkCharacters: 11),
                .invalidPolicy("minChunkCharacters must be less than or equal to maxCharacters")
            )
        ]

        for (policy, expectedError) in invalidPolicies {
            XCTAssertThrowsError(try DocumentChunker(policy: policy).chunks(from: document)) { error in
                XCTAssertEqual(error as? DocumentChunkingError, expectedError)
            }
        }
    }

    func testChunkerEnforcesExactUTF8ByteCeilingBeforeCharacterArrayAllocation() throws {
        let combiningMarkBytes = "\u{0301}".utf8.count
        let base = "é"
        let remainingBytes = documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling
            - base.utf8.count
        let exactText = base + String(
            repeating: "\u{0301}",
            count: remainingBytes / combiningMarkBytes
        )
        XCTAssertEqual(exactText.count, 1)
        XCTAssertEqual(
            exactText.utf8.count,
            documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling
        )
        let document = ExtractedDocument(
            fileName: "utf8-ceiling.txt",
            mimeType: "text/plain",
            text: exactText
        )

        let chunks = try DocumentChunker().chunks(from: document)
        XCTAssertEqual(chunks.single?.text, exactText)

        let oversizedDocument = ExtractedDocument(
            fileName: document.fileName,
            mimeType: document.mimeType,
            text: exactText + "x"
        )
        XCTAssertThrowsError(try DocumentChunker().chunks(from: oversizedDocument)) { error in
            XCTAssertEqual(
                error as? DocumentIngestionError,
                .resourceLimitExceeded(
                    resource: "extracted text UTF-8 bytes",
                    limit: documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling,
                    actual: documentIngestionResourcePolicyMaxExtractedTextUTF8BytesCeiling + 1
                )
            )
        }
    }

    private func substring(_ text: String, start: Int, end: Int) -> String {
        let startIndex = text.index(text.startIndex, offsetBy: start)
        let endIndex = text.index(text.startIndex, offsetBy: end)
        return String(text[startIndex..<endIndex])
    }
}

private extension Array {
    var single: Element? {
        count == 1 ? self[0] : nil
    }
}
