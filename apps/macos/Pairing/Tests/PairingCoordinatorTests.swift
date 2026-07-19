import XCTest
@testable import Pairing

final class PairingCoordinatorTests: XCTestCase {
    func testPairingSessionReportsCompleteCanonicalRelayQRCodeMaterial() throws {
        var session = relayPairingSession(relayHost: "RELAY.EXAMPLE.TEST.", relayScope: "remote")
        session.relaySecret = String(repeating: "s", count: 512)
        session.relayNonce = String(repeating: "n", count: 512)

        XCTAssertTrue(session.hasCompleteCanonicalRelayQRCodeMaterial)
        let queryItems = try parseQueryItems(from: session.qrPayload)
        let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)
        XCTAssertEqual(queryItems["relay_host"], "relay.example.test")
        XCTAssertEqual(queryItems["relay_secret"], session.relaySecret)
        XCTAssertEqual(queryItems["relay_nonce"], session.relayNonce)
        XCTAssertEqual(compactQueryItems["rh"], "relay.example.test")
        XCTAssertEqual(compactQueryItems["rs"], session.relaySecret)
        XCTAssertEqual(compactQueryItems["rrn"], session.relayNonce)
    }

    func testPairingSessionRejectsIncompleteOrNonCanonicalRelayQRCodeMaterial() throws {
        let overlongValue = String(repeating: "x", count: 513)
        let invalidCases: [(name: String, mutate: (inout PairingSession) -> Void)] = [
            ("overlong secret", { $0.relaySecret = overlongValue }),
            ("overlong nonce", { $0.relayNonce = overlongValue }),
            ("whitespace secret", { $0.relaySecret = "relay secret" }),
            ("whitespace nonce", { $0.relayNonce = "relay\nnonce" }),
            ("invalid host", { $0.relayHost = "https://relay.example.test" }),
            ("invalid scope", { $0.relayScope = "REMOTE" }),
            ("missing host", { $0.relayHost = nil }),
            ("missing port", { $0.relayPort = nil }),
            ("missing id", { $0.relayID = nil }),
            ("missing secret", { $0.relaySecret = nil }),
            ("missing expiration", { $0.relayExpiresAtEpochMillis = nil }),
            ("missing nonce", { $0.relayNonce = nil })
        ]

        for invalidCase in invalidCases {
            var session = relayPairingSession(relayHost: "relay.example.test", relayScope: "remote")
            invalidCase.mutate(&session)

            XCTAssertFalse(
                session.hasCompleteCanonicalRelayQRCodeMaterial,
                invalidCase.name
            )
            let queryItems = try parseQueryItems(from: session.qrPayload)
            let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)
            for key in ["relay_host", "relay_port", "relay_id", "relay_secret", "relay_expires_at", "relay_nonce"] {
                XCTAssertNil(queryItems[key], invalidCase.name)
            }
            for key in ["rh", "rp", "ri", "rs", "rx", "rrn"] {
                XCTAssertNil(compactQueryItems[key], invalidCase.name)
            }
        }
    }

    func testPairingQRCodeRejectsInvalidRelayScopeBeforeEmission() throws {
        let session = relayPairingSession(relayHost: "relay.example.test", relayScope: "REMOTE")

        XCTAssertNil(session.relayScope)
        let queryItems = try parseQueryItems(from: session.qrPayload)
        let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)
        XCTAssertEqual(queryItems["relay_host"], "relay.example.test")
        XCTAssertEqual(queryItems["relay_port"], "43171")
        XCTAssertNil(queryItems["relay_scope"])
        XCTAssertNil(queryItems["route_scope"])
        XCTAssertNil(compactQueryItems["rsc"])
        XCTAssertFalse(session.qrPayload.contains("REMOTE"))
        XCTAssertFalse(session.compactQRCodePayload.contains("REMOTE"))
    }

    func testPairingQRCodeEmitsRelayHostsWithMatchingScopeBeforeEmission() throws {
        let cases: [(host: String, scope: String?)] = [
            ("relay.example.test", nil),
            ("relay.example.test", "remote"),
            ("100.64.1.10", "private_overlay"),
            ("fd00::1", "private_overlay"),
            ("127.0.0.1", "usb_reverse")
        ]
        for qrCase in cases {
            let session = relayPairingSession(relayHost: qrCase.host, relayScope: qrCase.scope)

            XCTAssertEqual(session.relayScope, qrCase.scope)
            try assertEmitsRelayRouteMaterial(session, relayHost: qrCase.host, relayScope: qrCase.scope)
        }
    }

    func testPairingQRCodeEmitsCanonicalRelayHostsBeforeEmission() throws {
        let cases: [(host: String, scope: String?, canonicalHost: String)] = [
            ("RELAY.EXAMPLE.TEST.", nil, "relay.example.test"),
            ("[fd00::1]", "private_overlay", "fd00::1"),
            ("[::1]", "usb_reverse", "::1")
        ]
        for qrCase in cases {
            let session = relayPairingSession(relayHost: qrCase.host, relayScope: qrCase.scope)

            try assertEmitsRelayRouteMaterial(
                session,
                relayHost: qrCase.canonicalHost,
                relayScope: qrCase.scope
            )
        }
    }

    func testPairingQRCodeOmitsRelayHostsWithoutMatchingScopeBeforeEmission() throws {
        let cases: [(host: String, scope: String?)] = [
            ("relay.example.test", "private_overlay"),
            ("relay.example.test", "usb_reverse"),
            ("100.64.1.10", nil),
            ("100.64.1.10", "remote"),
            ("100.64.1.10", "usb_reverse"),
            ("fd00::1", nil),
            ("fd00::1", "remote"),
            ("127.0.0.1", nil),
            ("127.0.0.1", "remote"),
            ("runtime.local", "remote"),
            ("169.254.1.10", "private_overlay"),
            ("0.0.0.0", "remote"),
            ("224.0.0.1", "remote"),
            ("ff02::1", "remote"),
            ("relay.example.test:43171", "remote"),
            ("https://relay.example.test", "remote")
        ]
        for qrCase in cases {
            let session = relayPairingSession(relayHost: qrCase.host, relayScope: qrCase.scope)

            try assertOmitsRelayRouteMaterial(session)
        }
    }

    func testPairingQRCodeDirectEndpointScopeDefaultsToLocalDiagnosticOnly() throws {
        let coordinator = PairingCoordinator()
        let defaultSession = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            routeToken: "route-token-1",
            host: "192.168.1.10",
            port: 43170
        )
        XCTAssertEqual(defaultSession.relayScope, "local_diagnostic")
        XCTAssertEqual(try parseQueryItems(from: defaultSession.qrPayload)["route_scope"], "local_diagnostic")
        XCTAssertEqual(try parseQueryItems(from: defaultSession.compactQRCodePayload)["rsc"], "local_diagnostic")

        let invalidScopeSession = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            routeToken: "route-token-1",
            host: "192.168.1.10",
            port: 43170,
            relayScope: "remote"
        )
        XCTAssertNil(invalidScopeSession.relayScope)
        XCTAssertNil(try parseQueryItems(from: invalidScopeSession.qrPayload)["route_scope"])
        XCTAssertNil(try parseQueryItems(from: invalidScopeSession.compactQRCodePayload)["rsc"])
    }

    func testPairingQRCodeOmitsNonCanonicalOpaqueRouteMaterialBeforeEmission() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            runtimePublicKeyBase64: "runtime public key",
            routeToken: "route token 1",
            relayHost: "relay.example.test",
            relayPort: 43171,
            relayID: "relay id 1",
            relaySecret: String(repeating: "s", count: 513),
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "relay\nnonce-1",
            relayScope: "remote",
            p2pRouteClass: "p2p_rendezvous",
            p2pRecordID: "p2p record 1",
            p2pEncryptedBody: String(repeating: "p", count: 2_049),
            p2pExpiresAtEpochMillis: 4_102_444_800_000,
            p2pAntiReplayNonce: "p2p\tnonce-1",
            p2pProtocolVersion: 1
        )

        let queryItems = try parseQueryItems(from: session.qrPayload)
        let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)

        XCTAssertNil(queryItems["runtime_public_key"])
        XCTAssertNil(queryItems["route_token"])
        XCTAssertNil(queryItems["relay_host"])
        XCTAssertNil(queryItems["relay_port"])
        XCTAssertNil(queryItems["relay_id"])
        XCTAssertNil(queryItems["relay_secret"])
        XCTAssertNil(queryItems["relay_expires_at"])
        XCTAssertNil(queryItems["relay_nonce"])
        XCTAssertNil(queryItems["relay_scope"])
        XCTAssertNil(queryItems["p2p_class"])
        XCTAssertNil(queryItems["p2p_record_id"])
        XCTAssertNil(queryItems["p2p_encrypted_body"])
        XCTAssertNil(queryItems["p2p_expires_at"])
        XCTAssertNil(queryItems["p2p_anti_replay_nonce"])
        XCTAssertNil(queryItems["p2p_protocol_version"])
        XCTAssertNil(compactQueryItems["rk"])
        XCTAssertNil(compactQueryItems["rt"])
        XCTAssertNil(compactQueryItems["rh"])
        XCTAssertNil(compactQueryItems["rp"])
        XCTAssertNil(compactQueryItems["ri"])
        XCTAssertNil(compactQueryItems["rs"])
        XCTAssertNil(compactQueryItems["rx"])
        XCTAssertNil(compactQueryItems["rrn"])
        XCTAssertNil(compactQueryItems["rsc"])
        XCTAssertNil(compactQueryItems["pc"])
        XCTAssertNil(compactQueryItems["prid"])
        XCTAssertNil(compactQueryItems["peb"])
        XCTAssertNil(compactQueryItems["px"])
        XCTAssertNil(compactQueryItems["pn"])
        XCTAssertNil(compactQueryItems["pv"])
    }

    func testPairingQRCodePreservesCanonicalOpaqueRouteSymbolsBeforeEmission() throws {
        let coordinator = PairingCoordinator()
        let session = coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            runtimePublicKeyBase64: "runtime+public/key=",
            routeToken: "route+token/1=",
            relayHost: "relay.example.test",
            relayPort: 43171,
            relayID: "relay+id/1=",
            relaySecret: "secret+with/symbols=",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "relay+nonce/1=",
            relayScope: "remote",
            p2pRouteClass: "p2p_rendezvous",
            p2pRecordID: "p2p+record/1=",
            p2pEncryptedBody: "opaque+candidate/body=",
            p2pExpiresAtEpochMillis: 4_102_444_800_000,
            p2pAntiReplayNonce: "p2p+nonce/1=",
            p2pProtocolVersion: 1
        )

        let queryItems = try parseQueryItems(from: session.qrPayload)
        let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)

        XCTAssertEqual(queryItems["runtime_public_key"], "runtime+public/key=")
        XCTAssertEqual(queryItems["route_token"], "route+token/1=")
        XCTAssertEqual(queryItems["relay_id"], "relay+id/1=")
        XCTAssertEqual(queryItems["relay_secret"], "secret+with/symbols=")
        XCTAssertEqual(queryItems["relay_nonce"], "relay+nonce/1=")
        XCTAssertEqual(queryItems["p2p_record_id"], "p2p+record/1=")
        XCTAssertEqual(queryItems["p2p_encrypted_body"], "opaque+candidate/body=")
        XCTAssertEqual(queryItems["p2p_anti_replay_nonce"], "p2p+nonce/1=")
        XCTAssertEqual(compactQueryItems["rk"], "runtime+public/key=")
        XCTAssertEqual(compactQueryItems["rt"], "route+token/1=")
        XCTAssertEqual(compactQueryItems["ri"], "relay+id/1=")
        XCTAssertEqual(compactQueryItems["rs"], "secret+with/symbols=")
        XCTAssertEqual(compactQueryItems["rrn"], "relay+nonce/1=")
        XCTAssertEqual(compactQueryItems["prid"], "p2p+record/1=")
        XCTAssertEqual(compactQueryItems["peb"], "opaque+candidate/body=")
        XCTAssertEqual(compactQueryItems["pn"], "p2p+nonce/1=")
        XCTAssertTrue(session.qrPayload.contains("runtime_public_key=runtime%2Bpublic/key%3D"))
        XCTAssertTrue(session.qrPayload.contains("relay_secret=secret%2Bwith/symbols%3D"))
    }

    func testPairingQRCodeOmitsInvalidRouteExpirationAndRelayPortBeforeEmission() throws {
        for relayPort in [0, 65_536] {
            let coordinator = PairingCoordinator()
            let session = coordinator.beginPairing(
                macDeviceID: "runtime-1",
                macName: "AetherLink Runtime",
                fingerprint: "runtime-fingerprint",
                routeToken: "route-token-1",
                relayHost: "relay.example.test",
                relayPort: relayPort,
                relayID: "relay-id-1",
                relaySecret: "relay-secret-1",
                relayExpiresAtEpochMillis: 4_102_444_800_000,
                relayNonce: "relay-nonce-1",
                relayScope: "remote"
            )

            try assertOmitsRelayRouteMaterial(session)
        }

        for relayExpiresAtEpochMillis in [0, -1] {
            let coordinator = PairingCoordinator()
            let session = coordinator.beginPairing(
                macDeviceID: "runtime-1",
                macName: "AetherLink Runtime",
                fingerprint: "runtime-fingerprint",
                routeToken: "route-token-1",
                relayHost: "relay.example.test",
                relayPort: 43171,
                relayID: "relay-id-1",
                relaySecret: "relay-secret-1",
                relayExpiresAtEpochMillis: Int64(relayExpiresAtEpochMillis),
                relayNonce: "relay-nonce-1",
                relayScope: "remote"
            )

            try assertOmitsRelayRouteMaterial(session)
        }

        for p2pExpiresAtEpochMillis in [0, -1] {
            let coordinator = PairingCoordinator()
            let session = coordinator.beginPairing(
                macDeviceID: "runtime-1",
                macName: "AetherLink Runtime",
                fingerprint: "runtime-fingerprint",
                routeToken: "route-token-1",
                p2pRouteClass: "p2p_rendezvous",
                p2pRecordID: "p2p-record-1",
                p2pEncryptedBody: "opaque-candidate-1",
                p2pExpiresAtEpochMillis: Int64(p2pExpiresAtEpochMillis),
                p2pAntiReplayNonce: "p2p-nonce-1",
                p2pProtocolVersion: 1
            )

            try assertOmitsP2PRouteMaterial(session)
        }
    }

    private func parseQueryItems(from payload: String) throws -> [String: String] {
        let components = try XCTUnwrap(URLComponents(string: payload))
        return try XCTUnwrap(components.queryItems).reduce(into: [String: String]()) { result, item in
            result[item.name] = item.value
        }
    }

    private func relayPairingSession(relayHost: String, relayScope: String?) -> PairingSession {
        let coordinator = PairingCoordinator()
        return coordinator.beginPairing(
            macDeviceID: "runtime-1",
            macName: "AetherLink Runtime",
            fingerprint: "runtime-fingerprint",
            routeToken: "route-token-1",
            relayHost: relayHost,
            relayPort: 43171,
            relayID: "relay-id-1",
            relaySecret: "relay-secret-1",
            relayExpiresAtEpochMillis: 4_102_444_800_000,
            relayNonce: "relay-nonce-1",
            relayScope: relayScope
        )
    }

    private func assertEmitsRelayRouteMaterial(
        _ session: PairingSession,
        relayHost: String,
        relayScope: String?,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws {
        let queryItems = try parseQueryItems(from: session.qrPayload)
        let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)
        XCTAssertEqual(queryItems["relay_host"], relayHost, file: file, line: line)
        XCTAssertEqual(queryItems["relay_port"], "43171", file: file, line: line)
        XCTAssertEqual(queryItems["relay_id"], "relay-id-1", file: file, line: line)
        XCTAssertEqual(queryItems["relay_secret"], "relay-secret-1", file: file, line: line)
        XCTAssertEqual(queryItems["relay_expires_at"], "4102444800000", file: file, line: line)
        XCTAssertEqual(queryItems["relay_nonce"], "relay-nonce-1", file: file, line: line)
        XCTAssertEqual(queryItems["relay_scope"], relayScope, file: file, line: line)
        XCTAssertEqual(compactQueryItems["rh"], relayHost, file: file, line: line)
        XCTAssertEqual(compactQueryItems["rp"], "43171", file: file, line: line)
        XCTAssertEqual(compactQueryItems["ri"], "relay-id-1", file: file, line: line)
        XCTAssertEqual(compactQueryItems["rs"], "relay-secret-1", file: file, line: line)
        XCTAssertEqual(compactQueryItems["rx"], "4102444800000", file: file, line: line)
        XCTAssertEqual(compactQueryItems["rrn"], "relay-nonce-1", file: file, line: line)
        XCTAssertEqual(compactQueryItems["rsc"], relayScope, file: file, line: line)
    }

    private func assertOmitsRelayRouteMaterial(
        _ session: PairingSession,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws {
        let queryItems = try parseQueryItems(from: session.qrPayload)
        let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)
        for key in ["relay_host", "relay_port", "relay_id", "relay_secret", "relay_expires_at", "relay_nonce", "relay_scope"] {
            XCTAssertNil(queryItems[key], file: file, line: line)
        }
        for key in ["rh", "rp", "ri", "rs", "rx", "rrn", "rsc"] {
            XCTAssertNil(compactQueryItems[key], file: file, line: line)
        }
    }

    private func assertOmitsP2PRouteMaterial(
        _ session: PairingSession,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws {
        let queryItems = try parseQueryItems(from: session.qrPayload)
        let compactQueryItems = try parseQueryItems(from: session.compactQRCodePayload)
        for key in ["p2p_class", "p2p_record_id", "p2p_encrypted_body", "p2p_expires_at", "p2p_anti_replay_nonce", "p2p_protocol_version"] {
            XCTAssertNil(queryItems[key], file: file, line: line)
        }
        for key in ["pc", "prid", "peb", "px", "pn", "pv"] {
            XCTAssertNil(compactQueryItems[key], file: file, line: line)
        }
    }
}
