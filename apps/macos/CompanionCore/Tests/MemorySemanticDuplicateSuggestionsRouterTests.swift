import enum BridgeProtocol.JSONValue
import enum BridgeProtocol.MessageType
import struct BridgeProtocol.ProtocolEnvelope
import struct BridgeProtocol.TransportSecurityContext
@testable import CompanionCore
import CryptoKit
import Foundation
import OllamaBackend
import Transport
import TrustedDevices
import XCTest

final class MemorySemanticDuplicateSuggestionsRouterTests: XCTestCase {
    private let capability = "memory.semantic_duplicate_suggestions.v1"
    private let modelID = "ollama:nomic-embed-text"

    func testRequiresAuthenticationAndNegotiatedCapability() async throws {
        let fixture = try await makeFixture(entries: semanticEntries())
        let sink = SemanticDuplicateRecordingSink()

        fixture.router.handle(request(id: "unauthenticated"), sink: sink)
        var messages = try await sink.waitForMessages(count: 1)
        XCTAssertEqual(messages.last?.payload["code"], .string("authentication_required"))

        try await authenticate(
            router: fixture.router,
            sink: sink,
            fixture: fixture,
            capabilities: [],
            existingMessageCount: messages.count
        )
        fixture.router.handle(request(id: "missing-capability"), sink: sink)
        messages = try await sink.waitForMessages(count: 4)
        XCTAssertEqual(messages.last?.payload["code"], .string("unsupported_operation"))

        try await authenticate(
            router: fixture.router,
            sink: sink,
            fixture: fixture,
            capabilities: [capability],
            existingMessageCount: messages.count
        )
        fixture.router.handle(request(id: "negotiated"), sink: sink)
        messages = try await sink.waitForMessages(count: 7)

        XCTAssertEqual(
            MessageType.memorySemanticDuplicateSuggestionsList,
            "memory.semantic_duplicate_suggestions.list"
        )
        XCTAssertEqual(messages.last?.type, MessageType.memorySemanticDuplicateSuggestionsList)
    }

    func testClosedRequestRejectsUnknownAndConfusedFieldsAndInvalidModelIDs() async throws {
        let fixture = try await makeFixture(entries: semanticEntries())
        let sink = SemanticDuplicateRecordingSink()
        try await authenticate(router: fixture.router, sink: sink, fixture: fixture)

        let invalidPayloads: [(String, [String: JSONValue])] = [
            ("unknown", validPayload().merging(["include_content": .bool(true)]) { _, new in new }),
            ("missing-model", ["minimum_similarity_basis_points": .integer(8_000)]),
            ("blank-model", validPayload(modelID: " \n ")),
            ("unqualified-model", validPayload(modelID: "nomic-embed-text")),
            ("overlong-model", validPayload(modelID: "ollama:" + String(repeating: "x", count: 257))),
            ("object-model", validPayload(modelValue: .object(["id": .string(modelID)]))),
            ("missing-threshold", ["embedding_model_id": .string(modelID)]),
            ("float-threshold", validPayload(threshold: .number(8_000.5))),
            ("bool-threshold", validPayload(threshold: .bool(true))),
            ("string-threshold", validPayload(threshold: .string("8000"))),
            ("threshold-low", validPayload(threshold: .integer(7_999))),
            ("threshold-high", validPayload(threshold: .integer(10_001))),
        ]

        var expectedMessageCount = 2
        for (name, payload) in invalidPayloads {
            fixture.router.handle(ProtocolEnvelope(
                type: MessageType.memorySemanticDuplicateSuggestionsList,
                requestID: name,
                payload: payload
            ), sink: sink)
            expectedMessageCount += 1
            let messages = try await sink.waitForMessages(count: expectedMessageCount)
            XCTAssertEqual(messages.last?.requestID, name)
            XCTAssertEqual(messages.last?.type, MessageType.error)
            XCTAssertEqual(messages.last?.payload["code"], .string("invalid_payload"), name)
        }
        XCTAssertTrue(fixture.backend.embeddingRequests.isEmpty)
    }

    func testValidResponseIsDeterministicMinimalAndExcludesExactContentPair() async throws {
        let entries = semanticEntries()
        let backend = SemanticDuplicateBackend(
            models: [embeddingModel(revision: "valid-response")],
            embeddingResponder: { request, _ in
                EmbeddingResult(
                    model: request.model,
                    embeddings: request.texts.map { text in
                        switch text {
                        case "PRIVATE_ALPHA", "PRIVATE_BETA": return [1, 0]
                        case "PRIVATE_GAMMA": return [0.8, 0.6]
                        case "EXACT_PRIVATE_CONTENT": return [0, 1]
                        default: return [1, 0]
                        }
                    }
                )
            }
        )
        let fixture = try await makeFixture(entries: entries, backend: backend)
        let sink = SemanticDuplicateRecordingSink()
        try await authenticate(router: fixture.router, sink: sink, fixture: fixture)
        let before = fixture.memoryStore.entriesSnapshot

        fixture.router.handle(request(id: "valid", threshold: 8_000), sink: sink)
        let messages = try await sink.waitForMessages(count: 3)
        let response = try XCTUnwrap(messages.last)

        XCTAssertEqual(response.type, MessageType.memorySemanticDuplicateSuggestionsList)
        XCTAssertEqual(
            Set(response.payload.keys),
            ["pairs", "scanned_count", "omitted_count", "truncated"]
        )
        XCTAssertEqual(response.payload["scanned_count"], .number(5))
        XCTAssertEqual(response.payload["omitted_count"], .number(0))
        XCTAssertEqual(response.payload["truncated"], .bool(false))
        guard case .array(let pairs)? = response.payload["pairs"] else {
            XCTFail("Expected semantic duplicate pairs")
            return
        }
        XCTAssertEqual(pairs, [
            pair(["a", "b"], score: 10_000),
            pair(["a", "c"], score: 8_000),
            pair(["b", "c"], score: 8_000),
        ])
        XCTAssertFalse(pairs.contains(pair(["exact-a", "exact-b"], score: 10_000)))
        for value in pairs {
            guard case .object(let pairPayload) = value else {
                XCTFail("Expected pair object")
                return
            }
            XCTAssertEqual(Set(pairPayload.keys), ["entry_ids", "similarity_basis_points"])
        }

        XCTAssertEqual(fixture.memoryStore.entriesSnapshot, before)
        XCTAssertEqual(fixture.memoryStore.memoryMutationCount, 0)
        let serialized = String(describing: response.payload)
        for forbidden in [
            "PRIVATE_", "EXACT_PRIVATE_CONTENT", "source-secret", "model-secret",
            "content", "embedding", "vector", "model", "revision", "fingerprint", "cache",
        ] {
            XCTAssertFalse(serialized.contains(forbidden), "Leaked semantic response data: \(forbidden)")
        }
    }

    func testMissingNonlocalAndWrongKindModelsAreRefused() async throws {
        let cases: [(String, [ModelInfo])] = [
            ("missing", []),
            ("not-installed", [embeddingModel(revision: "missing", installed: false)]),
            ("nonlocal", [embeddingModel(revision: "cloud", source: .cloud)]),
            ("wrong-kind", [embeddingModel(revision: "chat", kind: .chat)]),
            ("wrong-provider", [embeddingModel(revision: "provider", provider: .lmStudio)]),
        ]

        for (name, models) in cases {
            let backend = SemanticDuplicateBackend(models: models)
            let fixture = try await makeFixture(entries: semanticEntries(), backend: backend)
            let sink = SemanticDuplicateRecordingSink()
            try await authenticate(router: fixture.router, sink: sink, fixture: fixture)

            fixture.router.handle(request(id: name), sink: sink)
            let response = try await sink.waitForMessages(count: 3)
            XCTAssertEqual(response.last?.payload["code"], .string("model_not_installed"), name)
            XCTAssertTrue(backend.embeddingRequests.isEmpty, name)
        }
    }

    func testWeakRevisionRunsOnlyAsSingleBatchAndNeverCaches() async throws {
        let singleBatchBackend = SemanticDuplicateBackend(models: [embeddingModel(revision: nil)])
        let singleBatchFixture = try await makeFixture(
            entries: semanticEntries(),
            backend: singleBatchBackend
        )
        let singleBatchSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: singleBatchFixture.router,
            sink: singleBatchSink,
            fixture: singleBatchFixture
        )

