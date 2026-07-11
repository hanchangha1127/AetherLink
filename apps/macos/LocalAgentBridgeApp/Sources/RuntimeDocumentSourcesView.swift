import AppKit
import CompanionCore
import Foundation
import SwiftUI
import UniformTypeIdentifiers

struct RuntimeDocumentSourcesView: View {
    @ObservedObject var model: CompanionAppModel

    @Environment(\.dismiss) private var dismiss
    @State private var isFileImporterPresented = false
    @State private var replacingSourceID: String?
    @State private var pendingRemoval: CompanionRuntimeDocumentSource?
    @State private var isReviewPresented = false
    @State private var confirmedRuntimeSharedScope = false
    @State private var importerError: String?
    @State private var auditDocument: RuntimeDocumentAuditFile?
    @State private var isAuditExporterPresented = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            header

            Text(NSLocalizedString("Every authenticated trusted device connected to this runtime can list approved source metadata and receive bounded lexical search snippets. Original paths, bookmarks, full files, queries, and document contents are not included in the audit export.", comment: ""))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            if let errorMessage = visibleErrorMessage {
                warningBanner(errorMessage)
            }

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 18) {
                    sourceSection
                    Divider()
                    auditSection
                }
                .padding(.vertical, 2)
            }
        }
        .padding(24)
        .frame(minWidth: 680, minHeight: 560)
        .background(Color(nsColor: .windowBackgroundColor))
        .task {
            await model.refreshRuntimeDocumentSources()
            presentReviewIfNeeded()
        }
        .onChange(of: model.pendingRuntimeDocumentReview?.id) { _, reviewID in
            confirmedRuntimeSharedScope = false
            isReviewPresented = reviewID != nil
        }
        .fileImporter(
            isPresented: $isFileImporterPresented,
            allowedContentTypes: runtimeDocumentSupportedContentTypes,
            allowsMultipleSelection: false,
            onCompletion: handleFileImport
        )
        .sheet(isPresented: $isReviewPresented, onDismiss: discardPendingReviewIfNeeded) {
            if let review = model.pendingRuntimeDocumentReview {
                RuntimeDocumentReviewSheet(
                    review: review,
                    isOperationInFlight: model.isRuntimeDocumentSourceOperationInFlight,
                    errorMessage: model.runtimeDocumentSourcesIssue.map(localizedRuntimeDocumentSourceIssue),
                    confirmedRuntimeSharedScope: $confirmedRuntimeSharedScope,
                    onApprove: approvePendingReview,
                    onCancel: cancelPendingReview
                )
            }
        }
        .confirmationDialog(
            pendingRemoval.map {
                String(
                    format: NSLocalizedString("Remove source %@?", comment: ""),
                    $0.displayName
                )
            } ?? NSLocalizedString("Remove this source and stop sharing it with trusted devices?", comment: ""),
            isPresented: Binding(
                get: { pendingRemoval != nil },
                set: { if !$0 { pendingRemoval = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button(NSLocalizedString("Remove Source", comment: ""), role: .destructive) {
                removePendingSource()
            }
            Button(NSLocalizedString("Cancel", comment: ""), role: .cancel) {}
        } message: {
            Text(NSLocalizedString("Removing deletes the local index and approval. Content-free audit tombstones remain.", comment: ""))
        }
        .fileExporter(
            isPresented: $isAuditExporterPresented,
            document: auditDocument,
            contentType: .json,
            defaultFilename: "aetherlink-document-audit.json"
        ) { result in
            if case .failure = result {
                importerError = NSLocalizedString("The document source audit could not be exported.", comment: "")
            }
            auditDocument = nil
        }
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 12) {
            Label(NSLocalizedString("Document Source Inspector", comment: ""), systemImage: "doc.text.magnifyingglass")
                .font(.title2.weight(.semibold))
                .accessibilityAddTraits(.isHeader)

            Spacer(minLength: 0)

            if model.isRuntimeDocumentSourceOperationInFlight {
                ProgressView()
                    .controlSize(.small)
                    .accessibilityLabel(Text(NSLocalizedString("Document source operation in progress", comment: "")))
            }

            Button {
                Task { await model.refreshRuntimeDocumentSources() }
            } label: {
                Label(NSLocalizedString("Refresh Document Sources", comment: ""), systemImage: "arrow.clockwise")
            }
            .buttonStyle(.bordered)
            .disabled(model.isRuntimeDocumentSourceOperationInFlight)
            .help(NSLocalizedString("Refresh Document Sources", comment: ""))

            Button {
                dismiss()
            } label: {
                Text(NSLocalizedString("Close", comment: ""))
            }
            .keyboardShortcut(.cancelAction)
            .accessibilityLabel(Text(NSLocalizedString("Close Document Source Inspector", comment: "")))
        }
    }

    @ViewBuilder
    private var sourceSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(NSLocalizedString("Approved sources", comment: ""))
                        .font(.headline)
                        .accessibilityAddTraits(.isHeader)
                    Text(runtimeDocumentSourceCountText(model.runtimeDocumentSources.count))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer(minLength: 0)

                Button {
                    replacingSourceID = nil
                    importerError = nil
                    isFileImporterPresented = true
                } label: {
                    Label(NSLocalizedString("Add Source", comment: ""), systemImage: "plus")
                }
                .buttonStyle(.borderedProminent)
                .disabled(model.isRuntimeDocumentSourceOperationInFlight)
                .help(NSLocalizedString("Review Document Source", comment: ""))
            }

            if model.runtimeDocumentSources.isEmpty {
                ContentUnavailableView(
                    NSLocalizedString("No document sources", comment: ""),
                    systemImage: "doc.badge.plus",
                    description: Text(NSLocalizedString("Add a document source to make approved metadata and bounded search snippets available to authenticated trusted devices.", comment: ""))
                )
                .frame(maxWidth: .infinity, minHeight: 180)
            } else {
                LazyVStack(alignment: .leading, spacing: 10) {
                    ForEach(model.runtimeDocumentSources) { source in
                        RuntimeDocumentSourceRow(
                            source: source,
                            isDisabled: model.isRuntimeDocumentSourceOperationInFlight,
                            onReplace: {
                                replacingSourceID = source.id
                                importerError = nil
                                isFileImporterPresented = true
                            },
                            onRemove: { pendingRemoval = source }
                        )
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var auditSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(NSLocalizedString("Recent Access Audit", comment: ""))
                        .font(.headline)
                        .accessibilityAddTraits(.isHeader)
                    Text(NSLocalizedString("Audit events are retained for the lifetime of AetherLink app data. Export includes at most the latest 1,000 content-free events.", comment: ""))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer(minLength: 0)

                Button {
                    exportAuditLog()
                } label: {
                    Label(NSLocalizedString("Export Audit", comment: ""), systemImage: "square.and.arrow.up")
                }
                .buttonStyle(.bordered)
                .disabled(model.isRuntimeDocumentSourceOperationInFlight)
                .help(NSLocalizedString("Export Audit", comment: ""))
            }

            if model.runtimeDocumentAuditEvents.isEmpty {
                ContentUnavailableView(
                    NSLocalizedString("No recent access audit events.", comment: ""),
                    systemImage: "clock.arrow.circlepath",
                    description: Text(NSLocalizedString("Audit events are retained for the lifetime of AetherLink app data. Export includes at most the latest 1,000 content-free events.", comment: ""))
                )
                .frame(maxWidth: .infinity, minHeight: 150)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(model.runtimeDocumentAuditEvents.enumerated()), id: \.element.eventID) { index, event in
                        RuntimeDocumentAuditRow(event: event)
                        if index < model.runtimeDocumentAuditEvents.count - 1 {
                            Divider()
                        }
                    }
                }
            }
        }
    }

    private var visibleErrorMessage: String? {
        let candidate = importerError ?? model.runtimeDocumentSourcesIssue.map(localizedRuntimeDocumentSourceIssue)
        guard let candidate else { return nil }
        let trimmed = candidate.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func warningBanner(_ message: String) -> some View {
        Label(message, systemImage: "exclamationmark.triangle.fill")
            .font(.callout)
            .foregroundStyle(.orange)
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 8))
            .accessibilityLabel(Text(message))
    }

    private func handleFileImport(_ result: Result<[URL], Error>) {
        let replacementID = replacingSourceID
        replacingSourceID = nil

        switch result {
        case .success(let urls):
            guard let fileURL = urls.first else { return }
            importerError = nil
            Task {
                await model.prepareRuntimeDocumentSource(
                    fileURL: fileURL,
                    replacingSourceID: replacementID
                )
                presentReviewIfNeeded()
            }
        case .failure(let error):
            if !runtimeDocumentImporterWasCancelled(error) {
                importerError = NSLocalizedString("The selected document is no longer available.", comment: "")
            }
        }
    }

    private func presentReviewIfNeeded() {
        guard model.pendingRuntimeDocumentReview != nil else { return }
        confirmedRuntimeSharedScope = false
        isReviewPresented = true
    }

    private func approvePendingReview() {
        guard confirmedRuntimeSharedScope else { return }
        Task {
            await model.approveRuntimeDocumentSourceReview()
            if model.pendingRuntimeDocumentReview == nil {
                confirmedRuntimeSharedScope = false
                isReviewPresented = false
            }
        }
    }

    private func cancelPendingReview() {
        Task {
            await model.discardRuntimeDocumentSourceReview()
            confirmedRuntimeSharedScope = false
            isReviewPresented = false
        }
    }

    private func discardPendingReviewIfNeeded() {
        confirmedRuntimeSharedScope = false
        guard model.pendingRuntimeDocumentReview != nil else { return }
        Task { await model.discardRuntimeDocumentSourceReview() }
    }

    private func removePendingSource() {
        guard let source = pendingRemoval else { return }
        pendingRemoval = nil
        Task {
            await model.removeRuntimeDocumentSource(
                id: source.id,
                expectedRevision: source.sourceRevision
            )
        }
    }

    private func exportAuditLog() {
        importerError = nil
        Task {
            guard let data = await model.makeRuntimeDocumentAuditExport() else { return }
            auditDocument = RuntimeDocumentAuditFile(data: data)
            isAuditExporterPresented = true
        }
    }
}

