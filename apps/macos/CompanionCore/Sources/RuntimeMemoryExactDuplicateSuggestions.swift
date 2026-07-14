import Foundation

public struct RuntimeMemoryDuplicateSuggestionGroup: Equatable, Sendable {
    public var entryIDs: [String]

    public init(entryIDs: [String]) {
        self.entryIDs = entryIDs
    }
}

public struct RuntimeMemoryDuplicateSuggestions: Equatable, Sendable {
    public var groups: [RuntimeMemoryDuplicateSuggestionGroup]
    public var scannedCount: Int
    public var truncated: Bool

    public init(
        groups: [RuntimeMemoryDuplicateSuggestionGroup],
        scannedCount: Int,
        truncated: Bool
    ) {
        self.groups = groups
        self.scannedCount = scannedCount
        self.truncated = truncated
    }
}

public enum RuntimeMemoryExactDuplicateSuggester {
    public static let candidateLimit = 200
    public static let maximumSourceEventLogByteCount = 8 * 1_024 * 1_024
    public static let maximumCandidateContentUTF8ByteCount = 1 * 1_024 * 1_024
    public static let maximumResponseEntryIDUTF8ByteCount = 128 * 1_024

    public static func suggestions(
        from entries: [RuntimeMemoryEntry]
    ) throws -> RuntimeMemoryDuplicateSuggestions {
        let orderedEntries = entries.sorted { lhs, rhs in
            if lhs.updatedAt != rhs.updatedAt {
                return lhs.updatedAt > rhs.updatedAt
            }
            return utf8LexicographicallyPrecedes(lhs.id, rhs.id)
        }

        var seenEntryIDs = Set<String>()
        var candidates: [RuntimeMemoryEntry] = []
        var candidateContentUTF8ByteCount = 0
        var truncated = false
        for entry in orderedEntries {
            guard seenEntryIDs.insert(entry.id).inserted else { continue }
            guard candidates.count < candidateLimit else {
                truncated = true
                break
            }
            let (nextContentByteCount, overflow) = candidateContentUTF8ByteCount
                .addingReportingOverflow(entry.content.utf8.count)
            guard !overflow,
                  nextContentByteCount <= maximumCandidateContentUTF8ByteCount else {
                throw RuntimeMemoryStoreError.duplicateSuggestionResourceLimitExceeded
            }
            candidateContentUTF8ByteCount = nextContentByteCount
            candidates.append(entry)
        }

        var entryIDsByStoredContent: [Data: [String]] = [:]
        for entry in candidates {
            entryIDsByStoredContent[Data(entry.content.utf8), default: []].append(entry.id)
        }

        let groups = entryIDsByStoredContent.values.compactMap { entryIDs -> RuntimeMemoryDuplicateSuggestionGroup? in
            let sortedEntryIDs = entryIDs.sorted(by: utf8LexicographicallyPrecedes)
            guard sortedEntryIDs.count >= 2 else { return nil }
            return RuntimeMemoryDuplicateSuggestionGroup(entryIDs: sortedEntryIDs)
        }.sorted { lhs, rhs in
            utf8LexicographicallyPrecedes(lhs.entryIDs[0], rhs.entryIDs[0])
        }

        let responseEntryIDUTF8ByteCount = groups
            .lazy
            .flatMap(\.entryIDs)
            .reduce(into: 0) { byteCount, entryID in
                let (nextByteCount, overflow) = byteCount.addingReportingOverflow(entryID.utf8.count)
                byteCount = overflow ? Int.max : nextByteCount
            }
        guard responseEntryIDUTF8ByteCount <= maximumResponseEntryIDUTF8ByteCount else {
            throw RuntimeMemoryStoreError.duplicateSuggestionResourceLimitExceeded
        }

        return RuntimeMemoryDuplicateSuggestions(
            groups: groups,
            scannedCount: candidates.count,
            truncated: truncated
        )
    }

    public static func utf8LexicographicallyPrecedes(_ lhs: String, _ rhs: String) -> Bool {
        lhs.utf8.lexicographicallyPrecedes(rhs.utf8)
    }
}
