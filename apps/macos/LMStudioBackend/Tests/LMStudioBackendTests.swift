import Foundation
@testable import LMStudioBackend
import OllamaBackend
import XCTest

final class LMStudioBackendTests: XCTestCase {
    func testLMStudioUsageWireModeRawValues() {
        XCTAssertEqual(ChatProviderWireMode.lmStudioNative.rawValue, "lmstudio_native")
        XCTAssertEqual(ChatProviderWireMode.lmStudioOpenAICompatible.rawValue, "lmstudio_openai_compat")
    }

    override func tearDown() {
        MockURLProtocol.handler = nil
        super.tearDown()
    }

    func testNativeCatalogStreamingReadAcceptsExactByteLimitAndRejectsLimitPlusOneWithoutFallback() async throws {
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
        await assertBadCatalogResponse(from: oversizedBackend, endpoint: "GET /api/v1/models")
        XCTAssertEqual(paths, ["/api/v1/models"])
    }

    func testFallbackCatalogStreamingReadAcceptsExactByteLimitAndRejectsLimitPlusOne() async throws {
        let fallbackBody = #"{"data":[]}"#
        let limit = Data(fallbackBody.utf8).count
        let exactBackend = makeBackend(catalogResponseByteLimit: limit) { request in
            if request.url?.path == "/api/v1/models" {
                return self.response(statusCode: 404, body: "x")
            }
            return self.response(statusCode: 200, body: fallbackBody)
        }
        let exactModels = try await exactBackend.listModels()
        XCTAssertEqual(exactModels, [])

        let oversizedBackend = makeBackend(catalogResponseByteLimit: limit) { request in
            if request.url?.path == "/api/v1/models" {
                return self.response(statusCode: 404, body: "x")
            }
            return self.response(statusCode: 200, body: fallbackBody + " ")
        }
        await assertBadCatalogResponse(from: oversizedBackend, endpoint: "GET /v1/models")
    }

    func testNativeCatalogRejectsOversizedPositiveContentLengthWithoutFallback() async {
        var paths: [String] = []
        let backend = makeBackend(catalogResponseByteLimit: 64) { request in
            paths.append(request.url?.path ?? "")
            return self.response(
                statusCode: 200,
                body: #"{"models":[]}"#,
                headers: ["Content-Length": "65"]
            )
        }

        await assertBadCatalogResponse(from: backend, endpoint: "GET /api/v1/models")
        XCTAssertEqual(paths, ["/api/v1/models"])
    }

