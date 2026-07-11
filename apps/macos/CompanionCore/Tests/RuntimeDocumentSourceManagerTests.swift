import DocumentIngestion
import Foundation
import OllamaBackend
import TrustedDevices
import XCTest
@testable import CompanionCore

final class RuntimeDocumentSourceManagerTests: XCTestCase {
    func testPrepareDoesNotApproveUntilMatchingDisclosureConfirmation() async throws {
        let fixture = try makeFixture(text: "private review canary")
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }

        let review = try await fixture.manager.prepareImport(from: fixture.fileURL)

        XCTAssertTrue(try fixture.store.documents().isEmpty)
        XCTAssertNil(try fixture.store.sourceApproval(documentID: review.sourceID))

        do {
            _ = try await fixture.manager.approve(
                reviewID: review.id,
                confirmationToken: "wrong-token",
                disclosureVersion: review.disclosureVersion
            )
            XCTFail("Expected an invalid confirmation error")
        } catch {
            XCTAssertEqual(error as? RuntimeDocumentSourceManagementError, .invalidConfirmation)
        }

        let source = try await fixture.manager.approve(
            reviewID: review.id,
            confirmationToken: review.confirmationToken,
            disclosureVersion: review.disclosureVersion
        )
        XCTAssertEqual(source.id, review.sourceID)
        XCTAssertEqual(source.sourceRevision, review.candidateRevision)
        XCTAssertEqual(try fixture.store.documents().map(\.id), [source.id])
        XCTAssertEqual(try fixture.store.sourceApproval(documentID: source.id)?.scope, .runtimeShared)

