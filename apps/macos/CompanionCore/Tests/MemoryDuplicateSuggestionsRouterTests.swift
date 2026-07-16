import enum BridgeProtocol.JSONValue
import enum BridgeProtocol.MessageType
import struct BridgeProtocol.ProtocolEnvelope
import struct BridgeProtocol.TransportSecurityContext
@testable import CompanionCore
import CryptoKit
import Dispatch
import Foundation
import OllamaBackend
import Transport
import TrustedDevices
import XCTest

final class MemoryDuplicateSuggestionsRouterTests: XCTestCase {
    private let capability = "memory.duplicate_suggestions.v1"

    func testRequiresAuthenticationAndNegotiatedCapability() async throws {
        let fixture = try await makeFixture()
        let sink = DuplicateSuggestionRecordingSink()

        fixture.router.handle(ProtocolEnvelope(
            type: MessageType.memoryDuplicateSuggestionsList,
            requestID: "unauthenticated"
        ), sink: sink)
        var messages = try await sink.waitForMessages(count: 1)
        XCTAssertEqual(messages.last?.payload["code"], .string("authentication_required"))

        try await authenticate(
            router: fixture.router,
            sink: sink,
            deviceID: fixture.ownerA,
            privateKey: fixture.ownerAKey,
            capabilities: [],
            existingMessageCount: messages.count
        )
        messages = try await sink.waitForMessages(count: 3)
        fixture.router.handle(ProtocolEnvelope(
            type: MessageType.memoryDuplicateSuggestionsList,
            requestID: "missing-capability"
        ), sink: sink)
        messages = try await sink.waitForMessages(count: 4)
        XCTAssertEqual(messages.last?.payload["code"], .string("unsupported_operation"))

        try await authenticate(
            router: fixture.router,
            sink: sink,
            deviceID: fixture.ownerA,
            privateKey: fixture.ownerAKey,
            capabilities: [capability.uppercased()],
            existingMessageCount: messages.count
        )
        messages = try await sink.waitForMessages(count: 6)
        fixture.router.handle(ProtocolEnvelope(
            type: MessageType.memoryDuplicateSuggestionsList,
            requestID: "negotiated"
        ), sink: sink)
        messages = try await sink.waitForMessages(count: 7)

        XCTAssertEqual(MessageType.memoryDuplicateSuggestionsList, "memory.duplicate_suggestions.list")
        XCTAssertEqual(messages.last?.type, MessageType.memoryDuplicateSuggestionsList)
    }

    func testOwnerScopedExactResponseRejectsFieldsAndDoesNotMutateOrLeak() async throws {
        let fixture = try await makeFixture()
        let sinkA = DuplicateSuggestionRecordingSink()
        let sinkB = DuplicateSuggestionRecordingSink()
        try await authenticate(
            router: fixture.router,
            sink: sinkA,
            deviceID: fixture.ownerA,
            privateKey: fixture.ownerAKey,
            capabilities: [capability],
            existingMessageCount: 0
        )
        try await authenticate(
            router: fixture.router,
            sink: sinkB,
            deviceID: fixture.ownerB,
            privateKey: fixture.ownerBKey,
            capabilities: [capability],
            existingMessageCount: 0
        )
        let before = try Data(contentsOf: fixture.memoryFileURL)

        fixture.router.handle(ProtocolEnvelope(
            type: MessageType.memoryDuplicateSuggestionsList,
            requestID: "unsupported-field",
            payload: ["include_content": .bool(true)]
        ), sink: sinkA)
        var messagesA = try await sinkA.waitForMessages(count: 3)
        XCTAssertEqual(messagesA.last?.payload["code"], .string("invalid_payload"))

        fixture.router.handle(ProtocolEnvelope(
            type: MessageType.memoryDuplicateSuggestionsList,
            requestID: "owner-a"
        ), sink: sinkA)
        messagesA = try await sinkA.waitForMessages(count: 4)
        let ownerAResponse = try XCTUnwrap(messagesA.last)
        assertResponse(ownerAResponse, expectedEntryIDs: ["a-disabled", "a-enabled"])

        fixture.router.handle(ProtocolEnvelope(
            type: MessageType.memoryDuplicateSuggestionsList,
            requestID: "owner-b"
        ), sink: sinkB)
        let messagesB = try await sinkB.waitForMessages(count: 3)
        let ownerBResponse = try XCTUnwrap(messagesB.last)
        assertResponse(ownerBResponse, expectedEntryIDs: ["b-one", "b-two"])

        XCTAssertEqual(try Data(contentsOf: fixture.memoryFileURL), before)
        let serializedPayloads = String(describing: [ownerAResponse.payload, ownerBResponse.payload])
        for forbidden in [
            "OWNER_A_SECRET_CONTENT",
            "OWNER_B_SECRET_CONTENT",
            "draft-owner-a",
            "source excerpt",
            "content_hash",
            "source",
            "model"
        ] {
            XCTAssertFalse(serializedPayloads.contains(forbidden), "Leaked forbidden response data: \(forbidden)")
        }
    }

