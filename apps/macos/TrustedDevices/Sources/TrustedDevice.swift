import CryptoKit
import Darwin
import Foundation
import P2PNATContracts

@_silgen_name("flock")
private func systemFlock(_ descriptor: Int32, _ operation: Int32) -> Int32

private let trustedDeviceStoreLimitsUserInfoKey = CodingUserInfoKey(
    rawValue: "aetherlink.trusted-device-store-limits"
)!

public let trustedDeviceStoreMaxBytes = 1 * 1024 * 1024
public let trustedDeviceStoreMaxDevices = 256
public let trustedDeviceIdentifierMaxUTF8Bytes = 256
public let trustedDeviceNameMaxUTF8Bytes = 512
public let trustedDevicePublicKeyMaxUTF8Bytes = 4 * 1024

public struct TrustedDevice: Codable, Identifiable, Equatable, Sendable {
    public var id: String
    public var name: String
    public var publicKeyBase64: String
    public var pairedAt: Date
    public var productionPairState: ProductionPairStateSnapshot?
    var productionC1EndpointAdmissionState: StoredProductionC1EndpointAdmissionState?

    public init(
        id: String,
        name: String,
        publicKeyBase64: String,
        pairedAt: Date = Date()
    ) {
        self.init(
            id: id,
            name: name,
            publicKeyBase64: publicKeyBase64,
            pairedAt: pairedAt,
            productionPairState: nil,
            productionC1EndpointAdmissionState: nil
        )
    }

    public init(
        id: String,
        name: String,
        publicKeyBase64: String,
        pairedAt: Date = Date(),
        productionPairState: ProductionPairStateSnapshot?
    ) {
        self.init(
            id: id,
            name: name,
            publicKeyBase64: publicKeyBase64,
            pairedAt: pairedAt,
            productionPairState: productionPairState,
            productionC1EndpointAdmissionState: nil
        )
    }

    init(
        id: String,
        name: String,
        publicKeyBase64: String,
        pairedAt: Date,
        productionPairState: ProductionPairStateSnapshot?,
        productionC1EndpointAdmissionState: StoredProductionC1EndpointAdmissionState?
    ) {
        self.id = id
        self.name = name
        self.publicKeyBase64 = publicKeyBase64
        self.pairedAt = pairedAt
        self.productionPairState = productionPairState
        self.productionC1EndpointAdmissionState = productionC1EndpointAdmissionState
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case publicKeyBase64
        case pairedAt
        case productionPairState
        case productionC1EndpointAdmissionState
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        publicKeyBase64 = try container.decode(String.self, forKey: .publicKeyBase64)
        pairedAt = try container.decode(Date.self, forKey: .pairedAt)
        if let stateBytes = try container.decodeIfPresent(
            Data.self,
            forKey: .productionPairState
        ) {
            productionPairState = try ProductionPairStateSnapshot(canonicalBytes: stateBytes)
        } else {
            productionPairState = nil
        }
        productionC1EndpointAdmissionState = try container.decodeIfPresent(
            StoredProductionC1EndpointAdmissionState.self,
            forKey: .productionC1EndpointAdmissionState
        )
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(publicKeyBase64, forKey: .publicKeyBase64)
        try container.encode(pairedAt, forKey: .pairedAt)
        if let productionPairState {
            try container.encode(
                productionPairState.canonicalBytes(),
                forKey: .productionPairState
            )
        }
        try container.encodeIfPresent(
            productionC1EndpointAdmissionState,
            forKey: .productionC1EndpointAdmissionState
        )
    }
}

public struct VerifiedProductionC1AdmissionPermit: Equatable, Sendable {
    public let bindingDigest: String
    public let pairAuthorityDigest: String
    public let sessionId: String
    public let transcriptDigest: String
    public let routeAuthorizationDigest: String
    public let routeCapabilityDigest: String
    public let routePlanClaimsDigest: String
    public let connectorInputCommitmentDigest: String
    public let previousPairSnapshotDigest: String
    public let pairSnapshotDigest: String
    public let effectiveNotBeforeMs: UInt64
    public let expiresAtMs: UInt64

    fileprivate init(confirmed preparation: ProductionC1AdmissionPreparation) {
        bindingDigest = preparation.bindingDigest
        pairAuthorityDigest = preparation.pairAuthorityDigest
        sessionId = preparation.sessionId
        transcriptDigest = preparation.transcriptDigest
        routeAuthorizationDigest = preparation.routeAuthorizationDigest
        routeCapabilityDigest = preparation.routeCapabilityDigest
        routePlanClaimsDigest = preparation.routePlanClaimsDigest
        connectorInputCommitmentDigest = preparation.connectorInputCommitmentDigest
        previousPairSnapshotDigest = preparation.previousPairSnapshotDigest
        pairSnapshotDigest = preparation.pairSnapshotDigest
        effectiveNotBeforeMs = preparation.effectiveNotBeforeMs
        expiresAtMs = preparation.expiresAtMs
    }
}

public struct ProductionPairAdmissionPermit: Equatable, Sendable {
    public let bindingDigest: String
    public let pairAuthorityDigest: String
    public let sessionId: String
    public let transcriptDigest: String
    public let routeAuthorizationDigest: String
    public let previousPairSnapshotDigest: String
    public let pairSnapshotDigest: String

    fileprivate init(confirmed preparation: ProductionPairAdmissionPreparation) {
        bindingDigest = preparation.bindingDigest
        pairAuthorityDigest = preparation.pairAuthorityDigest
        sessionId = preparation.sessionId
        transcriptDigest = preparation.transcriptDigest
        routeAuthorizationDigest = preparation.routeAuthorizationDigest
        previousPairSnapshotDigest = preparation.previousPairSnapshotDigest
        pairSnapshotDigest = preparation.pairSnapshotDigest
    }
}

struct StoredProductionC1EndpointAdmissionState: Codable, Equatable, Sendable {
    static let schemaVersion: UInt32 = 2

    let version: UInt32
    let ledgerCanonicalBytes: Data
    let commitMarkerCanonicalBytes: [Data]

    init(ledgerCanonicalBytes: Data, commitMarkerCanonicalBytes: [Data]) {
        version = Self.schemaVersion
        self.ledgerCanonicalBytes = ledgerCanonicalBytes
        self.commitMarkerCanonicalBytes = commitMarkerCanonicalBytes
    }
}

struct StoredProductionC1EndpointCommitMarker: Codable, Equatable, Sendable {
    static let schemaVersion: UInt32 = 4
    static let maximumCanonicalBytes = 4 * 1024

    let version: UInt32
    let sequence: UInt32
    let deviceIDDigest: String
    let trustedPublicKeyDigest: String
    let admissionID: String
    let bindingDigest: String
    let sessionID: String
    let routeAuthorizationDigest: String
    let grantAuthorizationDigest: String
    let pairAuthorityDigest: String
    let effectiveNotBeforeMs: UInt64
    let expiresAtMs: UInt64
    let endpointEntryDigest: String
    let previousMarkerDigest: String?
    let expectedCompoundDigest: String
    let committedCompoundDigest: String
    let committedPairSnapshotDigest: String
    let committedLedgerSnapshotDigest: String
    let pairLocalRevision: UInt64
    let ledgerRevision: UInt64

    init(
        sequence: UInt32,
        deviceIDDigest: String,
        trustedPublicKeyDigest: String,
        admissionID: String,
        bindingDigest: String,
        sessionID: String,
        routeAuthorizationDigest: String,
        grantAuthorizationDigest: String,
        pairAuthorityDigest: String,
        effectiveNotBeforeMs: UInt64,
        expiresAtMs: UInt64,
        endpointEntryDigest: String,
        previousMarkerDigest: String?,
        expectedCompoundDigest: String,
        committedCompoundDigest: String,
        committedPairSnapshotDigest: String,
        committedLedgerSnapshotDigest: String,
        pairLocalRevision: UInt64,
        ledgerRevision: UInt64
    ) throws {
        version = Self.schemaVersion
        self.sequence = sequence
        self.deviceIDDigest = deviceIDDigest
        self.trustedPublicKeyDigest = trustedPublicKeyDigest
        self.admissionID = admissionID
        self.bindingDigest = bindingDigest
        self.sessionID = sessionID
        self.routeAuthorizationDigest = routeAuthorizationDigest
        self.grantAuthorizationDigest = grantAuthorizationDigest
        self.pairAuthorityDigest = pairAuthorityDigest
        self.effectiveNotBeforeMs = effectiveNotBeforeMs
        self.expiresAtMs = expiresAtMs
        self.endpointEntryDigest = endpointEntryDigest
        self.previousMarkerDigest = previousMarkerDigest
        self.expectedCompoundDigest = expectedCompoundDigest
        self.committedCompoundDigest = committedCompoundDigest
        self.committedPairSnapshotDigest = committedPairSnapshotDigest
        self.committedLedgerSnapshotDigest = committedLedgerSnapshotDigest
        self.pairLocalRevision = pairLocalRevision
        self.ledgerRevision = ledgerRevision
        try validate()
    }

    init(canonicalBytes: Data) throws {
        guard canonicalBytes.count <= Self.maximumCanonicalBytes else {
            throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
        }
        do {
            self = try JSONDecoder().decode(Self.self, from: canonicalBytes)
            try validate()
            guard try self.canonicalBytes() == canonicalBytes else {
                throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
            }
        } catch let error as TrustedDeviceStoreError {
            throw error
        } catch {
            throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
        }
    }

    func canonicalBytes() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        let bytes = try encoder.encode(self)
        guard bytes.count <= Self.maximumCanonicalBytes else {
            throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
        }
        return bytes
    }

    func digestHex() throws -> String {
        try trustedDeviceStoreDigestHex(canonicalBytes())
    }

    private func validate() throws {
        guard version == Self.schemaVersion,
              sequence > 0,
              trustedDeviceStoreIsSessionID(sessionID),
              effectiveNotBeforeMs < expiresAtMs,
              pairLocalRevision > 0,
              ledgerRevision > 0 else {
            throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
        }
        for digest in [
            deviceIDDigest, trustedPublicKeyDigest, admissionID, bindingDigest,
            routeAuthorizationDigest, grantAuthorizationDigest,
            pairAuthorityDigest, endpointEntryDigest,
            expectedCompoundDigest, committedCompoundDigest,
            committedPairSnapshotDigest, committedLedgerSnapshotDigest,
        ] {
            guard trustedDeviceStoreIsDigest(digest) else {
                throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
            }
        }
        if let previousMarkerDigest,
           !trustedDeviceStoreIsDigest(previousMarkerDigest) {
            throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
        }
    }
}

public struct ProductionC1EndpointGrantCompoundCommitToken: Equatable, Sendable {
    public let admissionID: String
    public let bindingDigest: String
    public let sessionID: String
    public let routeAuthorizationDigest: String
    public let grantAuthorizationDigest: String
    public let pairAuthorityDigest: String
    public let effectiveNotBeforeMs: UInt64
    public let expiresAtMs: UInt64
    public let routeGrantDigest: String
    public let transcriptDigest: String
    public let connectorInputCommitmentDigest: String
    public let pairSnapshotDigest: String
    public let ledgerSnapshotDigest: String
    public let compoundCommitDigest: String
    public let pairLocalRevision: UInt64
    public let ledgerRevision: UInt64
    public let markerDigest: String

