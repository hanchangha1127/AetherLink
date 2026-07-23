import CryptoKit
import Foundation

public enum ProductionSecureSessionCryptoContract {
    public static let keyConfirmationObjectType: UInt8 = 29
    public static let encryptedRecordObjectType: UInt8 = 30
    public static let maximumKeyConfirmationBytes = 384
    public static let maximumRecordBytes = 1_048_576
    public static let maximumPlaintextBytes = 1_048_448
    public static let maximumCiphertextBytes = 1_048_448
    public static let maximumEpoch: UInt32 = 15
    public static let maximumRecordsPerEpoch: UInt64 = 1 << 20
    public static let maximumPlaintextBytesPerEpoch: UInt64 = 1 << 30
    public static let maximumRecordsPerSession: UInt64 = 1 << 24
    public static let maximumPlaintextBytesPerSession: UInt64 = 1 << 34
}

public enum ProductionSecureSessionCryptoError: Error, Equatable, Sendable {
    case invalidBinding
    case invalidKey
    case ephemeralKeyAlreadyUsed
    case ephemeralKeyClosed
    case roleMismatch
    case notYetValid
    case expired
    case timeRegression
    case invalidCanonical
    case invalidContent
    case invalidConfirmation
    case confirmationConflict
    case confirmationIncomplete
    case cipherAlreadyCreated
    case unexpectedRecord
    case keyUpdateRequired
    case invalidKeyUpdate
    case recordLimitExceeded
    case byteLimitExceeded
    case sessionLimitExceeded
    case authenticationFailed
    case sealFailed
    case closed
}

public enum ProductionSecureSessionContentType: UInt8, Sendable {
    case application = 1
    case keyUpdate = 2
}

public struct ProductionSecureSessionKeyConfirmation: Equatable, Sendable {
    public let sessionId: String
    public let transcriptDigestHex: String
    public let grantAuthorizationDigestHex: String
    public let confirmingRole: P2PNATRole
    public let epoch: UInt32
    public let proof: Data

    public init(
        sessionId: String,
        transcriptDigestHex: String,
        grantAuthorizationDigestHex: String,
        confirmingRole: P2PNATRole,
        epoch: UInt32 = 0,
        proof: Data
    ) throws {
        guard sessionId.utf8.count == 32,
              productionCryptoIsLowerHex(sessionId),
              productionCryptoIsDigestHex(transcriptDigestHex),
              productionCryptoIsDigestHex(grantAuthorizationDigestHex),
              epoch == 0,
              proof.count == 32 else {
            throw ProductionSecureSessionCryptoError.invalidContent
        }
        self.sessionId = sessionId
        self.transcriptDigestHex = transcriptDigestHex
        self.grantAuthorizationDigestHex = grantAuthorizationDigestHex
        self.confirmingRole = confirmingRole
        self.epoch = epoch
        self.proof = proof
        guard canonicalBytes().count
                <= ProductionSecureSessionCryptoContract.maximumKeyConfirmationBytes else {
            throw ProductionSecureSessionCryptoError.invalidContent
        }
    }

    public init(canonicalBytes data: Data) throws {
        let fields: [Data]
        do {
            fields = try ProductionC1InternalBridge.decode(
                data,
                objectType: ProductionSecureSessionCryptoContract.keyConfirmationObjectType,
                fieldCount: 8,
                maximumBytes: ProductionSecureSessionCryptoContract.maximumKeyConfirmationBytes
            )
        } catch {
            throw ProductionSecureSessionCryptoError.invalidCanonical
        }
        guard fields[0] == ProductionC1InternalBridge.ascii(ProductionSecureSessionContract.suite),
              fields[1] == ProductionC1InternalBridge.ascii(ProductionSecureSessionContract.profile),
              let role = P2PNATRole(
                  rawValue: try productionCryptoText(fields[5])
              ) else {
            throw ProductionSecureSessionCryptoError.invalidContent
        }
        do {
            try self.init(
                sessionId: ProductionC1InternalBridge.text(fields[2]),
                transcriptDigestHex: ProductionC1InternalBridge.text(fields[3]),
                grantAuthorizationDigestHex: ProductionC1InternalBridge.text(fields[4]),
                confirmingRole: role,
                epoch: ProductionC1InternalBridge.uint32(fields[6]),
                proof: fields[7]
            )
        } catch let error as ProductionSecureSessionCryptoError {
            throw error
        } catch {
            throw ProductionSecureSessionCryptoError.invalidCanonical
        }
        guard canonicalBytes() == data else {
            throw ProductionSecureSessionCryptoError.invalidCanonical
        }
    }

    public func canonicalBytes() -> Data {
        ProductionC1InternalBridge.encode(
            objectType: ProductionSecureSessionCryptoContract.keyConfirmationObjectType,
            fields: prefixFields + [proof]
        )
    }

    fileprivate var canonicalPrefix: Data {
        ProductionC1InternalBridge.encode(
            objectType: ProductionSecureSessionCryptoContract.keyConfirmationObjectType,
            fields: prefixFields
        )
    }

    private var prefixFields: [Data] {
        [
            ProductionC1InternalBridge.ascii(ProductionSecureSessionContract.suite),
            ProductionC1InternalBridge.ascii(ProductionSecureSessionContract.profile),
            ProductionC1InternalBridge.ascii(sessionId),
            ProductionC1InternalBridge.ascii(transcriptDigestHex),
            ProductionC1InternalBridge.ascii(grantAuthorizationDigestHex),
            ProductionC1InternalBridge.ascii(confirmingRole.rawValue),
            ProductionC1InternalBridge.be(epoch),
        ]
    }
}

public struct ProductionSecureSessionEncryptedRecord: Equatable, Sendable {
    public let sessionId: String
    public let senderRole: P2PNATRole
    public let epoch: UInt32
    public let sequence: UInt64
    public let contentType: ProductionSecureSessionContentType
    public let ciphertext: Data
    public let tag: Data

    public init(
        sessionId: String,
        senderRole: P2PNATRole,
        epoch: UInt32,
        sequence: UInt64,
        contentType: ProductionSecureSessionContentType,
        ciphertext: Data,
        tag: Data
    ) throws {
        guard sessionId.utf8.count == 32,
              productionCryptoIsLowerHex(sessionId),
              epoch <= ProductionSecureSessionCryptoContract.maximumEpoch,
              sequence < ProductionSecureSessionCryptoContract.maximumRecordsPerEpoch,
              ciphertext.count
                <= ProductionSecureSessionCryptoContract.maximumCiphertextBytes,
              tag.count == 16 else {
            throw ProductionSecureSessionCryptoError.invalidContent
        }
        self.sessionId = sessionId
        self.senderRole = senderRole
        self.epoch = epoch
        self.sequence = sequence
        self.contentType = contentType
        self.ciphertext = ciphertext
        self.tag = tag
        guard canonicalBytes().count <= ProductionSecureSessionCryptoContract.maximumRecordBytes else {
            throw ProductionSecureSessionCryptoError.invalidContent
        }
    }