    func testTrustRemovalAndKeyReplacementDuringBlockedScanFailClosed() async throws {
        for trustChange in ["remove", "replace"] {
            let directory = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString, isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            defer { try? FileManager.default.removeItem(at: directory) }
            let trustedDeviceStore = TrustedDeviceStore(
                fileURL: directory.appendingPathComponent("trusted-devices.json")
            )
            let owner = "owner-\(trustChange)"
            let key = P256.Signing.PrivateKey()
            try await trustedDeviceStore.trust(TrustedDevice(
                id: owner,
                name: "Owner",
                publicKeyBase64: key.publicKey.derRepresentation.base64EncodedString()
            ))
            let memoryStore = BlockingDuplicateSuggestionMemoryStore(entries: [
                duplicateSuggestionEntry(id: "one", content: "same", updatedAt: 2),
                duplicateSuggestionEntry(id: "two", content: "same", updatedAt: 1)
            ])
            let router = LocalRuntimeMessageRouter(
                backend: OllamaBackend(),
                requiresAuthentication: true,
                trustedDeviceStore: trustedDeviceStore,
                chatEventStore: NullRuntimeChatEventStore(),
                memoryStore: memoryStore,
                documentIndexStore: RuntimeDocumentIndexStore()
            )
            let sink = DuplicateSuggestionRecordingSink()
            try await authenticate(
                router: router,
                sink: sink,
                deviceID: owner,
                privateKey: key,
                capabilities: [capability],
                existingMessageCount: 0
            )

            router.handle(ProtocolEnvelope(
                type: MessageType.memoryDuplicateSuggestionsList,
                requestID: "scan-\(trustChange)"
            ), sink: sink)
            XCTAssertTrue(memoryStore.waitUntilScanStarted())
            if trustChange == "remove" {
                try await trustedDeviceStore.remove(deviceID: owner)
            } else {
                let replacementKey = P256.Signing.PrivateKey()
                try await trustedDeviceStore.trust(TrustedDevice(
                    id: owner,
                    name: "Replacement",
                    publicKeyBase64: replacementKey.publicKey.derRepresentation.base64EncodedString()
                ))
            }
            memoryStore.resumeScan()

            var messages = try await sink.waitForMessages(count: 3)
            XCTAssertEqual(messages.last?.type, MessageType.error)
            XCTAssertEqual(messages.last?.requestID, "scan-\(trustChange)")
            XCTAssertEqual(messages.last?.payload["code"], .string("pairing_required"))
            XCTAssertFalse(messages.contains { message in
                message.requestID == "scan-\(trustChange)"
                    && message.type == MessageType.memoryDuplicateSuggestionsList
            })

            router.handle(ProtocolEnvelope(
                type: MessageType.memoryDuplicateSuggestionsList,
                requestID: "after-\(trustChange)"
            ), sink: sink)
            messages = try await sink.waitForMessages(count: 4)
            XCTAssertEqual(messages.last?.payload["code"], .string("authentication_required"))
        }
    }

