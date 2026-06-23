import Foundation

public final class BonjourAdvertiser: NSObject, NetServiceDelegate, RuntimeAdvertiser {
    private var service: NetService?
    public private(set) var serviceName = "AetherLink"

    public func start(port: Int32) {
        stop()
        let service = NetService(
            domain: "local.",
            type: "_aetherlink._tcp.",
            name: serviceName,
            port: port
        )
        service.delegate = self
        service.publish()
        self.service = service
    }

    public func stop() {
        service?.stop()
        service = nil
    }
}
