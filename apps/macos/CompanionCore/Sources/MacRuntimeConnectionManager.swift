import Foundation
import Transport

protocol MacRuntimeBootstrapRetiringTransport: RelayPeerTransport {
    func retireAfterCurrentConnection()
}

extension RelayPeerClient: MacRuntimeBootstrapRetiringTransport {}

public enum MacRuntimePrivateOverlayStatus: Equatable, Sendable {
    case connecting
    case ready
    case failed(String)
    case stopped
}

public protocol MacRuntimePrivateOverlayTransport: RuntimeDisconnectReporting, Sendable {
    func start(
        clientKeyFingerprint: String,
        onStatusChange: (@Sendable (MacRuntimePrivateOverlayStatus) -> Void)?,
        onMessage: @escaping LocalPeerMessageHandler
    )

    func stop()
}

private final class MacRuntimeCallbackLease: @unchecked Sendable {
    private let lock = NSRecursiveLock()
    private var isActive = true

    func invalidate() {
        lock.lock()
        isActive = false
        lock.unlock()
    }

    func performIfActive(_ operation: () -> Void) {
        lock.lock()
        defer { lock.unlock() }
        guard isActive else { return }
        operation()
    }
}

private final class MacRuntimeStopLease: @unchecked Sendable {
    private let lock = NSLock()
    private var isTerminal = false

    func markTerminal() {
        lock.lock()
        isTerminal = true
        lock.unlock()
    }

    func claimStop() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard !isTerminal else { return false }
        isTerminal = true
        return true
    }
}

/// Owns the local listener, Bonjour advertiser, bootstrap relay transport, and the transports
/// keyed to paired-client fingerprints.
///
/// `startLocal` and `refreshLocalAdvertisement` manage local discovery. `startBootstrap`,
/// `stopBootstrap`, and `retireBootstrapAfterCurrentConnection` manage the injected bootstrap
/// transport. `startPair` and `stopPair` manage one factory-created transport per fingerprint,
/// while `stopAll` releases every currently active resource.
@MainActor
public final class MacRuntimeConnectionManager {
    public typealias StatusHandler = @MainActor @Sendable (RelayPeerStatus) -> Void
    public typealias PrivateOverlayStatusHandler = @MainActor @Sendable (
        MacRuntimePrivateOverlayStatus
    ) -> Void

    private enum BootstrapState {
        case inactive
        case active(generationID: UUID)
        case retiring
    }

    private struct PairConnection {
        let generationID: UUID
        let transport: any RelayPeerTransport
        let messageLease: MacRuntimeCallbackLease
        let stopLease: MacRuntimeStopLease
    }

    private struct PairPrivateOverlayConnection {
        let generationID: UUID
        let transport: any MacRuntimePrivateOverlayTransport
        let messageLease: MacRuntimeCallbackLease
        let stopLease: MacRuntimeStopLease
    }

    private let localTransport: any RuntimeTransport
    private let advertiser: any RuntimeAdvertiser
    private let bootstrapTransport: any RelayPeerTransport
    private let pairTransportFactory: @Sendable () -> any RelayPeerTransport
    private let pairPrivateOverlayTransportFactory: (
        @Sendable () -> any MacRuntimePrivateOverlayTransport
    )?
    private let onDisconnect: @Sendable (UUID) -> Void
    let productionRawSessionAttachments =
        MacRuntimeProductionRawSessionAttachments()

    private var activeLocalPort: UInt16?
    private var localMessageLease: MacRuntimeCallbackLease?
    private var isAdvertisingLocalPort = false
    private var bootstrapState = BootstrapState.inactive
    private var bootstrapMessageLease: MacRuntimeCallbackLease?
    private var bootstrapStopLease: MacRuntimeStopLease?
    private var pairConnections: [String: PairConnection] = [:]
    private var pairPrivateOverlayConnections: [String: PairPrivateOverlayConnection] = [:]