    func testIdenticalReauthenticationDuringBlockedScanRejectsPreEpochResult() async throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let trustedDeviceStore = TrustedDeviceStore(
            fileURL: directory.appendingPathComponent("trusted-devices.json")
        )
        let owner = "owner-reauthenticated"
        let key = P256.Signing.PrivateKey()
        try await trustedDeviceStore.trust(TrustedDevice(
            id: owner,
            name: "Owner",
            publicKeyBase64: key.publicKey.derRepresentation.base64EncodedString()
        ))
        let memoryStore = BlockingDuplicateSuggestionMemoryStore(entries: [
            duplicateSuggestionEntry(id: "one", content: "same", updatedAt: 2),
            duplicateSuggestionEntry(id: "two", content: "same", updatedAt: 1)
        ])
        let router = LocalRuntimeMessageRouter(
            backend: OllamaBackend(),
            requiresAuthentication: true,
            trustedDeviceStore: trustedDeviceStore,
            chatEventStore: NullRuntimeChatEventStore(),
            memoryStore: memoryStore,
            documentIndexStore: RuntimeDocumentIndexStore()
        )
        let sink = DuplicateSuggestionRecordingSink()
        try await authenticate(
            router: router,
            sink: sink,
            deviceID: owner,
            privateKey: key,
            capabilities: [capability],
            existingMessageCount: 0
        )

        router.handle(ProtocolEnvelope(
            type: MessageType.memoryDuplicateSuggestionsList,
            requestID: "scan-before-identical-reauth"
        ), sink: sink)
        XCTAssertTrue(memoryStore.waitUntilScanStarted())
        try await authenticate(
            router: router,
            sink: sink,
            deviceID: owner,
            privateKey: key,
            capabilities: [capability],
            existingMessageCount: 2
        )
        memoryStore.resumeScan()

        var messages = try await sink.waitForMessages(count: 5)
        XCTAssertEqual(messages.last?.type, MessageType.error)
        XCTAssertEqual(messages.last?.requestID, "scan-before-identical-reauth")
        XCTAssertEqual(messages.last?.payload["code"], .string("authentication_required"))
        XCTAssertFalse(messages.contains { message in
            message.requestID == "scan-before-identical-reauth"
                && message.type == MessageType.memoryDuplicateSuggestionsList
        })

