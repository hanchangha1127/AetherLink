import CompanionCore
import SwiftUI

struct ModelPullApprovalPanel: View {
    @ObservedObject var model: CompanionAppModel
    @State private var confirmedOperationIDs = Set<String>()
    private let previewReviews: [CompanionPendingModelPullReview]?
    private let previewAuditEvents: [RuntimeModelPullAuditSummary]?
    private let previewErrorLocalizationKey: String?

    init(model: CompanionAppModel) {
        self.model = model
        self.previewReviews = nil
        self.previewAuditEvents = nil
        self.previewErrorLocalizationKey = nil
    }

    init(
        model: CompanionAppModel,
        previewReviews: [CompanionPendingModelPullReview],
        previewAuditEvents: [RuntimeModelPullAuditSummary],
        previewErrorLocalizationKey: String? = nil
    ) {
        self.model = model
        self.previewReviews = previewReviews
        self.previewAuditEvents = previewAuditEvents
        self.previewErrorLocalizationKey = previewErrorLocalizationKey
    }

    private var reviews: [CompanionPendingModelPullReview] {
        previewReviews ?? model.pendingModelPullReviews
    }

    private var auditEvents: [RuntimeModelPullAuditSummary] {
        previewAuditEvents ?? model.modelPullAuditEvents
    }

    private var approvalErrorLocalizationKey: String? {
        previewErrorLocalizationKey ?? model.modelPullApprovalErrorLocalizationKey
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if let errorKey = approvalErrorLocalizationKey {
                let error = localizedModelPullApprovalError(errorKey)
                Label(error, systemImage: "exclamationmark.triangle.fill")
                    .font(.callout)
                    .foregroundStyle(.orange)
                    .padding(.bottom, 12)
                    .accessibilityLabel(
                        Text(
                            String(
                                format: NSLocalizedString("Model download approval error: %@", comment: ""),
                                error
                            )
                        )
                    )
            }

            if reviews.isEmpty {
                ContentUnavailableView(
                    NSLocalizedString("No pending model downloads", comment: ""),
                    systemImage: "arrow.down.circle",
                    description: Text(
                        NSLocalizedString(
                            "Trusted device download requests will appear here for runtime-host approval.",
                            comment: ""
                        )
                    )
                )
                .frame(maxWidth: .infinity, minHeight: 140)
            } else {
                VStack(spacing: 0) {
                    ForEach(reviews) { review in
                        modelPullReviewRow(review)
                        if review.id != reviews.last?.id {
                            Divider()
                        }
                    }
                }
            }

            if !auditEvents.isEmpty {
                Divider()
                    .padding(.vertical, 14)
                Text(NSLocalizedString("Recent model download decisions", comment: ""))
                    .font(.headline)
                VStack(spacing: 0) {
                    ForEach(Array(auditEvents.prefix(8))) { event in
                        HStack(spacing: 10) {
                            Image(systemName: modelPullAuditSymbol(event.event))
                                .foregroundStyle(modelPullAuditColor(event.event))
                                .frame(width: 18)
                            Text(localizedModelPullAuditEvent(event.event))
                                .font(.callout)
                            Spacer(minLength: 12)
                            Text(event.occurredAt, style: .relative)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 8)
                        .accessibilityElement(children: .combine)
                    }
                }
            }
        }
        .onChange(of: reviews.map(\.operationID)) { _, currentIDs in
            confirmedOperationIDs.formIntersection(currentIDs)
        }
    }

    @ViewBuilder
    private func modelPullReviewRow(_ review: CompanionPendingModelPullReview) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "arrow.down.square")
                    .font(.title3)
                    .foregroundStyle(.orange)
                    .frame(width: 24)
                VStack(alignment: .leading, spacing: 4) {
                    Text(review.model)
                        .font(.headline)
                        .lineLimit(2)
                        .textSelection(.enabled)
                    Text(localizedModelPullRequester(review.requestingDeviceName))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    Text(
                        String(
                            format: NSLocalizedString("Key fingerprint %@", comment: ""),
                            review.requestingDeviceKeyFingerprint
                        )
                    )
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    Text(
                        String(
                            format: NSLocalizedString("Review expires %@", comment: ""),
                            review.expiresAt.formatted(
                                .relative(presentation: .named)
                                    .locale(
                                        Locale(
                                            identifier: AetherLinkAppLanguage.selected.localeIdentifier
                                        )
                                    )
                            )
                        )
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
                Spacer(minLength: 8)
                Text(NSLocalizedString("Ollama", comment: ""))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
            }

            Toggle(
                NSLocalizedString("I approve this runtime-host model download.", comment: ""),
                isOn: confirmationBinding(for: review.operationID)
            )
            .toggleStyle(.checkbox)
            .disabled(review.isDispatching || model.isModelPullDecisionInFlight)

            HStack(spacing: 8) {
                Spacer()
                Button {
                    confirmedOperationIDs.remove(review.operationID)
                    Task {
                        await model.dismissModelPull(operationID: review.operationID)
                    }
                } label: {
                    Label(NSLocalizedString("Dismiss", comment: ""), systemImage: "xmark")
                }
                .help(NSLocalizedString("Dismiss model download request", comment: ""))
                .disabled(review.isDispatching || model.isModelPullDecisionInFlight)

                Button {
                    Task {
                        await model.approveModelPull(operationID: review.operationID)
                        confirmedOperationIDs.remove(review.operationID)
                    }
                } label: {
                    Label(NSLocalizedString("Approve Download", comment: ""), systemImage: "checkmark")
                }
                .buttonStyle(.borderedProminent)
                .help(NSLocalizedString("Approve model download on this runtime host", comment: ""))
                .disabled(
                    !modelPullApprovalIsEnabled(
                        operationID: review.operationID,
                        confirmedOperationIDs: confirmedOperationIDs,
                        reviewIsDispatching: review.isDispatching,
                        decisionIsInFlight: model.isModelPullDecisionInFlight
                    )
                )
            }
        }
        .padding(.vertical, 12)
        .accessibilityElement(children: .contain)
    }

    private func confirmationBinding(for operationID: String) -> Binding<Bool> {
        Binding(
            get: { confirmedOperationIDs.contains(operationID) },
            set: { isConfirmed in
                if isConfirmed {
                    confirmedOperationIDs.insert(operationID)
                } else {
                    confirmedOperationIDs.remove(operationID)
                }
            }
        )
    }
}