    public init(canonicalBytes data: Data) throws {
        let fields: [Data]
        do {
            fields = try ProductionC1InternalBridge.decode(
                data,
                objectType: ProductionSecureSessionCryptoContract.encryptedRecordObjectType,
                fieldCount: 7,
                maximumBytes: ProductionSecureSessionCryptoContract.maximumRecordBytes
            )
        } catch {
            throw ProductionSecureSessionCryptoError.invalidCanonical
        }
        guard fields[1].count == 1,
              let role = productionCryptoRole(byte: fields[1][fields[1].startIndex]),
              fields[4].count == 1,
              let content = ProductionSecureSessionContentType(
                  rawValue: fields[4][fields[4].startIndex]
              ) else {
            throw ProductionSecureSessionCryptoError.invalidContent
        }
        do {
            try self.init(
                sessionId: ProductionC1InternalBridge.text(fields[0]),
                senderRole: role,
                epoch: ProductionC1InternalBridge.uint32(fields[2]),
                sequence: ProductionC1InternalBridge.uint64(fields[3]),
                contentType: content,
                ciphertext: fields[5],
                tag: fields[6]
            )
        } catch let error as ProductionSecureSessionCryptoError {
            throw error
        } catch {
            throw ProductionSecureSessionCryptoError.invalidCanonical
        }
        guard canonicalBytes() == data else {
            throw ProductionSecureSessionCryptoError.invalidCanonical
        }
    }

    /// Re-homes only the authenticated result bytes while preserving metadata
    /// that has already passed this type's public initializer.
    fileprivate init(
        trustedSessionId: String,
        senderRole: P2PNATRole,
        epoch: UInt32,
        sequence: UInt64,
        contentType: ProductionSecureSessionContentType,
        ciphertext: Data,
        tag: Data
    ) {
        sessionId = trustedSessionId
        self.senderRole = senderRole
        self.epoch = epoch
        self.sequence = sequence
        self.contentType = contentType
        self.ciphertext = ciphertext
        self.tag = tag
    }

    public func canonicalBytes() -> Data {
        ProductionC1InternalBridge.encode(
            objectType: ProductionSecureSessionCryptoContract.encryptedRecordObjectType,
            fields: prefixFields + [ciphertext, tag]
        )
    }

    fileprivate var canonicalPrefix: Data {
        ProductionC1InternalBridge.encode(
            objectType: ProductionSecureSessionCryptoContract.encryptedRecordObjectType,
            fields: prefixFields
        )
    }

    fileprivate static func canonicalPrefix(
        sessionId: String,
        senderRole: P2PNATRole,
        epoch: UInt32,
        sequence: UInt64,
        contentType: ProductionSecureSessionContentType
    ) -> Data {
        ProductionC1InternalBridge.encode(
            objectType: ProductionSecureSessionCryptoContract.encryptedRecordObjectType,
            fields: productionCryptoRecordPrefixFields(
                sessionId: sessionId,
                senderRole: senderRole,
                epoch: epoch,
                sequence: sequence,
                contentType: contentType
            )
        )
    }

    private var prefixFields: [Data] {
        productionCryptoRecordPrefixFields(
            sessionId: sessionId,
            senderRole: senderRole,
            epoch: epoch,
            sequence: sequence,
            contentType: contentType
        )
    }
}

public enum ProductionSecureSessionOpenedContent: Equatable, Sendable {
    case application(Data)
    case keyUpdate(nextEpoch: UInt32)
}

private final class ProductionSecureSessionSensitiveByteStorage:
    @unchecked Sendable
{
    private let lock = NSLock()
    private let pointer: UnsafeMutableRawPointer
    private let count: Int
    private var discarded = false

    init(copying source: Data) {
        count = source.count
        let allocation = UnsafeMutableRawPointer.allocate(
            byteCount: max(source.count, 1),
            alignment: MemoryLayout<UInt8>.alignment
        )
        allocation.initializeMemory(
            as: UInt8.self,
            repeating: 0,
            count: max(source.count, 1)
        )
        if !source.isEmpty {
            source.copyBytes(
                to: allocation.assumingMemoryBound(to: UInt8.self),
                count: source.count
            )
        }
        pointer = allocation
    }

    deinit {
        productionSecureSessionWipe(pointer, count: count)
        pointer.deallocate()
    }

    /// Returns a normal zero-based value snapshot while serializing reads with
    /// discard, so callers can never observe a partially wiped buffer.
    func snapshot() -> Data {
        lock.lock()
        defer { lock.unlock() }
        return Data(bytes: pointer, count: count)
    }

    /// Wipes the owned raw allocation directly. This is intentionally not a
    /// mutation of a Data snapshot, which would only affect that value copy.
    func discard() {
        lock.lock()
        defer { lock.unlock() }
        guard !discarded else { return }
        productionSecureSessionWipe(pointer, count: count)
        discarded = true
    }
}

private final class ProductionSecureSessionSealSensitiveStorage:
    @unchecked Sendable
{
    private let lock = NSLock()
    private let ciphertext: ProductionSecureSessionSensitiveByteStorage
    private let tag: ProductionSecureSessionSensitiveByteStorage

    init(ciphertext: Data, tag: Data) {
        self.ciphertext = ProductionSecureSessionSensitiveByteStorage(
            copying: ciphertext
        )
        self.tag = ProductionSecureSessionSensitiveByteStorage(copying: tag)
    }

    func snapshot() -> (ciphertext: Data, tag: Data) {
        lock.lock()
        defer { lock.unlock() }
        return (ciphertext.snapshot(), tag.snapshot())
    }

    func discard() {
        lock.lock()
        defer { lock.unlock() }
        ciphertext.discard()
        tag.discard()
    }
}

@inline(never)
private func productionSecureSessionWipe(
    _ pointer: UnsafeMutableRawPointer,
    count: Int
) {
    guard count > 0 else { return }
    for offset in 0..<count {
        pointer.storeBytes(of: UInt8.zero, toByteOffset: offset, as: UInt8.self)
    }
}

public struct ProductionSecureSessionSealResult: Equatable, Sendable {
    public var record: ProductionSecureSessionEncryptedRecord {
        let sensitiveBytes = sensitiveStorage.snapshot()
        return ProductionSecureSessionEncryptedRecord(
            trustedSessionId: sessionId,
            senderRole: senderRole,
            epoch: epoch,
            sequence: sequence,
            contentType: contentType,
            ciphertext: sensitiveBytes.ciphertext,
            tag: sensitiveBytes.tag
        )
    }
    public let keyUpdateRequired: Bool
    public let terminalAfterRecord: Bool

    private let sessionId: String
    private let senderRole: P2PNATRole
    private let epoch: UInt32
    private let sequence: UInt64
    private let contentType: ProductionSecureSessionContentType
    private let sensitiveStorage: ProductionSecureSessionSealSensitiveStorage

    fileprivate init(
        record: ProductionSecureSessionEncryptedRecord,
        keyUpdateRequired: Bool,
        terminalAfterRecord: Bool
    ) {
        sensitiveStorage = ProductionSecureSessionSealSensitiveStorage(
            ciphertext: record.ciphertext,
            tag: record.tag
        )
        sessionId = record.sessionId
        senderRole = record.senderRole
        epoch = record.epoch
        sequence = record.sequence
        contentType = record.contentType
        self.keyUpdateRequired = keyUpdateRequired
        self.terminalAfterRecord = terminalAfterRecord
    }

    public static func == (
        lhs: ProductionSecureSessionSealResult,
        rhs: ProductionSecureSessionSealResult
    ) -> Bool {
        lhs.record == rhs.record
            && lhs.keyUpdateRequired == rhs.keyUpdateRequired
            && lhs.terminalAfterRecord == rhs.terminalAfterRecord
    }