    public init(
        localTransport: any RuntimeTransport = LocalPeerServer(),
        advertiser: any RuntimeAdvertiser = BonjourAdvertiser(),
        bootstrapTransport: any RelayPeerTransport,
        pairTransportFactory: @escaping @Sendable () -> any RelayPeerTransport,
        pairPrivateOverlayTransportFactory: (
            @Sendable () -> any MacRuntimePrivateOverlayTransport
        )? = nil,
        onDisconnect: @escaping @Sendable (UUID) -> Void
    ) {
        self.localTransport = localTransport
        self.advertiser = advertiser
        self.bootstrapTransport = bootstrapTransport
        self.pairTransportFactory = pairTransportFactory
        self.pairPrivateOverlayTransportFactory = pairPrivateOverlayTransportFactory
        self.onDisconnect = onDisconnect
        forwardDisconnects(from: localTransport)
        forwardDisconnects(from: bootstrapTransport)
    }

    @discardableResult
    public func startLocal(
        port: UInt16,
        metadata: RuntimeAdvertisementMetadata,
        onMessage: @escaping LocalPeerMessageHandler
    ) -> PeerServerStatus {
        let stoppedAdvertisement = stopLocalOwnership()

        let messageLease = MacRuntimeCallbackLease()
        localMessageLease = messageLease
        activeLocalPort = port
        localTransport.start(port: port) { envelope, sink in
            messageLease.performIfActive {
                onMessage(envelope, sink)
            }
        }
        let status = localTransport.status
        guard status == .listening(port: port) else {
            let stoppedFailedAdvertisement = stopLocalOwnership()
            if !stoppedAdvertisement && !stoppedFailedAdvertisement {
                advertiser.stop()
            }
            return status
        }

        advertiser.start(port: Int32(port), metadata: metadata)
        isAdvertisingLocalPort = true
        return status
    }

    @discardableResult
    public func refreshLocalAdvertisement(
        metadata: RuntimeAdvertisementMetadata
    ) -> PeerServerStatus {
        let status = localTransport.status
        let hasLocalOwnership = activeLocalPort != nil || localMessageLease != nil || isAdvertisingLocalPort
        guard
            let port = activeLocalPort,
            status == .listening(port: port)
        else {
            if hasLocalOwnership {
                stopLocalOwnership()
            }
            return status
        }

        if isAdvertisingLocalPort {
            isAdvertisingLocalPort = false
            advertiser.stop()
        }
        advertiser.start(port: Int32(port), metadata: metadata)
        isAdvertisingLocalPort = true
        return status
    }

    public func startBootstrap(
        configuration: RelayPeerConfiguration,
        onStatusChange: StatusHandler? = nil,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        switch bootstrapState {
        case .inactive:
            break
        case .active, .retiring:
            bootstrapState = .inactive
            bootstrapMessageLease?.invalidate()
            bootstrapMessageLease = nil
            if bootstrapStopLease?.claimStop() == true {
                bootstrapTransport.stop()
            }
            bootstrapStopLease = nil
        }

        let generationID = UUID()
        let messageLease = MacRuntimeCallbackLease()
        let stopLease = MacRuntimeStopLease()
        bootstrapState = .active(generationID: generationID)
        bootstrapMessageLease = messageLease
        bootstrapStopLease = stopLease
        bootstrapTransport.start(
            configuration: configuration,
            onStatusChange: { [weak self] status in
                if status == .stopped {
                    messageLease.invalidate()
                    stopLease.markTerminal()
                }
                Task { @MainActor in
                    guard
                        let self,
                        case .active(let currentGenerationID) = self.bootstrapState,
                        currentGenerationID == generationID
                    else {
                        return
                    }
                    if status == .stopped {
                        self.bootstrapState = .inactive
                        self.bootstrapMessageLease = nil
                        self.bootstrapStopLease = nil
                    }
                    onStatusChange?(status)
                }
            },
            onMessage: { envelope, sink in
                messageLease.performIfActive {
                    onMessage(envelope, sink)
                }
            }
        )
    }

