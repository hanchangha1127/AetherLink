import DocumentIngestion
import Darwin
import Foundation

public let runtimeDocumentSourceDisclosureVersion = 1
public let runtimeDocumentSourceReviewLifetime: TimeInterval = 10 * 60
public let runtimeDocumentSourceCatalogLimit = 800
public let runtimeDocumentSourceAuditPreviewLimit = 50
public let runtimeDocumentSourceAuditExportLimit = 1_000

public struct CompanionRuntimeDocumentSource: Identifiable, Equatable, Sendable {
    public var id: String
    public var displayName: String
    public var mimeType: String
    public var extractedCharacterCount: Int
    public var chunkCount: Int
    public var quality: DocumentIngestionQuality
    public var sourceRevision: String
    public var approvedAt: Date
}

public struct CompanionRuntimeDocumentImportReview: Identifiable, Equatable, Sendable {
    public var id: UUID
    public var confirmationToken: String
    public var disclosureVersion: Int
    public var sourceID: String
    public var displayName: String
    public var mimeType: String
    public var extractedCharacterCount: Int
    public var chunkCount: Int
    public var quality: DocumentIngestionQuality
    public var candidateRevision: String
    public var replacingExistingSource: Bool
    public var expiresAt: Date
}

public enum RuntimeDocumentSourceManagementError: LocalizedError, Equatable, Sendable {
    case sourceUnavailable
    case unsupportedOrUnreadableDocument
    case resourceLimitExceeded
    case reviewExpired
    case invalidConfirmation
    case sourceChanged
    case storageUnavailable

    public var errorDescription: String? {
        switch self {
        case .sourceUnavailable:
            return "The selected document is no longer available."
        case .unsupportedOrUnreadableDocument:
            return "AetherLink could not extract supported text from this document."
        case .resourceLimitExceeded:
            return "This document exceeds the local ingestion safety limits."
        case .reviewExpired:
            return "This document review expired. Select the document again."
        case .invalidConfirmation:
            return "The document sharing confirmation is invalid. Review the source again."
        case .sourceChanged:
            return "This source changed after the review started. Review the latest source before sharing it."
        case .storageUnavailable:
            return "AetherLink could not update the local document library."
        }
    }
}