    /// SPI for an authority-lifecycle wrapper that must suppress a produced
    /// result. No key material or general-purpose raw-storage handle escapes.
    @_spi(AuthorityLifecycle)
    public mutating func discardSuppressedResultBytes() {
        sensitiveStorage.discard()
    }
}

public struct ProductionSecureSessionOpenResult: Equatable, Sendable {
    public var plaintext: Data { plaintextStorage.snapshot() }
    public let contentType: ProductionSecureSessionContentType
    public let keyUpdateRequired: Bool
    public let terminalAfterRecord: Bool

    private let plaintextStorage: ProductionSecureSessionSensitiveByteStorage

    public var openedContent: ProductionSecureSessionOpenedContent {
        switch contentType {
        case .application:
            .application(plaintext)
        case .keyUpdate:
            .keyUpdate(nextEpoch: plaintext.reduce(UInt32.zero) { ($0 << 8) | UInt32($1) })
        }
    }

    fileprivate init(
        plaintext: Data,
        contentType: ProductionSecureSessionContentType,
        keyUpdateRequired: Bool,
        terminalAfterRecord: Bool
    ) {
        let plaintextStorage = ProductionSecureSessionSensitiveByteStorage(
            copying: plaintext
        )
        self.plaintextStorage = plaintextStorage
        self.contentType = contentType
        self.keyUpdateRequired = keyUpdateRequired
        self.terminalAfterRecord = terminalAfterRecord
    }

    public static func == (
        lhs: ProductionSecureSessionOpenResult,
        rhs: ProductionSecureSessionOpenResult
    ) -> Bool {
        lhs.plaintext == rhs.plaintext
            && lhs.contentType == rhs.contentType
            && lhs.keyUpdateRequired == rhs.keyUpdateRequired
            && lhs.terminalAfterRecord == rhs.terminalAfterRecord
    }

    /// SPI for an authority-lifecycle wrapper that must suppress a produced
    /// result. It exposes neither traffic keys nor a reusable byte handle.
    @_spi(AuthorityLifecycle)
    public mutating func discardSuppressedResultBytes() {
        plaintextStorage.discard()
    }
}

public enum ProductionSecureSessionCrypto {
    /// Returns the domain-separated object-7/object-26 digest that is bound
    /// into the production secure-session KDF. This is intentionally narrower
    /// than exposing derived material and is not the endpoint token digest.
    @_spi(AuthorityLifecycle)
    public static func exactBindingDigestHex(
        _ binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding
    ) throws -> String {
        let transcriptBytes = binding.transcript.canonicalBytes()
        let grantBytes: Data
        do {
            grantBytes = try binding.grantAuthorization.authorization.canonicalBytes()
        } catch {
            throw ProductionSecureSessionCryptoError.invalidBinding
        }
        return productionSecureSessionBindingDigest(
            transcriptBytes: transcriptBytes,
            grantBytes: grantBytes
        ).map { String(format: "%02x", $0) }.joined()
    }

    public static func deriveHandshake(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        nowMs: UInt64
    ) throws -> ProductionSecureSessionHandshake {
        var material = try deriveMaterial(
            binding: binding,
            localEphemeralKey: localEphemeralKey,
            nowMs: nowMs
        )
        defer { material.wipeSecrets() }
        return ProductionSecureSessionHandshake(
            state: ProductionSecureSessionState(material: material, nowMs: nowMs)
        )
    }

    #if DEBUG
    // Test-vector exporter. Secret material is absent from optimized release builds.
    static func vectorMaterial(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        nowMs: UInt64
    ) throws -> ProductionSecureSessionVectorMaterial {
        var material = try deriveMaterial(
            binding: binding,
            localEphemeralKey: localEphemeralKey,
            nowMs: nowMs
        )
        defer { material.wipeSecrets() }
        return ProductionSecureSessionVectorMaterial(material: material)
    }
    #endif

    private static func deriveMaterial(
        binding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        localEphemeralKey: P2PNATSessionEphemeralKey,
        nowMs: UInt64
    ) throws -> ProductionSecureSessionDerivedMaterial {
        let transcript = binding.transcript
        let authorization = binding.grantAuthorization.authorization
        let transcriptBytes = transcript.canonicalBytes()
        let grantBytes: Data
        do {
            grantBytes = try authorization.canonicalBytes()
        } catch {
            throw ProductionSecureSessionCryptoError.invalidBinding
        }
        let freshGrantDigest = ProductionC1InternalBridge.digestHex(grantBytes)
        let expectedContext: ProductionC1PreauthorizationSessionContext
        do {
            expectedContext = try ProductionC1PreauthorizationSessionContext(
                transcript: transcript
            )
        } catch {
            throw ProductionSecureSessionCryptoError.invalidBinding
        }
        guard binding.securityContext == expectedContext,
              authorization.securityContextDigest == expectedContext.digestHex(),
              transcript.routeKind == .p2pDirect,
              transcript.routeAuthDigest == freshGrantDigest,
              binding.grantAuthorization.digestHex == freshGrantDigest,
              transcript.sessionId == authorization.sessionId,
              transcript.pairBindingDigest == authorization.pairBindingDigest,
              transcript.pairEpoch == authorization.pairEpoch,
              transcript.generation == authorization.generation,
              transcript.clientIdentityFingerprint == authorization.clientIdentityFingerprint,
              transcript.runtimeIdentityFingerprint == authorization.runtimeIdentityFingerprint,
              binding.localRole == authorization.initiatorRole
                || binding.localRole == authorization.connectorTargetRole else {
            throw ProductionSecureSessionCryptoError.invalidBinding
        }
        guard nowMs >= authorization.effectiveNotBeforeMs else {
            throw ProductionSecureSessionCryptoError.notYetValid
        }
        guard nowMs < authorization.expiresAtMs else {
            throw ProductionSecureSessionCryptoError.expired
        }

        let expectedLocalKey = binding.localRole == .client
            ? transcript.clientEphemeralPublicKey
            : transcript.runtimeEphemeralPublicKey
        guard localEphemeralKey.publicKeyX963 == expectedLocalKey else {
            throw ProductionSecureSessionCryptoError.roleMismatch
        }
        var sharedSecret: Data
        do {
            sharedSecret = try localEphemeralKey.productionSharedSecret(binding: binding)
        } catch P2PNATSessionCryptoError.ephemeralKeyAlreadyUsed {
            throw ProductionSecureSessionCryptoError.ephemeralKeyAlreadyUsed
        } catch P2PNATSessionCryptoError.ephemeralKeyClosed {
            throw ProductionSecureSessionCryptoError.ephemeralKeyClosed
        } catch P2PNATSessionCryptoError.roleMismatch {
            throw ProductionSecureSessionCryptoError.roleMismatch
        } catch {
            throw ProductionSecureSessionCryptoError.invalidKey
        }
        defer { sharedSecret.productionCryptoWipe() }
        guard sharedSecret.count == 32,
              sharedSecret.contains(where: { $0 != 0 }) else {
            throw ProductionSecureSessionCryptoError.invalidKey
        }

        let bindingDigest = productionSecureSessionBindingDigest(
            transcriptBytes: transcriptBytes,
            grantBytes: grantBytes
        )
        var prk = productionCryptoHMAC(key: bindingDigest, data: sharedSecret)
        defer { prk.productionCryptoWipe() }
        let rootInfo = ProductionC1InternalBridge.transcript(
            domain: "AetherLink production secure-session HKDF root v1",
            claims: bindingDigest
        )
        var root = productionCryptoHKDFExpand(prk: prk, info: rootInfo, outputByteCount: 128)
        defer { root.productionCryptoWipe() }
        #if DEBUG
        return ProductionSecureSessionDerivedMaterial(
            localRole: binding.localRole,
            sessionId: transcript.sessionId,
            transcriptDigestHex: ProductionC1InternalBridge.digestHex(transcriptBytes),
            grantAuthorizationDigestHex: freshGrantDigest,
            bindingDigest: bindingDigest,
            sharedSecret: sharedSecret,
            prk: prk,
            rootInfo: rootInfo,
            clientConfirmationKey: root.subdata(in: 0..<32),
            runtimeConfirmationKey: root.subdata(in: 32..<64),
            clientEpochSecret: root.subdata(in: 64..<96),
            runtimeEpochSecret: root.subdata(in: 96..<128),
            effectiveNotBeforeMs: authorization.effectiveNotBeforeMs,
            expiresAtMs: authorization.expiresAtMs
        )
        #else
        return ProductionSecureSessionDerivedMaterial(
            localRole: binding.localRole,
            sessionId: transcript.sessionId,
            transcriptDigestHex: ProductionC1InternalBridge.digestHex(transcriptBytes),
            grantAuthorizationDigestHex: freshGrantDigest,
            bindingDigest: bindingDigest,
            clientConfirmationKey: root.subdata(in: 0..<32),
            runtimeConfirmationKey: root.subdata(in: 32..<64),
            clientEpochSecret: root.subdata(in: 64..<96),
            runtimeEpochSecret: root.subdata(in: 96..<128),
            effectiveNotBeforeMs: authorization.effectiveNotBeforeMs,
            expiresAtMs: authorization.expiresAtMs
        )
        #endif
    }
}