func modelPullApprovalIsEnabled(
    operationID: String,
    confirmedOperationIDs: Set<String>,
    reviewIsDispatching: Bool,
    decisionIsInFlight: Bool
) -> Bool {
    confirmedOperationIDs.contains(operationID)
        && !reviewIsDispatching
        && !decisionIsInFlight
}

func localizedModelPullRequester(_ requestingDeviceName: String) -> String {
    let isolatedName = "\u{2068}\(requestingDeviceName)\u{2069}"
    return String(
        format: NSLocalizedString("Requested by %@", comment: ""),
        isolatedName
    )
}

func localizedModelPullApprovalError(_ localizationKey: String) -> String {
    NSLocalizedString(localizationKey, comment: "")
}

func localizedModelPullAuditEvent(_ event: String) -> String {
    switch event {
    case "requested":
        return NSLocalizedString("Download review requested", comment: "")
    case "dispatch_reserved":
        return NSLocalizedString("Approved and dispatch reserved", comment: "")
    case "success":
        return NSLocalizedString("Download completed", comment: "")
    case "failure":
        return NSLocalizedString("Download failed", comment: "")
    case "result_suppressed":
        return NSLocalizedString("Result suppressed after authority changed", comment: "")
    case "dismissal":
        return NSLocalizedString("Download request dismissed", comment: "")
    case "expiry":
        return NSLocalizedString("Download review expired", comment: "")
    case "connection_closed":
        return NSLocalizedString("Download request cancelled after disconnect", comment: "")
    case "authentication_changed":
        return NSLocalizedString("Download request cancelled after authentication changed", comment: "")
    case "permission_changed":
        return NSLocalizedString("Download request cancelled after permission policy changed", comment: "")
    case "host_restarted":
        return NSLocalizedString("Download request closed after runtime restart", comment: "")
    default:
        return NSLocalizedString("Model download decision recorded", comment: "")
    }
}

private func modelPullAuditSymbol(_ event: String) -> String {
    switch event {
    case "success":
        return "checkmark.circle.fill"
    case "failure", "result_suppressed":
        return "exclamationmark.triangle.fill"
    case "dismissal", "expiry", "connection_closed", "authentication_changed", "permission_changed", "host_restarted":
        return "xmark.circle.fill"
    default:
        return "clock.fill"
    }
}

private func modelPullAuditColor(_ event: String) -> Color {
    switch event {
    case "success":
        return .green
    case "failure", "result_suppressed":
        return .orange
    default:
        return .secondary
    }
}
