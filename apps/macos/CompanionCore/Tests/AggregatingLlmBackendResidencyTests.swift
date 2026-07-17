@testable import CompanionCore
import OllamaBackend
import XCTest

final class AggregatingLlmBackendResidencyTests: XCTestCase {
    func testListModelsPropagatesCancellationInsteadOfReturningPartialCatalog() async {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "ollama-model", name: "ollama-model", provider: .ollama)]
        )
        let lmStudio = ResidencyTestBackend(
            provider: .lmStudio,
            models: [ModelInfo(id: "lm-model", name: "lm-model", provider: .lmStudio)],
            holdsModelListingOpen: true
        )
        let backend = AggregatingLlmBackend([ollama, lmStudio])
        let task = Task {
            try await backend.listModels()
        }

        XCTAssertTrue(lmStudio.waitForModelListStart())
        task.cancel()
        lmStudio.releaseModelList()

        do {
            _ = try await task.value
            XCTFail("Expected aggregate catalog cancellation")
        } catch is CancellationError {
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
        XCTAssertEqual(ollama.modelListCallCount, 1)
        XCTAssertEqual(lmStudio.modelListCallCount, 1)
    }

    func testSwitchingModelsUnloadsPreviousInactiveModel() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let lmStudio = ResidencyTestBackend(
            provider: .lmStudio,
            models: [ModelInfo(id: "gemma-local", name: "gemma-local", provider: .lmStudio)]
        )
        let backend = AggregatingLlmBackend(
            [ollama, lmStudio],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        _ = try await collect(backend.chat(request: chatRequest(model: "lm_studio:gemma-local")))

        await eventually {
            ollama.unloadedModels == ["qwen-local"]
        }
        XCTAssertTrue(lmStudio.unloadedModels.isEmpty)
    }

    func testRepeatedSameModelDoesNotUnloadBetweenChats() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))

        XCTAssertTrue(ollama.unloadedModels.isEmpty)
    }

    func testIdlePolicyUnloadsActiveModelAfterDelay() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 0
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))

        await eventually {
            ollama.unloadedModels == ["qwen-local"]
        }
    }

    func testUpdatingIdlePolicyUnloadsModelWhenNewDelayAlreadyElapsed() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        try await Task.sleep(nanoseconds: 10_000_000)

        await backend.updateModelIdleUnloadDelayNanoseconds(1)

        await eventually {
            ollama.unloadedModels == ["qwen-local"]
        }
        XCTAssertNil(backend.modelResidencySnapshot().activeModelID)
    }

    func testUpdatingIdlePolicyWhileGenerationIsInFlightDefersUnloadUntilCompletion() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsChatsOpen: true
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let request = chatRequest(model: "ollama:qwen-local")
        let chatTask = Task {
            try await collect(backend.chat(request: request))
        }
        await eventually {
            backend.modelResidencySnapshot().inFlightGenerations == 1
        }

        await backend.updateModelIdleUnloadDelayNanoseconds(0)

        XCTAssertTrue(ollama.unloadedModels.isEmpty)
        XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "qwen-local")
        chatTask.cancel()
        _ = await chatTask.result
        await eventually {
            ollama.unloadedModels == ["qwen-local"]
        }
    }

    func testPendingIdleUnloadBlocksSameModelChatUntilProviderUnloadCompletes() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsUnloadsOpen: true
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        let policyTask = Task {
            await backend.updateModelIdleUnloadDelayNanoseconds(0)
        }
        XCTAssertTrue(ollama.waitForUnloadStart())

        let nextChatTask = Task {
            try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        }
        await eventually {
            ollama.modelListCallCount >= 2
        }

        XCTAssertEqual(ollama.routedModels, ["qwen-local"])
        XCTAssertEqual(backend.modelResidencySnapshot().inFlightGenerations, 0)

        ollama.releaseUnloads()
        await policyTask.value
        let nextChatEvents = try await nextChatTask.value
        XCTAssertEqual(nextChatEvents, [.done(inputTokens: 1, outputTokens: 1)])
        XCTAssertEqual(ollama.routedModels, ["qwen-local", "qwen-local"])
        XCTAssertEqual(ollama.unloadedModels, ["qwen-local", "qwen-local"])
    }

    func testCancelledChatWaitingForSameModelUnloadDoesNotReserveOrDispatch() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsUnloadsOpen: true
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        let policyTask = Task {
            await backend.updateModelIdleUnloadDelayNanoseconds(0)
        }
        XCTAssertTrue(ollama.waitForUnloadStart())

        let nextRequest = chatRequest(model: "ollama:qwen-local")
        let nextChatTask = Task {
            try await collect(backend.chat(request: nextRequest))
        }
        await eventually {
            ollama.modelListCallCount >= 2
        }
        XCTAssertEqual(
            backend.cancel(generationID: nextRequest.generationID),
            .cancelled(generationID: nextRequest.generationID)
        )
        ollama.releaseUnloads()
        await policyTask.value

        do {
            _ = try await nextChatTask.value
            XCTFail("Expected the chat waiting for provider unload to remain cancelled.")
        } catch is CancellationError {
            // Expected.
        }
        await eventually {
            backend.modelResidencySnapshot().inFlightGenerations == 0
        }
        XCTAssertEqual(ollama.routedModels, ["qwen-local"])
        XCTAssertEqual(ollama.unloadedModels, ["qwen-local"])
        XCTAssertNil(backend.modelResidencySnapshot().activeModelID)
    }

    func testCancelledChatWaitingForModelSwitchUnloadDoesNotReserveOrDispatch() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsUnloadsOpen: true
        )
        let lmStudio = ResidencyTestBackend(
            provider: .lmStudio,
            models: [ModelInfo(id: "gemma-local", name: "gemma-local", provider: .lmStudio)]
        )
        let backend = AggregatingLlmBackend(
            [ollama, lmStudio],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        let switchRequest = chatRequest(model: "lm_studio:gemma-local")
        let switchChatTask = Task {
            try await collect(backend.chat(request: switchRequest))
        }
        XCTAssertTrue(ollama.waitForUnloadStart())

        XCTAssertEqual(
            backend.cancel(generationID: switchRequest.generationID),
            .cancelled(generationID: switchRequest.generationID)
        )
        ollama.releaseUnloads()

        do {
            _ = try await switchChatTask.value
            XCTFail("Expected the chat waiting for model-switch unload to remain cancelled.")
        } catch is CancellationError {
            // Expected.
        }
        XCTAssertEqual(ollama.unloadedModels, ["qwen-local"])
        XCTAssertTrue(lmStudio.routedModels.isEmpty)
        XCTAssertNil(backend.modelResidencySnapshot().activeModelID)
        XCTAssertEqual(backend.modelResidencySnapshot().inFlightGenerations, 0)
    }

    func testCancelledEmbeddingWaitingForSameModelUnloadDoesNotDispatch() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(
                id: "nomic-embed",
                name: "nomic-embed",
                provider: .ollama,
                kind: .embedding
            )],
            holdsUnloadsOpen: true
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let request = EmbeddingRequest(model: "ollama:nomic-embed", texts: ["policy"])

        _ = try await backend.embed(request: request)
        let policyTask = Task {
            await backend.updateModelIdleUnloadDelayNanoseconds(0)
        }
        XCTAssertTrue(ollama.waitForUnloadStart())

        let nextEmbeddingTask = Task {
            try await backend.embed(request: request)
        }
        await eventually {
            ollama.modelListCallCount >= 2
        }
        nextEmbeddingTask.cancel()
        ollama.releaseUnloads()
        await policyTask.value

        do {
            _ = try await nextEmbeddingTask.value
            XCTFail("Expected the embedding waiting for provider unload to remain cancelled.")
        } catch is CancellationError {
            // Expected.
        }
        XCTAssertEqual(ollama.embeddingRequests, [EmbeddingRequest(
            model: "nomic-embed",
            texts: ["policy"],
        )])
        XCTAssertEqual(ollama.unloadedModels, ["nomic-embed"])
        XCTAssertNil(backend.modelResidencySnapshot().activeModelID)
        XCTAssertEqual(backend.modelResidencySnapshot().inFlightGenerations, 0)
    }

    func testExtendingIdlePolicyInvalidatesEarlierTimer() async throws {
        let sleeper = ControlledIdleUnloadSleeper()
        let idleUnloadAttempted = DispatchSemaphore(value: 0)
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 25_000_000,
            idleUnloadSleeper: { delayNanoseconds in
                try await sleeper.sleep(delayNanoseconds: delayNanoseconds)
            },
            idleUnloadAttemptHandler: {
                idleUnloadAttempted.signal()
            }
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        XCTAssertTrue(sleeper.waitForNextCall())
        await backend.updateModelIdleUnloadDelayNanoseconds(60_000_000_000)
        XCTAssertTrue(sleeper.waitForNextCall())

        sleeper.releaseCall(at: 0)
        XCTAssertEqual(idleUnloadAttempted.wait(timeout: .now() + 1), .success)

        XCTAssertTrue(ollama.unloadedModels.isEmpty)
        XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "qwen-local")
        _ = await backend.unloadActiveResidencyModelNow()
        sleeper.releaseCall(at: 1)
    }

    func testDoneEventClearsInFlightResidencyBeforeClientObservesCompletion() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        var iterator = backend.chat(request: chatRequest(model: "ollama:qwen-local")).makeAsyncIterator()
        let event = try await iterator.next()

        XCTAssertEqual(event, .done(inputTokens: 1, outputTokens: 1))
        XCTAssertEqual(
            backend.modelResidencySnapshot(),
            RuntimeModelResidencySnapshot(
                activeProvider: .ollama,
                activeModelID: "qwen-local",
                inFlightGenerations: 0,
                idleUnloadDelaySeconds: 60
            )
        )
    }

    func testProviderUsageSourceForwardsThroughAggregateAndIsConsumedOnce() async throws {
        let source = ChatProviderUsageSource(
            provider: .ollama,
            providerModelID: "qwen-local",
            wireMode: .ollamaChat
        )
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            providerUsageSource: source
        )
        let backend = AggregatingLlmBackend([ollama])
        let request = chatRequest(model: "ollama:qwen-local")

        let events = try await collect(backend.chat(request: request))
        XCTAssertEqual(events, [.done(inputTokens: 1, outputTokens: 1)])
        XCTAssertEqual(backend.takeProviderUsageSource(generationID: request.generationID), source)
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testRejectedDuplicateGenerationDoesNotEraseOriginalProviderUsageSource() async throws {
        let source = ChatProviderUsageSource(
            provider: .ollama,
            providerModelID: "qwen-local",
            wireMode: .ollamaChat
        )
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsChatsOpenAfterDone: true,
            providerUsageSource: source
        )
        let backend = AggregatingLlmBackend([ollama])
        let request = chatRequest(model: "ollama:qwen-local")
        var original = backend.chat(request: request).makeAsyncIterator()
        let originalDone = try await original.next()
        XCTAssertEqual(originalDone, .done(inputTokens: 1, outputTokens: 1))

        do {
            _ = try await collect(backend.chat(request: request))
            XCTFail("Expected duplicate generation rejection")
        } catch let error as BackendError {
            XCTAssertEqual(error.code, "generation_already_active")
        }

        XCTAssertEqual(backend.takeProviderUsageSource(generationID: request.generationID), source)
        XCTAssertNil(backend.takeProviderUsageSource(generationID: request.generationID))
    }

    func testManualUnloadClearsActiveResidentModelAndEmitsManualEvent() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let events = ResidencyEventRecorder()
        backend.setResidencyEventHandler { event in
            events.append(event)
        }

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        await eventually {
            let snapshot = backend.modelResidencySnapshot()
            return snapshot.activeModelID == "qwen-local" && snapshot.inFlightGenerations == 0
        }

        let result = await backend.unloadActiveResidencyModelNow()

        XCTAssertEqual(result, .requested(provider: .ollama, modelID: "qwen-local"))
        await eventually {
            ollama.unloadedModels == ["qwen-local"] &&
                events.containsUnloadSuccess(provider: .ollama, modelID: "qwen-local", reason: .manual)
        }
        XCTAssertEqual(
            backend.modelResidencySnapshot(),
            RuntimeModelResidencySnapshot(
                activeProvider: nil,
                activeModelID: nil,
                inFlightGenerations: 0,
                idleUnloadDelaySeconds: 60
            )
        )
    }

    func testManualUnloadKeepsActiveModelVisibleWhileProviderConfirmationIsPending() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsUnloadsOpen: true
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        let unloadTask = Task {
            await backend.unloadActiveResidencyModelNow()
        }
        XCTAssertTrue(ollama.waitForUnloadStart())

        XCTAssertEqual(
            backend.modelResidencySnapshot(),
            RuntimeModelResidencySnapshot(
                activeProvider: .ollama,
                activeModelID: "qwen-local",
                inFlightGenerations: 0,
                idleUnloadDelaySeconds: 60,
                unloadingProvider: .ollama,
                unloadingModelID: "qwen-local",
                unloadingReason: .manual
            )
        )

        ollama.releaseUnloads()
        let unloadResult = await unloadTask.value
        XCTAssertEqual(unloadResult, .requested(provider: .ollama, modelID: "qwen-local"))
        XCTAssertNil(backend.modelResidencySnapshot().activeModelID)
        XCTAssertNil(backend.modelResidencySnapshot().unloadingModelID)
    }

    func testManualUnloadFailureKeepsStructuredManualFailureReason() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            unloadErrors: [
                "qwen-local": NSError(
                    domain: "AetherLinkResidencyTest",
                    code: 43,
                    userInfo: [NSLocalizedDescriptionKey: "manual unload denied"]
                )
            ]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let events = ResidencyEventRecorder()
        backend.setResidencyEventHandler { event in
            events.append(event)
        }

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        await eventually {
            let snapshot = backend.modelResidencySnapshot()
            return snapshot.activeModelID == "qwen-local" && snapshot.inFlightGenerations == 0
        }
        let result = await backend.unloadActiveResidencyModelNow()

        XCTAssertEqual(result, .requested(provider: .ollama, modelID: "qwen-local"))
        await eventually {
            events.containsUnloadFailure(
                provider: .ollama,
                modelID: "qwen-local",
                reason: .manual,
                message: "manual unload denied"
            )
        }
        XCTAssertEqual(
            backend.modelResidencySnapshot().lastUnloadFailure,
            RuntimeModelResidencyUnloadFailure(provider: .ollama, modelID: "qwen-local", reason: .manual)
        )
        XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "qwen-local")
        XCTAssertNil(backend.modelResidencySnapshot().unloadingModelID)
    }

    func testNonthrowingUnsupportedUnloadIsFailureAndKeepsManualResidencyActive() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            unloadResults: [
                "qwen-local": .unsupported(provider: .ollama, modelID: "qwen-local")
            ]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let events = ResidencyEventRecorder()
        backend.setResidencyEventHandler { event in
            events.append(event)
        }

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        _ = await backend.unloadActiveResidencyModelNow()

        XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "qwen-local")
        XCTAssertEqual(
            backend.modelResidencySnapshot().lastUnloadFailure,
            RuntimeModelResidencyUnloadFailure(provider: .ollama, modelID: "qwen-local", reason: .manual)
        )
        XCTAssertTrue(events.containsUnloadFailure(
            provider: .ollama,
            modelID: "qwen-local",
            reason: .manual,
            message: "Ollama does not support runtime-managed model unload."
        ))
    }

    func testMismatchedUnloadConfirmationIdentityIsFailureAndKeepsManualResidencyActive() async throws {
        for mismatch in [
            ModelUnloadResult.unloaded(provider: .lmStudio, modelID: "qwen-local"),
            ModelUnloadResult.alreadyAbsent(provider: .ollama, modelID: "different-model"),
        ] {
            let ollama = ResidencyTestBackend(
                provider: .ollama,
                models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
                unloadResults: ["qwen-local": mismatch]
            )
            let backend = AggregatingLlmBackend(
                [ollama],
                modelIdleUnloadDelayNanoseconds: 60_000_000_000
            )
            let events = ResidencyEventRecorder()
            backend.setResidencyEventHandler { event in
                events.append(event)
            }

            _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
            _ = await backend.unloadActiveResidencyModelNow()

            XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "qwen-local")
            XCTAssertEqual(
                backend.modelResidencySnapshot().lastUnloadFailure,
                RuntimeModelResidencyUnloadFailure(
                    provider: .ollama,
                    modelID: "qwen-local",
                    reason: .manual
                )
            )
            XCTAssertTrue(events.containsUnloadFailure(
                provider: .ollama,
                modelID: "qwen-local",
                reason: .manual,
                message: "The model provider returned a mismatched unload confirmation."
            ))
        }
    }

    func testIdleUnloadFailureKeepsPossiblyResidentModelActive() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            unloadErrors: [
                "qwen-local": NSError(
                    domain: "AetherLinkResidencyTest",
                    code: 44,
                    userInfo: [NSLocalizedDescriptionKey: "idle unload not confirmed"]
                )
            ]
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 0
        )

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))

        XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "qwen-local")
        XCTAssertEqual(
            backend.modelResidencySnapshot().lastUnloadFailure,
            RuntimeModelResidencyUnloadFailure(provider: .ollama, modelID: "qwen-local", reason: .idleTimeout)
        )
        XCTAssertNil(backend.modelResidencySnapshot().unloadingModelID)
    }

    func testManualUnloadSkipsWhileGenerationIsInFlight() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsChatsOpen: true
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )

        let chatTask = Task {
            try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        }
        await eventually {
            backend.modelResidencySnapshot().inFlightGenerations == 1
        }

        let result = await backend.unloadActiveResidencyModelNow()

        XCTAssertEqual(result, .inFlightGenerations(1))
        XCTAssertTrue(ollama.unloadedModels.isEmpty)
        XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "qwen-local")
        chatTask.cancel()
        _ = await chatTask.result
    }

    func testCancelBeforeAsyncRouteResolutionPreventsProviderChatDispatch() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsModelListingOpen: true
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let request = ChatRequest(
            generationID: "cancel-before-route-resolution",
            sessionID: "cancel-before-route-session",
            model: "ollama:qwen-local",
            messages: [ChatMessage(role: "user", content: "Cancel before provider routing completes.")]
        )
        let chatTask = Task {
            try await collect(backend.chat(request: request))
        }
        XCTAssertTrue(ollama.waitForModelListStart())

        XCTAssertEqual(
            backend.cancel(generationID: request.generationID),
            .cancelled(generationID: request.generationID)
        )
        ollama.releaseModelList()
        _ = await chatTask.result

        XCTAssertTrue(ollama.routedModels.isEmpty)
        XCTAssertEqual(ollama.cancelCallCount, 0)
        await eventually {
            backend.modelResidencySnapshot().inFlightGenerations == 0
        }
    }

    func testRejectedDuplicateGenerationCannotRemoveOriginalReservation() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            holdsChatsOpen: true
        )
        let backend = AggregatingLlmBackend(
            [ollama],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let request = ChatRequest(
            generationID: "duplicate-reservation",
            sessionID: "duplicate-reservation-session",
            model: "ollama:qwen-local",
            messages: [ChatMessage(role: "user", content: "Keep the original reservation active.")]
        )
        let originalTask = Task {
            try await collect(backend.chat(request: request))
        }
        await eventually {
            ollama.routedModels == ["qwen-local"]
        }

        for _ in 0..<2 {
            do {
                _ = try await collect(backend.chat(request: request))
                XCTFail("Expected duplicate generation rejection.")
            } catch let error as BackendError {
                XCTAssertEqual(error.code, "generation_already_active")
            }
        }
        XCTAssertEqual(ollama.routedModels, ["qwen-local"])
        XCTAssertEqual(
            backend.cancel(generationID: request.generationID),
            .cancelled(generationID: request.generationID)
        )
        XCTAssertEqual(ollama.cancelCallCount, 1)

        originalTask.cancel()
        _ = await originalTask.result
    }

    func testUnloadFailureEmitsProviderSpecificFailureEventWithoutBreakingNextChat() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)],
            unloadErrors: [
                "qwen-local": NSError(
                    domain: "AetherLinkResidencyTest",
                    code: 42,
                    userInfo: [NSLocalizedDescriptionKey: "unload denied"]
                )
            ]
        )
        let lmStudio = ResidencyTestBackend(
            provider: .lmStudio,
            models: [ModelInfo(id: "gemma-local", name: "gemma-local", provider: .lmStudio)]
        )
        let backend = AggregatingLlmBackend(
            [ollama, lmStudio],
            modelIdleUnloadDelayNanoseconds: 60_000_000_000
        )
        let events = ResidencyEventRecorder()
        backend.setResidencyEventHandler { event in
            events.append(event)
        }

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        _ = try await collect(backend.chat(request: chatRequest(model: "lm_studio:gemma-local")))

        await eventually {
            events.containsUnloadFailure(
                provider: .ollama,
                modelID: "qwen-local",
                reason: .modelSwitch,
                message: "unload denied"
            )
        }
        XCTAssertEqual(ollama.unloadedModels, ["qwen-local"])
        XCTAssertEqual(lmStudio.routedModels, ["gemma-local"])
        XCTAssertEqual(
            backend.modelResidencySnapshot(),
            RuntimeModelResidencySnapshot(
                activeProvider: .lmStudio,
                activeModelID: "gemma-local",
                inFlightGenerations: 0,
                idleUnloadDelaySeconds: 60,
                lastUnloadFailure: RuntimeModelResidencyUnloadFailure(
                    provider: .ollama,
                    modelID: "qwen-local",
                    reason: .modelSwitch
                )
            )
        )
    }

    func testUnknownUnqualifiedModelDoesNotFallbackToOllama() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await collect(backend.chat(request: chatRequest(model: "synthetic-default")))
            XCTFail("Expected unknown model to be rejected")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .aggregate)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertFalse(error.retryable)
            XCTAssertTrue(ollama.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testQualifiedModelMustBeReportedByThatProvider() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let lmStudio = ResidencyTestBackend(
            provider: .lmStudio,
            models: [ModelInfo(id: "gemma-local", name: "gemma-local", provider: .lmStudio)]
        )
        let backend = AggregatingLlmBackend([ollama, lmStudio])

        do {
            _ = try await collect(backend.chat(request: chatRequest(model: "lm_studio:qwen-local")))
            XCTFail("Expected provider-mismatched model to be rejected")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .lmStudio)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertFalse(error.retryable)
            XCTAssertTrue(lmStudio.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testQualifiedModelMatchesOnlyExactProviderModelID() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(
                id: "retired-provider-id",
                name: "retired-provider-id",
                provider: .ollama,
                providerModelID: "different-provider-model"
            )]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await collect(backend.chat(request: chatRequest(
                model: "ollama:retired-provider-id"
            )))
            XCTFail("A qualified provider route must not rebind through model id or name")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .ollama)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertFalse(error.retryable)
            XCTAssertTrue(ollama.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testChatRejectsProviderModelIDWithReservedQualifiedPrefix() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(
                id: "safe-chat-alias",
                name: "safe-chat-alias",
                provider: .ollama,
                providerModelID: "ollama:provider-native-collision"
            )]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await collect(backend.chat(request: chatRequest(model: "safe-chat-alias")))
            XCTFail("Aggregate chat must reject reserved provider model prefixes")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .aggregate)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertTrue(ollama.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testEmbeddingRejectsProviderModelIDWithReservedQualifiedPrefix() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(
                id: "safe-embedding-alias",
                name: "safe-embedding-alias",
                provider: .ollama,
                kind: .embedding,
                providerModelID: "ollama:provider-native-collision"
            )]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await backend.embed(request: EmbeddingRequest(
                model: "ollama:ollama:provider-native-collision",
                texts: ["text"]
            ))
            XCTFail("Aggregate embedding must reject reserved provider model prefixes")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .ollama)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertTrue(ollama.embeddingRequests.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testInstalledEmbeddingModelIsNotRoutedAsChat() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [
                ModelInfo(
                    id: "nomic-embed-text",
                    name: "nomic-embed-text",
                    provider: .ollama,
                    kind: .embedding
                )
            ]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await collect(backend.chat(request: chatRequest(model: "ollama:nomic-embed-text")))
            XCTFail("Expected embedding model to be rejected for chat routing")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .ollama)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertFalse(error.retryable)
            XCTAssertTrue(ollama.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testQualifiedInstalledEmbeddingRoutesToItsProviderModelID() async throws {
        let ollama = ResidencyTestBackend(provider: .ollama)
        let lmStudio = ResidencyTestBackend(
            provider: .lmStudio,
            models: [
                ModelInfo(
                    id: "text-embedding-nomic",
                    name: "Nomic Embed",
                    provider: .lmStudio,
                    kind: .embedding,
                    providerModelID: "text-embedding-nomic"
                )
            ]
        )
        let backend = AggregatingLlmBackend([ollama, lmStudio])

        let result = try await backend.embed(request: EmbeddingRequest(
            model: "lm_studio:text-embedding-nomic",
            texts: ["first", "second"]
        ))

        XCTAssertEqual(result, EmbeddingResult(
            model: "text-embedding-nomic",
            embeddings: [[1, 2], [1, 2]]
        ))
        XCTAssertTrue(ollama.embeddingRequests.isEmpty)
        XCTAssertEqual(lmStudio.embeddingRequests, [EmbeddingRequest(
            model: "text-embedding-nomic",
            texts: ["first", "second"]
        )])
    }

    func testEmbeddingRejectsChatModelAndDoesNotRoute() async {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await backend.embed(request: EmbeddingRequest(
                model: "ollama:qwen-local",
                texts: ["text"]
            ))
            XCTFail("Expected chat model to be rejected for embedding routing")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .ollama)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertTrue(ollama.embeddingRequests.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testEmbeddingRejectsProviderManagedModelAndDoesNotRoute() async {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [
                ModelInfo(
                    id: "cloud-embed",
                    name: "cloud-embed",
                    provider: .ollama,
                    kind: .embedding,
                    source: .cloud
                )
            ]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await backend.embed(request: EmbeddingRequest(
                model: "ollama:cloud-embed",
                texts: ["text"]
            ))
            XCTFail("Expected provider-managed embedding model to be rejected")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .ollama)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertTrue(ollama.embeddingRequests.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testEmbeddingDoesNotEnterGenerationCancellationRegistry() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [
                ModelInfo(
                    id: "nomic-embed-text",
                    name: "nomic-embed-text",
                    provider: .ollama,
                    kind: .embedding
                )
            ]
        )
        let backend = AggregatingLlmBackend([ollama])

        _ = try await backend.embed(request: EmbeddingRequest(
            model: "ollama:nomic-embed-text",
            texts: ["text"]
        ))

        XCTAssertEqual(backend.cancel(generationID: "embedding-request"), .notFound(generationID: "embedding-request"))
        XCTAssertEqual(ollama.cancelCallCount, 1)
        XCTAssertEqual(backend.modelResidencySnapshot().inFlightGenerations, 0)
        XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "nomic-embed-text")
    }

    func testEmbeddingResidencyUnloadsPreviousChatModel() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [
                ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama),
                ModelInfo(
                    id: "nomic-embed-text",
                    name: "nomic-embed-text",
                    provider: .ollama,
                    kind: .embedding
                )
            ]
        )
        let backend = AggregatingLlmBackend([ollama])

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))
        _ = try await backend.embed(request: EmbeddingRequest(
            model: "ollama:nomic-embed-text",
            texts: ["text"]
        ))

        XCTAssertEqual(ollama.unloadedModels, ["qwen-local"])
        XCTAssertEqual(backend.modelResidencySnapshot().activeModelID, "nomic-embed-text")
        XCTAssertEqual(backend.modelResidencySnapshot().inFlightGenerations, 0)
    }

    func testInstalledCloudChatModelIsNotRoutedAsChat() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [
                ModelInfo(
                    id: "deepseek-v4-pro:cloud",
                    name: "deepseek-v4-pro:cloud",
                    provider: .ollama,
                    installed: true,
                    source: .cloud,
                    remoteModel: "deepseek-v4-pro",
                    remoteHost: "https://ollama.com:443"
                )
            ]
        )
        let backend = AggregatingLlmBackend([ollama])

        do {
            _ = try await collect(backend.chat(request: chatRequest(model: "ollama:deepseek-v4-pro:cloud")))
            XCTFail("Expected cloud model to be rejected for chat routing")
        } catch let error as BackendError {
            XCTAssertEqual(error.provider, .ollama)
            XCTAssertEqual(error.code, "model_not_installed")
            XCTAssertFalse(error.retryable)
            XCTAssertTrue(ollama.routedModels.isEmpty)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testExactModelIDWinsBeforeLatestCanonicalAlias() async throws {
        let ollama = ResidencyTestBackend(
            provider: .ollama,
            models: [
                ModelInfo(id: "qwen:latest", name: "qwen:latest", provider: .ollama),
                ModelInfo(id: "qwen", name: "qwen", provider: .ollama)
            ]
        )
        let backend = AggregatingLlmBackend([ollama])

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen")))

        XCTAssertEqual(ollama.routedModels, ["qwen"])
    }

    func testDuplicateProviderBackendsKeepFirstProviderInsteadOfCrashing() async throws {
        let primaryOllama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "qwen-local", name: "qwen-local", provider: .ollama)]
        )
        let duplicateOllama = ResidencyTestBackend(
            provider: .ollama,
            models: [ModelInfo(id: "shadow-local", name: "shadow-local", provider: .ollama)]
        )
        let backend = AggregatingLlmBackend([primaryOllama, duplicateOllama])

        let models = try await backend.listModels()
        XCTAssertEqual(models.map(\.id), ["qwen-local"])

        _ = try await collect(backend.chat(request: chatRequest(model: "ollama:qwen-local")))

        XCTAssertEqual(primaryOllama.routedModels, ["qwen-local"])
        XCTAssertTrue(duplicateOllama.routedModels.isEmpty)
    }

    private func chatRequest(model: String) -> ChatRequest {
        ChatRequest(
            generationID: UUID().uuidString,
            sessionID: "session-1",
            model: model,
            messages: [ChatMessage(role: "user", content: "Hi")]
        )
    }

    private func collect(_ stream: AsyncThrowingStream<ChatStreamEvent, Error>) async throws -> [ChatStreamEvent] {
        var events: [ChatStreamEvent] = []
        for try await event in stream {
            events.append(event)
        }
        return events
    }

    private func eventually(
        timeoutNanoseconds: UInt64 = 500_000_000,
        _ condition: @escaping () -> Bool
    ) async {
        let step: UInt64 = 10_000_000
        var waited: UInt64 = 0
        while waited <= timeoutNanoseconds {
            if condition() {
                return
            }
            try? await Task.sleep(nanoseconds: step)
            waited += step
        }
        XCTFail("Condition was not met before timeout.")
    }
}