    fileprivate init(
        entry: ProductionC1EndpointGrantEntry,
        ledger: ProductionC1EndpointGrantLedgerState,
        marker: StoredProductionC1EndpointCommitMarker
    ) throws {
        guard marker.admissionID == entry.admissionId,
              marker.bindingDigest == entry.bindingDigest,
              marker.sessionID == entry.sessionId,
              marker.routeAuthorizationDigest == entry.routeAuthorizationDigest,
              marker.grantAuthorizationDigest == entry.grantAuthorizationDigest,
              marker.pairAuthorityDigest == ledger.pairAuthorityDigest,
              marker.effectiveNotBeforeMs < marker.expiresAtMs else {
            throw ProductionC1CandidateCapabilityError.invalidValue
        }
        admissionID = entry.admissionId
        bindingDigest = entry.bindingDigest
        sessionID = entry.sessionId
        routeAuthorizationDigest = entry.routeAuthorizationDigest
        grantAuthorizationDigest = entry.grantAuthorizationDigest
        pairAuthorityDigest = ledger.pairAuthorityDigest
        effectiveNotBeforeMs = marker.effectiveNotBeforeMs
        expiresAtMs = marker.expiresAtMs
        routeGrantDigest = entry.routeGrantDigest
        transcriptDigest = entry.transcriptDigest
        connectorInputCommitmentDigest = entry.connectorInputCommitmentDigest
        pairSnapshotDigest = entry.pairSnapshotDigest
        ledgerSnapshotDigest = try ledger.snapshotDigestHex()
        compoundCommitDigest = marker.committedCompoundDigest
        pairLocalRevision = ledger.pairLocalRevision
        ledgerRevision = ledger.revision
        markerDigest = try marker.digestHex()
    }
}

struct ProductionC1ExactBoundStartRequest: Sendable {
    let deviceID: String
    let expectedPublicKeyBase64: String
    let token: ProductionC1EndpointGrantCompoundCommitToken
    let verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding
}

struct ProductionC1ExactBoundStartValidation: Equatable, Sendable {
    let deviceID: String
    let pairAuthorityDigest: String
    let markerDigest: String
    let admissionID: String
    let bindingDigest: String
    let sessionID: String
    let effectiveNotBeforeMs: UInt64
    let expiresAtMs: UInt64
    let pairLocalRevision: UInt64
    let ledgerRevision: UInt64
}

enum ProductionC1ExactBoundStartValidationError: Error, Equatable, Sendable {
    case noCurrentCommit
    case staleCommit
    case exactBindingMismatch
    case inactivePairAuthority
    case notYetValid
    case expired
}

public struct ProductionC1EndpointGrantCommitReadback: Equatable, Sendable {
    public let admissionID: String
    public let bindingDigest: String
    public let sessionID: String
    public let routeAuthorizationDigest: String
    public let grantAuthorizationDigest: String
    public let pairAuthorityDigest: String
    public let effectiveNotBeforeMs: UInt64
    public let expiresAtMs: UInt64
    public let compoundCommitDigest: String
    public let pairLocalRevision: UInt64
    public let ledgerRevision: UInt64
    public let markerDigest: String

    fileprivate init(marker: StoredProductionC1EndpointCommitMarker) throws {
        admissionID = marker.admissionID
        bindingDigest = marker.bindingDigest
        sessionID = marker.sessionID
        routeAuthorizationDigest = marker.routeAuthorizationDigest
        grantAuthorizationDigest = marker.grantAuthorizationDigest
        pairAuthorityDigest = marker.pairAuthorityDigest
        effectiveNotBeforeMs = marker.effectiveNotBeforeMs
        expiresAtMs = marker.expiresAtMs
        compoundCommitDigest = marker.committedCompoundDigest
        pairLocalRevision = marker.pairLocalRevision
        ledgerRevision = marker.ledgerRevision
        markerDigest = try marker.digestHex()
    }
}

public enum ProductionC1EndpointGrantCommitOutcome: Equatable, Sendable {
    case committed(ProductionC1EndpointGrantCompoundCommitToken)
    case alreadyCommitted(ProductionC1EndpointGrantCommitReadback)
}

public enum TrustedDeviceStoreError: Error, Equatable, Sendable {
    case invalidStoreLocation
    case unsafeStoreFile
    case ambiguousDeviceIdentifier
    case lockUnavailable
    case lockAcquisitionTimedOut
    case trustedDeviceNotFound
    case trustedDeviceIdentityMismatch
    case missingProductionPairState
    case productionPairStateOverwriteRejected
    case productionPairAdmissionReadbackMismatch
    case productionC1EndpointStateInjectionRejected
    case productionC1EndpointStateCorrupt
    case productionC1EndpointCommitChainMismatch
    case productionC1EndpointCommitReadbackMismatch
    case productionC1AdmissionReadbackMismatch
    case authorityPublicationOverloaded
    case trustedClockRegression
    case ioFailure(operation: String, code: Int32)
    case durabilityUncertainAfterRename
}

public struct TrustedDeviceStoreResourceLimitError: Error, Equatable, LocalizedError, Sendable {
    public let resource: String
    public let limit: Int
    public let actual: Int

    public init(resource: String, limit: Int, actual: Int) {
        self.resource = resource
        self.limit = limit
        self.actual = actual
    }

    public var errorDescription: String? {
        "Trusted device resource limit exceeded for \(resource): \(actual) exceeded \(limit)"
    }
}

struct TrustedDeviceStoreLimits: Equatable, Sendable {
    static let standard = TrustedDeviceStoreLimits(
        maxStoreBytes: trustedDeviceStoreMaxBytes,
        maxDevices: trustedDeviceStoreMaxDevices,
        maxIdentifierUTF8Bytes: trustedDeviceIdentifierMaxUTF8Bytes,
        maxNameUTF8Bytes: trustedDeviceNameMaxUTF8Bytes,
        maxPublicKeyUTF8Bytes: trustedDevicePublicKeyMaxUTF8Bytes
    )

    var maxStoreBytes: Int
    var maxDevices: Int
    var maxIdentifierUTF8Bytes: Int
    var maxNameUTF8Bytes: Int
    var maxPublicKeyUTF8Bytes: Int
}

struct TrustedDeviceStoreSynchronizationHooks: Sendable {
    var didLoadMutationSnapshot: (@Sendable () -> Void)?
    var didObserveMutationLockContention: (@Sendable () -> Void)?
    var didCreateTemporaryFile: (@Sendable (URL) -> Void)?
    var didPrepareAtomicReplacement: (@Sendable (URL) -> Void)?
    var didCommitBeforeReadback: (@Sendable (URL) -> Void)?
    var shouldFailDirectorySyncAfterRename: (@Sendable () -> Bool)?

    init(
        didLoadMutationSnapshot: (@Sendable () -> Void)? = nil,
        didObserveMutationLockContention: (@Sendable () -> Void)? = nil,
        didCreateTemporaryFile: (@Sendable (URL) -> Void)? = nil,
        didPrepareAtomicReplacement: (@Sendable (URL) -> Void)? = nil,
        didCommitBeforeReadback: (@Sendable (URL) -> Void)? = nil,
        shouldFailDirectorySyncAfterRename: (@Sendable () -> Bool)? = nil
    ) {
        self.didLoadMutationSnapshot = didLoadMutationSnapshot
        self.didObserveMutationLockContention = didObserveMutationLockContention
        self.didCreateTemporaryFile = didCreateTemporaryFile
        self.didPrepareAtomicReplacement = didPrepareAtomicReplacement
        self.didCommitBeforeReadback = didCommitBeforeReadback
        self.shouldFailDirectorySyncAfterRename =
            shouldFailDirectorySyncAfterRename
    }
}

private struct TrustedDeviceStoreDirectory {
    let url: URL
    let descriptor: Int32
    let storeName: String

    var lockName: String { "\(storeName).lock" }
}

