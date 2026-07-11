import BridgeProtocol
import Foundation

public struct RelayPairedAllocationRenewalRequest: Equatable, Sendable {
    public static let action = "renew"

    public let routeToken: String
    public let runtimeKeyFingerprint: String
    public let runtimePublicKey: String
    public let clientKeyFingerprint: String
    public let clientPublicKey: String
    public let requestID: String
    public let authorizationID: String
    public let transportBinding: String
    public let allocationToken: String?

    public init(
        routeToken: String,
        runtimeKeyFingerprint: String,
        runtimePublicKey: String,
        clientKeyFingerprint: String,
        clientPublicKey: String,
        requestID: String,
        authorizationID: String,
        transportBinding: String,
        allocationToken: String? = nil
    ) throws {
        _ = try RelayAllocationRequest(routeToken: routeToken)
        _ = try PairedRelayAllocationAuthorization.validatedRuntimePublicKey(
            base64: runtimePublicKey,
            fingerprint: runtimeKeyFingerprint
        )
        _ = try PairedRelayAllocationAuthorization.validatedClientPublicKey(
            base64: clientPublicKey,
            fingerprint: clientKeyFingerprint
        )
        guard runtimeKeyFingerprint != clientKeyFingerprint,
              PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(requestID),
              PairedRelayAllocationAuthorization.isCanonicalOpaqueIdentifier(authorizationID),
              PairedRelayAllocationAuthorization.isCanonicalDigest(transportBinding)
        else {
            throw RelayAllocationError.invalidFormat
        }
        if let allocationToken {
            guard !allocationToken.isEmpty,
                  allocationToken.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
            else {
                throw RelayAllocationError.invalidAllocationToken
            }
        }
        self.routeToken = routeToken
        self.runtimeKeyFingerprint = runtimeKeyFingerprint
        self.runtimePublicKey = runtimePublicKey
        self.clientKeyFingerprint = clientKeyFingerprint
        self.clientPublicKey = clientPublicKey
        self.requestID = requestID
        self.authorizationID = authorizationID
        self.transportBinding = transportBinding
        self.allocationToken = allocationToken
    }

    public var runtimeIdentity: RelayRuntimeIdentity {
        get throws {
            try RelayRuntimeIdentity(
                publicKeyBase64: runtimePublicKey,
                fingerprint: runtimeKeyFingerprint
            )
        }
    }

    public static func parse(_ line: String) throws -> Self {
        let parts = try pairedExactControlLineParts(line)
        guard (12...13).contains(parts.count),
              parts[0] == Substring(RelayHandshake.prefix),
              parts[1] == Substring(action),
              parts[3] == "crypto=2",
              parts[4] == "allocation_auth=\(PairedRelayAllocationAuthorization.scheme)",
              let runtimeKeyFingerprint = pairedExactFieldValue(
                parts[5],
                name: "runtime_key_fingerprint"
              ),
              let runtimePublicKey = pairedExactFieldValue(
                parts[6],
                name: "runtime_public_key"
              ),
              let clientKeyFingerprint = pairedExactFieldValue(
                parts[7],
                name: "client_key_fingerprint"
              ),
              let clientPublicKey = pairedExactFieldValue(
                parts[8],
                name: "client_public_key"
              ),
              let requestID = pairedExactFieldValue(parts[9], name: "request_id"),
              let authorizationID = pairedExactFieldValue(
                parts[10],
                name: "authorization_id"
              ),
              let transportBinding = pairedExactFieldValue(
                parts[11],
                name: "transport_binding"
              )
        else {
            throw RelayAllocationError.invalidFormat
        }
        var allocationToken: String?
        if parts.count == 13 {
            guard let value = pairedExactFieldValue(parts[12], name: "allocation_token") else {
                throw RelayAllocationError.invalidFormat
            }
            allocationToken = value
        }
        do {
            return try Self(
                routeToken: String(parts[2]),
                runtimeKeyFingerprint: runtimeKeyFingerprint,
                runtimePublicKey: runtimePublicKey,
                clientKeyFingerprint: clientKeyFingerprint,
                clientPublicKey: clientPublicKey,
                requestID: requestID,
                authorizationID: authorizationID,
                transportBinding: transportBinding,
                allocationToken: allocationToken
            )
        } catch let error as RelayAllocationError {
            throw error
        } catch {
            throw RelayAllocationError.invalidFormat
        }
    }

    public static func isRenewalLine(_ line: String) -> Bool {
        let parts = line.split(whereSeparator: { $0.isWhitespace })
        return parts.count >= 2 &&
            parts[0] == Substring(RelayHandshake.prefix) &&
            parts[1] == Substring(action)
    }

    public func requestLine() -> Data {
        var parts = [
            RelayHandshake.prefix,
            Self.action,
            routeToken,
            "crypto=2",
            "allocation_auth=\(PairedRelayAllocationAuthorization.scheme)",
            "runtime_key_fingerprint=\(runtimeKeyFingerprint)",
            "runtime_public_key=\(runtimePublicKey)",
            "client_key_fingerprint=\(clientKeyFingerprint)",
            "client_public_key=\(clientPublicKey)",
            "request_id=\(requestID)",
            "authorization_id=\(authorizationID)",
            "transport_binding=\(transportBinding)",
        ]
        if let allocationToken {
            parts.append("allocation_token=\(allocationToken)")
        }
        return Data("\(parts.joined(separator: " "))\n".utf8)
    }
}