        singleBatchFixture.router.handle(
            request(id: "weak-single-batch", threshold: 10_000),
            sink: singleBatchSink
        )
        let accepted = try await singleBatchSink.waitForMessages(count: 3)
        XCTAssertEqual(accepted.last?.type, MessageType.memorySemanticDuplicateSuggestionsList)
        XCTAssertEqual(singleBatchBackend.embeddingRequests.map(\.texts.count), [5])
        XCTAssertEqual(singleBatchFixture.memoryStore.cachedRecordCount, 0)
        XCTAssertEqual(singleBatchFixture.memoryStore.cacheWriteCount, 0)

        let multiBatchEntries = (0..<65).map { index in
            memoryEntry(id: String(format: "entry-%03d", index), content: "unique-content-\(index)")
        }
        let multiBatchBackend = SemanticDuplicateBackend(models: [embeddingModel(revision: nil)])
        let multiBatchFixture = try await makeFixture(
            entries: multiBatchEntries,
            backend: multiBatchBackend
        )
        let multiBatchSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: multiBatchFixture.router,
            sink: multiBatchSink,
            fixture: multiBatchFixture
        )

        multiBatchFixture.router.handle(
            request(id: "weak-multi-batch", threshold: 10_000),
            sink: multiBatchSink
        )
        let rejected = try await multiBatchSink.waitForMessages(count: 3)
        XCTAssertEqual(rejected.last?.type, MessageType.error)
        XCTAssertEqual(rejected.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertTrue(multiBatchBackend.embeddingRequests.isEmpty)
        XCTAssertEqual(multiBatchFixture.memoryStore.cachedRecordCount, 0)
        XCTAssertEqual(multiBatchFixture.memoryStore.cacheWriteCount, 0)
    }

    func testStrongFingerprintCachesEmbeddingsAcrossRequests() async throws {
        let backend = SemanticDuplicateBackend(models: [embeddingModel(revision: "strong-cache")])
        let fixture = try await makeFixture(entries: semanticEntries(), backend: backend)
        let sink = SemanticDuplicateRecordingSink()
        try await authenticate(router: fixture.router, sink: sink, fixture: fixture)

        fixture.router.handle(request(id: "cache-cold"), sink: sink)
        var messages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.type, MessageType.memorySemanticDuplicateSuggestionsList)
        XCTAssertEqual(backend.embeddingRequests.map(\.texts.count), [5])
        XCTAssertEqual(fixture.memoryStore.cachedRecordCount, 5)

        fixture.router.handle(request(id: "cache-warm"), sink: sink)
        messages = try await sink.waitForMessages(count: 4)
        XCTAssertEqual(messages.last?.type, MessageType.memorySemanticDuplicateSuggestionsList)
        XCTAssertEqual(backend.embeddingRequests.map(\.texts.count), [5])
        XCTAssertEqual(fixture.memoryStore.cacheWriteCount, 1)
    }

    func testStrongFingerprintSplitsAtByteBudgetAndWeakFingerprintRejectsBeforeDispatch() async throws {
        let entries = (0..<33).map { index in
            memoryEntry(
                id: String(format: "byte-batch-%03d", index),
                content: String(format: "%04d", index) + String(repeating: "x", count: 8_188)
            )
        }
        let strongBackend = SemanticDuplicateBackend(
            models: [embeddingModel(
                revision: "strong-byte-batches",
                contextWindowTokens: 8_224
            )]
        )
        let strongFixture = try await makeFixture(entries: entries, backend: strongBackend)
        let strongSink = SemanticDuplicateRecordingSink()
        try await authenticate(router: strongFixture.router, sink: strongSink, fixture: strongFixture)

        strongFixture.router.handle(
            request(id: "strong-byte-batches", threshold: 10_000),
            sink: strongSink
        )
        var messages = try await strongSink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.type, MessageType.memorySemanticDuplicateSuggestionsList)
        XCTAssertEqual(strongBackend.embeddingRequests.map(\.texts.count), [32, 1])
        XCTAssertTrue(strongBackend.embeddingRequests.allSatisfy { request in
            request.texts.reduce(0) { $0 + $1.utf8.count } <=
                RuntimeMemorySemanticDuplicateSuggester.maximumEmbeddingBatchUTF8ByteCount
        })

        let weakBackend = SemanticDuplicateBackend(models: [embeddingModel(
            revision: nil,
            contextWindowTokens: 8_224
        )])
        let weakFixture = try await makeFixture(entries: entries, backend: weakBackend)
        let weakSink = SemanticDuplicateRecordingSink()
        try await authenticate(router: weakFixture.router, sink: weakSink, fixture: weakFixture)

        weakFixture.router.handle(
            request(id: "weak-byte-batches", threshold: 10_000),
            sink: weakSink
        )
        messages = try await weakSink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.type, MessageType.error)
        XCTAssertEqual(messages.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertTrue(weakBackend.embeddingRequests.isEmpty)
    }

    func testInvalidEmbeddingProviderCountModelDimensionAndVectorFailClosed() async throws {
        let invalidCases: [(String, SemanticDuplicateBackend.EmbeddingResponder)] = [
            ("provider", { request, _ in
                EmbeddingResult(
                    model: "lm_studio:" + (ModelProvider.splitQualifiedModelID(request.model)?.modelID ?? request.model),
                    embeddings: request.texts.map { _ in [1, 0] }
                )
            }),
            ("count", { request, _ in
                EmbeddingResult(model: request.model, embeddings: Array(repeating: [1, 0], count: max(0, request.texts.count - 1)))
            }),
            ("model", { request, _ in
                EmbeddingResult(model: "different-embedding-model", embeddings: request.texts.map { _ in [1, 0] })
            }),
            ("dimension", { request, _ in
                EmbeddingResult(
                    model: request.model,
                    embeddings: request.texts.enumerated().map { index, _ in index == 0 ? [1, 0] : [1] }
                )
            }),
            ("oversized-dimension", { request, _ in
                let oversized = Array(
                    repeating: 1.0,
                    count: RuntimeMemorySemanticDuplicateSuggester.maximumEmbeddingDimension + 1
                )
                return EmbeddingResult(
                    model: request.model,
                    embeddings: request.texts.map { _ in oversized }
                )
            }),
            ("zero-vector", { request, _ in
                EmbeddingResult(model: request.model, embeddings: request.texts.map { _ in [0, 0] })
            }),
            ("nonfinite-vector", { request, _ in
                EmbeddingResult(model: request.model, embeddings: request.texts.map { _ in [.nan, 1] })
            }),
        ]

        for (name, responder) in invalidCases {
            let backend = SemanticDuplicateBackend(
                models: [embeddingModel(revision: "invalid-\(name)")],
                embeddingResponder: responder
            )
            let fixture = try await makeFixture(entries: semanticEntries(), backend: backend)
            let sink = SemanticDuplicateRecordingSink()
            try await authenticate(router: fixture.router, sink: sink, fixture: fixture)

            fixture.router.handle(request(id: "invalid-\(name)"), sink: sink)
            let response = try await sink.waitForMessages(count: 3)
            XCTAssertEqual(response.last?.type, MessageType.error, name)
            XCTAssertEqual(response.last?.payload["code"], .string("backend_unavailable"), name)
            XCTAssertFalse(response.contains { $0.type == MessageType.memorySemanticDuplicateSuggestionsList }, name)
            XCTAssertEqual(fixture.memoryStore.cachedRecordCount, 0, name)
        }
    }

    func testSourceMutationRetriesOnceAndRepeatedMutationFailsClosed() async throws {
        let onceStore = SemanticDuplicateMemoryStore(entries: semanticEntries()) { call, _ in
            call == 1 ? "source-v1" : "source-v2"
        }
        let onceBackend = SemanticDuplicateBackend(models: [embeddingModel(revision: nil)])
        let onceFixture = try await makeFixture(memoryStore: onceStore, backend: onceBackend)
        let onceSink = SemanticDuplicateRecordingSink()
        try await authenticate(router: onceFixture.router, sink: onceSink, fixture: onceFixture)

        onceFixture.router.handle(request(id: "source-retry"), sink: onceSink)
        let recovered = try await onceSink.waitForMessages(count: 3)
        XCTAssertEqual(recovered.last?.type, MessageType.memorySemanticDuplicateSuggestionsList)
        XCTAssertEqual(onceStore.semanticSourceReadCount, 6)
        XCTAssertEqual(onceBackend.embeddingRequests.count, 2)

        let repeatedStore = SemanticDuplicateMemoryStore(entries: semanticEntries()) { call, _ in
            "source-v\(call)"
        }
        let repeatedBackend = SemanticDuplicateBackend(models: [embeddingModel(revision: nil)])
        let repeatedFixture = try await makeFixture(memoryStore: repeatedStore, backend: repeatedBackend)
        let repeatedSink = SemanticDuplicateRecordingSink()
        try await authenticate(router: repeatedFixture.router, sink: repeatedSink, fixture: repeatedFixture)

        repeatedFixture.router.handle(request(id: "source-fail"), sink: repeatedSink)
        let failed = try await repeatedSink.waitForMessages(count: 3)
        XCTAssertEqual(failed.last?.type, MessageType.error)
        XCTAssertEqual(failed.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertEqual(repeatedStore.semanticSourceReadCount, 4)
        XCTAssertEqual(repeatedBackend.embeddingRequests.count, 2)
        XCTAssertEqual(repeatedStore.cachedRecordCount, 0)
    }

    func testModelIdentityDriftRetriesOnceAndRepeatedDriftFailsClosed() async throws {
        let modelA = embeddingModel(revision: "model-a")
        let modelB = embeddingModel(revision: "model-b")
        let modelC = embeddingModel(revision: "model-c")
        let modelD = embeddingModel(revision: "model-d")
        let recoveringBackend = SemanticDuplicateBackend(
            models: [modelB],
            modelListBatches: [[modelA], [modelB], [modelB], [modelB]]
        )
        let recoveringFixture = try await makeFixture(entries: semanticEntries(), backend: recoveringBackend)
        let recoveringSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: recoveringFixture.router,
            sink: recoveringSink,
            fixture: recoveringFixture
        )

        recoveringFixture.router.handle(request(id: "model-retry"), sink: recoveringSink)
        let recovered = try await recoveringSink.waitForMessages(count: 3)
        XCTAssertEqual(recovered.last?.type, MessageType.memorySemanticDuplicateSuggestionsList)
        XCTAssertEqual(recoveringBackend.listModelsCallCount, 7)
        XCTAssertEqual(recoveringBackend.embeddingRequests.count, 2)

        let driftingBackend = SemanticDuplicateBackend(
            models: [modelD],
            modelListBatches: [[modelA], [modelB], [modelC], [modelD]]
        )
        let driftingFixture = try await makeFixture(entries: semanticEntries(), backend: driftingBackend)
        let driftingSink = SemanticDuplicateRecordingSink()
        try await authenticate(router: driftingFixture.router, sink: driftingSink, fixture: driftingFixture)

        driftingFixture.router.handle(request(id: "model-fail"), sink: driftingSink)
        let failed = try await driftingSink.waitForMessages(count: 3)
        XCTAssertEqual(failed.last?.type, MessageType.error)
        XCTAssertEqual(failed.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertEqual(driftingBackend.listModelsCallCount, 4)
        XCTAssertEqual(driftingBackend.embeddingRequests.count, 2)
        XCTAssertEqual(driftingFixture.memoryStore.cachedRecordCount, 0)
    }

    func testFinalPublicationBoundaryRejectsLateSourceAndModelDriftBeforeCaching() async throws {
        let lateSourceStore = SemanticDuplicateMemoryStore(entries: semanticEntries()) { call, _ in
            call <= 2 ? "source-v1" : "source-v2"
        }
        let lateSourceBackend = SemanticDuplicateBackend(
            models: [embeddingModel(revision: "late-source")]
        )
        let lateSourceFixture = try await makeFixture(
            memoryStore: lateSourceStore,
            backend: lateSourceBackend
        )
        let lateSourceSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: lateSourceFixture.router,
            sink: lateSourceSink,
            fixture: lateSourceFixture
        )

        lateSourceFixture.router.handle(request(id: "late-source"), sink: lateSourceSink)
        let sourceRejected = try await lateSourceSink.waitForMessages(count: 3)
        XCTAssertEqual(sourceRejected.last?.type, MessageType.error)
        XCTAssertEqual(sourceRejected.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertEqual(lateSourceStore.semanticSourceReadCount, 3)
        XCTAssertEqual(lateSourceStore.cachedRecordCount, 0)
        XCTAssertEqual(lateSourceStore.cacheWriteCount, 0)

        let modelA = embeddingModel(revision: "late-model-a")
        let modelB = embeddingModel(revision: "late-model-b")
        let lateModelBackend = SemanticDuplicateBackend(
            models: [modelB],
            modelListBatches: [[modelA], [modelA], [modelB]]
        )
        let lateModelFixture = try await makeFixture(
            entries: semanticEntries(),
            backend: lateModelBackend
        )
        let lateModelSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: lateModelFixture.router,
            sink: lateModelSink,
            fixture: lateModelFixture
        )

        lateModelFixture.router.handle(request(id: "late-model"), sink: lateModelSink)
        let modelRejected = try await lateModelSink.waitForMessages(count: 3)
        XCTAssertEqual(modelRejected.last?.type, MessageType.error)
        XCTAssertEqual(modelRejected.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertEqual(lateModelBackend.listModelsCallCount, 3)
        XCTAssertEqual(lateModelFixture.memoryStore.cachedRecordCount, 0)
        XCTAssertEqual(lateModelFixture.memoryStore.cacheWriteCount, 0)
    }

    func testTrustRemovalKeyReplacementAndIdenticalReauthenticationSuppressStaleResponse() async throws {
        for change in ["remove", "replace", "reauthenticate"] {
            let backend = SemanticDuplicateBackend(
                models: [embeddingModel(revision: "trust-\(change)")],
                holdEmbeddings: true
            )
            let fixture = try await makeFixture(entries: semanticEntries(), backend: backend)
            let sink = SemanticDuplicateRecordingSink()
            try await authenticate(router: fixture.router, sink: sink, fixture: fixture)

            let requestID = "trust-\(change)"
            fixture.router.handle(request(id: requestID), sink: sink)
            try await waitUntil { backend.heldEmbeddingCount == 1 }

            switch change {
            case "remove":
                try await fixture.trustedDeviceStore.remove(deviceID: fixture.ownerDeviceID)
            case "replace":
                let replacement = P256.Signing.PrivateKey()
                try await fixture.trustedDeviceStore.trust(TrustedDevice(
                    id: fixture.ownerDeviceID,
                    name: "Replacement",
                    publicKeyBase64: replacement.publicKey.derRepresentation.base64EncodedString()
                ))
            default:
                try await authenticate(
                    router: fixture.router,
                    sink: sink,
                    fixture: fixture,
                    existingMessageCount: 2
                )
            }
            backend.releaseHeldEmbeddings()

            let expectedCount = change == "reauthenticate" ? 5 : 3
            let messages = try await sink.waitForMessages(count: expectedCount)
            let terminal = messages.last { $0.requestID == requestID }
            XCTAssertEqual(terminal?.type, MessageType.error, change)
            XCTAssertEqual(
                terminal?.payload["code"],
                .string(change == "reauthenticate" ? "authentication_required" : "pairing_required"),
                change
            )
            XCTAssertFalse(messages.contains {
                $0.requestID == requestID && $0.type == MessageType.memorySemanticDuplicateSuggestionsList
            }, change)
            XCTAssertEqual(fixture.memoryStore.cachedRecordCount, 0, change)
        }
    }

    func testSharedSemanticSlotLimitRejectsFifthConcurrentRequest() async throws {
        let backend = SemanticDuplicateBackend(
            models: [embeddingModel(revision: nil)],
            holdEmbeddings: true
        )
        let fixture = try await makeFixture(entries: semanticEntries(), backend: backend)
        let sinks = (0..<5).map { _ in SemanticDuplicateRecordingSink() }
        for (index, sink) in sinks.enumerated() {
            try await authenticate(
                router: fixture.router,
                sink: sink,
                fixture: fixture,
                capabilities: index == 4
                    ? ["memory.semantic_duplicate_clusters.v1"]
                    : nil
            )
        }

        for index in 0..<4 {
            fixture.router.handle(request(id: "slot-\(index)"), sink: sinks[index])
        }
        try await waitUntil { backend.heldEmbeddingCount == 4 }

        fixture.router.handle(clusterRequest(id: "slot-4"), sink: sinks[4])
        let rejected = try await sinks[4].waitForMessages(count: 3)
        XCTAssertEqual(rejected.last?.type, MessageType.error)
        XCTAssertEqual(rejected.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertEqual(backend.embeddingRequests.count, 4)

        backend.releaseHeldEmbeddings()
        for index in 0..<4 {
            let messages = try await sinks[index].waitForMessages(count: 3)
            XCTAssertEqual(messages.last?.type, MessageType.memorySemanticDuplicateSuggestionsList)
        }
    }

    func testFinalPublicationSerializesMemoryMutationBehindResponse() async throws {
        let barrier = SemanticDuplicatePublicationBarrier()
        let backend = SemanticDuplicateBackend(
            models: [embeddingModel(revision: "publication")],
            holdEmbeddings: true
        )
        let fixture = try await makeFixture(
            entries: semanticEntries(),
            backend: backend,
            semanticDuplicatePublicationCheckpoint: { barrier.checkpoint() },
            semanticDuplicateMemoryMutationPrelockCheckpoint: {
                barrier.holdMutationBeforeLock()
            },
            semanticDuplicateMemoryMutationContentionCheckpoint: {
                barrier.markMutationContended()
            }
        )
        let sink = SemanticDuplicateRecordingSink()
        try await authenticate(router: fixture.router, sink: sink, fixture: fixture)

        fixture.router.handle(request(id: "publication"), sink: sink)
        try await waitUntil { backend.heldEmbeddingCount == 1 }

        let router = fixture.router
        let mutationTask = Task.detached {
            router.handle(ProtocolEnvelope(
                type: MessageType.memoryUpsert,
                requestID: "mutation",
                payload: ["content": .string("MUTATED_AFTER_PUBLICATION")]
            ), sink: sink)
        }
        try await waitUntil { barrier.hasMutationAtPrelock }

        backend.releaseHeldEmbeddings()
        try await waitUntil { barrier.hasEnteredPublication }
        barrier.releaseMutationToContend()
        try await waitUntil { barrier.hasContendedMutation }
        XCTAssertEqual(fixture.memoryStore.memoryMutationCount, 0)

        barrier.releasePublication()
        await mutationTask.value

        let messages = try await sink.waitForMessages(count: 4)
        let terminalTypes = messages
            .filter { $0.requestID == "publication" || $0.requestID == "mutation" }
            .map(\.type)
        XCTAssertEqual(terminalTypes, [
            MessageType.memorySemanticDuplicateSuggestionsList,
            MessageType.memoryUpsert,
        ])
        XCTAssertEqual(fixture.memoryStore.memoryMutationCount, 1)
    }

    func testStrongCacheCommitAcquiresLifecycleBeforeMemoryStoreAccess() async throws {
        let barrier = SemanticDuplicatePublicationBarrier()
        let fixture = try await makeFixture(
            entries: semanticEntries(),
            backend: SemanticDuplicateBackend(
                models: [embeddingModel(revision: "cache-lock-order")]
            ),
            semanticDuplicateCacheCommitCheckpoint: { barrier.checkpoint() },
            semanticDuplicateMemoryMutationPrelockCheckpoint: {
                barrier.holdMutationBeforeLock()
            },
            semanticDuplicateMemoryMutationContentionCheckpoint: {
                barrier.markMutationContended()
            }
        )
        let sink = SemanticDuplicateRecordingSink()
        try await authenticate(router: fixture.router, sink: sink, fixture: fixture)

        fixture.router.handle(request(id: "cache-lock-order"), sink: sink)
        try await waitUntil { barrier.hasEnteredPublication }

        fixture.router.handle(ProtocolEnvelope(
            type: MessageType.memoryUpsert,
            requestID: "cache-lock-order-mutation",
            payload: ["content": .string("MUTATION_AFTER_CACHE_COMMIT")]
        ), sink: sink)
        try await waitUntil { barrier.hasMutationAtPrelock }
        barrier.releaseMutationToContend()
        try await waitUntil { barrier.hasContendedMutation }
        XCTAssertEqual(fixture.memoryStore.memoryMutationCount, 0)

        barrier.releasePublication()
        let messages = try await sink.waitForMessages(count: 4)
        XCTAssertTrue(messages.contains {
            $0.requestID == "cache-lock-order-mutation" && $0.type == MessageType.memoryUpsert
        })
        XCTAssertEqual(fixture.memoryStore.memoryMutationCount, 1)
    }

    func testFinalTrustLeaseRejectsRemovalAfterEarlyRevalidation() async throws {
        let barrier = SemanticDuplicatePublicationBarrier()
        let fixture = try await makeFixture(
            entries: semanticEntries(),
            semanticDuplicateAuthorityCheckpoint: { barrier.checkpoint() }
        )
        let sink = SemanticDuplicateRecordingSink()
        try await authenticate(router: fixture.router, sink: sink, fixture: fixture)

        fixture.router.handle(request(id: "late-trust-removal"), sink: sink)
        try await waitUntil { barrier.hasEnteredPublication }
        try await fixture.trustedDeviceStore.remove(deviceID: fixture.ownerDeviceID)
        barrier.releasePublication()

        let messages = try await sink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.type, MessageType.error)
        XCTAssertEqual(messages.last?.payload["code"], .string("pairing_required"))
        XCTAssertFalse(messages.contains {
            $0.requestID == "late-trust-removal" &&
                $0.type == MessageType.memorySemanticDuplicateSuggestionsList
        })
    }

    func testFinalModelCatalogTokenRejectsConcurrentRevisionObservation() async throws {
        let barrier = SemanticDuplicatePublicationBarrier()
        let backend = SemanticDuplicateBackend(models: [embeddingModel(revision: "model-a")])
        let fixture = try await makeFixture(
            entries: semanticEntries(),
            backend: backend,
            semanticDuplicateAuthorityCheckpoint: { barrier.checkpoint() }
        )
        let firstSink = SemanticDuplicateRecordingSink()
        let secondSink = SemanticDuplicateRecordingSink()
        try await authenticate(router: fixture.router, sink: firstSink, fixture: fixture)
        try await authenticate(router: fixture.router, sink: secondSink, fixture: fixture)

        fixture.router.handle(
            request(id: "model-a-publication", modelID: "ollama:nomic-embed-text:latest"),
            sink: firstSink
        )
        try await waitUntil { barrier.hasEnteredPublication }

        backend.replaceModels([embeddingModel(revision: "model-b")])
        fixture.router.handle(request(id: "model-b-observation"), sink: secondSink)
        let secondMessages = try await secondSink.waitForMessages(count: 3)
        XCTAssertEqual(
            secondMessages.last?.type,
            MessageType.memorySemanticDuplicateSuggestionsList
        )

        barrier.releasePublication()
        let firstMessages = try await firstSink.waitForMessages(count: 3)
        XCTAssertEqual(firstMessages.last?.type, MessageType.error)
        XCTAssertEqual(firstMessages.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertFalse(firstMessages.contains {
            $0.requestID == "model-a-publication" &&
                $0.type == MessageType.memorySemanticDuplicateSuggestionsList
        })
    }

    func testClusterOperationRequiresAuthenticationAndSeparateCapability() async throws {
        let fixture = try await makeFixture(entries: semanticEntries())

        let unauthenticatedSink = SemanticDuplicateRecordingSink()
        fixture.router.handle(clusterRequest(id: "cluster-unauthenticated"), sink: unauthenticatedSink)
        var messages = try await unauthenticatedSink.waitForMessages(count: 1)
        XCTAssertEqual(messages.last?.payload["code"], .string("authentication_required"))

        let missingCapabilitySink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: fixture.router,
            sink: missingCapabilitySink,
            fixture: fixture,
            capabilities: []
        )
        fixture.router.handle(clusterRequest(id: "cluster-missing-capability"), sink: missingCapabilitySink)
        messages = try await missingCapabilitySink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.payload["code"], .string("unsupported_operation"))

        let negotiatedSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: fixture.router,
            sink: negotiatedSink,
            fixture: fixture,
            capabilities: ["memory.semantic_duplicate_clusters.v1"]
        )
        fixture.router.handle(clusterRequest(id: "cluster-negotiated"), sink: negotiatedSink)
        messages = try await negotiatedSink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.type, MessageType.memorySemanticDuplicateClustersList)
    }

    func testClusterResponseIsMinimalDeterministicCachedAndDoesNotMutateMemory() async throws {
        let backend = SemanticDuplicateBackend(
            models: [embeddingModel(revision: "cluster-cache")],
            embeddingResponder: { request, _ in
                EmbeddingResult(
                    model: request.model,
                    embeddings: request.texts.map { text in
                        switch text {
                        case "PRIVATE_ALPHA", "PRIVATE_BETA": return [1, 0]
                        case "PRIVATE_GAMMA": return [0.8, 0.6]
                        case "EXACT_PRIVATE_CONTENT": return [0, 1]
                        default: return [1, 0]
                        }
                    }
                )
            }
        )
        let fixture = try await makeFixture(entries: semanticEntries(), backend: backend)
        let sink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: fixture.router,
            sink: sink,
            fixture: fixture,
            capabilities: ["memory.semantic_duplicate_clusters.v1"]
        )
        let before = fixture.memoryStore.entriesSnapshot

        fixture.router.handle(clusterRequest(id: "cluster-valid"), sink: sink)
        var messages = try await sink.waitForMessages(count: 3)
        let response = try XCTUnwrap(messages.last)
        XCTAssertEqual(response.type, MessageType.memorySemanticDuplicateClustersList)
        XCTAssertEqual(
            Set(response.payload.keys),
            ["clusters", "scanned_count", "omitted_count", "truncated"]
        )
        XCTAssertEqual(response.payload["clusters"], .array([
            cluster(["a", "b", "c"], minimumScore: 8_000)
        ]))
        XCTAssertEqual(response.payload["scanned_count"], .number(5))
        XCTAssertEqual(response.payload["omitted_count"], .number(0))
        XCTAssertEqual(response.payload["truncated"], .bool(false))
        XCTAssertEqual(fixture.memoryStore.entriesSnapshot, before)
        XCTAssertEqual(fixture.memoryStore.memoryMutationCount, 0)
        XCTAssertEqual(fixture.memoryStore.cachedRecordCount, 5)

        fixture.router.handle(clusterRequest(id: "cluster-cache-hit"), sink: sink)
        messages = try await sink.waitForMessages(count: 4)
        XCTAssertEqual(messages.last?.payload["clusters"], response.payload["clusters"])
        XCTAssertEqual(backend.embeddingRequests.map(\.texts.count), [5])

        let serialized = String(describing: response.payload)
        for forbidden in [
            "PRIVATE_", "EXACT_PRIVATE_CONTENT", "source-secret", "model-secret",
            "content", "embedding", "vector", "model", "revision", "fingerprint", "cache",
        ] {
            XCTAssertFalse(serialized.contains(forbidden), "Leaked cluster response data: \(forbidden)")
        }
    }

    func testClusterOperationRejectsClosedPayloadAndNoncanonicalModel() async throws {
        let fixture = try await makeFixture(entries: semanticEntries())
        let sink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: fixture.router,
            sink: sink,
            fixture: fixture,
            capabilities: ["memory.semantic_duplicate_clusters.v1"]
        )
        let payloads: [(String, [String: JSONValue])] = [
            ("cluster-unknown", validPayload().merging(["include_pairs": .bool(true)]) { _, new in new }),
            ("cluster-float", validPayload(threshold: .number(8_000))),
            ("cluster-empty-model", validPayload(modelID: "ollama:")),
            ("cluster-noncanonical", validPayload(modelID: "ollama:nomic-embed-text:latest")),
        ]

        var expectedCount = 2
        for (requestID, payload) in payloads {
            fixture.router.handle(ProtocolEnvelope(
                type: MessageType.memorySemanticDuplicateClustersList,
                requestID: requestID,
                payload: payload
            ), sink: sink)
            expectedCount += 1
            let messages = try await sink.waitForMessages(count: expectedCount)
            XCTAssertEqual(messages.last?.type, MessageType.error)
            XCTAssertEqual(messages.last?.payload["code"], .string("invalid_payload"))
        }
    }

    func testClusterWeakRevisionIsSingleBatchOnlyAndNeverCached() async throws {
        let singleBackend = SemanticDuplicateBackend(models: [embeddingModel(revision: nil)])
        let singleFixture = try await makeFixture(entries: semanticEntries(), backend: singleBackend)
        let singleSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: singleFixture.router,
            sink: singleSink,
            fixture: singleFixture,
            capabilities: ["memory.semantic_duplicate_clusters.v1"]
        )
        singleFixture.router.handle(clusterRequest(id: "cluster-weak-single"), sink: singleSink)
        var messages = try await singleSink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.type, MessageType.memorySemanticDuplicateClustersList)
        XCTAssertEqual(singleBackend.embeddingRequests.map(\.texts.count), [5])
        XCTAssertEqual(singleFixture.memoryStore.cachedRecordCount, 0)
        XCTAssertEqual(singleFixture.memoryStore.cacheWriteCount, 0)

        let entries = (0..<65).map { index in
            memoryEntry(id: String(format: "cluster-%03d", index), content: "content-\(index)")
        }
        let multiBackend = SemanticDuplicateBackend(models: [embeddingModel(revision: nil)])
        let multiFixture = try await makeFixture(entries: entries, backend: multiBackend)
        let multiSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: multiFixture.router,
            sink: multiSink,
            fixture: multiFixture,
            capabilities: ["memory.semantic_duplicate_clusters.v1"]
        )
        multiFixture.router.handle(clusterRequest(id: "cluster-weak-multi"), sink: multiSink)
        messages = try await multiSink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertTrue(multiBackend.embeddingRequests.isEmpty)
        XCTAssertEqual(multiFixture.memoryStore.cachedRecordCount, 0)
    }

    func testClusterOperationRejectsLateSourceAndModelDriftWithoutPublishing() async throws {
        let sourceStore = SemanticDuplicateMemoryStore(entries: semanticEntries()) { call, _ in
            call <= 2 ? "source-v1" : "source-v2"
        }
        let sourceFixture = try await makeFixture(
            memoryStore: sourceStore,
            backend: SemanticDuplicateBackend(models: [embeddingModel(revision: "cluster-source")])
        )
        let sourceSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: sourceFixture.router,
            sink: sourceSink,
            fixture: sourceFixture,
            capabilities: ["memory.semantic_duplicate_clusters.v1"]
        )
        sourceFixture.router.handle(clusterRequest(id: "cluster-source-drift"), sink: sourceSink)
        var messages = try await sourceSink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertFalse(messages.contains { $0.type == MessageType.memorySemanticDuplicateClustersList })
        XCTAssertEqual(sourceStore.cachedRecordCount, 0)

        let modelA = embeddingModel(revision: "cluster-model-a")
        let modelB = embeddingModel(revision: "cluster-model-b")
        let modelBackend = SemanticDuplicateBackend(
            models: [modelB],
            modelListBatches: [[modelA], [modelA], [modelB]]
        )
        let modelFixture = try await makeFixture(entries: semanticEntries(), backend: modelBackend)
        let modelSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: modelFixture.router,
            sink: modelSink,
            fixture: modelFixture,
            capabilities: ["memory.semantic_duplicate_clusters.v1"]
        )
        modelFixture.router.handle(clusterRequest(id: "cluster-model-drift"), sink: modelSink)
        messages = try await modelSink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.payload["code"], .string("backend_unavailable"))
        XCTAssertFalse(messages.contains { $0.type == MessageType.memorySemanticDuplicateClustersList })
        XCTAssertEqual(modelFixture.memoryStore.cachedRecordCount, 0)
    }

    func testClusterPublicKeyAndAuthenticationDriftSuppressStalePublication() async throws {
        for change in ["replace-key", "reauthenticate"] {
            let backend = SemanticDuplicateBackend(
                models: [embeddingModel(revision: "cluster-\(change)")],
                holdEmbeddings: true
            )
            let fixture = try await makeFixture(entries: semanticEntries(), backend: backend)
            let sink = SemanticDuplicateRecordingSink()
            try await authenticate(
                router: fixture.router,
                sink: sink,
                fixture: fixture,
                capabilities: ["memory.semantic_duplicate_clusters.v1"]
            )
            let requestID = "cluster-\(change)"
            fixture.router.handle(clusterRequest(id: requestID), sink: sink)
            try await waitUntil { backend.heldEmbeddingCount == 1 }

            if change == "replace-key" {
                let replacement = P256.Signing.PrivateKey()
                try await fixture.trustedDeviceStore.trust(TrustedDevice(
                    id: fixture.ownerDeviceID,
                    name: "Replacement",
                    publicKeyBase64: replacement.publicKey.derRepresentation.base64EncodedString()
                ))
            } else {
                try await authenticate(
                    router: fixture.router,
                    sink: sink,
                    fixture: fixture,
                    capabilities: ["memory.semantic_duplicate_clusters.v1"],
                    existingMessageCount: 2
                )
            }
            backend.releaseHeldEmbeddings()

            let expectedCount = change == "reauthenticate" ? 5 : 3
            let messages = try await sink.waitForMessages(count: expectedCount)
            let terminal = messages.last { $0.requestID == requestID }
            XCTAssertEqual(terminal?.type, MessageType.error)
            XCTAssertEqual(
                terminal?.payload["code"],
                .string(change == "replace-key" ? "pairing_required" : "authentication_required")
            )
            XCTAssertFalse(messages.contains {
                $0.requestID == requestID &&
                    $0.type == MessageType.memorySemanticDuplicateClustersList
            })
            XCTAssertEqual(fixture.memoryStore.cachedRecordCount, 0)
        }
    }

    func testClusterFinalTrustAndMutationPublicationLeasesArePreserved() async throws {
        let trustBarrier = SemanticDuplicatePublicationBarrier()
        let trustFixture = try await makeFixture(
            entries: semanticEntries(),
            semanticDuplicateAuthorityCheckpoint: { trustBarrier.checkpoint() }
        )
        let trustSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: trustFixture.router,
            sink: trustSink,
            fixture: trustFixture,
            capabilities: ["memory.semantic_duplicate_clusters.v1"]
        )
        trustFixture.router.handle(clusterRequest(id: "cluster-trust-drift"), sink: trustSink)
        try await waitUntil { trustBarrier.hasEnteredPublication }
        try await trustFixture.trustedDeviceStore.remove(deviceID: trustFixture.ownerDeviceID)
        trustBarrier.releasePublication()
        var messages = try await trustSink.waitForMessages(count: 3)
        XCTAssertEqual(messages.last?.payload["code"], .string("pairing_required"))
        XCTAssertFalse(messages.contains { $0.type == MessageType.memorySemanticDuplicateClustersList })

        let mutationBarrier = SemanticDuplicatePublicationBarrier()
        let mutationBackend = SemanticDuplicateBackend(
            models: [embeddingModel(revision: "cluster-publication")],
            holdEmbeddings: true
        )
        let mutationFixture = try await makeFixture(
            entries: semanticEntries(),
            backend: mutationBackend,
            semanticDuplicatePublicationCheckpoint: { mutationBarrier.checkpoint() },
            semanticDuplicateMemoryMutationPrelockCheckpoint: {
                mutationBarrier.holdMutationBeforeLock()
            },
            semanticDuplicateMemoryMutationContentionCheckpoint: {
                mutationBarrier.markMutationContended()
            }
        )
        let mutationSink = SemanticDuplicateRecordingSink()
        try await authenticate(
            router: mutationFixture.router,
            sink: mutationSink,
            fixture: mutationFixture,
            capabilities: ["memory.semantic_duplicate_clusters.v1"]
        )
        mutationFixture.router.handle(clusterRequest(id: "cluster-publication"), sink: mutationSink)
        try await waitUntil { mutationBackend.heldEmbeddingCount == 1 }
        let router = mutationFixture.router
        let mutationTask = Task.detached {
            router.handle(ProtocolEnvelope(
                type: MessageType.memoryDelete,
                requestID: "cluster-mutation",
                payload: ["id": .string("a")]
            ), sink: mutationSink)
        }
        try await waitUntil { mutationBarrier.hasMutationAtPrelock }
        mutationBackend.releaseHeldEmbeddings()
        try await waitUntil { mutationBarrier.hasEnteredPublication }
        mutationBarrier.releaseMutationToContend()
        try await waitUntil { mutationBarrier.hasContendedMutation }
        XCTAssertEqual(mutationFixture.memoryStore.memoryMutationCount, 0)
        mutationBarrier.releasePublication()
        await mutationTask.value

        messages = try await mutationSink.waitForMessages(count: 4)
        XCTAssertEqual(
            messages.filter { ["cluster-publication", "cluster-mutation"].contains($0.requestID) }
                .map(\.type),
            [MessageType.memorySemanticDuplicateClustersList, MessageType.memoryDelete]
        )
        XCTAssertEqual(mutationFixture.memoryStore.memoryMutationCount, 1)
    }

    private func request(
        id: String,
        threshold: Int = 8_000,
        modelID: String = "ollama:nomic-embed-text"
    ) -> ProtocolEnvelope {
        ProtocolEnvelope(
            type: MessageType.memorySemanticDuplicateSuggestionsList,
            requestID: id,
            payload: validPayload(
                modelID: modelID,
                threshold: .integer(Int64(threshold))
            )
        )
    }

    private func clusterRequest(
        id: String,
        threshold: Int = 8_000,
        modelID: String = "ollama:nomic-embed-text"
    ) -> ProtocolEnvelope {
        ProtocolEnvelope(
            type: MessageType.memorySemanticDuplicateClustersList,
            requestID: id,
            payload: validPayload(
                modelID: modelID,
                threshold: .integer(Int64(threshold))
            )
        )
    }

    private func validPayload(
        modelID: String = "ollama:nomic-embed-text",
        threshold: JSONValue = .integer(8_000)
    ) -> [String: JSONValue] {
        validPayload(modelValue: .string(modelID), threshold: threshold)
    }

    private func validPayload(
        modelValue: JSONValue,
        threshold: JSONValue = .integer(8_000)
    ) -> [String: JSONValue] {
        [
            "embedding_model_id": modelValue,
            "minimum_similarity_basis_points": threshold,
        ]
    }

    private func pair(_ entryIDs: [String], score: Int) -> JSONValue {
        .object([
            "entry_ids": .array(entryIDs.map(JSONValue.string)),
            "similarity_basis_points": .number(Double(score)),
        ])
    }

    private func cluster(_ entryIDs: [String], minimumScore: Int) -> JSONValue {
        .object([
            "entry_ids": .array(entryIDs.map(JSONValue.string)),
            "minimum_similarity_basis_points": .number(Double(minimumScore)),
        ])
    }

    private func semanticEntries() -> [RuntimeMemoryEntry] {
        [
            memoryEntry(id: "b", content: "PRIVATE_BETA"),
            memoryEntry(id: "exact-b", content: "EXACT_PRIVATE_CONTENT"),
            memoryEntry(id: "c", content: "PRIVATE_GAMMA"),
            memoryEntry(id: "a", content: "PRIVATE_ALPHA", source: secretSource()),
            memoryEntry(id: "exact-a", content: "EXACT_PRIVATE_CONTENT"),
        ]
    }

    private func secretSource() -> RuntimeMemoryEntrySource {
        RuntimeMemoryEntrySource(
            kind: "source-secret",
            draftID: "draft-secret",
            summaryMethod: "secret-method",
            session: RuntimeMemoryEntrySourceSession(
                sessionID: "session-secret",
                title: "title-secret",
                model: "model-secret",
                lastActivityAt: Date(timeIntervalSince1970: 1),
                messageCount: 1,
                inactiveSeconds: 1
            ),
            sourceMessageCount: 1,
            sourceRange: "secret-range",
            sourcePointers: [RuntimeMemoryEntrySourcePointer(
                sessionID: "session-secret",
                messageIndex: 0,
                role: "user",
                createdAt: nil,
                excerpt: "excerpt-secret"
            )]
        )
    }

    private func makeFixture(
        entries: [RuntimeMemoryEntry],
        backend: SemanticDuplicateBackend? = nil,
        semanticDuplicateAuthorityCheckpoint: (@Sendable () -> Void)? = nil,
        semanticDuplicateCacheCommitCheckpoint: (@Sendable () -> Void)? = nil,
        semanticDuplicatePublicationCheckpoint: (@Sendable () -> Void)? = nil,
        semanticDuplicateMemoryMutationPrelockCheckpoint: (@Sendable () -> Void)? = nil,
        semanticDuplicateMemoryMutationContentionCheckpoint: (@Sendable () -> Void)? = nil
    ) async throws -> SemanticDuplicateFixture {
        try await makeFixture(
            memoryStore: SemanticDuplicateMemoryStore(entries: entries),
            backend: backend ?? SemanticDuplicateBackend(models: [embeddingModel(revision: "default")]),
            semanticDuplicateAuthorityCheckpoint: semanticDuplicateAuthorityCheckpoint,
            semanticDuplicateCacheCommitCheckpoint: semanticDuplicateCacheCommitCheckpoint,
            semanticDuplicatePublicationCheckpoint: semanticDuplicatePublicationCheckpoint,
            semanticDuplicateMemoryMutationPrelockCheckpoint:
                semanticDuplicateMemoryMutationPrelockCheckpoint,
            semanticDuplicateMemoryMutationContentionCheckpoint:
                semanticDuplicateMemoryMutationContentionCheckpoint
        )
    }

    private func makeFixture(
        memoryStore: SemanticDuplicateMemoryStore,
        backend: SemanticDuplicateBackend,
        semanticDuplicateAuthorityCheckpoint: (@Sendable () -> Void)? = nil,
        semanticDuplicateCacheCommitCheckpoint: (@Sendable () -> Void)? = nil,
        semanticDuplicatePublicationCheckpoint: (@Sendable () -> Void)? = nil,
        semanticDuplicateMemoryMutationPrelockCheckpoint: (@Sendable () -> Void)? = nil,
        semanticDuplicateMemoryMutationContentionCheckpoint: (@Sendable () -> Void)? = nil
    ) async throws -> SemanticDuplicateFixture {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("semantic-duplicate-router-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        let trustedDeviceStore = TrustedDeviceStore(
            fileURL: directory.appendingPathComponent("trusted-devices.json")
        )
        let ownerDeviceID = "semantic-owner"
        let ownerKey = P256.Signing.PrivateKey()
        try await trustedDeviceStore.trust(TrustedDevice(
            id: ownerDeviceID,
            name: "Semantic Owner",
            publicKeyBase64: ownerKey.publicKey.derRepresentation.base64EncodedString()
        ))
        let router = LocalRuntimeMessageRouter(
            backend: backend,
            requiresAuthentication: true,
            trustedDeviceStore: trustedDeviceStore,
            chatEventStore: NullRuntimeChatEventStore(),
            memoryStore: memoryStore,
            documentIndexStore: RuntimeDocumentIndexStore(),
            semanticDuplicateAuthorityCheckpoint: semanticDuplicateAuthorityCheckpoint,
            semanticDuplicateCacheCommitCheckpoint: semanticDuplicateCacheCommitCheckpoint,
            semanticDuplicatePublicationCheckpoint: semanticDuplicatePublicationCheckpoint,
            semanticDuplicateMemoryMutationPrelockCheckpoint:
                semanticDuplicateMemoryMutationPrelockCheckpoint,
            semanticDuplicateMemoryMutationContentionCheckpoint:
                semanticDuplicateMemoryMutationContentionCheckpoint
        )
        return SemanticDuplicateFixture(
            router: router,
            backend: backend,
            memoryStore: memoryStore,
            trustedDeviceStore: trustedDeviceStore,
            ownerDeviceID: ownerDeviceID,
            ownerKey: ownerKey
        )
    }

    private func authenticate(
        router: LocalRuntimeMessageRouter,
        sink: SemanticDuplicateRecordingSink,
        fixture: SemanticDuplicateFixture,
        capabilities: [String]? = nil,
        existingMessageCount: Int = 0
    ) async throws {
        var payload: [String: JSONValue] = ["device_id": .string(fixture.ownerDeviceID)]
        let negotiatedCapabilities = capabilities ?? [capability]
        if !negotiatedCapabilities.isEmpty {
            payload["client_capabilities"] = .array(negotiatedCapabilities.map(JSONValue.string))
        }
        router.handle(ProtocolEnvelope(
            type: MessageType.hello,
            requestID: "hello-\(UUID().uuidString)",
            payload: payload
        ), sink: sink)
        let challenge = try await sink.waitForMessages(count: existingMessageCount + 1).last
        guard case .string(let nonce)? = challenge?.payload["nonce"] else {
            XCTFail("Expected authentication challenge nonce")
            return
        }
        let authenticationMessage = LocalRuntimeMessageRouter.clientAuthenticationResponseMessage(
            deviceID: fixture.ownerDeviceID,
            nonce: nonce
        )
        let signature = try fixture.ownerKey
            .signature(for: SHA256.hash(data: Data(authenticationMessage.utf8)))
            .derRepresentation
            .base64EncodedString()
        router.handle(ProtocolEnvelope(
            type: MessageType.authResponse,
            requestID: "auth-\(UUID().uuidString)",
            payload: [
                "device_id": .string(fixture.ownerDeviceID),
                "nonce": .string(nonce),
                "signature": .string(signature),
            ]
        ), sink: sink)
        let messages = try await sink.waitForMessages(count: existingMessageCount + 2)
        XCTAssertEqual(messages.last?.type, MessageType.authResponse)
        XCTAssertEqual(messages.last?.payload["accepted"], .bool(true))
    }

    private func waitUntil(
        timeout: TimeInterval = 2,
        condition: @escaping () -> Bool
    ) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if condition() { return }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        XCTFail("Timed out waiting for asynchronous router state")
    }
}