private struct RuntimeDocumentSourceRow: View {
    let source: CompanionRuntimeDocumentSource
    let isDisabled: Bool
    let onReplace: () -> Void
    let onRemove: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: "doc.text.fill")
                .font(.title3)
                .foregroundStyle(.secondary)
                .frame(width: 24, height: 24)
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 7) {
                Text(source.displayName)
                    .font(.body.weight(.semibold))
                    .lineLimit(2)
                    .textSelection(.enabled)

                Text(runtimeDocumentMetadataText(
                    mimeType: source.mimeType,
                    characterCount: source.extractedCharacterCount,
                    chunkCount: source.chunkCount
                ))
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

                HStack(spacing: 10) {
                    Label(NSLocalizedString("Approved", comment: ""), systemImage: "checkmark.seal")
                    Text(localizedCompanionDateString(from: source.approvedAt))
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            Spacer(minLength: 8)

            Button(action: onReplace) {
                Label(NSLocalizedString("Replace Source", comment: ""), systemImage: "arrow.triangle.2.circlepath")
            }
            .buttonStyle(.bordered)
            .disabled(isDisabled)
            .help(NSLocalizedString("This source will replace the currently approved revision only after you confirm.", comment: ""))

            Button(role: .destructive, action: onRemove) {
                Image(systemName: "trash")
            }
            .buttonStyle(.bordered)
            .disabled(isDisabled)
            .help(NSLocalizedString("Remove Source", comment: ""))
            .accessibilityLabel(
                Text(
                    String(
                        format: NSLocalizedString("Remove source %@", comment: ""),
                        source.displayName
                    )
                )
            )
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(.separator.opacity(0.5), lineWidth: 1)
        }
        .accessibilityElement(children: .contain)
    }
}