public struct RelayPairedAllocationChallengeResponse: Equatable, Sendable {
    public static let responsePrefix = "\(RelayHandshake.prefix) paired_allocation_challenge "

    public let challenge: PairedRelayAllocationAuthorizationChallenge

    public init(challenge: PairedRelayAllocationAuthorizationChallenge) {
        self.challenge = challenge
    }

    public func responseLine() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return Data(
            "\(Self.responsePrefix)\(String(decoding: try encoder.encode(challenge), as: UTF8.self))\n".utf8
        )
    }

    public static func parseResponseLine(_ line: String) throws -> Self {
        guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else {
            throw RelayAllocationError.invalidResponseFormat
        }
        let body = String(line.dropLast())
        guard body.hasPrefix(responsePrefix),
              !body.dropFirst(responsePrefix.count).contains("\n")
        else {
            throw RelayAllocationError.invalidResponseFormat
        }
        do {
            let data = Data(body.dropFirst(responsePrefix.count).utf8)
            guard let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  Set(payload.keys) == challengeFieldNames
            else {
                throw RelayAllocationError.unexpectedResponseMetadata
            }
            let challenge = try JSONDecoder().decode(
                PairedRelayAllocationAuthorizationChallenge.self,
                from: data
            )
            return Self(challenge: challenge)
        } catch {
            throw RelayAllocationError.invalidResponseFormat
        }
    }

    private static let challengeFieldNames: Set<String> = [
        "scheme",
        "protocol_version",
        "operation",
        "request_id",
        "authorization_id",
        "current_relay_id",
        "next_relay_id",
        "route_token_hash",
        "runtime_key_fingerprint",
        "client_key_fingerprint",
        "current_ticket_generation",
        "next_ticket_generation",
        "current_relay_expires_at",
        "current_relay_nonce",
        "next_relay_expires_at",
        "next_relay_nonce",
        "challenge",
        "challenge_expires_at",
        "transport_binding",
    ]
}

public struct RelayPairedAllocationProofRequest: Equatable, Sendable {
    public static let prefix = "\(RelayHandshake.prefix) paired_allocation_proof"

    public let challenge: String
    public let runtimeProof: PairedRelayAllocationRuntimeProof
    public let clientProof: PairedRelayAllocationClientProof

    public init(
        challenge: String,
        runtimeSignatureBase64: String,
        clientSignatureBase64: String,
        renewalRequest: RelayPairedAllocationRenewalRequest
    ) throws {
        guard PairedRelayAllocationAuthorization.isCanonicalDigest(challenge) else {
            throw RelayAllocationError.invalidFormat
        }
        do {
            runtimeProof = try PairedRelayAllocationRuntimeProof(
                publicKeyBase64: renewalRequest.runtimePublicKey,
                signatureBase64: runtimeSignatureBase64
            )
            clientProof = try PairedRelayAllocationClientProof(
                publicKeyBase64: renewalRequest.clientPublicKey,
                signatureBase64: clientSignatureBase64
            )
        } catch {
            throw RelayAllocationError.invalidFormat
        }
        self.challenge = challenge
    }

    public static func parse(
        _ line: String,
        renewalRequest: RelayPairedAllocationRenewalRequest
    ) throws -> Self {
        let parts = try pairedExactControlLineParts(line)
        guard parts.count == 6,
              parts[0] == Substring(RelayHandshake.prefix),
              parts[1] == "paired_allocation_proof",
              parts[2] == "crypto=2",
              let challenge = pairedExactFieldValue(parts[3], name: "challenge"),
              let runtimeSignature = pairedExactFieldValue(
                parts[4],
                name: "runtime_signature"
              ),
              let clientSignature = pairedExactFieldValue(
                parts[5],
                name: "client_signature"
              )
        else {
            throw RelayAllocationError.invalidFormat
        }
        return try Self(
            challenge: challenge,
            runtimeSignatureBase64: runtimeSignature,
            clientSignatureBase64: clientSignature,
            renewalRequest: renewalRequest
        )
    }

    public func requestLine() -> Data {
        let line =
            "\(Self.prefix) crypto=2 challenge=\(challenge) " +
                "runtime_signature=\(runtimeProof.signatureBase64) " +
                "client_signature=\(clientProof.signatureBase64)\n"
        return Data(line.utf8)
    }
}

private func pairedExactControlLineParts(_ line: String) throws -> [Substring] {
    guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else {
        throw RelayAllocationError.invalidFormat
    }
    let body = line.dropLast()
    guard !body.contains("\n"), !body.contains("\r") else {
        throw RelayAllocationError.invalidFormat
    }
    let parts = body.split(separator: " ", omittingEmptySubsequences: false)
    guard parts.allSatisfy({ !$0.isEmpty }) else {
        throw RelayAllocationError.invalidFormat
    }
    return parts
}

private func pairedExactFieldValue(_ field: Substring, name: String) -> String? {
    let prefix = "\(name)="
    guard field.hasPrefix(prefix) else { return nil }
    let value = String(field.dropFirst(prefix.count))
    return value.isEmpty ? nil : value
}
