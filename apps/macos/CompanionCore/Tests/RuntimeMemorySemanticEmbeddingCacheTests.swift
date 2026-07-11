import XCTest
@testable import CompanionCore

final class RuntimeMemorySemanticEmbeddingCacheTests: XCTestCase {
    func testPersistentCacheReopensAndKeepsOwnerIsolation() throws {
        let urls = try temporaryURLs()
        let store = JSONLRuntimeMemoryStore(
            fileURL: urls.events,
            semanticCacheDatabaseURL: urls.cache
        )
        _ = try store.upsert(
            ownerDeviceID: "device-a",
            id: "memory-1",
            content: "Relay recovery uses the latest QR.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 10)
        )
        _ = try store.upsert(
            ownerDeviceID: "device-b",
            id: "memory-1",
            content: "A different owner's memory.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 11)
        )
        let sourceA = try XCTUnwrap(store.listSemanticSearchSources(ownerDeviceID: "device-a", limit: 10).first)
        let sourceB = try XCTUnwrap(store.listSemanticSearchSources(ownerDeviceID: "device-b", limit: 10).first)
        let keyA = key(owner: "device-a", source: sourceA)
        let keyB = key(owner: "device-b", source: sourceB)
        try store.upsertMemorySemanticEmbeddings([
            RuntimeMemorySemanticEmbeddingRecord(key: keyA, embedding: [1, 0]),
            RuntimeMemorySemanticEmbeddingRecord(key: keyB, embedding: [0, 1])
        ], if: { true })

        let reopened = JSONLRuntimeMemoryStore(
            fileURL: urls.events,
            semanticCacheDatabaseURL: urls.cache
        )
        XCTAssertEqual(
            try reopened.cachedMemorySemanticEmbeddings(for: [keyA]).first?.embedding,
            [1, 0]
        )
        XCTAssertEqual(
            try reopened.cachedMemorySemanticEmbeddings(for: [keyB]).first?.embedding,
            [0, 1]
        )
        XCTAssertTrue(try reopened.cachedMemorySemanticEmbeddings(for: [
            RuntimeMemorySemanticEmbeddingKey(
                ownerDeviceID: "device-b",
                entryID: keyA.entryID,
                canonicalQualifiedEmbeddingModelID: keyA.canonicalQualifiedEmbeddingModelID,
                modelFingerprint: keyA.modelFingerprint,
                documentFingerprint: keyA.documentFingerprint,
                sourceRevision: keyA.sourceRevision
            )
        ]).isEmpty)
    }

    func testUpdateAndDeletePurgeDerivedVectorsBeforeMutation() throws {
        let urls = try temporaryURLs()
        let store = JSONLRuntimeMemoryStore(fileURL: urls.events, semanticCacheDatabaseURL: urls.cache)
        _ = try store.upsert(
            ownerDeviceID: "device-a",
            id: "memory-1",
            content: "Old private content",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 10)
        )
        let oldSource = try XCTUnwrap(store.listSemanticSearchSources(ownerDeviceID: "device-a", limit: 10).first)
        let oldKey = key(owner: "device-a", source: oldSource)
        try store.upsertMemorySemanticEmbeddings([
            RuntimeMemorySemanticEmbeddingRecord(key: oldKey, embedding: [1, 2])
        ], if: { true })

