import BridgeProtocol
import CryptoKit
import Foundation

public enum FileRuntimeIdentityKeyStoreError: Error, LocalizedError, Equatable, Sendable {
    case readFailed(path: String, reason: String)
    case writeFailed(path: String, reason: String)
    case invalidData(path: String, reason: String)

    public var errorDescription: String? {
        switch self {
        case .readFailed(let path, let reason):
            return "Could not read the runtime identity key file at \(path): \(reason)"
        case .writeFailed(let path, let reason):
            return "Could not write the runtime identity key file at \(path): \(reason)"
        case .invalidData(let path, let reason):
            return "The runtime identity key file at \(path) is invalid: \(reason)"
        }
    }
}

public final class FileRuntimeIdentityKeyStore: RuntimeChallengeSigning, RelayIdentityAuthorizationSigning, InitialPairingRuntimeResultSigning, PairedRelayAllocationRuntimeSigning, @unchecked Sendable {
    private struct StoredIdentityKey: Codable {
        var version: Int
        var privateKeyBase64: String
    }

    private static let directoryPermissions = 0o700
    private static let filePermissions = 0o600

    private let fileURL: URL
    private let fileManager: FileManager
    private let lock = NSLock()

    public convenience init(fileManager: FileManager = .default) {
        self.init(fileURL: Self.defaultFileURL(), fileManager: fileManager)
    }

    public init(fileURL: URL, fileManager: FileManager = .default) {
        self.fileURL = fileURL
        self.fileManager = fileManager
    }

    public convenience init(path: String, fileManager: FileManager = .default) {
        self.init(fileURL: URL(fileURLWithPath: path), fileManager: fileManager)
    }

    public static func defaultFileURL() -> URL {
        let baseDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support", isDirectory: true)
        return baseDirectory
            .appendingPathComponent("AetherLink", isDirectory: true)
            .appendingPathComponent("runtime-identity.json", isDirectory: false)
    }

    public func loadOrCreate() throws -> RuntimeIdentityKey {
        let privateKey = try loadOrCreatePrivateKey()
        return RuntimeIdentityKeyStore.identityKey(from: privateKey)
    }

    public func relayRuntimeIdentity() throws -> RelayRuntimeIdentity {
        let privateKey = try loadOrCreatePrivateKey()
        return try relayRuntimeIdentity(from: privateKey)
    }