private func productionSecureSessionBindingDigest(
    transcriptBytes: Data,
    grantBytes: Data
) -> Data {
    var bindingClaims = ProductionC1InternalBridge.be(UInt32(transcriptBytes.count))
    bindingClaims.append(transcriptBytes)
    bindingClaims.append(ProductionC1InternalBridge.be(UInt32(grantBytes.count)))
    bindingClaims.append(grantBytes)
    return Data(SHA256.hash(data: ProductionC1InternalBridge.transcript(
        domain: "AetherLink production secure-session object7+object26 binding v1",
        claims: bindingClaims
    )))
}

public final class ProductionSecureSessionHandshake: @unchecked Sendable {
    private let state: ProductionSecureSessionState

    fileprivate init(state: ProductionSecureSessionState) {
        self.state = state
    }

    public var localRole: P2PNATRole { state.localRole }

    public func localConfirmation(nowMs: UInt64) throws -> Data {
        try state.localConfirmation(nowMs: nowMs)
    }

    public func markLocalConfirmationSent(
        _ canonicalConfirmation: Data,
        nowMs: UInt64
    ) throws {
        try state.markLocalConfirmationSent(canonicalConfirmation, nowMs: nowMs)
    }

    public func acceptPeerConfirmation(
        _ canonicalConfirmation: Data,
        nowMs: UInt64
    ) throws {
        try state.acceptPeerConfirmation(canonicalConfirmation, nowMs: nowMs)
    }

    public func makeCipher(nowMs: UInt64) throws -> ProductionSecureSessionCipher {
        try state.activate(nowMs: nowMs)
        return ProductionSecureSessionCipher(state: state)
    }

    public func invalidate() {
        state.close()
    }
}

public final class ProductionSecureSessionCipher: @unchecked Sendable {
    private let state: ProductionSecureSessionState

    fileprivate init(state: ProductionSecureSessionState) {
        self.state = state
    }

    public func sealApplication(
        _ plaintext: Data,
        nowMs: UInt64
    ) throws -> ProductionSecureSessionSealResult {
        try state.sealApplication(plaintext, nowMs: nowMs)
    }

    public func sealKeyUpdate(
        nowMs: UInt64
    ) throws -> ProductionSecureSessionSealResult {
        try state.sealKeyUpdate(nowMs: nowMs)
    }

    public func open(
        _ record: ProductionSecureSessionEncryptedRecord,
        nowMs: UInt64
    ) throws -> ProductionSecureSessionOpenResult {
        try state.open(record, nowMs: nowMs)
    }

    public func open(
        canonicalRecord: Data,
        nowMs: UInt64
    ) throws -> ProductionSecureSessionOpenResult {
        let record = try ProductionSecureSessionEncryptedRecord(canonicalBytes: canonicalRecord)
        return try state.open(record, nowMs: nowMs)
    }

    public func close() {
        state.close()
    }
}

private struct ProductionSecureSessionDerivedMaterial {
    let localRole: P2PNATRole
    let sessionId: String
    let transcriptDigestHex: String
    let grantAuthorizationDigestHex: String
    let bindingDigest: Data
    #if DEBUG
    var sharedSecret: Data
    var prk: Data
    let rootInfo: Data
    #endif
    var clientConfirmationKey: Data
    var runtimeConfirmationKey: Data
    var clientEpochSecret: Data
    var runtimeEpochSecret: Data
    let effectiveNotBeforeMs: UInt64
    let expiresAtMs: UInt64

    mutating func wipeSecrets() {
        #if DEBUG
        sharedSecret.productionCryptoWipe()
        prk.productionCryptoWipe()
        #endif
        clientConfirmationKey.productionCryptoWipe()
        runtimeConfirmationKey.productionCryptoWipe()
        clientEpochSecret.productionCryptoWipe()
        runtimeEpochSecret.productionCryptoWipe()
    }
}

#if DEBUG
struct ProductionSecureSessionVectorMaterial {
    let sharedSecret: Data
    let bindingDigest: Data
    let prk: Data
    let rootInfo: Data
    let rootOutput: Data
    let clientConfirmationKey: Data
    let runtimeConfirmationKey: Data
    let clientEpoch0Secret: Data
    let runtimeEpoch0Secret: Data

    fileprivate init(material: ProductionSecureSessionDerivedMaterial) {
        sharedSecret = material.sharedSecret
        bindingDigest = material.bindingDigest
        prk = material.prk
        rootInfo = material.rootInfo
        clientConfirmationKey = material.clientConfirmationKey
        runtimeConfirmationKey = material.runtimeConfirmationKey
        clientEpoch0Secret = material.clientEpochSecret
        runtimeEpoch0Secret = material.runtimeEpochSecret
        rootOutput = material.clientConfirmationKey
            + material.runtimeConfirmationKey
            + material.clientEpochSecret
            + material.runtimeEpochSecret
    }
}
#endif

private final class ProductionSecureSessionDirectionState {
    let role: P2PNATRole
    var epoch: UInt32 = 0
    var sequence: UInt64 = 0
    var epochRecords: UInt64 = 0
    var epochBytes: UInt64 = 0
    var sessionRecords: UInt64 = 0
    var sessionBytes: UInt64 = 0
    var epochSecret: Data
    var isTerminal = false

    init(role: P2PNATRole, epochSecret: Data) {
        self.role = role
        self.epochSecret = epochSecret
    }

    func wipe() {
        isTerminal = true
        epochSecret.productionCryptoWipe()
        epochSecret.removeAll(keepingCapacity: false)
    }
}

struct ProductionSecureSessionCounterSnapshot: Equatable, Sendable {
    let epoch: UInt32
    let sequence: UInt64
    let epochRecords: UInt64
    let epochBytes: UInt64
    let sessionRecords: UInt64
    let sessionBytes: UInt64
    let isTerminal: Bool
}