    func testNativeCatalogAccepts256RowsAndRejects257Rows() async throws {
        let acceptedRows = (0..<ModelInfo.maximumCatalogModelCount).map { "{\"key\":\"model-\($0)\"}" }.joined(separator: ",")
        let acceptedBackend = makeBackend { _ in
            self.response(statusCode: 200, body: "{\"models\":[\(acceptedRows)]}")
        }
        let acceptedModels = try await acceptedBackend.listModels()
        XCTAssertEqual(acceptedModels.count, ModelInfo.maximumCatalogModelCount)

        let rejectedRows = (0...ModelInfo.maximumCatalogModelCount).map { "{\"key\":\"model-\($0)\"}" }.joined(separator: ",")
        var paths: [String] = []
        let rejectedBackend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            return self.response(statusCode: 200, body: "{\"models\":[\(rejectedRows)]}")
        }
        await assertBadCatalogResponse(from: rejectedBackend, endpoint: "GET /api/v1/models")
        XCTAssertEqual(paths, ["/api/v1/models"])
    }

    func testNativeCatalogRejectsInvalidPublicationMetadataWithoutFallback() async {
        let invalidBodies = [
            #"{"models":[{"key":"   "}]}"#,
            "{\"models\":[{\"key\":\"\(String(repeating: "m", count: 513))\"}]}",
            #"{"models":[{"key":"model","display_name":" \n\t "}]}"#,
            #"{"models":[{"key":"model","size_bytes":-1}]}"#,
            "{\"models\":[{\"key\":\"model\",\"type\":\"\(String(repeating: " ", count: 128))x\"}]}",
        ]
        for body in invalidBodies {
            var paths: [String] = []
            let backend = makeBackend { request in
                paths.append(request.url?.path ?? "")
                return self.response(statusCode: 200, body: body)
            }
            await assertBadCatalogResponse(from: backend, endpoint: "GET /api/v1/models")
            XCTAssertEqual(paths, ["/api/v1/models"])
        }
    }

    func testHealthCheckUsesNativeLocalModelsEndpoint() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.host, "127.0.0.1")
            XCTAssertEqual(request.url?.port, 1234)
            XCTAssertEqual(request.url?.path, "/api/v1/models")
            return self.response(statusCode: 200, body: #"{"models":[]}"#)
        }

        let status = await backend.healthCheck()

        XCTAssertEqual(status, .available)
    }

    func testListModelsParsesNativeLocalLLMAndEmbeddingModelsSeparately() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/v1/models")
            return self.response(
                statusCode: 200,
                body: """
                {
                  "models": [
                    {
                      "type": "llm",
                      "publisher": "google",
                      "key": "google/gemma-4-26b-a4b",
                      "display_name": "Gemma 4 26B A4B",
                      "size_bytes": 17990911801,
                      "context_length": 131072,
                      "loaded_instances": [{"id": "google/gemma-4-26b-a4b"}]
                    },
                    {
                      "type": "embedding",
                      "key": "text-embedding-nomic",
                      "display_name": "Nomic Embed",
                      "loaded_instances": []
                    }
                  ]
                }
                """
            )
        }

        let models = try await backend.listModels()

        XCTAssertEqual(models.count, 2)
        XCTAssertEqual(models.first?.id, "google/gemma-4-26b-a4b")
        XCTAssertEqual(models.first?.name, "Gemma 4 26B A4B")
        XCTAssertEqual(models.first?.provider, .lmStudio)
        XCTAssertEqual(models.first?.kind, .chat)
        XCTAssertEqual(models.first?.capabilities, ["chat"])
        XCTAssertEqual(models.first?.providerModelID, "google/gemma-4-26b-a4b")
        XCTAssertEqual(models.first?.sizeBytes, 17990911801)
        XCTAssertEqual(models.first?.contextWindowTokens, 131072)
        XCTAssertEqual(models.first?.source, .local)
        XCTAssertTrue(models.first?.installed == true)
        XCTAssertTrue(models.first?.running == true)
        XCTAssertEqual(models.last?.id, "text-embedding-nomic")
        XCTAssertEqual(models.last?.name, "Nomic Embed")
        XCTAssertEqual(models.last?.kind, .embedding)
        XCTAssertEqual(models.last?.capabilities, ["embedding"])
    }

    func testListModelsFallsBackToOpenAICompatibleModels() async throws {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 404, body: "missing")
            case "/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"object":"list","data":[{"id":"loaded-local-model","object":"model","context_window_tokens":32768},{"id":"text-embedding-nomic","object":"model"}]}"#
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(paths, ["/api/v1/models", "/v1/models"])
        XCTAssertEqual(models.map(\.id), ["loaded-local-model", "text-embedding-nomic"])
        XCTAssertEqual(models.map(\.provider), [.lmStudio, .lmStudio])
        XCTAssertEqual(models.map(\.kind), [.chat, .embedding])
        XCTAssertEqual(models.map(\.capabilities), [["chat"], ["embedding"]])
        XCTAssertEqual(models.first?.contextWindowTokens, 32768)
    }

    func testListModelsFallsBackForExplicitNativeEndpointIncompatibility() async throws {
        for statusCode in [405, 501] {
            var paths: [String] = []
            let backend = makeBackend { request in
                paths.append(request.url?.path ?? "")
                switch request.url?.path {
                case "/api/v1/models":
                    return self.response(statusCode: statusCode, body: "unsupported")
                case "/v1/models":
                    return self.response(statusCode: 200, body: #"{"data":[{"id":"fallback-model"}]}"#)
                default:
                    return self.response(statusCode: 500, body: "{}")
                }
            }

            let models = try await backend.listModels()

            XCTAssertEqual(paths, ["/api/v1/models", "/v1/models"])
            XCTAssertEqual(models.map(\.id), ["fallback-model"])
        }
    }

    func testListModelsDoesNotFallbackForNativeAuthClientOrServerFailures() async {
        for statusCode in [400, 401, 403, 422, 500, 503] {
            var paths: [String] = []
            let backend = makeBackend { request in
                paths.append(request.url?.path ?? "")
                return self.response(statusCode: statusCode, body: "failure")
            }

            do {
                _ = try await backend.listModels()
                XCTFail("Expected HTTP \(statusCode) rejection")
            } catch let error as LMStudioBackendError {
                guard case .httpStatus(_, let actualStatusCode, _) = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertEqual(actualStatusCode, statusCode)
                XCTAssertEqual(paths, ["/api/v1/models"])
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testListModelsDoesNotFallbackForNativeTransportFailure() async {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            throw URLError(.timedOut)
        }

        do {
            _ = try await backend.listModels()
            XCTFail("Expected transport rejection")
        } catch let error as LMStudioBackendError {
            guard case .unavailable = error else {
                return XCTFail("Unexpected error: \(error)")
            }
            XCTAssertEqual(paths, ["/api/v1/models"])
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testListModelsRejectsDuplicateAndEscapeEquivalentNativeObjectKeysWithoutFallback() async {
        let bodies = [
            #"{"models":[],"models":[]}"#,
            #"{"models":[],"mod\u0065ls":[]}"#,
        ]
        for body in bodies {
            var paths: [String] = []
            let backend = makeBackend { request in
                paths.append(request.url?.path ?? "")
                return self.response(statusCode: 200, body: body)
            }

            await assertBadCatalogResponse(from: backend, endpoint: "GET /api/v1/models")
            XCTAssertEqual(paths, ["/api/v1/models"])
        }
    }

    func testListModelsRejectsDuplicateAndEscapeEquivalentFallbackObjectKeys() async {
        let bodies = [
            #"{"data":[],"data":[]}"#,
            #"{"data":[],"d\u0061ta":[]}"#,
        ]
        for body in bodies {
            var paths: [String] = []
            let backend = makeBackend { request in
                paths.append(request.url?.path ?? "")
                if request.url?.path == "/api/v1/models" {
                    return self.response(statusCode: 404, body: "missing")
                }
                return self.response(statusCode: 200, body: body)
            }

            await assertBadCatalogResponse(from: backend, endpoint: "GET /v1/models")
            XCTAssertEqual(paths, ["/api/v1/models", "/v1/models"])
        }
    }

    func testListModelsRejectsExactAndCanonicalDuplicateModelIdentities() async {
        let nativeBodies = [
            #"{"models":[{"key":"duplicate"},{"key":"duplicate"}]}"#,
            #"{"models":[{"key":"caf\u00e9"},{"key":"cafe\u0301"}]}"#,
        ]
        for body in nativeBodies {
            let backend = makeBackend { _ in self.response(statusCode: 200, body: body) }
            await assertBadCatalogResponse(from: backend, endpoint: "GET /api/v1/models")
        }

        let fallbackBodies = [
            #"{"data":[{"id":"duplicate"},{"id":"duplicate"}]}"#,
            #"{"data":[{"id":"caf\u00e9"},{"id":"cafe\u0301"}]}"#,
        ]
        for body in fallbackBodies {
            let backend = makeBackend { request in
                if request.url?.path == "/api/v1/models" {
                    return self.response(statusCode: 404, body: "missing")
                }
                return self.response(statusCode: 200, body: body)
            }
            await assertBadCatalogResponse(from: backend, endpoint: "GET /v1/models")
        }
    }

    func testListModelsRejectsConflictingNativeModelIdentityAliases() async {
        let bodies = [
            #"{"models":[{"key":"model-a","id":"model-b"}]}"#,
            "{\"models\":[{\"key\":\"caf\u{00E9}\",\"id\":\"cafe\u{0301}\"}]}",
        ]
        for body in bodies {
            let backend = makeBackend { _ in
                self.response(statusCode: 200, body: body)
            }

            await assertBadCatalogResponse(from: backend, endpoint: "GET /api/v1/models")
        }
    }

    func testListModelsAcceptsExactIntegralContextAliasesAtSharedCeiling() async throws {
        let ceiling = ModelInfo.maximumContextWindowTokens
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 405, body: "unsupported")
            case "/v1/models":
                return self.response(
                    statusCode: 200,
                    body: """
                    {"data":[{"id":"model","context_window_tokens":\(ceiling),"context_length":\(ceiling).0,"max_context_length":1.6777216e7}]}
                    """
                )
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let models = try await backend.listModels()

        XCTAssertEqual(models.first?.contextWindowTokens, ceiling)
    }

    func testListModelsAcceptsMatchingNativeContextAliases() async throws {
        let backend = makeBackend { _ in
            self.response(
                statusCode: 200,
                body: #"{"models":[{"key":"model","context_window_tokens":32768,"context_length":32768.0,"max_context_length":3.2768e4,"n_ctx":32768}]}"#
            )
        }

        let models = try await backend.listModels()

        XCTAssertEqual(models.first?.contextWindowTokens, 32768)
    }

    func testListModelsRejectsInvalidNativeContextWindowValuesWithoutFallback() async {
        let invalidValues = [
            "true",
            #""32768""#,
            "32768.5",
            "16777215.9999999999",
            "16777216.0000000001",
            "NaN",
            "Infinity",
            "-Infinity",
            "1e309",
            "9223372036854775808",
            "0",
            "-1",
            "\(ModelInfo.maximumContextWindowTokens + 1)",
            "null",
        ]
        for invalidValue in invalidValues {
            var paths: [String] = []
            let backend = makeBackend { request in
                paths.append(request.url?.path ?? "")
                let body = #"{"models":[{"key":"model","context_length":\#(invalidValue)}]}"#
                return self.response(statusCode: 200, body: body)
            }

            await assertBadCatalogResponse(from: backend, endpoint: "GET /api/v1/models")
            XCTAssertEqual(paths, ["/api/v1/models"])
        }
    }

    func testListModelsRejectsInvalidFallbackContextWindowValues() async {
        let invalidValues = [
            "true",
            #""32768""#,
            "32768.5",
            "16777215.9999999999",
            "16777216.0000000001",
            "NaN",
            "Infinity",
            "-Infinity",
            "1e309",
            "9223372036854775808",
            "0",
            "-1",
            "\(ModelInfo.maximumContextWindowTokens + 1)",
            "null",
        ]
        for invalidValue in invalidValues {
            let backend = makeBackend { request in
                if request.url?.path == "/api/v1/models" {
                    return self.response(statusCode: 404, body: "missing")
                }
                let body = #"{"data":[{"id":"model","context_length":\#(invalidValue)}]}"#
                return self.response(statusCode: 200, body: body)
            }

            await assertBadCatalogResponse(from: backend, endpoint: "GET /v1/models")
        }
    }

    func testListModelsRejectsConflictingContextWindowAliases() async {
        let nativeBackend = makeBackend { _ in
            self.response(
                statusCode: 200,
                body: #"{"models":[{"key":"model","context_window_tokens":32768,"context_length":65536}]}"#
            )
        }
        await assertBadCatalogResponse(from: nativeBackend, endpoint: "GET /api/v1/models")

        let fallbackBackend = makeBackend { request in
            if request.url?.path == "/api/v1/models" {
                return self.response(statusCode: 404, body: "missing")
            }
            return self.response(
                statusCode: 200,
                body: #"{"data":[{"id":"model","context_window_tokens":32768,"max_context_length":65536}]}"#
            )
        }
        await assertBadCatalogResponse(from: fallbackBackend, endpoint: "GET /v1/models")

        let precisionBackend = makeBackend { _ in
            self.response(
                statusCode: 200,
                body: #"{"models":[{"key":"model","context_window_tokens":16777216,"context_length":16777215.9999999999}]}"#
            )
        }
        await assertBadCatalogResponse(from: precisionBackend, endpoint: "GET /api/v1/models")
    }

    func testEmbedPostsBatchAndRestoresIndexOrder() async throws {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/v1/embeddings")
            XCTAssertEqual(request.httpMethod, "POST")
            let posted = try JSONDecoder().decode(PostedEmbeddingRequest.self, from: self.requestBodyData(from: request))
            XCTAssertEqual(posted.model, "text-embedding-nomic")
            XCTAssertEqual(posted.input, ["first", "second"])
            return self.response(
                statusCode: 200,
                body: #"{"model":"text-embedding-nomic","data":[{"index":1,"embedding":[0.3,0.4]},{"index":0,"embedding":[0.1,0.2]}]}"#
            )
        }

        let result = try await backend.embed(request: EmbeddingRequest(
            model: "text-embedding-nomic",
            texts: ["first", "second"]
        ))

        XCTAssertEqual(result.model, "text-embedding-nomic")
        XCTAssertEqual(result.embeddings, [[0.1, 0.2], [0.3, 0.4]])
    }

    func testEmbedRejectsDuplicateMissingOrOutOfRangeIndexes() async {
        let bodies = [
            #"{"data":[{"index":0,"embedding":[0.1]},{"index":0,"embedding":[0.2]}]}"#,
            #"{"data":[{"index":0,"embedding":[0.1]}]}"#,
            #"{"data":[{"index":0,"embedding":[0.1]},{"index":2,"embedding":[0.2]}]}"#,
        ]
        for body in bodies {
            let backend = makeBackend { _ in self.response(statusCode: 200, body: body) }
            do {
                _ = try await backend.embed(request: EmbeddingRequest(model: "embed", texts: ["a", "b"]))
                XCTFail("Expected invalid embedding indexes")
            } catch is LMStudioBackendError {
                continue
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testEmbedRejectsEmptyOrInconsistentVectors() async {
        let cases: [(body: String, texts: [String])] = [
            (#"{"data":[{"index":0,"embedding":[]}]}"#, ["a"]),
            (#"{"data":[{"index":0,"embedding":[0.1]},{"index":1,"embedding":[0.2,0.3]}]}"#, ["a", "b"]),
        ]
        for testCase in cases {
            let backend = makeBackend { _ in self.response(statusCode: 200, body: testCase.body) }
            do {
                _ = try await backend.embed(request: EmbeddingRequest(model: "embed", texts: testCase.texts))
                XCTFail("Expected invalid embedding vectors")
            } catch is LMStudioBackendError {
                continue
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelPostsLoadedInstanceID() async throws {
        var paths: [String] = []
        var postedInstanceIDs: [String] = []
        var modelRequestCount = 0
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                modelRequestCount += 1
                let instances = modelRequestCount == 1
                    ? #"[{"id":"instance-gemma-a"},{"id":"instance-gemma-b"}]"#
                    : "[]"
                return self.response(
                    statusCode: 200,
                    body: """
                    {
                      "models": [
                        {
                          "type": "llm",
                          "key": "google/gemma-4-26b-a4b",
                          "display_name": "Gemma 4 26B A4B",
                          "loaded_instances": \(instances)
                        }
                      ]
                    }
                    """
                )
            case "/api/v1/models/unload":
                XCTAssertEqual(request.httpMethod, "POST")
                let body = try self.requestBodyData(from: request)
                let posted = try JSONDecoder().decode(PostedUnloadRequest.self, from: body)
                postedInstanceIDs.append(posted.instanceID)
                return self.response(statusCode: 200, body: #"{"instance_id":"\#(posted.instanceID)"}"#)
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let result = try await backend.unloadModel(providerModelID: "google/gemma-4-26b-a4b")

        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/models/unload", "/api/v1/models/unload", "/api/v1/models"])
        XCTAssertEqual(postedInstanceIDs, ["instance-gemma-a", "instance-gemma-b"])
        XCTAssertEqual(result, .unloaded(provider: .lmStudio, modelID: "google/gemma-4-26b-a4b"))
        XCTAssertEqual(result.outcome, .confirmed)
        XCTAssertTrue(result.unloaded)
    }

    func testUnloadModelAcceptsMaximumLoadedInstanceFanout() async throws {
        let instanceIDs = (0..<ModelInfo.maximumCatalogModelCount).map { "instance-\($0)" }
        let instances = instanceIDs.map { #"{"id":"\#($0)"}"# }.joined(separator: ",")
        var modelRequestCount = 0
        var postedInstanceIDs: [String] = []
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                modelRequestCount += 1
                let loadedInstances = modelRequestCount == 1 ? "[\(instances)]" : "[]"
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"key":"model-key","loaded_instances":\#(loadedInstances)}]}"#
                )
            case "/api/v1/models/unload":
                let posted = try JSONDecoder().decode(
                    PostedUnloadRequest.self,
                    from: self.requestBodyData(from: request)
                )
                postedInstanceIDs.append(posted.instanceID)
                return self.response(
                    statusCode: 200,
                    body: #"{"instance_id":"\#(posted.instanceID)"}"#
                )
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let result = try await backend.unloadModel(providerModelID: "model-key")

        XCTAssertEqual(postedInstanceIDs, instanceIDs)
        XCTAssertEqual(result, .unloaded(provider: .lmStudio, modelID: "model-key"))
    }

    func testUnloadModelRejectsInvalidLoadedInstanceFanoutBeforePosting() async {
        let excessiveInstances = (0...ModelInfo.maximumCatalogModelCount)
            .map { #"{"id":"instance-\#($0)"}"# }
            .joined(separator: ",")
        let oversizedInstanceID = String(
            repeating: "i",
            count: ModelInfo.maximumModelIdentityCodePoints + 1
        )
        let canonicallyEquivalentInstances =
            #"[{"id":"caf\#("\u{00E9}")"},{"id":"cafe\#("\u{0301}")"}]"#
        let invalidInstances = [
            "[\(excessiveInstances)]",
            #"[{"id":"duplicate"},{"id":"duplicate"}]"#,
            canonicallyEquivalentInstances,
            #"[{"id":"   "}]"#,
            #"[{"id":"\#(oversizedInstanceID)"}]"#,
        ]

        for instances in invalidInstances {
            var paths: [String] = []
            let backend = makeBackend { request in
                paths.append(request.url?.path ?? "")
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"key":"model-key","loaded_instances":\#(instances)}]}"#
                )
            }

            do {
                _ = try await backend.unloadModel(providerModelID: "model-key")
                XCTFail("Expected invalid loaded-instance fanout rejection")
            } catch let error as LMStudioBackendError {
                guard case .unloadNotConfirmed = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertEqual(paths, ["/api/v1/models"])
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelRejectsInvalidLoadedInstanceMetadataDuringPolling() async {
        let excessiveInstances = (0...ModelInfo.maximumCatalogModelCount)
            .map { #"{"id":"instance-\#($0)"}"# }
            .joined(separator: ",")
        let oversizedInstanceID = String(
            repeating: "i",
            count: ModelInfo.maximumModelIdentityCodePoints + 1
        )
        let canonicallyEquivalentInstances =
            #"[{"id":"caf\#("\u{00E9}")"},{"id":"cafe\#("\u{0301}")"}]"#
        let invalidInstances = [
            "[\(excessiveInstances)]",
            #"[{"id":"duplicate"},{"id":"duplicate"}]"#,
            canonicallyEquivalentInstances,
            #"[{"id":"   "}]"#,
            #"[{"id":"\#(oversizedInstanceID)"}]"#,
        ]

        for instances in invalidInstances {
            var modelRequestCount = 0
            var unloadRequestCount = 0
            let backend = makeBackend { request in
                switch request.url?.path {
                case "/api/v1/models":
                    modelRequestCount += 1
                    let loadedInstances = modelRequestCount == 1
                        ? #"[{"id":"instance-a"}]"#
                        : instances
                    return self.response(
                        statusCode: 200,
                        body: #"{"models":[{"key":"model-key","loaded_instances":\#(loadedInstances)}]}"#
                    )
                case "/api/v1/models/unload":
                    unloadRequestCount += 1
                    return self.response(statusCode: 200, body: #"{"instance_id":"instance-a"}"#)
                default:
                    return self.response(statusCode: 500, body: "{}")
                }
            }

            do {
                _ = try await backend.unloadModel(providerModelID: "model-key")
                XCTFail("Expected invalid polling loaded-instance metadata rejection")
            } catch let error as LMStudioBackendError {
                guard case .unloadNotConfirmed = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertEqual(modelRequestCount, 2)
                XCTAssertEqual(unloadRequestCount, 1)
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelReturnsAlreadyAbsentForMissingModelWithoutRawIDFallback() async throws {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            return self.response(statusCode: 200, body: #"{"models":[]}"#)
        }

        let result = try await backend.unloadModel(providerModelID: "google/gemma-4-26b-a4b")

        XCTAssertEqual(paths, ["/api/v1/models"])
        XCTAssertEqual(result.outcome, .alreadyAbsent)
        XCTAssertTrue(result.unloaded)
    }

    func testUnloadModelRejectsOversizedNativeCatalogBeforePosting() async {
        let body = #"{"models":[]}"#
        var paths: [String] = []
        let backend = makeBackend(catalogResponseByteLimit: Data(body.utf8).count) { request in
            paths.append(request.url?.path ?? "")
            return self.response(statusCode: 200, body: body + " ")
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "model")
            XCTFail("Expected oversized native catalog rejection")
        } catch let error as LMStudioBackendError {
            guard case .unloadNotConfirmed = error else {
                return XCTFail("Unexpected error: \(error)")
            }
            XCTAssertEqual(paths, ["/api/v1/models"])
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadModelReturnsAlreadyAbsentWhenExactModelHasNoInstances() async throws {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            return self.response(
                statusCode: 200,
                body: #"{"models":[{"key":"google/gemma-4-26b-a4b","loaded_instances":[]}]}"#
            )
        }

        let result = try await backend.unloadModel(providerModelID: "google/gemma-4-26b-a4b")

        XCTAssertEqual(paths, ["/api/v1/models"])
        XCTAssertEqual(result.outcome, .alreadyAbsent)
    }

    func testUnloadModelRejectsMissingNullOrDuplicateResidencyAtInitialLookup() async {
        let malformedBodies = [
            #"{"models":[{"key":"model-key"}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":null}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":[]},{"key":"model-key","loaded_instances":[]}]}"#,
            #"{"models":[{"key":"model-key","id":"other","loaded_instances":[{"id":"instance-a"}]}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]},{"key":"other","loaded_instances":[]},{"key":"other","loaded_instances":[]}]}"#,
            "{\"models\":[{\"key\":\"model-key\",\"loaded_instances\":[{\"id\":\"instance-a\"}]},{\"key\":\"caf\u{00E9}\",\"loaded_instances\":[]},{\"key\":\"cafe\u{0301}\",\"loaded_instances\":[]}]}",
            #"{"models":[{"key":"model-key","loaded_instances":[],"loaded_instances":[{"id":"instance-a"}]}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}],"loaded_instances":[]}]}"#,
            #"{"models":[],"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]}],"models":[]}"#,
        ]

        for body in malformedBodies {
            var paths: [String] = []
            let backend = makeBackend { request in
                paths.append(request.url?.path ?? "")
                return self.response(statusCode: 200, body: body)
            }

            do {
                _ = try await backend.unloadModel(providerModelID: "model-key")
                XCTFail("Expected malformed residency rejection")
            } catch let error as LMStudioBackendError {
                guard case .unloadNotConfirmed = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertEqual(paths, ["/api/v1/models"])
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelRejectsMissingNullOrDuplicateResidencyDuringPolling() async {
        let malformedBodies = [
            #"{"models":[{"key":"model-key"}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":null}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":[]},{"key":"model-key","loaded_instances":[]}]}"#,
            #"{"models":[{"key":"model-key","id":"other","loaded_instances":[{"id":"instance-a"}]}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]},{"key":"other","loaded_instances":[]},{"key":"other","loaded_instances":[]}]}"#,
            "{\"models\":[{\"key\":\"model-key\",\"loaded_instances\":[{\"id\":\"instance-a\"}]},{\"key\":\"caf\u{00E9}\",\"loaded_instances\":[]},{\"key\":\"cafe\u{0301}\",\"loaded_instances\":[]}]}",
            #"{"models":[{"key":"model-key","loaded_instances":[],"loaded_instances":[{"id":"instance-a"}]}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}],"loaded_instances":[]}]}"#,
            #"{"models":[],"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]}]}"#,
            #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]}],"models":[]}"#,
        ]

        for body in malformedBodies {
            var modelRequestCount = 0
            let backend = makeBackend { request in
                switch request.url?.path {
                case "/api/v1/models":
                    modelRequestCount += 1
                    if modelRequestCount == 1 {
                        return self.response(
                            statusCode: 200,
                            body: #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]}]}"#
                        )
                    }
                    return self.response(statusCode: 200, body: body)
                case "/api/v1/models/unload":
                    return self.response(statusCode: 200, body: #"{"instance_id":"instance-a"}"#)
                default:
                    return self.response(statusCode: 500, body: "{}")
                }
            }

            do {
                _ = try await backend.unloadModel(providerModelID: "model-key")
                XCTFail("Expected malformed polling residency rejection")
            } catch let error as LMStudioBackendError {
                guard case .unloadNotConfirmed = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertEqual(modelRequestCount, 2)
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelResolvesExactKeyOnly() async throws {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            return self.response(
                statusCode: 200,
                body: #"{"models":[{"key":"google/gemma-4-26b-a4b","display_name":"Gemma 4","loaded_instances":[{"id":"instance-gemma"}]}]}"#
            )
        }

        let result = try await backend.unloadModel(providerModelID: "Gemma 4")

        XCTAssertEqual(paths, ["/api/v1/models"])
        XCTAssertEqual(result.outcome, .alreadyAbsent)
    }

    func testUnloadModelReturnsUnsupportedWhenNativeAPIRequiresFallback() async throws {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            return self.response(statusCode: 404, body: "native API unavailable")
        }

        let result = try await backend.unloadModel(providerModelID: "google/gemma-4-26b-a4b")

        XCTAssertEqual(paths, ["/api/v1/models"])
        XCTAssertEqual(result.outcome, .unsupported)
        XCTAssertFalse(result.unloaded)
    }

    func testUnloadModelDoesNotConfirmWhenNativeStateFallsBackDuringPolling() async {
        var modelRequestCount = 0
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                modelRequestCount += 1
                if modelRequestCount == 1 {
                    return self.response(
                        statusCode: 200,
                        body: #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]}]}"#
                    )
                }
                return self.response(statusCode: 404, body: "native API unavailable")
            case "/api/v1/models/unload":
                return self.response(statusCode: 200, body: #"{"instance_id":"instance-a"}"#)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "model-key")
            XCTFail("Expected native-state confirmation failure")
        } catch let error as LMStudioBackendError {
            guard case .unloadNotConfirmed = error else {
                return XCTFail("Unexpected error: \(error)")
            }
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadModelRejectsMalformedAndMismatchedInstanceAcknowledgements() async {
        let acknowledgements = [
            "not-json",
            #"{"instance_id":"different-instance"}"#,
            "{\"instance_id\":\"cafe\u{0301}\"}",
            #"{"instance_id":"exact-instance","instance_id":"different-instance"}"#,
            #"{"instance_id":"different-instance","instance_id":"exact-instance"}"#,
        ]
        for acknowledgement in acknowledgements {
            let requestedInstanceID = acknowledgement.contains("cafe")
                ? "caf\u{00E9}"
                : "exact-instance"
            let backend = makeBackend { request in
                switch request.url?.path {
                case "/api/v1/models":
                    return self.response(
                        statusCode: 200,
                        body: #"{"models":[{"key":"model-key","loaded_instances":[{"id":"\#(requestedInstanceID)"}]}]}"#
                    )
                case "/api/v1/models/unload":
                    return self.response(statusCode: 200, body: acknowledgement)
                default:
                    return self.response(statusCode: 500, body: "{}")
                }
            }

            do {
                _ = try await backend.unloadModel(providerModelID: "model-key")
                XCTFail("Expected acknowledgement rejection")
            } catch let error as LMStudioBackendError {
                guard case .unloadNotConfirmed = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertEqual(error.code, "lm_studio_unload_not_confirmed")
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    func testUnloadModelRejectsPartialMultipleInstanceAcknowledgement() async {
        var postedInstanceIDs: [String] = []
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"},{"id":"instance-b"},{"id":"instance-c"}]}]}"#
                )
            case "/api/v1/models/unload":
                let posted = try JSONDecoder().decode(PostedUnloadRequest.self, from: self.requestBodyData(from: request))
                postedInstanceIDs.append(posted.instanceID)
                let acknowledged = posted.instanceID == "instance-a" ? posted.instanceID : "wrong-instance"
                return self.response(statusCode: 200, body: #"{"instance_id":"\#(acknowledged)"}"#)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "model-key")
            XCTFail("Expected partial acknowledgement failure")
        } catch let error as LMStudioBackendError {
            guard case .unloadNotConfirmed = error else {
                return XCTFail("Unexpected error: \(error)")
            }
            XCTAssertEqual(postedInstanceIDs, ["instance-a", "instance-b"])
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadModelRejectsPersistentProviderResidencyAfterBoundedPolling() async {
        var paths: [String] = []
        let backend = makeBackend(unloadPollAttempts: 3) { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]}]}"#
                )
            case "/api/v1/models/unload":
                return self.response(statusCode: 200, body: #"{"instance_id":"instance-a"}"#)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "model-key")
            XCTFail("Expected persistent residency failure")
        } catch let error as LMStudioBackendError {
            guard case .unloadNotConfirmed = error else {
                return XCTFail("Unexpected error: \(error)")
            }
            XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/models/unload", "/api/v1/models", "/api/v1/models", "/api/v1/models"])
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
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]}]}"#
                )
            case "/api/v1/models/unload":
                return self.response(statusCode: 200, body: #"{"instance_id":"instance-a"}"#)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "model-key")
            XCTFail("Expected cancellation")
        } catch is CancellationError {
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadModelHTTPStatusReturnsStructuredError() async {
        var paths: [String] = []
        let unsafeBody = "unload denied http://127.0.0.1:1234/api/v1/models/unload route_token=secret"
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: """
                    {
                      "models": [
                        {
                          "type": "llm",
                          "key": "google/gemma-4-26b-a4b",
                          "display_name": "Gemma 4 26B A4B",
                          "loaded_instances": [{"id": "instance-gemma"}]
                        }
                      ]
                    }
                    """
                )
            case "/api/v1/models/unload":
                XCTAssertEqual(request.httpMethod, "POST")
                let body = try self.requestBodyData(from: request)
                let posted = try JSONDecoder().decode(PostedUnloadRequest.self, from: body)
                XCTAssertEqual(posted.instanceID, "instance-gemma")
                return self.response(statusCode: 503, body: unsafeBody)
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "google/gemma-4-26b-a4b")
            XCTFail("Expected structured unload error")
        } catch let error as LMStudioBackendError {
            XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/models/unload"])
            XCTAssertEqual(error, .httpStatus(endpoint: "POST /api/v1/models/unload", statusCode: 503, body: unsafeBody))
            XCTAssertEqual(error.code, "lm_studio_http_status")
            XCTAssertTrue(error.retryable)
            XCTAssertEqual(error.backendError.provider, .lmStudio)
            XCTAssertFalse(error.backendError.message.contains("127.0.0.1"))
            XCTAssertFalse(error.backendError.message.contains("route_token"))
            XCTAssertFalse(error.backendError.message.contains("/api/v1/models/unload"))
            XCTAssertFalse(error.localizedDescription.contains("127.0.0.1"))
            XCTAssertFalse(error.localizedDescription.contains("route_token"))
            XCTAssertFalse(error.localizedDescription.contains("/api/v1/models/unload"))
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testUnloadConfirmationFailureBackendErrorIsSanitized() async {
        let unsafeInstanceID = "http://127.0.0.1:1234/api/v1/models/unload?route_token=secret"
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"key":"model-key","loaded_instances":[{"id":"instance-a"}]}]}"#
                )
            case "/api/v1/models/unload":
                return self.response(statusCode: 200, body: #"{"instance_id":"\#(unsafeInstanceID)"}"#)
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }

        do {
            _ = try await backend.unloadModel(providerModelID: "model-key")
            XCTFail("Expected confirmation failure")
        } catch let error as LMStudioBackendError {
            let mapped = error.backendError
            XCTAssertEqual(mapped.code, "model_unload_not_confirmed")
            XCTAssertFalse(mapped.message.contains("127.0.0.1"))
            XCTAssertFalse(mapped.message.contains("route_token"))
            XCTAssertFalse(mapped.message.contains("/api/v1/models/unload"))
            XCTAssertFalse(error.localizedDescription.contains("127.0.0.1"))
            XCTAssertFalse(error.localizedDescription.contains("route_token"))
            XCTAssertFalse(error.localizedDescription.contains("/api/v1/models/unload"))
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testChatStreamsNativeServerSentEvents() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"qwen-local","display_name":"Qwen Local","loaded_instances":[{"id":"qwen-local"}]}]}"#)
            case "/api/v1/chat":
                XCTAssertEqual(request.httpMethod, "POST")
                let body = try self.requestBodyData(from: request)
                let posted = try JSONDecoder().decode(PostedNativeChatRequest.self, from: body)
                XCTAssertEqual(posted.model, "qwen-local")
                XCTAssertTrue(posted.stream)
                XCTAssertFalse(posted.store)
                XCTAssertEqual(posted.input.map(\.type), ["message"])
                XCTAssertEqual(posted.input.map(\.role), ["user"])
                XCTAssertEqual(posted.input.map(\.content), ["Hi"])
                return self.response(
                    statusCode: 200,
                    body: """
                    event: chat.start
                    data: {"type":"chat.start","model_instance_id":"qwen-local"}

                    event: message.delta
                    data: {"type":"message.delta","content":"Hello "}

                    event: message.delta
                    data: {"type":"message.delta","content":"there"}

                    event: chat.end
                    data: {"type":"chat.end","result":{"model_instance_id":"qwen-local","output":[{"type":"message","content":"Hello there"}],"stats":{"input_tokens":3,"total_output_tokens":4}}}

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-1",
            sessionID: "session-1",
            model: "qwen-local",
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
            ChatProviderUsageSource(provider: .lmStudio, providerModelID: "qwen-local", wireMode: .lmStudioNative)
        )
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testChatStreamsFinalNativeJSONLineWithoutTrailingBlankSeparator() async throws {
        let terminalPayload = #"{"type":"chat.end","result":{"model_instance_id":"qwen-local","output":[],"stats":{"input_tokens":2,"total_output_tokens":1}}}"#
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"key":"qwen-local"}]}"#)
            case "/api/v1/chat":
                return self.response(
                    statusCode: 200,
                    body: "event: chat.end\ndata: \(terminalPayload)"
                )
            default:
                return self.response(statusCode: 500, body: "{}")
            }
        }
        let request = ChatRequest(
            generationID: "lm-final-line",
            sessionID: "session-final-line",
            model: "qwen-local",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [.done(inputTokens: 2, outputTokens: 1)])
    }

    func testChatStreamsNativeReasoningSeparatelyFromAnswerContent() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"reasoning-local","loaded_instances":[{"id":"reasoning-local"}]}]}"#)
            case "/api/v1/chat":
                return self.response(
                    statusCode: 200,
                    body: """
                    event: chat.start
                    data: {"type":"chat.start","model_instance_id":"reasoning-local"}

                    event: message.delta
                    data: {"type":"message.delta","reasoning_content":"Plan first. "}

                    event: message.delta
                    data: {"type":"message.delta","thinking":"Then answer. ","content":"Hello"}

                    event: chat.end
                    data: {"type":"chat.end","result":{"model_instance_id":"reasoning-local","output":[{"type":"message","content":"Hello"}],"stats":{"input_tokens":4,"total_output_tokens":1}}}

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-reasoning-native",
            sessionID: "session-1",
            model: "reasoning-local",
            messages: [ChatMessage(role: "user", content: "Think")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .reasoningDelta("Plan first. "),
            .reasoningDelta("Then answer. "),
            .delta("Hello"),
            .done(inputTokens: 4, outputTokens: 1)
        ])
        XCTAssertEqual(
            backend.takeProviderUsageSource(generationID: request.generationID),
            ChatProviderUsageSource(provider: .lmStudio, providerModelID: "reasoning-local", wireMode: .lmStudioNative)
        )
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testChatFallsBackToOpenAICompatibleStreamingWhenNativeChatShapeFails() async throws {
        var paths: [String] = []
        var postedPayload: [String: Any]?
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"qwen-local","loaded_instances":[]}]}"#)
            case "/api/v1/chat":
                return self.response(statusCode: 422, body: "native rejected")
            case "/v1/chat/completions":
                let body = try self.requestBodyData(from: request)
                postedPayload = try JSONSerialization.jsonObject(with: body) as? [String: Any]
                return self.response(
                    statusCode: 200,
                    body: """
                    data: {"choices":[{"delta":{"content":"Fallback"},"finish_reason":null}]}
                    data: {"choices":[{"delta":{"content":" stream"},"finish_reason":null}]}
                    data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
                    data: {"choices":[],"usage":{"prompt_tokens":2,"completion_tokens":3}}
                    data: [DONE]

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-fallback",
            sessionID: "session-1",
            model: "qwen-local",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/chat", "/v1/chat/completions"])
        XCTAssertEqual(events, [
            .delta("Fallback"),
            .delta(" stream"),
            .done(inputTokens: 2, outputTokens: 3)
        ])
        XCTAssertEqual(
            backend.takeProviderUsageSource(generationID: request.generationID),
            ChatProviderUsageSource(
                provider: .lmStudio,
                providerModelID: "qwen-local",
                wireMode: .lmStudioOpenAICompatible
            )
        )
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
        let streamOptions = try XCTUnwrap(postedPayload?["stream_options"] as? [String: Any])
        XCTAssertEqual(streamOptions["include_usage"] as? Bool, true)
    }

    func testChatDoesNotFallbackAfterMalformedNativeStreamEmitsContent() async {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"qwen-local","loaded_instances":[]}]}"#)
            case "/api/v1/chat":
                return self.response(
                    statusCode: 200,
                    body: """
                    event: message.delta
                    data: {"type":"message.delta","content":"Native"}

                    event: message.delta
                    data: not-json

                    """
                )
            case "/v1/chat/completions":
                XCTFail("Malformed native output must not trigger a second provider dispatch")
                return self.response(statusCode: 500, body: "{}")
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }
        let request = ChatRequest(
            generationID: "lm-generation-malformed-native",
            sessionID: "session-1",
            model: "qwen-local",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        do {
            for try await event in backend.chat(request: request) {
                events.append(event)
            }
            XCTFail("Expected malformed native stream rejection")
        } catch let error as LMStudioBackendError {
            XCTAssertEqual(error.code, "lm_studio_stream_decoding")
        } catch {
            XCTFail("Unexpected error: \(error)")
        }

        XCTAssertEqual(events, [.delta("Native")])
        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/chat"])
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testChatRejectsNativeStreamEOFWithoutTerminalAndDoesNotFallback() async {
        var paths: [String] = []
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"qwen-local","loaded_instances":[]}]}"#)
            case "/api/v1/chat":
                return self.response(
                    statusCode: 200,
                    body: """
                    event: message.delta
                    data: {"type":"message.delta","content":"Native"}

                    """
                )
            case "/v1/chat/completions":
                XCTFail("A terminal-less native stream must not trigger a second provider dispatch")
                return self.response(statusCode: 500, body: "{}")
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }
        let request = ChatRequest(
            generationID: "lm-generation-native-eof",
            sessionID: "session-1",
            model: "qwen-local",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        var events: [ChatStreamEvent] = []
        do {
            for try await event in backend.chat(request: request) {
                events.append(event)
            }
            XCTFail("Expected terminal-less native stream rejection")
        } catch let error as LMStudioBackendError {
            XCTAssertEqual(error.code, "lm_studio_bad_response")
        } catch {
            XCTFail("Unexpected error: \(error)")
        }

        XCTAssertEqual(events, [.delta("Native")])
        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/chat"])
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testChatStreamsOpenAICompatibleReasoningSeparatelyFromAnswerContent() async throws {
        let backend = makeBackend { request in
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(statusCode: 200, body: #"{"models":[{"type":"llm","key":"reasoning-openai","loaded_instances":[]}]}"#)
            case "/api/v1/chat":
                return self.response(statusCode: 422, body: "native rejected")
            case "/v1/chat/completions":
                return self.response(
                    statusCode: 200,
                    body: """
                    data: {"choices":[{"delta":{"reasoning_content":"Plan. "},"finish_reason":null}]}
                    data: {"choices":[{"delta":{"thinking":"Check. ","content":"Answer"},"finish_reason":null}]}
                    data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
                    data: {"choices":[],"usage":{"prompt_tokens":3,"completion_tokens":2}}

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-reasoning-openai",
            sessionID: "session-1",
            model: "reasoning-openai",
            messages: [ChatMessage(role: "user", content: "Think")]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(events, [
            .reasoningDelta("Plan. "),
            .reasoningDelta("Check. "),
            .delta("Answer"),
            .done(inputTokens: 3, outputTokens: 2)
        ])
        XCTAssertEqual(
            backend.takeProviderUsageSource(generationID: request.generationID),
            ChatProviderUsageSource(
                provider: .lmStudio,
                providerModelID: "reasoning-openai",
                wireMode: .lmStudioOpenAICompatible
            )
        )
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testChatWithImageAttachmentUsesNativeImageInput() async throws {
        var paths: [String] = []
        var postedRequest: PostedNativeChatRequest?
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"type":"vision","key":"vision-local","loaded_instances":[]}]}"#
                )
            case "/api/v1/chat":
                let body = try self.requestBodyData(from: request)
                postedRequest = try JSONDecoder().decode(PostedNativeChatRequest.self, from: body)
                return self.response(
                    statusCode: 200,
                    body: """
                    event: chat.start
                    data: {"type":"chat.start","model_instance_id":"vision-local"}

                    event: message.delta
                    data: {"type":"message.delta","content":"Vision"}

                    event: chat.end
                    data: {"type":"chat.end","result":{"model_instance_id":"vision-local","output":[{"type":"message","content":"Vision"}],"stats":{"input_tokens":5,"total_output_tokens":1}}}

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-vision",
            sessionID: "session-1",
            model: "vision-local",
            messages: [
                ChatMessage(
                    role: "user",
                    content: "Describe this image.",
                    attachments: [
                        ChatAttachment(
                            type: "image",
                            mimeType: "image/png",
                            name: "diagram.png",
                            dataBase64: "iVBORw0KGgo="
                        )
                    ]
                )
            ]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/chat"])
        XCTAssertEqual(events, [
            .delta("Vision"),
            .done(inputTokens: 5, outputTokens: 1)
        ])
        XCTAssertEqual(
            backend.takeProviderUsageSource(generationID: request.generationID),
            ChatProviderUsageSource(provider: .lmStudio, providerModelID: "vision-local", wireMode: .lmStudioNative)
        )
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))

        let payload = try XCTUnwrap(postedRequest)
        XCTAssertEqual(payload.model, "vision-local")
        XCTAssertTrue(payload.stream)
        XCTAssertFalse(payload.store)
        XCTAssertEqual(payload.input.count, 2)
        XCTAssertEqual(payload.input[0].type, "message")
        XCTAssertEqual(payload.input[0].role, "user")
        XCTAssertEqual(payload.input[0].content, "Describe this image.")
        XCTAssertNil(payload.input[0].dataURL)
        XCTAssertEqual(payload.input[1].type, "image")
        XCTAssertNil(payload.input[1].role)
        XCTAssertNil(payload.input[1].content)
        XCTAssertEqual(payload.input[1].dataURL, "data:image/png;base64,iVBORw0KGgo=")
    }

    func testChatWithImageAttachmentFallsBackToOpenAICompatibleVisionContentWhenNativeRejects() async throws {
        var paths: [String] = []
        var postedPayload: [String: Any]?
        let backend = makeBackend { request in
            paths.append(request.url?.path ?? "")
            switch request.url?.path {
            case "/api/v1/models":
                return self.response(
                    statusCode: 200,
                    body: #"{"models":[{"type":"vision","key":"vision-local","loaded_instances":[]}]}"#
                )
            case "/api/v1/chat":
                return self.response(statusCode: 422, body: "native rejected")
            case "/v1/chat/completions":
                let body = try self.requestBodyData(from: request)
                postedPayload = try JSONSerialization.jsonObject(with: body) as? [String: Any]
                return self.response(
                    statusCode: 200,
                    body: """
                    data: {"choices":[{"delta":{"content":"Vision"},"finish_reason":null}]}
                    data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
                    data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":1}}
                    data: [DONE]

                    """
                )
            default:
                XCTFail("Unexpected path: \(request.url?.path ?? "nil")")
                return self.response(statusCode: 500, body: "{}")
            }
        }

        let request = ChatRequest(
            generationID: "lm-generation-vision-fallback",
            sessionID: "session-1",
            model: "vision-local",
            messages: [
                ChatMessage(
                    role: "user",
                    content: "Describe this image.",
                    attachments: [
                        ChatAttachment(
                            type: "image",
                            mimeType: "image/png",
                            name: "diagram.png",
                            dataBase64: "iVBORw0KGgo="
                        )
                    ]
                )
            ]
        )

        var events: [ChatStreamEvent] = []
        for try await event in backend.chat(request: request) {
            events.append(event)
        }

        XCTAssertEqual(paths, ["/api/v1/models", "/api/v1/chat", "/v1/chat/completions"])
        XCTAssertEqual(events, [
            .delta("Vision"),
            .done(inputTokens: 5, outputTokens: 1)
        ])
        XCTAssertEqual(
            backend.takeProviderUsageSource(generationID: request.generationID),
            ChatProviderUsageSource(
                provider: .lmStudio,
                providerModelID: "vision-local",
                wireMode: .lmStudioOpenAICompatible
            )
        )
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))

        let payload = try XCTUnwrap(postedPayload)
        XCTAssertEqual(payload["model"] as? String, "vision-local")
        XCTAssertEqual(payload["stream"] as? Bool, true)
        let streamOptions = try XCTUnwrap(payload["stream_options"] as? [String: Any])
        XCTAssertEqual(streamOptions["include_usage"] as? Bool, true)
        let messages = try XCTUnwrap(payload["messages"] as? [[String: Any]])
        let message = try XCTUnwrap(messages.first)
        XCTAssertNil(message["attachments"])
        XCTAssertEqual(message["role"] as? String, "user")

        let content = try XCTUnwrap(message["content"] as? [[String: Any]])
        XCTAssertEqual(content.count, 2)
        XCTAssertEqual(content[0]["type"] as? String, "text")
        XCTAssertEqual(content[0]["text"] as? String, "Describe this image.")
        XCTAssertEqual(content[1]["type"] as? String, "image_url")
        let imageURL = try XCTUnwrap(content[1]["image_url"] as? [String: Any])
        XCTAssertEqual(imageURL["url"] as? String, "data:image/png;base64,iVBORw0KGgo=")
    }

    func testChatWithoutModelsReturnsStructuredNoModelsError() async {
        let backend = makeBackend { request in
            XCTAssertEqual(request.url?.path, "/api/v1/models")
            return self.response(statusCode: 200, body: #"{"models":[]}"#)
        }

        let request = ChatRequest(
            generationID: "lm-no-models",
            sessionID: "session-1",
            model: "missing",
            messages: [ChatMessage(role: "user", content: "Hi")]
        )

        do {
            for try await _ in backend.chat(request: request) {}
            XCTFail("Expected no models error")
        } catch let error as LMStudioBackendError {
            XCTAssertEqual(error, .noModels)
            XCTAssertEqual(error.code, "lm_studio_no_models")
            XCTAssertFalse(error.retryable)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testLiveLMStudioConfirmedUnload() async throws {
        let environment = ProcessInfo.processInfo.environment
        guard environment["AETHERLINK_RUN_LMSTUDIO_LIVE_UNLOAD_TEST"] == "1" else {
            throw XCTSkip("Set AETHERLINK_RUN_LMSTUDIO_LIVE_UNLOAD_TEST=1 to enable the localhost LM Studio unload test.")
        }
        guard let modelID = environment["AETHERLINK_LMSTUDIO_LIVE_UNLOAD_MODEL_ID"], !modelID.isEmpty else {
            throw XCTSkip("Set AETHERLINK_LMSTUDIO_LIVE_UNLOAD_MODEL_ID to the exact native model key to unload.")
        }

        let session = URLSession(configuration: .ephemeral)
        let modelsBefore = try await liveLMStudioModels(session: session)
        let modelBefore = try XCTUnwrap(modelsBefore.first(where: { $0["key"] as? String == modelID }))
        let instancesBefore = try XCTUnwrap(modelBefore["loaded_instances"] as? [[String: Any]])
        guard !instancesBefore.isEmpty else {
            XCTFail("The explicitly selected LM Studio model must already be running before this test starts.")
            return
        }

        let result = try await LMStudioBackend().unloadModel(providerModelID: modelID)

        XCTAssertEqual(result.outcome, .confirmed)
        let modelsAfter = try await liveLMStudioModels(session: session)
        let installedAfter = try XCTUnwrap(modelsAfter.first(where: { $0["key"] as? String == modelID }))
        let instancesAfter = try XCTUnwrap(installedAfter["loaded_instances"] as? [[String: Any]])
        XCTAssertTrue(instancesAfter.isEmpty)
    }

    private func assertBadCatalogResponse(
        from backend: LMStudioBackend,
        endpoint: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async {
        do {
            _ = try await backend.listModels()
            XCTFail("Expected malformed catalog rejection", file: file, line: line)
        } catch let error as LMStudioBackendError {
            guard case .badResponse(let actualEndpoint, _) = error else {
                return XCTFail("Unexpected error: \(error)", file: file, line: line)
            }
            XCTAssertEqual(actualEndpoint, endpoint, file: file, line: line)
        } catch {
            XCTFail("Unexpected error: \(error)", file: file, line: line)
        }
    }

    private func makeBackend(
        unloadPollAttempts: Int = 3,
        catalogResponseByteLimit: Int = ModelInfo.maximumCatalogResponseBytes,
        unloadSleeper: @escaping @Sendable (UInt64) async throws -> Void = { _ in },
        handler: @escaping (URLRequest) throws -> (HTTPURLResponse, Data)
    ) -> LMStudioBackend {
        MockURLProtocol.handler = handler
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: configuration)
        return LMStudioBackend(
            baseURL: URL(string: "http://127.0.0.1:1234")!,
            session: session,
            unloadPollAttempts: unloadPollAttempts,
            catalogResponseByteLimit: catalogResponseByteLimit,
            unloadSleeper: unloadSleeper
        )
    }

    private func liveLMStudioModels(session: URLSession) async throws -> [[String: Any]] {
        let url = LMStudioBackend.defaultBaseURL.appending(path: "api/v1/models")
        let (data, response) = try await session.data(from: url)
        let http = try XCTUnwrap(response as? HTTPURLResponse)
        XCTAssertTrue((200..<300).contains(http.statusCode))
        let object = try JSONSerialization.jsonObject(with: data)
        let payload = try XCTUnwrap(object as? [String: Any])
        return try XCTUnwrap(payload["models"] as? [[String: Any]])
    }

    private func response(
        statusCode: Int,
        body: String,
        headers: [String: String] = [:]
    ) -> (HTTPURLResponse, Data) {
        let url = URL(string: "http://127.0.0.1:1234")!
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

private struct PostedNativeChatRequest: Decodable {
    var model: String
    var input: [PostedNativeInput]
    var stream: Bool
    var store: Bool
}

private struct PostedNativeInput: Decodable {
    var type: String?
    var role: String?
    var content: String?
    var dataURL: String?

    enum CodingKeys: String, CodingKey {
        case type
        case role
        case content
        case dataURL = "data_url"
    }
}

private struct PostedUnloadRequest: Decodable {
    var instanceID: String

    enum CodingKeys: String, CodingKey {
        case instanceID = "instance_id"
    }
}

private struct PostedEmbeddingRequest: Decodable {
    var model: String
    var input: [String]
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