    public func signRelayAllocationChallenge(
        _ challenge: RelayAllocationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof {
        let privateKey = try loadOrCreatePrivateKey()
        let identity = try relayRuntimeIdentity(from: privateKey)
        guard challenge.runtimeKeyFingerprint == identity.fingerprint else {
            throw RelayIdentityAuthorizationError.invalidChallenge
        }
        let signature = try privateKey.signature(
            for: SHA256.hash(data: challenge.signedMessageData())
        )
        return try RelayIdentityAuthorizationProof(
            runtimeIdentity: identity,
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
    }

    public func signRelayRuntimeRegistrationChallenge(
        _ challenge: RelayRuntimeRegistrationIdentityChallenge
    ) throws -> RelayIdentityAuthorizationProof {
        let privateKey = try loadOrCreatePrivateKey()
        let identity = try relayRuntimeIdentity(from: privateKey)
        guard challenge.runtimeKeyFingerprint == identity.fingerprint else {
            throw RelayIdentityAuthorizationError.invalidChallenge
        }
        let signature = try privateKey.signature(
            for: SHA256.hash(data: challenge.signedMessageData())
        )
        return try RelayIdentityAuthorizationProof(
            runtimeIdentity: identity,
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
    }

    public func signPairedRelayAllocationAuthorization(
        _ challenge: PairedRelayAllocationAuthorizationChallenge
    ) throws -> PairedRelayAllocationRuntimeProof {
        let privateKey = try loadOrCreatePrivateKey()
        let identity = RuntimeIdentityKeyStore.identityKey(from: privateKey)
        guard challenge.runtimeKeyFingerprint == identity.fingerprint else {
            throw PairedRelayAllocationAuthorizationError.invalidFingerprint(
                "runtime_key_fingerprint"
            )
        }
        let proof = try PairedRelayAllocationRuntimeProof.sign(
            challenge: challenge,
            using: privateKey
        )
        guard proof.verify(challenge: challenge) else {
            throw PairedRelayAllocationAuthorizationError.invalidSignature(
                "runtime_signature"
            )
        }
        return proof
    }

    public func signAuthChallenge(
        deviceID: String,
        nonce: String,
        transportBinding: String? = nil
    ) throws -> RuntimeChallengeSignature {
        guard transportBinding.map(RuntimeIdentityKeyStore.isCanonicalTransportBinding) ?? true else {
            throw RuntimeIdentityKeyStoreError.invalidTransportBinding
        }
        let privateKey = try loadOrCreatePrivateKey()
        let messageData = RuntimeIdentityKeyStore.authChallengeMessageData(
            deviceID: deviceID,
            nonce: nonce,
            transportBinding: transportBinding
        )
        let signature = try privateKey.signature(for: SHA256.hash(data: messageData))
        return RuntimeChallengeSignature(
            runtimeKeyFingerprint: RuntimeIdentityKeyStore.identityKey(from: privateKey).fingerprint,
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
    }

    public func signInitialPairingResult(
        _ result: InitialPairingRuntimeResult
    ) throws -> InitialPairingRuntimeResultProof {
        try result.validate()
        let privateKey = try loadOrCreatePrivateKey()
        let identity = RuntimeIdentityKeyStore.identityKey(from: privateKey)
        guard result.runtimePublicKey == identity.publicKeyBase64,
              result.runtimeKeyFingerprint == identity.fingerprint else {
            throw InitialPairingProofError.invalidPublicKey("runtime_public_key")
        }
        let signature = try privateKey.signature(for: SHA256.hash(data: result.signedMessageData()))
        return try InitialPairingRuntimeResultProof(
            result: result,
            signatureBase64: signature.derRepresentation.base64EncodedString()
        )
    }

    private func loadOrCreatePrivateKey() throws -> P256.Signing.PrivateKey {
        lock.lock()
        defer { lock.unlock() }

        if let privateKey = try loadPrivateKey() {
            return privateKey
        }

        let privateKey = P256.Signing.PrivateKey()
        try store(privateKey)
        return privateKey
    }

    private func relayRuntimeIdentity(
        from privateKey: P256.Signing.PrivateKey
    ) throws -> RelayRuntimeIdentity {
        let identity = RuntimeIdentityKeyStore.identityKey(from: privateKey)
        return try RelayRuntimeIdentity(
            publicKeyBase64: identity.publicKeyBase64,
            fingerprint: identity.fingerprint
        )
    }

    private func loadPrivateKey() throws -> P256.Signing.PrivateKey? {
        let path = normalizedPath
        guard fileManager.fileExists(atPath: path) else {
            return nil
        }
        do {
            try secureDirectory()
            try secureFile()
        } catch {
            throw FileRuntimeIdentityKeyStoreError.writeFailed(path: path, reason: error.localizedDescription)
        }

        let data: Data
        do {
            data = try Data(contentsOf: fileURL)
        } catch {
            throw FileRuntimeIdentityKeyStoreError.readFailed(path: path, reason: error.localizedDescription)
        }

        let storedKey: StoredIdentityKey
        do {
            storedKey = try JSONDecoder().decode(StoredIdentityKey.self, from: data)
        } catch {
            throw FileRuntimeIdentityKeyStoreError.invalidData(path: path, reason: "Expected JSON with a base64 P-256 private key.")
        }

        guard storedKey.version == 1 else {
            throw FileRuntimeIdentityKeyStoreError.invalidData(path: path, reason: "Unsupported identity key file version \(storedKey.version).")
        }

        guard let privateKeyData = Data(base64Encoded: storedKey.privateKeyBase64) else {
            throw FileRuntimeIdentityKeyStoreError.invalidData(path: path, reason: "The private key is not valid base64.")
        }

        do {
            return try P256.Signing.PrivateKey(rawRepresentation: privateKeyData)
        } catch {
            throw FileRuntimeIdentityKeyStoreError.invalidData(path: path, reason: "The private key is not a valid P-256 signing key.")
        }
    }

    private func store(_ privateKey: P256.Signing.PrivateKey) throws {
        let path = normalizedPath
        do {
            try secureDirectory()
            let storedKey = StoredIdentityKey(
                version: 1,
                privateKeyBase64: privateKey.rawRepresentation.base64EncodedString()
            )
            let data = try JSONEncoder().encode(storedKey)
            try data.write(to: fileURL, options: [.atomic])
            try secureFile()
        } catch {
            throw FileRuntimeIdentityKeyStoreError.writeFailed(path: path, reason: error.localizedDescription)
        }
    }

    private func secureDirectory() throws {
        let directoryURL = fileURL.deletingLastPathComponent()
        try fileManager.createDirectory(
            at: directoryURL,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: Self.directoryPermissions]
        )
        try fileManager.setAttributes(
            [.posixPermissions: Self.directoryPermissions],
            ofItemAtPath: directoryURL.standardizedFileURL.path
        )
    }

    private func secureFile() throws {
        try fileManager.setAttributes(
            [.posixPermissions: Self.filePermissions],
            ofItemAtPath: normalizedPath
        )
    }

    private var normalizedPath: String {
        fileURL.standardizedFileURL.path
    }
}