    public func stopBootstrap() {
        if case .inactive = bootstrapState { return }
        bootstrapState = .inactive
        bootstrapMessageLease?.invalidate()
        bootstrapMessageLease = nil
        let shouldStop = bootstrapStopLease?.claimStop() ?? true
        bootstrapStopLease = nil
        if shouldStop {
            bootstrapTransport.stop()
        }
    }

    public func retireBootstrapAfterCurrentConnection() {
        switch bootstrapState {
        case .retiring:
            return
        case .active:
            bootstrapState = .retiring
            bootstrapMessageLease?.invalidate()
            bootstrapMessageLease = nil
            if let retiringTransport = bootstrapTransport as? any MacRuntimeBootstrapRetiringTransport {
                retiringTransport.retireAfterCurrentConnection()
            } else {
                bootstrapState = .inactive
                let shouldStop = bootstrapStopLease?.claimStop() ?? true
                bootstrapStopLease = nil
                if shouldStop {
                    bootstrapTransport.stop()
                }
            }
        case .inactive:
            if let retiringTransport = bootstrapTransport as? any MacRuntimeBootstrapRetiringTransport {
                retiringTransport.retireAfterCurrentConnection()
            } else {
                bootstrapTransport.stop()
            }
        }
    }

    /// Starts the existing development/legacy relay path without production admission.
    /// The exact-bound production coordinator remains unavailable until G1a-C.
    public func startPair(
        fingerprint: String,
        configuration: RelayPeerConfiguration,
        onStatusChange: StatusHandler? = nil,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        if let previous = pairConnections.removeValue(forKey: fingerprint) {
            previous.messageLease.invalidate()
            if previous.stopLease.claimStop() {
                previous.transport.stop()
            }
        }

        let transport = pairTransportFactory()
        forwardDisconnects(from: transport)
        let generationID = UUID()
        let messageLease = MacRuntimeCallbackLease()
        let stopLease = MacRuntimeStopLease()
        pairConnections[fingerprint] = PairConnection(
            generationID: generationID,
            transport: transport,
            messageLease: messageLease,
            stopLease: stopLease
        )

        transport.start(
            configuration: configuration,
            onStatusChange: { [weak self, weak transport] status in
                if status == .stopped {
                    messageLease.invalidate()
                    stopLease.markTerminal()
                }
                Task { @MainActor in
                    guard
                        let self,
                        let transport,
                        let current = self.pairConnections[fingerprint],
                        current.generationID == generationID,
                        current.transport === transport
                    else {
                        return
                    }
                    if status == .stopped {
                        self.pairConnections.removeValue(forKey: fingerprint)
                    }
                    onStatusChange?(status)
                }
            },
            onMessage: { envelope, sink in
                messageLease.performIfActive {
                    onMessage(envelope, sink)
                }
            }
        )
    }

    #if DEBUG
    func startAdmittedProductionPairRelay(
        _ admittedStart: MacRuntimeAdmittedProductionPairRelayStart,
        onStatusChange: StatusHandler? = nil,
        onMessage: @escaping LocalPeerMessageHandler
    ) {
        startPair(
            fingerprint: admittedStart.clientKeyFingerprint,
            configuration: admittedStart.configuration,
            onStatusChange: onStatusChange,
            onMessage: onMessage
        )
    }
    #endif

