import Foundation
import XCTest
@testable import OllamaBackend

final class OllamaBackendHealthTimeoutTests: XCTestCase {
    override func tearDown() {
        OllamaHealthTimeoutURLProtocol.handler = nil
        super.tearDown()
    }

    func testHealthCheckUsesFiveSecondsWhileCatalogRetainsSixtySeconds() async throws {
        let recorder = OllamaHealthRequestRecorder()
        OllamaHealthTimeoutURLProtocol.handler = { request in
            recorder.record(request)
            let body: Data
            switch request.url?.path {
            case "/api/tags", "/api/ps":
                body = Data(#"{"models":[]}"#.utf8)
            default:
                throw URLError(.unsupportedURL)
            }
            return (
                HTTPURLResponse(
                    url: try XCTUnwrap(request.url),
                    statusCode: 200,
                    httpVersion: nil,
                    headerFields: ["Content-Type": "application/json"]
                )!,
                body
            )
        }

        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [OllamaHealthTimeoutURLProtocol.self]
        let backend = OllamaBackend(
            session: URLSession(configuration: configuration)
        )

        let status = await backend.healthCheck()
        XCTAssertEqual(status, .available)
        let models = try await backend.listModels()
        XCTAssertEqual(models, [])
        XCTAssertEqual(
            recorder.snapshot(),
            [
                .init(path: "/api/tags", timeout: 5),
                .init(path: "/api/tags", timeout: 60),
                .init(path: "/api/ps", timeout: 60),
            ]
        )
    }
}

private struct OllamaHealthRequestObservation: Equatable {
    let path: String
    let timeout: TimeInterval
}

private final class OllamaHealthRequestRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var observations: [OllamaHealthRequestObservation] = []

    func record(_ request: URLRequest) {
        lock.withLock {
            observations.append(.init(
                path: request.url?.path ?? "",
                timeout: request.timeoutInterval
            ))
        }
    }

    func snapshot() -> [OllamaHealthRequestObservation] {
        lock.withLock { observations }
    }
}

private final class OllamaHealthTimeoutURLProtocol: URLProtocol {
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