private struct SemanticDuplicateFixture {
    var router: LocalRuntimeMessageRouter
    var backend: SemanticDuplicateBackend
    var memoryStore: SemanticDuplicateMemoryStore
    var trustedDeviceStore: TrustedDeviceStore
    var ownerDeviceID: String
    var ownerKey: P256.Signing.PrivateKey
}

private final class SemanticDuplicatePublicationBarrier: @unchecked Sendable {
    private let condition = NSCondition()
    private var publicationEntered = false
    private var publicationReleased = false
    private var mutationAtPrelock = false
    private var mutationMayContend = false
    private var mutationContended = false

    var hasEnteredPublication: Bool {
        condition.withLock { publicationEntered }
    }

    var hasContendedMutation: Bool {
        condition.withLock { mutationContended }
    }

    var hasMutationAtPrelock: Bool {
        condition.withLock { mutationAtPrelock }
    }

    func checkpoint() {
        condition.lock()
        if publicationEntered {
            condition.unlock()
            return
        }
        publicationEntered = true
        condition.broadcast()
        while !publicationReleased {
            condition.wait()
        }
        condition.unlock()
    }

    func markMutationContended() {
        condition.withLock { mutationContended = true }
    }

    func holdMutationBeforeLock() {
        condition.lock()
        mutationAtPrelock = true
        condition.broadcast()
        while !mutationMayContend {
            condition.wait()
        }
        condition.unlock()
    }

