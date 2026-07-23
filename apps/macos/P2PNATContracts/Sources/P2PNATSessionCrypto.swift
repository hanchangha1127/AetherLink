import CryptoKit
import Foundation

public enum P2PNATSessionCryptoError: Error, Equatable {
    case invalidKey
    case ephemeralKeyAlreadyUsed
    case ephemeralKeyClosed
    case roleMismatch
    case confirmationIncomplete
    case cipherAlreadyCreated
    case invalidConfirmation
    case counterExhausted
    case authenticationFailed
}

public final class P2PNATSessionEphemeralKey: @unchecked Sendable {
    private enum Lifecycle: Equatable {
        case available
        case consumed
        case closed
    }

    private var privateKey: P256.KeyAgreement.PrivateKey?
    private let lock = NSLock()
    private var lifecycle = Lifecycle.available
    public let publicKeyX963: Data

    public init() {
        let key = P256.KeyAgreement.PrivateKey()
        privateKey = key
        publicKeyX963 = key.publicKey.x963Representation
    }

    init(testPrivateScalar: Data) throws {
        do {
            let key = try P256.KeyAgreement.PrivateKey(rawRepresentation: testPrivateScalar)
            privateKey = key
            publicKeyX963 = key.publicKey.x963Representation
        } catch {
            throw P2PNATSessionCryptoError.invalidKey
        }
    }

    fileprivate func sharedSecret(peerPublicKeyX963: Data) throws -> Data {
        lock.lock()
        switch lifecycle {
        case .consumed:
            lock.unlock()
            throw P2PNATSessionCryptoError.ephemeralKeyAlreadyUsed
        case .closed:
            lock.unlock()
            throw P2PNATSessionCryptoError.ephemeralKeyClosed
        case .available:
            break
        }
        guard let privateKey else {
            lifecycle = .closed
            lock.unlock()
            throw P2PNATSessionCryptoError.ephemeralKeyClosed
        }
        lifecycle = .consumed
        // Ownership transfers atomically to this one ECDH operation. Drop the
        // object's retained reference before releasing the lock; the local
        // reference lives only until this call returns.
        self.privateKey = nil
        lock.unlock()
        do {
            let peer = try P256.KeyAgreement.PublicKey(x963Representation: peerPublicKeyX963)
            let secret = try privateKey.sharedSecretFromKeyAgreement(with: peer)
            return secret.withUnsafeBytes { Data($0) }
        } catch {
            throw P2PNATSessionCryptoError.invalidKey
        }
    }

    /// Irreversibly abandons caller ownership of the one-use private key.
    ///
    /// Callers own a fresh key until handing it to a consuming API. The
    /// receiving API must call `close()` on every success, failure, and
    /// cancellation path. Closing is thread-safe and idempotent; if close wins
    /// before ECDH begins, later derivation fails with `ephemeralKeyClosed`.
    /// If ECDH already claimed ownership, close is a harmless no-op.
    public func close() {
        lock.lock()
        guard lifecycle == .available else {
            lock.unlock()
            return
        }
        lifecycle = .closed
        privateKey = nil
        lock.unlock()
    }

    func productionSharedSecret(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding
    ) throws -> Data {
        let transcript = binding.transcript
        let expectedLocalKey = binding.localRole == .client
            ? transcript.clientEphemeralPublicKey
            : transcript.runtimeEphemeralPublicKey
        guard publicKeyX963 == expectedLocalKey else {
            throw P2PNATSessionCryptoError.roleMismatch
        }
        let peerKey = binding.localRole == .client
            ? transcript.runtimeEphemeralPublicKey
            : transcript.clientEphemeralPublicKey
        return try sharedSecret(peerPublicKeyX963: peerKey)
    }

    #if DEBUG
    var testOnlyRetainsPrivateKey: Bool {
        lock.lock()
        defer { lock.unlock() }
        return privateKey != nil
    }

    var testOnlyIsClosed: Bool {
        lock.lock()
        defer { lock.unlock() }
        return lifecycle == .closed
    }

    var testOnlyIsConsumed: Bool {
        lock.lock()
        defer { lock.unlock() }
        return lifecycle == .consumed
    }
    #endif
}

public struct P2PNATSealedPayload: Equatable, Sendable {
    public let ciphertext: Data
    public let tag: Data

    public init(ciphertext: Data, tag: Data) {
        self.ciphertext = ciphertext
        self.tag = tag
    }
}

public final class P2PNATSessionKeys: @unchecked Sendable {
    public let transcriptDigest: Data
    fileprivate let transcript: IdentitySessionTranscript
    fileprivate let clientTrafficKey: SymmetricKey
    fileprivate let runtimeTrafficKey: SymmetricKey
    fileprivate let confirmationKey: SymmetricKey
    private let lock = NSLock()
    private var cipherIssued = false

    fileprivate init(
        transcriptDigest: Data,
        transcript: IdentitySessionTranscript,
        clientTrafficKey: SymmetricKey,
        runtimeTrafficKey: SymmetricKey,
        confirmationKey: SymmetricKey
    ) {
        self.transcriptDigest = transcriptDigest
        self.transcript = transcript
        self.clientTrafficKey = clientTrafficKey
        self.runtimeTrafficKey = runtimeTrafficKey
        self.confirmationKey = confirmationKey
    }

