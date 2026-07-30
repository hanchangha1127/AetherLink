import Foundation

public final class BonjourAdvertiser: NSObject, NetServiceDelegate, RuntimeAdvertiser,
    RuntimeAdvertisementStatusReporting, @unchecked Sendable
{
    private let lock = NSLock()
    private let lifecycleLock = NSRecursiveLock()
    private let publicationTimeout: TimeInterval
    private let serviceFactory: (
        _ domain: String,
        _ type: String,
        _ name: String,
        _ port: Int32
    ) -> NetService
    private let publishService: (NetService) -> Void
    private let stopService: (NetService) -> Void
    private var service: NetService?
    private var serviceGenerationID: UUID?
    private var publicationTimeoutWorkItem: DispatchWorkItem?
    private var storedAdvertisementStatus = RuntimeAdvertisementStatus.stopped
    private var statusChangeHandler: (
        @Sendable (RuntimeAdvertisementStatus) -> Void
    )?
    public private(set) var serviceName = "AetherLink"

    public var advertisementStatus: RuntimeAdvertisementStatus {
        lock.withLock { storedAdvertisementStatus }
    }

    public var onAdvertisementStatusChange: (
        @Sendable (RuntimeAdvertisementStatus) -> Void
    )? {
        get {
            lock.withLock { statusChangeHandler }
        }
        set {
            lock.withLock { statusChangeHandler = newValue }
        }
    }

    public override convenience init() {
        self.init(
            publicationTimeout: 5,
            serviceFactory: { domain, type, name, port in
                NetService(
                    domain: domain,
                    type: type,
                    name: name,
                    port: port
                )
            },
            publishService: { $0.publish() },
            stopService: { $0.stop() }
        )
    }

    init(
        publicationTimeout: TimeInterval,
        serviceFactory: @escaping (
            _ domain: String,
            _ type: String,
            _ name: String,
            _ port: Int32
        ) -> NetService,
        publishService: @escaping (NetService) -> Void,
        stopService: @escaping (NetService) -> Void
    ) {
        self.publicationTimeout = max(0, publicationTimeout)
        self.serviceFactory = serviceFactory
        self.publishService = publishService
        self.stopService = stopService
        super.init()
    }

    public func start(port: Int32, metadata: RuntimeAdvertisementMetadata = RuntimeAdvertisementMetadata()) {
        let preparation = lifecycleLock.withLock {
            stop(notify: false)
            let service = serviceFactory(
                "local.",
                "_aetherlink._tcp.",
                serviceName,
                port
            )
            service.setTXTRecord(NetService.data(fromTXTRecord: metadata.txtRecordData))
            service.delegate = self
            let generationID = UUID()
            let timeoutWorkItem = DispatchWorkItem { [weak self, weak service] in
                guard let self, let service else { return }
                self.failCurrentService(
                    service,
                    generationID: generationID,
                    message: "Local discovery publication timed out."
                )
            }
            let handler = lock.withLock {
                self.service = service
                serviceGenerationID = generationID
                storedAdvertisementStatus = .publishing
                publicationTimeoutWorkItem = timeoutWorkItem
                return statusChangeHandler
            }
            return (service, generationID, timeoutWorkItem, handler)
        }
        preparation.3?(.publishing)
        lifecycleLock.withLock {
            let isCurrent = lock.withLock {
                self.service === preparation.0
                    && serviceGenerationID == preparation.1
                    && storedAdvertisementStatus == .publishing
            }
            guard isCurrent else { return }
            DispatchQueue.main.asyncAfter(
                deadline: .now() + publicationTimeout,
                execute: preparation.2
            )
            publishService(preparation.0)
        }
    }

    public func stop() {
        stop(notify: true)
    }

    public func netServiceDidPublish(_ sender: NetService) {
        let handler: (@Sendable (RuntimeAdvertisementStatus) -> Void)? =
            lifecycleLock.withLock {
                lock.withLock {
                    guard service === sender else { return nil }
                    publicationTimeoutWorkItem?.cancel()
                    publicationTimeoutWorkItem = nil
                    guard storedAdvertisementStatus != .published else {
                        return nil
                    }
                    storedAdvertisementStatus = .published
                    return statusChangeHandler
                }
            }
        handler?(.published)
    }

    public func netService(
        _ sender: NetService,
        didNotPublish errorDict: [String: NSNumber]
    ) {
        let code = errorDict[NetService.errorCode]?.intValue
        let message = code.map {
            "Local discovery publication failed (code \($0))."
        } ?? "Local discovery publication failed."
        failCurrentService(sender, generationID: nil, message: message)
    }

    public func netServiceDidStop(_ sender: NetService) {
        let handler: (@Sendable (RuntimeAdvertisementStatus) -> Void)? =
            lifecycleLock.withLock {
                lock.withLock {
                    guard service === sender else { return nil }
                    service = nil
                    serviceGenerationID = nil
                    publicationTimeoutWorkItem?.cancel()
                    publicationTimeoutWorkItem = nil
                    guard storedAdvertisementStatus != .stopped else {
                        return nil
                    }
                    storedAdvertisementStatus = .stopped
                    return statusChangeHandler
                }
            }
        handler?(.stopped)
    }

    private func failCurrentService(
        _ failedService: NetService,
        generationID: UUID?,
        message: String
    ) {
        let transition: (
            matched: Bool,
            handler: (@Sendable (RuntimeAdvertisementStatus) -> Void)?
        ) =
            lifecycleLock.withLock {
                let transition: (
                    matched: Bool,
                    handler: (@Sendable (RuntimeAdvertisementStatus) -> Void)?
                ) =
                    lock.withLock {
                        guard service === failedService else {
                            return (false, nil)
                        }
                        if let generationID, serviceGenerationID != generationID {
                            return (false, nil)
                        }
                        guard storedAdvertisementStatus == .publishing else {
                            return (false, nil)
                        }
                        service = nil
                        serviceGenerationID = nil
                        publicationTimeoutWorkItem?.cancel()
                        publicationTimeoutWorkItem = nil
                        storedAdvertisementStatus = .failed(message)
                        return (true, statusChangeHandler)
                    }
                guard transition.matched else { return transition }
                failedService.delegate = nil
                stopService(failedService)
                return transition
            }
        guard transition.matched else { return }
        transition.handler?(.failed(message))
    }

    private func stop(notify: Bool) {
        let stopped = lifecycleLock.withLock {
            let stopped = lock.withLock {
                let stoppedService = service
                service = nil
                serviceGenerationID = nil
                publicationTimeoutWorkItem?.cancel()
                publicationTimeoutWorkItem = nil
                let shouldNotify = storedAdvertisementStatus != .stopped
                storedAdvertisementStatus = .stopped
                return (stoppedService, shouldNotify ? statusChangeHandler : nil)
            }
            if let service = stopped.0 {
                service.delegate = nil
                stopService(service)
            }
            return stopped
        }
        if notify {
            stopped.1?(.stopped)
        }
    }
}