    func releaseMutationToContend() {
        condition.withLock {
            mutationMayContend = true
            condition.broadcast()
        }
    }

    func releasePublication() {
        condition.withLock {
            publicationReleased = true
            condition.broadcast()
        }
    }
}

private final class SemanticDuplicateRecordingSink: RuntimeMessageSink, @unchecked Sendable {
    let connectionID = UUID()
    let transportSecurityContext: TransportSecurityContext? = nil
    private let lock = NSLock()
    private var recordedMessages: [ProtocolEnvelope] = []

    func withTransportSecurityContextTransaction<Result>(
        _ operation: (TransportSecurityContext?) throws -> Result
    ) rethrows -> Result {
        try operation(nil)
    }

    func send(_ envelope: ProtocolEnvelope) {
        lock.withLock { recordedMessages.append(envelope) }
    }

    func close() {}

    func waitForMessages(count: Int, timeout: TimeInterval = 2) async throws -> [ProtocolEnvelope] {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            let messages = lock.withLock { recordedMessages }
            if messages.count >= count { return messages }
            try await Task.sleep(nanoseconds: 1_000_000)
        }
        return lock.withLock { recordedMessages }
    }
}

private final class SemanticDuplicateMemoryStore: RuntimeMemoryStore, @unchecked Sendable {
    typealias RevisionProvider = (Int, RuntimeMemoryEntry) -> String