private final class ResidencyTestBackend: LlmBackend, @unchecked Sendable {
    let provider: ModelProvider

    private let lock = NSLock()
    private let models: [ModelInfo]
    private let unloadErrors: [String: Error]
    private let unloadResults: [String: ModelUnloadResult]
    private let holdsChatsOpen: Bool
    private let holdsChatsOpenAfterDone: Bool
    private let holdsModelListingOpen: Bool
    private let holdsUnloadsOpen: Bool
    private let providerUsageSource: ChatProviderUsageSource?
    private let modelListStarted = DispatchSemaphore(value: 0)
    private let unloadStarted = DispatchSemaphore(value: 0)
    private var modelListReleased = false
    private var modelListReleaseContinuations: [CheckedContinuation<Void, Never>] = []
    private var unloadReleased = false
    private var unloadReleaseContinuations: [CheckedContinuation<Void, Never>] = []
    private var modelListCalls = 0
    private var unloaded: [String] = []
    private var routed: [String] = []
    private var embedded: [EmbeddingRequest] = []
    private var cancellationCalls = 0
    private var completedProviderUsageSources: [String: ChatProviderUsageSource] = [:]

    var unloadedModels: [String] {
        lock.withLock { unloaded }
    }

    var routedModels: [String] {
        lock.withLock { routed }
    }

