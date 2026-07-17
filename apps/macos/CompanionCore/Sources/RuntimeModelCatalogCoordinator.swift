import Foundation
import OllamaBackend

enum RuntimeModelCatalogCoordinatorError: Error {
    case waiterLimitExceeded
}

private final class RuntimeModelCatalogFlight: @unchecked Sendable {
    enum WaiterRegistration {
        case accepted(UUID)
        case waiterLimitExceeded
        case closed(operationCompleted: Bool)
    }

    private let lock = NSLock()
    private var task: Task<Void, Never>?
    private var waiterIDs: Set<UUID> = []
    private var waiterContinuations: [UUID: CheckedContinuation<[ModelInfo], Error>] = [:]
    private var terminalResult: Result<[ModelInfo], Error>?
    private var completed = false
    private var acceptsWaiters = true

    func install(_ task: Task<Void, Never>) {
        lock.withLock {
            precondition(self.task == nil)
            self.task = task
        }
    }

    func result(for waiterID: UUID) async throws -> [ModelInfo] {
        try await withCheckedThrowingContinuation { continuation in
            let immediateResult = lock.withLock { () -> Result<[ModelInfo], Error>? in
                guard waiterIDs.contains(waiterID) else {
                    return .failure(CancellationError())
                }
                if let terminalResult {
                    return terminalResult
                }
                precondition(waiterContinuations[waiterID] == nil)
                waiterContinuations[waiterID] = continuation
                return nil
            }
            if let immediateResult {
                continuation.resume(with: immediateResult)
            }
        }
    }

    func registerWaiter(maximumWaiterCount: Int) -> WaiterRegistration {
        lock.withLock {
            guard acceptsWaiters, !completed else {
                return .closed(operationCompleted: completed)
            }
            guard waiterIDs.count < maximumWaiterCount else {
                return .waiterLimitExceeded
            }
            let waiterID = UUID()
            waiterIDs.insert(waiterID)
            return .accepted(waiterID)
        }
    }

    func cancelWaiter(_ waiterID: UUID) -> Bool {
        let outcome = lock.withLock {
            () -> (continuation: CheckedContinuation<[ModelInfo], Error>?, isEmpty: Bool) in
            guard waiterIDs.remove(waiterID) != nil else {
                return (nil, waiterIDs.isEmpty)
            }
            let continuation = waiterContinuations.removeValue(forKey: waiterID)
            if waiterIDs.isEmpty {
                acceptsWaiters = false
                if !completed {
                    task?.cancel()
                }
            }
            return (continuation, waiterIDs.isEmpty)
        }
        outcome.continuation?.resume(throwing: CancellationError())
        return outcome.isEmpty
    }

    func finishWaiter(_ waiterID: UUID) -> Bool {
        lock.withLock {
            waiterIDs.remove(waiterID)
            if waiterIDs.isEmpty {
                acceptsWaiters = false
            }
            return waiterIDs.isEmpty
        }
    }

    func complete(with result: Result<[ModelInfo], Error>) -> Bool {
        let continuations = lock.withLock {
            () -> [CheckedContinuation<[ModelInfo], Error>] in
            precondition(!completed)
            completed = true
            acceptsWaiters = false
            terminalResult = result
            let continuations = Array(waiterContinuations.values)
            waiterContinuations.removeAll()
            return continuations
        }
        continuations.forEach { $0.resume(with: result) }
        return lock.withLock { waiterIDs.isEmpty }
    }

    var isRetiredAndEmpty: Bool {
        lock.withLock {
            completed && !acceptsWaiters && waiterIDs.isEmpty
        }
    }
}

actor RuntimeModelCatalogCoordinator {
    private let maximumWaiterCount: Int
    private var flight: RuntimeModelCatalogFlight?

    init(maximumWaiterCount: Int) {
        precondition(maximumWaiterCount > 0)
        self.maximumWaiterCount = maximumWaiterCount
    }

    func listModels(
        waiterRegistered: @escaping @Sendable () -> Void,
        operation: @escaping @Sendable () async throws -> [ModelInfo]
    ) async throws -> [ModelInfo] {
        try Task.checkCancellation()

        let selectedFlight: RuntimeModelCatalogFlight
        let waiterID: UUID
        if let existingFlight = flight {
            switch existingFlight.registerWaiter(maximumWaiterCount: maximumWaiterCount) {
            case .accepted(let existingWaiterID):
                selectedFlight = existingFlight
                waiterID = existingWaiterID
            case .waiterLimitExceeded:
                throw RuntimeModelCatalogCoordinatorError.waiterLimitExceeded
            case .closed(operationCompleted: true):
                (selectedFlight, waiterID) = makeFlight(operation: operation)
            case .closed(operationCompleted: false):
                throw RuntimeModelCatalogCoordinatorError.waiterLimitExceeded
            }
        } else {
            (selectedFlight, waiterID) = makeFlight(operation: operation)
        }

        waiterRegistered()
        return try await withTaskCancellationHandler {
            do {
                let models = try await selectedFlight.result(for: waiterID)
                try Task.checkCancellation()
                removeFlightIfCurrent(
                    selectedFlight,
                    whenEmpty: selectedFlight.finishWaiter(waiterID)
                )
                return models
            } catch {
                removeFlightIfCurrent(
                    selectedFlight,
                    whenEmpty: selectedFlight.finishWaiter(waiterID)
                )
                throw error
            }
        } onCancel: {
            _ = selectedFlight.cancelWaiter(waiterID)
        }
    }

    private func makeFlight(
        operation: @escaping @Sendable () async throws -> [ModelInfo]
    ) -> (RuntimeModelCatalogFlight, UUID) {
        let newFlight = RuntimeModelCatalogFlight()
        let task = Task { [weak self] in
            let result: Result<[ModelInfo], Error>
            do {
                result = .success(try await operation())
            } catch {
                result = .failure(error)
            }
            let completedWithoutWaiters = newFlight.complete(with: result)
            guard completedWithoutWaiters, let self else { return }
            await self.removeFlightIfCurrent(newFlight, whenEmpty: true)
        }
        newFlight.install(task)
        flight = newFlight
        guard case .accepted(let waiterID) = newFlight.registerWaiter(
            maximumWaiterCount: maximumWaiterCount
        ) else {
            preconditionFailure("New model catalog flight rejected its first waiter")
        }
        return (newFlight, waiterID)
    }

    private func removeFlightIfCurrent(
        _ selectedFlight: RuntimeModelCatalogFlight,
        whenEmpty: Bool
    ) {
        guard whenEmpty,
              flight === selectedFlight,
              selectedFlight.isRetiredAndEmpty else { return }
        flight = nil
    }
}