    private let lock = NSLock()
    private var entries: [RuntimeMemoryEntry]
    private let revisionProvider: RevisionProvider?
    private var semanticReads = 0
    private var semanticCache: [RuntimeMemorySemanticEmbeddingKey: [Double]] = [:]
    private var cacheWrites = 0
    private var memoryMutations = 0

    init(entries: [RuntimeMemoryEntry], revisionProvider: RevisionProvider? = nil) {
        self.entries = entries
        self.revisionProvider = revisionProvider
    }

    var entriesSnapshot: [RuntimeMemoryEntry] { lock.withLock { entries } }
    var semanticSourceReadCount: Int { lock.withLock { semanticReads } }
    var cachedRecordCount: Int { lock.withLock { semanticCache.count } }
    var cacheWriteCount: Int { lock.withLock { cacheWrites } }
    var memoryMutationCount: Int { lock.withLock { memoryMutations } }

    func list(ownerDeviceID: String?) throws -> [RuntimeMemoryEntry] {
        lock.withLock { entries }
    }

    func exactDuplicateSuggestions(ownerDeviceID: String?) throws -> RuntimeMemoryDuplicateSuggestions {
        try RuntimeMemoryExactDuplicateSuggester.suggestions(from: list(ownerDeviceID: ownerDeviceID))
    }

