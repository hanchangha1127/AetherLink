import DocumentIngestion
import Foundation
import XCTest
@testable import CompanionCore

final class RuntimeDocumentCitationGovernanceTests: XCTestCase {
    func testInMemoryReviewGrantAndRevocationAreDeviceScopedAndContentFree() throws {
        let store = RuntimeDocumentIndexStore()
        let bodyCanary = "PRIVATE_CITATION_BODY_MUST_NOT_ENTER_AUDIT"
        _ = store.replaceDocument(
            result: try ingestedDocument(text: "Trusted source review. \(bodyCanary)"),
            documentID: "citation-guide"
        )
        let anchorID = try XCTUnwrap(
            store.query("trusted source", limit: 1, maxSnippetCharacters: 80)
                .first?.sourceAnchorID
        )
        let approvalBefore = try XCTUnwrap(store.sourceApproval(documentID: "citation-guide"))
        let prepared = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 1_000)
        )

        XCTAssertEqual(prepared.citation.schemaVersion, 1)
        XCTAssertEqual(
            runtimeDocumentCanonicalCitationID(prepared.citation.citationID),
            prepared.citation.citationID
        )
        XCTAssertEqual(prepared.citation.sourceAnchorID, anchorID)
        XCTAssertEqual(prepared.review.disclosureVersion, runtimeTrustedSourceDisclosureVersion)
        XCTAssertEqual(prepared.review.usageScope, .chatContext)
        XCTAssertNil(prepared.trustedSource)
        XCTAssertThrowsError(
            try store.approveTrustedSourceReview(
                reviewID: prepared.review.reviewID,
                confirmationToken: prepared.review.confirmationToken,
                disclosureVersion: prepared.review.disclosureVersion,
                usageScope: .chatContext,
                actorDeviceID: "device-b",
                timestamp: Date(timeIntervalSince1970: 1_001)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewNotFound)
        }

        let grant = try store.approveTrustedSourceReview(
            reviewID: prepared.review.reviewID,
            confirmationToken: prepared.review.confirmationToken,
            disclosureVersion: prepared.review.disclosureVersion,
            usageScope: .chatContext,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 1_001)
        )
        XCTAssertEqual(grant.citationID, prepared.citation.citationID)
        XCTAssertEqual(grant.document.id, "citation-guide")
        XCTAssertEqual(try store.trustedSources(actorDeviceID: "device-a", limit: 10).map(\.grantID), [grant.grantID])
        XCTAssertTrue(try store.trustedSources(actorDeviceID: "device-b", limit: 10).isEmpty)
        XCTAssertEqual(store.sourceApproval(documentID: "citation-guide"), approvalBefore)
        XCTAssertThrowsError(
            try store.approveTrustedSourceReview(
                reviewID: prepared.review.reviewID,
                confirmationToken: prepared.review.confirmationToken,
                disclosureVersion: prepared.review.disclosureVersion,
                usageScope: .chatContext,
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 1_002)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewNotFound)
        }

        try store.revokeTrustedSource(
            grantID: grant.grantID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 1_003)
        )
        XCTAssertTrue(try store.trustedSources(actorDeviceID: "device-a", limit: 10).isEmpty)

        let audit = try JSONEncoder().encode(store.sourceAuditEvents(limit: 100))
        let auditText = String(decoding: audit, as: UTF8.self)
        XCTAssertFalse(auditText.contains(bodyCanary))
        XCTAssertFalse(auditText.contains(prepared.review.confirmationToken))
        XCTAssertTrue(auditText.contains(RuntimeDocumentSourceAuditAction.citationResolved.rawValue))
        XCTAssertTrue(auditText.contains(RuntimeDocumentSourceAuditAction.trustedSourceApproved.rawValue))
        XCTAssertTrue(auditText.contains(RuntimeDocumentSourceAuditAction.trustedSourceRevoked.rawValue))
    }

    func testReviewExpiryAndNewReviewInvalidateApprovalWithoutGrant() throws {
        let store = RuntimeDocumentIndexStore()
        _ = store.replaceDocument(
            result: try ingestedDocument(text: "Review expiry and replacement token behavior."),
            documentID: "review-expiry"
        )
        let anchorID = try XCTUnwrap(
            store.query("replacement token", limit: 1, maxSnippetCharacters: 80)
                .first?.sourceAnchorID
        )
        let first = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 2_000)
        )
        let second = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 2_001)
        )
        XCTAssertNotEqual(first.review.reviewID, second.review.reviewID)
        XCTAssertThrowsError(
            try approve(first.review, store: store, timestamp: Date(timeIntervalSince1970: 2_002))
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewNotFound)
        }
        XCTAssertThrowsError(
            try approve(
                second.review,
                store: store,
                timestamp: second.review.expiresAt.addingTimeInterval(0.001)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewExpired)
        }
        XCTAssertTrue(try store.trustedSources(actorDeviceID: "device-a", limit: 10).isEmpty)
    }

    func testSQLiteGrantPersistsAndReplacementMakesReviewAndGrantStale() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "First approved source revision for a durable citation."),
            documentID: "durable-citation"
        )
        let anchorID = try XCTUnwrap(
            store.query("durable citation", limit: 1, maxSnippetCharacters: 80)
                .first?.sourceAnchorID
        )
        let prepared = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 3_000)
        )
        let grant = try approve(
            prepared.review,
            store: store,
            timestamp: Date(timeIntervalSince1970: 3_001)
        )

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try reopened.trustedSources(actorDeviceID: "device-a", limit: 10).map(\.grantID),
            [grant.grantID]
        )
        let pending = try reopened.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 3_002)
        )
        try reopened.replaceDocument(
            result: ingestedDocument(text: "Changed approved source revision invalidates prior trust."),
            documentID: "durable-citation"
        )
        XCTAssertTrue(try reopened.trustedSources(actorDeviceID: "device-a", limit: 10).isEmpty)
        XCTAssertThrowsError(
            try approve(
                pending.review,
                store: reopened,
                timestamp: Date(timeIntervalSince1970: 3_003)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewStale)
        }
        let replayed = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertThrowsError(
            try approve(
                pending.review,
                store: replayed,
                timestamp: Date(timeIntervalSince1970: 3_004)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewNotFound)
        }
    }

    func testSQLiteExpiredReviewIsConsumedAcrossReopen() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "Expired durable source review must be consumed once."),
            documentID: "expired-review"
        )
        let anchorID = try XCTUnwrap(
            store.query("consumed once", limit: 1, maxSnippetCharacters: 80)
                .first?.sourceAnchorID
        )
        let pending = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 6_000)
        )
        XCTAssertThrowsError(
            try approve(
                pending.review,
                store: store,
                timestamp: pending.review.expiresAt.addingTimeInterval(1)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewExpired)
        }

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertThrowsError(
            try approve(
                pending.review,
                store: reopened,
                timestamp: pending.review.expiresAt.addingTimeInterval(2)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewNotFound)
        }
    }

    func testSQLiteSameRevisionReindexPreservesCitationReviewAndGrant() throws {
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: temporaryDatabaseURL())
        let document = try ingestedDocument(
            text: "An identical approved source revision preserves reviewed trust."
        )
        try store.replaceDocument(result: document, documentID: "same-revision")
        let anchorID = try XCTUnwrap(
            store.query("reviewed trust", limit: 1, maxSnippetCharacters: 80)
                .first?.sourceAnchorID
        )
        let prepared = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 3_100)
        )
        let grant = try approve(
            prepared.review,
            store: store,
            timestamp: Date(timeIntervalSince1970: 3_101)
        )
        let pending = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 3_102)
        )

        try store.replaceDocument(result: document, documentID: "same-revision")

        XCTAssertEqual(
            try store.trustedSources(actorDeviceID: "device-a", limit: 10).map(\.grantID),
            [grant.grantID]
        )
        XCTAssertEqual(
            try approve(
                pending.review,
                store: store,
                timestamp: Date(timeIntervalSince1970: 3_103)
            ).grantID,
            grant.grantID
        )
    }

    func testSQLiteDismissAndDeleteFailClosedAcrossReopen() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        try store.replaceDocument(
            result: ingestedDocument(text: "Dismissed reviews and deleted sources cannot grant trust."),
            documentID: "dismiss-delete"
        )
        let anchorID = try XCTUnwrap(
            store.query("deleted sources", limit: 1, maxSnippetCharacters: 80)
                .first?.sourceAnchorID
        )
        let dismissed = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 4_000)
        )
        try store.dismissTrustedSourceReview(
            reviewID: dismissed.review.reviewID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 4_001)
        )
        XCTAssertThrowsError(
            try approve(
                dismissed.review,
                store: store,
                timestamp: Date(timeIntervalSince1970: 4_002)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewNotFound)
        }

        let pending = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 4_003)
        )
        try store.deleteDocument(id: "dismiss-delete")
        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertThrowsError(
            try approve(
                pending.review,
                store: reopened,
                timestamp: Date(timeIntervalSince1970: 4_004)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .reviewStale)
        }
        XCTAssertThrowsError(
            try reopened.prepareTrustedSourceReview(
                sourceAnchorID: anchorID,
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 4_005)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .citationNotFound)
        }
    }

    func testSQLiteApprovalAndReplacementLinearizeWithoutLeavingStaleGrant() async throws {
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: temporaryDatabaseURL())
        try store.replaceDocument(
            result: ingestedDocument(text: "Concurrent trust approval starts from this revision."),
            documentID: "approval-race"
        )
        let anchorID = try XCTUnwrap(
            store.query("concurrent trust", limit: 1, maxSnippetCharacters: 80)
                .first?.sourceAnchorID
        )
        let pending = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 5_000)
        )
        let approvalReachedCommit = DispatchSemaphore(value: 0)
        let allowApprovalCommit = DispatchSemaphore(value: 0)
        let replacementFinished = DispatchSemaphore(value: 0)
        store.onBeforeTrustedSourceApprovalCommit = {
            approvalReachedCommit.signal()
            _ = allowApprovalCommit.wait(timeout: .now() + 2)
        }
        let replacementDocument = try ingestedDocument(
            text: "Replacement revision invalidates the concurrently approved grant."
        )

        let approvalTask = Task.detached {
            try store.approveTrustedSourceReview(
                reviewID: pending.review.reviewID,
                confirmationToken: pending.review.confirmationToken,
                disclosureVersion: pending.review.disclosureVersion,
                usageScope: pending.review.usageScope,
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 5_001)
            )
        }
        XCTAssertEqual(approvalReachedCommit.wait(timeout: .now() + 2), .success)
        let replacementTask = Task.detached {
            try store.replaceDocument(
                result: replacementDocument,
                documentID: "approval-race"
            )
            replacementFinished.signal()
        }
        XCTAssertEqual(replacementFinished.wait(timeout: .now() + 0.05), .timedOut)
        allowApprovalCommit.signal()
        _ = try await approvalTask.value
        try await replacementTask.value
        store.onBeforeTrustedSourceApprovalCommit = nil

        XCTAssertTrue(try store.trustedSources(actorDeviceID: "device-a", limit: 10).isEmpty)
    }

    func testInMemoryChatContextConsumptionIsDeviceScopedOrderedAndContentFreeInAudit() throws {
        let store = RuntimeDocumentIndexStore()
        let firstBody = "FIRST_PRIVATE_CONTEXT_BODY"
        let secondBody = "SECOND_PRIVATE_CONTEXT_BODY"
        let firstGrant = try approvedGrant(
            store: store,
            documentID: "context-first",
            text: "Trusted first source. \(firstBody)",
            query: "first source",
            timestamp: 7_000
        )
        let secondGrant = try approvedGrant(
            store: store,
            documentID: "context-second",
            text: "Trusted second source. \(secondBody)",
            query: "second source",
            timestamp: 7_010
        )

        let contexts = try store.consumeTrustedSourceChatContexts(
            grantIDs: [secondGrant.grantID, firstGrant.grantID],
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 7_020)
        )
        XCTAssertEqual(contexts.map(\.grantID), [secondGrant.grantID, firstGrant.grantID])
        XCTAssertTrue(contexts[0].text.contains(secondBody))
        XCTAssertTrue(contexts[1].text.contains(firstBody))
        XCTAssertLessThanOrEqual(
            contexts.map { $0.text.utf8.count }.max() ?? 0,
            runtimeTrustedSourceChatContextTextUTF8ByteLimit
        )
        XCTAssertThrowsError(
            try store.consumeTrustedSourceChatContexts(
                grantIDs: [firstGrant.grantID],
                actorDeviceID: "device-b",
                timestamp: Date(timeIntervalSince1970: 7_021)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .trustedSourceNotFound)
        }

        let auditData = try JSONEncoder().encode(store.sourceAuditEvents(limit: 100))
        let auditText = String(decoding: auditData, as: UTF8.self)
        XCTAssertEqual(
            store.sourceAuditEvents(limit: 100)
                .filter { $0.action == .trustedSourceContextConsumed }.count,
            2
        )
        XCTAssertFalse(auditText.contains(firstBody))
        XCTAssertFalse(auditText.contains(secondBody))
    }

    func testInMemoryChatContextConsumptionIsAllOrNothingAndRevocationBlocksReuse() throws {
        let store = RuntimeDocumentIndexStore()
        let grant = try approvedGrant(
            store: store,
            documentID: "context-atomic",
            text: "Atomic trusted source context.",
            query: "atomic trusted",
            timestamp: 7_100
        )
        XCTAssertThrowsError(
            try store.consumeTrustedSourceChatContexts(
                grantIDs: [grant.grantID, "trusted_source_ffffffffffffffffffffffffffffffff"],
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 7_101)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .trustedSourceNotFound)
        }
        XCTAssertTrue(
            store.sourceAuditEvents(limit: 100)
                .filter { $0.action == .trustedSourceContextConsumed }.isEmpty
        )
        try store.revokeTrustedSource(
            grantID: grant.grantID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 7_102)
        )
        XCTAssertThrowsError(
            try store.consumeTrustedSourceChatContexts(
                grantIDs: [grant.grantID],
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 7_103)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .trustedSourceNotFound)
        }
    }

    func testSQLiteChatContextConsumptionPersistsAndTracksExactRevision() throws {
        let databaseURL = temporaryDatabaseURL()
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        let original = try ingestedDocument(text: "Durable trusted chat context revision.")
        try store.replaceDocument(result: original, documentID: "durable-context")
        let anchorID = try XCTUnwrap(
            store.query("chat context", limit: 1, maxSnippetCharacters: 80).first?.sourceAnchorID
        )
        let review = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: 7_200)
        )
        let grant = try approve(
            review.review,
            store: store,
            timestamp: Date(timeIntervalSince1970: 7_201)
        )

        let reopened = SQLiteRuntimeDocumentIndexStore(databaseURL: databaseURL)
        XCTAssertEqual(
            try reopened.consumeTrustedSourceChatContexts(
                grantIDs: [grant.grantID],
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 7_202)
            ).first?.sourceAnchorID,
            anchorID
        )
        try reopened.replaceDocument(result: original, documentID: "durable-context")
        XCTAssertEqual(
            try reopened.consumeTrustedSourceChatContexts(
                grantIDs: [grant.grantID],
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 7_203)
            ).count,
            1
        )
        try reopened.replaceDocument(
            result: ingestedDocument(text: "A changed revision invalidates prior context grants."),
            documentID: "durable-context"
        )
        XCTAssertThrowsError(
            try reopened.consumeTrustedSourceChatContexts(
                grantIDs: [grant.grantID],
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 7_204)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .trustedSourceNotFound)
        }
    }

    func testSQLiteChatContextConsumptionLinearizesBeforeConcurrentRevocation() async throws {
        let store = SQLiteRuntimeDocumentIndexStore(databaseURL: temporaryDatabaseURL())
        let grant = try approvedGrant(
            store: store,
            documentID: "context-race",
            text: "Context consumption and revoke must serialize.",
            query: "must serialize",
            timestamp: 7_300
        )
        let consumptionReachedCommit = DispatchSemaphore(value: 0)
        let allowConsumptionCommit = DispatchSemaphore(value: 0)
        let revokeFinished = DispatchSemaphore(value: 0)
        store.onBeforeTrustedSourceContextAuditCommit = {
            consumptionReachedCommit.signal()
            _ = allowConsumptionCommit.wait(timeout: .now() + 2)
        }
        let consumptionTask = Task.detached {
            try store.consumeTrustedSourceChatContexts(
                grantIDs: [grant.grantID],
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 7_301)
            )
        }
        XCTAssertEqual(consumptionReachedCommit.wait(timeout: .now() + 2), .success)
        let revokeTask = Task.detached {
            try store.revokeTrustedSource(
                grantID: grant.grantID,
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 7_302)
            )
            revokeFinished.signal()
        }
        XCTAssertEqual(revokeFinished.wait(timeout: .now() + 0.05), .timedOut)
        allowConsumptionCommit.signal()
        let consumedContexts = try await consumptionTask.value
        XCTAssertEqual(consumedContexts.count, 1)
        try await revokeTask.value
        store.onBeforeTrustedSourceContextAuditCommit = nil

        XCTAssertThrowsError(
            try store.consumeTrustedSourceChatContexts(
                grantIDs: [grant.grantID],
                actorDeviceID: "device-a",
                timestamp: Date(timeIntervalSince1970: 7_303)
            )
        ) {
            XCTAssertEqual($0 as? RuntimeTrustedSourceGovernanceError, .trustedSourceNotFound)
        }
    }

    private func approve(
        _ review: RuntimeTrustedSourceReview,
        store: any RuntimeDocumentSourceGovernance,
        timestamp: Date
    ) throws -> RuntimeTrustedSourceGrant {
        try store.approveTrustedSourceReview(
            reviewID: review.reviewID,
            confirmationToken: review.confirmationToken,
            disclosureVersion: review.disclosureVersion,
            usageScope: review.usageScope,
            actorDeviceID: "device-a",
            timestamp: timestamp
        )
    }

    private func approvedGrant(
        store: any RuntimeDocumentSourceGovernance & RuntimeDocumentIndexSearchReading,
        documentID: String,
        text: String,
        query: String,
        timestamp: TimeInterval
    ) throws -> RuntimeTrustedSourceGrant {
        if let store = store as? RuntimeDocumentIndexStore {
            _ = store.replaceDocument(result: try ingestedDocument(text: text), documentID: documentID)
        } else if let store = store as? SQLiteRuntimeDocumentIndexStore {
            try store.replaceDocument(result: ingestedDocument(text: text), documentID: documentID)
        } else {
            XCTFail("Unsupported document store type")
        }
        let anchorID = try XCTUnwrap(
            try store.query(query, limit: 1, maxSnippetCharacters: 80).first?.sourceAnchorID
        )
        let prepared = try store.prepareTrustedSourceReview(
            sourceAnchorID: anchorID,
            actorDeviceID: "device-a",
            timestamp: Date(timeIntervalSince1970: timestamp)
        )
        return try approve(
            prepared.review,
            store: store,
            timestamp: Date(timeIntervalSince1970: timestamp + 1)
        )
    }

    private func ingestedDocument(text: String) throws -> DocumentIngestionResult {
        try DocumentIngestor(chunker: DocumentChunker(policy: DocumentChunkingPolicy(
            maxCharacters: 120,
            overlapCharacters: 8,
            minChunkCharacters: 24
        ))).ingest(extractedDocument: ExtractedDocument(
            fileName: "citation-guide.md",
            mimeType: "text/markdown",
            text: text
        ))
    }

    private func temporaryDatabaseURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("runtime-document-index.sqlite")
    }
}