        router.handle(ProtocolEnvelope(
            type: MessageType.runtimeHealth,
            requestID: "health-after-identical-reauth"
        ), sink: sink)
        messages = try await sink.waitForMessages(count: 6)
        XCTAssertEqual(messages.last?.type, MessageType.runtimeHealth)
    }

    private func duplicateSuggestionEntry(
        id: String,
        content: String,
        updatedAt: TimeInterval
    ) -> RuntimeMemoryEntry {
        RuntimeMemoryEntry(
            id: id,
            content: content,
            enabled: true,
            createdAt: Date(timeIntervalSince1970: 0),
            updatedAt: Date(timeIntervalSince1970: updatedAt),
            source: nil
        )
    }

    private func assertResponse(
        _ response: ProtocolEnvelope,
        expectedEntryIDs: [String],
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertEqual(response.type, MessageType.memoryDuplicateSuggestionsList, file: file, line: line)
        XCTAssertEqual(Set(response.payload.keys), ["groups", "scanned_count", "truncated"], file: file, line: line)
        XCTAssertEqual(response.payload["scanned_count"], .number(2), file: file, line: line)
        XCTAssertEqual(response.payload["truncated"], .bool(false), file: file, line: line)
        guard case .array(let groups)? = response.payload["groups"],
              case .object(let group)? = groups.first else {
            XCTFail("Expected one duplicate suggestion group", file: file, line: line)
            return
        }
        XCTAssertEqual(groups.count, 1, file: file, line: line)
        XCTAssertEqual(Set(group.keys), ["entry_ids"], file: file, line: line)
        XCTAssertEqual(
            group["entry_ids"],
            .array(expectedEntryIDs.map(JSONValue.string)),
            file: file,
            line: line
        )
    }

    private func makeFixture() async throws -> DuplicateSuggestionFixture {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let trustedDeviceFileURL = directory.appendingPathComponent("trusted-devices.json")
        let memoryFileURL = directory.appendingPathComponent("memory.jsonl")
        let trustedDeviceStore = TrustedDeviceStore(fileURL: trustedDeviceFileURL)
        let ownerAKey = P256.Signing.PrivateKey()
        let ownerBKey = P256.Signing.PrivateKey()
        let ownerA = "owner-a"
        let ownerB = "owner-b"
        try await trustedDeviceStore.trust(TrustedDevice(
            id: ownerA,
            name: "Owner A",
            publicKeyBase64: ownerAKey.publicKey.derRepresentation.base64EncodedString()
        ))
        try await trustedDeviceStore.trust(TrustedDevice(
            id: ownerB,
            name: "Owner B",
            publicKeyBase64: ownerBKey.publicKey.derRepresentation.base64EncodedString()
        ))

        let memoryStore = JSONLRuntimeMemoryStore(fileURL: memoryFileURL)
        let source = RuntimeMemoryEntrySource(
            kind: "test-source",
            draftID: "draft-owner-a",
            summaryMethod: "test",
            session: RuntimeMemoryEntrySourceSession(
                sessionID: "session-a",
                title: "Owner A source",
                model: "secret-model",
                lastActivityAt: Date(timeIntervalSince1970: 1),
                messageCount: 1,
                inactiveSeconds: 1
            ),
            sourceMessageCount: 1,
            sourceRange: "1",
            sourcePointers: [RuntimeMemoryEntrySourcePointer(
                sessionID: "session-a",
                messageIndex: 0,
                role: "user",
                createdAt: nil,
                excerpt: "source excerpt"
            )]
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: ownerA,
            id: "a-enabled",
            content: "OWNER_A_SECRET_CONTENT",
            enabled: true,
            source: source,
            timestamp: Date(timeIntervalSince1970: 1)
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: ownerA,
            id: "a-disabled",
            content: "OWNER_A_SECRET_CONTENT",
            enabled: false,
            source: nil,
            timestamp: Date(timeIntervalSince1970: 2)
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: ownerB,
            id: "b-two",
            content: "OWNER_B_SECRET_CONTENT",
            enabled: true,
            source: nil,
            timestamp: Date(timeIntervalSince1970: 3)
        )
        _ = try memoryStore.upsert(
            ownerDeviceID: ownerB,
            id: "b-one",
            content: "OWNER_B_SECRET_CONTENT",
            enabled: true,
            source: nil,
            timestamp: Date(timeIntervalSince1970: 4)
        )

        let router = LocalRuntimeMessageRouter(
            backend: OllamaBackend(),
            requiresAuthentication: true,
            trustedDeviceStore: trustedDeviceStore,
            chatEventStore: NullRuntimeChatEventStore(),
            memoryStore: memoryStore,
            documentIndexStore: RuntimeDocumentIndexStore()
        )
        return DuplicateSuggestionFixture(
            router: router,
            memoryFileURL: memoryFileURL,
            ownerA: ownerA,
            ownerB: ownerB,
            ownerAKey: ownerAKey,
            ownerBKey: ownerBKey
        )
    }

    private func authenticate(
        router: LocalRuntimeMessageRouter,
        sink: DuplicateSuggestionRecordingSink,
        deviceID: String,
        privateKey: P256.Signing.PrivateKey,
        capabilities: [String],
        existingMessageCount: Int
    ) async throws {
        var helloPayload: [String: JSONValue] = ["device_id": .string(deviceID)]
        if !capabilities.isEmpty {
            helloPayload["client_capabilities"] = .array(capabilities.map(JSONValue.string))
        }
        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-\(UUID().uuidString)",
            payload: helloPayload
        ), sink: sink)
        let challenge = try await sink.waitForMessages(count: existingMessageCount + 1).last
        guard case .string(let nonce)? = challenge?.payload["nonce"] else {
            XCTFail("Expected authentication challenge nonce")
            return
        }
        let message = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
            deviceID: deviceID,
            nonce: nonce
        )
        let signature = try privateKey
            .signature(for: SHA256.hash(data: Data(message.utf8)))
            .derRepresentation
            .base64EncodedString()
        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-\(UUID().uuidString)",
            payload: [
                "device_id": .string(deviceID),
                "nonce": .string(nonce),
                "signature": .string(signature)
            ]
        ), sink: sink)
        let messages = try await sink.waitForMessages(count: existingMessageCount + 2)
        XCTAssertEqual(messages.last?.type, MessageType.authResponse)
        XCTAssertEqual(messages.last?.payload["accepted"], .bool(true))
    }
}