    /// Starts the existing development/legacy private-overlay path without production admission.
    /// The exact-bound production coordinator remains unavailable until G1a-C.
    @discardableResult
    public func startPairPrivateOverlay(
        fingerprint: String,
        onStatusChange: PrivateOverlayStatusHandler? = nil,
        onMessage: @escaping LocalPeerMessageHandler
    ) -> Bool {
        guard let pairPrivateOverlayTransportFactory else { return false }

        if let previous = pairPrivateOverlayConnections.removeValue(forKey: fingerprint) {
            previous.messageLease.invalidate()
            if previous.stopLease.claimStop() {
                previous.transport.stop()
            }
        }

        let transport = pairPrivateOverlayTransportFactory()
        transport.onDisconnect = onDisconnect
        let generationID = UUID()
        let messageLease = MacRuntimeCallbackLease()
        let stopLease = MacRuntimeStopLease()
        pairPrivateOverlayConnections[fingerprint] = PairPrivateOverlayConnection(
            generationID: generationID,
            transport: transport,
            messageLease: messageLease,
            stopLease: stopLease
        )
        transport.start(
            clientKeyFingerprint: fingerprint,
            onStatusChange: { [weak self, weak transport] status in
                if status == .stopped {
                    messageLease.invalidate()
                    stopLease.markTerminal()
                }
                Task { @MainActor in
                    guard
                        let self,
                        let transport,
                        let current = self.pairPrivateOverlayConnections[fingerprint],
                        current.generationID == generationID,
                        current.transport === transport
                    else {
                        return
                    }
                    if status == .stopped {
                        self.pairPrivateOverlayConnections.removeValue(forKey: fingerprint)
                    }
                    onStatusChange?(status)
                }
            },
            onMessage: { envelope, sink in
                messageLease.performIfActive {
                    onMessage(envelope, sink)
                }
            }
        )
        return true
    }

    public func stopPair(fingerprint: String) {
        if let connection = pairPrivateOverlayConnections.removeValue(forKey: fingerprint) {
            connection.messageLease.invalidate()
            if connection.stopLease.claimStop() {
                connection.transport.stop()
            }
        }
        if let connection = pairConnections.removeValue(forKey: fingerprint) {
            connection.messageLease.invalidate()
            if connection.stopLease.claimStop() {
                connection.transport.stop()
            }
        }
    }

    public func stopAll() {
        productionRawSessionAttachments.closeAll()
        stopLocalOwnership()

        var transports: [any RelayPeerTransport] = []
        switch bootstrapState {
        case .inactive:
            break
        case .active, .retiring:
            bootstrapMessageLease?.invalidate()
            if bootstrapStopLease?.claimStop() == true {
                transports.append(bootstrapTransport)
            }
        }
        let currentPairConnections = Array(pairConnections.values)
        currentPairConnections.forEach { $0.messageLease.invalidate() }
        transports.append(contentsOf: currentPairConnections.compactMap {
            $0.stopLease.claimStop() ? $0.transport : nil
        })
        let currentPairPrivateOverlayConnections = Array(pairPrivateOverlayConnections.values)
        currentPairPrivateOverlayConnections.forEach { $0.messageLease.invalidate() }

        bootstrapState = .inactive
        bootstrapMessageLease = nil
        bootstrapStopLease = nil
        pairConnections.removeAll()
        pairPrivateOverlayConnections.removeAll()

        var stoppedTransportIDs = Set<ObjectIdentifier>()
        for transport in transports where stoppedTransportIDs.insert(ObjectIdentifier(transport)).inserted {
            transport.stop()
        }
        for connection in currentPairPrivateOverlayConnections where connection.stopLease.claimStop() &&
            stoppedTransportIDs.insert(ObjectIdentifier(connection.transport)).inserted {
            connection.transport.stop()
        }
    }

    private func forwardDisconnects(from transport: any RelayPeerTransport) {
        guard let disconnectReporting = transport as? any RuntimeDisconnectReporting else { return }
        disconnectReporting.onDisconnect = onDisconnect
    }

    private func forwardDisconnects(from transport: any RuntimeTransport) {
        guard let disconnectReporting = transport as? any RuntimeDisconnectReporting else { return }
        disconnectReporting.onDisconnect = onDisconnect
    }

    @discardableResult
    private func stopLocalOwnership() -> Bool {
        let stoppedAdvertisement = isAdvertisingLocalPort
        localMessageLease?.invalidate()
        localMessageLease = nil
        if isAdvertisingLocalPort {
            isAdvertisingLocalPort = false
            advertiser.stop()
        }
        guard activeLocalPort != nil else { return stoppedAdvertisement }
        activeLocalPort = nil
        localTransport.stop()
        return stoppedAdvertisement
    }
}
