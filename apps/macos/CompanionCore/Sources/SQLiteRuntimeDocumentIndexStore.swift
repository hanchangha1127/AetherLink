import DocumentIngestion
import Foundation
import SQLite3

public final class SQLiteRuntimeDocumentIndexStore: @unchecked Sendable {
    private let databaseURL: URL
    private let lock = NSLock()

    public init(databaseURL: URL = SQLiteRuntimeDocumentIndexStore.defaultDatabaseURL()) {
        self.databaseURL = databaseURL
    }

    public static func defaultDatabaseURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-document-index.sqlite", isDirectory: false)
    }

    @discardableResult
    public func replaceDocument(
        result: DocumentIngestionResult,
        documentID requestedDocumentID: String? = nil
    ) throws -> RuntimeDocumentIndexDocument {
        let documentID = runtimeDocumentIndexEffectiveDocumentID(
            requestedDocumentID,
            fallback: RuntimeDocumentIndexStore.stableDocumentID(for: result)
        )
        let document = runtimeDocumentIndexDocument(for: result, documentID: documentID)
        let chunks = runtimeDocumentIndexChunks(for: result, documentID: documentID)

        return try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    try deleteDocumentUnlocked(id: documentID, database: database)
                    try insertDocumentUnlocked(document, database: database)
                    for chunk in chunks {
                        try insertChunkUnlocked(chunk, database: database)
                    }
                    try Self.execute(database, "COMMIT")
                    return document
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocument(id documentID: String) throws {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return }
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    try deleteDocumentUnlocked(id: documentID, database: database)
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteAllDocuments() throws {
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    try deleteAllDocumentsUnlocked(database: database)
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocuments(matchingQuality quality: DocumentIngestionQuality) throws {
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let documentIDs = try documentIDsUnlocked(matchingQuality: quality, database: database)
                    for documentID in documentIDs {
                        try deleteDocumentUnlocked(id: documentID, database: database)
                    }
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocuments(matchingContentFingerprint contentFingerprint: String) throws {
        guard let contentFingerprint = runtimeDocumentIndexCanonicalContentFingerprint(contentFingerprint) else { return }
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let documentIDs = try documentIDsUnlocked(
                        matchingContentFingerprint: contentFingerprint,
                        database: database
                    )
                    for documentID in documentIDs {
                        try deleteDocumentUnlocked(id: documentID, database: database)
                    }
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocuments(matchingDisplayName displayName: String) throws {
        guard let displayName = runtimeDocumentIndexCanonicalDisplayName(displayName) else { return }
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let documentIDs = try documentIDsUnlocked(matchingDisplayName: displayName, database: database)
                    for documentID in documentIDs {
                        try deleteDocumentUnlocked(id: documentID, database: database)
                    }
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func deleteDocuments(matchingMimeType mimeType: String) throws {
        guard let mimeType = runtimeDocumentIndexCanonicalMimeType(mimeType) else { return }
        try lock.withLock {
            try withDatabase { database in
                try Self.execute(database, "BEGIN IMMEDIATE")
                do {
                    let documentIDs = try documentIDsUnlocked(matchingMimeType: mimeType, database: database)
                    for documentID in documentIDs {
                        try deleteDocumentUnlocked(id: documentID, database: database)
                    }
                    try Self.execute(database, "COMMIT")
                } catch {
                    try? Self.execute(database, "ROLLBACK")
                    throw error
                }
            }
        }
    }

    public func document(id documentID: String) throws -> RuntimeDocumentIndexDocument? {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                try documentUnlocked(id: documentID, database: database)
            }
        }
    }

    public func chunks(
        for documentID: String,
        limit: Int = 200
    ) throws -> [RuntimeDocumentIndexChunk] {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexChunkReadLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try chunksUnlocked(for: documentID, limit: effectiveLimit, database: database)
            }
        }
    }

    public func chunkSummaries(
        for documentID: String,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexChunkSummary] {
        guard let documentID = runtimeDocumentIndexCanonicalDocumentID(documentID),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexChunkSummaryLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try chunkSummariesUnlocked(for: documentID, limit: effectiveLimit, database: database)
            }
        }
    }

    public func sourceAnchor(id sourceAnchorID: String) throws -> RuntimeDocumentSourceAnchor? {
        guard let sourceAnchorID = runtimeDocumentIndexCanonicalSourceAnchorID(sourceAnchorID) else { return nil }
        return try lock.withLock {
            try withDatabase { database in
                try sourceAnchorUnlocked(id: sourceAnchorID, database: database)
            }
        }
    }

    public func documents(limit: Int = 100) throws -> [RuntimeDocumentIndexDocument] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(limit: effectiveLimit, database: database)
            }
        }
    }

    public func documents(
        matchingDisplayName displayName: String,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexDocument] {
        guard let displayName = runtimeDocumentIndexCanonicalDisplayName(displayName),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(matchingDisplayName: displayName, limit: effectiveLimit, database: database)
            }
        }
    }

    public func documents(
        matchingContentFingerprint contentFingerprint: String,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexDocument] {
        guard let contentFingerprint = runtimeDocumentIndexCanonicalContentFingerprint(contentFingerprint),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(
                    matchingContentFingerprint: contentFingerprint,
                    limit: effectiveLimit,
                    database: database
                )
            }
        }
    }

    public func documents(
        matchingMimeType mimeType: String,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexDocument] {
        guard let mimeType = runtimeDocumentIndexCanonicalMimeType(mimeType),
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexCatalogLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(matchingMimeType: mimeType, limit: effectiveLimit, database: database)
            }
        }
    }

    public func documents(
        matchingQuality quality: DocumentIngestionQuality,
        limit: Int = 100
    ) throws -> [RuntimeDocumentIndexDocument] {
        guard let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
            limit,
            ceiling: runtimeDocumentIndexCatalogLimitCeiling
        ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                try documentsUnlocked(matchingQuality: quality, limit: effectiveLimit, database: database)
            }
        }
    }

    public func summary() throws -> RuntimeDocumentIndexSummary {
        try lock.withLock {
            try withDatabase { database in
                try summaryUnlocked(database: database)
            }
        }
    }

    public func query(
        _ query: String,
        limit: Int = 10,
        maxSnippetCharacters: Int = 160
    ) throws -> [RuntimeDocumentSearchResult] {
        let terms = runtimeDocumentSearchTerms(query)
        guard !terms.isEmpty,
              let effectiveLimit = runtimeDocumentIndexEffectiveLimit(
                limit,
                ceiling: runtimeDocumentIndexQueryLimitCeiling
              ),
              let effectiveSnippetLimit = runtimeDocumentIndexEffectiveLimit(
                maxSnippetCharacters,
                ceiling: runtimeDocumentIndexSnippetCharacterLimitCeiling
              ) else { return [] }
        return try lock.withLock {
            try withDatabase { database in
                return try runtimeDocumentSearchResults(
                    from: searchSnapshotUnlocked(database),
                    query: query,
                    limit: effectiveLimit,
                    maxSnippetCharacters: effectiveSnippetLimit
                )
            }
        }
    }

    private func insertDocumentUnlocked(
        _ document: RuntimeDocumentIndexDocument,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_index_documents(
                document_id,
                display_name,
                mime_type,
                content_fingerprint,
                extracted_character_count,
                chunk_count,
                quality
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(document.id, to: statement, at: 1)
        try Self.bindText(document.displayName, to: statement, at: 2)
        try Self.bindText(document.mimeType, to: statement, at: 3)
        try Self.bindText(document.contentFingerprint, to: statement, at: 4)
        try Self.bindInt(document.extractedCharacterCount, to: statement, at: 5)
        try Self.bindInt(document.chunkCount, to: statement, at: 6)
        try Self.bindText(document.quality.rawValue, to: statement, at: 7)
        try Self.stepDone(statement, database: database)
    }

    private func insertChunkUnlocked(
        _ chunk: RuntimeDocumentIndexChunk,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_index_chunks(
                chunk_id,
                document_id,
                document_display_name,
                document_mime_type,
                chunk_index,
                start_character_offset,
                end_character_offset,
                text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(chunk.id, to: statement, at: 1)
        try Self.bindText(chunk.documentID, to: statement, at: 2)
        try Self.bindText(chunk.documentDisplayName, to: statement, at: 3)
        try Self.bindText(chunk.documentMimeType, to: statement, at: 4)
        try Self.bindInt(chunk.chunkIndex, to: statement, at: 5)
        try Self.bindInt(chunk.startCharacterOffset, to: statement, at: 6)
        try Self.bindInt(chunk.endCharacterOffset, to: statement, at: 7)
        try Self.bindText(chunk.text, to: statement, at: 8)
        try Self.stepDone(statement, database: database)
        try insertChunkSearchRowUnlocked(chunk, database: database)
    }

    private func insertChunkSearchRowUnlocked(
        _ chunk: RuntimeDocumentIndexChunk,
        database: OpaquePointer
    ) throws {
        let statement = try Self.prepare(
            database,
            """
            INSERT INTO runtime_document_index_chunk_fts(
                chunk_id,
                document_id,
                text
            ) VALUES (?, ?, ?)
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(chunk.id, to: statement, at: 1)
        try Self.bindText(chunk.documentID, to: statement, at: 2)
        try Self.bindText(chunk.text, to: statement, at: 3)
        try Self.stepDone(statement, database: database)
    }

    private func deleteDocumentUnlocked(id documentID: String, database: OpaquePointer) throws {
        let deleteSearchRows = try Self.prepare(
            database,
            "DELETE FROM runtime_document_index_chunk_fts WHERE document_id = ?"
        )
        defer { sqlite3_finalize(deleteSearchRows) }
        try Self.bindText(documentID, to: deleteSearchRows, at: 1)
        try Self.stepDone(deleteSearchRows, database: database)

        let deleteChunks = try Self.prepare(
            database,
            "DELETE FROM runtime_document_index_chunks WHERE document_id = ?"
        )
        defer { sqlite3_finalize(deleteChunks) }
        try Self.bindText(documentID, to: deleteChunks, at: 1)
        try Self.stepDone(deleteChunks, database: database)

        let deleteDocument = try Self.prepare(
            database,
            "DELETE FROM runtime_document_index_documents WHERE document_id = ?"
        )
        defer { sqlite3_finalize(deleteDocument) }
        try Self.bindText(documentID, to: deleteDocument, at: 1)
        try Self.stepDone(deleteDocument, database: database)
    }

    private func deleteAllDocumentsUnlocked(database: OpaquePointer) throws {
        try Self.execute(database, "DELETE FROM runtime_document_index_chunk_fts")
        try Self.execute(database, "DELETE FROM runtime_document_index_chunks")
        try Self.execute(database, "DELETE FROM runtime_document_index_documents")
    }

    private func documentIDsUnlocked(
        matchingQuality quality: DocumentIngestionQuality,
        database: OpaquePointer
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id
            FROM runtime_document_index_documents
            WHERE quality = ?
            ORDER BY document_id ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(quality.rawValue, to: statement, at: 1)

        var documentIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index quality deletion rows.")
            }
            documentIDs.append(try Self.columnText(statement, 0))
        }
        return documentIDs
    }

    private func documentIDsUnlocked(
        matchingContentFingerprint contentFingerprint: String,
        database: OpaquePointer
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id
            FROM runtime_document_index_documents
            WHERE content_fingerprint = ?
            ORDER BY document_id ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(contentFingerprint, to: statement, at: 1)

        var documentIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index fingerprint deletion rows.")
            }
            documentIDs.append(try Self.columnText(statement, 0))
        }
        return documentIDs
    }

    private func documentIDsUnlocked(
        matchingDisplayName displayName: String,
        database: OpaquePointer
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id
            FROM runtime_document_index_documents
            WHERE display_name = ?
            ORDER BY document_id ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(displayName, to: statement, at: 1)

        var documentIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index display-name deletion rows.")
            }
            documentIDs.append(try Self.columnText(statement, 0))
        }
        return documentIDs
    }

    private func documentIDsUnlocked(
        matchingMimeType mimeType: String,
        database: OpaquePointer
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id
            FROM runtime_document_index_documents
            WHERE mime_type = ?
            ORDER BY document_id ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(mimeType, to: statement, at: 1)

        var documentIDs: [String] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index MIME-type deletion rows.")
            }
            documentIDs.append(try Self.columnText(statement, 0))
        }
        return documentIDs
    }

    private func documentUnlocked(
        id documentID: String,
        database: OpaquePointer
    ) throws -> RuntimeDocumentIndexDocument? {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id, display_name, mime_type, content_fingerprint,
                   extracted_character_count, chunk_count, quality
            FROM runtime_document_index_documents
            WHERE document_id = ?
            LIMIT 1
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(documentID, to: statement, at: 1)
        let result = sqlite3_step(statement)
        if result == SQLITE_DONE { return nil }
        guard result == SQLITE_ROW else {
            throw Self.failure(database, "Could not read runtime document index document.")
        }
        return try Self.document(from: statement)
    }

    private func chunksUnlocked(
        for documentID: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexChunk] {
        try readChunksUnlocked(
            database,
            sql: """
            SELECT chunk_id, document_id, document_display_name, document_mime_type,
                   chunk_index, start_character_offset, end_character_offset, text
            FROM runtime_document_index_chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            LIMIT ?
            """,
            bind: { statement in
                try Self.bindText(documentID, to: statement, at: 1)
                try Self.bindInt(limit, to: statement, at: 2)
            }
        )
    }

    private func chunkSummariesUnlocked(
        for documentID: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexChunkSummary] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id, document_display_name, document_mime_type,
                   chunk_index, start_character_offset, end_character_offset, length(text)
            FROM runtime_document_index_chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(documentID, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var chunks: [RuntimeDocumentIndexChunkSummary] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index chunk summaries.")
            }
            chunks.append(try Self.chunkSummary(from: statement))
        }
        return chunks
    }

    private func sourceAnchorUnlocked(
        id sourceAnchorID: String,
        database: OpaquePointer
    ) throws -> RuntimeDocumentSourceAnchor? {
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality,
                   c.document_id, c.document_display_name, c.document_mime_type,
                   c.chunk_index, c.start_character_offset, c.end_character_offset, length(c.text)
            FROM runtime_document_index_chunks c
            JOIN runtime_document_index_documents d ON d.document_id = c.document_id
            ORDER BY d.display_name ASC, c.chunk_index ASC
            """
        )
        defer { sqlite3_finalize(statement) }

        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { return nil }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not resolve runtime document source anchor.")
            }
            let document = try Self.document(from: statement, offset: 0)
            let chunkSummary = try Self.chunkSummary(from: statement, offset: 7)
            let anchor = RuntimeDocumentSourceAnchor(
                sourceAnchorID: runtimeDocumentSourceAnchorID(document: document, chunkSummary: chunkSummary),
                document: document,
                chunkSummary: chunkSummary
            )
            if anchor.sourceAnchorID == sourceAnchorID {
                return anchor
            }
        }
    }

    private func documentsUnlocked(
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id, display_name, mime_type, content_fingerprint,
                   extracted_character_count, chunk_count, quality
            FROM runtime_document_index_documents
            ORDER BY display_name ASC, document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindInt(limit, to: statement, at: 1)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index catalog rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func documentsUnlocked(
        matchingMimeType mimeType: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id, display_name, mime_type, content_fingerprint,
                   extracted_character_count, chunk_count, quality
            FROM runtime_document_index_documents
            WHERE mime_type = ?
            ORDER BY display_name ASC, document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(mimeType, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index MIME-type rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func documentsUnlocked(
        matchingDisplayName displayName: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id, display_name, mime_type, content_fingerprint,
                   extracted_character_count, chunk_count, quality
            FROM runtime_document_index_documents
            WHERE display_name = ?
            ORDER BY display_name ASC, document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(displayName, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index display-name rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func documentsUnlocked(
        matchingQuality quality: DocumentIngestionQuality,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id, display_name, mime_type, content_fingerprint,
                   extracted_character_count, chunk_count, quality
            FROM runtime_document_index_documents
            WHERE quality = ?
            ORDER BY display_name ASC, document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(quality.rawValue, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index quality-filtered rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func documentsUnlocked(
        matchingContentFingerprint contentFingerprint: String,
        limit: Int,
        database: OpaquePointer
    ) throws -> [RuntimeDocumentIndexDocument] {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id, display_name, mime_type, content_fingerprint,
                   extracted_character_count, chunk_count, quality
            FROM runtime_document_index_documents
            WHERE content_fingerprint = ?
            ORDER BY display_name ASC, document_id ASC
            LIMIT ?
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(contentFingerprint, to: statement, at: 1)
        try Self.bindInt(limit, to: statement, at: 2)

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index fingerprint rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return documents
    }

    private func summaryUnlocked(
        database: OpaquePointer
    ) throws -> RuntimeDocumentIndexSummary {
        let statement = try Self.prepare(
            database,
            """
            SELECT document_id, display_name, mime_type, content_fingerprint,
                   extracted_character_count, chunk_count, quality
            FROM runtime_document_index_documents
            """
        )
        defer { sqlite3_finalize(statement) }

        var documents: [RuntimeDocumentIndexDocument] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not summarize runtime document index rows.")
            }
            documents.append(try Self.document(from: statement))
        }
        return runtimeDocumentIndexSummary(documents)
    }

    private func searchSnapshotUnlocked(
        _ database: OpaquePointer,
        candidateChunkIDs: [String]? = nil
    ) throws -> [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)] {
        let chunkFilter: String
        if let candidateChunkIDs {
            chunkFilter = "WHERE c.chunk_id IN (\(Array(repeating: "?", count: candidateChunkIDs.count).joined(separator: ", ")))"
        } else {
            chunkFilter = ""
        }
        let statement = try Self.prepare(
            database,
            """
            SELECT d.document_id, d.display_name, d.mime_type, d.content_fingerprint,
                   d.extracted_character_count, d.chunk_count, d.quality,
                   c.chunk_id, c.document_id, c.document_display_name, c.document_mime_type,
                   c.chunk_index, c.start_character_offset, c.end_character_offset, c.text
            FROM runtime_document_index_chunks c
            JOIN runtime_document_index_documents d ON d.document_id = c.document_id
            \(chunkFilter)
            ORDER BY d.display_name ASC, c.chunk_index ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        if let candidateChunkIDs {
            for (index, chunkID) in candidateChunkIDs.enumerated() {
                try Self.bindText(chunkID, to: statement, at: Int32(index + 1))
            }
        }

        var snapshot: [(RuntimeDocumentIndexDocument, RuntimeDocumentIndexChunk)] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index search rows.")
            }
            snapshot.append((
                try Self.document(from: statement, offset: 0),
                try Self.chunk(from: statement, offset: 7)
            ))
        }
        return snapshot
    }

    private func ftsCandidateChunkIDsUnlocked(
        _ database: OpaquePointer,
        terms: [String]
    ) throws -> [String] {
        let statement = try Self.prepare(
            database,
            """
            SELECT chunk_id
            FROM runtime_document_index_chunk_fts
            WHERE runtime_document_index_chunk_fts MATCH ?
            ORDER BY rowid ASC
            """
        )
        defer { sqlite3_finalize(statement) }
        try Self.bindText(Self.ftsMatchQuery(for: terms), to: statement, at: 1)

        var chunkIDs: [String] = []
        var seen = Set<String>()
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index FTS candidates.")
            }
            let chunkID = try Self.columnText(statement, 0)
            if seen.insert(chunkID).inserted {
                chunkIDs.append(chunkID)
            }
        }
        return chunkIDs
    }

    private func readChunksUnlocked(
        _ database: OpaquePointer,
        sql: String,
        bind: (OpaquePointer) throws -> Void
    ) throws -> [RuntimeDocumentIndexChunk] {
        let statement = try Self.prepare(database, sql)
        defer { sqlite3_finalize(statement) }
        try bind(statement)

        var chunks: [RuntimeDocumentIndexChunk] = []
        while true {
            let result = sqlite3_step(statement)
            if result == SQLITE_DONE { break }
            guard result == SQLITE_ROW else {
                throw Self.failure(database, "Could not read runtime document index chunks.")
            }
            chunks.append(try Self.chunk(from: statement))
        }
        return chunks
    }

    private func withDatabase<T>(_ body: (OpaquePointer) throws -> T) throws -> T {
        try RuntimeEventLogFileProtection.prepareDirectory(for: databaseURL)
        if FileManager.default.fileExists(atPath: databaseURL.path) {
            try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        var database: OpaquePointer?
        let flags = SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX
        guard sqlite3_open_v2(databaseURL.path, &database, flags, nil) == SQLITE_OK,
              let openedDatabase = database else {
            defer {
                if let database {
                    sqlite3_close(database)
                }
            }
            throw SQLiteRuntimeDocumentIndexStoreError("Could not open runtime document index SQLite store.")
        }
        defer {
            sqlite3_close(openedDatabase)
            try? RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        }
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        try Self.ensureSchema(openedDatabase)
        try RuntimeEventLogFileProtection.secureFile(at: databaseURL)
        return try body(openedDatabase)
    }

    private static func ensureSchema(_ database: OpaquePointer) throws {
        try execute(database, "PRAGMA foreign_keys = ON")
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_index_documents(
                document_id TEXT PRIMARY KEY NOT NULL,
                display_name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                content_fingerprint TEXT NOT NULL,
                extracted_character_count INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL,
                quality TEXT NOT NULL
            )
            """
        )
        try execute(
            database,
            """
            CREATE TABLE IF NOT EXISTS runtime_document_index_chunks(
                chunk_id TEXT PRIMARY KEY NOT NULL,
                document_id TEXT NOT NULL,
                document_display_name TEXT NOT NULL,
                document_mime_type TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_character_offset INTEGER NOT NULL,
                end_character_offset INTEGER NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES runtime_document_index_documents(document_id) ON DELETE CASCADE
            )
            """
        )
        try execute(
            database,
            "CREATE INDEX IF NOT EXISTS idx_runtime_document_index_chunks_document ON runtime_document_index_chunks(document_id, chunk_index)"
        )
        try execute(
            database,
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS runtime_document_index_chunk_fts USING fts5(
                chunk_id UNINDEXED,
                document_id UNINDEXED,
                text,
                tokenize = 'unicode61 remove_diacritics 2'
            )
            """
        )
    }

    private static func document(
        from statement: OpaquePointer,
        offset: Int32 = 0
    ) throws -> RuntimeDocumentIndexDocument {
        let qualityRawValue = try columnText(statement, offset + 6)
        guard let quality = DocumentIngestionQuality(rawValue: qualityRawValue) else {
            throw SQLiteRuntimeDocumentIndexStoreError("Runtime document index SQLite quality is invalid.")
        }
        return RuntimeDocumentIndexDocument(
            id: try columnText(statement, offset),
            displayName: try columnText(statement, offset + 1),
            mimeType: try columnText(statement, offset + 2),
            contentFingerprint: try columnText(statement, offset + 3),
            extractedCharacterCount: columnInt(statement, offset + 4),
            chunkCount: columnInt(statement, offset + 5),
            quality: quality
        )
    }

    private static func chunk(
        from statement: OpaquePointer,
        offset: Int32 = 0
    ) throws -> RuntimeDocumentIndexChunk {
        RuntimeDocumentIndexChunk(
            id: try columnText(statement, offset),
            documentID: try columnText(statement, offset + 1),
            documentDisplayName: try columnText(statement, offset + 2),
            documentMimeType: try columnText(statement, offset + 3),
            chunkIndex: columnInt(statement, offset + 4),
            startCharacterOffset: columnInt(statement, offset + 5),
            endCharacterOffset: columnInt(statement, offset + 6),
            text: try columnText(statement, offset + 7)
        )
    }

    private static func chunkSummary(
        from statement: OpaquePointer,
        offset: Int32 = 0
    ) throws -> RuntimeDocumentIndexChunkSummary {
        RuntimeDocumentIndexChunkSummary(
            documentID: try columnText(statement, offset),
            documentDisplayName: try columnText(statement, offset + 1),
            documentMimeType: try columnText(statement, offset + 2),
            chunkIndex: columnInt(statement, offset + 3),
            startCharacterOffset: columnInt(statement, offset + 4),
            endCharacterOffset: columnInt(statement, offset + 5),
            characterCount: columnInt(statement, offset + 6)
        )
    }

    private static func execute(_ database: OpaquePointer, _ sql: String) throws {
        var error: UnsafeMutablePointer<CChar>?
        if sqlite3_exec(database, sql, nil, nil, &error) != SQLITE_OK {
            let message = error.map { String(cString: $0) } ?? "unknown SQLite error"
            sqlite3_free(error)
            throw SQLiteRuntimeDocumentIndexStoreError(message)
        }
    }

    private static func prepare(_ database: OpaquePointer, _ sql: String) throws -> OpaquePointer {
        var statement: OpaquePointer?
        guard sqlite3_prepare_v2(database, sql, -1, &statement, nil) == SQLITE_OK,
              let statement else {
            throw failure(database, "Could not prepare runtime document index SQLite statement.")
        }
        return statement
    }

    private static func bindText(_ value: String, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_text(statement, index, value, -1, sqliteDocumentIndexTransient) == SQLITE_OK else {
            throw SQLiteRuntimeDocumentIndexStoreError("Could not bind runtime document index SQLite text.")
        }
    }

    private static func bindInt(_ value: Int, to statement: OpaquePointer, at index: Int32) throws {
        guard sqlite3_bind_int64(statement, index, sqlite3_int64(value)) == SQLITE_OK else {
            throw SQLiteRuntimeDocumentIndexStoreError("Could not bind runtime document index SQLite integer.")
        }
    }

    private static func columnText(_ statement: OpaquePointer, _ index: Int32) throws -> String {
        guard let text = sqlite3_column_text(statement, index) else {
            throw SQLiteRuntimeDocumentIndexStoreError("Runtime document index SQLite text column is empty.")
        }
        return String(cString: text)
    }

    private static func columnInt(_ statement: OpaquePointer, _ index: Int32) -> Int {
        Int(sqlite3_column_int64(statement, index))
    }

    private static func stepDone(_ statement: OpaquePointer, database: OpaquePointer) throws {
        guard sqlite3_step(statement) == SQLITE_DONE else {
            throw failure(database, "Could not write runtime document index SQLite row.")
        }
    }

    private static func ftsMatchQuery(for terms: [String]) -> String {
        terms
            .map { term in
                "\"\(term.replacingOccurrences(of: "\"", with: "\"\""))\""
            }
            .joined(separator: " OR ")
    }

    private static func failure(_ database: OpaquePointer, _ fallback: String) -> SQLiteRuntimeDocumentIndexStoreError {
        let message = sqlite3_errmsg(database).map { String(cString: $0) } ?? fallback
        return SQLiteRuntimeDocumentIndexStoreError(message.isEmpty ? fallback : message)
    }
}

extension SQLiteRuntimeDocumentIndexStore: RuntimeDocumentIndexReading {}

private let sqliteDocumentIndexTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

private struct SQLiteRuntimeDocumentIndexStoreError: LocalizedError {
    var message: String

    init(_ message: String) {
        self.message = message
    }

    var errorDescription: String? {
        message
    }
}
