import BridgeProtocol
@testable import CompanionCore
import CryptoKit
import Darwin
import Foundation
import Transport
import XCTest

final class PairedRelayAllocationClientTests: XCTestCase {
    func testClaimSendsExactWireAndVerifiesBothProofs() async throws {
        try await assertSuccessfulRenewal(operation: .claim)
    }

    func testRenewSendsExactWireAndPreservesNextTicketGeneration() async throws {
        try await assertSuccessfulRenewal(operation: .renew)
    }

    func testRejectsWrongChallengePrefixWithoutCallingProvider() async throws {
        let fixture = try PairedRenewalFixture(operation: .claim)
        let challengeLine = try fixture.challengeLine(
            prefix: "AETHERLINK_RELAY allocation_challenge "
        )
        let server = try PairedRelayTestServer(responseLines: [challengeLine])
        defer { server.stop() }
        let providerCalls = LockedCounter()
        let context = try fixture.authorizationContext { challenge in
            providerCalls.increment()
            return try PairedRelayAllocationClientProof.sign(
                challenge: challenge,
                using: fixture.clientKey
            )
        }

        await XCTAssertThrowsErrorAsync(try await fixture.allocator.renewPairedRelayRoute(
            currentRouteToken: fixture.routeToken,
            currentConfiguration: fixture.configuration(host: "127.0.0.1", port: server.port),
            currentLease: fixture.currentLease,
            runtimeIdentity: fixture.runtimeIdentity,
            authorizationSigner: fixture.runtimeSigner,
            authorizationContext: context,
            timeout: 1
        )) {
            XCTAssertEqual($0 as? RelayServiceRouteAllocationError, .invalidChallenge)
        }
        XCTAssertEqual(providerCalls.value, 0)
    }

    func testRejectsUnknownChallengeFieldAndStaleChallenge() async throws {
        for mutation in [ChallengeMutation.unknownField, .stale] {
            let fixture = try PairedRenewalFixture(operation: .claim)
            let server = try PairedRelayTestServer(responseLines: [
                try fixture.challengeLine(mutation: mutation)
            ])
            defer { server.stop() }
            let providerCalls = LockedCounter()
            let context = try fixture.authorizationContext { challenge in
                providerCalls.increment()
                return try PairedRelayAllocationClientProof.sign(
                    challenge: challenge,
                    using: fixture.clientKey
                )
            }

            await XCTAssertThrowsErrorAsync(try await fixture.allocator.renewPairedRelayRoute(
                currentRouteToken: fixture.routeToken,
                currentConfiguration: fixture.configuration(host: "127.0.0.1", port: server.port),
                currentLease: fixture.currentLease,
                runtimeIdentity: fixture.runtimeIdentity,
                authorizationSigner: fixture.runtimeSigner,
                authorizationContext: context,
                timeout: 1
            )) {
                XCTAssertEqual($0 as? RelayServiceRouteAllocationError, .invalidChallenge)
            }
            XCTAssertEqual(providerCalls.value, 0)
        }
    }

    func testRejectsWrongClientProofBeforeSendingProofLine() async throws {
        let fixture = try PairedRenewalFixture(operation: .claim)
        let server = try PairedRelayTestServer(responseLines: [try fixture.challengeLine()])
        defer { server.stop() }
        let wrongKey = P256.Signing.PrivateKey()
        let context = try fixture.authorizationContext { challenge in
            let signature = try wrongKey.signature(
                for: SHA256.hash(data: challenge.clientSignedMessageData())
            )
            return try PairedRelayAllocationClientProof(
                publicKeyBase64: wrongKey.publicKey.derRepresentation.base64EncodedString(),
                signatureBase64: signature.derRepresentation.base64EncodedString()
            )
        }

        await XCTAssertThrowsErrorAsync(try await fixture.allocator.renewPairedRelayRoute(
            currentRouteToken: fixture.routeToken,
            currentConfiguration: fixture.configuration(host: "127.0.0.1", port: server.port),
            currentLease: fixture.currentLease,
            runtimeIdentity: fixture.runtimeIdentity,
            authorizationSigner: fixture.runtimeSigner,
            authorizationContext: context,
            timeout: 1
        )) {
            XCTAssertEqual($0 as? RelayServiceRouteAllocationError, .clientAuthorizationRejected)
        }
        XCTAssertEqual(server.waitForRequests(count: 1).count, 1)
    }

