import Foundation

struct ProductionC1AuthorityPublicationReadPermit: Sendable {
    fileprivate let id: UUID
}

struct ProductionC1AuthorityPublicationWritePermit: Sendable {
    fileprivate let id: UUID
}

enum ProductionC1AuthorityPublicationGateError: Error, Equatable, Sendable {
    case capacityExceeded
}

/// In-process publication fence between exact-bound session results and
/// durable authority mutation. FIFO writer admission prevents a stream of new
/// session operations from starving a pending transition.
actor ProductionC1AuthorityPublicationGate {
    static let defaultMaximumWaiters = 1_024

    private enum Waiter {
        case read(
            UUID,
            CheckedContinuation<ProductionC1AuthorityPublicationReadPermit, Error>
        )
        case write(
            UUID,
            CheckedContinuation<ProductionC1AuthorityPublicationWritePermit, Error>
        )

        var id: UUID {
            switch self {
            case let .read(id, _), let .write(id, _): id
            }
        }
    }

    private let maximumWaiters: Int
    private var activeReaders: Set<UUID> = []
    private var activeWriter: UUID?
    private var waiters: [Waiter] = []

    init(maximumWaiters: Int = defaultMaximumWaiters) {
        precondition(maximumWaiters > 0)
        self.maximumWaiters = maximumWaiters
    }

    func acquireRead() async throws -> ProductionC1AuthorityPublicationReadPermit {
        try Task.checkCancellation()
        let id = UUID()
        if activeWriter == nil,
           !waiters.contains(where: { if case .write = $0 { true } else { false } }) {
            activeReaders.insert(id)
            return ProductionC1AuthorityPublicationReadPermit(id: id)
        }
        let permit: ProductionC1AuthorityPublicationReadPermit =
            try await withTaskCancellationHandler {
                try await withCheckedThrowingContinuation {
                    (continuation: CheckedContinuation<
                        ProductionC1AuthorityPublicationReadPermit,
                        Error
                    >) in
                    guard !Task.isCancelled else {
                        continuation.resume(throwing: CancellationError())
                        return
                    }
                    guard waiters.count < maximumWaiters else {
                        continuation.resume(
                            throwing: ProductionC1AuthorityPublicationGateError.capacityExceeded
                        )
                        return
                    }
                    waiters.append(.read(id, continuation))
                }
            } onCancel: {
                Task { await self.cancelWaiter(id: id) }
            }
        do {
            try Task.checkCancellation()
            return permit
        } catch {
            releaseRead(permit)
            throw error
        }
    }

    func releaseRead(_ permit: ProductionC1AuthorityPublicationReadPermit) {
        guard activeReaders.remove(permit.id) != nil else { return }
        promoteWaiters()
    }

    func acquireWrite() async throws -> ProductionC1AuthorityPublicationWritePermit {
        try Task.checkCancellation()
        let id = UUID()
        if activeWriter == nil, activeReaders.isEmpty, waiters.isEmpty {
            activeWriter = id
            return ProductionC1AuthorityPublicationWritePermit(id: id)
        }
        let permit: ProductionC1AuthorityPublicationWritePermit =
            try await withTaskCancellationHandler {
                try await withCheckedThrowingContinuation {
                    (continuation: CheckedContinuation<
                        ProductionC1AuthorityPublicationWritePermit,
                        Error
                    >) in
                    guard !Task.isCancelled else {
                        continuation.resume(throwing: CancellationError())
                        return
                    }
                    guard waiters.count < maximumWaiters else {
                        continuation.resume(
                            throwing: ProductionC1AuthorityPublicationGateError.capacityExceeded
                        )
                        return
                    }
                    waiters.append(.write(id, continuation))
                }
            } onCancel: {
                Task { await self.cancelWaiter(id: id) }
            }
        do {
            try Task.checkCancellation()
            return permit
        } catch {
            releaseWrite(permit)
            throw error
        }
    }

    func releaseWrite(_ permit: ProductionC1AuthorityPublicationWritePermit) {
        guard activeWriter == permit.id else { return }
        activeWriter = nil
        promoteWaiters()
    }

    #if DEBUG
    func waitingCountForTesting() -> Int {
        waiters.count
    }

    func waitingWriterCountForTesting() -> Int {
        waiters.reduce(into: 0) { count, waiter in
            if case .write = waiter { count += 1 }
        }
    }
    #endif

    private func cancelWaiter(id: UUID) {
        guard let index = waiters.firstIndex(where: { $0.id == id }) else { return }
        let waiter = waiters.remove(at: index)
        switch waiter {
        case let .read(_, continuation):
            continuation.resume(throwing: CancellationError())
        case let .write(_, continuation):
            continuation.resume(throwing: CancellationError())
        }
        promoteWaiters()
    }

    private func promoteWaiters() {
        guard activeWriter == nil, activeReaders.isEmpty, !waiters.isEmpty else {
            return
        }
        switch waiters.removeFirst() {
        case let .write(id, continuation):
            activeWriter = id
            continuation.resume(returning: .init(id: id))
        case let .read(id, continuation):
            activeReaders.insert(id)
            continuation.resume(returning: .init(id: id))
            while let first = waiters.first {
                guard case let .read(nextID, nextContinuation) = first else { break }
                waiters.removeFirst()
                activeReaders.insert(nextID)
                nextContinuation.resume(returning: .init(id: nextID))
            }
        }
    }
}