        _ = try store.upsert(
            ownerDeviceID: "device-a",
            id: "memory-1",
            content: "Replacement content",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 20)
        )
        XCTAssertTrue(try store.cachedMemorySemanticEmbeddings(for: [oldKey]).isEmpty)

        let updatedSource = try XCTUnwrap(store.listSemanticSearchSources(ownerDeviceID: "device-a", limit: 10).first)
        let updatedKey = key(owner: "device-a", source: updatedSource)
        try store.upsertMemorySemanticEmbeddings([
            RuntimeMemorySemanticEmbeddingRecord(key: updatedKey, embedding: [2, 1])
        ], if: { true })
        _ = try store.delete(
            ownerDeviceID: "device-a",
            id: "memory-1",
            timestamp: Date(timeIntervalSince1970: 30)
        )
        XCTAssertTrue(try store.cachedMemorySemanticEmbeddings(for: [updatedKey]).isEmpty)
    }

    func testStaleSourceRevisionAndCancelledCommitDoNotWrite() throws {
        let urls = try temporaryURLs()
        let store = JSONLRuntimeMemoryStore(fileURL: urls.events, semanticCacheDatabaseURL: urls.cache)
        _ = try store.upsert(
            ownerDeviceID: "device-a",
            id: "memory-1",
            content: "Original content",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 10)
        )
        let original = try XCTUnwrap(store.listSemanticSearchSources(ownerDeviceID: "device-a", limit: 10).first)
        let staleKey = key(owner: "device-a", source: original)
        _ = try store.upsert(
            ownerDeviceID: "device-a",
            id: "memory-1",
            content: "Changed content",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 20)
        )

        try store.upsertMemorySemanticEmbeddings([
            RuntimeMemorySemanticEmbeddingRecord(key: staleKey, embedding: [1, 0])
        ], if: { true })
        XCTAssertTrue(try store.cachedMemorySemanticEmbeddings(for: [staleKey]).isEmpty)

        let current = try XCTUnwrap(store.listSemanticSearchSources(ownerDeviceID: "device-a", limit: 10).first)
        let currentKey = key(owner: "device-a", source: current)
        let commitChecks = LockedTestCounter()
        try store.upsertMemorySemanticEmbeddings([
            RuntimeMemorySemanticEmbeddingRecord(key: currentKey, embedding: [0, 1])
        ], if: {
            commitChecks.increment() < 4
        })
        XCTAssertEqual(commitChecks.value, 4)
        XCTAssertTrue(try store.cachedMemorySemanticEmbeddings(for: [currentKey]).isEmpty)
    }

    func testCachePurgeFailurePreventsPrivacySensitiveMutation() throws {
        let urls = try temporaryURLs()
        try FileManager.default.createDirectory(at: urls.cache, withIntermediateDirectories: true)
        let store = JSONLRuntimeMemoryStore(fileURL: urls.events, semanticCacheDatabaseURL: urls.cache)

        XCTAssertThrowsError(try store.upsert(
            ownerDeviceID: "device-a",
            id: "memory-1",
            content: "Content that must not outlive a failed purge.",
            enabled: true,
            timestamp: Date(timeIntervalSince1970: 10)
        ))
        XCTAssertFalse(FileManager.default.fileExists(atPath: urls.events.path))
    }

    func testGeneratedReviewDraftsNeverBecomeSemanticSources() throws {
        let urls = try temporaryURLs()
        let store = JSONLRuntimeMemoryStore(fileURL: urls.events, semanticCacheDatabaseURL: urls.cache)
        _ = try store.cacheGeneratedMemorySummaryDraft(
            ownerDeviceID: "device-a",
            draft: RuntimeGeneratedMemorySummaryDraft(
                draftID: "draft-1",
                sessionID: "session-1",
                sourceMessageCount: 2,
                content: "This still requires review.",
                modelID: "ollama:test",
                generatedAt: Date(timeIntervalSince1970: 10)
            )
        )

        XCTAssertTrue(try store.listSemanticSearchSources(ownerDeviceID: "device-a", limit: 10).isEmpty)
    }

    func testOwnerModelRowLimitBoundsPersistentCache() throws {
        let urls = try temporaryURLs()
        let store = JSONLRuntimeMemoryStore(
            fileURL: urls.events,
            semanticCacheDatabaseURL: urls.cache,
            semanticEmbeddingRowLimitPerOwnerModel: 2
        )
        for index in 0..<3 {
            _ = try store.upsert(
                ownerDeviceID: "device-a",
                id: "memory-\(index)",
                content: "Memory \(index)",
                enabled: true,
                timestamp: Date(timeIntervalSince1970: TimeInterval(index + 1))
            )
        }
        let sources = try store.listSemanticSearchSources(ownerDeviceID: "device-a", limit: 10)
        let keys = sources.map { key(owner: "device-a", source: $0) }
        try store.upsertMemorySemanticEmbeddings(
            keys.enumerated().map { index, key in
                RuntimeMemorySemanticEmbeddingRecord(key: key, embedding: [Double(index + 1), 1])
            },
            if: { true }
        )

        XCTAssertEqual(try store.cachedMemorySemanticEmbeddings(for: keys).count, 2)
    }

    private func key(
        owner: String,
        source: RuntimeMemorySemanticSearchSource
    ) -> RuntimeMemorySemanticEmbeddingKey {
        let candidate = RuntimeSemanticMemorySearch.candidate(source: source)!
        return RuntimeMemorySemanticEmbeddingKey(
            ownerDeviceID: owner,
            entryID: source.entry.id,
            canonicalQualifiedEmbeddingModelID: "ollama:nomic-embed-text",
            modelFingerprint: String(repeating: "a", count: 64),
            documentFingerprint: candidate.documentFingerprint,
            sourceRevision: source.sourceRevision
        )
    }

    private func temporaryURLs() throws -> (events: URL, cache: URL) {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-memory-semantic-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        return (
            directory.appendingPathComponent("memory.jsonl"),
            directory.appendingPathComponent("memory-semantic.sqlite")
        )
    }
}

private final class LockedTestCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var count = 0

    var value: Int { lock.withLock { count } }

    func increment() -> Int {
        lock.withLock {
            count += 1
            return count
        }
    }
}
