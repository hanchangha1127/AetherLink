import BridgeProtocol
import Foundation

public struct RelayPairedClientRegistrationChallengeResponse: Equatable, Sendable {
    public static let prefix = "\(RelayHandshake.prefix) client_registration_challenge "

    public let challenge: PairedClientRelayRegistrationChallenge

    public init(challenge: PairedClientRelayRegistrationChallenge) {
        self.challenge = challenge
    }

    public func responseLine() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let body = try encoder.encode(challenge)
        guard let json = String(data: body, encoding: .utf8) else {
            throw RelayAllocationError.invalidResponseFormat
        }
        return Data("\(Self.prefix)\(json)\n".utf8)
    }

    public static func parseResponseLine(_ line: String) throws -> Self {
        guard line.hasSuffix("\n"), !line.hasSuffix("\r\n") else {
            throw RelayAllocationError.invalidResponseFormat
        }
        let body = line.dropLast()
        guard body.hasPrefix(Self.prefix) else {
            throw RelayAllocationError.invalidResponseFormat
        }
        let json = body.dropFirst(Self.prefix.count)
        guard !json.isEmpty, let data = String(json).data(using: .utf8) else {
            throw RelayAllocationError.invalidResponseFormat
        }
        do {
            return Self(
                challenge: try JSONDecoder().decode(
                    PairedClientRelayRegistrationChallenge.self,
                    from: data
                )
            )
        } catch {
            throw RelayAllocationError.invalidResponseFormat
        }
    }
}

public struct RelayPairedClientRegistrationProofRequest: Equatable, Sendable {
    public static let prefix = "\(RelayHandshake.prefix) client_registration_proof"

    public let challenge: String
    public let proof: PairedClientRelayRegistrationProof

    public init(
        challenge: String,
        clientPublicKeyBase64: String,
        clientSignatureBase64: String
    ) throws {
        guard PairedRelayAllocationAuthorization.isCanonicalDigest(challenge) else {
            throw RelayAllocationError.invalidFormat
        }
        do {
            proof = try PairedClientRelayRegistrationProof(
                clientPublicKeyBase64: clientPublicKeyBase64,
                clientSignatureBase64: clientSignatureBase64
            )
        } catch {
            throw RelayAllocationError.invalidFormat
        }
        self.challenge = challenge
    }

    public static func parse(_ line: String) throws -> Self {
        let parts = try exactControlLineParts(line)
        guard parts.count == 6,
              parts[0] == Substring(RelayHandshake.prefix),
              parts[1] == "client_registration_proof",
              parts[2] == "crypto=2",
              let challenge = exactFieldValue(parts[3], name: "challenge"),
              let clientPublicKey = exactFieldValue(parts[4], name: "client_public_key"),
              let clientSignature = exactFieldValue(parts[5], name: "client_signature")
        else {
            throw RelayAllocationError.invalidFormat
        }
        return try Self(
            challenge: challenge,
            clientPublicKeyBase64: clientPublicKey,
            clientSignatureBase64: clientSignature
        )
    }

    public func requestLine() -> Data {
        Data(
            ("\(Self.prefix) crypto=2 challenge=\(challenge) " +
                "client_public_key=\(proof.clientPublicKeyBase64) " +
                "client_signature=\(proof.clientSignatureBase64)\n").utf8
        )
    }
}

private func exactControlLineParts(_ line: String) throws -> [Substring] {
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

private func exactFieldValue(_ field: Substring, name: String) -> String? {
    let prefix = "\(name)="
    guard field.hasPrefix(prefix) else { return nil }
    let value = String(field.dropFirst(prefix.count))
    return value.isEmpty ? nil : value
}
