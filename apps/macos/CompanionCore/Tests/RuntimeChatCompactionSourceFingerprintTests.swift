import XCTest
import OllamaBackend
@testable import CompanionCore

final class RuntimeChatCompactionSourceFingerprintTests: XCTestCase {
    func testCanonicalFingerprintMatchesGoldenMultilingualAttachmentVector() {
        let pointer = makePointer()
        let messages = [
            ChatMessage(
                role: "user",
                content: "Hello\n안녕 🌏",
                attachments: [
                    ChatAttachment(
                        type: "document",
                        mimeType: "text/plain",
                        text: ""
                    )
                ]
            ),
            ChatMessage(role: "assistant", content: "Cafe\u{301}"),
        ]

        let fingerprint = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: messages
        )

        XCTAssertEqual(fingerprint.algorithm, "sha256-length-framed-chat-compaction-source-v1")
        XCTAssertEqual(fingerprint.canonicalByteCount, 319)
        XCTAssertEqual(
            fingerprint.digest,
            "85f22817816f4cd782f7aad0830520e2aadca289c15b037dc64c462825234d8e"
        )
    }

    func testFingerprintDistinguishesPointerIdentityUnicodeAndNilFromEmpty() {
        let pointer = makePointer()
        let decomposed = ChatMessage(
            role: "user",
            content: "Cafe\u{301}",
            attachments: [ChatAttachment(type: "document", mimeType: "text/plain")]
        )
        let baseline = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: [decomposed]
        )

        var changedPointer = pointer
        changedPointer.requestID = "request-2"
        let changedIdentity = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: changedPointer,
            messages: [decomposed]
        )
        let composed = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: [ChatMessage(
                role: "user",
                content: "Café",
                attachments: [ChatAttachment(type: "document", mimeType: "text/plain")]
            )]
        )
        let emptyName = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: [ChatMessage(
                role: "user",
                content: "Cafe\u{301}",
                attachments: [ChatAttachment(type: "document", mimeType: "text/plain", name: "")]
            )]
        )

        XCTAssertNotEqual(baseline.digest, changedIdentity.digest)
        XCTAssertNotEqual(baseline.digest, composed.digest)
        XCTAssertNotEqual(baseline.digest, emptyName.digest)
    }

    func testFingerprintPreservesMessageAndAttachmentOrder() {
        let pointer = makePointer()
        let first = ChatMessage(
            role: "user",
            content: "first",
            attachments: [
                ChatAttachment(type: "document", mimeType: "text/plain", name: "a"),
                ChatAttachment(type: "document", mimeType: "text/plain", name: "b"),
            ]
        )
        let second = ChatMessage(role: "assistant", content: "second")
        let baseline = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: [first, second]
        )
        var reversedAttachments = first
        reversedAttachments.attachments.reverse()
        let attachmentOrder = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: [reversedAttachments, second]
        )
        let messageOrder = RuntimeChatCompactionSourceFingerprinter.fingerprint(
            pointer: pointer,
            messages: [second, first]
        )

        XCTAssertNotEqual(baseline.digest, attachmentOrder.digest)
        XCTAssertNotEqual(baseline.digest, messageOrder.digest)
    }

    private func makePointer() -> RuntimeChatCompactionSourcePointer {
        RuntimeChatCompactionSourcePointer(
            sessionID: "session-한글",
            requestID: "request-1",
            startTurn: 1,
            endTurn: 2,
            totalTurns: 3,
            compactedTurnCount: 2,
            retainedStartTurn: 3,
            retainedEndTurn: 3,
            retainedTurnCount: 1
        )
    }
}
