import CryptoKit
import Foundation
import OllamaBackend

struct RuntimeChatCompactionSourceFingerprintValue: Equatable, Sendable {
    var algorithm: String
    var digest: String
    var canonicalByteCount: Int
}

enum RuntimeChatCompactionSourceFingerprinter {
    static let algorithm = "sha256-length-framed-chat-compaction-source-v1"

    static func fingerprint(
        pointer: RuntimeChatCompactionSourcePointer,
        messages: [ChatMessage]
    ) -> RuntimeChatCompactionSourceFingerprintValue {
        var hasher = SHA256()
        var canonicalByteCount = 0

        func append(_ data: Data) {
            hasher.update(data: data)
            canonicalByteCount += data.count
        }

        func appendByte(_ value: UInt8) {
            append(Data([value]))
        }

        func appendCount(_ value: Int) {
            var encoded = UInt64(value).bigEndian
            append(withUnsafeBytes(of: &encoded) { Data($0) })
        }

        func appendString(_ value: String) {
            let data = Data(value.utf8)
            appendCount(data.count)
            append(data)
        }

        func appendOptionalString(_ value: String?) {
            guard let value else {
                appendByte(0)
                return
            }
            appendByte(1)
            appendString(value)
        }

        func appendOptionalCount(_ value: Int?) {
            guard let value else {
                appendByte(0)
                return
            }
            appendByte(1)
            appendCount(value)
        }

        append(Data("AetherLink runtime chat compacted prefix v1\0".utf8))
        appendString(pointer.sourceKind)
        appendString(pointer.sessionID)
        appendString(pointer.requestID)
        appendCount(pointer.startTurn)
        appendCount(pointer.endTurn)
        appendCount(pointer.totalTurns)
        appendCount(pointer.compactedTurnCount)
        appendOptionalCount(pointer.retainedStartTurn)
        appendOptionalCount(pointer.retainedEndTurn)
        appendCount(pointer.retainedTurnCount)
        appendCount(messages.count)
        for message in messages {
            appendString(message.role)
            appendString(message.content)
            appendCount(message.attachments.count)
            for attachment in message.attachments {
                appendString(attachment.type)
                appendString(attachment.mimeType)
                appendOptionalString(attachment.name)
                appendOptionalString(attachment.dataBase64)
                appendOptionalString(attachment.text)
            }
        }

        return RuntimeChatCompactionSourceFingerprintValue(
            algorithm: algorithm,
            digest: hasher.finalize().map { String(format: "%02x", $0) }.joined(),
            canonicalByteCount: canonicalByteCount
        )
    }
}
