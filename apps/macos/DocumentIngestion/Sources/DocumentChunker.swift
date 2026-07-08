import Foundation

public struct DocumentChunkingPolicy: Equatable, Sendable {
    public static let standard = DocumentChunkingPolicy()

    public var maxCharacters: Int
    public var overlapCharacters: Int
    public var minChunkCharacters: Int

    public init(
        maxCharacters: Int = 1_500,
        overlapCharacters: Int = 150,
        minChunkCharacters: Int = 400
    ) {
        self.maxCharacters = maxCharacters
        self.overlapCharacters = overlapCharacters
        self.minChunkCharacters = minChunkCharacters
    }
}

public enum DocumentChunkingError: Error, Equatable, Sendable {
    case invalidPolicy(String)
}

public struct DocumentChunk: Equatable, Sendable {
    public var documentFileName: String
    public var documentMimeType: String
    public var index: Int
    public var startCharacterOffset: Int
    public var endCharacterOffset: Int
    public var text: String

    public init(
        documentFileName: String,
        documentMimeType: String,
        index: Int,
        startCharacterOffset: Int,
        endCharacterOffset: Int,
        text: String
    ) {
        self.documentFileName = documentFileName
        self.documentMimeType = documentMimeType
        self.index = index
        self.startCharacterOffset = startCharacterOffset
        self.endCharacterOffset = endCharacterOffset
        self.text = text
    }
}

public final class DocumentChunker: Sendable {
    private let policy: DocumentChunkingPolicy

    public init(policy: DocumentChunkingPolicy = .standard) {
        self.policy = policy
    }

    public func chunks(from document: ExtractedDocument) throws -> [DocumentChunk] {
        try validatePolicy()
        let sourceText = document.text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !sourceText.isEmpty else { return [] }

        let characters = Array(sourceText)
        var pendingChunks: [(start: Int, end: Int, text: String)] = []
        var start = nextNonWhitespaceOffset(in: characters, from: 0)

        while start < characters.count {
            let proposedEnd = proposedChunkEnd(in: characters, start: start)
            let trimmedStart = nextNonWhitespaceOffset(in: characters, from: start)
            let trimmedEnd = previousNonWhitespaceOffset(in: characters, before: proposedEnd)

            if trimmedStart < trimmedEnd {
                pendingChunks.append((
                    start: trimmedStart,
                    end: trimmedEnd,
                    text: String(characters[trimmedStart..<trimmedEnd])
                ))
            }

            guard proposedEnd < characters.count else { break }
            let overlappedStart = max(proposedEnd - policy.overlapCharacters, start + 1)
            start = nextNonWhitespaceOffset(in: characters, from: overlappedStart)
        }

        return pendingChunks.enumerated().map { index, pending in
            DocumentChunk(
                documentFileName: document.fileName,
                documentMimeType: document.mimeType,
                index: index,
                startCharacterOffset: pending.start,
                endCharacterOffset: pending.end,
                text: pending.text
            )
        }
    }

    private func validatePolicy() throws {
        guard policy.maxCharacters > 0 else {
            throw DocumentChunkingError.invalidPolicy("maxCharacters must be greater than zero")
        }
        guard policy.overlapCharacters >= 0 else {
            throw DocumentChunkingError.invalidPolicy("overlapCharacters must not be negative")
        }
        guard policy.overlapCharacters < policy.maxCharacters else {
            throw DocumentChunkingError.invalidPolicy("overlapCharacters must be less than maxCharacters")
        }
        guard policy.minChunkCharacters > 0 else {
            throw DocumentChunkingError.invalidPolicy("minChunkCharacters must be greater than zero")
        }
        guard policy.minChunkCharacters <= policy.maxCharacters else {
            throw DocumentChunkingError.invalidPolicy("minChunkCharacters must be less than or equal to maxCharacters")
        }
    }

    private func proposedChunkEnd(in characters: [Character], start: Int) -> Int {
        let hardEnd = min(start + policy.maxCharacters, characters.count)
        guard hardEnd < characters.count else { return hardEnd }

        let earliestBoundary = min(start + policy.minChunkCharacters, hardEnd)
        var lastSentenceBoundary: Int?
        var lastWordBoundary: Int?

        var offset = start
        while offset < hardEnd {
            let character = characters[offset]
            if offset >= earliestBoundary {
                if isWhitespace(character) {
                    lastWordBoundary = offset
                }
                if isSentenceTerminal(character),
                   offset + 1 < characters.count,
                   isWhitespace(characters[offset + 1]) {
                    lastSentenceBoundary = offset + 1
                }
            }
            offset += 1
        }

        return lastSentenceBoundary ?? lastWordBoundary ?? hardEnd
    }
}

private func nextNonWhitespaceOffset(in characters: [Character], from start: Int) -> Int {
    var offset = max(0, start)
    while offset < characters.count, isWhitespace(characters[offset]) {
        offset += 1
    }
    return offset
}

private func previousNonWhitespaceOffset(in characters: [Character], before end: Int) -> Int {
    var offset = min(end, characters.count)
    while offset > 0, isWhitespace(characters[offset - 1]) {
        offset -= 1
    }
    return offset
}

private func isWhitespace(_ character: Character) -> Bool {
    character.unicodeScalars.allSatisfy { CharacterSet.whitespacesAndNewlines.contains($0) }
}

private func isSentenceTerminal(_ character: Character) -> Bool {
    character == "." || character == "!" || character == "?" || character == "。" || character == "！" || character == "？"
}