    func testClientAuthorizationTimeoutClosesBoundedSocketTransaction() async throws {
        let fixture = try PairedRenewalFixture(operation: .claim)
        let server = try PairedRelayTestServer(responseLines: [try fixture.challengeLine()])
        defer { server.stop() }
        let context = try fixture.authorizationContext { challenge in
            try await Task.sleep(nanoseconds: 5_000_000_000)
            return try PairedRelayAllocationClientProof.sign(
                challenge: challenge,
                using: fixture.clientKey
            )
        }
        let startedAt = Date()

        await XCTAssertThrowsErrorAsync(try await fixture.allocator.renewPairedRelayRoute(
            currentRouteToken: fixture.routeToken,
            currentConfiguration: fixture.configuration(host: "127.0.0.1", port: server.port),
            currentLease: fixture.currentLease,
            runtimeIdentity: fixture.runtimeIdentity,
            authorizationSigner: fixture.runtimeSigner,
            authorizationContext: context,
            timeout: 0.05
        )) {
            XCTAssertEqual($0 as? RelayServiceRouteAllocationError, .clientAuthorizationTimedOut)
        }
        XCTAssertLessThan(Date().timeIntervalSince(startedAt), 1)
    }

    func testDisconnectAfterChallengeFailsWithoutAllocation() async throws {
        let fixture = try PairedRenewalFixture(operation: .renew)
        let server = try PairedRelayTestServer(responseLines: [try fixture.challengeLine()])
        defer { server.stop() }
        let context = try fixture.authorizationContext { challenge in
            try PairedRelayAllocationClientProof.sign(
                challenge: challenge,
                using: fixture.clientKey
            )
        }

        await XCTAssertThrowsErrorAsync(try await fixture.allocator.renewPairedRelayRoute(
            currentRouteToken: fixture.routeToken,
            currentConfiguration: fixture.configuration(host: "127.0.0.1", port: server.port),
            currentLease: fixture.currentLease,
            runtimeIdentity: fixture.runtimeIdentity,
            authorizationSigner: fixture.runtimeSigner,
            authorizationContext: context,
            timeout: 1
        )) {
            XCTAssertTrue(
                $0 as? RelayServiceRouteAllocationError == .writeFailed ||
                    $0 as? RelayServiceRouteAllocationError == .readFailed
            )
        }
    }

    func testSignerFailureStopsBeforeClientAuthorization() async throws {
        let fixture = try PairedRenewalFixture(operation: .claim)
        let server = try PairedRelayTestServer(responseLines: [try fixture.challengeLine()])
        defer { server.stop() }
        let providerCalls = LockedCounter()
        let context = try fixture.authorizationContext { challenge in
            providerCalls.increment()
            return try PairedRelayAllocationClientProof.sign(
                challenge: challenge,
                using: fixture.clientKey
            )
        }
        let signer = FailingPairedRuntimeSigner(base: fixture.runtimeSigner)

        await XCTAssertThrowsErrorAsync(try await fixture.allocator.renewPairedRelayRoute(
            currentRouteToken: fixture.routeToken,
            currentConfiguration: fixture.configuration(host: "127.0.0.1", port: server.port),
            currentLease: fixture.currentLease,
            runtimeIdentity: fixture.runtimeIdentity,
            authorizationSigner: signer,
            authorizationContext: context,
            timeout: 1
        )) {
            XCTAssertTrue($0 is PairedSignerTestError)
        }
        XCTAssertEqual(providerCalls.value, 0)
    }

    func testRejectsFinalAllocationMutationAfterSendingValidProofs() async throws {
        let fixture = try PairedRenewalFixture(operation: .renew)
        let server = try PairedRelayTestServer(responseLines: [
            try fixture.challengeLine(),
            fixture.allocationLine(relayNonce: "mutated-next-nonce"),
        ])
        defer { server.stop() }
        let context = try fixture.authorizationContext { challenge in
            try PairedRelayAllocationClientProof.sign(
                challenge: challenge,
                using: fixture.clientKey
            )
        }

        await XCTAssertThrowsErrorAsync(try await fixture.allocator.renewPairedRelayRoute(
            currentRouteToken: fixture.routeToken,
            currentConfiguration: fixture.configuration(host: "127.0.0.1", port: server.port),
            currentLease: fixture.currentLease,
            runtimeIdentity: fixture.runtimeIdentity,
            authorizationSigner: fixture.runtimeSigner,
            authorizationContext: context,
            timeout: 1
        )) {
            XCTAssertEqual($0 as? RelayServiceRouteAllocationError, .invalidResponse)
        }
        XCTAssertEqual(server.waitForRequests(count: 2).count, 2)
    }