    var clientTrafficKeyBytes: Data { clientTrafficKey.bytes }
    var runtimeTrafficKeyBytes: Data { runtimeTrafficKey.bytes }
    var confirmationKeyBytes: Data { confirmationKey.bytes }

    public func confirmation(for role: P2PNATRole) throws -> Data {
        try transcript.keyConfirmation(key: confirmationKey.bytes, role: role)
    }

    public func verifiesConfirmation(_ proof: Data, for role: P2PNATRole) -> Bool {
        guard let expected = try? confirmation(for: role) else { return false }
        return constantTimeEqual(expected, proof)
    }

    fileprivate func trafficKey(for role: P2PNATRole) -> SymmetricKey {
        role == .client ? clientTrafficKey : runtimeTrafficKey
    }

    fileprivate func claimCipher() throws {
        lock.lock()
        defer { lock.unlock() }
        guard !cipherIssued else {
            throw P2PNATSessionCryptoError.cipherAlreadyCreated
        }
        cipherIssued = true
    }
}

public enum P2PNATSessionCrypto {
    static let keyInfoPrefix = Data("aetherlink-p2p-v1/session-keys/v1".utf8) + Data([0])

    public static func deriveKeys(
        localRole: P2PNATRole,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        transcript: IdentitySessionTranscript
    ) throws -> P2PNATSessionKeys {
        let expectedLocalKey = localRole == .client ? transcript.clientKey : transcript.runtimeKey
        guard localEphemeralKey.publicKeyX963 == expectedLocalKey else {
            throw P2PNATSessionCryptoError.roleMismatch
        }
        let peerKey = localRole == .client ? transcript.runtimeKey : transcript.clientKey
        var sharedSecret = try localEphemeralKey.sharedSecret(peerPublicKeyX963: peerKey)
        defer { sharedSecret.p2pNatWipe() }
        guard sharedSecret.count == 32 else { throw P2PNATSessionCryptoError.invalidKey }

        let transcriptDigest = Data(SHA256.hash(data: transcript.canonicalBytes()))
        let info = keyInfoPrefix + transcriptDigest
        var output = HKDF<SHA256>.deriveKey(
            inputKeyMaterial: SymmetricKey(data: sharedSecret),
            salt: transcriptDigest,
            info: info,
            outputByteCount: 96
        ).bytes
        defer { output.p2pNatWipe() }

        return P2PNATSessionKeys(
            transcriptDigest: transcriptDigest,
            transcript: transcript,
            clientTrafficKey: SymmetricKey(data: output[0..<32]),
            runtimeTrafficKey: SymmetricKey(data: output[32..<64]),
            confirmationKey: SymmetricKey(data: output[64..<96])
        )
    }

    #if DEBUG
    // Test-vector exporter. Secret material is absent from optimized release builds.
    static func vectorMaterial(
        localRole: P2PNATRole,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        transcript: IdentitySessionTranscript
    ) throws -> (sharedSecret: Data, salt: Data, info: Data, prk: Data, okm: Data) {
        let expectedLocalKey = localRole == .client ? transcript.clientKey : transcript.runtimeKey
        guard localEphemeralKey.publicKeyX963 == expectedLocalKey else {
            throw P2PNATSessionCryptoError.roleMismatch
        }
        let peerKey = localRole == .client ? transcript.runtimeKey : transcript.clientKey
        let sharedSecret = try localEphemeralKey.sharedSecret(peerPublicKeyX963: peerKey)
        let salt = Data(SHA256.hash(data: transcript.canonicalBytes()))
        let info = keyInfoPrefix + salt
        let prk = Data(HMAC<SHA256>.authenticationCode(
            for: sharedSecret,
            using: SymmetricKey(data: salt)
        ))
        let okm = HKDF<SHA256>.deriveKey(
            inputKeyMaterial: SymmetricKey(data: sharedSecret),
            salt: salt,
            info: info,
            outputByteCount: 96
        ).bytes
        return (sharedSecret, salt, info, prk, okm)
    }
    #endif
}

public final class P2PNATSessionHandshake: @unchecked Sendable {
    private let localRole: P2PNATRole
    private let keys: P2PNATSessionKeys
    private let lock = NSLock()
    private var localConfirmationEmitted = false
    private var peerConfirmationVerified = false
    private var cipherCreated = false

    public init(localRole: P2PNATRole, keys: P2PNATSessionKeys) {
        self.localRole = localRole
        self.keys = keys
    }

    public func localConfirmation() throws -> Data {
        lock.lock()
        defer { lock.unlock() }
        let proof = try keys.confirmation(for: localRole)
        localConfirmationEmitted = true
        return proof
    }

    public func acceptPeerConfirmation(_ proof: Data) throws {
        lock.lock()
        defer { lock.unlock() }
        let peerRole: P2PNATRole = localRole == .client ? .runtime : .client
        guard keys.verifiesConfirmation(proof, for: peerRole) else {
            throw P2PNATSessionCryptoError.invalidConfirmation
        }
        peerConfirmationVerified = true
    }