public actor TrustedDeviceStore {
    private static let directoryPermissions = mode_t(S_IRWXU)
    private static let filePermissions = mode_t(S_IRUSR | S_IWUSR)
    private static let defaultLockTimeoutNanoseconds: UInt64 = 5_000_000_000
    private static let lockRetryNanoseconds: UInt64 = 10_000_000

    private let fileURL: URL
    private let fileManager: FileManager
    private let lockTimeoutNanoseconds: UInt64
    private let synchronizationHooks: TrustedDeviceStoreSynchronizationHooks
    private let limits: TrustedDeviceStoreLimits
    private let trustedNowEpochMillis: @Sendable () -> UInt64
    private let productionC1AuthorityPublicationGate:
        ProductionC1AuthorityPublicationGate
    private var productionC1ExactBoundStartCoordinatorCache:
        ProductionC1ExactBoundStartCoordinator?
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    public init(fileURL: URL? = nil, fileManager: FileManager = .default) {
        let base = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let directory = base.appendingPathComponent("AetherLink", isDirectory: true)
        self.fileURL = fileURL ?? directory.appendingPathComponent("trusted-devices.json")
        self.fileManager = fileManager
        lockTimeoutNanoseconds = Self.defaultLockTimeoutNanoseconds
        synchronizationHooks = TrustedDeviceStoreSynchronizationHooks()
        limits = .standard
        trustedNowEpochMillis = { Self.systemNowEpochMillis() }
        productionC1AuthorityPublicationGate =
            ProductionC1AuthorityPublicationGate()
        productionC1ExactBoundStartCoordinatorCache = nil
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
        decoder.userInfo[trustedDeviceStoreLimitsUserInfoKey] = limits
    }

    init(
        fileURL: URL,
        fileManager: FileManager = .default,
        lockTimeoutNanoseconds: UInt64 = TrustedDeviceStore.defaultLockTimeoutNanoseconds,
        synchronizationHooks: TrustedDeviceStoreSynchronizationHooks,
        limits: TrustedDeviceStoreLimits = .standard,
        trustedNowEpochMillis: @escaping @Sendable () -> UInt64 = {
            TrustedDeviceStore.systemNowEpochMillis()
        }
    ) {
        self.fileURL = fileURL
        self.fileManager = fileManager
        self.lockTimeoutNanoseconds = lockTimeoutNanoseconds
        self.synchronizationHooks = synchronizationHooks
        self.limits = limits
        self.trustedNowEpochMillis = trustedNowEpochMillis
        productionC1AuthorityPublicationGate =
            ProductionC1AuthorityPublicationGate()
        productionC1ExactBoundStartCoordinatorCache = nil
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
        decoder.userInfo[trustedDeviceStoreLimitsUserInfoKey] = limits
    }

    static func systemNowEpochMillis() -> UInt64 {
        let milliseconds = Date().timeIntervalSince1970 * 1_000
        guard milliseconds.isFinite, milliseconds >= 0,
              milliseconds <= Double(UInt64.max) else {
            return UInt64.max
        }
        return UInt64(milliseconds.rounded(.down))
    }

    public func load() throws -> [TrustedDevice] {
        return try withStoreLock(exclusive: false) { directory in
            try loadUnlocked(from: directory)
        }
    }

    public func trust(_ device: TrustedDevice) throws {
        guard device.productionC1EndpointAdmissionState == nil else {
            throw TrustedDeviceStoreError.productionC1EndpointStateInjectionRejected
        }
        try validateDevice(device)
        try withStoreLock(exclusive: true) { directory in
            var devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            if let existingIndex = devices.firstIndex(where: { $0.id == device.id }) {
                let existing = devices[existingIndex]
                var replacement = device
                if let existingState = existing.productionPairState {
                    guard existing.publicKeyBase64 == replacement.publicKeyBase64 else {
                        throw TrustedDeviceStoreError.trustedDeviceIdentityMismatch
                    }
                    if let replacementState = replacement.productionPairState {
                        guard try existingState.canonicalBytes()
                            == replacementState.canonicalBytes() else {
                            throw TrustedDeviceStoreError.productionPairStateOverwriteRejected
                        }
                    } else {
                        replacement.productionPairState = existingState
                    }
                } else if replacement.productionPairState != nil {
                    throw TrustedDeviceStoreError.productionPairStateOverwriteRejected
                }
                replacement.productionC1EndpointAdmissionState =
                    existing.productionC1EndpointAdmissionState
                devices[existingIndex] = replacement
            } else {
                guard device.productionPairState == nil else {
                    throw TrustedDeviceStoreError.productionPairStateOverwriteRejected
                }
                try enforceLimit(
                    devices.count + 1,
                    resource: "trusted device rows",
                    limit: limits.maxDevices
                )
                devices.append(device)
            }
            try saveUnlocked(devices.sorted { $0.name < $1.name }, in: directory)
        }
    }

    @discardableResult
    func applyVerifiedProductionPairTransition(
        deviceID: String,
        expectedPublicKeyBase64: String,
        transition: ProductionPairStateTransition
    ) async throws -> ProductionPairStateSnapshot {
        try validatePairMutationIdentity(
            deviceID: deviceID,
            expectedPublicKeyBase64: expectedPublicKeyBase64
        )
        let publicationPermit = try await acquireProductionC1AuthorityWritePermit()
        var uncertainFence: (digest: String, isRevocation: Bool)?
        do {
        let committed = try withStoreLock(exclusive: true) { directory in
            var devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            guard let index = devices.firstIndex(where: { $0.id == deviceID }) else {
                throw TrustedDeviceStoreError.trustedDeviceNotFound
            }
            guard devices[index].publicKeyBase64 == expectedPublicKeyBase64 else {
                throw TrustedDeviceStoreError.trustedDeviceIdentityMismatch
            }

            let previousAuthority = devices[index].productionPairState?.authority
            let result = try ProductionPairStateMachine.apply(
                transition,
                to: devices[index].productionPairState
            )
            devices[index].productionPairState = result.snapshot
            if result.disposition == .applied {
                devices[index].productionC1EndpointAdmissionState = nil
            }
            let previousAuthorityDigest = try previousAuthority?.digestHex()
            let nextAuthorityDigest = try result.snapshot.authority.digestHex()
            let isRevocation = result.disposition == .applied
                && previousAuthority?.status == .active
                && result.snapshot.authority.status == .revoked
            let isAuthorityAdvance = result.disposition == .applied
                && !isRevocation
                && previousAuthorityDigest != nil
                && previousAuthorityDigest != nextAuthorityDigest
            if let previousAuthorityDigest,
               isRevocation || isAuthorityAdvance {
                uncertainFence = (previousAuthorityDigest, isRevocation)
            }
            try saveUnlocked(devices.sorted { $0.name < $1.name }, in: directory)
            return (
                snapshot: result.snapshot,
                previousAuthorityDigest: previousAuthorityDigest,
                isRevocation: isRevocation,
                isAuthorityAdvance: isAuthorityAdvance
            )
        }
        if let coordinator = productionC1ExactBoundStartCoordinatorCache,
           let previousAuthorityDigest = committed.previousAuthorityDigest {
            if committed.isRevocation {
                await coordinator.fenceRevoked(
                    pairAuthorityDigest: previousAuthorityDigest
                )
            } else if committed.isAuthorityAdvance {
                await coordinator.fenceAuthorityAdvance(
                    previousPairAuthorityDigest: previousAuthorityDigest
                )
            }
        }
        await productionC1AuthorityPublicationGate.releaseWrite(publicationPermit)
        return committed.snapshot
        } catch {
            await fenceDurabilityUncertainMutation(
                error,
                candidate: uncertainFence
            )
            await productionC1AuthorityPublicationGate.releaseWrite(publicationPermit)
            throw error
        }
    }

    #if DEBUG
    @_spi(TrustedDeviceTesting)
    @discardableResult
    public func installProductionPairStateForTesting(
        deviceID: String,
        expectedPublicKeyBase64: String,
        authority: ProductionPairAuthorityState
    ) async throws -> ProductionPairStateSnapshot {
        try await applyVerifiedProductionPairTransition(
            deviceID: deviceID,
            expectedPublicKeyBase64: expectedPublicKeyBase64,
            transition: ProductionPairStateTransition(
                expectedPreviousAuthorityDigest: nil,
                nextAuthority: authority
            )
        )
    }
    #endif

    @discardableResult
    public func applyVerifiedProductionC1FreshPairTransition(
        deviceID: String,
        expectedPublicKeyBase64: String,
        transition: VerifiedProductionC1FreshPairTransition
    ) async throws -> ProductionPairStateSnapshot {
        try validatePairMutationIdentity(
            deviceID: deviceID,
            expectedPublicKeyBase64: expectedPublicKeyBase64
        )
        let publicationPermit = try await acquireProductionC1AuthorityWritePermit()
        var uncertainFence: (digest: String, isRevocation: Bool)?
        do {
        let committed = try withStoreLock(exclusive: true) { directory in
            var devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            guard let index = devices.firstIndex(where: { $0.id == deviceID }) else {
                throw TrustedDeviceStoreError.trustedDeviceNotFound
            }
            guard devices[index].publicKeyBase64 == expectedPublicKeyBase64 else {
                throw TrustedDeviceStoreError.trustedDeviceIdentityMismatch
            }
            guard let current = devices[index].productionPairState else {
                throw TrustedDeviceStoreError.missingProductionPairState
            }
            let result = try ProductionC1FreshPairStateMachine.apply(
                transition,
                to: current,
                nowMs: trustedNowEpochMillis()
            )
            guard result.disposition == .applied else {
                return (
                    snapshot: result.snapshot,
                    previousAuthorityDigest: Optional<String>.none,
                    isRevocation: false,
                    isAuthorityAdvance: false
                )
            }
            devices[index].productionPairState = result.snapshot
            devices[index].productionC1EndpointAdmissionState = nil
            let previousAuthorityDigest = try current.authority.digestHex()
            let nextAuthorityDigest = try result.snapshot.authority.digestHex()
            let isRevocation = current.authority.status == .active
                && result.snapshot.authority.status == .revoked
            let isAuthorityAdvance = !isRevocation
                && previousAuthorityDigest != nextAuthorityDigest
            if isRevocation || isAuthorityAdvance {
                uncertainFence = (previousAuthorityDigest, isRevocation)
            }
            try saveUnlocked(devices.sorted { $0.name < $1.name }, in: directory)
            return (
                snapshot: result.snapshot,
                previousAuthorityDigest: Optional(previousAuthorityDigest),
                isRevocation: isRevocation,
                isAuthorityAdvance: isAuthorityAdvance
            )
        }
        if let coordinator = productionC1ExactBoundStartCoordinatorCache,
           let previousAuthorityDigest = committed.previousAuthorityDigest {
            if committed.isRevocation {
                await coordinator.fenceRevoked(
                    pairAuthorityDigest: previousAuthorityDigest
                )
            } else if committed.isAuthorityAdvance {
                await coordinator.fenceAuthorityAdvance(
                    previousPairAuthorityDigest: previousAuthorityDigest
                )
            }
        }
        await productionC1AuthorityPublicationGate.releaseWrite(publicationPermit)
        return committed.snapshot
        } catch {
            await fenceDurabilityUncertainMutation(
                error,
                candidate: uncertainFence
            )
            await productionC1AuthorityPublicationGate.releaseWrite(publicationPermit)
            throw error
        }
    }

    func admitProductionSecureSession(
        deviceID: String,
        expectedPublicKeyBase64: String,
        transcript: ProductionSecureSessionTranscript,
        routeAuthorization: ProductionRouteAuthorization
    ) throws -> ProductionPairAdmissionPermit {
        try validatePairMutationIdentity(
            deviceID: deviceID,
            expectedPublicKeyBase64: expectedPublicKeyBase64
        )
        return try withStoreLock(exclusive: true) { directory in
            var devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            guard let index = devices.firstIndex(where: { $0.id == deviceID }) else {
                throw TrustedDeviceStoreError.trustedDeviceNotFound
            }
            guard devices[index].publicKeyBase64 == expectedPublicKeyBase64 else {
                throw TrustedDeviceStoreError.trustedDeviceIdentityMismatch
            }
            guard let state = devices[index].productionPairState else {
                throw TrustedDeviceStoreError.missingProductionPairState
            }

            let preparation = try ProductionPairStateAdmission.prepare(
                transcript: transcript,
                routeAuthorization: routeAuthorization,
                to: state
            )
            devices[index].productionPairState = preparation.snapshot
            devices[index].productionC1EndpointAdmissionState = nil
            let committedBytes = try saveUnlocked(
                devices.sorted { $0.name < $1.name },
                in: directory
            )
            synchronizationHooks.didCommitBeforeReadback?(
                directory.url.appendingPathComponent(directory.storeName)
            )
            guard let readbackBytes = try readStoreBytesUnlocked(from: directory),
                  readbackBytes == committedBytes else {
                throw TrustedDeviceStoreError.productionPairAdmissionReadbackMismatch
            }
            let readbackDevices = try decodeDevices(readbackBytes)
            guard let readbackDevice = readbackDevices.first(where: {
                $0.id == deviceID && $0.publicKeyBase64 == expectedPublicKeyBase64
            }),
                let readbackPairSnapshot = readbackDevice.productionPairState,
                readbackPairSnapshot == preparation.snapshot,
                try readbackPairSnapshot.digestHex() == preparation.pairSnapshotDigest,
                let consumedTombstone = readbackPairSnapshot.consumedEntries.last,
                consumedTombstone.sessionId == preparation.sessionId,
                consumedTombstone.transcriptDigest == preparation.transcriptDigest,
                readbackDevice.productionC1EndpointAdmissionState == nil else {
                throw TrustedDeviceStoreError.productionPairAdmissionReadbackMismatch
            }
            return ProductionPairAdmissionPermit(confirmed: preparation)
        }
    }

    public func admitVerifiedProductionC1SecureSession(
        deviceID: String,
        expectedPublicKeyBase64: String,
        binding: VerifiedProductionC1TranscriptBinding
    ) throws -> VerifiedProductionC1AdmissionPermit {
        try validatePairMutationIdentity(
            deviceID: deviceID,
            expectedPublicKeyBase64: expectedPublicKeyBase64
        )
        return try withStoreLock(exclusive: true) { directory in
            var devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            guard let index = devices.firstIndex(where: { $0.id == deviceID }) else {
                throw TrustedDeviceStoreError.trustedDeviceNotFound
            }
            guard devices[index].publicKeyBase64 == expectedPublicKeyBase64 else {
                throw TrustedDeviceStoreError.trustedDeviceIdentityMismatch
            }
            guard let state = devices[index].productionPairState else {
                throw TrustedDeviceStoreError.missingProductionPairState
            }
            let verificationNowMs = trustedNowEpochMillis()
            let preparation = try ProductionC1PairStateAdmission.prepare(
                binding: binding,
                to: state,
                nowMs: verificationNowMs
            )
            devices[index].productionPairState = preparation.snapshot
            devices[index].productionC1EndpointAdmissionState = nil
            let sortedDevices = devices.sorted { $0.name < $1.name }
            let precommitNowMs = trustedNowEpochMillis()
            guard precommitNowMs >= verificationNowMs else {
                throw TrustedDeviceStoreError.trustedClockRegression
            }
            try validateProductionC1AdmissionPreparationWindow(
                preparation,
                nowMs: precommitNowMs
            )
            let committedBytes = try saveUnlocked(sortedDevices, in: directory)
            synchronizationHooks.didCommitBeforeReadback?(
                directory.url.appendingPathComponent(directory.storeName)
            )
            guard let readbackBytes = try readStoreBytesUnlocked(from: directory),
                  readbackBytes == committedBytes else {
                throw TrustedDeviceStoreError.productionC1AdmissionReadbackMismatch
            }
            let readbackDevices = try decodeDevices(readbackBytes)
            guard let readbackDevice = readbackDevices.first(where: {
                $0.id == deviceID && $0.publicKeyBase64 == expectedPublicKeyBase64
            }),
                let readbackPairSnapshot = readbackDevice.productionPairState,
                readbackPairSnapshot == preparation.snapshot,
                try readbackPairSnapshot.digestHex() == preparation.pairSnapshotDigest,
                let consumedTombstone = readbackPairSnapshot.consumedEntries.last,
                consumedTombstone.sessionId == preparation.sessionId,
                consumedTombstone.transcriptDigest == preparation.transcriptDigest,
                readbackDevice.productionC1EndpointAdmissionState == nil else {
                throw TrustedDeviceStoreError.productionC1AdmissionReadbackMismatch
            }
            let permitNowMs = trustedNowEpochMillis()
            guard permitNowMs >= precommitNowMs else {
                throw TrustedDeviceStoreError.trustedClockRegression
            }
            try validateProductionC1AdmissionPreparationWindow(
                preparation,
                nowMs: permitNowMs
            )
            return VerifiedProductionC1AdmissionPermit(confirmed: preparation)
        }
    }

    public func commitProductionC1EndpointGrant(
        deviceID: String,
        expectedPublicKeyBase64: String,
        admissionID: String,
        bindingDigest: String,
        verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding
    ) throws -> ProductionC1EndpointGrantCommitOutcome {
        try validatePairMutationIdentity(
            deviceID: deviceID,
            expectedPublicKeyBase64: expectedPublicKeyBase64
        )
        return try withStoreLock(exclusive: true) { directory in
            var devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            guard let index = devices.firstIndex(where: { $0.id == deviceID }) else {
                throw TrustedDeviceStoreError.trustedDeviceNotFound
            }
            let device = devices[index]
            guard device.publicKeyBase64 == expectedPublicKeyBase64 else {
                throw TrustedDeviceStoreError.trustedDeviceIdentityMismatch
            }
            guard let pairSnapshot = device.productionPairState else {
                throw TrustedDeviceStoreError.missingProductionPairState
            }
            let current = try endpointLedgerForCommit(device)
            let verificationNowMs = trustedNowEpochMillis()
            let preparation = try ProductionC1EndpointGrantAdmission
                .prepareForTrustedPersistence(
                    state: current,
                    expectedRevision: current.revision,
                    expectedSnapshotDigest: current.snapshotDigestHex(),
                    admissionId: admissionID,
                    bindingDigest: bindingDigest,
                    verifiedBinding: verifiedBinding,
                    currentPairSnapshot: pairSnapshot,
                    nowMs: verificationNowMs
                )
            return try persistProductionC1EndpointPreparationUnlocked(
                preparation,
                deviceIndex: index,
                devices: &devices,
                directory: directory,
                minimumTrustedNowMs: verificationNowMs
            )
        }
    }

    #if DEBUG
    func commitPreparedProductionC1EndpointGrantForTesting(
        deviceID: String,
        expectedPublicKeyBase64: String,
        preparation: ProductionC1EndpointGrantAdmissionPreparation
    ) throws -> ProductionC1EndpointGrantCommitOutcome {
        try validatePairMutationIdentity(
            deviceID: deviceID,
            expectedPublicKeyBase64: expectedPublicKeyBase64
        )
        return try withStoreLock(exclusive: true) { directory in
            var devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            guard let index = devices.firstIndex(where: { $0.id == deviceID }) else {
                throw TrustedDeviceStoreError.trustedDeviceNotFound
            }
            guard devices[index].publicKeyBase64 == expectedPublicKeyBase64 else {
                throw TrustedDeviceStoreError.trustedDeviceIdentityMismatch
            }
            return try persistProductionC1EndpointPreparationUnlocked(
                preparation,
                deviceIndex: index,
                devices: &devices,
                directory: directory,
                minimumTrustedNowMs: nil
            )
        }
    }
    #endif

    public func readProductionC1EndpointGrantCommit(
        deviceID: String,
        expectedPublicKeyBase64: String,
        admissionID: String,
        bindingDigest: String
    ) throws -> ProductionC1EndpointGrantCommitReadback? {
        try validatePairMutationIdentity(
            deviceID: deviceID,
            expectedPublicKeyBase64: expectedPublicKeyBase64
        )
        return try withStoreLock(exclusive: false) { directory in
            guard let bytes = try readStoreBytesUnlocked(from: directory) else { return nil }
            let devices = try decodeDevices(bytes)
            guard let device = devices.first(where: { $0.id == deviceID }) else { return nil }
            guard device.publicKeyBase64 == expectedPublicKeyBase64 else {
                throw TrustedDeviceStoreError.trustedDeviceIdentityMismatch
            }
            guard let validated = try validatedEndpointState(for: device) else { return nil }
            guard let marker = validated.markers.first(where: {
                $0.admissionID == admissionID
            }) else { return nil }
            guard marker.bindingDigest == bindingDigest else {
                throw ProductionC1CandidateCapabilityError.requestConflict
            }
            return try ProductionC1EndpointGrantCommitReadback(marker: marker)
        }
    }

    func productionC1ExactBoundStartCoordinator()
        -> ProductionC1ExactBoundStartCoordinator
    {
        if let productionC1ExactBoundStartCoordinatorCache {
            return productionC1ExactBoundStartCoordinatorCache
        }
        let coordinator = ProductionC1ExactBoundStartCoordinator.storeOwned(
            validator: { [weak self] request in
                guard let self else {
                    throw ProductionC1ExactBoundStartValidationError.noCurrentCommit
                }
                return try await self.validateProductionC1ExactBoundStart(request)
            },
            nowMs: trustedNowEpochMillis,
            publicationGate: productionC1AuthorityPublicationGate
        )
        productionC1ExactBoundStartCoordinatorCache = coordinator
        return coordinator
    }

    /// Store-owned entry point for a transport session bound to the exact
    /// current durable endpoint commit. The internal authority permit,
    /// coordinator, and raw crypto state never cross this SPI boundary.
    @_spi(ProductionTransport)
    public func beginProductionC1TransportSecureSession(
        deviceID: String,
        expectedPublicKeyBase64: String,
        token: ProductionC1EndpointGrantCompoundCommitToken,
        verifiedBinding: VerifiedProductionC1CandidateP2PTranscriptBinding,
        localEphemeralKey: P2PNATSessionEphemeralKey
    ) async throws -> ProductionC1TransportSecureSession {
        // Ownership transfers at method entry. The exact-bound start either
        // consumes the key once or this defer irreversibly discards it; no
        // success, validation failure, or cancellation returns it to caller.
        defer { localEphemeralKey.close() }
        let request = ProductionC1ExactBoundStartRequest(
            deviceID: deviceID,
            expectedPublicKeyBase64: expectedPublicKeyBase64,
            token: token,
            verifiedBinding: verifiedBinding
        )
        return try await ProductionC1TransportSecureSession.start(
            coordinator: productionC1ExactBoundStartCoordinator(),
            request: request,
            localEphemeralKey: localEphemeralKey,
            nowMs: trustedNowEpochMillis
        )
    }

    /// Validates a connector start against the exact current durable compound commit.
    /// Historical markers and restart readbacks are deliberately ineligible here.
    func validateProductionC1ExactBoundStart(
        _ request: ProductionC1ExactBoundStartRequest
    ) throws -> ProductionC1ExactBoundStartValidation {
        try validatePairMutationIdentity(
            deviceID: request.deviceID,
            expectedPublicKeyBase64: request.expectedPublicKeyBase64
        )
        return try withStoreLock(exclusive: false) { directory in
            guard let bytes = try readStoreBytesUnlocked(from: directory) else {
                throw ProductionC1ExactBoundStartValidationError.noCurrentCommit
            }
            let devices = try decodeDevices(bytes)
            guard let device = devices.first(where: { $0.id == request.deviceID }) else {
                throw TrustedDeviceStoreError.trustedDeviceNotFound
            }
            guard device.publicKeyBase64 == request.expectedPublicKeyBase64 else {
                throw TrustedDeviceStoreError.trustedDeviceIdentityMismatch
            }
            guard let pairSnapshot = device.productionPairState else {
                throw TrustedDeviceStoreError.missingProductionPairState
            }
            guard pairSnapshot.authority.status == .active else {
                throw ProductionC1ExactBoundStartValidationError.inactivePairAuthority
            }
            guard let state = try validatedEndpointState(for: device),
                  let entry = state.ledger.entries.last,
                  let marker = state.markers.last else {
                throw ProductionC1ExactBoundStartValidationError.noCurrentCommit
            }

            let token = request.token
            let binding = request.verifiedBinding
            let evidence = binding.grant.evidence
            let transcript = binding.transcript
            let routeAuthorization = binding.grant.routeAuthorizations.finalP2PDirect
            let routeAuthorizationDigest = trustedDeviceStoreDigestHex(
                try routeAuthorization.canonicalBytes()
            )
            let grantAuthorizationDigest = try binding.grant
                .grantAuthorization.authorization.digestHex()
            let routeGrantDigest = try evidence.digestHex()
            let transcriptDigest = trustedDeviceStoreDigestHex(transcript.canonicalBytes())
            let connectorInputCommitmentDigest = binding.connectorInput.commitmentDigest
            let bindingDigest = try ProductionC1EndpointGrantAdmission.bindingDigest(
                admissionId: token.admissionID,
                routeGrantDigest: routeGrantDigest,
                transcriptDigest: transcriptDigest,
                routeAuthorizationDigest: routeAuthorizationDigest,
                grantAuthorizationDigest: grantAuthorizationDigest,
                connectorInputCommitmentDigest: connectorInputCommitmentDigest
            )
            let pairAuthorityDigest = try pairSnapshot.authority.digestHex()
            let pairSnapshotDigest = try pairSnapshot.digestHex()
            let ledgerSnapshotDigest = try state.ledger.snapshotDigestHex()
            let compoundCommitDigest = try ProductionC1EndpointCompoundRecord(
                grantLedger: state.ledger,
                pairSnapshot: pairSnapshot
            ).digestHex()
            let markerDigest = try marker.digestHex()
            let authority = pairSnapshot.authority
            let nowMs = trustedNowEpochMillis()

            guard nowMs >= evidence.effectiveNotBeforeMs,
                  nowMs >= marker.effectiveNotBeforeMs else {
                throw ProductionC1ExactBoundStartValidationError.notYetValid
            }
            guard nowMs < evidence.expiresAtMs,
                  nowMs < marker.expiresAtMs else {
                throw ProductionC1ExactBoundStartValidationError.expired
            }
            guard pairAuthorityDigest == evidence.pairAuthorityDigest,
                  authority.pairBindingDigest == evidence.pairBindingDigest,
                  authority.pairEpoch == evidence.pairEpoch,
                  authority.generation == evidence.generation,
                  authority.clientIdentityFingerprint == evidence.clientIdentityFingerprint,
                  authority.runtimeIdentityFingerprint == evidence.runtimeIdentityFingerprint,
                  authority.keysetVersion == evidence.keysetVersion,
                  transcript.pairBindingDigest == authority.pairBindingDigest,
                  transcript.pairEpoch == authority.pairEpoch,
                  transcript.generation == authority.generation,
                  transcript.serviceConfigVersion == authority.serviceConfigVersion,
                  transcript.keysetVersion == authority.keysetVersion,
                  transcript.revocationCounter == authority.revocationCounter,
                  transcript.clientIdentityFingerprint
                    == authority.clientIdentityFingerprint,
                  transcript.runtimeIdentityFingerprint
                    == authority.runtimeIdentityFingerprint else {
                throw ProductionC1ExactBoundStartValidationError.inactivePairAuthority
            }

            guard entry == state.ledger.entries.last,
                  marker == state.markers.last,
                  token.admissionID == entry.admissionId,
                  token.bindingDigest == entry.bindingDigest,
                  token.sessionID == entry.sessionId,
                  token.routeAuthorizationDigest == entry.routeAuthorizationDigest,
                  token.grantAuthorizationDigest == entry.grantAuthorizationDigest,
                  token.pairAuthorityDigest == state.ledger.pairAuthorityDigest,
                  token.effectiveNotBeforeMs == marker.effectiveNotBeforeMs,
                  token.expiresAtMs == marker.expiresAtMs,
                  token.routeGrantDigest == entry.routeGrantDigest,
                  token.transcriptDigest == entry.transcriptDigest,
                  token.connectorInputCommitmentDigest
                    == entry.connectorInputCommitmentDigest,
                  token.pairSnapshotDigest == entry.pairSnapshotDigest,
                  token.ledgerSnapshotDigest == ledgerSnapshotDigest,
                  token.compoundCommitDigest == marker.committedCompoundDigest,
                  token.pairLocalRevision == marker.pairLocalRevision,
                  token.ledgerRevision == marker.ledgerRevision,
                  token.markerDigest == markerDigest,
                  entry.admissionId == marker.admissionID,
                  entry.bindingDigest == marker.bindingDigest,
                  entry.sessionId == marker.sessionID,
                  entry.routeAuthorizationDigest == marker.routeAuthorizationDigest,
                  entry.grantAuthorizationDigest == marker.grantAuthorizationDigest,
                  entry.pairSnapshotDigest == marker.committedPairSnapshotDigest,
                  pairSnapshotDigest == marker.committedPairSnapshotDigest,
                  ledgerSnapshotDigest == marker.committedLedgerSnapshotDigest,
                  compoundCommitDigest == marker.committedCompoundDigest,
                  pairSnapshot.localRevision == marker.pairLocalRevision,
                  state.ledger.revision == marker.ledgerRevision else {
                throw ProductionC1ExactBoundStartValidationError.staleCommit
            }

            guard token.bindingDigest == bindingDigest,
                  token.routeGrantDigest == routeGrantDigest,
                  token.transcriptDigest == transcriptDigest,
                  token.routeAuthorizationDigest == routeAuthorizationDigest,
                  token.grantAuthorizationDigest == grantAuthorizationDigest,
                  token.connectorInputCommitmentDigest
                    == connectorInputCommitmentDigest,
                  token.pairAuthorityDigest == pairAuthorityDigest,
                  token.pairSnapshotDigest == pairSnapshotDigest,
                  token.ledgerSnapshotDigest == ledgerSnapshotDigest,
                  token.compoundCommitDigest == compoundCommitDigest,
                  token.markerDigest == markerDigest,
                  token.sessionID == transcript.sessionId,
                  token.sessionID == evidence.sessionId,
                  token.effectiveNotBeforeMs == evidence.effectiveNotBeforeMs,
                  token.expiresAtMs == evidence.expiresAtMs,
                  routeAuthorizationDigest == evidence.finalRouteAuthorizationDigest,
                  transcript.routeKind == .p2pDirect,
                  transcript.routeAuthDigest == grantAuthorizationDigest else {
                throw ProductionC1ExactBoundStartValidationError.exactBindingMismatch
            }

            return ProductionC1ExactBoundStartValidation(
                deviceID: request.deviceID,
                pairAuthorityDigest: pairAuthorityDigest,
                markerDigest: markerDigest,
                admissionID: token.admissionID,
                bindingDigest: bindingDigest,
                sessionID: token.sessionID,
                effectiveNotBeforeMs: token.effectiveNotBeforeMs,
                expiresAtMs: token.expiresAtMs,
                pairLocalRevision: token.pairLocalRevision,
                ledgerRevision: token.ledgerRevision
            )
        }
    }

    private func endpointLedgerForCommit(
        _ device: TrustedDevice
    ) throws -> ProductionC1EndpointGrantLedgerState {
        if let validated = try validatedEndpointState(for: device) {
            return validated.ledger
        }
        guard let pairSnapshot = device.productionPairState else {
            throw TrustedDeviceStoreError.missingProductionPairState
        }
        let capacity = ProductionC1EndpointLedgerPersistenceContract.maximumEntries
        guard pairSnapshot.consumedEntries.count <= capacity else {
            throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
        }
        return try ProductionC1EndpointGrantLedgerState(
            pairAuthorityDigest: pairSnapshot.authority.digestHex(),
            pairLocalRevision: pairSnapshot.localRevision,
            remainingGrants: UInt64(capacity - pairSnapshot.consumedEntries.count),
            retentionLimit: UInt32(capacity)
        )
    }

    private func persistProductionC1EndpointPreparationUnlocked(
        _ preparation: ProductionC1EndpointGrantAdmissionPreparation,
        deviceIndex: Int,
        devices: inout [TrustedDevice],
        directory: TrustedDeviceStoreDirectory,
        minimumTrustedNowMs: UInt64?
    ) throws -> ProductionC1EndpointGrantCommitOutcome {
        let currentDevice = devices[deviceIndex]
        guard let currentPair = currentDevice.productionPairState else {
            throw TrustedDeviceStoreError.missingProductionPairState
        }
        let currentLedger = try endpointLedgerForCommit(currentDevice)
        let currentCompound = try ProductionC1EndpointCompoundRecord(
            grantLedger: currentLedger,
            pairSnapshot: currentPair
        )
        let currentLedgerDigest = try currentLedger.snapshotDigestHex()
        let currentPairDigest = try currentPair.digestHex()
        let currentCompoundDigest = try currentCompound.digestHex()
        guard preparation.expectedRevision == currentLedger.revision,
              preparation.expectedSnapshotDigest == currentLedgerDigest,
              preparation.expectedPairSnapshotDigest == currentPairDigest,
              preparation.expectedCompoundDigest == currentCompoundDigest else {
            throw ProductionC1CandidateCapabilityError.revisionMismatch
        }

        let existingMarkers = try validatedEndpointState(for: currentDevice)?.markers ?? []
        if preparation.disposition == .idempotent {
            guard preparation.nextState == currentLedger,
                  preparation.nextPairSnapshot == currentPair,
                  let marker = existingMarkers.first(where: {
                      $0.admissionID == preparation.entry.admissionId
                  }),
                  marker.bindingDigest == preparation.entry.bindingDigest,
                  marker.sessionID == preparation.sessionID,
                  marker.routeAuthorizationDigest == preparation.routeAuthorizationDigest,
                  marker.grantAuthorizationDigest == preparation.grantAuthorizationDigest,
                  marker.pairAuthorityDigest == preparation.pairAuthorityDigest,
                  marker.effectiveNotBeforeMs == preparation.effectiveNotBeforeMs,
                  marker.expiresAtMs == preparation.expiresAtMs else {
                throw ProductionC1CandidateCapabilityError.requestConflict
            }
            // An idempotent/restart result is deliberately non-authorizing. The verifier's
            // idempotent path does not re-check expiry, so only an applied durable save may
            // mint the opaque live commit token.
            guard let readbackBytes = try readStoreBytesUnlocked(from: directory) else {
                throw TrustedDeviceStoreError.productionC1EndpointCommitReadbackMismatch
            }
            let readbackDevices = try decodeDevices(readbackBytes)
            guard let readbackDevice = readbackDevices.first(where: {
                $0.id == currentDevice.id
            }), try validatedEndpointState(for: readbackDevice)?.markers.contains(marker) == true else {
                throw TrustedDeviceStoreError.productionC1EndpointCommitReadbackMismatch
            }
            return .alreadyCommitted(
                try ProductionC1EndpointGrantCommitReadback(marker: marker)
            )
        }

        guard preparation.disposition == .applied,
              preparation.nextState.entries.count == currentLedger.entries.count + 1,
              preparation.nextState.entries.last == preparation.entry,
              preparation.nextPairSnapshot == preparation.nextCompoundRecord.pairSnapshot,
              preparation.nextState == preparation.nextCompoundRecord.grantLedger,
              preparation.entry.committedRevision == preparation.nextState.revision,
              existingMarkers.count < ProductionC1EndpointLedgerPersistenceContract.maximumEntries,
              let sequence = UInt32(exactly: existingMarkers.count + 1) else {
            throw ProductionC1CandidateCapabilityError.revisionMismatch
        }

        let nextLedgerDigest = try preparation.nextState.snapshotDigestHex()
        let nextPairDigest = try preparation.nextPairSnapshot.digestHex()
        let committedCompoundDigest = try preparation.nextCompoundRecord.digestHex()
        let marker = try StoredProductionC1EndpointCommitMarker(
            sequence: sequence,
            deviceIDDigest: trustedDeviceStoreIdentityDigest(
                domain: "AetherLink trusted-device identifier v1",
                value: currentDevice.id
            ),
            trustedPublicKeyDigest: trustedDeviceStoreIdentityDigest(
                domain: "AetherLink trusted-device public key v1",
                value: currentDevice.publicKeyBase64
            ),
            admissionID: preparation.entry.admissionId,
            bindingDigest: preparation.entry.bindingDigest,
            sessionID: preparation.sessionID,
            routeAuthorizationDigest: preparation.routeAuthorizationDigest,
            grantAuthorizationDigest: preparation.grantAuthorizationDigest,
            pairAuthorityDigest: preparation.pairAuthorityDigest,
            effectiveNotBeforeMs: preparation.effectiveNotBeforeMs,
            expiresAtMs: preparation.expiresAtMs,
            endpointEntryDigest: trustedDeviceStoreEndpointEntryDigest(preparation.entry),
            previousMarkerDigest: try existingMarkers.last?.digestHex(),
            expectedCompoundDigest: preparation.expectedCompoundDigest,
            committedCompoundDigest: committedCompoundDigest,
            committedPairSnapshotDigest: nextPairDigest,
            committedLedgerSnapshotDigest: nextLedgerDigest,
            pairLocalRevision: preparation.nextPairSnapshot.localRevision,
            ledgerRevision: preparation.nextState.revision
        )
        let nextState = StoredProductionC1EndpointAdmissionState(
            ledgerCanonicalBytes: try preparation.nextState.persistenceCanonicalBytes(),
            commitMarkerCanonicalBytes: try (existingMarkers + [marker]).map {
                try $0.canonicalBytes()
            }
        )
        devices[deviceIndex].productionPairState = preparation.nextPairSnapshot
        devices[deviceIndex].productionC1EndpointAdmissionState = nextState
        let sortedDevices = devices.sorted { $0.name < $1.name }
        let precommitNowMs = trustedNowEpochMillis()
        if let minimumTrustedNowMs, precommitNowMs < minimumTrustedNowMs {
            throw TrustedDeviceStoreError.trustedClockRegression
        }
        try validateProductionC1EndpointPreparationWindow(
            preparation,
            nowMs: precommitNowMs
        )
        let committedBytes = try saveUnlocked(sortedDevices, in: directory)
        synchronizationHooks.didCommitBeforeReadback?(
            directory.url.appendingPathComponent(directory.storeName)
        )
        guard let readbackBytes = try readStoreBytesUnlocked(from: directory),
              readbackBytes == committedBytes else {
            throw TrustedDeviceStoreError.productionC1EndpointCommitReadbackMismatch
        }
        let readbackDevices = try decodeDevices(readbackBytes)
        guard let readbackDevice = readbackDevices.first(where: {
            $0.id == currentDevice.id
        }),
            readbackDevice.productionPairState == preparation.nextPairSnapshot,
            let readbackState = try validatedEndpointState(for: readbackDevice),
            readbackState.ledger == preparation.nextState,
            readbackState.markers.last == marker else {
            throw TrustedDeviceStoreError.productionC1EndpointCommitReadbackMismatch
        }
        let tokenNowMs = trustedNowEpochMillis()
        guard tokenNowMs >= precommitNowMs else {
            throw TrustedDeviceStoreError.trustedClockRegression
        }
        try validateProductionC1EndpointPreparationWindow(
            preparation,
            nowMs: tokenNowMs
        )
        return .committed(
            try ProductionC1EndpointGrantCompoundCommitToken(
                entry: preparation.entry,
                ledger: preparation.nextState,
                marker: marker
            )
        )
    }

    private func validateProductionC1EndpointPreparationWindow(
        _ preparation: ProductionC1EndpointGrantAdmissionPreparation,
        nowMs: UInt64
    ) throws {
        guard nowMs >= preparation.effectiveNotBeforeMs else {
            throw ProductionC1Error.notYetValid
        }
        guard nowMs < preparation.expiresAtMs else {
            throw ProductionC1Error.expired
        }
    }

    private func validateProductionC1AdmissionPreparationWindow(
        _ preparation: ProductionC1AdmissionPreparation,
        nowMs: UInt64
    ) throws {
        guard nowMs >= preparation.effectiveNotBeforeMs else {
            throw ProductionC1Error.notYetValid
        }
        guard nowMs < preparation.expiresAtMs else {
            throw ProductionC1Error.expired
        }
    }

    public func remove(deviceID: String) async throws {
        try validateField(
            deviceID,
            resource: "device identifier UTF-8 bytes",
            limit: limits.maxIdentifierUTF8Bytes
        )
        let publicationPermit = try await acquireProductionC1AuthorityWritePermit()
        var uncertainPreviousAuthorityDigest: String?
        do {
        let previousAuthorityDigest = try withStoreLock(exclusive: true) { directory in
            let devices = try loadUnlocked(from: directory)
            synchronizationHooks.didLoadMutationSnapshot?()
            let previousAuthorityDigest = try devices
                .first(where: { $0.id == deviceID })?
                .productionPairState?
                .authority.digestHex()
            uncertainPreviousAuthorityDigest = previousAuthorityDigest
            try saveUnlocked(devices.filter { $0.id != deviceID }, in: directory)
            return previousAuthorityDigest
        }
        if let previousAuthorityDigest,
           let coordinator = productionC1ExactBoundStartCoordinatorCache {
            await coordinator.fenceRevoked(
                pairAuthorityDigest: previousAuthorityDigest
            )
        }
        await productionC1AuthorityPublicationGate.releaseWrite(publicationPermit)
        } catch {
            await fenceDurabilityUncertainMutation(
                error,
                candidate: uncertainPreviousAuthorityDigest.map { ($0, true) }
            )
            await productionC1AuthorityPublicationGate.releaseWrite(publicationPermit)
            throw error
        }
    }

    public func withTrustedDeviceSnapshot<Result: Sendable>(
        deviceID: String,
        operation: @Sendable (TrustedDevice?) throws -> Result
    ) throws -> Result {
        try validateField(
            deviceID,
            resource: "device identifier UTF-8 bytes",
            limit: limits.maxIdentifierUTF8Bytes
        )
        return try withStoreLock(exclusive: false) { directory in
            let device = try loadUnlocked(from: directory).first { $0.id == deviceID }
            return try operation(device)
        }
    }

    private func withStoreLock<Result>(
        exclusive: Bool,
        operation: (TrustedDeviceStoreDirectory) throws -> Result
    ) throws -> Result {
        let directory = try openSecureDirectory()
        defer { Darwin.close(directory.descriptor) }

        let lockDescriptor = try openSecureLockFile(in: directory)
        defer { Darwin.close(lockDescriptor) }
        try acquireLock(
            descriptor: lockDescriptor,
            operation: exclusive ? LOCK_EX : LOCK_SH
        )
        defer { _ = systemFlock(lockDescriptor, LOCK_UN) }
        return try operation(directory)
    }

    private func openSecureDirectory() throws -> TrustedDeviceStoreDirectory {
        guard fileURL.isFileURL,
              !fileURL.lastPathComponent.isEmpty,
              fileURL.lastPathComponent != ".",
              fileURL.lastPathComponent != ".."
        else {
            throw TrustedDeviceStoreError.invalidStoreLocation
        }
        let requestedDirectory = fileURL.deletingLastPathComponent()
        do {
            try fileManager.createDirectory(
                at: requestedDirectory,
                withIntermediateDirectories: true,
                attributes: [.posixPermissions: Self.directoryPermissions]
            )
        } catch {
            throw TrustedDeviceStoreError.invalidStoreLocation
        }
        let canonicalDirectory = requestedDirectory
            .resolvingSymlinksInPath()
            .standardizedFileURL
        let descriptor = Darwin.open(
            canonicalDirectory.path,
            O_RDONLY | O_CLOEXEC | O_NOFOLLOW
        )
        guard descriptor >= 0 else {
            throw ioFailure("open directory")
        }
        var metadata = stat()
        guard Darwin.fstat(descriptor, &metadata) == 0,
              metadata.st_uid == geteuid(),
              metadata.st_mode & S_IFMT == S_IFDIR
        else {
            Darwin.close(descriptor)
            throw TrustedDeviceStoreError.invalidStoreLocation
        }
        do {
            try secureDescriptor(
                descriptor,
                permissions: Self.directoryPermissions,
                operation: "secure trusted device directory"
            )
        } catch {
            Darwin.close(descriptor)
            throw error
        }
        return TrustedDeviceStoreDirectory(
            url: canonicalDirectory,
            descriptor: descriptor,
            storeName: fileURL.lastPathComponent
        )
    }

    private func openSecureLockFile(in directory: TrustedDeviceStoreDirectory) throws -> Int32 {
        let descriptor = Darwin.openat(
            directory.descriptor,
            directory.lockName,
            O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW,
            Self.filePermissions
        )
        guard descriptor >= 0 else {
            throw TrustedDeviceStoreError.lockUnavailable
        }
        do {
            try validateRegularFileDescriptor(descriptor, failure: .lockUnavailable)
            try secureDescriptor(
                descriptor,
                permissions: Self.filePermissions,
                operation: "secure lock file"
            )
            return descriptor
        } catch {
            Darwin.close(descriptor)
            throw error
        }
    }

    private func acquireLock(descriptor: Int32, operation: Int32) throws {
        let started = try monotonicNanoseconds()
        let deadlineResult = started.addingReportingOverflow(lockTimeoutNanoseconds)
        guard !deadlineResult.overflow else {
            throw TrustedDeviceStoreError.lockUnavailable
        }
        let deadline = deadlineResult.partialValue
        var reportedContention = false

        while systemFlock(descriptor, operation | LOCK_NB) != 0 {
            let lockError = errno
            if lockError == EINTR { continue }
            guard lockError == EWOULDBLOCK || lockError == EAGAIN else {
                throw TrustedDeviceStoreError.lockUnavailable
            }
            if operation == LOCK_EX && !reportedContention {
                reportedContention = true
                synchronizationHooks.didObserveMutationLockContention?()
            }
            let now = try monotonicNanoseconds()
            guard now < deadline else {
                throw TrustedDeviceStoreError.lockAcquisitionTimedOut
            }
            let delayNanoseconds = min(Self.lockRetryNanoseconds, deadline - now)
            var delay = timespec(
                tv_sec: time_t(delayNanoseconds / 1_000_000_000),
                tv_nsec: Int(delayNanoseconds % 1_000_000_000)
            )
            var remaining = timespec()
            while Darwin.nanosleep(&delay, &remaining) != 0 {
                guard errno == EINTR else {
                    throw TrustedDeviceStoreError.lockUnavailable
                }
                delay = remaining
            }
        }
    }

    private func readStoreBytesUnlocked(
        from directory: TrustedDeviceStoreDirectory
    ) throws -> Data? {
        var pathMetadata = stat()
        guard Darwin.fstatat(
            directory.descriptor,
            directory.storeName,
            &pathMetadata,
            AT_SYMLINK_NOFOLLOW
        ) == 0 else {
            if errno == ENOENT { return nil }
            throw ioFailure("inspect trusted device store")
        }
        guard isSafeRegularFile(pathMetadata) else {
            throw TrustedDeviceStoreError.unsafeStoreFile
        }
        let descriptor = Darwin.openat(
            directory.descriptor,
            directory.storeName,
            O_RDONLY | O_CLOEXEC | O_NOFOLLOW
        )
        guard descriptor >= 0 else {
            throw ioFailure("open trusted device store")
        }
        defer { Darwin.close(descriptor) }
        try validateRegularFileDescriptor(descriptor, failure: .unsafeStoreFile)
        try secureDescriptor(
            descriptor,
            permissions: Self.filePermissions,
            operation: "secure trusted device store"
        )
        return try readAll(from: descriptor)
    }

    private func decodeDevices(_ data: Data) throws -> [TrustedDevice] {
        let decoded = try decoder.decode(BoundedTrustedDeviceCollection.self, from: data)
        return decoded.devices
    }

    private func loadUnlocked(from directory: TrustedDeviceStoreDirectory) throws -> [TrustedDevice] {
        guard let data = try readStoreBytesUnlocked(from: directory) else { return [] }
        return try decodeDevices(data)
    }

    @discardableResult
    private func saveUnlocked(
        _ devices: [TrustedDevice],
        in directory: TrustedDeviceStoreDirectory
    ) throws -> Data {
        try validateDevices(devices)
        try validateDestination(in: directory)
        let data = try encoder.encode(devices)
        try enforceLimit(
            data.count,
            resource: "trusted device store bytes",
            limit: limits.maxStoreBytes
        )
        let temporaryName = ".\(directory.storeName).tmp.\(getpid()).\(UUID().uuidString)"
        let descriptor = Darwin.openat(
            directory.descriptor,
            temporaryName,
            O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW,
            Self.filePermissions
        )
        guard descriptor >= 0 else {
            throw ioFailure("create trusted device temporary file")
        }
        let temporaryURL = directory.url.appendingPathComponent(temporaryName)
        var shouldRemoveTemporaryFile = true
        defer {
            Darwin.close(descriptor)
            if shouldRemoveTemporaryFile {
                Darwin.unlinkat(directory.descriptor, temporaryName, 0)
            }
        }
        synchronizationHooks.didCreateTemporaryFile?(temporaryURL)
        try validateRegularFileDescriptor(descriptor, failure: .unsafeStoreFile)
        try secureDescriptor(
            descriptor,
            permissions: Self.filePermissions,
            operation: "secure trusted device temporary file"
        )
        try writeAll(data, to: descriptor)
        try syncFile(descriptor)

        synchronizationHooks.didPrepareAtomicReplacement?(temporaryURL)
        guard Darwin.renameat(
            directory.descriptor,
            temporaryName,
            directory.descriptor,
            directory.storeName
        ) == 0 else {
            throw ioFailure("replace trusted device store")
        }
        shouldRemoveTemporaryFile = false
        guard synchronizationHooks.shouldFailDirectorySyncAfterRename?() != true,
              syncDescriptor(directory.descriptor) else {
            throw TrustedDeviceStoreError.durabilityUncertainAfterRename
        }
        return data
    }

    private func validateDestination(in directory: TrustedDeviceStoreDirectory) throws {
        var metadata = stat()
        guard Darwin.fstatat(
            directory.descriptor,
            directory.storeName,
            &metadata,
            AT_SYMLINK_NOFOLLOW
        ) == 0 else {
            if errno == ENOENT { return }
            throw ioFailure("inspect trusted device destination")
        }
        guard isSafeRegularFile(metadata) else {
            throw TrustedDeviceStoreError.unsafeStoreFile
        }
    }

    private func validateRegularFileDescriptor(
        _ descriptor: Int32,
        failure: TrustedDeviceStoreError
    ) throws {
        var metadata = stat()
        guard Darwin.fstat(descriptor, &metadata) == 0,
              isSafeRegularFile(metadata)
        else {
            throw failure
        }
    }

    private func isSafeRegularFile(_ metadata: stat) -> Bool {
        metadata.st_uid == geteuid()
            && metadata.st_mode & S_IFMT == S_IFREG
            && metadata.st_nlink == 1
    }

    private func readAll(from descriptor: Int32) throws -> Data {
        var metadata = stat()
        guard Darwin.fstat(descriptor, &metadata) == 0,
              metadata.st_size >= 0
        else {
            throw TrustedDeviceStoreError.unsafeStoreFile
        }
        if UInt64(metadata.st_size) > UInt64(limits.maxStoreBytes) {
            throw TrustedDeviceStoreResourceLimitError(
                resource: "trusted device store bytes",
                limit: limits.maxStoreBytes,
                actual: boundedStoreActualCount(metadata.st_size)
            )
        }

        var data = Data()
        data.reserveCapacity(Int(metadata.st_size))
        var buffer = [UInt8](repeating: 0, count: 64 * 1024)
        while true {
            let requestedCount = min(buffer.count, limits.maxStoreBytes - data.count + 1)
            let count = Darwin.read(descriptor, &buffer, requestedCount)
            if count < 0 && errno == EINTR { continue }
            guard count >= 0 else {
                throw ioFailure("read trusted device store")
            }
            guard count > 0 else { return data }

            let actualCount = data.count + count
            guard actualCount <= limits.maxStoreBytes else {
                throw TrustedDeviceStoreResourceLimitError(
                    resource: "trusted device store bytes",
                    limit: limits.maxStoreBytes,
                    actual: actualCount
                )
            }
            data.append(contentsOf: buffer[0..<count])
        }
    }

    private func secureDescriptor(
        _ descriptor: Int32,
        permissions: mode_t,
        operation: String
    ) throws {
        guard Darwin.fchmod(descriptor, permissions) == 0 else {
            throw ioFailure(operation)
        }
        guard let emptyACL = Darwin.acl_init(0) else {
            throw ioFailure(operation)
        }
        defer { _ = Darwin.acl_free(UnsafeMutableRawPointer(emptyACL)) }
        while Darwin.acl_set_fd_np(descriptor, emptyACL, ACL_TYPE_EXTENDED) != 0 {
            if errno == EINTR { continue }
            throw ioFailure(operation)
        }
    }

    private func validateDevice(_ device: TrustedDevice) throws {
        try validateTrustedDevice(device, limits: limits)
    }

    private func validatePairMutationIdentity(
        deviceID: String,
        expectedPublicKeyBase64: String
    ) throws {
        try validateField(
            deviceID,
            resource: "device identifier UTF-8 bytes",
            limit: limits.maxIdentifierUTF8Bytes
        )
        try validateField(
            expectedPublicKeyBase64,
            resource: "device public key UTF-8 bytes",
            limit: limits.maxPublicKeyUTF8Bytes
        )
    }

    private func acquireProductionC1AuthorityWritePermit()
        async throws -> ProductionC1AuthorityPublicationWritePermit
    {
        do {
            return try await productionC1AuthorityPublicationGate.acquireWrite()
        } catch let error as CancellationError {
            throw error
        } catch ProductionC1AuthorityPublicationGateError.capacityExceeded {
            throw TrustedDeviceStoreError.authorityPublicationOverloaded
        }
    }

    /// A successful rename followed by failed directory sync has ambiguous
    /// durability. The old authority must not be republished in that case.
    /// All pre-rename failures deliberately leave the old session live.
    private func fenceDurabilityUncertainMutation(
        _ error: Error,
        candidate: (digest: String, isRevocation: Bool)?
    ) async {
        guard let candidate,
              error as? TrustedDeviceStoreError
                == .durabilityUncertainAfterRename,
              let coordinator = productionC1ExactBoundStartCoordinatorCache else {
            return
        }
        if candidate.isRevocation {
            await coordinator.fenceRevoked(
                pairAuthorityDigest: candidate.digest
            )
        } else {
            await coordinator.fenceAuthorityAdvance(
                previousPairAuthorityDigest: candidate.digest
            )
        }
    }

    private func validateDevices(_ devices: [TrustedDevice]) throws {
        try enforceLimit(
            devices.count,
            resource: "trusted device rows",
            limit: limits.maxDevices
        )
        var deviceIdentifiers = Set<String>()
        for device in devices {
            try validateDevice(device)
            guard deviceIdentifiers.insert(device.id).inserted else {
                throw TrustedDeviceStoreError.ambiguousDeviceIdentifier
            }
        }
    }

    private func validateField(
        _ value: String,
        resource: String,
        limit: Int
    ) throws {
        try enforceLimit(value.utf8.count, resource: resource, limit: limit)
    }

    private func enforceLimit(
        _ actual: Int,
        resource: String,
        limit: Int
    ) throws {
        guard actual <= limit else {
            throw TrustedDeviceStoreResourceLimitError(
                resource: resource,
                limit: limit,
                actual: actual
            )
        }
    }

    private func writeAll(_ data: Data, to descriptor: Int32) throws {
        try data.withUnsafeBytes { buffer in
            guard let baseAddress = buffer.baseAddress else { return }
            var offset = 0
            while offset < buffer.count {
                let count = Darwin.write(
                    descriptor,
                    baseAddress.advanced(by: offset),
                    buffer.count - offset
                )
                if count < 0 && errno == EINTR { continue }
                guard count > 0 else {
                    throw ioFailure("write trusted device store")
                }
                offset += count
            }
        }
    }

    private func syncFile(_ descriptor: Int32) throws {
        while Darwin.fcntl(descriptor, F_FULLFSYNC) != 0 {
            let syncError = errno
            if syncError == EINTR { continue }
            if syncError == EINVAL || syncError == ENOTSUP {
                guard syncDescriptor(descriptor) else {
                    throw ioFailure("sync trusted device store", code: errno)
                }
                return
            }
            throw ioFailure("sync trusted device store", code: syncError)
        }
    }

    private func syncDescriptor(_ descriptor: Int32) -> Bool {
        while Darwin.fsync(descriptor) != 0 {
            if errno != EINTR { return false }
        }
        return true
    }

    private func monotonicNanoseconds() throws -> UInt64 {
        var value = timespec()
        guard Darwin.clock_gettime(CLOCK_MONOTONIC, &value) == 0,
              value.tv_sec >= 0,
              value.tv_nsec >= 0
        else {
            throw TrustedDeviceStoreError.lockUnavailable
        }
        return UInt64(value.tv_sec) * 1_000_000_000 + UInt64(value.tv_nsec)
    }

    private func ioFailure(
        _ operation: String,
        code: Int32 = errno
    ) -> TrustedDeviceStoreError {
        .ioFailure(operation: operation, code: code)
    }
}