    func testDefaultPairedRenewalImplementationDoesNotFallBackToBootstrapAllocation() async throws {
        let fixture = try PairedRenewalFixture(operation: .claim)
        let allocator = BootstrapOnlyRelayAllocator()
        let context = try fixture.authorizationContext { challenge in
            try PairedRelayAllocationClientProof.sign(
                challenge: challenge,
                using: fixture.clientKey
            )
        }

        await XCTAssertThrowsErrorAsync(try await allocator.renewPairedRelayRoute(
            currentRouteToken: fixture.routeToken,
            currentConfiguration: fixture.configuration(host: "127.0.0.1", port: 43171),
            currentLease: fixture.currentLease,
            runtimeIdentity: fixture.runtimeIdentity,
            authorizationSigner: fixture.runtimeSigner,
            authorizationContext: context,
            timeout: 1
        )) {
            XCTAssertEqual($0 as? RelayServiceRouteAllocationError, .pairedRenewalUnavailable)
        }
        XCTAssertEqual(allocator.bootstrapCalls.value, 0)
    }

    private func assertSuccessfulRenewal(
        operation: PairedRelayAllocationOperation,
        file: StaticString = #filePath,
        line: UInt = #line
    ) async throws {
        let fixture = try PairedRenewalFixture(operation: operation)
        let server = try PairedRelayTestServer(responseLines: [
            try fixture.challengeLine(),
            fixture.allocationLine(),
        ])
        defer { server.stop() }
        let receivedChallenge = LockedValue<PairedRelayAllocationAuthorizationChallenge>()
        let context = try fixture.authorizationContext { challenge in
            receivedChallenge.set(challenge)
            return try PairedRelayAllocationClientProof.sign(
                challenge: challenge,
                using: fixture.clientKey
            )
        }

        let allocation = try await fixture.allocator.renewPairedRelayRoute(
            currentRouteToken: fixture.routeToken,
            currentConfiguration: fixture.configuration(host: "127.0.0.1", port: server.port),
            currentLease: fixture.currentLease,
            runtimeIdentity: fixture.runtimeIdentity,
            authorizationSigner: fixture.runtimeSigner,
            authorizationContext: context,
            allocationToken: "allocation-token",
            timeout: 1
        )

        let requests = server.waitForRequests(count: 2)
        XCTAssertEqual(requests.count, 2, file: file, line: line)
        let expectedRequestParts = [
            "AETHERLINK_RELAY",
            "renew",
            fixture.routeToken,
            "crypto=2",
            "allocation_auth=runtime-client-p256-v2",
            "runtime_key_fingerprint=\(fixture.runtimeIdentity.fingerprint)",
            "runtime_public_key=\(fixture.runtimeIdentity.publicKeyBase64)",
            "client_key_fingerprint=\(fixture.clientFingerprint)",
            "client_public_key=\(fixture.clientPublicKeyBase64)",
            "request_id=\(fixture.requestID)",
            "authorization_id=\(fixture.authorizationID)",
            "transport_binding=\(fixture.transportBinding)",
            "allocation_token=allocation-token",
        ]
        XCTAssertEqual(
            requests.first,
            expectedRequestParts.joined(separator: " ") + "\n",
            file: file,
            line: line
        )
        let proofLine = try XCTUnwrap(requests.last, file: file, line: line)
        let proofParts = proofLine.dropLast().split(separator: " ", omittingEmptySubsequences: false)
        XCTAssertEqual(proofParts.count, 6, file: file, line: line)
        XCTAssertEqual(proofParts[0], "AETHERLINK_RELAY", file: file, line: line)
        XCTAssertEqual(proofParts[1], "paired_allocation_proof", file: file, line: line)
        XCTAssertEqual(proofParts[2], "crypto=2", file: file, line: line)
        XCTAssertEqual(proofParts[3], "challenge=\(fixture.challenge.challenge)", file: file, line: line)
        let runtimeSignature = String(proofParts[4].dropFirst("runtime_signature=".count))
        let clientSignature = String(proofParts[5].dropFirst("client_signature=".count))
        let runtimeProof = try PairedRelayAllocationRuntimeProof(
            publicKeyBase64: fixture.runtimeIdentity.publicKeyBase64,
            signatureBase64: runtimeSignature
        )
        let clientProof = try PairedRelayAllocationClientProof(
            publicKeyBase64: fixture.clientPublicKeyBase64,
            signatureBase64: clientSignature
        )
        XCTAssertTrue(runtimeProof.verify(challenge: fixture.challenge), file: file, line: line)
        XCTAssertTrue(clientProof.verify(challenge: fixture.challenge), file: file, line: line)
        XCTAssertEqual(receivedChallenge.value, fixture.challenge, file: file, line: line)
        XCTAssertEqual(allocation.relayID, fixture.challenge.nextRelayID, file: file, line: line)
        XCTAssertEqual(
            allocation.relayExpiresAtEpochMillis,
            fixture.challenge.nextRelayExpiresAtEpochMillis,
            file: file,
            line: line
        )
        XCTAssertEqual(allocation.relayNonce, fixture.challenge.nextRelayNonce, file: file, line: line)
        XCTAssertEqual(allocation.ticketGeneration, fixture.challenge.nextTicketGeneration, file: file, line: line)
        XCTAssertEqual(allocation.runtimeKeyFingerprint, fixture.runtimeIdentity.fingerprint, file: file, line: line)
        XCTAssertEqual(allocation.cryptoVersion, 2, file: file, line: line)
    }
}