    func semanticDuplicateSuggestionSources(
        ownerDeviceID: String?,
        limit: Int
    ) throws -> [RuntimeMemorySemanticSearchSource] {
        lock.withLock {
            semanticReads += 1
            let call = semanticReads
            return entries.prefix(limit).map { entry in
                RuntimeMemorySemanticSearchSource(
                    entry: entry,
                    sourceRevision: revisionProvider?(call, entry)
                        ?? RuntimeSemanticMemorySearch.sourceRevision(for: entry)
                )
            }
        }
    }

    func listAll() throws -> [RuntimeMemoryEntry] { try list(ownerDeviceID: nil) }

    func upsert(
        ownerDeviceID: String?,
        id: String?,
        content: String,
        enabled: Bool?,
        source: RuntimeMemoryEntrySource?,
        timestamp: Date
    ) throws -> RuntimeMemoryEntry {
        lock.withLock { memoryMutations += 1 }
        return memoryEntry(
            id: id ?? UUID().uuidString,
            content: content,
            enabled: enabled ?? true,
            source: source,
            timestamp: timestamp
        )
    }

    func delete(
        ownerDeviceID: String?,
        id: String,
        timestamp: Date
    ) throws -> RuntimeMemoryDeleteResult {
        lock.withLock { memoryMutations += 1 }
        return RuntimeMemoryDeleteResult(id: id, deletedAt: timestamp)
    }

