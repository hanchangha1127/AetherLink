import BridgeProtocol
import Foundation

public protocol RuntimeTransport {
    var status: PeerServerStatus { get }

    func start(port: UInt16, onMessage: @escaping LocalPeerMessageHandler)
    func stop()
}

public protocol RuntimeAdvertiser {
    func start(port: Int32)
    func stop()
}