private enum ChallengeMutation: Equatable {
    case unknownField
    case stale
}

private struct PairedRenewalFixture {
    let routeToken = "route-token"
    let requestID = "route-refresh-request"
    let authorizationID = "authorization-id"
    let transportBinding = String(repeating: "b", count: 64)
    let runtimeSigner: TestPairedRuntimeSigner
    let runtimeIdentity: RelayRuntimeIdentity
    let clientKey: P256.Signing.PrivateKey
    let clientPublicKeyBase64: String
    let clientFingerprint: String
    let currentLease: CompanionRemoteRouteLease
    let challenge: PairedRelayAllocationAuthorizationChallenge
    let allocator: TCPRelayServiceRouteAllocator

    init(operation: PairedRelayAllocationOperation) throws {
        let runtimeSigner = TestPairedRuntimeSigner(privateKey: P256.Signing.PrivateKey())
        let runtimeIdentity = try runtimeSigner.relayRuntimeIdentity()
        let clientKey = P256.Signing.PrivateKey()
        let clientPublicKeyBase64 = clientKey.publicKey.derRepresentation.base64EncodedString()
        let clientFingerprint = try PairedRelayAllocationAuthorization.publicKeyFingerprint(
            publicKeyBase64: clientPublicKeyBase64
        )
        let now = Int64((Date().timeIntervalSince1970 * 1_000).rounded())
        let currentLease = CompanionRemoteRouteLease(
            expiresAtEpochMillis: now + 60_000,
            nonce: "current-nonce",
            ticketGeneration: 7
        )
        self.runtimeSigner = runtimeSigner
        self.runtimeIdentity = runtimeIdentity
        self.clientKey = clientKey
        self.clientPublicKeyBase64 = clientPublicKeyBase64
        self.clientFingerprint = clientFingerprint
        self.currentLease = currentLease
        let bootstrapRelayID = RelayAllocationIdentityChallenge.relayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint
        )
        let pairedRelayID = RelayAllocationIdentityChallenge.pairedRelayID(
            routeToken: routeToken,
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: clientFingerprint
        )
        challenge = try PairedRelayAllocationAuthorizationChallenge(
            operation: operation,
            requestID: requestID,
            authorizationID: authorizationID,
            currentRelayID: operation == .claim ? bootstrapRelayID : pairedRelayID,
            nextRelayID: pairedRelayID,
            routeTokenHash: PairedRelayAllocationAuthorization.routeTokenHash(routeToken),
            runtimeKeyFingerprint: runtimeIdentity.fingerprint,
            clientKeyFingerprint: clientFingerprint,
            currentTicketGeneration: 7,
            nextTicketGeneration: 8,
            currentRelayExpiresAtEpochMillis: currentLease.expiresAtEpochMillis,
            currentRelayNonce: currentLease.nonce,
            nextRelayExpiresAtEpochMillis: currentLease.expiresAtEpochMillis + 60_000,
            nextRelayNonce: "next-nonce",
            challenge: String(repeating: "c", count: 64),
            challengeExpiresAtEpochMillis: now + 30_000,
            transportBinding: transportBinding
        )
        allocator = TCPRelayServiceRouteAllocator(
            authorizationIDProvider: { "authorization-id" }
        )
    }

    func configuration(host: String, port: UInt16) -> RelayPeerConfiguration {
        RelayPeerConfiguration(
            host: host,
            port: port,
            relayID: challenge.currentRelayID,
            relaySecret: "endpoint-owned-secret",
            relayNonce: currentLease.nonce,
            runtimeIdentity: runtimeIdentity,
            identityAuthorizationSigner: runtimeSigner
        )
    }

    func authorizationContext(
        provider: @escaping RuntimePairedRelayAuthorizationProvider
    ) throws -> RuntimePairedRelayAuthorizationContext {
        try RuntimePairedRelayAuthorizationContext(
            requestID: requestID,
            connectionID: UUID(),
            trustedClientPublicKeyBase64: clientPublicKeyBase64,
            trustedClientKeyFingerprint: clientFingerprint,
            transportBinding: transportBinding,
            clientAuthorizationProvider: provider
        )
    }

    func challengeLine(
        prefix: String = "AETHERLINK_RELAY paired_allocation_challenge ",
        mutation: ChallengeMutation? = nil
    ) throws -> String {
        var object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: JSONEncoder().encode(challenge)) as? [String: Any]
        )
        if mutation == .unknownField {
            object["future_field"] = true
        }
        if mutation == .stale {
            object["challenge_expires_at"] = 1
        }
        let data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        return prefix + String(decoding: data, as: UTF8.self) + "\n"
    }

    func allocationLine(relayNonce: String? = nil) -> String {
        let object: [String: Any] = [
            "relay_id": challenge.nextRelayID,
            "relay_expires_at": challenge.nextRelayExpiresAtEpochMillis,
            "relay_nonce": relayNonce ?? challenge.nextRelayNonce,
            "runtime_key_fingerprint": runtimeIdentity.fingerprint,
            "ticket_generation": challenge.nextTicketGeneration,
            "crypto_version": 2,
        ]
        let data = try! JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        return "AETHERLINK_RELAY allocation \(String(decoding: data, as: UTF8.self))\n"
    }
}