    func dismissedMemorySummaryDraftIDs(ownerDeviceID: String?) throws -> Set<String> { [] }

    func dismissMemorySummaryDraft(
        ownerDeviceID: String?,
        draftID: String,
        timestamp: Date
    ) throws -> RuntimeMemorySummaryDraftDismissResult {
        RuntimeMemorySummaryDraftDismissResult(draftID: draftID, dismissedAt: timestamp)
    }

    func generatedMemorySummaryDrafts(ownerDeviceID: String?) throws -> [RuntimeGeneratedMemorySummaryDraft] {
        []
    }

    func listSemanticSearchSources(
        ownerDeviceID: String?,
        limit: Int
    ) throws -> [RuntimeMemorySemanticSearchSource] {
        try semanticDuplicateSuggestionSources(ownerDeviceID: ownerDeviceID, limit: limit)
    }

    func cachedMemorySemanticEmbeddings(
        for keys: [RuntimeMemorySemanticEmbeddingKey]
    ) throws -> [RuntimeMemorySemanticEmbeddingRecord] {
        lock.withLock {
            keys.compactMap { key in
                semanticCache[key].map { RuntimeMemorySemanticEmbeddingRecord(key: key, embedding: $0) }
            }
        }
    }

    func upsertMemorySemanticEmbeddings(
        _ records: [RuntimeMemorySemanticEmbeddingRecord],
        if shouldCommit: @Sendable () -> Bool
    ) throws {
        guard shouldCommit() else { return }
        lock.withLock {
            guard shouldCommit() else { return }
            cacheWrites += 1
            for record in records { semanticCache[record.key] = record.embedding }
        }
    }

