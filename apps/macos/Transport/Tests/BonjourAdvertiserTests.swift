@testable import Transport
import Foundation
import XCTest

final class BonjourAdvertiserTests: XCTestCase {
    func testPublicationReportsReadinessAndIgnoresSupersededServiceCallbacks() {
        let services = NetServiceRecorder()
        let stops = LockedInt()
        let statuses = AdvertisementStatusRecorder()
        let advertiser = makeAdvertiser(
            services: services,
            stops: stops
        )
        advertiser.onAdvertisementStatusChange = { statuses.append($0) }

        advertiser.start(
            port: 43_170,
            metadata: RuntimeAdvertisementMetadata(version: "first")
        )
        let first = services.service(at: 0)

        XCTAssertEqual(advertiser.advertisementStatus, .publishing)
        XCTAssertEqual(statuses.values, [.publishing])
        XCTAssertEqual(first.port, 43_170)

        advertiser.netServiceDidPublish(first)

        XCTAssertEqual(advertiser.advertisementStatus, .published)
        XCTAssertEqual(statuses.values, [.publishing, .published])

        advertiser.start(
            port: 43_171,
            metadata: RuntimeAdvertisementMetadata(version: "second")
        )
        let second = services.service(at: 1)
        XCTAssertFalse(first === second)
        XCTAssertEqual(stops.value, 1)
        advertiser.netService(
            first,
            didNotPublish: [NetService.errorCode: NSNumber(value: -72_001)]
        )

        XCTAssertEqual(advertiser.advertisementStatus, .publishing)
        XCTAssertEqual(stops.value, 1)
        XCTAssertEqual(
            statuses.values,
            [.publishing, .published, .publishing]
        )

        advertiser.netServiceDidPublish(second)

        XCTAssertEqual(advertiser.advertisementStatus, .published)
        XCTAssertEqual(
            statuses.values,
            [.publishing, .published, .publishing, .published]
        )
    }

    func testPublicationFailureStopsServiceAndReportsStableFailure() {
        let services = NetServiceRecorder()
        let stops = LockedInt()
        let statuses = AdvertisementStatusRecorder()
        let advertiser = makeAdvertiser(
            services: services,
            stops: stops
        )
        advertiser.onAdvertisementStatusChange = { statuses.append($0) }
        advertiser.start(port: 43_170)
        let service = services.service(at: 0)

        advertiser.netService(
            service,
            didNotPublish: [NetService.errorCode: NSNumber(value: -72_001)]
        )

        let failure = RuntimeAdvertisementStatus.failed(
            "Local discovery publication failed (code -72001)."
        )
        XCTAssertEqual(advertiser.advertisementStatus, failure)
        XCTAssertEqual(statuses.values, [.publishing, failure])
        XCTAssertEqual(stops.value, 1)

        advertiser.netServiceDidStop(service)
        XCTAssertEqual(advertiser.advertisementStatus, failure)
        XCTAssertEqual(statuses.values, [.publishing, failure])
    }

    func testPublicationTimeoutFailsInsteadOfRemainingPublishing() {
        let services = NetServiceRecorder()
        let stops = LockedInt()
        let statuses = AdvertisementStatusRecorder()
        let timedOut = expectation(description: "publication timed out")
        let advertiser = makeAdvertiser(
            publicationTimeout: 0.01,
            services: services,
            stops: stops
        )
        advertiser.onAdvertisementStatusChange = {
            statuses.append($0)
            if $0 == .failed("Local discovery publication timed out.") {
                timedOut.fulfill()
            }
        }

        advertiser.start(port: 43_170)

        wait(for: [timedOut], timeout: 1)
        XCTAssertEqual(
            advertiser.advertisementStatus,
            .failed("Local discovery publication timed out.")
        )
        XCTAssertEqual(stops.value, 1)
    }

    func testPublishedStatusRemainsStablePastPublicationTimeout() {
        let services = NetServiceRecorder()
        let stops = LockedInt()
        let statuses = AdvertisementStatusRecorder()
        let remainedPublished = expectation(
            description: "published status remained stable"
        )
        let advertiser = makeAdvertiser(
            publicationTimeout: 0.01,
            services: services,
            stops: stops
        )
        advertiser.onAdvertisementStatusChange = { statuses.append($0) }
        advertiser.start(port: 43_170)
        advertiser.netServiceDidPublish(services.service(at: 0))

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.03) {
            remainedPublished.fulfill()
        }
        wait(for: [remainedPublished], timeout: 1)