    var embeddingRequests: [EmbeddingRequest] {
        lock.withLock { embedded }
    }

    var cancelCallCount: Int {
        lock.withLock { cancellationCalls }
    }

    var modelListCallCount: Int {
        lock.withLock { modelListCalls }
    }

    init(
        provider: ModelProvider,
        models: [ModelInfo] = [],
        unloadErrors: [String: Error] = [:],
        unloadResults: [String: ModelUnloadResult] = [:],
        holdsChatsOpen: Bool = false,
        holdsChatsOpenAfterDone: Bool = false,
        holdsModelListingOpen: Bool = false,
        holdsUnloadsOpen: Bool = false,
        providerUsageSource: ChatProviderUsageSource? = nil
    ) {
        self.provider = provider
        self.models = models
        self.unloadErrors = unloadErrors
        self.unloadResults = unloadResults
        self.holdsChatsOpen = holdsChatsOpen
        self.holdsChatsOpenAfterDone = holdsChatsOpenAfterDone
        self.holdsModelListingOpen = holdsModelListingOpen
        self.holdsUnloadsOpen = holdsUnloadsOpen
        self.providerUsageSource = providerUsageSource
    }

    func healthCheck() async -> BackendStatus {
        .available
    }

    func listModels() async throws -> [ModelInfo] {
        lock.withLock {
            modelListCalls += 1
        }
        if holdsModelListingOpen {
            modelListStarted.signal()
            await withCheckedContinuation { continuation in
                lock.withLock {
                    if modelListReleased {
                        continuation.resume()
                    } else {
                        modelListReleaseContinuations.append(continuation)
                    }
                }
            }
            try Task.checkCancellation()
        }
        return models
    }