    func cacheGeneratedMemorySummaryDraft(
        ownerDeviceID: String?,
        draft: RuntimeGeneratedMemorySummaryDraft
    ) throws -> RuntimeGeneratedMemorySummaryDraft {
        draft
    }
}

private final class SemanticDuplicateBackend: LlmBackend, @unchecked Sendable {
    typealias EmbeddingResponder = @Sendable (EmbeddingRequest, Int) throws -> EmbeddingResult

    let provider: ModelProvider
    private let lock = NSLock()
    private var models: [ModelInfo]
    private var modelListBatches: [[ModelInfo]]
    private var modelListCalls = 0
    private var recordedEmbeddingRequests: [EmbeddingRequest] = []
    private let embeddingResponder: EmbeddingResponder
    private let holdEmbeddings: Bool
    private var heldContinuations: [CheckedContinuation<Void, Never>] = []

    init(
        provider: ModelProvider = .ollama,
        models: [ModelInfo],
        modelListBatches: [[ModelInfo]] = [],
        holdEmbeddings: Bool = false,
        embeddingResponder: @escaping EmbeddingResponder = { request, _ in
            EmbeddingResult(model: request.model, embeddings: request.texts.map { _ in [1, 0] })
        }
    ) {
        self.provider = provider
        self.models = models
        self.modelListBatches = modelListBatches
        self.holdEmbeddings = holdEmbeddings
        self.embeddingResponder = embeddingResponder
    }

    var listModelsCallCount: Int { lock.withLock { modelListCalls } }
    var embeddingRequests: [EmbeddingRequest] { lock.withLock { recordedEmbeddingRequests } }
    var heldEmbeddingCount: Int { lock.withLock { heldContinuations.count } }

    func replaceModels(_ models: [ModelInfo]) {
        lock.withLock { self.models = models }
    }

    func releaseHeldEmbeddings() {
        let continuations = lock.withLock {
            let current = heldContinuations
            heldContinuations.removeAll()
            return current
        }
        continuations.forEach { $0.resume() }
    }

    func healthCheck() async -> BackendStatus { .available }

    func listModels() async throws -> [ModelInfo] {
        lock.withLock {
            modelListCalls += 1
            return modelListBatches.isEmpty ? models : modelListBatches.removeFirst()
        }
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { $0.finish() }
    }

    func embed(request: EmbeddingRequest) async throws -> EmbeddingResult {
        let call = lock.withLock {
            recordedEmbeddingRequests.append(request)
            return recordedEmbeddingRequests.count
        }
        if holdEmbeddings {
            await withCheckedContinuation { continuation in
                lock.withLock { heldContinuations.append(continuation) }
            }
        }
        try Task.checkCancellation()
        return try embeddingResponder(request, call)
    }

    func cancel(generationID: String) -> GenerationCancellationResult {
        .notFound(generationID: generationID)
    }
}

private func embeddingModel(
    revision: String?,
    provider: ModelProvider = .ollama,
    installed: Bool = true,
    source: ModelSource = .local,
    kind: ModelKind = .embedding,
    contextWindowTokens: Int? = 2_048
) -> ModelInfo {
    let persistentRevision = revision.map { value in
        "ollama-sha256:" + SHA256.hash(data: Data(value.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
    }
    return ModelInfo(
        id: "nomic-embed-text",
        name: "nomic-embed-text",
        provider: provider,
        kind: kind,
        capabilities: kind.defaultCapabilities,
        providerModelID: "nomic-embed-text",
        installed: installed,
        source: source,
        contextWindowTokens: contextWindowTokens,
        persistentEmbeddingRevision: persistentRevision
    )
}

private func memoryEntry(
    id: String,
    content: String,
    enabled: Bool = true,
    source: RuntimeMemoryEntrySource? = nil,
    timestamp: Date = Date(timeIntervalSince1970: 1)
) -> RuntimeMemoryEntry {
    RuntimeMemoryEntry(
        id: id,
        content: content,
        enabled: enabled,
        createdAt: timestamp,
        updatedAt: timestamp,
        source: source
    )
}