private struct RuntimeDocumentAuditRow: View {
    let event: RuntimeDocumentSourceAuditEvent

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Image(systemName: runtimeDocumentAuditActionIcon(event.action))
                .foregroundStyle(.secondary)
                .frame(width: 18)
                .accessibilityHidden(true)

            Text(runtimeDocumentAuditActionText(event.action))
                .font(.callout.weight(.medium))

            if let resultCount = event.resultCount {
                Text(runtimeDocumentResultCountText(resultCount))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer(minLength: 8)

            Text(localizedCompanionDateString(from: event.occurredAt))
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 10)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text(runtimeDocumentAuditAccessibilityLabel(event)))
    }
}

struct RuntimeDocumentReviewSheet: View {
    let review: CompanionRuntimeDocumentImportReview
    let isOperationInFlight: Bool
    let errorMessage: String?
    @Binding var confirmedRuntimeSharedScope: Bool
    let onApprove: () -> Void
    let onCancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Label(
                NSLocalizedString("Review Document Source", comment: ""),
                systemImage: "doc.text.magnifyingglass"
            )
            .font(.title2.weight(.semibold))
            .accessibilityAddTraits(.isHeader)

            Text(NSLocalizedString(review.replacingExistingSource ? "This source will replace the currently approved revision only after you confirm." : "This source will be available to every authenticated trusted device connected to this runtime.", comment: ""))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            if let errorMessage, !errorMessage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                    .font(.callout)
                    .foregroundStyle(.orange)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 8))
            }

            VStack(alignment: .leading, spacing: 10) {
                Text(review.displayName)
                    .font(.headline)
                    .lineLimit(2)
                    .textSelection(.enabled)
                Text(runtimeDocumentMetadataText(
                    mimeType: review.mimeType,
                    characterCount: review.extractedCharacterCount,
                    chunkCount: review.chunkCount
                ))
                .font(.callout)
                .foregroundStyle(.secondary)
                Text(
                    String(
                        format: NSLocalizedString("Review expires %@", comment: ""),
                        localizedCompanionDateString(from: review.expiresAt)
                    )
                )
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(.separator.opacity(0.5), lineWidth: 1)
            }

            Toggle(isOn: $confirmedRuntimeSharedScope) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(NSLocalizedString("Share with trusted devices", comment: ""))
                        .font(.body.weight(.semibold))
                    Text(NSLocalizedString("This source will be available to every authenticated trusted device connected to this runtime.", comment: ""))
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .toggleStyle(.checkbox)
            .disabled(isOperationInFlight)
            .accessibilityHint(Text(NSLocalizedString("Share with trusted devices", comment: "")))

            HStack(spacing: 10) {
                Spacer(minLength: 0)
                Button(NSLocalizedString("Cancel", comment: ""), action: onCancel)
                    .keyboardShortcut(.cancelAction)
                    .disabled(isOperationInFlight)
                Button(action: onApprove) {
                    if isOperationInFlight {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Label(
                            NSLocalizedString("Approve and Share", comment: ""),
                            systemImage: "checkmark.shield"
                        )
                    }
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
                .disabled(!confirmedRuntimeSharedScope || isOperationInFlight)
                .accessibilityLabel(Text(NSLocalizedString("Approve and Share", comment: "")))
            }
        }
        .padding(24)
        .frame(minWidth: 520, minHeight: 390)
        .interactiveDismissDisabled(isOperationInFlight)
    }
}