    func waitForModelListStart(timeout: TimeInterval = 1) -> Bool {
        modelListStarted.wait(timeout: .now() + timeout) == .success
    }

    func releaseModelList() {
        let continuations = lock.withLock {
            modelListReleased = true
            let continuations = modelListReleaseContinuations
            modelListReleaseContinuations.removeAll()
            return continuations
        }
        continuations.forEach { $0.resume() }
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            lock.withLock {
                routed.append(request.model)
            }
            guard !holdsChatsOpen else {
                return
            }
            if let providerUsageSource {
                lock.withLock {
                    completedProviderUsageSources[request.generationID] = providerUsageSource
                }
            }
            continuation.yield(.done(inputTokens: 1, outputTokens: 1))
            guard !holdsChatsOpenAfterDone else { return }
            continuation.finish()
        }
    }

    func takeProviderUsageSource(generationID: String) -> ChatProviderUsageSource? {
        lock.withLock {
            completedProviderUsageSources.removeValue(forKey: generationID)
        }
    }

    func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        lock.withLock {
            unloaded.append(providerModelID)
        }
        if holdsUnloadsOpen {
            unloadStarted.signal()
            await withCheckedContinuation { continuation in
                lock.withLock {
                    if unloadReleased {
                        continuation.resume()
                    } else {
                        unloadReleaseContinuations.append(continuation)
                    }
                }
            }
        }
        if let error = unloadErrors[providerModelID] {
            throw error
        }
        if let result = unloadResults[providerModelID] {
            return result
        }
        return .unloaded(provider: provider, modelID: providerModelID)
    }

    func waitForUnloadStart(timeout: TimeInterval = 1) -> Bool {
        unloadStarted.wait(timeout: .now() + timeout) == .success
    }

    func releaseUnloads() {
        let continuations = lock.withLock {
            unloadReleased = true
            let continuations = unloadReleaseContinuations
            unloadReleaseContinuations.removeAll()
            return continuations
        }
        continuations.forEach { $0.resume() }
    }

    func embed(request: EmbeddingRequest) async throws -> EmbeddingResult {
        lock.withLock {
            embedded.append(request)
        }
        return EmbeddingResult(
            model: request.model,
            embeddings: request.texts.map { _ in [1, 2] }
        )
    }

    @discardableResult
    func cancel(generationID: String) -> GenerationCancellationResult {
        lock.withLock {
            cancellationCalls += 1
        }
        return .notFound(generationID: generationID)
    }
}