        do {
            _ = try await fixture.manager.approve(
                reviewID: review.id,
                confirmationToken: review.confirmationToken,
                disclosureVersion: review.disclosureVersion
            )
            XCTFail("Expected one-time review consumption")
        } catch {
            XCTAssertEqual(error as? RuntimeDocumentSourceManagementError, .reviewExpired)
        }
    }

    func testReplacementKeepsApprovedRevisionUntilExplicitApprovalThenRotatesSameSource() async throws {
        let fixture = try makeFixture(text: "alphaonlytoken")
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        let firstReview = try await fixture.manager.prepareImport(from: fixture.fileURL)
        let first = try await fixture.manager.approve(
            reviewID: firstReview.id,
            confirmationToken: firstReview.confirmationToken,
            disclosureVersion: firstReview.disclosureVersion
        )
        try "betaonlytoken".write(to: fixture.fileURL, atomically: true, encoding: .utf8)

        let replacement = try await fixture.manager.prepareImport(
            from: fixture.fileURL,
            replacingSourceID: first.id
        )

        XCTAssertTrue(replacement.replacingExistingSource)
        XCTAssertNotEqual(replacement.candidateRevision, first.sourceRevision)
        XCTAssertEqual(try fixture.store.sourceApproval(documentID: first.id)?.sourceRevision, first.sourceRevision)
        XCTAssertEqual(try fixture.store.query("alphaonlytoken").first?.document.id, first.id)
        XCTAssertTrue(try fixture.store.query("betaonlytoken").isEmpty)

        let updated = try await fixture.manager.approve(
            reviewID: replacement.id,
            confirmationToken: replacement.confirmationToken,
            disclosureVersion: replacement.disclosureVersion
        )
        XCTAssertEqual(updated.id, first.id)
        XCTAssertEqual(updated.sourceRevision, replacement.candidateRevision)
        XCTAssertEqual(try fixture.store.documents().count, 1)
        XCTAssertTrue(try fixture.store.query("alphaonlytoken").isEmpty)
        XCTAssertEqual(try fixture.store.query("betaonlytoken").first?.document.id, first.id)
    }

    func testStaleReplacementCannotOverwriteNewerApprovedRevision() async throws {
        let fixture = try makeFixture(text: "base revision")
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        let firstReview = try await fixture.manager.prepareImport(from: fixture.fileURL)
        let first = try await fixture.manager.approve(
            reviewID: firstReview.id,
            confirmationToken: firstReview.confirmationToken,
            disclosureVersion: firstReview.disclosureVersion
        )
        try "candidateonlytoken".write(to: fixture.fileURL, atomically: true, encoding: .utf8)
        let staleReview = try await fixture.manager.prepareImport(
            from: fixture.fileURL,
            replacingSourceID: first.id
        )

        let external = try DocumentIngestor().ingest(extractedDocument: ExtractedDocument(
            fileName: "external.txt",
            mimeType: "text/plain",
            text: "newerapprovedtoken"
        ))
        _ = try fixture.store.replaceDocument(result: external, documentID: first.id)

        do {
            _ = try await fixture.manager.approve(
                reviewID: staleReview.id,
                confirmationToken: staleReview.confirmationToken,
                disclosureVersion: staleReview.disclosureVersion
            )
            XCTFail("Expected source revision compare-and-swap failure")
        } catch {
            XCTAssertEqual(error as? RuntimeDocumentSourceManagementError, .sourceChanged)
        }
        XCTAssertEqual(try fixture.store.query("newerapprovedtoken").first?.document.id, first.id)
        XCTAssertTrue(try fixture.store.query("candidateonlytoken").isEmpty)
    }

    func testStaleRemovalCannotDeleteNewerApprovedRevision() async throws {
        let fixture = try makeFixture(text: "originalremovaltoken")
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        let review = try await fixture.manager.prepareImport(from: fixture.fileURL)
        let original = try await fixture.manager.approve(
            reviewID: review.id,
            confirmationToken: review.confirmationToken,
            disclosureVersion: review.disclosureVersion
        )
        let newerResult = try DocumentIngestor().ingest(extractedDocument: ExtractedDocument(
            fileName: "newer.txt",
            mimeType: "text/plain",
            text: "newerremovaltoken"
        ))
        let newer = try fixture.store.replaceDocument(result: newerResult, documentID: original.id)
        let newerRevision = try XCTUnwrap(
            fixture.store.sourceApproval(documentID: newer.id)?.sourceRevision
        )

        do {
            try await fixture.manager.removeSource(
                id: original.id,
                expectedRevision: original.sourceRevision
            )
            XCTFail("Expected stale removal compare-and-swap failure")
        } catch {
            XCTAssertEqual(error as? RuntimeDocumentSourceManagementError, .sourceChanged)
        }
        XCTAssertEqual(
            try fixture.store.sourceApproval(documentID: original.id)?.sourceRevision,
            newerRevision
        )
        XCTAssertEqual(try fixture.store.query("newerremovaltoken").first?.document.id, original.id)
    }

    func testSnapshotOpenRejectsFileSwappedToSymlinkAfterValidation() async throws {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("runtime-document-source-symlink-tests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directoryURL) }
        let sourceURL = directoryURL.appendingPathComponent("source.txt")
        let targetURL = directoryURL.appendingPathComponent("private-target.txt")
        try "safe-original-token".write(to: sourceURL, atomically: true, encoding: .utf8)
        try "private-symlink-target-token".write(to: targetURL, atomically: true, encoding: .utf8)
        let store = SQLiteRuntimeDocumentIndexStore(
            databaseURL: directoryURL.appendingPathComponent("runtime-document-index.sqlite")
        )
        let manager = RuntimeDocumentSourceManager(
            store: store,
            onBeforeSnapshotOpen: {
                try? FileManager.default.removeItem(at: sourceURL)
                try? FileManager.default.createSymbolicLink(at: sourceURL, withDestinationURL: targetURL)
            }
        )

        do {
            _ = try await manager.prepareImport(from: sourceURL)
            XCTFail("Expected no-follow snapshot open to reject the symlink swap")
        } catch {
            XCTAssertEqual(error as? RuntimeDocumentSourceManagementError, .sourceUnavailable)
        }
        XCTAssertTrue(try store.documents().isEmpty)
        XCTAssertTrue(try store.query("private-symlink-target-token").isEmpty)
    }

    func testExpiredReviewAndCancelledReviewCannotApprove() async throws {
        let clock = TestDocumentSourceClock(Date(timeIntervalSince1970: 1_000))
        let fixture = try makeFixture(text: "expiring review", now: { clock.now() })
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        let expired = try await fixture.manager.prepareImport(from: fixture.fileURL)
        clock.advance(by: runtimeDocumentSourceReviewLifetime + 1)

        do {
            _ = try await fixture.manager.approve(
                reviewID: expired.id,
                confirmationToken: expired.confirmationToken,
                disclosureVersion: expired.disclosureVersion
            )
            XCTFail("Expected expired review")
        } catch {
            XCTAssertEqual(error as? RuntimeDocumentSourceManagementError, .reviewExpired)
        }

        let cancelled = try await fixture.manager.prepareImport(from: fixture.fileURL)
        await fixture.manager.cancel(reviewID: cancelled.id)
        do {
            _ = try await fixture.manager.approve(
                reviewID: cancelled.id,
                confirmationToken: cancelled.confirmationToken,
                disclosureVersion: cancelled.disclosureVersion
            )
            XCTFail("Expected cancelled review")
        } catch {
            XCTAssertEqual(error as? RuntimeDocumentSourceManagementError, .reviewExpired)
        }
        XCTAssertTrue(try fixture.store.documents().isEmpty)
    }

    func testPreparingNewReviewInvalidatesPriorCandidate() async throws {
        let fixture = try makeFixture(text: "firstpendingtoken")
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        let first = try await fixture.manager.prepareImport(from: fixture.fileURL)
        try "secondpendingtoken".write(to: fixture.fileURL, atomically: true, encoding: .utf8)
        let second = try await fixture.manager.prepareImport(from: fixture.fileURL)

        do {
            _ = try await fixture.manager.approve(
                reviewID: first.id,
                confirmationToken: first.confirmationToken,
                disclosureVersion: first.disclosureVersion
            )
            XCTFail("Expected the superseded review to be invalid")
        } catch {
            XCTAssertEqual(error as? RuntimeDocumentSourceManagementError, .reviewExpired)
        }
        let source = try await fixture.manager.approve(
            reviewID: second.id,
            confirmationToken: second.confirmationToken,
            disclosureVersion: second.disclosureVersion
        )
        XCTAssertEqual(try fixture.store.query("secondpendingtoken").first?.document.id, source.id)
        XCTAssertTrue(try fixture.store.query("firstpendingtoken").isEmpty)
    }

    func testAuditExportIsBoundedContentFreeAndPathFree() async throws {
        let privateText = "audit-export-private-canary"
        let fixture = try makeFixture(text: privateText)
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        let review = try await fixture.manager.prepareImport(from: fixture.fileURL)
        let source = try await fixture.manager.approve(
            reviewID: review.id,
            confirmationToken: review.confirmationToken,
            disclosureVersion: review.disclosureVersion
        )
        _ = try fixture.store.queryApprovedDocuments(
            privateText,
            limit: 10,
            maxSnippetCharacters: 160,
            actorDeviceID: "trusted-test-device",
            timestamp: Date(timeIntervalSince1970: 2_000)
        )

        let data = try await fixture.manager.auditExportData()
        let json = try XCTUnwrap(String(data: data, encoding: .utf8))
        XCTAssertTrue(json.contains("\"retentionPolicy\" : \"app_data_lifetime\""))
        XCTAssertTrue(json.contains("\"maximumExportedEvents\" : 1000"))
        XCTAssertTrue(json.contains(source.id))
        XCTAssertTrue(json.contains("trusted-test-device"))
        XCTAssertFalse(json.contains(privateText))
        XCTAssertFalse(json.contains(fixture.directoryURL.path))
        XCTAssertFalse(json.contains(fixture.fileURL.path))
        XCTAssertFalse(json.contains("snippet"))
        XCTAssertFalse(json.contains("query"))
    }

    func testAuditExportUsesExactLatestThousandNewestFirst() async throws {
        let fixture = try makeFixture(text: "bounded audit export")
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        for index in 0..<1_002 {
            try fixture.store.recordSourceAudit(
                action: .queried,
                actorDeviceID: "audit-actor-\(index)",
                documentID: nil,
                sourceAnchorID: nil,
                resultCount: index,
                timestamp: Date(timeIntervalSince1970: TimeInterval(index))
            )
        }

        let data = try await fixture.manager.auditExportData()
        let envelope = try XCTUnwrap(
            JSONSerialization.jsonObject(with: data) as? [String: Any]
        )
        let events = try XCTUnwrap(envelope["events"] as? [[String: Any]])
        XCTAssertEqual(events.count, runtimeDocumentSourceAuditExportLimit)
        XCTAssertEqual(events.first?["actorDeviceID"] as? String, "audit-actor-1001")
        XCTAssertEqual(events.last?["actorDeviceID"] as? String, "audit-actor-2")
        XCTAssertEqual(envelope["maximumExportedEvents"] as? Int, 1_000)
    }

    func testRemoveRequiresCurrentRevisionAndLeavesAuditTombstone() async throws {
        let fixture = try makeFixture(text: "remove me")
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        let review = try await fixture.manager.prepareImport(from: fixture.fileURL)
        let source = try await fixture.manager.approve(
            reviewID: review.id,
            confirmationToken: review.confirmationToken,
            disclosureVersion: review.disclosureVersion
        )

        do {
            try await fixture.manager.removeSource(id: source.id, expectedRevision: "stale")
            XCTFail("Expected stale revision rejection")
        } catch {
            XCTAssertEqual(error as? RuntimeDocumentSourceManagementError, .sourceChanged)
        }
        XCTAssertNotNil(try fixture.store.sourceApproval(documentID: source.id))

        try await fixture.manager.removeSource(id: source.id, expectedRevision: source.sourceRevision)
        XCTAssertNil(try fixture.store.sourceApproval(documentID: source.id))
        XCTAssertTrue(try fixture.store.documents().isEmpty)
        let actions = try fixture.store.sourceAuditEvents(limit: 10).map(\.action)
        XCTAssertTrue(actions.contains(.revoked))
        XCTAssertTrue(actions.contains(.deleted))
    }

    func testHostManagementListsAndRevokesApprovedSourcesBeyondRemoteCatalogPage() async throws {
        let fixture = try makeFixture(text: "host management corpus")
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        let result = try DocumentIngestor().ingest(extractedDocument: ExtractedDocument(
            fileName: "managed-source.txt",
            mimeType: "text/plain",
            text: "approved source management content"
        ))
        for index in 0...runtimeDocumentIndexCatalogLimitCeiling {
            _ = try fixture.store.replaceDocument(
                result: result,
                documentID: String(format: "managed-%03d", index)
            )
        }

        let sources = try await fixture.manager.sources()
        XCTAssertEqual(sources.count, runtimeDocumentIndexCatalogLimitCeiling + 1)
        let sourceBeyondRemotePage = try XCTUnwrap(
            sources.first(where: { $0.id == "managed-100" })
        )

        try await fixture.manager.removeSource(
            id: sourceBeyondRemotePage.id,
            expectedRevision: sourceBeyondRemotePage.sourceRevision
        )
        XCTAssertNil(try fixture.store.sourceApproval(documentID: sourceBeyondRemotePage.id))
        let remainingSources = try await fixture.manager.sources()
        XCTAssertEqual(remainingSources.count, runtimeDocumentIndexCatalogLimitCeiling)
    }

    @MainActor
    func testCompanionAppModelPublishesOnlyReviewedSourcesFromInjectedRuntimeStore() async throws {
        let fixture = try makeFixture(text: "model-shared-store-canary")
        defer { try? FileManager.default.removeItem(at: fixture.directoryURL) }
        let defaultsName = "runtime-document-source-model-tests-\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: defaultsName))
        defaults.removePersistentDomain(forName: defaultsName)
        defer { defaults.removePersistentDomain(forName: defaultsName) }
        let model = CompanionAppModel(
            backend: RuntimeDocumentSourceTestBackend(),
            environment: [
                "AETHERLINK_RUNTIME_IDENTITY_FILE": fixture.directoryURL
                    .appendingPathComponent("runtime-identity.json").path
            ],
            userDefaults: defaults,
            trustedDeviceStore: TrustedDeviceStore(
                fileURL: fixture.directoryURL.appendingPathComponent("trusted-devices.json")
            ),
            runtimeChatEventStore: JSONLRuntimeChatEventStore(
                fileURL: fixture.directoryURL.appendingPathComponent("chat-events.jsonl")
            ),
            runtimeMemoryStore: JSONLRuntimeMemoryStore(
                fileURL: fixture.directoryURL.appendingPathComponent("memory-events.jsonl")
            ),
            runtimeDocumentIndexStore: fixture.store,
            runtimeRouteHostProvider: { "127.0.0.1" }
        )

        await model.prepareRuntimeDocumentSource(fileURL: fixture.fileURL)

        XCTAssertNotNil(model.pendingRuntimeDocumentReview)
        XCTAssertTrue(model.runtimeDocumentSources.isEmpty)
        XCTAssertTrue(try fixture.store.documents().isEmpty)

        await model.approveRuntimeDocumentSourceReview()

        let source = try XCTUnwrap(model.runtimeDocumentSources.first)
        XCTAssertNil(model.pendingRuntimeDocumentReview)
        XCTAssertNil(model.runtimeDocumentSourcesError)
        XCTAssertEqual(try fixture.store.documents().map(\.id), [source.id])
        let remoteCatalog = try fixture.store.readApprovedCatalog(
            limit: 10,
            actorDeviceID: "trusted-model-test",
            timestamp: Date(timeIntervalSince1970: 3_000)
        )
        XCTAssertEqual(remoteCatalog.documents.map(\.id), [source.id])

        await model.removeRuntimeDocumentSource(id: source.id, expectedRevision: source.sourceRevision)
        XCTAssertTrue(model.runtimeDocumentSources.isEmpty)
        XCTAssertTrue(try fixture.store.documents().isEmpty)
    }

    private func makeFixture(
        text: String,
        now: @escaping @Sendable () -> Date = { Date() }
    ) throws -> (
        directoryURL: URL,
        fileURL: URL,
        store: SQLiteRuntimeDocumentIndexStore,
        manager: RuntimeDocumentSourceManager
    ) {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("runtime-document-source-manager-tests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        let fileURL = directoryURL.appendingPathComponent("private-source.txt")
        try text.write(to: fileURL, atomically: true, encoding: .utf8)
        let store = SQLiteRuntimeDocumentIndexStore(
            databaseURL: directoryURL.appendingPathComponent("runtime-document-index.sqlite")
        )
        return (
            directoryURL,
            fileURL,
            store,
            RuntimeDocumentSourceManager(store: store, now: now)
        )
    }
}

private struct RuntimeDocumentSourceTestBackend: LlmBackend {
    let provider = ModelProvider.ollama

    func healthCheck() async -> BackendStatus { .available }
    func listModels() async throws -> [ModelInfo] { [] }
    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in continuation.finish() }
    }
    func cancel(generationID: String) -> GenerationCancellationResult {
        .notFound(generationID: generationID)
    }
}

private final class TestDocumentSourceClock: @unchecked Sendable {
    private let lock = NSLock()
    private var date: Date

    init(_ date: Date) {
        self.date = date
    }

    func now() -> Date {
        lock.withLock { date }
    }

    func advance(by interval: TimeInterval) {
        lock.withLock { date = date.addingTimeInterval(interval) }
    }
}
