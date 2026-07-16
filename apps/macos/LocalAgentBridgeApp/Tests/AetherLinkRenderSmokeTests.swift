import AppKit
import CompanionCore
import CryptoKit
import DocumentIngestion
import OllamaBackend
import SwiftUI
import TrustedDevices
import XCTest
@testable import LocalAgentBridge

@MainActor
final class AetherLinkRenderSmokeTests: XCTestCase {
    private let minimumWindowSize = CGSize(width: 860, height: 560)
    private let minimumDetailSize = CGSize(width: 680, height: 560)
    private let compactDetailSize = CGSize(width: 520, height: 640)

    func testCompanionShellRendersAtMinimumWindowAcrossLanguagesAndAppearances() throws {
        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let bitmap = try render(
                        ContentView(
                            model: renderSmokeModel(),
                            requestedSection: .constant(.pairing)
                        )
                        .environment(\.locale, Locale(identifier: language.localeIdentifier))
                        .preferredColorScheme(appearance.preferredColorScheme),
                        size: minimumWindowSize
                    )

                    assertMeaningfulRender(
                        bitmap,
                        label: "ContentView \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    func testCompanionShellPreferenceControlsRenderAtAccessibilitySizeAcrossLanguages() throws {
        for language in AetherLinkAppLanguage.allCases {
            try withStoredPreferences(language: language, appearance: .system) {
                let bitmap = try render(
                    ContentView(
                        model: renderSmokeModel(),
                        requestedSection: .constant(.status)
                    )
                    .environment(\.locale, Locale(identifier: language.localeIdentifier))
                    .environment(\.dynamicTypeSize, .accessibility3),
                    size: minimumWindowSize
                )

                assertMeaningfulRender(
                    bitmap,
                    label: "ContentView accessibility text preferences \(language.rawValue)"
                )
            }
        }
    }

    func testModelPullApprovalPanelRendersPendingReviewAcrossLanguagesAndAppearances() throws {
        let requestedAt = Date(timeIntervalSince1970: 1_782_000_000)
        let review = CompanionPendingModelPullReview(
            operationID: "00000000-0000-0000-0000-000000000001",
            model: "ollama:very-long-runtime-host-model-name-with-context-and-quantization:latest",
            provider: .ollama,
            requestingDeviceName: "جهاز-" + String(repeating: "장치👨‍👩‍👧‍👦", count: 16),
            requestingDeviceKeyFingerprint: "D4:14:AF:87:F9:9D",
            requestedAt: requestedAt,
            expiresAt: requestedAt.addingTimeInterval(300)
        )
        XCTAssertGreaterThan(review.requestingDeviceName.utf8.count, 500)
        XCTAssertLessThanOrEqual(review.requestingDeviceName.utf8.count, 512)
        let events = [
            RuntimeModelPullAuditSummary(
                id: "audit-1",
                operationID: review.operationID,
                event: "dispatch_reserved",
                provider: .ollama,
                occurredAt: requestedAt
            ),
            RuntimeModelPullAuditSummary(
                id: "audit-2",
                operationID: review.operationID,
                event: "result_suppressed",
                provider: .ollama,
                occurredAt: requestedAt.addingTimeInterval(1)
            ),
        ]

        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let longestErrorKey = try XCTUnwrap(
                        RuntimeModelPullApprovalBrokerError.allCases
                            .map(\.localizationKey)
                            .max {
                                localizedModelPullApprovalError($0).count
                                    < localizedModelPullApprovalError($1).count
                            }
                    )
                    let panel = ModelPullApprovalPanel(
                        model: renderSmokeModel(),
                        previewReviews: [review],
                        previewAuditEvents: events,
                        previewErrorLocalizationKey: longestErrorKey
                    )
                    .padding(16)
                    .frame(width: compactDetailSize.width, alignment: .topLeading)
                    .background(Color(nsColor: .windowBackgroundColor))
                    .environment(\.locale, Locale(identifier: language.localeIdentifier))
                    .environment(\.dynamicTypeSize, .accessibility3)
                    .preferredColorScheme(appearance.preferredColorScheme)
                    let idealSize = fittingSize(panel)
                    XCTAssertLessThanOrEqual(
                        idealSize.height,
                        compactDetailSize.height,
                        "ModelPullApprovalPanel height \(language.rawValue) \(appearance.rawValue)"
                    )
                    let bitmap = try render(
                        panel.frame(
                            width: compactDetailSize.width,
                            height: compactDetailSize.height,
                            alignment: .topLeading
                        ),
                        size: compactDetailSize
                    )
                    assertMeaningfulRender(
                        bitmap,
                        label: "ModelPullApprovalPanel \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    func testPrimaryCompanionSurfacesRenderAtMinimumDetailSizeAcrossLanguagesAndAppearances() throws {
        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let model = renderSmokeModel()
                    let surfaces: [(String, AnyView)] = [
                        ("StatusView", AnyView(StatusView(model: model))),
                        ("PairingView", AnyView(PairingView(model: model))),
                        ("RemoteRelayRoutePanel", AnyView(RemoteRelayRoutePanel(model: model))),
                        ("TrustedDevicesView", AnyView(TrustedDevicesView(model: model))),
                        ("RuntimeDocumentSourcesView", AnyView(RuntimeDocumentSourcesView(model: model))),
                        ("LogsView", AnyView(LogsView(model: model))),
                    ]

                    for (name, surface) in surfaces {
                        let bitmap = try render(
                            surface
                                .environment(\.locale, Locale(identifier: language.localeIdentifier))
                                .preferredColorScheme(appearance.preferredColorScheme),
                            size: minimumDetailSize
                        )

                        assertMeaningfulRender(
                            bitmap,
                            label: "\(name) \(language.rawValue) \(appearance.rawValue)"
                        )
                    }
                }
            }
        }
    }

    func testPopulatedDocumentSourceInspectorAndReviewRenderAcrossLanguagesAndAppearances() async throws {
        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try await withStoredPreferences(language: language, appearance: appearance) {
                    let directoryURL = FileManager.default.temporaryDirectory
                        .appendingPathComponent("aetherlink-render-document-review-\(UUID().uuidString)", isDirectory: true)
                    try FileManager.default.createDirectory(at: directoryURL, withIntermediateDirectories: true)
                    defer { try? FileManager.default.removeItem(at: directoryURL) }
                    let fileURL = directoryURL.appendingPathComponent(
                        "quarterly-runtime-knowledge-source-with-a-very-long-review-name-2026.txt"
                    )
                    try "render audit source canary".write(to: fileURL, atomically: true, encoding: .utf8)
                    let store = SQLiteRuntimeDocumentIndexStore(
                        databaseURL: directoryURL.appendingPathComponent("runtime-document-index.sqlite")
                    )
                    let approved = try store.replaceDocument(
                        result: DocumentIngestor().ingest(extractedDocument: ExtractedDocument(
                            fileName: fileURL.lastPathComponent,
                            mimeType: "text/plain",
                            text: "render audit source canary"
                        ))
                    )
                    _ = try store.readApprovedCatalog(
                        limit: 10,
                        actorDeviceID: "render-trusted-device",
                        timestamp: Date(timeIntervalSince1970: 100)
                    )
                    let model = renderSmokeModel(runtimeDocumentIndexStore: store)
                    await model.refreshRuntimeDocumentSources()
                    XCTAssertEqual(model.runtimeDocumentSources.map(\.id), [approved.id])

                    let inspectorBitmap = try render(
                        RuntimeDocumentSourcesView(model: model)
                            .environment(\.locale, Locale(identifier: language.localeIdentifier))
                            .environment(\.dynamicTypeSize, .accessibility3)
                            .preferredColorScheme(appearance.preferredColorScheme),
                        size: minimumDetailSize
                    )
                    assertMeaningfulRender(
                        inspectorBitmap,
                        label: "Populated RuntimeDocumentSourcesView \(language.rawValue) \(appearance.rawValue)"
                    )

                    try "replacement review source canary".write(
                        to: fileURL,
                        atomically: true,
                        encoding: .utf8
                    )
                    await model.prepareRuntimeDocumentSource(
                        fileURL: fileURL,
                        replacingSourceID: approved.id
                    )
                    let review = try XCTUnwrap(model.pendingRuntimeDocumentReview)
                    let reviewBitmap = try render(
                        RuntimeDocumentReviewSheet(
                            review: review,
                            isOperationInFlight: false,
                            errorMessage: nil,
                            confirmedRuntimeSharedScope: .constant(false),
                            onApprove: {},
                            onCancel: {}
                        )
                        .environment(\.locale, Locale(identifier: language.localeIdentifier))
                        .environment(\.dynamicTypeSize, .accessibility3)
                        .preferredColorScheme(appearance.preferredColorScheme),
                        size: compactDetailSize
                    )
                    assertMeaningfulRender(
                        reviewBitmap,
                        label: "RuntimeDocumentReviewSheet \(language.rawValue) \(appearance.rawValue)"
                    )
                    await model.discardRuntimeDocumentSourceReview()
                }
            }
        }
    }

    func testActivePairingQRCodeRendersAtCompactDetailSizeAcrossLanguagesAndAppearances() throws {
        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let model = renderSmokeModel()
                    model.beginPairing(routePolicy: .allowLocalDiagnostic)
                    XCTAssertNotNil(
                        model.pairingSession,
                        "Expected an active pairing QR session for \(language.rawValue) \(appearance.rawValue)"
                    )

                    let bitmap = try render(
                        PairingView(model: model)
                            .environment(\.locale, Locale(identifier: language.localeIdentifier))
                            .preferredColorScheme(appearance.preferredColorScheme),
                        size: compactDetailSize
                    )

                    assertMeaningfulRender(
                        bitmap,
                        label: "Active PairingView \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    func testStatusQuickActionsRenderAtCompactDetailSizeAcrossLanguagesAndAppearances() throws {
        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let model = renderSmokeModel()

                    let bitmap = try render(
                        StatusView(model: model, onGenerateRelayQRCode: {})
                            .environment(\.locale, Locale(identifier: language.localeIdentifier))
                            .preferredColorScheme(appearance.preferredColorScheme),
                        size: compactDetailSize
                    )

                    assertMeaningfulRender(
                        bitmap,
                        label: "Compact StatusView Quick Actions \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    func testStatusModelRowsRenderLongLocalModelNamesAtCompactDetailSizeAcrossLanguagesAndAppearances() throws {
        let models = [
            ModelInfo(
                id: "ollama:qwen3.6-coder-super-long-local-runtime-model-name-with-vision-tools:35b-q8_0",
                name: "Qwen3.6 Coder Super Long Local Runtime Model Name With Vision Tools 35B",
                provider: .ollama,
                kind: .chat,
                capabilities: ["chat", "vision", "raw_future_capability"],
                sizeBytes: 23_400_000_000,
                installed: true,
                running: true,
                source: .local,
                contextWindowTokens: 131_072
            ),
            ModelInfo(
                id: "lm_studio:text-embedding-nomic-long-context-index-model-q8_0",
                name: "Text Embedding Nomic Long Context Index Model",
                provider: .lmStudio,
                kind: .embedding,
                capabilities: ["embedding", "raw_future_capability"],
                sizeBytes: 720_000_000,
                installed: true,
                source: .local,
                contextWindowTokens: 8_192
            ),
        ]

        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let bitmap = try render(
                        VStack(spacing: 0) {
                            ForEach(models, id: \.id) { model in
                                ModelRow(model: model)
                                Divider()
                            }
                        }
                            .padding(20)
                            .background(Color(nsColor: .windowBackgroundColor))
                            .environment(\.locale, Locale(identifier: language.localeIdentifier))
                            .preferredColorScheme(appearance.preferredColorScheme),
                        size: compactDetailSize
                    )

                    assertMeaningfulRender(
                        bitmap,
                        label: "Compact model rows \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    func testStatusModelResidencyStatesRenderAtCompactDetailSizeAcrossLanguagesAndAppearances() async throws {
        let activeModelID = "qwen3.6-coder-super-long-local-runtime-model-name-with-vision-tools-35b-q8_0"
        let activeModel = ModelInfo(
            id: activeModelID,
            name: "Qwen3.6 Coder Super Long Local Runtime Model Name With Vision Tools 35B",
            provider: .ollama,
            kind: .chat,
            sizeBytes: 23_400_000_000,
            installed: true,
            running: true,
            source: .local
        )
        let failureModelID = "runtime-residency-unload-failure-compact-render-q4_k_m"
        let failureModel = ModelInfo(
            id: failureModelID,
            name: "Runtime Residency Unload Failure Compact Render Q4_K_M",
            provider: .ollama,
            kind: .chat,
            installed: true,
            running: true,
            source: .local
        )

        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try await withStoredPreferences(language: language, appearance: appearance) {
                    let activeAggregate = AggregatingLlmBackend(
                        [RenderSmokeResidencyBackend(provider: .ollama, models: [activeModel])],
                        modelIdleUnloadDelayNanoseconds: 60_000_000_000
                    )
                    let activeModelState = renderSmokeModel(backend: activeAggregate)
                    _ = try await collectRenderSmokeChat(
                        activeAggregate.chat(request: renderSmokeChatRequest(model: "ollama:\(activeModelID)"))
                    )
                    activeModelState.refreshModelResidencyStatus()
                    XCTAssertEqual(activeModelState.modelResidency.activeModelID, activeModelID)

                    let activeBitmap = try render(
                        StatusView(model: activeModelState)
                            .environment(\.locale, Locale(identifier: language.localeIdentifier))
                            .preferredColorScheme(appearance.preferredColorScheme),
                        size: compactDetailSize
                    )

                    assertMeaningfulRender(
                        activeBitmap,
                        label: "Compact StatusView active model residency \(language.rawValue) \(appearance.rawValue)"
                    )

                    let failingAggregate = AggregatingLlmBackend(
                        [
                            RenderSmokeResidencyBackend(
                                provider: .ollama,
                                models: [failureModel],
                                unloadErrorMessage: "compact render unload denied"
                            ),
                        ],
                        modelIdleUnloadDelayNanoseconds: 0
                    )
                    let failedUnloadModelState = renderSmokeModel(backend: failingAggregate)
                    _ = try await collectRenderSmokeChat(
                        failingAggregate.chat(request: renderSmokeChatRequest(model: "ollama:\(failureModelID)"))
                    )
                    await waitForModelResidencyEventPrefix(
                        "Model unload failed:",
                        in: failedUnloadModelState,
                        label: "unload failure \(language.rawValue) \(appearance.rawValue)"
                    )

                    let failureBitmap = try render(
                        StatusView(model: failedUnloadModelState)
                            .environment(\.locale, Locale(identifier: language.localeIdentifier))
                            .preferredColorScheme(appearance.preferredColorScheme),
                        size: compactDetailSize
                    )

                    assertMeaningfulRender(
                        failureBitmap,
                        label: "Compact StatusView unload-failure model residency \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    func testTrustedDeviceRowsRenderLongDeviceNamesAtCompactDetailSizeAcrossLanguagesAndAppearances() async throws {
        let devices = [
            TrustedDevice(
                id: "android-client-foldable-runtime-owner-device-with-long-suffix-001",
                name: "Hanchangha Foldable Android Runtime Client With Very Long Owner Label",
                publicKeyBase64: renderSmokePublicKeyBase64(),
                pairedAt: Date(timeIntervalSince1970: 1_720_000_000)
            ),
            TrustedDevice(
                id: "android-tablet-field-test-client-with-long-route-identifier-002",
                name: "Shared Family Tablet Android Client For Cross Network Relay Testing",
                publicKeyBase64: renderSmokePublicKeyBase64(),
                pairedAt: Date(timeIntervalSince1970: 1_720_086_400)
            ),
        ]

        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try await withStoredPreferences(language: language, appearance: appearance) {
                    let trustedDeviceStore = isolatedTrustedDeviceStore()
                    for device in devices {
                        try await trustedDeviceStore.trust(device)
                    }
                    let model = renderSmokeModel(trustedDeviceStore: trustedDeviceStore)
                    await model.refreshTrustedDevices()

                    XCTAssertEqual(
                        model.trustedDevices.count,
                        devices.count,
                        "Expected trusted-device rows for \(language.rawValue) \(appearance.rawValue)"
                    )

                    let bitmap = try render(
                        TrustedDevicesView(model: model)
                            .environment(\.locale, Locale(identifier: language.localeIdentifier))
                            .preferredColorScheme(appearance.preferredColorScheme),
                        size: compactDetailSize
                    )

                    assertMeaningfulRender(
                        bitmap,
                        label: "Compact TrustedDevicesView long device rows \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    func testRuntimeMemoryInspectorRendersAcrossLanguagesAndAppearances() throws {
        let source = RuntimeMemoryEntrySource(
            kind: "long_inactivity_summary",
            draftID: "render-draft-id",
            summaryMethod: "extractive",
            session: RuntimeMemoryEntrySourceSession(
                sessionID: "render-session-id",
                title: "Roadmap planning with source metadata",
                model: "qwen-local",
                lastActivityAt: Date(timeIntervalSince1970: 100),
                messageCount: 7,
                inactiveSeconds: 7200
            ),
            sourceMessageCount: 7,
            sourceRange: "Messages 1-7",
            sourcePointers: [
                RuntimeMemoryEntrySourcePointer(
                    sessionID: "render-session-id",
                    messageIndex: 0,
                    role: "user",
                    createdAt: Date(timeIntervalSince1970: 100),
                    excerpt: "Prefer concise roadmap updates with concrete validation."
                ),
                RuntimeMemoryEntrySourcePointer(
                    sessionID: "render-session-id",
                    messageIndex: 1,
                    role: "assistant",
                    createdAt: Date(timeIntervalSince1970: 110),
                    excerpt: "Keep no-device evidence separate from live-device proof."
                ),
                RuntimeMemoryEntrySourcePointer(
                    sessionID: "render-session-id",
                    messageIndex: 2,
                    role: "user",
                    createdAt: Date(timeIntervalSince1970: 120),
                    excerpt: "This third excerpt should stay collapsed by default."
                ),
            ]
        )
        let entries = [
            RuntimeMemoryEntry(
                id: "memory-enabled",
                content: "Prefer concise technical explanations.",
                enabled: true,
                createdAt: Date(timeIntervalSince1970: 100),
                updatedAt: Date(timeIntervalSince1970: 120),
                source: source
            ),
            RuntimeMemoryEntry(
                id: "memory-paused",
                content: "Paused project-specific note.",
                enabled: false,
                createdAt: Date(timeIntervalSince1970: 80),
                updatedAt: Date(timeIntervalSince1970: 90)
            ),
        ]

        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let bitmap = try render(
                        RuntimeMemoryInspectorSheet(
                            entries: entries,
                            errorMessage: nil,
                            onRefresh: {}
                        )
                        .environment(\.locale, Locale(identifier: language.localeIdentifier))
                        .preferredColorScheme(appearance.preferredColorScheme),
                        size: minimumDetailSize
                    )

                    assertMeaningfulRender(
                        bitmap,
                        label: "RuntimeMemoryInspectorSheet \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    func testRuntimeHistoryInspectorRendersAcrossLanguagesAndAppearances() throws {
        let sessions = [
            RuntimeChatStoredSession(
                sessionID: "session-active",
                title: "Planning next release",
                model: "ollama:llama3.1:8b",
                lastActivityAt: Date(timeIntervalSince1970: 120),
                messageCount: 4,
                status: "active",
                lastEvent: "done",
                lastFinishReason: "stop"
            ),
            RuntimeChatStoredSession(
                sessionID: "session-archived",
                title: "Archived research",
                model: "lmstudio:local/vision",
                lastActivityAt: Date(timeIntervalSince1970: 90),
                messageCount: 6,
                status: "archived",
                archivedAt: Date(timeIntervalSince1970: 100),
                lastEvent: "archived"
            ),
        ]

        for language in AetherLinkAppLanguage.allCases {
            for appearance in AetherLinkAppAppearance.pickerOptions {
                try withStoredPreferences(language: language, appearance: appearance) {
                    let bitmap = try render(
                        RuntimeHistoryInspectorSheet(
                            sessions: sessions,
                            transcriptMessages: [
                                "session-active": [
                                    RuntimeChatStoredMessage(
                                        role: "user",
                                        content: "What should ship next?",
                                        createdAt: Date(timeIntervalSince1970: 110)
                                    ),
                                    RuntimeChatStoredMessage(
                                        role: "assistant",
                                        content: "Ship runtime-owned history inspection.",
                                        reasoning: "Check stored events before showing the summary.",
                                        createdAt: Date(timeIntervalSince1970: 120)
                                    ),
                                ],
                            ],
                            transcriptErrors: [:],
                            errorMessage: nil,
                            retentionStatus: CompanionRuntimeChatRetentionStatus(
                                state: .completed,
                                prunedDeletedSessionCount: 2,
                                lastRunAt: Date(timeIntervalSince1970: 125)
                            ),
                            onRefresh: {},
                            onRunRetentionMaintenance: {},
                            onLoadTranscriptPreview: { _ in }
                        )
                        .environment(\.locale, Locale(identifier: language.localeIdentifier))
                        .preferredColorScheme(appearance.preferredColorScheme),
                        size: minimumDetailSize
                    )

                    assertMeaningfulRender(
                        bitmap,
                        label: "RuntimeHistoryInspectorSheet \(language.rawValue) \(appearance.rawValue)"
                    )
                }
            }
        }
    }

    private func render<Content: View>(_ view: Content, size: CGSize) throws -> NSBitmapImageRep {
        let hostingView = NSHostingView(rootView: view.frame(width: size.width, height: size.height))
        hostingView.frame = NSRect(origin: .zero, size: size)

        let window = NSWindow(
            contentRect: NSRect(origin: .zero, size: size),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        window.contentView = hostingView
        window.layoutIfNeeded()
        hostingView.layoutSubtreeIfNeeded()
        hostingView.displayIfNeeded()
        RunLoop.main.run(until: Date().addingTimeInterval(0.05))

        guard let bitmap = hostingView.bitmapImageRepForCachingDisplay(in: hostingView.bounds) else {
            throw RenderSmokeFailure.bitmapAllocationFailed
        }
        hostingView.cacheDisplay(in: hostingView.bounds, to: bitmap)
        window.contentView = nil
        return bitmap
    }

    private func fittingSize<Content: View>(_ view: Content) -> CGSize {
        let hostingView = NSHostingView(rootView: view)
        hostingView.layoutSubtreeIfNeeded()
        return hostingView.fittingSize
    }

    private func assertMeaningfulRender(
        _ bitmap: NSBitmapImageRep,
        label: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertGreaterThan(bitmap.pixelsWide, 0, "\(label) width", file: file, line: line)
        XCTAssertGreaterThan(bitmap.pixelsHigh, 0, "\(label) height", file: file, line: line)

        let stepX = max(bitmap.pixelsWide / 18, 1)
        let stepY = max(bitmap.pixelsHigh / 14, 1)
        var colors = Set<String>()
        var opaqueSamples = 0

        for y in stride(from: 0, to: bitmap.pixelsHigh, by: stepY) {
            for x in stride(from: 0, to: bitmap.pixelsWide, by: stepX) {
                guard let color = bitmap.colorAt(x: x, y: y)?
                    .usingColorSpace(.deviceRGB)
                else {
                    continue
                }
                if color.alphaComponent > 0.2 {
                    opaqueSamples += 1
                }
                colors.insert(
                    [
                        color.redComponent,
                        color.greenComponent,
                        color.blueComponent,
                        color.alphaComponent,
                    ]
                    .map { Int(($0 * 255).rounded()).clamped(to: 0...255) }
                    .map { String(format: "%02X", $0) }
                    .joined()
                )
            }
        }

        XCTAssertGreaterThan(opaqueSamples, 20, "\(label) opaque samples", file: file, line: line)
        XCTAssertGreaterThanOrEqual(colors.count, 4, "\(label) sampled colors", file: file, line: line)
    }

    private func withStoredPreferences<T>(
        language: AetherLinkAppLanguage,
        appearance: AetherLinkAppAppearance,
        assertions: () throws -> T
    ) throws -> T {
        let previousLanguage = UserDefaults.standard.string(forKey: AetherLinkAppLanguageStorageKey)
        let previousAppearance = UserDefaults.standard.string(forKey: AetherLinkAppAppearanceStorageKey)
        UserDefaults.standard.set(language.rawValue, forKey: AetherLinkAppLanguageStorageKey)
        UserDefaults.standard.set(appearance.rawValue, forKey: AetherLinkAppAppearanceStorageKey)
        defer {
            restore(previousLanguage, forKey: AetherLinkAppLanguageStorageKey)
            restore(previousAppearance, forKey: AetherLinkAppAppearanceStorageKey)
        }
        return try assertions()
    }

    private func withStoredPreferences<T>(
        language: AetherLinkAppLanguage,
        appearance: AetherLinkAppAppearance,
        assertions: () async throws -> T
    ) async throws -> T {
        let previousLanguage = UserDefaults.standard.string(forKey: AetherLinkAppLanguageStorageKey)
        let previousAppearance = UserDefaults.standard.string(forKey: AetherLinkAppAppearanceStorageKey)
        UserDefaults.standard.set(language.rawValue, forKey: AetherLinkAppLanguageStorageKey)
        UserDefaults.standard.set(appearance.rawValue, forKey: AetherLinkAppAppearanceStorageKey)
        defer {
            restore(previousLanguage, forKey: AetherLinkAppLanguageStorageKey)
            restore(previousAppearance, forKey: AetherLinkAppAppearanceStorageKey)
        }
        return try await assertions()
    }

    private func restore(_ value: String?, forKey key: String) {
        if let value {
            UserDefaults.standard.set(value, forKey: key)
        } else {
            UserDefaults.standard.removeObject(forKey: key)
        }
    }

    private func isolatedDefaults() -> UserDefaults {
        let suiteName = "dev.aetherlink.render-smoke.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defaults.removePersistentDomain(forName: suiteName)
        return defaults
    }

    private func renderSmokeModel(
        backend: (any LlmBackend)? = nil,
        trustedDeviceStore: TrustedDeviceStore? = nil,
        runtimeDocumentIndexStore: SQLiteRuntimeDocumentIndexStore? = nil
    ) -> CompanionAppModel {
        CompanionAppModel(
            backend: backend ?? RenderSmokeBackend(models: []),
            environment: isolatedRuntimeIdentityEnvironment(),
            userDefaults: isolatedDefaults(),
            trustedDeviceStore: trustedDeviceStore ?? isolatedTrustedDeviceStore(),
            runtimeDocumentIndexStore: runtimeDocumentIndexStore ?? isolatedRuntimeDocumentIndexStore(),
            runtimeModelPullApprovalPersistence: isolatedRuntimeModelPullApprovalStore(),
            runtimeRouteHostProvider: { "127.0.0.1" }
        )
    }

    private func isolatedTrustedDeviceStore() -> TrustedDeviceStore {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-render-trusted-devices-\(UUID().uuidString)", isDirectory: true)
        return TrustedDeviceStore(fileURL: directoryURL.appendingPathComponent("trusted-devices.json"))
    }

    private func isolatedRuntimeDocumentIndexStore() -> SQLiteRuntimeDocumentIndexStore {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-render-document-index-\(UUID().uuidString)", isDirectory: true)
        return SQLiteRuntimeDocumentIndexStore(
            databaseURL: directoryURL.appendingPathComponent("runtime-document-index.sqlite")
        )
    }

    private func isolatedRuntimeModelPullApprovalStore() -> SQLiteRuntimeModelPullApprovalStore {
        let directoryURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-render-model-pull-\(UUID().uuidString)", isDirectory: true)
        return SQLiteRuntimeModelPullApprovalStore(
            databaseURL: directoryURL.appendingPathComponent("runtime-model-pull-approvals.sqlite")
        )
    }

    private func isolatedRuntimeIdentityEnvironment() -> [String: String] {
        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("aetherlink-render-runtime-identity-\(UUID().uuidString).json")
        return ["AETHERLINK_RUNTIME_IDENTITY_FILE": fileURL.path]
    }

    private func renderSmokePublicKeyBase64() -> String {
        P256.Signing.PrivateKey().publicKey.derRepresentation.base64EncodedString()
    }

    private func renderSmokeChatRequest(model: String) -> ChatRequest {
        ChatRequest(
            generationID: UUID().uuidString,
            sessionID: "render-smoke-residency",
            model: model,
            messages: [ChatMessage(role: "user", content: "Render the residency card.")]
        )
    }

    private func collectRenderSmokeChat(
        _ stream: AsyncThrowingStream<ChatStreamEvent, Error>
    ) async throws -> [ChatStreamEvent] {
        var events: [ChatStreamEvent] = []
        for try await event in stream {
            events.append(event)
        }
        return events
    }

    private func waitForModelResidencyEventPrefix(
        _ prefix: String,
        in model: CompanionAppModel,
        label: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async {
        for _ in 0..<50 {
            if model.modelResidency.lastEvent?.hasPrefix(prefix) == true {
                return
            }
            try? await Task.sleep(nanoseconds: 10_000_000)
        }
        XCTFail(
            "Timed out waiting for model residency event \(prefix) in \(label); last event: \(model.modelResidency.lastEvent ?? "nil")",
            file: file,
            line: line
        )
    }
}

private enum RenderSmokeFailure: Error {
    case bitmapAllocationFailed
}

private final class RenderSmokeBackend: LlmBackend, @unchecked Sendable {
    let provider: ModelProvider = .aggregate
    private let models: [ModelInfo]

    init(models: [ModelInfo]) {
        self.models = models
    }

    func healthCheck() async -> BackendStatus {
        .available
    }

    func listModels() async throws -> [ModelInfo] {
        models
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            continuation.finish()
        }
    }

    func cancel(generationID: String) -> GenerationCancellationResult {
        .notFound(generationID: generationID)
    }
}

private final class RenderSmokeResidencyBackend: LlmBackend, @unchecked Sendable {
    let provider: ModelProvider
    private let models: [ModelInfo]
    private let unloadErrorMessage: String?

    init(provider: ModelProvider, models: [ModelInfo], unloadErrorMessage: String? = nil) {
        self.provider = provider
        self.models = models
        self.unloadErrorMessage = unloadErrorMessage
    }

    func healthCheck() async -> BackendStatus {
        .available
    }

    func listModels() async throws -> [ModelInfo] {
        models
    }

    func chat(request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            continuation.yield(.done(inputTokens: 1, outputTokens: 1))
            continuation.finish()
        }
    }

    func unloadModel(providerModelID: String) async throws -> ModelUnloadResult {
        if let unloadErrorMessage {
            throw NSError(
                domain: "AetherLinkRenderSmokeResidency",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: unloadErrorMessage]
            )
        }
        return .unloaded(provider: provider, modelID: providerModelID)
    }

    func cancel(generationID: String) -> GenerationCancellationResult {
        .notFound(generationID: generationID)
    }
}

private extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self {
        min(max(self, range.lowerBound), range.upperBound)
    }
}