private struct DuplicateSuggestionFixture {
    var router: LocalRuntimeMessageRouter
    var memoryFileURL: URL
    var ownerA: String
    var ownerB: String
    var ownerAKey: P256.Signing.PrivateKey
    var ownerBKey: P256.Signing.PrivateKey
}

private final class DuplicateSuggestionRecordingSink: RuntimeMessageSink, @unchecked Sendable {
    let connectionID = UUID()
    let transportSecurityContext: TransportSecurityContext? = nil
    private let lock = NSLock()
    private var messages: [ProtocolEnvelope] = []

    func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result {
        try operation(nil)
    }

    func send(_ envelope: ProtocolEnvelope) {
        lock.withLock {
            messages.append(envelope)
        }
    }

    func close() {}

    func waitForMessages(count: Int, timeout: TimeInterval = 2) async throws -> [ProtocolEnvelope] {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            let snapshot = lock.withLock { messages }
            if snapshot.count >= count { return snapshot }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        return lock.withLock { messages }
    }
}

private final class BlockingDuplicateSuggestionMemoryStore: RuntimeMemoryStore, @unchecked Sendable {
    private let entries: [RuntimeMemoryEntry]
    private let started = DispatchSemaphore(value: 0)
    private let release = DispatchSemaphore(value: 0)

    init(entries: [RuntimeMemoryEntry]) {
        self.entries = entries
    }

    func exactDuplicateSuggestions(ownerDeviceID: String?) throws -> RuntimeMemoryDuplicateSuggestions {
        started.signal()
        release.wait()
        return try RuntimeMemoryExactDuplicateSuggester.suggestions(from: entries)
    }

    func waitUntilScanStarted(timeout: TimeInterval = 2) -> Bool {
        started.wait(timeout: .now() + timeout) == .success
    }

    func resumeScan() {
        release.signal()
    }

    func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry] { entries }
    func listAll() throws -> [RuntimeMemoryEntry] { entries }

    func upsert(
        ownerDeviceID: String?,
        id: String?,
        content: String,
        enabled: Bool?,
        source: RuntimeMemoryEntrySource?,
        timestamp: Date
    ) throws -> RuntimeMemoryEntry {
        RuntimeMemoryEntry(
            id: id ?? UUID().uuidString,
            content: content,
            enabled: enabled ?? true,
            createdAt: timestamp,
            updatedAt: timestamp,
            source: source
        )
    }

    func delete(ownerDeviceID: String?, id: String, timestamp: Date) throws -> RuntimeMemoryDeleteResult {
        RuntimeMemoryDeleteResult(id: id, deletedAt: timestamp)
    }

    func dismissedMemorySummaryDraftIDs(ownerDeviceID: String?) throws -> Set<String> { [] }

    func dismissMemorySummaryDraft(
        ownerDeviceID: String?,
        draftID: String,
        timestamp: Date
    ) throws -> RuntimeMemorySummaryDraftDismissResult {
        RuntimeMemorySummaryDraftDismissResult(draftID: draftID, dismissedAt: timestamp)
    }
}