struct ProductionSecureSessionCapacityDecision: Equatable, Sendable {
    let keyUpdateRequired: Bool
    let terminalAfterRecord: Bool
}

struct ProductionSecureSessionKeyUpdateCapacityDecision: Equatable, Sendable {
    let nextEpoch: UInt32
    let terminalAfterRecord: Bool
}

enum ProductionSecureSessionCapacityOracle {
    static func application(
        snapshot: ProductionSecureSessionCounterSnapshot,
        byteCount: UInt64
    ) throws -> ProductionSecureSessionCapacityDecision {
        let limits = ProductionSecureSessionCryptoContract.self
        try validate(snapshot)
        guard !snapshot.isTerminal else {
            throw ProductionSecureSessionCryptoError.recordLimitExceeded
        }
        guard byteCount <= UInt64(limits.maximumPlaintextBytes) else {
            throw ProductionSecureSessionCryptoError.byteLimitExceeded
        }
        let nextEpochRecords = snapshot.epochRecords + 1
        let nextEpochBytes = snapshot.epochBytes + byteCount
        let nextSessionRecords = snapshot.sessionRecords + 1
        let nextSessionBytes = snapshot.sessionBytes + byteCount
        guard nextSessionRecords <= limits.maximumRecordsPerSession,
              nextSessionBytes <= limits.maximumPlaintextBytesPerSession else {
            throw ProductionSecureSessionCryptoError.sessionLimitExceeded
        }
        if snapshot.epoch < limits.maximumEpoch {
            guard nextEpochRecords <= limits.maximumRecordsPerEpoch - 1,
                  nextEpochBytes <= limits.maximumPlaintextBytesPerEpoch - 4 else {
                throw ProductionSecureSessionCryptoError.keyUpdateRequired
            }
            return ProductionSecureSessionCapacityDecision(
                keyUpdateRequired:
                    nextEpochRecords == limits.maximumRecordsPerEpoch - 1
                    || nextEpochBytes == limits.maximumPlaintextBytesPerEpoch - 4,
                terminalAfterRecord:
                    nextSessionRecords == limits.maximumRecordsPerSession
                    || nextSessionBytes == limits.maximumPlaintextBytesPerSession
            )
        }
        guard nextEpochRecords <= limits.maximumRecordsPerEpoch else {
            throw ProductionSecureSessionCryptoError.recordLimitExceeded
        }
        guard nextEpochBytes <= limits.maximumPlaintextBytesPerEpoch else {
            throw ProductionSecureSessionCryptoError.byteLimitExceeded
        }
        return ProductionSecureSessionCapacityDecision(
            keyUpdateRequired: false,
            terminalAfterRecord:
                nextEpochRecords == limits.maximumRecordsPerEpoch
                || nextEpochBytes == limits.maximumPlaintextBytesPerEpoch
                || nextSessionRecords == limits.maximumRecordsPerSession
                || nextSessionBytes == limits.maximumPlaintextBytesPerSession
        )
    }

    static func keyUpdateNextEpoch(
        snapshot: ProductionSecureSessionCounterSnapshot
    ) throws -> UInt32 {
        try keyUpdate(snapshot: snapshot).nextEpoch
    }

    static func keyUpdate(
        snapshot: ProductionSecureSessionCounterSnapshot
    ) throws -> ProductionSecureSessionKeyUpdateCapacityDecision {
        let limits = ProductionSecureSessionCryptoContract.self
        try validate(snapshot)
        guard !snapshot.isTerminal,
              snapshot.epoch < limits.maximumEpoch else {
            throw ProductionSecureSessionCryptoError.recordLimitExceeded
        }
        guard snapshot.epochRecords + 1 <= limits.maximumRecordsPerEpoch,
              snapshot.epochBytes + 4 <= limits.maximumPlaintextBytesPerEpoch else {
            throw ProductionSecureSessionCryptoError.recordLimitExceeded
        }
        guard snapshot.sessionRecords + 1 <= limits.maximumRecordsPerSession,
              snapshot.sessionBytes + 4 <= limits.maximumPlaintextBytesPerSession else {
            throw ProductionSecureSessionCryptoError.sessionLimitExceeded
        }
        return ProductionSecureSessionKeyUpdateCapacityDecision(
            nextEpoch: snapshot.epoch + 1,
            terminalAfterRecord:
                snapshot.sessionRecords + 1 == limits.maximumRecordsPerSession
                || snapshot.sessionBytes + 4 == limits.maximumPlaintextBytesPerSession
        )
    }

    private static func validate(_ snapshot: ProductionSecureSessionCounterSnapshot) throws {
        let limits = ProductionSecureSessionCryptoContract.self
        guard snapshot.epoch <= limits.maximumEpoch,
              snapshot.sequence == snapshot.epochRecords,
              snapshot.epochRecords <= limits.maximumRecordsPerEpoch,
              snapshot.epochBytes <= limits.maximumPlaintextBytesPerEpoch,
              snapshot.sessionRecords <= limits.maximumRecordsPerSession,
              snapshot.sessionBytes <= limits.maximumPlaintextBytesPerSession else {
            throw ProductionSecureSessionCryptoError.invalidContent
        }
    }
}

private final class ProductionSecureSessionState: @unchecked Sendable {
    let localRole: P2PNATRole
    private let peerRole: P2PNATRole
    private let sessionId: String
    private let transcriptDigestHex: String
    private let grantAuthorizationDigestHex: String
    private let bindingDigest: Data
    private let effectiveNotBeforeMs: UInt64
    private let expiresAtMs: UInt64
    private let lock = NSLock()

    private var clientConfirmationKey: Data
    private var runtimeConfirmationKey: Data
    private var clientEpochSecret: Data
    private var runtimeEpochSecret: Data
    private var lastObservedTimeMs: UInt64
    private var localConfirmationBytes: Data?
    private var localConfirmationSent: Data?
    private var peerConfirmationAccepted: Data?
    private var cipherIssued = false
    private var sendState: ProductionSecureSessionDirectionState?
    private var receiveState: ProductionSecureSessionDirectionState?
    private var isClosed = false

    init(material: ProductionSecureSessionDerivedMaterial, nowMs: UInt64) {
        localRole = material.localRole
        peerRole = material.localRole == .client ? .runtime : .client
        sessionId = material.sessionId
        transcriptDigestHex = material.transcriptDigestHex
        grantAuthorizationDigestHex = material.grantAuthorizationDigestHex
        bindingDigest = material.bindingDigest
        effectiveNotBeforeMs = material.effectiveNotBeforeMs
        expiresAtMs = material.expiresAtMs
        clientConfirmationKey = material.clientConfirmationKey
        runtimeConfirmationKey = material.runtimeConfirmationKey
        clientEpochSecret = material.clientEpochSecret
        runtimeEpochSecret = material.runtimeEpochSecret
        lastObservedTimeMs = nowMs
    }

    deinit {
        lock.lock()
        terminateLocked()
        lock.unlock()
    }

    func localConfirmation(nowMs: UInt64) throws -> Data {
        lock.lock()
        defer { lock.unlock() }
        try validateTimeLocked(nowMs)
        guard !cipherIssued else {
            throw ProductionSecureSessionCryptoError.cipherAlreadyCreated
        }
        if let localConfirmationBytes { return localConfirmationBytes }
        let confirmation = try makeConfirmationLocked(role: localRole)
        let bytes = confirmation.canonicalBytes()
        localConfirmationBytes = bytes
        return bytes
    }