private struct ValidatedProductionC1EndpointAdmissionState {
    let ledger: ProductionC1EndpointGrantLedgerState
    let markers: [StoredProductionC1EndpointCommitMarker]
}

private func validatedEndpointState(
    for device: TrustedDevice
) throws -> ValidatedProductionC1EndpointAdmissionState? {
    guard let stored = device.productionC1EndpointAdmissionState else { return nil }
    guard stored.version == StoredProductionC1EndpointAdmissionState.schemaVersion,
          let pairSnapshot = device.productionPairState,
          !stored.commitMarkerCanonicalBytes.isEmpty,
          stored.commitMarkerCanonicalBytes.count
            <= ProductionC1EndpointLedgerPersistenceContract.maximumEntries else {
        throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
    }

    let ledger: ProductionC1EndpointGrantLedgerState
    let markers: [StoredProductionC1EndpointCommitMarker]
    do {
        ledger = try ProductionC1EndpointGrantLedgerState(
            persistenceCanonicalBytes: stored.ledgerCanonicalBytes
        )
        markers = try stored.commitMarkerCanonicalBytes.map {
            try StoredProductionC1EndpointCommitMarker(canonicalBytes: $0)
        }
        _ = try ProductionC1EndpointCompoundRecord(
            grantLedger: ledger,
            pairSnapshot: pairSnapshot
        )
    } catch let error as TrustedDeviceStoreError {
        throw error
    } catch {
        throw TrustedDeviceStoreError.productionC1EndpointStateCorrupt
    }
    guard markers.count == ledger.entries.count else {
        throw TrustedDeviceStoreError.productionC1EndpointCommitChainMismatch
    }

    let deviceIDDigest = trustedDeviceStoreIdentityDigest(
        domain: "AetherLink trusted-device identifier v1",
        value: device.id
    )
    let keyDigest = trustedDeviceStoreIdentityDigest(
        domain: "AetherLink trusted-device public key v1",
        value: device.publicKeyBase64
    )
    guard let chainLength = UInt64(exactly: markers.count),
          pairSnapshot.localRevision > chainLength,
          pairSnapshot.consumedEntries.count >= markers.count else {
        throw TrustedDeviceStoreError.productionC1EndpointCommitChainMismatch
    }
    let initialRemainingResult = ledger.remainingGrants.addingReportingOverflow(chainLength)
    guard !initialRemainingResult.overflow else {
        throw TrustedDeviceStoreError.productionC1EndpointCommitChainMismatch
    }
    let initialPairRevision = pairSnapshot.localRevision - chainLength
    let initialConsumedCount = pairSnapshot.consumedEntries.count - markers.count
    var reconstructedPair = try ProductionPairStateSnapshot(
        authority: pairSnapshot.authority,
        localRevision: initialPairRevision,
        consumedEntries: Array(pairSnapshot.consumedEntries.prefix(initialConsumedCount)),
        transitionHistory: pairSnapshot.transitionHistory
    )
    var reconstructedLedger = try ProductionC1EndpointGrantLedgerState(
        revision: 1,
        pairAuthorityDigest: ledger.pairAuthorityDigest,
        pairLocalRevision: initialPairRevision,
        remainingGrants: initialRemainingResult.partialValue,
        retentionLimit: ledger.retentionLimit
    )
    var previousMarkerDigest: String?
    var previousCommittedCompoundDigest = try ProductionC1EndpointCompoundRecord(
        grantLedger: reconstructedLedger,
        pairSnapshot: reconstructedPair
    ).digestHex()
    for (offset, pair) in zip(markers, ledger.entries).enumerated() {
        let (marker, entry) = pair
        let nextPairRevisionResult = reconstructedPair.localRevision.addingReportingOverflow(1)
        guard !nextPairRevisionResult.overflow,
              reconstructedLedger.remainingGrants > 0 else {
            throw TrustedDeviceStoreError.productionC1EndpointCommitChainMismatch
        }
        let nextPair = try ProductionPairStateSnapshot(
            authority: reconstructedPair.authority,
            localRevision: nextPairRevisionResult.partialValue,
            consumedEntries: reconstructedPair.consumedEntries + [
                try ProductionPairConsumedSession(
                    sessionId: entry.sessionId,
                    transcriptDigest: entry.transcriptDigest
                ),
            ],
            transitionHistory: reconstructedPair.transitionHistory
        )
        let nextLedger = try ProductionC1EndpointGrantLedgerState(
            revision: reconstructedLedger.revision + 1,
            pairAuthorityDigest: reconstructedLedger.pairAuthorityDigest,
            pairLocalRevision: nextPair.localRevision,
            remainingGrants: reconstructedLedger.remainingGrants - 1,
            retentionLimit: reconstructedLedger.retentionLimit,
            entries: reconstructedLedger.entries + [entry]
        )
        let nextPairDigest = try nextPair.digestHex()
        let nextLedgerDigest = try nextLedger.snapshotDigestHex()
        let nextCompoundDigest = try ProductionC1EndpointCompoundRecord(
            grantLedger: nextLedger,
            pairSnapshot: nextPair
        ).digestHex()
        guard marker.sequence == UInt32(offset + 1),
              marker.deviceIDDigest == deviceIDDigest,
              marker.trustedPublicKeyDigest == keyDigest,
              marker.admissionID == entry.admissionId,
              marker.bindingDigest == entry.bindingDigest,
              marker.sessionID == entry.sessionId,
              marker.routeAuthorizationDigest == entry.routeAuthorizationDigest,
              marker.grantAuthorizationDigest == entry.grantAuthorizationDigest,
              marker.pairAuthorityDigest == nextLedger.pairAuthorityDigest,
              marker.endpointEntryDigest == trustedDeviceStoreEndpointEntryDigest(entry),
              marker.previousMarkerDigest == previousMarkerDigest,
              marker.expectedCompoundDigest == previousCommittedCompoundDigest,
              marker.ledgerRevision == entry.committedRevision,
              marker.ledgerRevision == nextLedger.revision,
              marker.pairLocalRevision == nextPair.localRevision,
              marker.committedPairSnapshotDigest == entry.pairSnapshotDigest,
              marker.committedPairSnapshotDigest == nextPairDigest,
              marker.committedLedgerSnapshotDigest == nextLedgerDigest,
              marker.committedCompoundDigest == nextCompoundDigest else {
            throw TrustedDeviceStoreError.productionC1EndpointCommitChainMismatch
        }
        previousMarkerDigest = try marker.digestHex()
        previousCommittedCompoundDigest = marker.committedCompoundDigest
        reconstructedPair = nextPair
        reconstructedLedger = nextLedger
    }

    guard reconstructedPair == pairSnapshot,
          reconstructedLedger == ledger else {
        throw TrustedDeviceStoreError.productionC1EndpointCommitChainMismatch
    }
    return ValidatedProductionC1EndpointAdmissionState(ledger: ledger, markers: markers)
}

