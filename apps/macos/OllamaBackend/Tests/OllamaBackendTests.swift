import Foundation
@testable import OllamaBackend
import XCTest

final class OllamaBackendTests: XCTestCase {
    func testOllamaChatUsageWireModeRawValue() {
        XCTAssertEqual(ChatProviderWireMode.ollamaChat.rawValue, "ollama_chat")
    }

    func testModelUnloadResultOutcomesPreserveBooleanGuard() {
        let confirmed = ModelUnloadResult.unloaded(provider: .ollama, modelID: "model")
        let absent = ModelUnloadResult.alreadyAbsent(provider: .ollama, modelID: "model")
        let unsupported = ModelUnloadResult.unsupported(provider: .ollama, modelID: "model")

        XCTAssertEqual(confirmed.outcome, .confirmed)
        XCTAssertEqual(absent.outcome, .alreadyAbsent)
        XCTAssertEqual(unsupported.outcome, .unsupported)
        XCTAssertTrue(confirmed.unloaded)
        XCTAssertTrue(absent.unloaded)
        XCTAssertFalse(unsupported.unloaded)
    }

    override func tearDown() {
        MockURLProtocol.handler = nil
        BoundedStreamingURLProtocol.handler = nil
        BoundedStreamingURLProtocol.onStop = nil
        OllamaShowFanoutURLProtocol.controller = nil
        SuspendingURLProtocol.onStart = nil
        SuspendingURLProtocol.onStop = nil
        SuspendingCatalogURLProtocol.onShowStart = nil
        SuspendingCatalogURLProtocol.onStop = nil
        super.tearDown()
    }

    func testModelInfoCatalogPublicationLimitsAcceptExactBoundariesAndRejectLimitPlusOne() throws {
        XCTAssertEqual(ModelInfo.maximumCatalogModelCount, 256)
        XCTAssertEqual(ModelInfo.maximumCatalogResponseBytes, 4_194_304)
        XCTAssertEqual(ModelInfo.maximumModelIdentityCodePoints, 512)
        XCTAssertEqual(ModelInfo.maximumQualifiedModelIDCodePoints, 522)
        XCTAssertEqual(ModelInfo.maximumCapabilityCount, 32)
        XCTAssertEqual(ModelInfo.maximumCapabilityCodePoints, 128)
        XCTAssertEqual(ModelInfo.maximumSizeBytes, Int64.max)

        let exactIdentity = String(repeating: "m", count: ModelInfo.maximumModelIdentityCodePoints)
        let exactCapability = String(repeating: "c", count: ModelInfo.maximumCapabilityCodePoints)
        let exactModel = ModelInfo(
            id: exactIdentity,
            name: exactIdentity,
            capabilities: [exactCapability],
            providerModelID: exactIdentity,
            sizeBytes: ModelInfo.maximumSizeBytes,
            remoteModel: exactIdentity,
            contextWindowTokens: ModelInfo.maximumContextWindowTokens
        )
        XCTAssertNoThrow(try ModelInfo.validateForCatalogPublication(exactModel))
        XCTAssertNoThrow(try ModelInfo.validateQualifiedModelID(
            String(repeating: "q", count: ModelInfo.maximumQualifiedModelIDCodePoints)
        ))

        var oversizedIdentityModel = exactModel
        oversizedIdentityModel.id.append("x")
        XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(oversizedIdentityModel))