    func markLocalConfirmationSent(_ bytes: Data, nowMs: UInt64) throws {
        lock.lock()
        defer { lock.unlock() }
        try validateTimeLocked(nowMs)
        guard !cipherIssued else {
            throw ProductionSecureSessionCryptoError.cipherAlreadyCreated
        }
        let expected: Data
        if let localConfirmationBytes {
            expected = localConfirmationBytes
        } else {
            let confirmation = try makeConfirmationLocked(role: localRole)
            expected = confirmation.canonicalBytes()
            localConfirmationBytes = expected
        }
        guard productionCryptoConstantTimeEqual(expected, bytes) else {
            let error: ProductionSecureSessionCryptoError = localConfirmationSent == nil
                ? .invalidConfirmation
                : .confirmationConflict
            terminateLocked()
            throw error
        }
        if let sent = localConfirmationSent {
            guard productionCryptoConstantTimeEqual(sent, bytes) else {
                terminateLocked()
                throw ProductionSecureSessionCryptoError.confirmationConflict
            }
            return
        }
        localConfirmationSent = bytes
    }

    func acceptPeerConfirmation(_ bytes: Data, nowMs: UInt64) throws {
        lock.lock()
        defer { lock.unlock() }
        try validateTimeLocked(nowMs)
        guard !cipherIssued else {
            throw ProductionSecureSessionCryptoError.cipherAlreadyCreated
        }
        if let accepted = peerConfirmationAccepted {
            guard productionCryptoConstantTimeEqual(accepted, bytes) else {
                terminateLocked()
                throw ProductionSecureSessionCryptoError.confirmationConflict
            }
            return
        }
        let decoded: ProductionSecureSessionKeyConfirmation
        do {
            decoded = try ProductionSecureSessionKeyConfirmation(canonicalBytes: bytes)
        } catch {
            terminateLocked()
            throw ProductionSecureSessionCryptoError.invalidConfirmation
        }
        guard decoded.confirmingRole == peerRole,
              decoded.sessionId == sessionId,
              decoded.transcriptDigestHex == transcriptDigestHex,
              decoded.grantAuthorizationDigestHex == grantAuthorizationDigestHex else {
            terminateLocked()
            throw ProductionSecureSessionCryptoError.invalidConfirmation
        }
        let expected = try makeConfirmationLocked(role: peerRole).canonicalBytes()
        guard productionCryptoConstantTimeEqual(expected, bytes) else {
            terminateLocked()
            throw ProductionSecureSessionCryptoError.invalidConfirmation
        }
        peerConfirmationAccepted = bytes
    }

    func activate(nowMs: UInt64) throws {
        lock.lock()
        defer { lock.unlock() }
        try validateTimeLocked(nowMs)
        guard localConfirmationSent != nil, peerConfirmationAccepted != nil else {
            throw ProductionSecureSessionCryptoError.confirmationIncomplete
        }
        guard !cipherIssued else {
            throw ProductionSecureSessionCryptoError.cipherAlreadyCreated
        }
        let localSecret = localRole == .client ? clientEpochSecret : runtimeEpochSecret
        let peerSecret = peerRole == .client ? clientEpochSecret : runtimeEpochSecret
        sendState = ProductionSecureSessionDirectionState(
            role: localRole,
            epochSecret: localSecret
        )
        receiveState = ProductionSecureSessionDirectionState(
            role: peerRole,
            epochSecret: peerSecret
        )
        clientConfirmationKey.productionCryptoWipe()
        runtimeConfirmationKey.productionCryptoWipe()
        clientConfirmationKey.removeAll(keepingCapacity: false)
        runtimeConfirmationKey.removeAll(keepingCapacity: false)
        clientEpochSecret.productionCryptoWipe()
        runtimeEpochSecret.productionCryptoWipe()
        clientEpochSecret.removeAll(keepingCapacity: false)
        runtimeEpochSecret.removeAll(keepingCapacity: false)
        cipherIssued = true
    }

    func sealApplication(
        _ plaintext: Data,
        nowMs: UInt64
    ) throws -> ProductionSecureSessionSealResult {
        lock.lock()
        defer { lock.unlock() }
        try validateTimeLocked(nowMs)
        guard plaintext.count <= ProductionSecureSessionCryptoContract.maximumPlaintextBytes else {
            throw ProductionSecureSessionCryptoError.byteLimitExceeded
        }
        guard let direction = sendState, cipherIssued else {
            throw ProductionSecureSessionCryptoError.confirmationIncomplete
        }
        let capacity = try requireApplicationCapacityLocked(
            direction: direction,
            byteCount: UInt64(plaintext.count)
        )
        let record = try sealLocked(
            plaintext,
            contentType: .application,
            direction: direction
        )
        commitApplicationLocked(
            direction,
            byteCount: UInt64(plaintext.count),
            capacity: capacity
        )
        return ProductionSecureSessionSealResult(
            record: record,
            keyUpdateRequired: capacity.keyUpdateRequired,
            terminalAfterRecord: capacity.terminalAfterRecord
        )
    }

    func sealKeyUpdate(nowMs: UInt64) throws -> ProductionSecureSessionSealResult {
        lock.lock()
        defer { lock.unlock() }
        try validateTimeLocked(nowMs)
        guard let direction = sendState, cipherIssued else {
            throw ProductionSecureSessionCryptoError.confirmationIncomplete
        }
        let capacity = try requireKeyUpdateCapacityLocked(direction: direction)
        let plaintext = ProductionC1InternalBridge.be(capacity.nextEpoch)
        let nextSecret = productionCryptoNextEpochSecret(
            current: direction.epochSecret,
            bindingDigest: bindingDigest,
            role: direction.role,
            nextEpoch: capacity.nextEpoch
        )
        let record = try sealLocked(
            plaintext,
            contentType: .keyUpdate,
            direction: direction
        )
        commitKeyUpdateLocked(direction, capacity: capacity, nextSecret: nextSecret)
        return ProductionSecureSessionSealResult(
            record: record,
            keyUpdateRequired: false,
            terminalAfterRecord: capacity.terminalAfterRecord
        )
    }