private func trustedDeviceStoreIdentityDigest(domain: String, value: String) -> String {
    var bytes = Data(domain.utf8)
    bytes.append(0)
    trustedDeviceStoreAppendFramed(Data(value.utf8), to: &bytes)
    return trustedDeviceStoreDigestHex(bytes)
}

private func trustedDeviceStoreEndpointEntryDigest(
    _ entry: ProductionC1EndpointGrantEntry
) -> String {
    var bytes = Data(
        "AetherLink C1 endpoint grant entry marker v2 object4+object26".utf8
    )
    bytes.append(0)
    for value in [
        entry.admissionId, entry.bindingDigest, entry.routeGrantDigest, entry.sessionId,
        entry.transcriptDigest, entry.routeAuthorizationDigest,
        entry.grantAuthorizationDigest,
        entry.connectorInputCommitmentDigest, entry.pairSnapshotDigest,
    ] {
        trustedDeviceStoreAppendFramed(Data(value.utf8), to: &bytes)
    }
    var revision = entry.committedRevision.bigEndian
    withUnsafeBytes(of: &revision) { bytes.append(contentsOf: $0) }
    return trustedDeviceStoreDigestHex(bytes)
}

private func trustedDeviceStoreAppendFramed(_ value: Data, to result: inout Data) {
    var length = UInt32(value.count).bigEndian
    withUnsafeBytes(of: &length) { result.append(contentsOf: $0) }
    result.append(value)
}