private struct RuntimeDocumentAuditFile: FileDocument {
    static var readableContentTypes: [UTType] { [.json] }

    let data: Data

    init(data: Data) {
        self.data = data
    }

    init(configuration: ReadConfiguration) throws {
        data = configuration.file.regularFileContents ?? Data()
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: data)
    }
}

private let runtimeDocumentSupportedContentTypes: [UTType] = {
    let extensions = [
        "pdf", "doc", "docx", "docm", "dotx", "dotm",
        "xls", "xlt", "xlsx", "xlsm", "xltx", "xltm",
        "ppt", "pps", "pot", "pptx", "pptm", "ppsx", "ppsm", "potx", "potm",
        "hwp", "hwpx", "hwpml", "odt", "ods", "odp", "epub",
        "pages", "numbers", "key", "rtf", "html", "htm", "xhtml", "webarchive", "xml",
        "txt", "md", "markdown", "rst", "adoc", "asciidoc", "log", "text", "conf", "ini",
        "toml", "properties", "env", "csv", "tsv", "json", "jsonl", "yaml", "yml"
    ]
    var seen = Set<String>()
    return extensions.compactMap { UTType(filenameExtension: $0) }.filter { seen.insert($0.identifier).inserted }
}()

private func runtimeDocumentSourceCountText(_ count: Int) -> String {
    "\(count.formatted()) \(NSLocalizedString("Approved sources", comment: ""))"
}

private func runtimeDocumentMetadataText(mimeType: String, characterCount: Int, chunkCount: Int) -> String {
    let characterText = "\(characterCount.formatted()) \(NSLocalizedString("Characters", comment: ""))"
    let chunkText = "\(chunkCount.formatted()) \(NSLocalizedString("Chunks", comment: ""))"
    return "\(mimeType) | \(characterText) | \(chunkText)"
}