    func open(
        _ record: ProductionSecureSessionEncryptedRecord,
        nowMs: UInt64
    ) throws -> ProductionSecureSessionOpenResult {
        lock.lock()
        defer { lock.unlock() }
        try validateTimeLocked(nowMs)
        guard let direction = receiveState, cipherIssued else {
            throw ProductionSecureSessionCryptoError.confirmationIncomplete
        }
        guard record.sessionId == sessionId,
              record.senderRole == direction.role,
              record.epoch == direction.epoch,
              record.sequence == direction.sequence else {
            throw ProductionSecureSessionCryptoError.unexpectedRecord
        }
        let applicationCapacity: ProductionSecureSessionCapacityDecision?
        let keyUpdateCapacity: ProductionSecureSessionKeyUpdateCapacityDecision?
        switch record.contentType {
        case .application:
            applicationCapacity = try requireApplicationCapacityLocked(
                direction: direction,
                byteCount: UInt64(record.ciphertext.count)
            )
            keyUpdateCapacity = nil
        case .keyUpdate:
            applicationCapacity = nil
            keyUpdateCapacity = try requireKeyUpdateCapacityLocked(direction: direction)
        }
        let plaintext = try openLocked(record, direction: direction)
        guard plaintext.count <= ProductionSecureSessionCryptoContract.maximumPlaintextBytes else {
            throw ProductionSecureSessionCryptoError.byteLimitExceeded
        }
        switch record.contentType {
        case .application:
            let capacity = applicationCapacity!
            commitApplicationLocked(
                direction,
                byteCount: UInt64(plaintext.count),
                capacity: capacity
            )
            return ProductionSecureSessionOpenResult(
                plaintext: plaintext,
                contentType: .application,
                keyUpdateRequired: capacity.keyUpdateRequired,
                terminalAfterRecord: capacity.terminalAfterRecord
            )
        case .keyUpdate:
            let capacity = keyUpdateCapacity!
            guard plaintext == ProductionC1InternalBridge.be(capacity.nextEpoch) else {
                throw ProductionSecureSessionCryptoError.invalidKeyUpdate
            }
            let nextSecret = productionCryptoNextEpochSecret(
                current: direction.epochSecret,
                bindingDigest: bindingDigest,
                role: direction.role,
                nextEpoch: capacity.nextEpoch
            )
            commitKeyUpdateLocked(direction, capacity: capacity, nextSecret: nextSecret)
            return ProductionSecureSessionOpenResult(
                plaintext: plaintext,
                contentType: .keyUpdate,
                keyUpdateRequired: false,
                terminalAfterRecord: capacity.terminalAfterRecord
            )
        }
    }

    func close() {
        lock.lock()
        defer { lock.unlock() }
        terminateLocked()
    }

    private func makeConfirmationLocked(
        role: P2PNATRole
    ) throws -> ProductionSecureSessionKeyConfirmation {
        let key = role == .client ? clientConfirmationKey : runtimeConfirmationKey
        guard key.count == 32 else { throw ProductionSecureSessionCryptoError.closed }
        let emptyProof = Data(repeating: 0, count: 32)
        let prefix = try ProductionSecureSessionKeyConfirmation(
            sessionId: sessionId,
            transcriptDigestHex: transcriptDigestHex,
            grantAuthorizationDigestHex: grantAuthorizationDigestHex,
            confirmingRole: role,
            proof: emptyProof
        ).canonicalPrefix
        let proof = productionCryptoHMAC(
            key: key,
            data: ProductionC1InternalBridge.transcript(
                domain: "AetherLink production secure-session key confirmation v1",
                claims: prefix
            )
        )
        return try ProductionSecureSessionKeyConfirmation(
            sessionId: sessionId,
            transcriptDigestHex: transcriptDigestHex,
            grantAuthorizationDigestHex: grantAuthorizationDigestHex,
            confirmingRole: role,
            proof: proof
        )
    }

    private func sealLocked(
        _ plaintext: Data,
        contentType: ProductionSecureSessionContentType,
        direction: ProductionSecureSessionDirectionState
    ) throws -> ProductionSecureSessionEncryptedRecord {
        var keyAndIV = productionCryptoTrafficKeyAndIV(
            epochSecret: direction.epochSecret,
            bindingDigest: bindingDigest,
            role: direction.role,
            epoch: direction.epoch
        )
        defer { keyAndIV.wipe() }
        let prefix = ProductionSecureSessionEncryptedRecord.canonicalPrefix(
            sessionId: sessionId,
            senderRole: direction.role,
            epoch: direction.epoch,
            sequence: direction.sequence,
            contentType: contentType
        )
        let aad = productionCryptoRecordAAD(
            bindingDigest: bindingDigest,
            prefix: prefix,
            ciphertextCount: plaintext.count
        )
        do {
            var nonceBytes = productionCryptoNonce(
                staticIV: keyAndIV.iv,
                sequence: direction.sequence
            )
            defer { nonceBytes.productionCryptoWipe() }
            let nonce = try AES.GCM.Nonce(data: nonceBytes)
            let sealed = try AES.GCM.seal(
                plaintext,
                using: SymmetricKey(data: keyAndIV.key),
                nonce: nonce,
                authenticating: aad
            )
            return try ProductionSecureSessionEncryptedRecord(
                sessionId: sessionId,
                senderRole: direction.role,
                epoch: direction.epoch,
                sequence: direction.sequence,
                contentType: contentType,
                ciphertext: sealed.ciphertext,
                tag: sealed.tag
            )
        } catch {
            terminateLocked()
            throw ProductionSecureSessionCryptoError.sealFailed
        }
    }

    private func openLocked(
        _ record: ProductionSecureSessionEncryptedRecord,
        direction: ProductionSecureSessionDirectionState
    ) throws -> Data {
        var keyAndIV = productionCryptoTrafficKeyAndIV(
            epochSecret: direction.epochSecret,
            bindingDigest: bindingDigest,
            role: direction.role,
            epoch: direction.epoch
        )
        defer { keyAndIV.wipe() }
        let aad = productionCryptoRecordAAD(
            bindingDigest: bindingDigest,
            prefix: record.canonicalPrefix,
            ciphertextCount: record.ciphertext.count
        )
        do {
            var nonceBytes = productionCryptoNonce(
                staticIV: keyAndIV.iv,
                sequence: direction.sequence
            )
            defer { nonceBytes.productionCryptoWipe() }
            let nonce = try AES.GCM.Nonce(data: nonceBytes)
            let sealed = try AES.GCM.SealedBox(
                nonce: nonce,
                ciphertext: record.ciphertext,
                tag: record.tag
            )
            return try AES.GCM.open(
                sealed,
                using: SymmetricKey(data: keyAndIV.key),
                authenticating: aad
            )
        } catch {
            throw ProductionSecureSessionCryptoError.authenticationFailed
        }
    }

    private func requireApplicationCapacityLocked(
        direction: ProductionSecureSessionDirectionState,
        byteCount: UInt64
    ) throws -> ProductionSecureSessionCapacityDecision {
        try ProductionSecureSessionCapacityOracle.application(
            snapshot: snapshot(direction),
            byteCount: byteCount
        )
    }

    private func requireKeyUpdateCapacityLocked(
        direction: ProductionSecureSessionDirectionState
    ) throws -> ProductionSecureSessionKeyUpdateCapacityDecision {
        try ProductionSecureSessionCapacityOracle.keyUpdate(
            snapshot: snapshot(direction)
        )
    }

    private func commitApplicationLocked(
        _ direction: ProductionSecureSessionDirectionState,
        byteCount: UInt64,
        capacity: ProductionSecureSessionCapacityDecision
    ) {
        advanceCountersLocked(direction, byteCount: byteCount)
        if capacity.terminalAfterRecord {
            direction.wipe()
        }
    }

    private func commitKeyUpdateLocked(
        _ direction: ProductionSecureSessionDirectionState,
        capacity: ProductionSecureSessionKeyUpdateCapacityDecision,
        nextSecret: Data
    ) {
        advanceCountersLocked(direction, byteCount: 4)
        direction.epochSecret.productionCryptoWipe()
        direction.epochSecret = nextSecret
        direction.epoch = capacity.nextEpoch
        direction.sequence = 0
        direction.epochRecords = 0
        direction.epochBytes = 0
        if capacity.terminalAfterRecord {
            direction.wipe()
        }
    }

    private func advanceCountersLocked(
        _ direction: ProductionSecureSessionDirectionState,
        byteCount: UInt64
    ) {
        direction.sequence += 1
        direction.epochRecords += 1
        direction.epochBytes += byteCount
        direction.sessionRecords += 1
        direction.sessionBytes += byteCount
    }