        XCTAssertEqual(advertiser.advertisementStatus, .published)
        XCTAssertEqual(statuses.values, [.publishing, .published])
        XCTAssertEqual(stops.value, 0)
    }

    func testReentrantStartPublishesOnlyReplacementService() {
        let services = NetServiceRecorder()
        let publishedServices = NetServiceRecorder()
        let stops = LockedInt()
        let statuses = AdvertisementStatusRecorder()
        let advertiserBox = BonjourAdvertiserBox()
        let supersedeClaim = LockedInt()
        let advertiser = makeAdvertiser(
            services: services,
            publishedServices: publishedServices,
            stops: stops
        )
        advertiserBox.advertiser = advertiser
        advertiser.onAdvertisementStatusChange = { status in
            statuses.append(status)
            guard status == .publishing, supersedeClaim.claimFirst() else {
                return
            }
            advertiserBox.advertiser?.start(port: 43_171)
        }

        advertiser.start(port: 43_170)

        XCTAssertEqual(services.count, 2)
        XCTAssertEqual(publishedServices.count, 1)
        XCTAssertTrue(
            publishedServices.service(at: 0) === services.service(at: 1)
        )
        XCTAssertEqual(statuses.values, [.publishing, .publishing])
        XCTAssertEqual(advertiser.advertisementStatus, .publishing)
        XCTAssertEqual(stops.value, 1)
    }

    func testStatusHandlerCanStopFromAnotherQueueWithoutLifecycleLockInversion() {
        let services = NetServiceRecorder()
        let stops = LockedInt()
        let crossQueueStopSucceeded = LockedInt()
        let advertiserBox = BonjourAdvertiserBox()
        let advertiser = makeAdvertiser(
            services: services,
            stops: stops
        )
        advertiserBox.advertiser = advertiser
        advertiser.onAdvertisementStatusChange = { status in
            guard status == .published else { return }
            let stopped = DispatchSemaphore(value: 0)
            DispatchQueue.global().async {
                advertiserBox.advertiser?.stop()
                stopped.signal()
            }
            if stopped.wait(timeout: .now() + 0.2) == .success {
                crossQueueStopSucceeded.increment()
            }
        }
        advertiser.start(port: 43_170)

        advertiser.netServiceDidPublish(services.service(at: 0))

        XCTAssertEqual(crossQueueStopSucceeded.value, 1)
        XCTAssertEqual(advertiser.advertisementStatus, .stopped)
        XCTAssertEqual(stops.value, 1)
    }

    func testUnexpectedPublishedServiceStopIsReported() {
        let services = NetServiceRecorder()
        let stops = LockedInt()
        let statuses = AdvertisementStatusRecorder()
        let advertiser = makeAdvertiser(
            services: services,
            stops: stops
        )
        advertiser.onAdvertisementStatusChange = { statuses.append($0) }
        advertiser.start(port: 43_170)
        let service = services.service(at: 0)
        advertiser.netServiceDidPublish(service)

        advertiser.netServiceDidStop(service)

        XCTAssertEqual(advertiser.advertisementStatus, .stopped)
        XCTAssertEqual(
            statuses.values,
            [.publishing, .published, .stopped]
        )
    }

    private func makeAdvertiser(
        publicationTimeout: TimeInterval = 60,
        services: NetServiceRecorder,
        publishedServices: NetServiceRecorder? = nil,
        stops: LockedInt
    ) -> BonjourAdvertiser {
        BonjourAdvertiser(
            publicationTimeout: publicationTimeout,
            serviceFactory: { domain, type, name, port in
                let service = NetService(
                    domain: domain,
                    type: type,
                    name: name,
                    port: port
                )
                services.append(service)
                return service
            },
            publishService: { service in publishedServices?.append(service) },
            stopService: { _ in stops.increment() }
        )
    }
}

private final class BonjourAdvertiserBox: @unchecked Sendable {
    var advertiser: BonjourAdvertiser?
}

private final class NetServiceRecorder {
    private let lock = NSLock()
    private var services: [NetService] = []

    func append(_ service: NetService) {
        lock.withLock {
            services.append(service)
        }
    }

    func service(at index: Int) -> NetService {
        lock.withLock { services[index] }
    }

    var count: Int {
        lock.withLock { services.count }
    }
}

private final class AdvertisementStatusRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var statuses: [RuntimeAdvertisementStatus] = []

    var values: [RuntimeAdvertisementStatus] {
        lock.withLock { statuses }
    }

    func append(_ status: RuntimeAdvertisementStatus) {
        lock.withLock {
            statuses.append(status)
        }
    }
}

private final class LockedInt: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValue = 0

    var value: Int {
        lock.withLock { storedValue }
    }

    func increment() {
        lock.withLock {
            storedValue += 1
        }
    }

    func claimFirst() -> Bool {
        lock.withLock {
            guard storedValue == 0 else { return false }
            storedValue = 1
            return true
        }
    }
}