private func trustedDeviceStoreDigestHex(_ value: Data) -> String {
    SHA256.hash(data: value).map { String(format: "%02x", $0) }.joined()
}

private func trustedDeviceStoreIsDigest(_ value: String) -> Bool {
    value.utf8.count == 64 && value.utf8.allSatisfy {
        (48...57).contains($0) || (97...102).contains($0)
    }
}

private func trustedDeviceStoreIsSessionID(_ value: String) -> Bool {
    value.utf8.count == 32 && value.utf8.allSatisfy {
        (48...57).contains($0) || (97...102).contains($0)
    }
}

private struct BoundedTrustedDeviceCollection: Decodable {
    let devices: [TrustedDevice]

    init(from decoder: Decoder) throws {
        guard let limits = decoder.userInfo[trustedDeviceStoreLimitsUserInfoKey]
            as? TrustedDeviceStoreLimits
        else {
            throw TrustedDeviceStoreError.unsafeStoreFile
        }
        var container = try decoder.unkeyedContainer()
        if let declaredCount = container.count {
            try enforceTrustedDeviceLimit(
                declaredCount,
                resource: "trusted device rows",
                limit: limits.maxDevices
            )
        }

        var devices: [TrustedDevice] = []
        var deviceIdentifiers = Set<String>()
        devices.reserveCapacity(min(container.count ?? 0, limits.maxDevices))
        while !container.isAtEnd {
            guard devices.count < limits.maxDevices else {
                throw TrustedDeviceStoreResourceLimitError(
                    resource: "trusted device rows",
                    limit: limits.maxDevices,
                    actual: limits.maxDevices + 1
                )
            }
            let device = try container.decode(TrustedDevice.self)
            try validateTrustedDevice(device, limits: limits)
            guard deviceIdentifiers.insert(device.id).inserted else {
                throw TrustedDeviceStoreError.ambiguousDeviceIdentifier
            }
            devices.append(device)
        }
        self.devices = devices
    }
}

private func validateTrustedDevice(
    _ device: TrustedDevice,
    limits: TrustedDeviceStoreLimits
) throws {
    try enforceTrustedDeviceLimit(
        device.id.utf8.count,
        resource: "device identifier UTF-8 bytes",
        limit: limits.maxIdentifierUTF8Bytes
    )
    try enforceTrustedDeviceLimit(
        device.name.utf8.count,
        resource: "device name UTF-8 bytes",
        limit: limits.maxNameUTF8Bytes
    )
    try enforceTrustedDeviceLimit(
        device.publicKeyBase64.utf8.count,
        resource: "device public key UTF-8 bytes",
        limit: limits.maxPublicKeyUTF8Bytes
    )
    _ = try validatedEndpointState(for: device)
}

private func enforceTrustedDeviceLimit(
    _ actual: Int,
    resource: String,
    limit: Int
) throws {
    guard actual <= limit else {
        throw TrustedDeviceStoreResourceLimitError(
            resource: resource,
            limit: limit,
            actual: actual
        )
    }
}

private func boundedStoreActualCount(_ value: off_t) -> Int {
    value > off_t(Int.max) ? Int.max : Int(value)
}