private final class ControlledIdleUnloadSleeper: @unchecked Sendable {
    private let lock = NSLock()
    private let callStarted = DispatchSemaphore(value: 0)
    private var continuations: [CheckedContinuation<Void, Never>?] = []

    func sleep(delayNanoseconds: UInt64) async throws {
        _ = delayNanoseconds
        await withCheckedContinuation { continuation in
            lock.withLock {
                continuations.append(continuation)
            }
            callStarted.signal()
        }
    }

    func waitForNextCall(timeout: TimeInterval = 1) -> Bool {
        callStarted.wait(timeout: .now() + timeout) == .success
    }

    func releaseCall(at index: Int) {
        let continuation = lock.withLock { () -> CheckedContinuation<Void, Never>? in
            guard continuations.indices.contains(index) else { return nil }
            let continuation = continuations[index]
            continuations[index] = nil
            return continuation
        }
        continuation?.resume()
    }
}

private final class ResidencyEventRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var events: [RuntimeModelResidencyEvent] = []

    func append(_ event: RuntimeModelResidencyEvent) {
        lock.withLock {
            events.append(event)
        }
    }

    func containsUnloadSuccess(
        provider: ModelProvider,
        modelID: String,
        reason: RuntimeModelResidencyUnloadReason
    ) -> Bool {
        lock.withLock {
            events.contains { event in
                if case let .unloadSucceeded(eventProvider, eventModelID, eventReason) = event {
                    return eventProvider == provider &&
                        eventModelID == modelID &&
                        eventReason == reason
                }
                return false
            }
        }
    }

    func containsUnloadFailure(
        provider: ModelProvider,
        modelID: String,
        reason: RuntimeModelResidencyUnloadReason,
        message: String
    ) -> Bool {
        lock.withLock {
            events.contains { event in
                if case let .unloadFailed(eventProvider, eventModelID, eventReason, eventMessage) = event {
                    return eventProvider == provider &&
                        eventModelID == modelID &&
                        eventReason == reason &&
                        eventMessage == message
                }
                return false
            }
        }
    }
}

private extension NSLock {
    func withLock<T>(_ body: () throws -> T) rethrows -> T {
        lock()
        defer { unlock() }
        return try body()
    }
}