func runtimeDocumentAuditActionText(_ action: RuntimeDocumentSourceAuditAction) -> String {
    switch action {
    case .approved: return NSLocalizedString("Approved", comment: "")
    case .indexed: return NSLocalizedString("Indexed", comment: "")
    case .reindexed: return NSLocalizedString("Reindexed", comment: "")
    case .catalogListed: return NSLocalizedString("Catalog listed", comment: "")
    case .semanticAccessed: return NSLocalizedString("Semantic access", comment: "")
    case .queried: return NSLocalizedString("Queried", comment: "")
    case .anchorResolved: return NSLocalizedString("Anchor resolved", comment: "")
    case .citationResolved: return NSLocalizedString("Citation resolved", comment: "")
    case .trustedSourceReviewPrepared: return NSLocalizedString("Trust review prepared", comment: "")
    case .trustedSourceReviewDismissed: return NSLocalizedString("Trust review dismissed", comment: "")
    case .trustedSourceApproved: return NSLocalizedString("Trusted source approved", comment: "")
    case .trustedSourcesListed: return NSLocalizedString("Trusted sources listed", comment: "")
    case .trustedSourceRevoked: return NSLocalizedString("Trusted source revoked", comment: "")
    case .trustedSourceContextConsumed: return NSLocalizedString("Used in chat", comment: "")
    case .revoked: return NSLocalizedString("Revoked", comment: "")
    case .deleted: return NSLocalizedString("Deleted", comment: "")
    }
}

private func runtimeDocumentAuditActionIcon(_ action: RuntimeDocumentSourceAuditAction) -> String {
    switch action {
    case .approved: return "checkmark.shield"
    case .indexed, .reindexed: return "doc.badge.gearshape"
    case .catalogListed: return "list.bullet.rectangle"
    case .semanticAccessed: return "sparkle.magnifyingglass"
    case .queried: return "magnifyingglass"
    case .anchorResolved: return "link"
    case .citationResolved: return "quote.bubble"
    case .trustedSourceReviewPrepared: return "doc.text.magnifyingglass"
    case .trustedSourceReviewDismissed: return "xmark.circle"
    case .trustedSourceApproved: return "checkmark.shield"
    case .trustedSourcesListed: return "list.bullet.rectangle"
    case .trustedSourceRevoked: return "shield.slash"
    case .trustedSourceContextConsumed: return "text.document"
    case .revoked: return "hand.raised.slash"
    case .deleted: return "trash"
    }
}

private func runtimeDocumentResultCountText(_ count: Int) -> String {
    count.formatted()
}

private func runtimeDocumentAuditAccessibilityLabel(_ event: RuntimeDocumentSourceAuditEvent) -> String {
    var parts = [
        runtimeDocumentAuditActionText(event.action),
        localizedCompanionDateString(from: event.occurredAt)
    ]
    if let resultCount = event.resultCount {
        parts.append(runtimeDocumentResultCountText(resultCount))
    }
    return parts.joined(separator: ". ")
}

private func runtimeDocumentImporterWasCancelled(_ error: Error) -> Bool {
    let cocoaError = error as NSError
    return cocoaError.domain == NSCocoaErrorDomain && cocoaError.code == NSUserCancelledError
}

func localizedRuntimeDocumentSourceIssue(
    _ issue: RuntimeDocumentSourceManagementError
) -> String {
    switch issue {
    case .sourceUnavailable:
        return NSLocalizedString("The selected document is no longer available.", comment: "")
    case .unsupportedOrUnreadableDocument:
        return NSLocalizedString("AetherLink could not extract supported text from this document.", comment: "")
    case .resourceLimitExceeded:
        return NSLocalizedString("This document exceeds the local ingestion safety limits.", comment: "")
    case .reviewExpired:
        return NSLocalizedString("This document review expired. Select the document again.", comment: "")
    case .invalidConfirmation:
        return NSLocalizedString("The document sharing confirmation is invalid. Review the source again.", comment: "")
    case .sourceChanged:
        return NSLocalizedString("This source changed after the review started. Review the latest source before sharing it.", comment: "")
    case .storageUnavailable:
        return NSLocalizedString("AetherLink could not update the local document library.", comment: "")
    }
}