public actor RuntimeDocumentSourceManager {
    private struct PendingReview: Sendable {
        var review: CompanionRuntimeDocumentImportReview
        var result: DocumentIngestionResult
        var expectedActiveRevision: String?
    }

    private struct AuditExportEnvelope: Codable {
        var schemaVersion: Int
        var generatedAt: Date
        var retentionPolicy: String
        var maximumExportedEvents: Int
        var events: [RuntimeDocumentSourceAuditEvent]
    }

    private let store: SQLiteRuntimeDocumentIndexStore
    private let ingestor: DocumentIngestor
    private let now: @Sendable () -> Date
    private let onBeforeSnapshotOpen: (@Sendable () -> Void)?
    private var pendingReviews: [UUID: PendingReview] = [:]

    public init(
        store: SQLiteRuntimeDocumentIndexStore,
        ingestor: DocumentIngestor = DocumentIngestor(),
        now: @escaping @Sendable () -> Date = { Date() },
        onBeforeSnapshotOpen: (@Sendable () -> Void)? = nil
    ) {
        self.store = store
        self.ingestor = ingestor
        self.now = now
        self.onBeforeSnapshotOpen = onBeforeSnapshotOpen
    }

    public func prepareImport(
        from sourceURL: URL,
        replacingSourceID: String? = nil
    ) throws -> CompanionRuntimeDocumentImportReview {
        purgeExpiredReviews()
        let replacementID = replacingSourceID.flatMap(runtimeDocumentIndexCanonicalDocumentID)
        if replacingSourceID != nil, replacementID == nil {
            throw RuntimeDocumentSourceManagementError.sourceChanged
        }

        let snapshot = try makePrivateSnapshot(of: sourceURL)
        defer { try? FileManager.default.removeItem(at: snapshot.directoryURL) }

        let result: DocumentIngestionResult
        do {
            let snapshotResult = try ingestor.ingest(fileURL: snapshot.fileURL)
            result = try ingestor.ingest(extractedDocument: ExtractedDocument(
                fileName: safeDisplayName(for: sourceURL),
                mimeType: snapshotResult.document.mimeType,
                text: snapshotResult.document.text
            ))
        } catch let error as DocumentIngestionError {
            switch error {
            case .resourceLimitExceeded, .invalidResourcePolicy:
                throw RuntimeDocumentSourceManagementError.resourceLimitExceeded
            default:
                throw RuntimeDocumentSourceManagementError.unsupportedOrUnreadableDocument
            }
        } catch {
            throw RuntimeDocumentSourceManagementError.unsupportedOrUnreadableDocument
        }

        let sourceID = replacementID ?? "source_\(UUID().uuidString.lowercased())"
        let expectedApproval: RuntimeDocumentSourceApproval?
        do {
            expectedApproval = try replacementID.flatMap { try store.sourceApproval(documentID: $0) }
        } catch {
            throw RuntimeDocumentSourceManagementError.storageUnavailable
        }
        if replacementID != nil, expectedApproval == nil {
            throw RuntimeDocumentSourceManagementError.sourceChanged
        }

        let document = runtimeDocumentIndexDocument(for: result, documentID: sourceID)
        let chunks = runtimeDocumentIndexChunks(for: result, documentID: sourceID)
        let reviewID = UUID()
        let timestamp = now()
        let review = CompanionRuntimeDocumentImportReview(
            id: reviewID,
            confirmationToken: "\(UUID().uuidString.lowercased()).\(UUID().uuidString.lowercased())",
            disclosureVersion: runtimeDocumentSourceDisclosureVersion,
            sourceID: sourceID,
            displayName: document.displayName,
            mimeType: document.mimeType,
            extractedCharacterCount: document.extractedCharacterCount,
            chunkCount: document.chunkCount,
            quality: document.quality,
            candidateRevision: runtimeDocumentSourceRevision(document: document, chunks: chunks),
            replacingExistingSource: replacementID != nil,
            expiresAt: timestamp.addingTimeInterval(runtimeDocumentSourceReviewLifetime)
        )
        pendingReviews.removeAll(keepingCapacity: true)
        pendingReviews[reviewID] = PendingReview(
            review: review,
            result: result,
            expectedActiveRevision: expectedApproval?.sourceRevision
        )
        return review
    }

    public func approve(
        reviewID: UUID,
        confirmationToken: String,
        disclosureVersion: Int
    ) throws -> CompanionRuntimeDocumentSource {
        purgeExpiredReviews()
        guard let pending = pendingReviews[reviewID] else {
            throw RuntimeDocumentSourceManagementError.reviewExpired
        }
        guard pending.review.confirmationToken == confirmationToken,
              pending.review.disclosureVersion == disclosureVersion,
              disclosureVersion == runtimeDocumentSourceDisclosureVersion else {
            throw RuntimeDocumentSourceManagementError.invalidConfirmation
        }

        do {
            let document = try store.replaceDocument(
                result: pending.result,
                documentID: pending.review.sourceID,
                ifCurrentSourceRevisionEquals: pending.expectedActiveRevision
            )
            pendingReviews.removeValue(forKey: reviewID)
            return CompanionRuntimeDocumentSource(
                id: document.id,
                displayName: document.displayName,
                mimeType: document.mimeType,
                extractedCharacterCount: document.extractedCharacterCount,
                chunkCount: document.chunkCount,
                quality: document.quality,
                sourceRevision: pending.review.candidateRevision,
                approvedAt: now()
            )
        } catch is RuntimeDocumentSourceRevisionConflictError {
            throw RuntimeDocumentSourceManagementError.sourceChanged
        } catch let error as RuntimeDocumentSourceManagementError {
            throw error
        } catch {
            throw RuntimeDocumentSourceManagementError.storageUnavailable
        }
    }

    public func cancel(reviewID: UUID) {
        pendingReviews.removeValue(forKey: reviewID)
    }

    public func sources(limit: Int = runtimeDocumentSourceCatalogLimit) throws -> [CompanionRuntimeDocumentSource] {
        do {
            return try store.hostManagedApprovedDocuments(limit: limit).compactMap { document in
                guard let approval = try store.sourceApproval(documentID: document.id) else { return nil }
                return sourceRecord(document: document, approval: approval)
            }
        } catch {
            throw RuntimeDocumentSourceManagementError.storageUnavailable
        }
    }

    public func removeSource(id sourceID: String, expectedRevision: String) throws {
        do {
            try store.deleteDocument(
                id: sourceID,
                ifCurrentSourceRevisionEquals: expectedRevision
            )
        } catch is RuntimeDocumentSourceRevisionConflictError {
            throw RuntimeDocumentSourceManagementError.sourceChanged
        } catch let error as RuntimeDocumentSourceManagementError {
            throw error
        } catch {
            throw RuntimeDocumentSourceManagementError.storageUnavailable
        }
    }

    public func auditEvents(limit: Int = runtimeDocumentSourceAuditPreviewLimit) throws -> [RuntimeDocumentSourceAuditEvent] {
        do {
            return try store.sourceAuditEvents(limit: limit)
        } catch {
            throw RuntimeDocumentSourceManagementError.storageUnavailable
        }
    }

    public func auditExportData() throws -> Data {
        let events: [RuntimeDocumentSourceAuditEvent]
        do {
            events = try store.sourceAuditEvents(limit: runtimeDocumentSourceAuditExportLimit)
        } catch {
            throw RuntimeDocumentSourceManagementError.storageUnavailable
        }
        let envelope = AuditExportEnvelope(
            schemaVersion: 1,
            generatedAt: now(),
            retentionPolicy: "app_data_lifetime",
            maximumExportedEvents: runtimeDocumentSourceAuditExportLimit,
            events: events
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        do {
            return try encoder.encode(envelope)
        } catch {
            throw RuntimeDocumentSourceManagementError.storageUnavailable
        }
    }

    private func purgeExpiredReviews() {
        let timestamp = now()
        pendingReviews = pendingReviews.filter { $0.value.review.expiresAt > timestamp }
    }

    private func makePrivateSnapshot(of sourceURL: URL) throws -> (directoryURL: URL, fileURL: URL) {
        let didAccessSecurityScope = sourceURL.startAccessingSecurityScopedResource()
        defer {
            if didAccessSecurityScope {
                sourceURL.stopAccessingSecurityScopedResource()
            }
        }

        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-document-review-\(UUID().uuidString)", isDirectory: true)
        do {
            try FileManager.default.createDirectory(
                at: directoryURL,
                withIntermediateDirectories: false,
                attributes: [.posixPermissions: 0o700]
            )
        } catch {
            throw RuntimeDocumentSourceManagementError.sourceUnavailable
        }

        let safeExtension = sourceURL.pathExtension
            .lowercased()
            .filter { $0.isASCII && ($0.isLetter || $0.isNumber) }
        let snapshotName = safeExtension.isEmpty ? "source" : "source.\(safeExtension.prefix(16))"
        let snapshotURL = directoryURL.appendingPathComponent(snapshotName, isDirectory: false)
        var coordinationError: NSError?
        var copyError: Error?
        NSFileCoordinator().coordinate(
            readingItemAt: sourceURL,
            options: [.withoutChanges],
            error: &coordinationError
        ) { coordinatedURL in
            do {
                let values = try coordinatedURL.resourceValues(forKeys: [
                    .isRegularFileKey,
                    .isSymbolicLinkKey,
                    .fileSizeKey,
                ])
                guard values.isRegularFile == true, values.isSymbolicLink != true else {
                    throw RuntimeDocumentSourceManagementError.sourceUnavailable
                }
                if let fileSize = values.fileSize,
                   fileSize > documentIngestionResourcePolicyMaxInputBytesCeiling {
                    throw RuntimeDocumentSourceManagementError.resourceLimitExceeded
                }
                onBeforeSnapshotOpen?()
                try copyBoundedFile(from: coordinatedURL, to: snapshotURL)
            } catch {
                copyError = error
            }
        }
        if let copyError {
            try? FileManager.default.removeItem(at: directoryURL)
            if let managementError = copyError as? RuntimeDocumentSourceManagementError {
                throw managementError
            }
            throw RuntimeDocumentSourceManagementError.sourceUnavailable
        }
        if coordinationError != nil {
            try? FileManager.default.removeItem(at: directoryURL)
            throw RuntimeDocumentSourceManagementError.sourceUnavailable
        }
        return (directoryURL, snapshotURL)
    }

    private func copyBoundedFile(from sourceURL: URL, to destinationURL: URL) throws {
        let inputDescriptor = Darwin.open(
            sourceURL.path,
            O_RDONLY | O_CLOEXEC | O_NOFOLLOW
        )
        guard inputDescriptor >= 0 else {
            throw RuntimeDocumentSourceManagementError.sourceUnavailable
        }
        var sourceStatus = stat()
        guard fstat(inputDescriptor, &sourceStatus) == 0,
              sourceStatus.st_mode & S_IFMT == S_IFREG,
              sourceStatus.st_size >= 0,
              sourceStatus.st_size <= off_t(documentIngestionResourcePolicyMaxInputBytesCeiling) else {
            Darwin.close(inputDescriptor)
            if sourceStatus.st_size > off_t(documentIngestionResourcePolicyMaxInputBytesCeiling) {
                throw RuntimeDocumentSourceManagementError.resourceLimitExceeded
            }
            throw RuntimeDocumentSourceManagementError.sourceUnavailable
        }
        let outputDescriptor = Darwin.open(
            destinationURL.path,
            O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW,
            mode_t(0o600)
        )
        guard outputDescriptor >= 0 else {
            Darwin.close(inputDescriptor)
            throw RuntimeDocumentSourceManagementError.sourceUnavailable
        }
        let input = FileHandle(fileDescriptor: inputDescriptor, closeOnDealloc: true)
        let output = FileHandle(fileDescriptor: outputDescriptor, closeOnDealloc: true)
        defer {
            try? input.close()
            try? output.close()
        }
        var copiedBytes = 0
        while let data = try input.read(upToCount: 64 * 1024), !data.isEmpty {
            copiedBytes += data.count
            guard copiedBytes <= documentIngestionResourcePolicyMaxInputBytesCeiling else {
                throw RuntimeDocumentSourceManagementError.resourceLimitExceeded
            }
            try output.write(contentsOf: data)
        }
        try output.synchronize()
    }

    private func safeDisplayName(for sourceURL: URL) -> String {
        let name = sourceURL.lastPathComponent.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty,
              name.count <= documentIngestionDocumentFileNameCharacterLimitCeiling,
              !name.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else {
            return documentIngestionUnknownDocumentFileName
        }
        return name
    }

    private func sourceRecord(
        document: RuntimeDocumentIndexDocument,
        approval: RuntimeDocumentSourceApproval
    ) -> CompanionRuntimeDocumentSource {
        CompanionRuntimeDocumentSource(
            id: document.id,
            displayName: document.displayName,
            mimeType: document.mimeType,
            extractedCharacterCount: document.extractedCharacterCount,
            chunkCount: document.chunkCount,
            quality: document.quality,
            sourceRevision: approval.sourceRevision,
            approvedAt: approval.approvedAt
        )
    }
}