    private func snapshot(
        _ direction: ProductionSecureSessionDirectionState
    ) -> ProductionSecureSessionCounterSnapshot {
        ProductionSecureSessionCounterSnapshot(
            epoch: direction.epoch,
            sequence: direction.sequence,
            epochRecords: direction.epochRecords,
            epochBytes: direction.epochBytes,
            sessionRecords: direction.sessionRecords,
            sessionBytes: direction.sessionBytes,
            isTerminal: direction.isTerminal
        )
    }

    private func validateTimeLocked(_ nowMs: UInt64) throws {
        guard !isClosed else { throw ProductionSecureSessionCryptoError.closed }
        guard nowMs >= lastObservedTimeMs else {
            terminateLocked()
            throw ProductionSecureSessionCryptoError.timeRegression
        }
        lastObservedTimeMs = nowMs
        guard nowMs >= effectiveNotBeforeMs else {
            terminateLocked()
            throw ProductionSecureSessionCryptoError.notYetValid
        }
        guard nowMs < expiresAtMs else {
            terminateLocked()
            throw ProductionSecureSessionCryptoError.expired
        }
    }

    private func terminateLocked() {
        guard !isClosed else { return }
        clientConfirmationKey.productionCryptoWipe()
        runtimeConfirmationKey.productionCryptoWipe()
        clientEpochSecret.productionCryptoWipe()
        runtimeEpochSecret.productionCryptoWipe()
        clientConfirmationKey.removeAll(keepingCapacity: false)
        runtimeConfirmationKey.removeAll(keepingCapacity: false)
        clientEpochSecret.removeAll(keepingCapacity: false)
        runtimeEpochSecret.removeAll(keepingCapacity: false)
        sendState?.wipe()
        sendState = nil
        receiveState?.wipe()
        receiveState = nil
        isClosed = true
    }
}

private func productionCryptoRecordPrefixFields(
    sessionId: String,
    senderRole: P2PNATRole,
    epoch: UInt32,
    sequence: UInt64,
    contentType: ProductionSecureSessionContentType
) -> [Data] {
    [
        ProductionC1InternalBridge.ascii(sessionId),
        Data([productionCryptoRoleByte(senderRole)]),
        ProductionC1InternalBridge.be(epoch),
        ProductionC1InternalBridge.be(sequence),
        Data([contentType.rawValue]),
    ]
}

private func productionCryptoRecordAAD(
    bindingDigest: Data,
    prefix: Data,
    ciphertextCount: Int
) -> Data {
    var claims = bindingDigest
    claims.append(ProductionC1InternalBridge.be(UInt32(prefix.count)))
    claims.append(prefix)
    claims.append(ProductionC1InternalBridge.be(UInt32(ciphertextCount)))
    return ProductionC1InternalBridge.transcript(
        domain: "AetherLink production secure-session record AAD v1",
        claims: claims
    )
}

private struct ProductionSecureSessionTrafficMaterial {
    var key: Data
    var iv: Data

    mutating func wipe() {
        // Best-effort for our mutable Data buffers; CryptoKit owns any copies
        // made while constructing SymmetricKey and AES.GCM.Nonce values.
        key.productionCryptoWipe()
        iv.productionCryptoWipe()
        key.removeAll(keepingCapacity: false)
        iv.removeAll(keepingCapacity: false)
    }
}

private func productionCryptoTrafficKeyAndIV(
    epochSecret: Data,
    bindingDigest: Data,
    role: P2PNATRole,
    epoch: UInt32
) -> ProductionSecureSessionTrafficMaterial {
    var epochContext = bindingDigest
    epochContext.append(productionCryptoRoleByte(role))
    epochContext.append(ProductionC1InternalBridge.be(epoch))
    return ProductionSecureSessionTrafficMaterial(
        key: productionCryptoHKDFExpand(
            prk: epochSecret,
            info: ProductionC1InternalBridge.transcript(
                domain: "AetherLink production secure-session traffic key v1",
                claims: epochContext
            ),
            outputByteCount: 32
        ),
        iv: productionCryptoHKDFExpand(
            prk: epochSecret,
            info: ProductionC1InternalBridge.transcript(
                domain: "AetherLink production secure-session traffic iv v1",
                claims: epochContext
            ),
            outputByteCount: 12
        )
    )
}

private func productionCryptoNextEpochSecret(
    current: Data,
    bindingDigest: Data,
    role: P2PNATRole,
    nextEpoch: UInt32
) -> Data {
    var epochContext = bindingDigest
    epochContext.append(productionCryptoRoleByte(role))
    epochContext.append(ProductionC1InternalBridge.be(nextEpoch))
    return productionCryptoHKDFExpand(
        prk: current,
        info: ProductionC1InternalBridge.transcript(
            domain: "AetherLink production secure-session traffic update v1",
            claims: epochContext
        ),
        outputByteCount: 32
    )
}

private func productionCryptoNonce(staticIV: Data, sequence: UInt64) -> Data {
    var nonce = staticIV
    let sequenceBytes = ProductionC1InternalBridge.be(sequence)
    for index in 0..<8 {
        nonce[nonce.startIndex + 4 + index] ^= sequenceBytes[sequenceBytes.startIndex + index]
    }
    return nonce
}

private func productionCryptoHKDFExpand(
    prk: Data,
    info: Data,
    outputByteCount: Int
) -> Data {
    precondition(outputByteCount > 0 && outputByteCount <= 255 * 32)
    var output = Data()
    var previous = Data()
    var counter: UInt8 = 1
    while output.count < outputByteCount {
        var input = previous
        input.append(info)
        input.append(counter)
        previous = productionCryptoHMAC(key: prk, data: input)
        output.append(previous)
        counter &+= 1
    }
    return output.prefix(outputByteCount)
}

private func productionCryptoHMAC(key: Data, data: Data) -> Data {
    Data(HMAC<SHA256>.authenticationCode(
        for: data,
        using: SymmetricKey(data: key)
    ))
}

private func productionCryptoRoleByte(_ role: P2PNATRole) -> UInt8 {
    role == .client ? 1 : 2
}

private func productionCryptoRole(byte: UInt8) -> P2PNATRole? {
    switch byte {
    case 1: .client
    case 2: .runtime
    default: nil
    }
}

private func productionCryptoText(_ data: Data) throws -> String {
    do {
        return try ProductionC1InternalBridge.text(data)
    } catch {
        throw ProductionSecureSessionCryptoError.invalidCanonical
    }
}

private func productionCryptoIsLowerHex(_ value: String) -> Bool {
    !value.isEmpty && value.utf8.allSatisfy {
        ($0 >= UInt8(ascii: "0") && $0 <= UInt8(ascii: "9"))
            || ($0 >= UInt8(ascii: "a") && $0 <= UInt8(ascii: "f"))
    }
}

private func productionCryptoIsDigestHex(_ value: String) -> Bool {
    value.utf8.count == 64 && productionCryptoIsLowerHex(value)
}

private func productionCryptoConstantTimeEqual(_ lhs: Data, _ rhs: Data) -> Bool {
    let left = [UInt8](lhs)
    let right = [UInt8](rhs)
    var difference = left.count ^ right.count
    for index in 0..<max(left.count, right.count) {
        difference |= Int(
            (index < left.count ? left[index] : 0)
                ^ (index < right.count ? right[index] : 0)
        )
    }
    return difference == 0
}

private extension Data {
    mutating func productionCryptoWipe() {
        resetBytes(in: startIndex..<endIndex)
    }
}