private struct TestPairedRuntimeSigner: RelayIdentityAuthorizationSigning, PairedRelayAllocationRuntimeSigning {
    let privateKey: P256.Signing.PrivateKey

    func relayRuntimeIdentity() throws -> RelayRuntimeIdentity {
        let publicKey = privateKey.publicKey.derRepresentation
        return try RelayRuntimeIdentity(
            publicKeyBase64: publicKey.base64EncodedString(),
            fingerprint: PairedRelayAllocationAuthorization.digestHex(publicKey)
        )
    }

    func signRelayAllocationChallenge(
        _ challenge: RelayAllocationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof {
        try identityProof(messageData: challenge.signedMessageData())
    }

    func signRelayRuntimeRegistrationChallenge(
        _ challenge: RelayRuntimeRegistrationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof {
        try identityProof(messageData: challenge.signedMessageData())
    }

    func signPairedRelayAllocationAuthorization(
        _ challenge: PairedRelayAllocationAuthorizationChallenge
    ) throws -> PairedRelayAllocationRuntimeProof {
        try PairedRelayAllocationRuntimeProof.sign(challenge: challenge, using: privateKey)
    }

    private func identityProof(messageData: Data) throws -> RelayIdentityAuthorizationProof {
        let signature = try privateKey.signature(for: SHA256.hash(data: messageData))
        return try RelayIdentityAuthorizationProof(
            runtimeIdentity: relayRuntimeIdentity(),
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
    }
}

private enum PairedSignerTestError: Error {
    case failed
}

private struct FailingPairedRuntimeSigner: RelayIdentityAuthorizationSigning, PairedRelayAllocationRuntimeSigning {
    let base: TestPairedRuntimeSigner

    func relayRuntimeIdentity() throws -> RelayRuntimeIdentity {
        try base.relayRuntimeIdentity()
    }

    func signRelayAllocationChallenge(
        _ challenge: RelayAllocationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof {
        try base.signRelayAllocationChallenge(challenge)
    }

    func signRelayRuntimeRegistrationChallenge(
        _ challenge: RelayRuntimeRegistrationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof {
        try base.signRelayRuntimeRegistrationChallenge(challenge)
    }

    func signPairedRelayAllocationAuthorization(
        _ challenge: PairedRelayAllocationAuthorizationChallenge
    ) throws -> PairedRelayAllocationRuntimeProof {
        throw PairedSignerTestError.failed
    }
}

private final class BootstrapOnlyRelayAllocator: RelayServiceRouteAllocating, @unchecked Sendable {
    let bootstrapCalls = LockedCounter()

    func allocateRelayRoute(
        host: String,
        port: UInt16,
        routeToken: String,
        allocationToken: String?,
        runtimeIdentity: RelayRuntimeIdentity,
        identityAuthorizationSigner: any RelayIdentityAuthorizationSigning,
        timeout: TimeInterval
    ) throws -> RelayServiceRouteAllocation {
        bootstrapCalls.increment()
        throw RelayServiceRouteAllocationError.invalidResponse
    }
}

private final class PairedRelayTestServer: @unchecked Sendable {
    let port: UInt16

    private let listenSocket: Int32
    private let responseLines: [String]
    private let lock = NSLock()
    private let requestSemaphore = DispatchSemaphore(value: 0)
    private var activeSocket: Int32 = -1
    private var requestLines: [String] = []

    init(responseLines: [String]) throws {
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else { throw PairedRelayTestServerError.socket }
        var yes: Int32 = 1
        setsockopt(socket, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = 0
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let bound = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(socket, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard bound == 0, Darwin.listen(socket, 1) == 0 else {
            Darwin.close(socket)
            throw PairedRelayTestServerError.socket
        }
        var boundAddress = sockaddr_in()
        var boundLength = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &boundAddress) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.getsockname(socket, $0, &boundLength)
            }
        }
        guard named == 0 else {
            Darwin.close(socket)
            throw PairedRelayTestServerError.socket
        }
        listenSocket = socket
        port = UInt16(bigEndian: boundAddress.sin_port)
        self.responseLines = responseLines
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.serve()
        }
    }

    func waitForRequests(count: Int, timeout: DispatchTime = .now() + 2) -> [String] {
        for _ in 0..<count {
            guard requestSemaphore.wait(timeout: timeout) == .success else { break }
        }
        lock.lock()
        defer { lock.unlock() }
        return requestLines
    }

    func stop() {
        Darwin.close(listenSocket)
        lock.lock()
        let socket = activeSocket
        activeSocket = -1
        lock.unlock()
        if socket >= 0 {
            Darwin.shutdown(socket, SHUT_RDWR)
            Darwin.close(socket)
        }
    }

    private func serve() {
        let socket = Darwin.accept(listenSocket, nil, nil)
        guard socket >= 0 else { return }
        lock.lock()
        activeSocket = socket
        lock.unlock()
        defer {
            lock.lock()
            if activeSocket == socket {
                activeSocket = -1
                Darwin.close(socket)
            }
            lock.unlock()
        }
        for responseLine in responseLines {
            guard let requestLine = readLine(socket: socket) else { return }
            lock.lock()
            requestLines.append(requestLine)
            lock.unlock()
            requestSemaphore.signal()
            guard writeAll(socket: socket, value: responseLine) else { return }
        }
    }

    private func readLine(socket: Int32) -> String? {
        var bytes: [UInt8] = []
        while bytes.count < 8_192 {
            var byte: UInt8 = 0
            guard Darwin.recv(socket, &byte, 1, 0) == 1 else { return nil }
            bytes.append(byte)
            if byte == UInt8(ascii: "\n") {
                return String(bytes: bytes, encoding: .utf8)
            }
        }
        return nil
    }

    private func writeAll(socket: Int32, value: String) -> Bool {
        let data = Data(value.utf8)
        return data.withUnsafeBytes { buffer in
            guard let base = buffer.baseAddress else { return true }
            var sent = 0
            while sent < buffer.count {
                let count = Darwin.send(socket, base.advanced(by: sent), buffer.count - sent, 0)
                guard count > 0 else { return false }
                sent += count
            }
            return true
        }
    }
}

private enum PairedRelayTestServerError: Error {
    case socket
}

private final class LockedCounter: @unchecked Sendable {
    private let lock = NSLock()
    private var count = 0

    var value: Int {
        lock.lock()
        defer { lock.unlock() }
        return count
    }

    func increment() {
        lock.lock()
        count += 1
        lock.unlock()
    }
}

private final class LockedValue<Value: Sendable>: @unchecked Sendable {
    private let lock = NSLock()
    private var storedValue: Value?

    var value: Value? {
        lock.lock()
        defer { lock.unlock() }
        return storedValue
    }

    func set(_ value: Value) {
        lock.lock()
        storedValue = value
        lock.unlock()
    }
}

private func XCTAssertThrowsErrorAsync<T>(
    _ expression: @autoclosure () async throws -> T,
    _ errorHandler: (any Error) -> Void,
    file: StaticString = #filePath,
    line: UInt = #line
) async {
    do {
        _ = try await expression()
        XCTFail("Expected expression to throw", file: file, line: line)
    } catch {
        errorHandler(error)
    }
}