    public func makeCipher() throws -> P2PNATSessionCipher {
        lock.lock()
        defer { lock.unlock() }
        guard localConfirmationEmitted, peerConfirmationVerified else {
            throw P2PNATSessionCryptoError.confirmationIncomplete
        }
        guard !cipherCreated else {
            throw P2PNATSessionCryptoError.cipherAlreadyCreated
        }
        try keys.claimCipher()
        cipherCreated = true
        return P2PNATSessionCipher(localRole: localRole, keys: keys)
    }
}

public final class P2PNATSessionCipher: @unchecked Sendable {
    private let localRole: P2PNATRole
    private let keys: P2PNATSessionKeys
    private let lock = NSLock()
    private var sendSequence: UInt64
    private var receiveSequence: UInt64

    init(
        localRole: P2PNATRole,
        keys: P2PNATSessionKeys,
        sendSequence: UInt64 = 0,
        receiveSequence: UInt64 = 0
    ) {
        self.localRole = localRole
        self.keys = keys
        self.sendSequence = sendSequence
        self.receiveSequence = receiveSequence
    }

    public func seal(_ plaintext: Data) throws -> P2PNATSealedPayload {
        lock.lock()
        defer { lock.unlock() }
        guard sendSequence < UInt64.max - 1 else {
            throw P2PNATSessionCryptoError.counterExhausted
        }
        let sealed = try cryptSeal(plaintext, senderRole: localRole, sequence: sendSequence)
        sendSequence += 1
        return sealed
    }

    public func open(_ payload: P2PNATSealedPayload) throws -> Data {
        lock.lock()
        defer { lock.unlock() }
        guard receiveSequence < UInt64.max - 1 else {
            throw P2PNATSessionCryptoError.counterExhausted
        }
        let peerRole: P2PNATRole = localRole == .client ? .runtime : .client
        let plaintext = try cryptOpen(payload, senderRole: peerRole, sequence: receiveSequence)
        receiveSequence += 1
        return plaintext
    }

    static func nonce(role: P2PNATRole, sequence: UInt64) throws -> Data {
        guard sequence < UInt64.max else { throw P2PNATSessionCryptoError.counterExhausted }
        return Data((role == .client ? "CLNT" : "RUNT").utf8) + sequence.bigEndianData
    }

    static func aad(
        transcript: IdentitySessionTranscript,
        senderRole: P2PNATRole,
        sequence: UInt64
    ) -> Data {
        transcript.canonicalBytes()
            + Data("aetherlink-p2p-v1:traffic:\(senderRole.rawValue):".utf8)
            + sequence.bigEndianData
    }

    private func cryptSeal(
        _ plaintext: Data,
        senderRole: P2PNATRole,
        sequence: UInt64
    ) throws -> P2PNATSealedPayload {
        do {
            let nonce = try AES.GCM.Nonce(data: Self.nonce(role: senderRole, sequence: sequence))
            let sealed = try AES.GCM.seal(
                plaintext,
                using: keys.trafficKey(for: senderRole),
                nonce: nonce,
                authenticating: Self.aad(
                    transcript: keys.transcript,
                    senderRole: senderRole,
                    sequence: sequence
                )
            )
            return P2PNATSealedPayload(ciphertext: sealed.ciphertext, tag: sealed.tag)
        } catch let error as P2PNATSessionCryptoError {
            throw error
        } catch {
            throw P2PNATSessionCryptoError.authenticationFailed
        }
    }

    private func cryptOpen(
        _ payload: P2PNATSealedPayload,
        senderRole: P2PNATRole,
        sequence: UInt64
    ) throws -> Data {
        do {
            let nonce = try AES.GCM.Nonce(data: Self.nonce(role: senderRole, sequence: sequence))
            let box = try AES.GCM.SealedBox(
                nonce: nonce,
                ciphertext: payload.ciphertext,
                tag: payload.tag
            )
            return try AES.GCM.open(
                box,
                using: keys.trafficKey(for: senderRole),
                authenticating: Self.aad(
                    transcript: keys.transcript,
                    senderRole: senderRole,
                    sequence: sequence
                )
            )
        } catch let error as P2PNATSessionCryptoError {
            throw error
        } catch {
            throw P2PNATSessionCryptoError.authenticationFailed
        }
    }

}

private func constantTimeEqual(_ lhs: Data, _ rhs: Data) -> Bool {
    let left = [UInt8](lhs)
    let right = [UInt8](rhs)
    var difference = left.count ^ right.count
    for index in 0..<max(left.count, right.count) {
        difference |= Int((index < left.count ? left[index] : 0) ^ (index < right.count ? right[index] : 0))
    }
    return difference == 0
}

private extension SymmetricKey {
    var bytes: Data { withUnsafeBytes { Data($0) } }
}

private extension Data {
    mutating func p2pNatWipe() {
        resetBytes(in: startIndex..<endIndex)
    }
}

private extension UInt64 {
    var bigEndianData: Data {
        var value = bigEndian
        return withUnsafeBytes(of: &value) { Data($0) }
    }
}
