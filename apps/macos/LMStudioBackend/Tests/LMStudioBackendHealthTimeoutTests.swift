import Foundation
import XCTest
@testable import LMStudioBackend

final class LMStudioBackendHealthTimeoutTests: XCTestCase {
    override func tearDown() {
        LMStudioHealthTimeoutURLProtocol.handler = nil
        super.tearDown()
    }

    func testHealthCheckUsesFiveSecondsWhileCatalogRetainsSixtySeconds() async throws {
        let recorder = LMStudioHealthRequestRecorder()
        LMStudioHealthTimeoutURLProtocol.handler = { request in
            recorder.record(request)
            guard request.url?.path == "/api/v1/models" else {
                throw URLError(.unsupportedURL)
            }
            return (
                HTTPURLResponse(
                    url: try XCTUnwrap(request.url),
                    statusCode: 200,
                    httpVersion: nil,
                    headerFields: ["Content-Type": "application/json"]
                )!,
                Data(#"{"models":[]}"#.utf8)
            )
        }

        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [LMStudioHealthTimeoutURLProtocol.self]
        let backend = LMStudioBackend(
            session: URLSession(configuration: configuration)
        )

        let status = await backend.healthCheck()
        XCTAssertEqual(status, .available)
        let models = try await backend.listModels()
        XCTAssertEqual(models, [])
        XCTAssertEqual(
            recorder.snapshot(),
            [
                .init(path: "/api/v1/models", timeout: 5),
                .init(path: "/api/v1/models", timeout: 60),
            ]
        )

        let fallbackClock = LMStudioHealthClock(uptime: 100)
        let fallbackRecorder = LMStudioHealthRequestRecorder()
        LMStudioHealthTimeoutURLProtocol.handler = { request in
            fallbackRecorder.record(request)
            switch request.url?.path {
            case "/api/v1/models":
                fallbackClock.advance(by: 3)
                return (
                    try Self.response(for: request, statusCode: 404),
                    Data("missing".utf8)
                )
            case "/v1/models":
                return (
                    try Self.response(for: request, statusCode: 200),
                    Data(#"{"data":[]}"#.utf8)
                )
            default:
                throw URLError(.unsupportedURL)
            }
        }
        let fallbackBackend = LMStudioBackend(
            baseURL: LMStudioBackend.defaultBaseURL,
            session: Self.session(),
            unloadPollAttempts: 1,
            healthResponseTimeout: 5,
            healthUptime: { fallbackClock.now() }
        )

        let fallbackStatus = await fallbackBackend.healthCheck()
        XCTAssertEqual(fallbackStatus, .available)
        XCTAssertEqual(
            fallbackRecorder.snapshot(),
            [
                .init(path: "/api/v1/models", timeout: 5),
                .init(path: "/v1/models", timeout: 2),
            ]
        )

        let expiredClock = LMStudioHealthClock(uptime: 200)
        let expiredRecorder = LMStudioHealthRequestRecorder()
        LMStudioHealthTimeoutURLProtocol.handler = { request in
            expiredRecorder.record(request)
            guard request.url?.path == "/api/v1/models" else {
                XCTFail("Expired health deadline must not start fallback")
                throw URLError(.cancelled)
            }
            expiredClock.advance(by: 5)
            return (
                try Self.response(for: request, statusCode: 404),
                Data("missing".utf8)
            )
        }
        let expiredBackend = LMStudioBackend(
            baseURL: LMStudioBackend.defaultBaseURL,
            session: Self.session(),
            unloadPollAttempts: 1,
            healthResponseTimeout: 5,
            healthUptime: { expiredClock.now() }
        )

        let expiredStatus = await expiredBackend.healthCheck()
        guard case .unavailable(let error) = expiredStatus else {
            return XCTFail("Expected an unavailable expired health result")
        }
        XCTAssertTrue(error.retryable)
        XCTAssertEqual(
            expiredRecorder.snapshot(),
            [.init(path: "/api/v1/models", timeout: 5)]
        )
    }

    private static func session() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [LMStudioHealthTimeoutURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    private static func response(
        for request: URLRequest,
        statusCode: Int
    ) throws -> HTTPURLResponse {
        HTTPURLResponse(
            url: try XCTUnwrap(request.url),
            statusCode: statusCode,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
    }
}

private struct LMStudioHealthRequestObservation: Equatable {
    let path: String
    let timeout: TimeInterval
}

private final class LMStudioHealthRequestRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var observations: [LMStudioHealthRequestObservation] = []

    func record(_ request: URLRequest) {
        lock.withLock {
            observations.append(.init(
                path: request.url?.path ?? "",
                timeout: request.timeoutInterval
            ))
        }
    }

    func snapshot() -> [LMStudioHealthRequestObservation] {
        lock.withLock { observations }
    }
}

private final class LMStudioHealthClock: @unchecked Sendable {
    private let lock = NSLock()
    private var uptime: TimeInterval

    init(uptime: TimeInterval) {
        self.uptime = uptime
    }

    func now() -> TimeInterval {
        lock.withLock { uptime }
    }

    func advance(by interval: TimeInterval) {
        lock.withLock {
            uptime += interval
        }
    }
}

private final class LMStudioHealthTimeoutURLProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        do {
            let handler = try XCTUnwrap(Self.handler)
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