        var oversizedCapabilityModel = exactModel
        oversizedCapabilityModel.capabilities = [exactCapability + "x"]
        XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(oversizedCapabilityModel))

        var paddedCapabilityModel = exactModel
        paddedCapabilityModel.capabilities = [String(repeating: " ", count: 128) + "x"]
        XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(paddedCapabilityModel))

        var duplicateCapabilityModel = exactModel
        duplicateCapabilityModel.capabilities = ["chat", "chat"]
        XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(duplicateCapabilityModel))

        var exactDistinctCapabilitiesModel = exactModel
        exactDistinctCapabilitiesModel.capabilities = [
            "chat",
            " CHAT ",
            "caf\u{00E9}",
            "cafe\u{0301}",
        ]
        XCTAssertNoThrow(try ModelInfo.validateForCatalogPublication(exactDistinctCapabilitiesModel))

        var tooManyCapabilitiesModel = exactModel
        tooManyCapabilitiesModel.capabilities = (0...ModelInfo.maximumCapabilityCount).map { "capability-\($0)" }
        XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(tooManyCapabilitiesModel))

        var invalidSizeModel = exactModel
        invalidSizeModel.sizeBytes = -1
        XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(invalidSizeModel))

        for keyPath in [\ModelInfo.id, \ModelInfo.name, \ModelInfo.providerModelID] {
            var blankIdentityModel = exactModel
            blankIdentityModel[keyPath: keyPath] = " \n\t "
            XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(blankIdentityModel))
        }
        var blankRemoteModel = exactModel
        blankRemoteModel.remoteModel = " \n\t "
        XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(blankRemoteModel))
        let sharedBlankCodePoints =
            "\u{0009}\u{000A}\u{000B}\u{000C}\u{000D}\u{0020}\u{0085}\u{00A0}\u{1680}" +
            "\u{2000}\u{2001}\u{2002}\u{2003}\u{2004}\u{2005}\u{2006}\u{2007}" +
            "\u{2008}\u{2009}\u{200A}\u{200B}\u{2028}\u{2029}\u{202F}\u{205F}" +
            "\u{3000}\u{FEFF}"
        for keyPath in [\ModelInfo.id, \ModelInfo.name, \ModelInfo.providerModelID] {
            var blankIdentityModel = exactModel
            blankIdentityModel[keyPath: keyPath] = sharedBlankCodePoints
            XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(blankIdentityModel))
        }
        var blankSharedCapabilityModel = exactModel
        blankSharedCapabilityModel.capabilities = [sharedBlankCodePoints]
        XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(blankSharedCapabilityModel))
        var blankSharedRemoteModel = exactModel
        blankSharedRemoteModel.remoteModel = sharedBlankCodePoints
        XCTAssertThrowsError(try ModelInfo.validateForCatalogPublication(blankSharedRemoteModel))
        var contentAfterBlankModel = exactModel
        contentAfterBlankModel.name = sharedBlankCodePoints + "x"
        XCTAssertNoThrow(try ModelInfo.validateForCatalogPublication(contentAfterBlankModel))
        XCTAssertThrowsError(try ModelInfo.validateQualifiedModelID(sharedBlankCodePoints))
        XCTAssertThrowsError(try ModelInfo.validateQualifiedModelID(
            String(repeating: "q", count: ModelInfo.maximumQualifiedModelIDCodePoints + 1)
        ))
    }

    func testCatalogStreamingReadAcceptsExactByteLimitAndRejectsLimitPlusOne() async throws {
        let body = #"{"models":[]}"#
        let exactBackend = makeBackend(catalogResponseByteLimit: Data(body.utf8).count) { _ in
            self.response(statusCode: 200, body: body)
        }
        let exactModels = try await exactBackend.listModels()
        XCTAssertEqual(exactModels, [])

        var paths: [String] = []
        let oversizedBackend = makeBackend(catalogResponseByteLimit: Data(body.utf8).count) { request in
            paths.append(request.url?.path ?? "")
            return self.response(statusCode: 200, body: body + " ")
        }
        await assertListModelsResponseDecodingError(from: oversizedBackend, endpoint: "GET /api/tags")
        XCTAssertEqual(paths, ["/api/tags"])
    }

    func testCatalogStreamingReadRejectsOversizedPositiveContentLength() async {
        let backend = makeBackend(catalogResponseByteLimit: 64) { _ in
            self.response(
                statusCode: 200,
                body: #"{"models":[]}"#,
                headers: ["Content-Length": "65"]
            )
        }
        await assertListModelsResponseDecodingError(from: backend, endpoint: "GET /api/tags")
    }

    func testTagsCatalogRejectsInvalidPublicationMetadata() async {
        let invalidRows = [
            #"{"name":"   "}"#,
            "{\"name\":\"\(String(repeating: "m", count: 513))\"}",
            #"{"name":"model","remote_model":" \n\t "}"#,
            "{\"name\":\"model\",\"remote_model\":\"\(String(repeating: "r", count: 513))\"}",
            #"{"name":"model","size":-1}"#,
        ]
        for row in invalidRows {
            await assertCatalogRejected(
                tagsBody: "{\"models\":[\(row)]}",
                runningBody: #"{"models":[]}"#,
                expectedEndpoint: "GET /api/tags"
            )
        }
    }

    func testShowStreamingReadAcceptsExactByteLimitAndExcludesOnlyLimitPlusOneDetail() async throws {
        let limit = 64
        let showJSON = #"{"capabilities":["embedding"]}"#
        let exactShowBody = showJSON + String(repeating: " ", count: limit - Data(showJSON.utf8).count)
        let exactBackend = makeBackend(catalogResponseByteLimit: limit) { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"model"}]}"#)
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                return self.response(statusCode: 200, body: exactShowBody)
            default:
                return self.response(statusCode: 404, body: "{}")
            }
        }
        let exactModels = try await exactBackend.listModels()
        XCTAssertEqual(exactModels.map(\.id), ["model"])

        let oversizedBackend = makeBackend(catalogResponseByteLimit: limit) { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"model"}]}"#)
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                return self.response(statusCode: 200, body: exactShowBody + " ")
            default:
                return self.response(statusCode: 404, body: "{}")
            }
        }
        let oversizedModels = try await oversizedBackend.listModels()
        XCTAssertEqual(oversizedModels, [])
    }

    func testListModelsPropagatesCancellationDuringShowFanout() async {
        let fourRequestsStarted = expectation(description: "four show requests started")
        let loadingStopped = expectation(description: "all active show requests stopped")
        loadingStopped.expectedFulfillmentCount = 4
        let names = (0..<8).map { "cancel-model-\($0)" }
        let controller = OllamaShowFanoutController(modelNames: names)
        controller.onFourActive = { fourRequestsStarted.fulfill() }
        controller.onStop = { loadingStopped.fulfill() }
        let backend = makeShowFanoutBackend(controller: controller)
        let task = Task {
            try await backend.listModels()
        }

        await fulfillment(of: [fourRequestsStarted], timeout: 1)
        XCTAssertEqual(controller.maximumActiveRequestCount, 4)
        task.cancel()

        do {
            _ = try await task.value
            XCTFail("Expected catalog cancellation")
        } catch is CancellationError {
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
        await fulfillment(of: [loadingStopped], timeout: 1)
        XCTAssertEqual(controller.stoppedRequestCount, 4)
    }

    func testListModelsBoundsShowFanoutAtFourAndAppliesOutOfOrderResultsInCatalogOrder() async throws {
        let fourRequestsStarted = expectation(description: "fanout reached four requests")
        let names = (0..<11).map { "ordered-model-\($0)" }
        let controller = OllamaShowFanoutController(modelNames: names)
        controller.onFourActive = { fourRequestsStarted.fulfill() }
        let backend = makeShowFanoutBackend(controller: controller)
        let task = Task { try await backend.listModels() }

        await fulfillment(of: [fourRequestsStarted], timeout: 1)
        XCTAssertEqual(controller.maximumActiveRequestCount, 4)
        controller.releaseHeldRequestsInReverseOrder()

        let models = try await task.value
        XCTAssertEqual(models.map(\.id), names)
        XCTAssertEqual(models.map(\.contextWindowTokens), names.indices.map { 4_096 + $0 })
        XCTAssertEqual(controller.maximumActiveRequestCount, 4)
        XCTAssertNotEqual(controller.completedModelNames, names)
    }

    func testListModelsFanoutKeepsMalformedDetailsUntrustedAndOmitsTransportFailures() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"name":"malformed-detail"},{"name":"transport-detail"}]}"#
                )
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                let posted = try JSONDecoder().decode(
                    PostedShowRequest.self,
                    from: self.requestBodyData(from: request)
                )
                if posted.model == "malformed-detail" {
                    return self.response(statusCode: 200, body: "not-json")
                }
                throw URLError(.networkConnectionLost)
            default:
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()
        XCTAssertEqual(models.map(\.id), ["transport-detail"])
        XCTAssertNil(models.first?.contextWindowTokens)
    }

    func testListModelsAccepts256RowsAndRejects257RowsOrUniqueDetailFanout() async throws {
        let acceptedRows = (0..<ModelInfo.maximumCatalogModelCount).map { "{\"name\":\"model-\($0)\"}" }.joined(separator: ",")
        let acceptedShowCalls = LockedBox(0)
        let acceptedBackend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: "{\"models\":[\(acceptedRows)]}")
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                acceptedShowCalls.withValue { $0 += 1 }
                return self.response(statusCode: 200, body: "{}")
            default:
                return self.response(statusCode: 404, body: "{}")
            }
        }
        let acceptedModels = try await acceptedBackend.listModels()
        XCTAssertEqual(acceptedModels.count, ModelInfo.maximumCatalogModelCount)
        XCTAssertEqual(acceptedShowCalls.snapshot, ModelInfo.maximumCatalogModelCount)

        let rejectedRows = (0...ModelInfo.maximumCatalogModelCount).map { "{\"name\":\"model-\($0)\"}" }.joined(separator: ",")
        let tooManyRowsBackend = makeBackend { _ in
            self.response(statusCode: 200, body: "{\"models\":[\(rejectedRows)]}")
        }
        await assertListModelsResponseDecodingError(from: tooManyRowsBackend, endpoint: "GET /api/tags")

        let installedRows = (0..<128).map { "{\"name\":\"installed-\($0)\"}" }.joined(separator: ",")
        let runningRows = (0..<129).map { "{\"name\":\"running-\($0)\"}" }.joined(separator: ",")
        var rejectedShowCalls = 0
        let fanoutBackend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: "{\"models\":[\(installedRows)]}")
            case "/api/ps":
                return self.response(statusCode: 200, body: "{\"models\":[\(runningRows)]}")
            case "/api/show":
                rejectedShowCalls += 1
                return self.response(statusCode: 200, body: "{}")
            default:
                return self.response(statusCode: 404, body: "{}")
            }
        }
        await assertListModelsResponseDecodingError(from: fanoutBackend, endpoint: "GET /api/tags")
        XCTAssertEqual(rejectedShowCalls, 0)
    }

    func testHealthCheckUsesLocalTagsEndpoint() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/tags")
            return self.response(statusCode: 200, body: #"{"models":[]}"#)
        }

        let status = await backend.healthCheck()

        XCTAssertEqual(status, .available)
    }

    func testHealthCheckRejectsMalformedTagsCatalog() async {
        let backend = makeBackend { _ in
            self.response(statusCode: 200, body: #"{"models":[],"\u006dodels":[]}"#)
        }

        let status = await backend.healthCheck()

        guard case .unavailable(let error) = status else {
            XCTFail("Expected malformed catalog to be unavailable")
            return
        }
        XCTAssertEqual(error.code, "bad_backend_response")
        XCTAssertFalse(error.retryable)
    }

    func testListModelsMergesTagsRunningAndCloudModelsWithoutRecommendedDefaults() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(
                    statusCode: 200,
                    body: """
                    {
                      "models": [
                        {
                          "name": "custom-local:7b",
                          "size": 1234
                        },
                        {
                          "name": "deepseek-v4-pro:cloud",
                          "model": "deepseek-v4-pro:cloud",
                          "remote_model": "deepseek-v4-pro",
                          "remote_host": "https://ollama.com:443",
                          "size": 344,
                          "modified_at": "2026-06-23T09:00:00Z"
                        },
                        {
                          "name": "provider-cloud",
                          "size": 222
                        }
                      ]
                    }
                    """
                )
            case "/api/ps":
                return self.response(
                    statusCode: 200,
                    body: """
                    {
                      "models": [
                        {
                          "name": "deepseek-v4-pro:cloud",
                          "size": 999
                        },
                        {
                          "model": "local-running:latest",
                          "size_vram": 2048
                        },
                        {
                          "name": "ps-only-cloud:cloud",
                          "size": 512
                        }
                      ]
                    }
                    """
                )
            case "/api/show":
                return self.response(
                    statusCode: 200,
                    body: #"{"capabilities":["completion"],"model_info":{"llama.context_length":32768}}"#
                )
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(models.map(\.id), [
            "custom-local:7b",
            "deepseek-v4-pro:cloud",
            "provider-cloud",
            "local-running:latest"
        ])
        XCTAssertEqual(models[0].source, .local)
        XCTAssertTrue(models[0].installed)
        XCTAssertFalse(models[0].running)
        XCTAssertEqual(models[1].source, .cloud)
        XCTAssertTrue(models[1].installed)
        XCTAssertTrue(models[1].running)
        XCTAssertEqual(models[1].remoteModel, "deepseek-v4-pro")
        XCTAssertEqual(models[1].remoteHost, "https://ollama.com:443")
        XCTAssertEqual(models[1].sizeBytes, 344)
        XCTAssertNotNil(models[1].modifiedAt)
        XCTAssertEqual(models[2].source, .cloud)
        XCTAssertTrue(models[2].installed)
        XCTAssertFalse(models[2].running)
        XCTAssertEqual(models[3].source, .local)
        XCTAssertTrue(models[3].installed)
        XCTAssertTrue(models[3].running)
        XCTAssertEqual(models[3].sizeBytes, 2048)
        XCTAssertEqual(models.map(\.kind), [.chat, .chat, .chat, .chat])
        XCTAssertEqual(models[0].capabilities, ["completion"])
        XCTAssertEqual(models[0].contextWindowTokens, 32768)
    }

    func testListModelsUsesShowCapabilitiesToSeparateEmbeddingModels() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"nomic-embed-text","size":10},{"name":"qwen3:8b","size":20}]}"#)
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                let posted = try JSONDecoder().decode(
                    PostedShowRequest.self,
                    from: self.requestBodyData(from: request)
                )
                if posted.model == "nomic-embed-text" {
                    return self.response(
                        statusCode: 200,
                        body: #"{"capabilities":["embedding"],"context_window_tokens":8192}"#
                    )
                }
                return self.response(
                    statusCode: 200,
                    body: #"{"capabilities":["completion"],"parameters":"num_ctx 32768\n"}"#
                )
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(models.first { $0.id == "nomic-embed-text" }?.kind, .embedding)
        XCTAssertEqual(models.first { $0.id == "nomic-embed-text" }?.capabilities, ["embedding"])
        XCTAssertEqual(models.first { $0.id == "nomic-embed-text" }?.contextWindowTokens, 8192)
        XCTAssertEqual(models.first { $0.id == "qwen3:8b" }?.kind, .chat)
        XCTAssertEqual(models.first { $0.id == "qwen3:8b" }?.contextWindowTokens, 32768)
    }

    func testListModelsRejectsDuplicateAndEscapeEquivalentKeysInTagsAndRunningCatalogs() async {
        let cases: [(tags: String, running: String, endpoint: String)] = [
            (#"{"models":[],"models":[]}"#, #"{"models":[]}"#, "GET /api/tags"),
            (#"{"models":[],"\u006dodels":[]}"#, #"{"models":[]}"#, "GET /api/tags"),
            (#"{"models":[]}"#, #"{"models":[],"models":[]}"#, "GET /api/ps"),
            (#"{"models":[]}"#, #"{"models":[],"\u006dodels":[]}"#, "GET /api/ps"),
        ]

        for testCase in cases {
            await assertCatalogRejected(
                tagsBody: testCase.tags,
                runningBody: testCase.running,
                expectedEndpoint: testCase.endpoint
            )
        }
    }

    func testListModelsRejectsDuplicateExactAndCanonicalModelIdentities() async {
        let duplicateExact = #"{"models":[{"name":"plain-model"},{"name":"plain-model"}]}"#
        let duplicateCanonical = #"{"models":[{"name":"plain-model"},{"name":"plain-model:latest"}]}"#

        for body in [duplicateExact, duplicateCanonical] {
            await assertCatalogRejected(
                tagsBody: body,
                runningBody: #"{"models":[]}"#,
                expectedEndpoint: "GET /api/tags"
            )
            await assertCatalogRejected(
                tagsBody: #"{"models":[]}"#,
                runningBody: body,
                expectedEndpoint: "GET /api/ps"
            )
        }
    }

    func testListModelsKeepsByteDistinctUnicodeIdentitiesAcrossCatalogs() async throws {
        let installedName = "caf\u{00E9}"
        let runningName = "cafe\u{0301}"
        let showModelIdentities = LockedBox<[Data]>([])
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(
                    statusCode: 200,
                    body: "{\"models\":[{\"name\":\"\(installedName)\"}]}"
                )
            case "/api/ps":
                return self.response(
                    statusCode: 200,
                    body: "{\"models\":[{\"name\":\"\(runningName)\"}]}"
                )
            case "/api/show":
                let posted = try JSONDecoder().decode(
                    PostedShowRequest.self,
                    from: self.requestBodyData(from: request)
                )
                showModelIdentities.withValue { $0.append(Data(posted.model.utf8)) }
                return self.response(statusCode: 200, body: #"{"capabilities":["chat"]}"#)
            default:
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(
            models.map { Data($0.id.utf8) },
            [Data(installedName.utf8), Data(runningName.utf8)]
        )
        XCTAssertEqual(models.map(\.running), [false, true])
        XCTAssertEqual(
            Set(showModelIdentities.snapshot),
            Set([Data(installedName.utf8), Data(runningName.utf8)])
        )
    }

    func testListModelsPreservesByteDistinctUnicodeCapabilities() async throws {
        let composedCapability = "caf\u{00E9}"
        let decomposedCapability = "cafe\u{0301}"
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"model"}]}"#)
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                return self.response(
                    statusCode: 200,
                    body: "{\"capabilities\":[\"\(composedCapability)\",\"\(decomposedCapability)\"]}"
                )
            default:
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(models.count, 1)
        XCTAssertEqual(
            models[0].capabilities.map { Data($0.utf8) },
            [Data(composedCapability.utf8), Data(decomposedCapability.utf8)]
        )
    }

    func testUnloadModelDoesNotMatchByteDistinctUnicodeRunningIdentity() async throws {
        let requestedName = "caf\u{00E9}"
        let runningName = "cafe\u{0301}"
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            return self.response(
                statusCode: 200,
                body: "{\"models\":[{\"name\":\"\(runningName)\"}]}"
            )
        }

        let result = try await backend.unloadModel(providerModelID: requestedName)

        XCTAssertEqual(result, .alreadyAbsent(provider: .ollama, modelID: requestedName))
        XCTAssertEqual(paths, ["/api/ps"])
    }

    func testListModelsRejectsConflictingNameAndModelIdentityAliases() async {
        let bodies = [
            #"{"models":[{"name":"plain-model","model":"plain-model:latest"}]}"#,
            "{\"models\":[{\"name\":\"caf\u{00E9}\",\"model\":\"cafe\u{0301}\"}]}",
        ]
        for body in bodies {
            await assertCatalogRejected(
                tagsBody: body,
                runningBody: #"{"models":[]}"#,
                expectedEndpoint: "GET /api/tags"
            )
        }
    }

    func testListModelsAcceptsContextWindowBoundariesAndMatchingAliases() async throws {
        let maximum = ModelInfo.maximumContextWindowTokens
        let cases: [(body: String, expected: Int)] = [
            (#"{"context_window_tokens":1}"#, 1),
            ("{\"context_window_tokens\":\(maximum)}", maximum),
            (#"{"context_window_tokens":8192,"context_length":8192,"model_info":{"llama.context_length":8192,"num_ctx":8192},"parameters":"num_ctx 8192\n"}"#, 8_192),
        ]

        for testCase in cases {
            let model = try await modelFromShow(body: testCase.body)
            XCTAssertEqual(model.contextWindowTokens, testCase.expected)
        }
    }

    func testListModelsPreservesValidMissingContextWindowMetadata() async throws {
        let model = try await modelFromShow(body: #"{"capabilities":["embedding"]}"#)

        XCTAssertEqual(model.capabilities, ["embedding"])
        XCTAssertEqual(model.kind, .embedding)
        XCTAssertNil(model.contextWindowTokens)
    }

    func testListModelsOmitsInvalidContextMetadataAndPreservesValidCapabilities() async throws {
        let maximum = ModelInfo.maximumContextWindowTokens
        let invalidBodies = [
            #"{"capabilities":["embedding"],"context_window_tokens":true}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":"8192"}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":1.5}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":16777215.9999999999}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":16777216.0000000001}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":1e999}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":9223372036854775808}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":0}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":-1}"#,
            "{\"capabilities\":[\"embedding\"],\"context_window_tokens\":\(maximum + 1)}",
            #"{"capabilities":["embedding"],"model_info":{"llama.context_length":null}}"#,
            #"{"capabilities":["embedding"],"parameters":"num_ctx 8192.0\n"}"#,
            #"{"capabilities":["embedding"],"parameters":"num_ctx 0\n"}"#,
            "{\"capabilities\":[\"embedding\"],\"parameters\":\"num_ctx \(maximum + 1)\\n\"}",
            #"{"capabilities":["embedding"],"parameters":"num_ctx 9223372036854775808\n"}"#,
        ]

        for body in invalidBodies {
            let models = try await modelsFromShow(body: body)
            guard let model = models.first else {
                XCTFail("Expected valid capabilities to survive invalid context metadata: \(body)")
                continue
            }
            XCTAssertNil(model.contextWindowTokens, "Unexpected context window for: \(body)")
            XCTAssertEqual(model.capabilities, ["embedding"], "Capabilities changed for: \(body)")
            XCTAssertEqual(model.kind, .embedding)
        }
    }

    func testListModelsOmitsConflictingContextMetadataAndPreservesValidCapabilities() async throws {
        let conflictingBodies = [
            #"{"capabilities":["embedding"],"context_window_tokens":8192,"context_length":4096}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":16777216,"context_length":16777215.9999999999}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":8192,"model_info":{"llama.context_length":4096}}"#,
            #"{"capabilities":["embedding"],"model_info":{"llama.context_length":8192,"general.context_length":4096}}"#,
            #"{"capabilities":["embedding"],"model_info":{"llama.context_length":8192},"parameters":"num_ctx 4096\n"}"#,
            #"{"capabilities":["embedding"],"parameters":"num_ctx 8192\nnum_ctx 4096\n"}"#,
        ]

        for body in conflictingBodies {
            let model = try await modelFromShow(body: body)
            XCTAssertNil(model.contextWindowTokens, "Unexpected context window for: \(body)")
            XCTAssertEqual(model.capabilities, ["embedding"], "Capabilities changed for: \(body)")
            XCTAssertEqual(model.kind, .embedding)
        }
    }

    func testListModelsOmitsShowDetailsWithDuplicateOrEscapeEquivalentKeys() async throws {
        let untrustedBodies = [
            #"{"capabilities":["embedding"],"context_length":8192,"context_length":4096}"#,
            #"{"capabilities":["embedding"],"context_length":8192,"\u0063ontext_length":4096}"#,
            #"{"capabilities":["embedding"],"model_info":{"num_ctx":8192,"\u006eum_ctx":4096}}"#,
            #"{"capabilities":["embedding"],"context_window_tokens":NaN}"#,
        ]

        for body in untrustedBodies {
            let models = try await modelsFromShow(body: body)
            XCTAssertTrue(models.isEmpty, "Untrusted model details were admitted for: \(body)")
        }
    }

    func testListModelsExcludesShowDetailsWithInvalidCapabilities() async throws {
        let tooManyCapabilities = (0...ModelInfo.maximumCapabilityCount)
            .map { "\"capability-\($0)\"" }
            .joined(separator: ",")
        let invalidBodies = [
            #"{"capabilities":["   "]}"#,
            #"{"capabilities":["chat"," CHAT "]}"#,
            "{\"capabilities\":[\"\(String(repeating: " ", count: 128))x\"]}",
            "{\"capabilities\":[\(tooManyCapabilities)]}",
        ]

        for body in invalidBodies {
            let models = try await modelsFromShow(body: body)
            XCTAssertTrue(models.isEmpty, "Invalid capability metadata was admitted for: \(body)")
        }
    }

    func testListModelsExposesNamespacedTagsDigestAsPersistentEmbeddingRevision() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"name":"nomic-embed-text:latest","digest":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}]}"#
                )
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                return self.response(statusCode: 200, body: #"{"capabilities":["embedding"]}"#)
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(
            models.first?.persistentEmbeddingRevision,
            "ollama-sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        )
    }

    func testListModelsRejectsNonCanonicalDigestForPersistentEmbeddingRevision() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"name":"nomic-embed-text:latest","digest":"not-a-model-digest"}]}"#
                )
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                return self.response(statusCode: 200, body: #"{"capabilities":["embedding"]}"#)
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertNil(models.first?.persistentEmbeddingRevision)
    }

    func testListModelsLeavesPersistentEmbeddingRevisionNilWithoutTagsDigest() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"nomic-embed-text"}]}"#)
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                return self.response(statusCode: 200, body: #"{"capabilities":["embedding"]}"#)
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertNil(models.first?.persistentEmbeddingRevision)
    }

    func testListModelsDoesNotInventRecommendedDefaultsWhenTagsAreEmpty() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags", "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertTrue(models.isEmpty)
    }

    func testPullModelPostsNonStreamingPullRequest() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/pull")
            XCTAssertEqual(request.httpMethod, "POST")
            let body = try self.requestBodyData(from: request)
            let postedRequest = try JSONDecoder().decode(PostedPullRequest.self, from: body)
            XCTAssertEqual(postedRequest.model, "deepseek-v4-pro:cloud")
            XCTAssertFalse(postedRequest.stream)
            return self.response(statusCode: 200, body: #"{"status":"success"}"#)
        }

        let result = try await backend.pullModel(name: "deepseek-v4-pro:cloud")

        XCTAssertEqual(result, ModelPullResult(model: "deepseek-v4-pro:cloud", status: "success", installed: true))
    }

    func testPullModelBoundedResponseAcceptsExactLimitAndRejectsLimitPlusOne() async throws {
        let body = #"{"status":"success"}"#
        let limit = Data(body.utf8).count
        let exactBackend = makeBackend(
            dataResponseByteLimit: limit,
            dataResponseTimeout: 7.25
        ) { request in
            XCTAssertEqual(request.timeoutInterval, 7.25, accuracy: 0.001)
            return self.response(
                statusCode: 200,
                body: body,
                headers: ["Content-Length": "\(limit)"]
            )
        }
        _ = try await exactBackend.pullModel(name: "bounded-pull")

        let oversizedBackend = makeBackend(dataResponseByteLimit: limit) { _ in
            self.response(
                statusCode: 200,
                body: " " + body,
                headers: ["Content-Length": "\(limit + 1)"]
            )
        }
        await assertOversizedDataResponse(endpoint: "POST /api/pull") {
            _ = try await oversizedBackend.pullModel(name: "oversized-pull")
        }
    }

    func testPullModelBoundedResponsePropagatesCancellation() async {
        await assertNonStreamingRequestCancellation(targetPath: "/api/pull") { backend in
            _ = try await backend.pullModel(name: "cancelled-pull")
        }
    }

    func testPullModelBoundedResponseEnforcesAbsoluteDeadline() async {
        let stopped = expectation(description: "deadline stopped URL task")
        BoundedStreamingURLProtocol.onStop = { request in
            if request.url?.path == "/api/pull" { stopped.fulfill() }
        }
        let backend = makeStreamingBackend(
            dataResponseByteLimit: 64,
            dataResponseTimeout: 0.05,
            streamLimits: OllamaStreamLimits()
        ) { _, urlProtocol in
            urlProtocol.respond(body: Data(), finish: false)
        }

        do {
            _ = try await backend.pullModel(name: "deadline-pull")
            XCTFail("Expected absolute response deadline")
        } catch let error as OllamaBackendError {
            guard case .unreachable(let endpoint, _, _) = error else {
                return XCTFail("Unexpected Ollama error: \(error)")
            }
            XCTAssertEqual(endpoint, "POST /api/pull")
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
        await fulfillment(of: [stopped], timeout: 1)
    }

    func testEmbedPostsBatchWithoutTruncationAndReturnsVectors() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/embed")
            XCTAssertEqual(request.httpMethod, "POST")
            let posted = try JSONDecoder().decode(PostedEmbedRequest.self, from: self.requestBodyData(from: request))
            XCTAssertEqual(posted.model, "nomic-embed-text")
            XCTAssertEqual(posted.input, ["first", "second"])
            XCTAssertFalse(posted.truncate)
            return self.response(
                statusCode: 200,
                body: #"{"model":"nomic-embed-text:latest","embeddings":[[0.1,0.2],[0.3,0.4]]}"#
            )
        }

        let result = try await backend.embed(request: EmbeddingRequest(
            model: "nomic-embed-text",
            texts: ["first", "second"]
        ))

        XCTAssertEqual(result.model, "nomic-embed-text:latest")
        XCTAssertEqual(result.embeddings, [[0.1, 0.2], [0.3, 0.4]])
    }

    func testEmbedBoundedResponseAcceptsExactLimitAndRejectsLimitPlusOne() async throws {
        let body = #"{"model":"embed","embeddings":[[0.1,0.2]]}"#
        let limit = Data(body.utf8).count
        let exactBackend = makeBackend(
            dataResponseByteLimit: limit,
            dataResponseTimeout: 8.5
        ) { request in
            XCTAssertEqual(request.timeoutInterval, 8.5, accuracy: 0.001)
            return self.response(statusCode: 200, body: body)
        }
        _ = try await exactBackend.embed(request: EmbeddingRequest(model: "embed", texts: ["one"]))

        let oversizedBackend = makeBackend(dataResponseByteLimit: limit) { _ in
            self.response(statusCode: 200, body: " " + body)
        }
        await assertOversizedDataResponse(endpoint: "POST /api/embed") {
            _ = try await oversizedBackend.embed(request: EmbeddingRequest(model: "embed", texts: ["one"]))
        }
    }

    func testEmbedBoundedResponsePropagatesCancellation() async {
        await assertNonStreamingRequestCancellation(targetPath: "/api/embed") { backend in
            _ = try await backend.embed(request: EmbeddingRequest(model: "embed", texts: ["one"]))
        }
    }

    func testEmbedRejectsWrongVectorCount() async {
        let backend = makeBackend { _ in
            self.response(statusCode: 200, body: #"{"embeddings":[[0.1,0.2]]}"#)
        }

        do {
            _ = try await backend.embed(request: EmbeddingRequest(model: "embed", texts: ["a", "b"]))
            XCTFail("Expected invalid embedding response")
        } catch let error as OllamaBackendError {
            guard case .responseDecoding(let endpoint, let reason) = error else {
                return XCTFail("Unexpected error: \(error)")
            }
            XCTAssertEqual(endpoint, "POST /api/embed")
            XCTAssertTrue(reason.contains("Expected 2"))
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testEmbedRejectsEmptyOrInconsistentVectors() async {
        let cases: [(body: String, texts: [String])] = [
            (#"{"embeddings":[[]]}"#, ["a"]),
            (#"{"embeddings":[[0.1],[0.2,0.3]]}"#, ["a", "b"]),
        ]
        for testCase in cases {
            let backend = makeBackend { _ in self.response(statusCode: 200, body: testCase.body) }
            do {
                _ = try await backend.embed(request: EmbeddingRequest(model: "embed", texts: testCase.texts))
                XCTFail("Expected invalid embedding response")
            } catch is OllamaBackendError {
                continue
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testDefaultEmbedImplementationReturnsUnsupportedOperation() async {
        let backend = UnsupportedEmbeddingBackend()

        do {
            _ = try await backend.embed(request: EmbeddingRequest(model: "embed", texts: ["text"]))
            XCTFail("Expected unsupported operation")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .ollama)
            XCTAssertEqual(error.code, "unsupported_operation")
            XCTAssertFalse(error.retryable)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testPullModelHTTPStatusReturnsStructuredError() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/pull")
            return self.response(statusCode: 500, body: "pull failed")
        }

        do {
            _ = try await backend.pullModel(name: "gemma3")
            XCTFail("Expected structured error")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(error, .httpStatus(endpoint: "POST /api/pull", statusCode: 500, body: "pull failed"))
            XCTAssertEqual(error.code, "ollama_http_status")
            XCTAssertTrue(error.retryable)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testPullModelOversizedHTTPErrorPreservesStatusWithoutBufferingBody() async {
        let backend = makeBackend(dataResponseByteLimit: 4) { _ in
            self.response(
                statusCode: 503,
                body: "12345",
                headers: ["Content-Length": "5"]
            )
        }

        do {
            _ = try await backend.pullModel(name: "bounded-error")
            XCTFail("Expected bounded HTTP error")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(
                error,
                .httpStatus(endpoint: "POST /api/pull", statusCode: 503, body: nil)
            )
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadModelPostsEmptyChatWithKeepAliveZero() async throws {
        var paths: [String] = []
        var psRequestCount = 0
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/ps":
                psRequestCount += 1
                let body = psRequestCount == 1
                    ? #"{"models":[{"name":"llama3.1:8b"}]}"#
                    : #"{"models":[]}"#
                return self.response(statusCode: 200, body: body)
            case "/api/chat":
                XCTAssertEqual(request.httpMethod, "POST")
                let body = try self.requestBodyData(from: request)
                let postedRequest = try JSONDecoder().decode(PostedUnloadRequest.self, from: body)
                XCTAssertEqual(postedRequest.model, "llama3.1:8b")
                XCTAssertTrue(postedRequest.messages.isEmpty)
                XCTAssertEqual(postedRequest.keepAlive, 0)
                return self.response(statusCode: 200, body: #"{"done":true,"done_reason":"unload"}"#)
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let result = try await backend.unloadModel(providerModelID: "llama3.1:8b")

        XCTAssertEqual(paths, ["/api/ps", "/api/chat", "/api/ps"])
        XCTAssertEqual(result, .unloaded(provider: .ollama, modelID: "llama3.1:8b"))
        XCTAssertEqual(result.outcome, .confirmed)
        XCTAssertTrue(result.unloaded)
    }

    func testUnloadBoundedAcknowledgementAcceptsExactLimitAndRejectsLimitPlusOne() async throws {
        let body = #"{"done":true,"done_reason":"unload"}"#
        let limit = Data(body.utf8).count
        var exactPSCount = 0
        let exactBackend = makeBackend(
            dataResponseByteLimit: limit,
            dataResponseTimeout: 9.75
        ) { request in
            switch request.url?.path {
            case "/api/ps":
                exactPSCount += 1
                return self.response(
                    statusCode: 200,
                    body: exactPSCount == 1 ? #"{"models":[{"name":"model"}]}"# : #"{"models":[]}"#
                )
            case "/api/chat":
                XCTAssertEqual(request.timeoutInterval, 9.75, accuracy: 0.001)
                return self.response(statusCode: 200, body: body)
            default:
                return self.response(statusCode: 404, body: "{}")
            }
        }
        _ = try await exactBackend.unloadModel(providerModelID: "model")

        let oversizedBackend = makeBackend(dataResponseByteLimit: limit) { request in
            switch request.url?.path {
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"model"}]}"#)
            case "/api/chat":
                return self.response(statusCode: 200, body: " " + body)
            default:
                return self.response(statusCode: 404, body: "{}")
            }
        }
        await assertOversizedDataResponse(endpoint: "POST /api/chat") {
            _ = try await oversizedBackend.unloadModel(providerModelID: "model")
        }
    }

    func testUnloadBoundedAcknowledgementPropagatesCancellation() async {
        await assertNonStreamingRequestCancellation(targetPath: "/api/chat") { backend in
            _ = try await backend.unloadModel(providerModelID: "model")
        }
    }

    func testUnloadModelUsesCanonicalRunningTarget() async throws {
        var psRequestCount = 0
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/ps":
                psRequestCount += 1
                return self.response(
                    statusCode: 200,
                    body: psRequestCount == 1 ? #"{"models":[{"name":"gemma3:latest"}]}"# : #"{"models":[]}"#
                )
            case "/api/chat":
                let posted = try JSONDecoder().decode(PostedUnloadRequest.self, from: self.requestBodyData(from: request))
                XCTAssertEqual(posted.model, "gemma3:latest")
                return self.response(statusCode: 200, body: #"{"done":true,"done_reason":"unload"}"#)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let result = try await backend.unloadModel(providerModelID: "gemma3")

        XCTAssertEqual(result.outcome, .confirmed)
    }

    func testUnloadModelReturnsAlreadyAbsentWithoutPosting() async throws {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            return self.response(statusCode: 200, body: #"{"models":[{"name":"other:latest"}]}"#)
        }

        let result = try await backend.unloadModel(providerModelID: "llama3.1:8b")

        XCTAssertEqual(paths, ["/api/ps"])
        XCTAssertEqual(result.outcome, .alreadyAbsent)
        XCTAssertTrue(result.unloaded)
    }

    func testUnloadModelRejectsOversizedRunningCatalogBeforePosting() async {
        let body = #"{"models":[]}"#
        var paths: [String] = []
        let backend = makeBackend(catalogResponseByteLimit: Data(body.utf8).count) { request in
            paths.append(request.url?.path ?? "")
            return self.response(statusCode: 200, body: body + " ")
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "model")
            XCTFail("Expected oversized running catalog rejection")
        } catch let error as OllamaBackendError {
            guard case .responseDecoding(let endpoint, _) = error else {
                return XCTFail("Unexpected error: \(error)")
            }
            XCTAssertEqual(endpoint, "GET /api/ps")
            XCTAssertEqual(paths, ["/api/ps"])
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadModelRejectsDuplicateRunningStateKeysAtInitialLookup() async {
        let malformedBodies = [
            #"{"models":[],"models":[{"name":"llama3.1:8b"}]}"#,
            #"{"models":[{"name":"llama3.1:8b"}],"models":[]}"#,
            #"{"models":[],"m\u006fdels":[{"name":"llama3.1:8b"}]}"#,
        ]

        for body in malformedBodies {
            var paths: [String] = []
            let backend = makeBackend { request in
                paths.append(request.url?.path ?? "")
                return self.response(statusCode: 200, body: body)
            }

            do {
                _ = try await backend.unloadModel(providerModelID: "llama3.1:8b")
                XCTFail("Expected duplicate running-state key rejection")
            } catch let error as OllamaBackendError {
                guard case .responseDecoding = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertEqual(paths, ["/api/ps"])
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelRejectsDuplicateRunningStateKeysDuringPolling() async {
        let malformedBodies = [
            #"{"models":[],"models":[{"name":"llama3.1:8b"}]}"#,
            #"{"models":[{"name":"llama3.1:8b"}],"models":[]}"#,
            #"{"models":[],"m\u006fdels":[{"name":"llama3.1:8b"}]}"#,
        ]

        for body in malformedBodies {
            var psRequestCount = 0
            let backend = makeBackend { request in
                switch request.url?.path {
                case "/api/ps":
                    psRequestCount += 1
                    return self.response(
                        statusCode: 200,
                        body: psRequestCount == 1
                            ? #"{"models":[{"name":"llama3.1:8b"}]}"#
                            : body
                    )
                case "/api/chat":
                    return self.response(statusCode: 200, body: #"{"done":true,"done_reason":"unload"}"#)
                default:
                    return self.response(statusCode: 500, body: "{}")
                }
            }

            do {
                _ = try await backend.unloadModel(providerModelID: "llama3.1:8b")
                XCTFail("Expected duplicate polling-state key rejection")
            } catch let error as OllamaBackendError {
                guard case .responseDecoding = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertEqual(psRequestCount, 2)
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelRejectsMalformedAndFalseAcknowledgements() async {
        let acknowledgementBodies = [
            "not-json",
            #"{"done":false,"done_reason":"unload"}"#,
            #"{"done":true,"done_reason":"stop"}"#,
            #"{"done":true,"done":false,"done_reason":"unload"}"#,
            #"{"done":false,"done":true,"done_reason":"unload"}"#,
        ]

        for acknowledgementBody in acknowledgementBodies {
            let backend = makeBackend { request in
                switch request.url?.path {
                case "/api/ps":
                    return self.response(statusCode: 200, body: #"{"models":[{"name":"llama3.1:8b"}]}"#)
                case "/api/chat":
                    return self.response(statusCode: 200, body: acknowledgementBody)
                default:
                    return self.response(statusCode: 500, body: "{}")
                }
            }

            do {
                _ = try await backend.unloadModel(providerModelID: "llama3.1:8b")
                XCTFail("Expected acknowledgement rejection")
            } catch let error as OllamaBackendError {
                guard case .unloadNotConfirmed = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertEqual(error.code, "ollama_unload_not_confirmed")
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelRejectsPersistentProviderResidencyAfterBoundedPolling() async {
        var paths: [String] = []
        let backend = makeBackend(unloadPollAttempts: 3) { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"llama3.1:8b"}]}"#)
            case "/api/chat":
                return self.response(statusCode: 200, body: #"{"done":true,"done_reason":"unload"}"#)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "llama3.1:8b")
            XCTFail("Expected persistent residency failure")
        } catch let error as OllamaBackendError {
            guard case .unloadNotConfirmed = error else {
                return XCTFail("Unexpected error: \(error)")
            }
            XCTAssertEqual(paths, ["/api/ps", "/api/chat", "/api/ps", "/api/ps", "/api/ps"])
            XCTAssertEqual(error.backendError.code, "model_unload_not_confirmed")
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadModelPollingPropagatesCancellation() async {
        let backend = makeBackend(
            unloadPollAttempts: 3,
            unloadSleeper: { _ in throw CancellationError() }
        ) { request in
            switch request.url?.path {
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"llama3.1:8b"}]}"#)
            case "/api/chat":
                return self.response(statusCode: 200, body: #"{"done":true,"done_reason":"unload"}"#)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "llama3.1:8b")
            XCTFail("Expected cancellation")
        } catch is CancellationError {
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadModelHTTPStatusReturnsStructuredError() async {
        let unsafeBody = "unload denied http://127.0.0.1:11434/api/chat route_token=secret"
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"llama3.1:8b"}]}"#)
            case "/api/chat":
                XCTAssertEqual(request.httpMethod, "POST")
                let body = try self.requestBodyData(from: request)
                let postedRequest = try JSONDecoder().decode(PostedUnloadRequest.self, from: body)
                XCTAssertEqual(postedRequest.model, "llama3.1:8b")
                XCTAssertTrue(postedRequest.messages.isEmpty)
                XCTAssertEqual(postedRequest.keepAlive, 0)
                return self.response(statusCode: 503, body: unsafeBody)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "llama3.1:8b")
            XCTFail("Expected structured unload error")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(error, .httpStatus(endpoint: "POST /api/chat", statusCode: 503, body: unsafeBody))
            XCTAssertEqual(error.code, "ollama_http_status")
            XCTAssertTrue(error.retryable)
            XCTAssertEqual(error.backendError.provider, .ollama)
            XCTAssertFalse(error.backendError.message.contains("127.0.0.1"))
            XCTAssertFalse(error.backendError.message.contains("route_token"))
            XCTAssertFalse(error.backendError.message.contains("/api/chat"))
            XCTAssertFalse(error.localizedDescription.contains("127.0.0.1"))
            XCTAssertFalse(error.localizedDescription.contains("route_token"))
            XCTAssertFalse(error.localizedDescription.contains("/api/chat"))
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadConfirmationFailureBackendErrorIsSanitized() async {
        let unsafeAcknowledgement = #"{"done":false,"done_reason":"http://127.0.0.1:11434/api/chat?route_token=secret"}"#
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"llama3.1:8b"}]}"#)
            case "/api/chat":
                return self.response(statusCode: 200, body: unsafeAcknowledgement)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "llama3.1:8b")
            XCTFail("Expected confirmation failure")
        } catch let error as OllamaBackendError {
            let mapped = error.backendError
            XCTAssertEqual(mapped.code, "model_unload_not_confirmed")
            XCTAssertFalse(mapped.message.contains("127.0.0.1"))
            XCTAssertFalse(mapped.message.contains("route_token"))
            XCTAssertFalse(mapped.message.contains("/api/chat"))
            XCTAssertFalse(error.localizedDescription.contains("127.0.0.1"))
            XCTAssertFalse(error.localizedDescription.contains("route_token"))
            XCTAssertFalse(error.localizedDescription.contains("/api/chat"))
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testChatStreamsOllamaLineDelimitedJSON() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/chat")
            XCTAssertEqual(request.httpMethod, "POST")
            let body = try self.requestBodyData(from: request)
            let postedRequest = try JSONDecoder().decode(PostedChatRequest.self, from: body)
            XCTAssertEqual(postedRequest.model, "llama3.1:8b")
            XCTAssertEqual(postedRequest.messages, [ChatMessage(role: "user", content: "Hi")])
            XCTAssertTrue(postedRequest.stream)
            XCTAssertTrue(postedRequest.think)
            return self.response(
                statusCode: 200,
                body: """
                {"message":{"role":"assistant","content":"Hello "},"done":false}
                {"message":{"role":"assistant","content":"there"},"done":false}
                {"done":true,"prompt_eval_count":3,"eval_count":4}

                """
            )
        }
        let request = ChatRequest(
            generationID: "generation-1",
            sessionID: "session-1",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .delta("Hello "),
            .delta("there"),
            .done(inputTokens: 3, outputTokens: 4)
        ])
        XCTAssertEqual(
            backend.takeProviderUsageSource(generationID: request.generationID),
            ChatProviderUsageSource(
                provider: .ollama,
                providerModelID: "llama3.1:8b",
                wireMode: .ollamaChat
            )
        )
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testChatStreamsThinkingSeparatelyFromContent() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/chat")
            let body = try self.requestBodyData(from: request)
            let postedRequest = try JSONDecoder().decode(PostedChatRequest.self, from: body)
            XCTAssertTrue(postedRequest.think)
            return self.response(
                statusCode: 200,
                body: """
                {"message":{"role":"assistant","thinking":"I should reason first. "},"done":false}
                {"message":{"role":"assistant","thinking":"Now answer. ","content":"Hello"},"done":false}
                {"message":{"role":"assistant","content":" there"},"done":false}
                {"done":true,"prompt_eval_count":5,"eval_count":6}

                """
            )
        }
        let request = ChatRequest(
            generationID: "generation-thinking",
            sessionID: "session-1",
            model: "qwen3:8b",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .reasoningDelta("I should reason first. "),
            .reasoningDelta("Now answer. "),
            .delta("Hello"),
            .delta(" there"),
            .done(inputTokens: 5, outputTokens: 6)
        ])
        XCTAssertEqual(
            backend.takeProviderUsageSource(generationID: request.generationID),
            ChatProviderUsageSource(
                provider: .ollama,
                providerModelID: "qwen3:8b",
                wireMode: .ollamaChat
            )
        )
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testChatStreamsServerSentEventLines() async throws {
        let backend = makeBackend { _ in
            self.response(
                statusCode: 200,
                body: """
                data: {"message":{"role":"assistant","content":"Hello"},"done":false}
                data: {"done":true,"prompt_eval_count":1,"eval_count":2}
                data: [DONE]

                """
            )
        }
        let request = ChatRequest(
            generationID: "generation-sse",
            sessionID: "session-1",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .delta("Hello"),
            .done(inputTokens: 1, outputTokens: 2)
        ])
        XCTAssertEqual(
            backend.takeProviderUsageSource(generationID: request.generationID),
            ChatProviderUsageSource(
                provider: .ollama,
                providerModelID: "llama3.1:8b",
                wireMode: .ollamaChat
            )
        )
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testBoundedLineReaderHonorsResponseAndUnfinishedLineExactLimits() async throws {
        var exactResponse = OllamaBoundedLineReader(
            bytes: byteStream("abcd"),
            responseByteLimit: 4,
            lineByteLimit: 4
        )
        let exactLine = try await exactResponse.next()
        let exactEOF = try await exactResponse.next()
        XCTAssertEqual(exactLine, "abcd")
        XCTAssertNil(exactEOF)

        var oversizedResponse = OllamaBoundedLineReader(
            bytes: byteStream("abcde"),
            responseByteLimit: 4,
            lineByteLimit: 8
        )
        do {
            _ = try await oversizedResponse.next()
            XCTFail("Expected response byte limit rejection")
        } catch {}

        var oversizedLine = OllamaBoundedLineReader(
            bytes: byteStream("abcde"),
            responseByteLimit: 8,
            lineByteLimit: 4
        )
        do {
            _ = try await oversizedLine.next()
            XCTFail("Expected unfinished line limit rejection")
        } catch {}
    }

    func testChatResponseLimitsHonorContentLengthAndNoLengthExactPlusOne() async throws {
        let terminalBody = #"{"done":true}"#
        let byteLimit = Data(terminalBody.utf8).count

        for includesContentLength in [true, false] {
            let exactBackend = makeStreamingBackend(
                streamLimits: OllamaStreamLimits(responseByteLimit: byteLimit)
            ) { _, urlProtocol in
                let headers = includesContentLength ? ["Content-Length": "\(byteLimit)"] : [:]
                urlProtocol.respond(body: Data(terminalBody.utf8), headers: headers, finish: true)
            }
            let exactEvents = try await collect(
                exactBackend.chat(request: chatRequest(id: "exact-\(includesContentLength)"))
            )
            XCTAssertEqual(exactEvents, [
                .done(inputTokens: nil, outputTokens: nil)
            ])

            let stopped = expectation(description: "oversized stream URL task cancelled")
            BoundedStreamingURLProtocol.onStop = { request in
                if request.url?.path == "/api/chat" { stopped.fulfill() }
            }
            let oversizedBody = Data((" " + terminalBody).utf8)
            let oversizedBackend = makeStreamingBackend(
                streamLimits: OllamaStreamLimits(responseByteLimit: byteLimit)
            ) { _, urlProtocol in
                let headers = includesContentLength ? ["Content-Length": "\(byteLimit + 1)"] : [:]
                urlProtocol.respond(body: oversizedBody, headers: headers, finish: false)
            }
            await assertBadChatResponse(from: oversizedBackend, requestID: "oversized-\(includesContentLength)")
            await fulfillment(of: [stopped], timeout: 1)
            BoundedStreamingURLProtocol.onStop = nil
        }
    }

    func testChatRejectsGiantUnterminatedLineAndCancelsURLTask() async {
        let stopped = expectation(description: "giant line URL task cancelled")
        BoundedStreamingURLProtocol.onStop = { request in
            if request.url?.path == "/api/chat" { stopped.fulfill() }
        }
        let backend = makeStreamingBackend(
            streamLimits: OllamaStreamLimits(responseByteLimit: 128, lineByteLimit: 16)
        ) { _, urlProtocol in
            urlProtocol.respond(body: Data(String(repeating: "x", count: 17).utf8), finish: false)
        }

        await assertBadChatResponse(from: backend, requestID: "giant-line")
        await fulfillment(of: [stopped], timeout: 1)
    }

    func testChatRejectsStalledConsumerWhenBoundedEventBufferFills() async {
        let stopped = expectation(description: "backpressure URL task cancelled")
        BoundedStreamingURLProtocol.onStop = { request in
            if request.url?.path == "/api/chat" { stopped.fulfill() }
        }
        let body = """
        {"message":{"content":"one"},"done":false}
        {"message":{"content":"two"},"done":false}
        {"done":true}
        """
        let backend = makeStreamingBackend(
            streamLimits: OllamaStreamLimits(bufferedEventLimit: 1)
        ) { _, urlProtocol in
            urlProtocol.respond(body: Data(body.utf8), finish: false)
        }

        let stream = backend.chat(request: chatRequest(id: "stalled-consumer"))
        await fulfillment(of: [stopped], timeout: 1)
        var events: [ChatStreamEvent] = []
        do {
            for try await event in stream { events.append(event) }
            XCTFail("Expected bounded event buffer rejection")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(error.backendError.code, "bad_backend_response")
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
        XCTAssertEqual(events, [.delta("one")])
    }

    func testChatRejectsAggregateOutputLimitAndCancelsURLTask() async {
        let stopped = expectation(description: "aggregate output URL task cancelled")
        BoundedStreamingURLProtocol.onStop = { request in
            if request.url?.path == "/api/chat" { stopped.fulfill() }
        }
        let backend = makeStreamingBackend(
            streamLimits: OllamaStreamLimits(aggregateAccountingByteLimit: 3)
        ) { _, urlProtocol in
            urlProtocol.respond(
                body: Data((#"{"message":{"content":"four"},"done":false}"# + "\n").utf8),
                finish: false
            )
        }

        await assertBadChatResponse(from: backend, requestID: "aggregate-limit")
        await fulfillment(of: [stopped], timeout: 1)
    }

    func testChatRejectsEmptyAndDeltaEOFWithoutTerminalMarker() async {
        let cases: [(body: String, expectedEvents: [ChatStreamEvent])] = [
            ("", []),
            (#"{"message":{"content":"partial"},"done":false}"#, [.delta("partial")]),
        ]
        for (index, testCase) in cases.enumerated() {
            let backend = makeBackend { _ in
                self.response(statusCode: 200, body: testCase.body)
            }
            var events: [ChatStreamEvent] = []
            do {
                for try await event in backend.chat(request: chatRequest(id: "missing-terminal-\(index)")) {
                    events.append(event)
                }
                XCTFail("Expected terminal-less stream rejection")
            } catch let error as OllamaBackendError {
                guard case .responseDecoding(let endpoint, let reason) = error else {
                    return XCTFail("Unexpected Ollama error: \(error)")
                }
                XCTAssertEqual(endpoint, "POST /api/chat")
                XCTAssertEqual(reason, "The provider stream violated a bounded response contract.")
                XCTAssertEqual(error.backendError.code, "bad_backend_response")
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
            XCTAssertEqual(events, testCase.expectedEvents)
        }
    }

    func testChatCanonicalTerminalMarkerEmitsExactlyOneDone() async throws {
        let backend = makeBackend { _ in
            self.response(
                statusCode: 200,
                body: """
                {"done":true,"prompt_eval_count":1,"eval_count":2}
                {"done":true,"prompt_eval_count":9,"eval_count":9}
                """
            )
        }

        let events = try await collect(backend.chat(request: chatRequest(id: "terminal-once")))
        XCTAssertEqual(events, [
            .done(inputTokens: 1, outputTokens: 2)
        ])
    }

    func testChatRejectsDuplicateTerminalKeysBeforeTypedDecoding() async {
        let backend = makeBackend { _ in
            self.response(statusCode: 200, body: #"{"done":true,"done":false}"#)
        }

        do {
            _ = try await collect(backend.chat(request: chatRequest(id: "duplicate-terminal")))
            XCTFail("Expected duplicate stream key rejection")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(error.code, "ollama_stream_decoding")
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testHTTPStatusReturnsStructuredError() async {
        let backend = makeBackend { _ in
            self.response(statusCode: 503, body: "offline")
        }

        do {
            _ = try await backend.listModels()
            XCTFail("Expected structured error")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(error, .httpStatus(endpoint: "GET /api/tags", statusCode: 503, body: "offline"))
            XCTAssertEqual(error.code, "ollama_http_status")
            XCTAssertTrue(error.retryable)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testHTTPForbiddenMapsToOllamaAccessRequiredBackendError() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/tags")
            return self.response(statusCode: 403, body: "forbidden")
        }

        do {
            _ = try await backend.listModels()
            XCTFail("Expected structured error")
        } catch let error as OllamaBackendError {
            XCTAssertEqual(error, .httpStatus(endpoint: "GET /api/tags", statusCode: 403, body: "forbidden"))
            XCTAssertEqual(error.code, "ollama_auth_required")
            XCTAssertEqual(error.backendError.code, "ollama_auth_required")
            XCTAssertFalse(error.backendError.message.contains("Mac runtime"))
            XCTAssertTrue(error.retryable)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testCancelUnknownGenerationReturnsNotFound() {
        let backend = makeBackend { _ in
            self.response(statusCode: 200, body: "{}")
        }

        XCTAssertEqual(
            backend.cancel(generationID: "missing"),
            .notFound(generationID: "missing")
        )
    }

    func testCancelActiveGenerationCancelsStream() async {
        let requestStarted = expectation(description: "request started")
        let loadingStopped = expectation(description: "loading stopped")
        SuspendingURLProtocol.onStart = { request in
            XCTAssertEqual(request.url?.path, "/api/chat")
            requestStarted.fulfill()
        }
        SuspendingURLProtocol.onStop = {
            loadingStopped.fulfill()
        }

        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [SuspendingURLProtocol.self]
        let session = URLSession(configuration: configuration)
        let backend = OllamaBackend(baseURL: URL(string: "http://127.0.0.1:11434")!, session: session)
        let request = ChatRequest(
            generationID: "generation-cancel",
            sessionID: "session-1",
            model: "llama3.1:8b",
            messages: [ChatMessage(role: "user", content: "Keep going")]
        )

        let streamTask = Task<Error?, Never> {
            do {
                for try await _ in backend.chat(request: request) {}
                return nil
            } catch {
                return error
            }
        }

        await fulfillment(of: [requestStarted], timeout: 1)

        XCTAssertEqual(
            backend.cancel(generationID: "generation-cancel"),
            .cancelled(generationID: "generation-cancel")
        )

        let error = await streamTask.value
        XCTAssertEqual(error as? OllamaBackendError, .generationCancelled(generationID: "generation-cancel"))
        await fulfillment(of: [loadingStopped], timeout: 1)
    }

    func testLiveOllamaConfirmedUnload() async throws {
        let environment = ProcessInfo.processInfo.environment
        guard environment["AETHERLINK_RUN_OLLAMA_LIVE_UNLOAD_TEST"] == "1" else {
            throw XCTSkip("Set AETHERLINK_RUN_OLLAMA_LIVE_UNLOAD_TEST=1 to enable the localhost Ollama unload test.")
        }
        guard let modelID = environment["AETHERLINK_OLLAMA_LIVE_UNLOAD_MODEL_ID"], !modelID.isEmpty else {
            throw XCTSkip("Set AETHERLINK_OLLAMA_LIVE_UNLOAD_MODEL_ID to the exact model to unload.")
        }

        let session = URLSession(configuration: .ephemeral)
        let runningBefore = try await liveOllamaModelNames(path: "api/ps", session: session)
        guard runningBefore.contains(where: { Self.sameOllamaModel($0, modelID) }) else {
            XCTFail("The explicitly selected Ollama model must already be running before this test starts.")
            return
        }

        let result = try await OllamaBackend().unloadModel(providerModelID: modelID)

        XCTAssertEqual(result.outcome, .confirmed)
        let installedAfter = try await liveOllamaModelNames(path: "api/tags", session: session)
        let runningAfter = try await liveOllamaModelNames(path: "api/ps", session: session)
        XCTAssertTrue(installedAfter.contains(where: { Self.sameOllamaModel($0, modelID) }))
        XCTAssertFalse(runningAfter.contains(where: { Self.sameOllamaModel($0, modelID) }))
    }

    private func byteStream(_ value: String) -> AsyncStream<UInt8> {
        AsyncStream { continuation in
            for byte in value.utf8 { continuation.yield(byte) }
            continuation.finish()
        }
    }

    private func chatRequest(id: String) -> ChatRequest {
        ChatRequest(
            generationID: id,
            sessionID: "bounded-stream-session",
            model: "bounded-stream-model",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )
    }

    private func collect(
        _ stream: AsyncThrowingStream<ChatStreamEvent, Error>
    ) async throws -> [ChatStreamEvent] {
        var events: [ChatStreamEvent] = []
        for try await event in stream { events.append(event) }
        return events
    }

    private func assertBadChatResponse(
        from backend: OllamaBackend,
        requestID: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async {
        do {
            _ = try await collect(backend.chat(request: chatRequest(id: requestID)))
            XCTFail("Expected bounded stream rejection", file: file, line: line)
        } catch let error as OllamaBackendError {
            guard case .responseDecoding(let endpoint, let reason) = error else {
                return XCTFail("Unexpected Ollama error: \(error)", file: file, line: line)
            }
            XCTAssertEqual(endpoint, "POST /api/chat", file: file, line: line)
            XCTAssertEqual(
                reason,
                "The provider stream violated a bounded response contract.",
                file: file,
                line: line
            )
            XCTAssertEqual(error.backendError.code, "bad_backend_response", file: file, line: line)
            XCTAssertFalse(error.backendError.message.contains(requestID), file: file, line: line)
        } catch {
            XCTFail("Unexpected error: \(error)", file: file, line: line)
        }
    }

    private func assertOversizedDataResponse(
        endpoint: String,
        file: StaticString = #filePath,
        line: UInt = #line,
        operation: () async throws -> Void
    ) async {
        do {
            try await operation()
            XCTFail("Expected bounded response rejection", file: file, line: line)
        } catch let error as OllamaBackendError {
            guard case .responseDecoding(let actualEndpoint, let reason) = error else {
                return XCTFail("Unexpected Ollama error: \(error)", file: file, line: line)
            }
            XCTAssertEqual(actualEndpoint, endpoint, file: file, line: line)
            XCTAssertEqual(
                reason,
                "The provider response exceeds the supported byte limit.",
                file: file,
                line: line
            )
        } catch {
            XCTFail("Unexpected error: \(error)", file: file, line: line)
        }
    }

    private func assertNonStreamingRequestCancellation(
        targetPath: String,
        file: StaticString = #filePath,
        line: UInt = #line,
        operation: @escaping (OllamaBackend) async throws -> Void
    ) async {
        let started = expectation(description: "\(targetPath) started")
        let stopped = expectation(description: "\(targetPath) stopped")
        BoundedStreamingURLProtocol.onStop = { request in
            if request.url?.path == targetPath { stopped.fulfill() }
        }
        let backend = makeStreamingBackend(
            dataResponseByteLimit: 64,
            dataResponseTimeout: 11,
            streamLimits: OllamaStreamLimits()
        ) { request, urlProtocol in
            switch request.url?.path {
            case "/api/ps":
                urlProtocol.respond(
                    body: Data(#"{"models":[{"name":"model"}]}"#.utf8),
                    finish: true
                )
            case targetPath:
                XCTAssertEqual(request.timeoutInterval, 11, accuracy: 0.001, file: file, line: line)
                urlProtocol.respond(body: Data(), finish: false)
                started.fulfill()
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")", file: file, line: line)
            }
        }
        let task = Task {
            try await operation(backend)
        }

        await fulfillment(of: [started], timeout: 1)
        task.cancel()
        do {
            try await task.value
            XCTFail("Expected cancellation", file: file, line: line)
        } catch is CancellationError {
        } catch {
            XCTFail("Unexpected cancellation error: \(error)", file: file, line: line)
        }
        await fulfillment(of: [stopped], timeout: 1)
    }

    private func makeStreamingBackend(
        dataResponseByteLimit: Int = 32 * 1_024 * 1_024,
        dataResponseTimeout: TimeInterval = 60,
        streamLimits: OllamaStreamLimits,
        handler: @escaping (URLRequest, BoundedStreamingURLProtocol) -> Void
    ) -> OllamaBackend {
        BoundedStreamingURLProtocol.handler = handler
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [BoundedStreamingURLProtocol.self]
        return OllamaBackend(
            baseURL: URL(string: "http://127.0.0.1:11434")!,
            session: URLSession(configuration: configuration),
            unloadPollAttempts: 3,
            dataResponseByteLimit: dataResponseByteLimit,
            dataResponseTimeout: dataResponseTimeout,
            streamLimits: streamLimits
        )
    }

    private func makeShowFanoutBackend(controller: OllamaShowFanoutController) -> OllamaBackend {
        OllamaShowFanoutURLProtocol.controller = controller
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [OllamaShowFanoutURLProtocol.self]
        return OllamaBackend(
            baseURL: URL(string: "http://127.0.0.1:11434")!,
            session: URLSession(configuration: configuration)
        )
    }

    private func makeBackend(
        unloadPollAttempts: Int = 3,
        catalogResponseByteLimit: Int = ModelInfo.maximumCatalogResponseBytes,
        dataResponseByteLimit: Int = 32 * 1_024 * 1_024,
        dataResponseTimeout: TimeInterval = 60,
        streamLimits: OllamaStreamLimits = OllamaStreamLimits(),
        unloadSleeper: @escaping @Sendable (UInt64) async throws -> Void = { _ in },
        handler: @escaping (URLRequest) throws -> (HTTPURLResponse, Data)
    ) -> OllamaBackend {
        MockURLProtocol.handler = handler
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: configuration)
        return OllamaBackend(
            baseURL: URL(string: "http://127.0.0.1:11434")!,
            session: session,
            unloadPollAttempts: unloadPollAttempts,
            catalogResponseByteLimit: catalogResponseByteLimit,
            dataResponseByteLimit: dataResponseByteLimit,
            dataResponseTimeout: dataResponseTimeout,
            streamLimits: streamLimits,
            unloadSleeper: unloadSleeper
        )
    }

    private func assertListModelsResponseDecodingError(
        from backend: OllamaBackend,
        endpoint: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async {
        do {
            _ = try await backend.listModels()
            XCTFail("Expected catalog rejection", file: file, line: line)
        } catch let error as OllamaBackendError {
            guard case .responseDecoding(let actualEndpoint, _) = error else {
                return XCTFail("Unexpected Ollama error: \(error)", file: file, line: line)
            }
            XCTAssertEqual(actualEndpoint, endpoint, file: file, line: line)
        } catch {
            XCTFail("Unexpected error: \(error)", file: file, line: line)
        }
    }

    private func assertCatalogRejected(
        tagsBody: String,
        runningBody: String,
        expectedEndpoint: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: tagsBody)
            case "/api/ps":
                return self.response(statusCode: 200, body: runningBody)
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")", file: file, line: line)
                return self.response(statusCode: 404, body: "{}")
            }
        }

        do {
            _ = try await backend.listModels()
            XCTFail("Expected catalog rejection", file: file, line: line)
        } catch let error as OllamaBackendError {
            guard case .responseDecoding(let endpoint, _) = error else {
                XCTFail("Unexpected Ollama error: \(error)", file: file, line: line)
                return
            }
            XCTAssertEqual(endpoint, expectedEndpoint, file: file, line: line)
        } catch {
            XCTFail("Unexpected error: \(error)", file: file, line: line)
        }
    }

    private func modelFromShow(body: String) async throws -> ModelInfo {
        let models = try await modelsFromShow(body: body)
        return try XCTUnwrap(models.first)
    }

    private func modelsFromShow(body: String) async throws -> [ModelInfo] {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/tags":
                return self.response(statusCode: 200, body: #"{"models":[{"name":"plain-model"}]}"#)
            case "/api/ps":
                return self.response(statusCode: 200, body: #"{"models":[]}"#)
            case "/api/show":
                return self.response(statusCode: 200, body: body)
            default:
                XCTFail("Unexpected request path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 404, body: "{}")
            }
        }
        return try await backend.listModels()
    }

    private func liveOllamaModelNames(path: String, session: URLSession) async throws -> [String] {
        let url = OllamaBackend.defaultBaseURL.appending(path: path)
        let (data, response) = try await session.data(from: url)
        let http = try XCTUnwrap(response as? HTTPURLResponse)
        XCTAssertTrue((200..<300).contains(http.statusCode))
        let object = try JSONSerialization.jsonObject(with: data)
        let payload = try XCTUnwrap(object as? [String: Any])
        let models = try XCTUnwrap(payload["models"] as? [[String: Any]])
        return models.compactMap { ($0["name"] as? String) ?? ($0["model"] as? String) }
    }

    private static func sameOllamaModel(_ lhs: String, _ rhs: String) -> Bool {
        func canonical(_ value: String) -> String {
            value.hasSuffix(":latest") ? String(value.dropLast(":latest".count)) : value
        }
        return lhs == rhs || canonical(lhs) == canonical(rhs)
    }

    private func response(
        statusCode: Int,
        body: String,
        headers: [String: String] = [:]
    ) -> (HTTPURLResponse, Data) {
        let url = URL(string: "http://127.0.0.1:11434")!
        var responseHeaders = ["Content-Type": "application/json"]
        responseHeaders.merge(headers) { _, new in new }
        let response = HTTPURLResponse(
            url: url,
            statusCode: statusCode,
            httpVersion: "HTTP/1.1",
            headerFields: responseHeaders
        )!
        return (response, Data(body.utf8))
    }

    private func requestBodyData(from request: URLRequest) throws -> Data {
        if let body = request.httpBody {
            return body
        }

        guard let bodyStream = request.httpBodyStream else {
            return try XCTUnwrap(nil as Data?)
        }

        bodyStream.open()
        defer { bodyStream.close() }

        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 4096)
        while bodyStream.hasBytesAvailable {
            let readCount = bodyStream.read(&buffer, maxLength: buffer.count)
            if readCount < 0 {
                throw bodyStream.streamError ?? URLError(.cannotDecodeContentData)
            }
            if readCount == 0 {
                break
            }
            data.append(buffer, count: readCount)
        }
        return data
    }
}

private struct PostedChatRequest: Decodable {
    var model: String
    var messages: [ChatMessage]
    var stream: Bool
    var think: Bool
}

private struct PostedPullRequest: Decodable {
    var model: String
    var stream: Bool
}

private struct PostedShowRequest: Decodable {
    var model: String
}

private struct PostedEmbedRequest: Decodable {
    var model: String
    var input: [String]
    var truncate: Bool
}

private struct PostedUnloadRequest: Decodable {
    var model: String
    var messages: [ChatMessage]
    var keepAlive: Int

    enum CodingKeys: String, CodingKey {
        case model
        case messages
        case keepAlive = "keep_alive"
    }
}

private final class UnsupportedEmbeddingBackend: LlmBackend, @unchecked Sendable {
    let provider = ModelProvider.ollama

    func healthCheck() async -> BackendStatus { .available }
    func listModels() async throws -> [ModelInfo] { [] }
    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { $0.finish() }
    }
    func cancel(generationID: String) -> GenerationCancellationResult {
        .notFound(generationID: generationID)
    }
}

private final class LockedBox<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var value: Value

    init(_ value: Value) {
        self.value = value
    }

    var snapshot: Value {
        lock.lock()
        defer { lock.unlock() }
        return value
    }

    func withValue(_ body: (inout Value) -> Void) {
        lock.lock()
        defer { lock.unlock() }
        body(&value)
    }
}

private final class OllamaShowFanoutController: @unchecked Sendable {
    let modelNames: [String]
    var onFourActive: (() -> Void)?
    var onStop: (() -> Void)?

    private let lock = NSLock()
    private var pending: [(name: String, urlProtocol: OllamaShowFanoutURLProtocol)] = []
    private var released = false
    private var didNotifyFourActive = false
    private var activeRequestCount = 0
    private var maximumActive = 0
    private var stopped = 0
    private var completed: [String] = []

    init(modelNames: [String]) {
        self.modelNames = modelNames
    }

    var maximumActiveRequestCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return maximumActive
    }

    var stoppedRequestCount: Int {
        lock.lock()
        defer { lock.unlock() }
        return stopped
    }

    var completedModelNames: [String] {
        lock.lock()
        defer { lock.unlock() }
        return completed
    }

    func startShow(_ urlProtocol: OllamaShowFanoutURLProtocol, modelName: String) {
        lock.lock()
        activeRequestCount += 1
        maximumActive = max(maximumActive, activeRequestCount)
        let respondImmediately = released
        if !respondImmediately {
            pending.append((modelName, urlProtocol))
        }
        let notifyFourActive = activeRequestCount == 4 && !didNotifyFourActive
        if notifyFourActive { didNotifyFourActive = true }
        lock.unlock()

        if notifyFourActive { onFourActive?() }
        if respondImmediately {
            urlProtocol.completeShow(body: showBody(for: modelName), modelName: modelName)
        }
    }

    func releaseHeldRequestsInReverseOrder() {
        lock.lock()
        released = true
        let held = pending.sorted {
            (modelNames.firstIndex(of: $0.name) ?? 0) > (modelNames.firstIndex(of: $1.name) ?? 0)
        }
        pending.removeAll()
        lock.unlock()

        for item in held {
            item.urlProtocol.completeShow(body: showBody(for: item.name), modelName: item.name)
        }
    }

    func finishShow(
        _ urlProtocol: OllamaShowFanoutURLProtocol,
        modelName: String,
        cancelled: Bool
    ) {
        lock.lock()
        pending.removeAll { $0.urlProtocol === urlProtocol }
        activeRequestCount = max(0, activeRequestCount - 1)
        if cancelled {
            stopped += 1
        } else {
            completed.append(modelName)
        }
        lock.unlock()
        if cancelled { onStop?() }
    }

    func tagsBody() -> Data {
        let rows = modelNames.map { "{\"name\":\"\($0)\"}" }.joined(separator: ",")
        return Data("{\"models\":[\(rows)]}".utf8)
    }

    private func showBody(for modelName: String) -> Data {
        let index = modelNames.firstIndex(of: modelName) ?? 0
        return Data("{\"capabilities\":[\"chat\"],\"context_window_tokens\":\(4_096 + index)}".utf8)
    }
}

private final class OllamaShowFanoutURLProtocol: URLProtocol {
    static var controller: OllamaShowFanoutController?

    private let stateLock = NSLock()
    private var showModelName: String?
    private var didFinishShow = false

    override class func canInit(with request: URLRequest) -> Bool { true }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let controller = Self.controller else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        switch request.url?.path {
        case "/api/tags":
            complete(body: controller.tagsBody())
        case "/api/ps":
            complete(body: Data(#"{"models":[]}"#.utf8))
        case "/api/show":
            do {
                let posted = try JSONDecoder().decode(PostedShowRequest.self, from: requestBodyData())
                stateLock.lock()
                showModelName = posted.model
                stateLock.unlock()
                controller.startShow(self, modelName: posted.model)
            } catch {
                client?.urlProtocol(self, didFailWithError: error)
            }
        default:
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
        }
    }

    override func stopLoading() {
        stateLock.lock()
        let modelName = showModelName
        let shouldFinish = modelName != nil && !didFinishShow
        if shouldFinish { didFinishShow = true }
        stateLock.unlock()
        if shouldFinish, let modelName {
            Self.controller?.finishShow(self, modelName: modelName, cancelled: true)
        }
    }

    func completeShow(body: Data, modelName: String) {
        stateLock.lock()
        let shouldFinish = !didFinishShow
        if shouldFinish { didFinishShow = true }
        stateLock.unlock()
        guard shouldFinish else { return }

        complete(body: body)
        Self.controller?.finishShow(self, modelName: modelName, cancelled: false)
    }

    private func complete(body: Data) {
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "http://127.0.0.1:11434")!,
            statusCode: 200,
            httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }

    private func requestBodyData() throws -> Data {
        if let body = request.httpBody { return body }
        guard let stream = request.httpBodyStream else { throw URLError(.cannotDecodeContentData) }
        stream.open()
        defer { stream.close() }
        var result = Data()
        var buffer = [UInt8](repeating: 0, count: 1_024)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: buffer.count)
            guard count >= 0 else { throw stream.streamError ?? URLError(.cannotDecodeContentData) }
            guard count > 0 else { break }
            result.append(buffer, count: count)
        }
        return result
    }
}

private final class BoundedStreamingURLProtocol: URLProtocol {
    static var handler: ((URLRequest, BoundedStreamingURLProtocol) -> Void)?
    static var onStop: ((URLRequest) -> Void)?

    private let stateLock = NSLock()
    private var didStop = false

    override class func canInit(with request: URLRequest) -> Bool { true }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = Self.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        handler(request, self)
    }

    override func stopLoading() {
        stateLock.lock()
        let shouldNotify = !didStop
        didStop = true
        stateLock.unlock()
        if shouldNotify { Self.onStop?(request) }
    }

    func respond(
        statusCode: Int = 200,
        body: Data,
        headers: [String: String] = [:],
        finish: Bool
    ) {
        var responseHeaders = ["Content-Type": "application/x-ndjson"]
        responseHeaders.merge(headers) { _, new in new }
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "http://127.0.0.1:11434")!,
            statusCode: statusCode,
            httpVersion: "HTTP/1.1",
            headerFields: responseHeaders
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        if !body.isEmpty { client?.urlProtocol(self, didLoad: body) }
        if finish { client?.urlProtocolDidFinishLoading(self) }
    }
}

private final class MockURLProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let handler = Self.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }

        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}

private final class SuspendingURLProtocol: URLProtocol {
    static var onStart: ((URLRequest) -> Void)?
    static var onStop: (() -> Void)?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "http://127.0.0.1:11434")!,
            statusCode: 200,
            httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/x-ndjson"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        Self.onStart?(request)
    }

    override func stopLoading() {
        Self.onStop?()
    }
}

private final class SuspendingCatalogURLProtocol: URLProtocol {
    static var onShowStart: (() -> Void)?
    static var onStop: (() -> Void)?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "http://127.0.0.1:11434")!,
            statusCode: 200,
            httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        switch request.url?.path {
        case "/api/tags":
            client?.urlProtocol(
                self,
                didLoad: Data(#"{"models":[{"name":"model"}]}"#.utf8)
            )
            client?.urlProtocolDidFinishLoading(self)
        case "/api/ps":
            client?.urlProtocol(self, didLoad: Data(#"{"models":[]}"#.utf8))
            client?.urlProtocolDidFinishLoading(self)
        case "/api/show":
            Self.onShowStart?()
        default:
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
        }
    }

    override func stopLoading() {
        if request.url?.path == "/api/show" {
            Self.onStop?()
        }
    }
}
