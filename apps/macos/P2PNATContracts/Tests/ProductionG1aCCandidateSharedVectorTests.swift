import CryptoKit
import Foundation
import XCTest
@testable import P2PNATContracts

final class ProductionG1aCCandidateSharedVectorTests: XCTestCase {
    private let candidateFixtureSHA256 =
        "e6bc666dbf9fded82d5681fdcfdc2c4c9cd5fa197135fc0673569d35656236af"
    private let legacyFixtureSHA256 =
        "c25c0f4d74b0029f060bcedf31b19ef95c57a0a0e6708a741175c8cedeb611f3"

    func testCandidateFixtureNamespaceCanonicalObjectsAndPinnedHashes() throws {
        let fixture = try CandidateSharedVectorFixture.load()

        XCTAssertEqual(sha256Hex(fixture.rawData), candidateFixtureSHA256)
        XCTAssertEqual(try fixture.string("schema"), "aetherlink-production-g1a-c-candidate-v1-vectors")
        XCTAssertEqual(try fixture.uint64("version"), 1)
        XCTAssertEqual(try fixture.string("magic"), "ALS1")
        XCTAssertEqual(try fixture.string("artifactMagic"), "ALP1")
        XCTAssertEqual(try fixture.string("suite"), ProductionC1Contract.suite)
        XCTAssertEqual(try fixture.string("signatureAlgorithm"), ProductionC1Contract.signatureAlgorithm)
        XCTAssertEqual(
            try fixture.expectedString("operationOrder"),
            "client_publish,runtime_fetch_client,runtime_publish,client_fetch_runtime"
        )
        XCTAssertEqual(
            try fixture.operationStrings("wireName").joined(separator: ","),
            try fixture.expectedString("operationOrder")
        )
        XCTAssertFalse(try fixture.expectedBool("productionDurabilityClaim"))
        XCTAssertEqual(
            try fixture.expectedString("durabilityScope"),
            "synthetic_contract_readiness_only"
        )
        XCTAssertTrue(try fixture.syntheticBool("testOnly"))

        let legacyRecord = try fixture.dictionary("legacyFixture")
        XCTAssertEqual(
            try fixture.string(in: legacyRecord, "expectedSha256Hex"),
            legacyFixtureSHA256
        )
        XCTAssertTrue(try fixture.bool(in: legacyRecord, "mustRemainUnchanged"))
        let legacyURL = fixture.repositoryRoot.appendingPathComponent(
            try fixture.string(in: legacyRecord, "path")
        )
        XCTAssertEqual(sha256Hex(try Data(contentsOf: legacyURL)), legacyFixtureSHA256)

        let expectedTypes: [String: UInt8] = [
            "authority": 8,
            "authorizationClientFetchRuntime": 3,
            "authorizationClientPublish": 2,
            "authorizationRuntimeFetchClient": 3,
            "authorizationRuntimePublish": 2,
            "candidateSecureSessionTranscript": 7,
            "capabilityClientFetchRuntime": 24,
            "capabilityClientPublish": 23,
            "capabilityRuntimeFetchClient": 24,
            "capabilityRuntimePublish": 23,
            "endpointProofClientFetchRuntime": 27,
            "endpointProofClientPublish": 27,
            "endpointProofRuntimeFetchClient": 27,
            "endpointProofRuntimePublish": 27,
            "finalP2PDirectAuthorization": 4,
            "p2pConnector": 15,
            "p2pGrantAuthorization": 26,
            "p2pGrantEvidence": 25,
            "p2pRouteCapability": 13,
            "p2pRoutePlan": 14,
            "preauthorizationSessionContext": 18,
            "receiptClientFetchRuntime": 28,
            "receiptClientPublish": 28,
            "receiptRuntimeFetchClient": 28,
            "receiptRuntimePublish": 28,
            "serviceKeyset": 10,
        ]
        XCTAssertEqual(Set(fixture.objectNames), Set(expectedTypes.keys))
        for name in expectedTypes.keys.sorted() {
            let canonical = try fixture.canonical(name)
            XCTAssertEqual(canonical[canonical.startIndex + 4], expectedTypes[name], name)
            XCTAssertEqual(canonical.count, try fixture.canonicalByteCount(name), name)
            XCTAssertEqual(sha256Hex(canonical), try fixture.canonicalDigest(name), name)
            XCTAssertEqual(try roundTrip(name: name, canonical: canonical), canonical, name)
        }

        for name in ["clientCandidateBatch", "runtimeCandidateBatch"] {
            let canonical = try fixture.artifactCanonical(name)
            let decoded = try CandidateBatch(canonicalBytes: canonical)
            XCTAssertEqual(decoded.canonicalBytes(), canonical, name)
            XCTAssertEqual(canonical.count, try fixture.artifactCanonicalByteCount(name), name)
            XCTAssertEqual(sha256Hex(canonical), try fixture.artifactDigest(name), name)
        }
        let receiptBytes = try fixture.artifactCanonical("pathValidationReceipt")
        let pathReceipt = try PathValidationReceipt(
            freshCanonicalBytes: receiptBytes,
            now: try fixture.constant("nowMs")
        )
        XCTAssertEqual(pathReceipt.canonicalBytes(), receiptBytes)
        XCTAssertEqual(
            sha256Hex(receiptBytes),
            try fixture.artifactDigest("pathValidationReceipt")
        )

        let mutationIds = Set(try fixture.mutationIds())
        XCTAssertTrue([
            "grant_receipt_reorder",
            "grant_duplicate_receipt",
            "grant_other_ledger_chain",
            "transcript_legacy_final_auth",
        ].allSatisfy(mutationIds.contains))
    }

    func testCandidateFixtureVerifiesSignaturesPlanReceiptsGrantAndTranscript() throws {
        let fixture = try CandidateSharedVectorFixture.load()
        let chain = try verifiedChain(fixture)

        XCTAssertEqual(
            try chain.grant.evidence.digestHex(),
            try fixture.derived("grantEvidenceDigest")
        )
        XCTAssertEqual(
            chain.grant.grantAuthorization.digestHex,
            try fixture.derived("grantAuthorizationDigest")
        )
        XCTAssertEqual(
            chain.transcript.digestHex,
            try fixture.derived("secureSessionTranscriptDigest")
        )

        let grantAuthorizationBytes = try fixture.canonical("p2pGrantAuthorization")
        XCTAssertEqual(chain.transcript.routeAuthDigest, sha256Hex(grantAuthorizationBytes))
        XCTAssertEqual(chain.transcript.routeAuthDigest, try fixture.derived("grantAuthorizationDigest"))
        XCTAssertNotEqual(
            chain.transcript.routeAuthDigest,
            sha256Hex(try fixture.canonical("finalP2PDirectAuthorization"))
        )
    }

    func testCandidateFixtureCoreMutationsFailClosed() throws {
        let fixture = try CandidateSharedVectorFixture.load()
        let chain = try verifiedChain(fixture)
        let now = try fixture.constant("nowMs")

        var reordered = chain.receipts
        reordered.swapAt(0, 1)
        assertCandidateError(.authorityMismatch) {
            _ = try ProductionC1CandidateVerifier.deriveGrantEvidence(
                plan: chain.plan,
                routeAuthorizations: chain.authorizations,
                operationReceipts: reordered,
                initiatorRole: .client,
                authority: chain.authority,
                nowMs: now
            )
        }

        var duplicate = chain.receipts
        duplicate[3] = duplicate[0]
        assertCandidateError(.requestConflict) {
            _ = try ProductionC1CandidateVerifier.deriveGrantEvidence(
                plan: chain.plan,
                routeAuthorizations: chain.authorizations,
                operationReceipts: duplicate,
                initiatorRole: .client,
                authority: chain.authority,
                nowMs: now
            )
        }

        var wrongChain = chain.receipts
        wrongChain[0] = try otherLedgerFirstReceipt(fixture: fixture, chain: chain)
        assertCandidateError(.revisionMismatch) {
            _ = try ProductionC1CandidateVerifier.deriveGrantEvidence(
                plan: chain.plan,
                routeAuthorizations: chain.authorizations,
                operationReceipts: wrongChain,
                initiatorRole: .client,
                authority: chain.authority,
                nowMs: now
            )
        }

        let legacyFinalDigest = sha256Hex(try fixture.canonical("finalP2PDirectAuthorization"))
        let legacyTranscriptBytes = try replacingTLVFields(
            in: fixture.canonical("candidateSecureSessionTranscript"),
            replacements: [21: Data(legacyFinalDigest.utf8)]
        )
        let legacyTranscript = try ProductionSecureSessionTranscript(
            canonicalBytes: legacyTranscriptBytes
        )
        let key = try fixture.syntheticData("keyConfirmationKeyHex")
        let peerConfirmation = try ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            transcript: legacyTranscript,
            grantAuthorization: chain.grant.grantAuthorization,
            confirmingRole: .runtime,
            key: key
        )
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
                transcript: legacyTranscript,
                verifiedGrant: chain.grant,
                connectorInput: chain.connectorInput,
                localRole: .client,
                keyConfirmationKey: key,
                presentedPeerKeyConfirmation: peerConfirmation,
                authority: chain.authority,
                nowMs: now
            )
        }
    }

    func testProductionCryptoVectorMaterialConfirmationsAndRecordsMatchExactly() throws {
        let fixture = try CandidateSharedVectorFixture.load()
        let crypto = try ProductionCryptoSharedVectorFixture.load()
        let chain = try verifiedChain(fixture)
        let now = try fixture.constant("nowMs")
        let clientBinding = try keyScheduleBinding(
            fixture: fixture,
            chain: chain,
            role: .client
        )
        let runtimeBinding = try keyScheduleBinding(
            fixture: fixture,
            chain: chain,
            role: .runtime
        )

        let clientMaterial = try ProductionSecureSessionCrypto.vectorMaterial(
            binding: clientBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .client),
            nowMs: now
        )
        let runtimeMaterial = try ProductionSecureSessionCrypto.vectorMaterial(
            binding: runtimeBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .runtime),
            nowMs: now
        )
        for material in [clientMaterial, runtimeMaterial] {
            XCTAssertEqual(material.bindingDigest, try crypto.data("expected", "bindingHashHex"))
            XCTAssertEqual(material.sharedSecret, try crypto.data("expected", "sharedSecretHex"))
            XCTAssertEqual(material.prk, try crypto.data("expected", "hkdfPrkHex"))
            XCTAssertEqual(material.rootInfo, try crypto.data("expected", "hkdfRootInfoHex"))
            XCTAssertEqual(material.rootOutput, try crypto.data("expected", "hkdfOkmHex"))
            XCTAssertEqual(
                material.clientConfirmationKey,
                try crypto.data("expected", "keys", "clientConfirmationKeyHex")
            )
            XCTAssertEqual(
                material.runtimeConfirmationKey,
                try crypto.data("expected", "keys", "runtimeConfirmationKeyHex")
            )
            XCTAssertEqual(
                material.clientEpoch0Secret,
                try crypto.data("expected", "keys", "clientEpoch0SecretHex")
            )
            XCTAssertEqual(
                material.runtimeEpoch0Secret,
                try crypto.data("expected", "keys", "runtimeEpoch0SecretHex")
            )
        }
        try assertEpochMaterial(
            roleByte: 1,
            roleName: "client",
            epochZeroSecret: clientMaterial.clientEpoch0Secret,
            bindingDigest: clientMaterial.bindingDigest,
            fixture: crypto
        )
        try assertEpochMaterial(
            roleByte: 2,
            roleName: "runtime",
            epochZeroSecret: clientMaterial.runtimeEpoch0Secret,
            bindingDigest: clientMaterial.bindingDigest,
            fixture: crypto
        )

        let pair = try activatedPair(
            fixture: fixture,
            clientBinding: clientBinding,
            runtimeBinding: runtimeBinding
        )
        XCTAssertEqual(
            pair.clientConfirmation,
            try crypto.data("expected", "confirmations", "client", "canonicalHex")
        )
        XCTAssertEqual(
            pair.runtimeConfirmation,
            try crypto.data("expected", "confirmations", "runtime", "canonicalHex")
        )

        let clientApplication = try crypto.data(
            "expected", "records", "clientApplication0", "plaintextHex"
        )
        let clientRecord = try pair.clientCipher.sealApplication(clientApplication, nowMs: now)
        XCTAssertEqual(
            clientRecord.record.canonicalBytes(),
            try crypto.data("expected", "records", "clientApplication0", "canonicalHex")
        )
        XCTAssertEqual(
            try pair.runtimeCipher.open(clientRecord.record, nowMs: now).openedContent,
            .application(clientApplication)
        )

        let runtimeApplication = try crypto.data(
            "expected", "records", "runtimeApplication0", "plaintextHex"
        )
        let runtimeRecord = try pair.runtimeCipher.sealApplication(runtimeApplication, nowMs: now)
        XCTAssertEqual(
            runtimeRecord.record.canonicalBytes(),
            try crypto.data("expected", "records", "runtimeApplication0", "canonicalHex")
        )
        XCTAssertEqual(
            try pair.clientCipher.open(runtimeRecord.record, nowMs: now).openedContent,
            .application(runtimeApplication)
        )

        let update = try pair.clientCipher.sealKeyUpdate(nowMs: now)
        XCTAssertEqual(
            update.record.canonicalBytes(),
            try crypto.data("expected", "records", "clientKeyUpdate1", "canonicalHex")
        )
        XCTAssertEqual(
            try pair.runtimeCipher.open(update.record, nowMs: now).openedContent,
            .keyUpdate(nextEpoch: 1)
        )

        let epochOneApplication = try crypto.data(
            "expected", "records", "clientEpoch1Application0", "plaintextHex"
        )
        let epochOneRecord = try pair.clientCipher.sealApplication(epochOneApplication, nowMs: now)
        XCTAssertEqual(
            epochOneRecord.record.canonicalBytes(),
            try crypto.data("expected", "records", "clientEpoch1Application0", "canonicalHex")
        )
        XCTAssertEqual(
            try pair.runtimeCipher.open(epochOneRecord.record, nowMs: now).openedContent,
            .application(epochOneApplication)
        )
    }

    func testProductionCryptoDerivationAndConfirmationFailuresAreClosed() throws {
        let fixture = try CandidateSharedVectorFixture.load()
        let chain = try verifiedChain(fixture)
        let now = try fixture.constant("nowMs")
        let clientBinding = try keyScheduleBinding(
            fixture: fixture,
            chain: chain,
            role: .client
        )
        let runtimeBinding = try keyScheduleBinding(
            fixture: fixture,
            chain: chain,
            role: .runtime
        )

        let mismatched = try ephemeralKey(fixture, role: .runtime)
        XCTAssertTrue(mismatched.testOnlyRetainsPrivateKey)
        assertCryptoError(.roleMismatch) {
            _ = try ProductionSecureSessionCrypto.vectorMaterial(
                binding: clientBinding,
                localEphemeralKey: mismatched,
                nowMs: now
            )
        }
        XCTAssertTrue(
            mismatched.testOnlyRetainsPrivateKey,
            "a public-key role mismatch must fail before consuming the private key"
        )
        _ = try ProductionSecureSessionCrypto.vectorMaterial(
            binding: runtimeBinding,
            localEphemeralKey: mismatched,
            nowMs: now
        )
        XCTAssertFalse(mismatched.testOnlyRetainsPrivateKey)
        let consumed = try ephemeralKey(fixture, role: .client)
        XCTAssertTrue(consumed.testOnlyRetainsPrivateKey)
        _ = try ProductionSecureSessionCrypto.vectorMaterial(
            binding: clientBinding,
            localEphemeralKey: consumed,
            nowMs: now
        )
        XCTAssertFalse(
            consumed.testOnlyRetainsPrivateKey,
            "a one-use ECDH handle must release its retained private-key reference"
        )
        assertCryptoError(.ephemeralKeyAlreadyUsed) {
            _ = try ProductionSecureSessionCrypto.vectorMaterial(
                binding: clientBinding,
                localEphemeralKey: consumed,
                nowMs: now
            )
        }

        let object4Digest = sha256Hex(try fixture.canonical("finalP2PDirectAuthorization"))
        let substitutedBytes = try replacingTLVFields(
            in: fixture.canonical("candidateSecureSessionTranscript"),
            replacements: [21: Data(object4Digest.utf8)]
        )
        let substituted = try ProductionSecureSessionTranscript(canonicalBytes: substitutedBytes)
        assertCandidateError(.routeMismatch) {
            _ = try ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
                transcript: substituted,
                verifiedGrant: chain.grant,
                localRole: .client,
                authority: chain.authority,
                nowMs: now
            )
        }

        let client = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: clientBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .client),
            nowMs: now
        )
        let runtime = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: runtimeBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .runtime),
            nowMs: now
        )
        let clientConfirmation = try client.localConfirmation(nowMs: now)
        let runtimeConfirmation = try runtime.localConfirmation(nowMs: now)
        assertCryptoError(.confirmationIncomplete) {
            _ = try client.makeCipher(nowMs: now)
        }
        try client.acceptPeerConfirmation(runtimeConfirmation, nowMs: now)
        assertCryptoError(.confirmationIncomplete) {
            _ = try client.makeCipher(nowMs: now)
        }
        try client.markLocalConfirmationSent(clientConfirmation, nowMs: now)
        try client.markLocalConfirmationSent(clientConfirmation, nowMs: now)
        try client.acceptPeerConfirmation(runtimeConfirmation, nowMs: now)
        _ = try client.makeCipher(nowMs: now)

        let reflected = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: clientBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .client),
            nowMs: now
        )
        let reflectedLocal = try reflected.localConfirmation(nowMs: now)
        assertCryptoError(.invalidConfirmation) {
            try reflected.acceptPeerConfirmation(reflectedLocal, nowMs: now)
        }
        assertCryptoError(.closed) {
            _ = try reflected.localConfirmation(nowMs: now)
        }

        let flipped = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: clientBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .client),
            nowMs: now
        )
        var flippedProof = runtimeConfirmation
        flippedProof[flippedProof.index(before: flippedProof.endIndex)] ^= 1
        assertCryptoError(.invalidConfirmation) {
            try flipped.acceptPeerConfirmation(flippedProof, nowMs: now)
        }

        let conflict = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: clientBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .client),
            nowMs: now
        )
        try conflict.acceptPeerConfirmation(runtimeConfirmation, nowMs: now)
        try conflict.acceptPeerConfirmation(runtimeConfirmation, nowMs: now)
        assertCryptoError(.confirmationConflict) {
            try conflict.acceptPeerConfirmation(flippedProof, nowMs: now)
        }
        assertCryptoError(.closed) {
            _ = try conflict.localConfirmation(nowMs: now)
        }
    }

    func testProductionCryptoRecordOrderingAuthenticationAndKeyUpdates() throws {
        let fixture = try CandidateSharedVectorFixture.load()
        let crypto = try ProductionCryptoSharedVectorFixture.load()
        let chain = try verifiedChain(fixture)
        let now = try fixture.constant("nowMs")
        let clientBinding = try keyScheduleBinding(fixture: fixture, chain: chain, role: .client)
        let runtimeBinding = try keyScheduleBinding(fixture: fixture, chain: chain, role: .runtime)
        let pair = try activatedPair(
            fixture: fixture,
            clientBinding: clientBinding,
            runtimeBinding: runtimeBinding
        )
        let plaintext = try crypto.data("expected", "records", "clientApplication0", "plaintextHex")
        let original = try pair.clientCipher.sealApplication(plaintext, nowMs: now).record

        let wrongSession = try ProductionSecureSessionEncryptedRecord(
            sessionId: String(repeating: "0", count: 32),
            senderRole: original.senderRole,
            epoch: original.epoch,
            sequence: original.sequence,
            contentType: original.contentType,
            ciphertext: original.ciphertext,
            tag: original.tag
        )
        assertCryptoError(.unexpectedRecord) {
            _ = try pair.runtimeCipher.open(wrongSession, nowMs: now)
        }
        let wrongRole = try ProductionSecureSessionEncryptedRecord(
            sessionId: original.sessionId,
            senderRole: .runtime,
            epoch: original.epoch,
            sequence: original.sequence,
            contentType: original.contentType,
            ciphertext: original.ciphertext,
            tag: original.tag
        )
        assertCryptoError(.unexpectedRecord) {
            _ = try pair.runtimeCipher.open(wrongRole, nowMs: now)
        }
        let gap = try ProductionSecureSessionEncryptedRecord(
            sessionId: original.sessionId,
            senderRole: original.senderRole,
            epoch: original.epoch,
            sequence: 1,
            contentType: original.contentType,
            ciphertext: original.ciphertext,
            tag: original.tag
        )
        assertCryptoError(.unexpectedRecord) {
            _ = try pair.runtimeCipher.open(gap, nowMs: now)
        }
        let futureEpoch = try ProductionSecureSessionEncryptedRecord(
            sessionId: original.sessionId,
            senderRole: original.senderRole,
            epoch: 1,
            sequence: original.sequence,
            contentType: original.contentType,
            ciphertext: original.ciphertext,
            tag: original.tag
        )
        assertCryptoError(.unexpectedRecord) {
            _ = try pair.runtimeCipher.open(futureEpoch, nowMs: now)
        }

        var badTag = original.tag
        badTag[badTag.startIndex] ^= 1
        let tagFlip = try ProductionSecureSessionEncryptedRecord(
            sessionId: original.sessionId,
            senderRole: original.senderRole,
            epoch: original.epoch,
            sequence: original.sequence,
            contentType: original.contentType,
            ciphertext: original.ciphertext,
            tag: badTag
        )
        assertCryptoError(.authenticationFailed) {
            _ = try pair.runtimeCipher.open(tagFlip, nowMs: now)
        }
        var badCiphertext = original.ciphertext
        badCiphertext[badCiphertext.startIndex] ^= 1
        let ciphertextFlip = try ProductionSecureSessionEncryptedRecord(
            sessionId: original.sessionId,
            senderRole: original.senderRole,
            epoch: original.epoch,
            sequence: original.sequence,
            contentType: original.contentType,
            ciphertext: badCiphertext,
            tag: original.tag
        )
        assertCryptoError(.authenticationFailed) {
            _ = try pair.runtimeCipher.open(ciphertextFlip, nowMs: now)
        }
        XCTAssertEqual(
            try pair.runtimeCipher.open(original, nowMs: now).openedContent,
            .application(plaintext),
            "authentication failure must not advance receive sequence"
        )
        assertCryptoError(.unexpectedRecord) {
            _ = try pair.runtimeCipher.open(original, nowMs: now)
        }

        let updatePair = try activatedPair(
            fixture: fixture,
            clientBinding: clientBinding,
            runtimeBinding: runtimeBinding
        )
        let clientMaterial = try ProductionSecureSessionCrypto.vectorMaterial(
            binding: clientBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .client),
            nowMs: now
        )
        let skipped = try authenticatedClientKeyUpdate(
            nextEpoch: 2,
            epoch: 0,
            sequence: 0,
            material: clientMaterial,
            sessionId: chain.transcript.sessionId
        )
        assertCryptoError(.invalidKeyUpdate) {
            _ = try updatePair.runtimeCipher.open(skipped, nowMs: now)
        }

        let validPair = try activatedPair(
            fixture: fixture,
            clientBinding: clientBinding,
            runtimeBinding: runtimeBinding
        )
        var lastUpdate: ProductionSecureSessionEncryptedRecord?
        for expectedEpoch in UInt32(1)...ProductionSecureSessionCryptoContract.maximumEpoch {
            let update = try validPair.clientCipher.sealKeyUpdate(nowMs: now).record
            XCTAssertEqual(
                try validPair.runtimeCipher.open(update, nowMs: now).openedContent,
                .keyUpdate(nextEpoch: expectedEpoch)
            )
            lastUpdate = update
        }
        if let lastUpdate {
            assertCryptoError(.unexpectedRecord) {
                _ = try validPair.runtimeCipher.open(lastUpdate, nowMs: now)
            }
        }
        assertCryptoError(.recordLimitExceeded) {
            _ = try validPair.clientCipher.sealKeyUpdate(nowMs: now)
        }
    }

    func testProductionCryptoSizeTimeAuthorityCloseAndConcurrentSealBoundaries() throws {
        let fixture = try CandidateSharedVectorFixture.load()
        let chain = try verifiedChain(fixture)
        let now = try fixture.constant("nowMs")
        let expiresAt = try fixture.expectedUInt64("expiresAtMs")
        let clientBinding = try keyScheduleBinding(fixture: fixture, chain: chain, role: .client)
        let runtimeBinding = try keyScheduleBinding(fixture: fixture, chain: chain, role: .runtime)

        assertCryptoError(.expired) {
            _ = try ProductionSecureSessionCrypto.deriveHandshake(
                binding: clientBinding,
                localEphemeralKey: ephemeralKey(fixture, role: .client),
                nowMs: expiresAt
            )
        }
        let rollback = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: clientBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .client),
            nowMs: now
        )
        assertCryptoError(.timeRegression) {
            _ = try rollback.localConfirmation(nowMs: now - 1)
        }
        assertCryptoError(.closed) {
            _ = try rollback.localConfirmation(nowMs: now)
        }
        let expiring = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: clientBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .client),
            nowMs: now
        )
        assertCryptoError(.expired) {
            _ = try expiring.localConfirmation(nowMs: expiresAt)
        }

        let revokedAuthority = try ProductionPairAuthorityState(
            pairBindingDigest: chain.authority.pairBindingDigest,
            pairEpoch: chain.authority.pairEpoch,
            clientIdentityFingerprint: chain.authority.clientIdentityFingerprint,
            runtimeIdentityFingerprint: chain.authority.runtimeIdentityFingerprint,
            generation: chain.authority.generation,
            serviceConfigVersion: chain.authority.serviceConfigVersion,
            keysetVersion: chain.authority.keysetVersion,
            revocationCounter: chain.authority.revocationCounter + 1,
            protocolFloor: chain.authority.protocolFloor,
            status: .revoked,
            transitionId: chain.authority.transitionId,
            transitionRequestDigest: chain.authority.transitionRequestDigest,
            acceptedReceiptDigest: chain.authority.acceptedReceiptDigest,
            authorityRevision: chain.authority.authorityRevision + 1
        )
        XCTAssertThrowsError(try ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
            transcript: chain.transcript,
            verifiedGrant: chain.grant,
            localRole: .client,
            authority: revokedAuthority,
            nowMs: now
        ))

        let sized = try activatedPair(
            fixture: fixture,
            clientBinding: clientBinding,
            runtimeBinding: runtimeBinding
        )
        assertCryptoError(.byteLimitExceeded) {
            _ = try sized.clientCipher.sealApplication(
                Data(
                    repeating: 0,
                    count: ProductionSecureSessionCryptoContract.maximumPlaintextBytes + 1
                ),
                nowMs: now
            )
        }
        sized.clientCipher.close()
        assertCryptoError(.closed) {
            _ = try sized.clientCipher.sealApplication(Data(), nowMs: now)
        }

        let concurrent = try activatedPair(
            fixture: fixture,
            clientBinding: clientBinding,
            runtimeBinding: runtimeBinding
        )
        let accumulator = ProductionCryptoConcurrentAccumulator()
        DispatchQueue.concurrentPerform(iterations: 64) { index in
            do {
                let result = try concurrent.clientCipher.sealApplication(
                    Data([UInt8(index)]),
                    nowMs: now
                )
                accumulator.append(result.record.sequence)
            } catch {
                accumulator.append(error)
            }
        }
        XCTAssertTrue(accumulator.errors.isEmpty)
        XCTAssertEqual(accumulator.sequences.sorted(), Array(UInt64(0)..<UInt64(64)))
        XCTAssertEqual(Set(accumulator.sequences).count, 64)
    }

    func testProductionCryptoCapacityOracleExactReserveAndTerminalBoundaries() throws {
        let limits = ProductionSecureSessionCryptoContract.self
        let epochRecordReserve = try ProductionSecureSessionCapacityOracle.application(
            snapshot: counterSnapshot(
                epoch: 0,
                epochRecords: limits.maximumRecordsPerEpoch - 2
            ),
            byteCount: 0
        )
        XCTAssertTrue(epochRecordReserve.keyUpdateRequired)
        assertCryptoError(.keyUpdateRequired) {
            _ = try ProductionSecureSessionCapacityOracle.application(
                snapshot: counterSnapshot(
                    epoch: 0,
                    epochRecords: limits.maximumRecordsPerEpoch - 1
                ),
                byteCount: 0
            )
        }
        XCTAssertEqual(
            try ProductionSecureSessionCapacityOracle.keyUpdateNextEpoch(
                snapshot: counterSnapshot(
                    epoch: 0,
                    epochRecords: limits.maximumRecordsPerEpoch - 1
                )
            ),
            1
        )
        let sessionRecordFinalUpdate = try ProductionSecureSessionCapacityOracle.keyUpdate(
            snapshot: counterSnapshot(
                epoch: 0,
                sessionRecords: limits.maximumRecordsPerSession - 1
            )
        )
        XCTAssertEqual(sessionRecordFinalUpdate.nextEpoch, 1)
        XCTAssertTrue(sessionRecordFinalUpdate.terminalAfterRecord)
        let sessionByteFinalUpdate = try ProductionSecureSessionCapacityOracle.keyUpdate(
            snapshot: counterSnapshot(
                epoch: 0,
                sessionBytes: limits.maximumPlaintextBytesPerSession - 4
            )
        )
        XCTAssertEqual(sessionByteFinalUpdate.nextEpoch, 1)
        XCTAssertTrue(sessionByteFinalUpdate.terminalAfterRecord)
        assertCryptoError(.sessionLimitExceeded) {
            _ = try ProductionSecureSessionCapacityOracle.keyUpdate(
                snapshot: counterSnapshot(
                    epoch: 0,
                    sessionRecords: limits.maximumRecordsPerSession
                )
            )
        }
        assertCryptoError(.sessionLimitExceeded) {
            _ = try ProductionSecureSessionCapacityOracle.keyUpdate(
                snapshot: counterSnapshot(
                    epoch: 0,
                    sessionBytes: limits.maximumPlaintextBytesPerSession - 3
                )
            )
        }

        let epochByteReserve = try ProductionSecureSessionCapacityOracle.application(
            snapshot: counterSnapshot(
                epoch: 0,
                epochBytes: limits.maximumPlaintextBytesPerEpoch - 5
            ),
            byteCount: 1
        )
        XCTAssertTrue(epochByteReserve.keyUpdateRequired)
        assertCryptoError(.keyUpdateRequired) {
            _ = try ProductionSecureSessionCapacityOracle.application(
                snapshot: counterSnapshot(
                    epoch: 0,
                    epochBytes: limits.maximumPlaintextBytesPerEpoch - 4
                ),
                byteCount: 1
            )
        }

        let finalEpochRecord = try ProductionSecureSessionCapacityOracle.application(
            snapshot: counterSnapshot(
                epoch: limits.maximumEpoch,
                epochRecords: limits.maximumRecordsPerEpoch - 1
            ),
            byteCount: 0
        )
        XCTAssertTrue(finalEpochRecord.terminalAfterRecord)
        assertCryptoError(.recordLimitExceeded) {
            _ = try ProductionSecureSessionCapacityOracle.application(
                snapshot: counterSnapshot(
                    epoch: limits.maximumEpoch,
                    epochRecords: limits.maximumRecordsPerEpoch
                ),
                byteCount: 0
            )
        }
        let finalEpochBytes = try ProductionSecureSessionCapacityOracle.application(
            snapshot: counterSnapshot(
                epoch: limits.maximumEpoch,
                epochBytes: limits.maximumPlaintextBytesPerEpoch - 1
            ),
            byteCount: 1
        )
        XCTAssertTrue(finalEpochBytes.terminalAfterRecord)
        assertCryptoError(.byteLimitExceeded) {
            _ = try ProductionSecureSessionCapacityOracle.application(
                snapshot: counterSnapshot(
                    epoch: limits.maximumEpoch,
                    epochBytes: limits.maximumPlaintextBytesPerEpoch
                ),
                byteCount: 1
            )
        }

        let sessionRecord = try ProductionSecureSessionCapacityOracle.application(
            snapshot: counterSnapshot(
                epoch: limits.maximumEpoch,
                sessionRecords: limits.maximumRecordsPerSession - 1
            ),
            byteCount: 0
        )
        XCTAssertTrue(sessionRecord.terminalAfterRecord)
        assertCryptoError(.sessionLimitExceeded) {
            _ = try ProductionSecureSessionCapacityOracle.application(
                snapshot: counterSnapshot(
                    epoch: limits.maximumEpoch,
                    sessionRecords: limits.maximumRecordsPerSession
                ),
                byteCount: 0
            )
        }
        let sessionBytes = try ProductionSecureSessionCapacityOracle.application(
            snapshot: counterSnapshot(
                epoch: limits.maximumEpoch,
                sessionBytes: limits.maximumPlaintextBytesPerSession - 1
            ),
            byteCount: 1
        )
        XCTAssertTrue(sessionBytes.terminalAfterRecord)
        assertCryptoError(.sessionLimitExceeded) {
            _ = try ProductionSecureSessionCapacityOracle.application(
                snapshot: counterSnapshot(
                    epoch: limits.maximumEpoch,
                    sessionBytes: limits.maximumPlaintextBytesPerSession
                ),
                byteCount: 1
            )
        }
        assertCryptoError(.byteLimitExceeded) {
            _ = try ProductionSecureSessionCapacityOracle.application(
                snapshot: counterSnapshot(epoch: 0),
                byteCount: UInt64(limits.maximumPlaintextBytes + 1)
            )
        }
        assertCryptoError(.recordLimitExceeded) {
            _ = try ProductionSecureSessionCapacityOracle.keyUpdateNextEpoch(
                snapshot: counterSnapshot(epoch: limits.maximumEpoch)
            )
        }
        assertCryptoError(.recordLimitExceeded) {
            _ = try ProductionSecureSessionCapacityOracle.application(
                snapshot: counterSnapshot(epoch: 0, isTerminal: true),
                byteCount: 0
            )
        }
    }

    func testProductionCryptoNegativeVectorInventoryIsExactAndOrdered() throws {
        let fixture = try ProductionCryptoSharedVectorFixture.load()
        XCTAssertEqual(try fixture.negativeVectorIds, [
            "object7_object26_substitution",
            "local_private_public_mismatch",
            "ephemeral_handle_reuse",
            "role_reflection_confirmation",
            "confirmation_proof_bit_flip",
            "confirmation_before_activation",
            "record_wrong_session",
            "record_wrong_role",
            "record_replay",
            "record_gap",
            "record_future_epoch",
            "record_tag_bit_flip",
            "record_ciphertext_bit_flip",
            "authentication_failure_no_receive_advance",
            "key_update_skip",
            "key_update_duplicate",
            "key_update_epoch_15",
            "record_max_plus_one",
            "epoch_record_limit",
            "epoch_plaintext_limit",
            "session_record_limit",
            "session_plaintext_limit",
            "expiry_boundary",
            "clock_regression",
            "authority_invalidation",
            "concurrent_seal_unique_sequence",
        ])
    }

    private func keyScheduleBinding(
        fixture: CandidateSharedVectorFixture,
        chain: CandidateSharedVectorChain,
        role: P2PNATRole
    ) throws -> VerifiedProductionC1CandidateP2PKeyScheduleBinding {
        try ProductionC1CandidateVerifier.verifyP2PKeyScheduleBinding(
            transcript: chain.transcript,
            verifiedGrant: chain.grant,
            localRole: role,
            authority: chain.authority,
            nowMs: fixture.constant("nowMs")
        )
    }

    private func ephemeralKey(
        _ fixture: CandidateSharedVectorFixture,
        role: P2PNATRole
    ) throws -> P2PNATSessionEphemeralKey {
        try P2PNATSessionEphemeralKey(
            testPrivateScalar: fixture.keyData(
                role == .client ? "clientEphemeral" : "runtimeEphemeral",
                "privateScalarHex"
            )
        )
    }

    private func activatedPair(
        fixture: CandidateSharedVectorFixture,
        clientBinding: VerifiedProductionC1CandidateP2PKeyScheduleBinding,
        runtimeBinding: VerifiedProductionC1CandidateP2PKeyScheduleBinding
    ) throws -> ProductionCryptoActivatedPair {
        let now = try fixture.constant("nowMs")
        let client = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: clientBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .client),
            nowMs: now
        )
        let runtime = try ProductionSecureSessionCrypto.deriveHandshake(
            binding: runtimeBinding,
            localEphemeralKey: ephemeralKey(fixture, role: .runtime),
            nowMs: now
        )
        let clientConfirmation = try client.localConfirmation(nowMs: now)
        let runtimeConfirmation = try runtime.localConfirmation(nowMs: now)
        try client.markLocalConfirmationSent(clientConfirmation, nowMs: now)
        try runtime.markLocalConfirmationSent(runtimeConfirmation, nowMs: now)
        try client.acceptPeerConfirmation(runtimeConfirmation, nowMs: now)
        try runtime.acceptPeerConfirmation(clientConfirmation, nowMs: now)
        return ProductionCryptoActivatedPair(
            clientCipher: try client.makeCipher(nowMs: now),
            runtimeCipher: try runtime.makeCipher(nowMs: now),
            clientConfirmation: clientConfirmation,
            runtimeConfirmation: runtimeConfirmation
        )
    }

    private func authenticatedClientKeyUpdate(
        nextEpoch: UInt32,
        epoch: UInt32,
        sequence: UInt64,
        material: ProductionSecureSessionVectorMaterial,
        sessionId: String
    ) throws -> ProductionSecureSessionEncryptedRecord {
        var context = material.bindingDigest
        context.append(1)
        context.append(ProductionC1InternalBridge.be(epoch))
        let key = testHKDFExpand(
            prk: material.clientEpoch0Secret,
            info: ProductionC1InternalBridge.transcript(
                domain: "AetherLink production secure-session traffic key v1",
                claims: context
            ),
            outputByteCount: 32
        )
        let iv = testHKDFExpand(
            prk: material.clientEpoch0Secret,
            info: ProductionC1InternalBridge.transcript(
                domain: "AetherLink production secure-session traffic iv v1",
                claims: context
            ),
            outputByteCount: 12
        )
        let prefix = ProductionC1InternalBridge.encode(
            objectType: ProductionSecureSessionCryptoContract.encryptedRecordObjectType,
            fields: [
                ProductionC1InternalBridge.ascii(sessionId),
                Data([1]),
                ProductionC1InternalBridge.be(epoch),
                ProductionC1InternalBridge.be(sequence),
                Data([ProductionSecureSessionContentType.keyUpdate.rawValue]),
            ]
        )
        let plaintext = ProductionC1InternalBridge.be(nextEpoch)
        var aadClaims = material.bindingDigest
        aadClaims.append(ProductionC1InternalBridge.be(UInt32(prefix.count)))
        aadClaims.append(prefix)
        aadClaims.append(ProductionC1InternalBridge.be(UInt32(plaintext.count)))
        let aad = ProductionC1InternalBridge.transcript(
            domain: "AetherLink production secure-session record AAD v1",
            claims: aadClaims
        )
        var nonce = iv
        let sequenceBytes = ProductionC1InternalBridge.be(sequence)
        for index in 0..<8 {
            nonce[nonce.startIndex + 4 + index] ^=
                sequenceBytes[sequenceBytes.startIndex + index]
        }
        let sealed = try AES.GCM.seal(
            plaintext,
            using: SymmetricKey(data: key),
            nonce: AES.GCM.Nonce(data: nonce),
            authenticating: aad
        )
        return try ProductionSecureSessionEncryptedRecord(
            sessionId: sessionId,
            senderRole: .client,
            epoch: epoch,
            sequence: sequence,
            contentType: .keyUpdate,
            ciphertext: sealed.ciphertext,
            tag: sealed.tag
        )
    }

    private func testHKDFExpand(prk: Data, info: Data, outputByteCount: Int) -> Data {
        var output = Data()
        var previous = Data()
        var counter: UInt8 = 1
        while output.count < outputByteCount {
            var input = previous
            input.append(info)
            input.append(counter)
            previous = Data(HMAC<SHA256>.authenticationCode(
                for: input,
                using: SymmetricKey(data: prk)
            ))
            output.append(previous)
            counter += 1
        }
        return output.prefix(outputByteCount)
    }

    private func assertEpochMaterial(
        roleByte: UInt8,
        roleName: String,
        epochZeroSecret: Data,
        bindingDigest: Data,
        fixture: ProductionCryptoSharedVectorFixture,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws {
        func context(_ epoch: UInt32) -> Data {
            var value = bindingDigest
            value.append(roleByte)
            value.append(ProductionC1InternalBridge.be(epoch))
            return value
        }
        func traffic(_ secret: Data, epoch: UInt32, label: String, count: Int) -> Data {
            testHKDFExpand(
                prk: secret,
                info: ProductionC1InternalBridge.transcript(
                    domain: label,
                    claims: context(epoch)
                ),
                outputByteCount: count
            )
        }
        XCTAssertEqual(
            traffic(
                epochZeroSecret,
                epoch: 0,
                label: "AetherLink production secure-session traffic key v1",
                count: 32
            ),
            try fixture.data("expected", "epochMaterial", roleName, "epoch0KeyHex"),
            file: file,
            line: line
        )
        XCTAssertEqual(
            traffic(
                epochZeroSecret,
                epoch: 0,
                label: "AetherLink production secure-session traffic iv v1",
                count: 12
            ),
            try fixture.data("expected", "epochMaterial", roleName, "epoch0IvHex"),
            file: file,
            line: line
        )
        let epochOneSecret = testHKDFExpand(
            prk: epochZeroSecret,
            info: ProductionC1InternalBridge.transcript(
                domain: "AetherLink production secure-session traffic update v1",
                claims: context(1)
            ),
            outputByteCount: 32
        )
        XCTAssertEqual(
            epochOneSecret,
            try fixture.data("expected", "epochMaterial", roleName, "epoch1SecretHex"),
            file: file,
            line: line
        )
        XCTAssertEqual(
            traffic(
                epochOneSecret,
                epoch: 1,
                label: "AetherLink production secure-session traffic key v1",
                count: 32
            ),
            try fixture.data("expected", "epochMaterial", roleName, "epoch1KeyHex"),
            file: file,
            line: line
        )
        XCTAssertEqual(
            traffic(
                epochOneSecret,
                epoch: 1,
                label: "AetherLink production secure-session traffic iv v1",
                count: 12
            ),
            try fixture.data("expected", "epochMaterial", roleName, "epoch1IvHex"),
            file: file,
            line: line
        )
    }

    private func counterSnapshot(
        epoch: UInt32,
        epochRecords: UInt64 = 0,
        epochBytes: UInt64 = 0,
        sessionRecords: UInt64 = 0,
        sessionBytes: UInt64 = 0,
        isTerminal: Bool = false
    ) -> ProductionSecureSessionCounterSnapshot {
        ProductionSecureSessionCounterSnapshot(
            epoch: epoch,
            sequence: epochRecords,
            epochRecords: epochRecords,
            epochBytes: epochBytes,
            sessionRecords: sessionRecords,
            sessionBytes: sessionBytes,
            isTerminal: isTerminal
        )
    }

    private func assertCryptoError(
        _ expected: ProductionSecureSessionCryptoError,
        file: StaticString = #filePath,
        line: UInt = #line,
        _ body: () throws -> Void
    ) {
        XCTAssertThrowsError(try body(), file: file, line: line) { error in
            XCTAssertEqual(
                error as? ProductionSecureSessionCryptoError,
                expected,
                file: file,
                line: line
            )
        }
    }

    private func verifiedChain(
        _ fixture: CandidateSharedVectorFixture
    ) throws -> CandidateSharedVectorChain {
        let now = try fixture.constant("nowMs")
        let keyset = try ProductionC1ServiceKeyset(canonicalBytes: fixture.canonical("serviceKeyset"))
        let verifiedKeyset = try ProductionC1Verifier.verifyServiceKeyset(
            keyset,
            expectedServiceIdDigest: keyset.serviceIdDigest,
            pinnedRootPublicKey: fixture.publicKey("root"),
            minimumAcceptedKeysetVersion: keyset.keysetVersion,
            nowMs: now
        )
        let authority = try ProductionPairAuthorityState(canonicalBytes: fixture.canonical("authority"))
        let context = try ProductionC1PreauthorizationSessionContext(
            canonicalBytes: fixture.canonical("preauthorizationSessionContext")
        )

        let operationVectors: [CandidateOperationVector] = [
            .init(
                proof: "endpointProofClientPublish",
                capability: "capabilityClientPublish",
                batch: "clientCandidateBatch",
                authorization: "authorizationClientPublish",
                receipt: "receiptClientPublish"
            ),
            .init(
                proof: "endpointProofRuntimeFetchClient",
                capability: "capabilityRuntimeFetchClient",
                batch: "clientCandidateBatch",
                authorization: "authorizationRuntimeFetchClient",
                receipt: "receiptRuntimeFetchClient"
            ),
            .init(
                proof: "endpointProofRuntimePublish",
                capability: "capabilityRuntimePublish",
                batch: "runtimeCandidateBatch",
                authorization: "authorizationRuntimePublish",
                receipt: "receiptRuntimePublish"
            ),
            .init(
                proof: "endpointProofClientFetchRuntime",
                capability: "capabilityClientFetchRuntime",
                batch: "runtimeCandidateBatch",
                authorization: "authorizationClientFetchRuntime",
                receipt: "receiptClientFetchRuntime"
            ),
        ]

        var capabilities: [VerifiedProductionC1CandidateCapability] = []
        for vector in operationVectors {
            let proof = try ProductionC1EndpointOperationProof(
                canonicalBytes: fixture.canonical(vector.proof)
            )
            let capability = try ProductionC1CandidateCapability(
                canonicalBytes: fixture.canonical(vector.capability)
            )
            capabilities.append(try ProductionC1CandidateVerifier.verifyCapability(
                capability,
                candidateBatchCanonicalBytes: fixture.artifactCanonical(vector.batch),
                endpointOperationProof: proof,
                securityContext: context,
                authority: authority,
                verifiedKeyset: verifiedKeyset,
                nowMs: now
            ))
        }
        let bilateral = try ProductionC1CandidateVerifier.verifyBilateral(
            clientPublish: capabilities[0],
            runtimeFetchClient: capabilities[1],
            runtimePublish: capabilities[2],
            clientFetchRuntime: capabilities[3],
            authority: authority,
            nowMs: now
        )

        guard let selectedClient = capabilities[0].candidateBatch.candidates.first,
              let selectedRuntime = capabilities[2].candidateBatch.candidates.first else {
            throw CandidateSharedVectorFixtureError.invalidValue("missing candidate")
        }
        let plan = try ProductionC1CandidateVerifier.verifyP2PDirectPlan(
            claims: ProductionC1RoutePlanClaims(canonicalBytes: fixture.canonical("p2pRoutePlan")),
            capability: ProductionC1RouteCapability(
                canonicalBytes: fixture.canonical("p2pRouteCapability")
            ),
            securityContext: context,
            bilateral: bilateral,
            selectedClientCandidate: selectedClient,
            selectedRuntimeCandidate: selectedRuntime,
            pathValidationReceiptCanonicalBytes: fixture.artifactCanonical("pathValidationReceipt"),
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            nowMs: now
        )
        let authorizations = try ProductionC1CandidateVerifier.makeBilateralRouteAuthorizations(
            for: plan,
            authority: authority,
            nowMs: now
        )
        let generatedAuthorizations = [
            authorizations.clientPublish,
            authorizations.runtimeFetchClient,
            authorizations.runtimePublish,
            authorizations.clientFetchRuntime,
        ]
        for (index, vector) in operationVectors.enumerated() {
            XCTAssertEqual(
                try generatedAuthorizations[index].canonicalBytes(),
                try fixture.canonical(vector.authorization),
                vector.authorization
            )
        }
        XCTAssertEqual(
            try authorizations.finalP2PDirect.canonicalBytes(),
            try fixture.canonical("finalP2PDirectAuthorization")
        )

        var receipts: [VerifiedProductionC1CandidateOperationReceipt] = []
        for (index, vector) in operationVectors.enumerated() {
            let receipt = try ProductionC1CandidateOperationReceipt(
                canonicalBytes: fixture.canonical(vector.receipt)
            )
            receipts.append(try ProductionC1CandidateOperationReceiptVerifier.verify(
                receipt,
                verifiedCapability: capabilities[index],
                authorization: generatedAuthorizations[index],
                authority: authority,
                verifiedKeyset: verifiedKeyset,
                nowMs: now
            ))
        }
        XCTAssertEqual(
            try receipts.map { try $0.receipt.digestHex() },
            try fixture.derivedStringArray("operationReceiptDigests")
        )

        let derivedGrant = try ProductionC1CandidateVerifier.deriveGrantEvidence(
            plan: plan,
            routeAuthorizations: authorizations,
            operationReceipts: receipts,
            initiatorRole: .client,
            authority: authority,
            nowMs: now
        )
        let vectorEvidence = try ProductionC1P2PGrantEvidence(
            canonicalBytes: fixture.canonical("p2pGrantEvidence")
        )
        XCTAssertEqual(try derivedGrant.evidence.canonicalBytes(), try fixture.canonical("p2pGrantEvidence"))
        XCTAssertEqual(derivedGrant.evidence, vectorEvidence)
        XCTAssertEqual(
            derivedGrant.evidence.effectiveNotBeforeMs,
            try fixture.expectedUInt64("effectiveNotBeforeMs")
        )
        XCTAssertEqual(derivedGrant.evidence.expiresAtMs, try fixture.expectedUInt64("expiresAtMs"))
        let grant = try ProductionC1CandidateVerifier.verifyGrantEvidence(
            vectorEvidence,
            plan: plan,
            routeAuthorizations: authorizations,
            operationReceipts: receipts,
            localRole: .client,
            authority: authority,
            nowMs: now
        )

        let vectorAuthorization = try ProductionC1P2PGrantAuthorization(
            canonicalBytes: fixture.canonical("p2pGrantAuthorization")
        )
        let projectedAuthorization = try ProductionC1CandidateVerifier.makeGrantAuthorization(
            vectorEvidence
        )
        XCTAssertEqual(projectedAuthorization, vectorAuthorization)
        XCTAssertEqual(
            try projectedAuthorization.canonicalBytes(),
            try fixture.canonical("p2pGrantAuthorization")
        )
        XCTAssertEqual(grant.grantAuthorization.authorization, vectorAuthorization)
        _ = try ProductionC1CandidateVerifier.verifyGrantAuthorization(
            vectorAuthorization,
            evidence: vectorEvidence,
            plan: plan,
            localRole: .client
        )

        let transcript = try ProductionSecureSessionTranscript(
            canonicalBytes: fixture.canonical("candidateSecureSessionTranscript")
        )
        XCTAssertEqual(transcript.routeAuthDigest, try vectorAuthorization.digestHex())
        let connectorInput = try ProductionC1CandidateVerifier.verifyP2PConnectorInput(
            for: grant,
            localRole: .client,
            routeHandle: fixture.syntheticString("routeHandle"),
            nonce: fixture.syntheticString("connectorNonce"),
            secret: fixture.syntheticData("connectorSecretHex"),
            authority: authority,
            nowMs: now
        )
        let key = try fixture.syntheticData("keyConfirmationKeyHex")
        let peerConfirmation = try ProductionC1CandidateVerifier.makeP2PKeyConfirmation(
            transcript: transcript,
            grantAuthorization: grant.grantAuthorization,
            confirmingRole: .runtime,
            key: key
        )
        _ = try ProductionC1CandidateVerifier.verifyP2PTranscriptBinding(
            transcript: transcript,
            verifiedGrant: grant,
            connectorInput: connectorInput,
            localRole: .client,
            keyConfirmationKey: key,
            presentedPeerKeyConfirmation: peerConfirmation,
            authority: authority,
            nowMs: now
        )

        return CandidateSharedVectorChain(
            authority: authority,
            verifiedKeyset: verifiedKeyset,
            capabilities: capabilities,
            plan: plan,
            authorizations: authorizations,
            receipts: receipts,
            grant: grant,
            transcript: transcript,
            connectorInput: connectorInput
        )
    }

    private func otherLedgerFirstReceipt(
        fixture: CandidateSharedVectorFixture,
        chain: CandidateSharedVectorChain
    ) throws -> VerifiedProductionC1CandidateOperationReceipt {
        let original = chain.receipts[0].receipt
        let previousRevision: UInt64 = 10
        let committedRevision: UInt64 = 11
        let resultDigest = try receiptResultDigest(
            original,
            previousRevision: previousRevision,
            committedRevision: committedRevision
        )
        let unsignedMutation = try replacingTLVFields(
            in: original.canonicalBytes(),
            replacements: [
                37: Data(resultDigest.utf8),
                38: ProductionC1InternalBridge.be(previousRevision),
                39: ProductionC1InternalBridge.be(committedRevision),
                40: Data(String(repeating: "c", count: 64).utf8),
                41: Data(String(repeating: "d", count: 64).utf8),
                42: Data(String(repeating: "e", count: 64).utf8),
            ]
        )
        let claims = try canonicalPrefix(in: unsignedMutation, beforeTag: 48)
        let transcript = ProductionC1InternalBridge.transcript(
            domain: "AetherLink G1a-C candidate-publish operation receipt service signature v1",
            claims: claims
        )
        let signingKey = try P256.Signing.PrivateKey(
            rawRepresentation: fixture.keyData("candidateReceipt", "privateScalarHex")
        )
        let signedBytes = try replacingTLVFields(
            in: unsignedMutation,
            replacements: [48: try ProductionC1InternalBridge.sign(transcript, using: signingKey)]
        )
        let receipt = try ProductionC1CandidateOperationReceipt(canonicalBytes: signedBytes)
        return try ProductionC1CandidateOperationReceiptVerifier.verify(
            receipt,
            verifiedCapability: chain.capabilities[0],
            authorization: chain.authorizations.clientPublish,
            authority: chain.authority,
            verifiedKeyset: chain.verifiedKeyset,
            nowMs: fixture.constant("nowMs")
        )
    }

    private func receiptResultDigest(
        _ receipt: ProductionC1CandidateOperationReceipt,
        previousRevision: UInt64,
        committedRevision: UInt64
    ) throws -> String {
        var claims = try ProductionC1InternalBridge.rawDigest(receipt.proofId)
        claims.append(try ProductionC1InternalBridge.rawDigest(receipt.requestDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(receipt.capabilityDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(receipt.operationAuthorizationDigest))
        claims.append(try ProductionC1InternalBridge.rawDigest(receipt.singleUseNonce))
        claims.append(ProductionC1InternalBridge.be(receipt.consumedBytes))
        claims.append(ProductionC1InternalBridge.be(previousRevision))
        claims.append(ProductionC1InternalBridge.be(committedRevision))
        return ProductionC1InternalBridge.digestHex(
            ProductionC1InternalBridge.transcript(
                domain: "AetherLink G1a-C readback-confirmed candidate usage receipt v1",
                claims: claims
            )
        )
    }

    private func roundTrip(name: String, canonical: Data) throws -> Data {
        switch name {
        case "authority":
            return try ProductionPairAuthorityState(canonicalBytes: canonical).canonicalBytes()
        case "serviceKeyset":
            return try ProductionC1ServiceKeyset(canonicalBytes: canonical).canonicalBytes()
        case "preauthorizationSessionContext":
            return try ProductionC1PreauthorizationSessionContext(
                canonicalBytes: canonical
            ).canonicalBytes()
        case "p2pConnector":
            return try ProductionC1RouteConnectorMaterial(canonicalBytes: canonical).canonicalBytes()
        case "p2pRoutePlan":
            return try ProductionC1RoutePlanClaims(canonicalBytes: canonical).canonicalBytes()
        case "p2pRouteCapability":
            return try ProductionC1RouteCapability(canonicalBytes: canonical).canonicalBytes()
        case "authorizationClientFetchRuntime", "authorizationClientPublish",
             "authorizationRuntimeFetchClient", "authorizationRuntimePublish",
             "finalP2PDirectAuthorization":
            return try ProductionRouteAuthorization(canonicalBytes: canonical).canonicalBytes()
        case "candidateSecureSessionTranscript":
            return try ProductionSecureSessionTranscript(canonicalBytes: canonical).canonicalBytes()
        case let value where value.hasPrefix("endpointProof"):
            return try ProductionC1EndpointOperationProof(canonicalBytes: canonical).canonicalBytes()
        case let value where value.hasPrefix("capability"):
            return try ProductionC1CandidateCapability(canonicalBytes: canonical).canonicalBytes()
        case "p2pGrantEvidence":
            return try ProductionC1P2PGrantEvidence(canonicalBytes: canonical).canonicalBytes()
        case "p2pGrantAuthorization":
            return try ProductionC1P2PGrantAuthorization(canonicalBytes: canonical).canonicalBytes()
        case let value where value.hasPrefix("receipt"):
            return try ProductionC1CandidateOperationReceipt(canonicalBytes: canonical).canonicalBytes()
        default:
            throw CandidateSharedVectorFixtureError.invalidValue("unknown object \(name)")
        }
    }

    private func assertCandidateError(
        _ expected: ProductionC1CandidateCapabilityError,
        file: StaticString = #filePath,
        line: UInt = #line,
        _ body: () throws -> Void
    ) {
        XCTAssertThrowsError(try body(), file: file, line: line) { error in
            XCTAssertEqual(
                error as? ProductionC1CandidateCapabilityError,
                expected,
                file: file,
                line: line
            )
        }
    }

    private func replacingTLVFields(
        in data: Data,
        replacements: [UInt8: Data]
    ) throws -> Data {
        guard data.count >= 6 else {
            throw CandidateSharedVectorFixtureError.invalidValue("short TLV")
        }
        var output = Data(data.prefix(6))
        var cursor = 6
        while cursor < data.count {
            guard cursor + 5 <= data.count else {
                throw CandidateSharedVectorFixtureError.invalidValue("short TLV header")
            }
            let tag = data[cursor]
            let length = data[(cursor + 1)..<(cursor + 5)].reduce(UInt32(0)) {
                ($0 << 8) | UInt32($1)
            }
            let valueStart = cursor + 5
            let valueEnd = valueStart + Int(length)
            guard valueEnd <= data.count else {
                throw CandidateSharedVectorFixtureError.invalidValue("short TLV value")
            }
            let value = replacements[tag] ?? Data(data[valueStart..<valueEnd])
            output.append(tag)
            var size = UInt32(value.count).bigEndian
            withUnsafeBytes(of: &size) { output.append(contentsOf: $0) }
            output.append(value)
            cursor = valueEnd
        }
        return output
    }

    private func canonicalPrefix(in data: Data, beforeTag target: UInt8) throws -> Data {
        var cursor = 6
        while cursor < data.count {
            guard cursor + 5 <= data.count else {
                throw CandidateSharedVectorFixtureError.invalidValue("short TLV header")
            }
            let tag = data[cursor]
            if tag == target { return Data(data[..<cursor]) }
            let length = data[(cursor + 1)..<(cursor + 5)].reduce(UInt32(0)) {
                ($0 << 8) | UInt32($1)
            }
            cursor += 5 + Int(length)
        }
        throw CandidateSharedVectorFixtureError.invalidValue("missing TLV tag \(target)")
    }

    private func sha256Hex(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }
}

private struct ProductionCryptoActivatedPair {
    let clientCipher: ProductionSecureSessionCipher
    let runtimeCipher: ProductionSecureSessionCipher
    let clientConfirmation: Data
    let runtimeConfirmation: Data
}

private final class ProductionCryptoConcurrentAccumulator: @unchecked Sendable {
    private let lock = NSLock()
    private var storedSequences: [UInt64] = []
    private var storedErrors: [Error] = []

    var sequences: [UInt64] {
        lock.withLock { storedSequences }
    }

    var errors: [Error] {
        lock.withLock { storedErrors }
    }

    func append(_ sequence: UInt64) {
        lock.withLock { storedSequences.append(sequence) }
    }

    func append(_ error: Error) {
        lock.withLock { storedErrors.append(error) }
    }
}

private struct ProductionCryptoSharedVectorFixture {
    let root: [String: Any]

    static func load() throws -> Self {
        let relative = "shared/protocol/fixtures/production-secure-session-crypto-v1-vectors.json"
        let starts = [
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true),
            URL(fileURLWithPath: #filePath).deletingLastPathComponent(),
        ]
        for start in starts {
            var directory = start.standardizedFileURL
            while true {
                let candidate = directory.appendingPathComponent(relative)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    let data = try Data(contentsOf: candidate)
                    guard let root = try JSONSerialization.jsonObject(with: data)
                            as? [String: Any] else {
                        throw CandidateSharedVectorFixtureError.invalidValue("crypto root")
                    }
                    return Self(root: root)
                }
                let parent = directory.deletingLastPathComponent()
                if parent.path == directory.path { break }
                directory = parent
            }
        }
        throw CandidateSharedVectorFixtureError.notFound
    }

    var negativeVectorIds: [String] {
        get throws {
            guard let values = root["negativeVectors"] as? [[String: Any]] else {
                throw CandidateSharedVectorFixtureError.invalidValue("negativeVectors")
            }
            return try values.map {
                guard let id = $0["id"] as? String else {
                    throw CandidateSharedVectorFixtureError.invalidValue("negativeVectors.id")
                }
                return id
            }
        }
    }

    func data(_ keys: String...) throws -> Data {
        var value: Any = root
        for key in keys {
            guard let dictionary = value as? [String: Any], let next = dictionary[key] else {
                throw CandidateSharedVectorFixtureError.invalidValue(keys.joined(separator: "."))
            }
            value = next
        }
        guard let hex = value as? String,
              hex.count.isMultiple(of: 2),
              hex.utf8.allSatisfy({
                  (48...57).contains($0) || (97...102).contains($0)
              }) else {
            throw CandidateSharedVectorFixtureError.invalidHex(keys.joined(separator: "."))
        }
        var output = Data()
        output.reserveCapacity(hex.count / 2)
        var index = hex.startIndex
        while index < hex.endIndex {
            let next = hex.index(index, offsetBy: 2)
            guard let byte = UInt8(hex[index..<next], radix: 16) else {
                throw CandidateSharedVectorFixtureError.invalidHex(hex)
            }
            output.append(byte)
            index = next
        }
        return output
    }
}

private struct CandidateOperationVector {
    let proof: String
    let capability: String
    let batch: String
    let authorization: String
    let receipt: String
}

private struct CandidateSharedVectorChain {
    let authority: ProductionPairAuthorityState
    let verifiedKeyset: VerifiedProductionC1ServiceKeyset
    let capabilities: [VerifiedProductionC1CandidateCapability]
    let plan: VerifiedProductionC1CandidateP2PPlan
    let authorizations: ProductionC1BilateralRouteAuthorizations
    let receipts: [VerifiedProductionC1CandidateOperationReceipt]
    let grant: VerifiedProductionC1P2PGrantEvidence
    let transcript: ProductionSecureSessionTranscript
    let connectorInput: VerifiedProductionC1CandidateP2PConnectorInput
}

private enum CandidateSharedVectorFixtureError: Error {
    case notFound
    case invalidValue(String)
    case invalidHex(String)
}

private struct CandidateSharedVectorFixture {
    let root: [String: Any]
    let rawData: Data
    let repositoryRoot: URL

    static func load() throws -> Self {
        let relative = "shared/protocol/fixtures/production-g1a-c-candidate-v1-vectors.json"
        let starts = [
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true),
            URL(fileURLWithPath: #filePath).deletingLastPathComponent(),
        ]
        for start in starts {
            var directory = start.standardizedFileURL
            while true {
                let candidate = directory.appendingPathComponent(relative)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    let data = try Data(contentsOf: candidate)
                    let value = try JSONSerialization.jsonObject(with: data)
                    guard let root = value as? [String: Any] else {
                        throw CandidateSharedVectorFixtureError.invalidValue("root")
                    }
                    return Self(root: root, rawData: data, repositoryRoot: directory)
                }
                let parent = directory.deletingLastPathComponent()
                if parent.path == directory.path { break }
                directory = parent
            }
        }
        throw CandidateSharedVectorFixtureError.notFound
    }

    var objectNames: [String] {
        ((try? dictionary("objects")) ?? [:]).keys.sorted()
    }

    func string(_ key: String) throws -> String {
        try string(in: root, key)
    }

    func uint64(_ key: String) throws -> UInt64 {
        try uint64(in: root, key)
    }

    func constant(_ key: String) throws -> UInt64 {
        try uint64(in: dictionary("constants"), key)
    }

    func expectedString(_ key: String) throws -> String {
        try string(in: dictionary("expectedOutcomes"), key)
    }

    func expectedUInt64(_ key: String) throws -> UInt64 {
        try uint64(in: dictionary("expectedOutcomes"), key)
    }

    func expectedBool(_ key: String) throws -> Bool {
        try bool(in: dictionary("expectedOutcomes"), key)
    }

    func syntheticString(_ key: String) throws -> String {
        try string(in: dictionary("syntheticMaterials"), key)
    }

    func syntheticData(_ key: String) throws -> Data {
        try decodeHex(syntheticString(key))
    }

    func syntheticBool(_ key: String) throws -> Bool {
        try bool(in: dictionary("syntheticMaterials"), key)
    }

    func derived(_ key: String) throws -> String {
        try string(in: dictionary("derived"), key)
    }

    func derivedStringArray(_ key: String) throws -> [String] {
        guard let values = try dictionary("derived")[key] as? [String] else {
            throw CandidateSharedVectorFixtureError.invalidValue("derived.\(key)")
        }
        return values
    }

    func dictionary(_ keys: String...) throws -> [String: Any] {
        var value: Any = root
        for key in keys {
            guard let dictionary = value as? [String: Any], let next = dictionary[key] else {
                throw CandidateSharedVectorFixtureError.invalidValue(keys.joined(separator: "."))
            }
            value = next
        }
        guard let result = value as? [String: Any] else {
            throw CandidateSharedVectorFixtureError.invalidValue(keys.joined(separator: "."))
        }
        return result
    }

    func string(in dictionary: [String: Any], _ key: String) throws -> String {
        guard let value = dictionary[key] as? String else {
            throw CandidateSharedVectorFixtureError.invalidValue(key)
        }
        return value
    }

    func bool(in dictionary: [String: Any], _ key: String) throws -> Bool {
        guard let value = dictionary[key] as? Bool else {
            throw CandidateSharedVectorFixtureError.invalidValue(key)
        }
        return value
    }

    func canonical(_ name: String) throws -> Data {
        try decodeHex(string(in: dictionary("objects", name), "expectedCanonicalHex"))
    }

    func canonicalByteCount(_ name: String) throws -> Int {
        Int(try uint64(in: dictionary("objects", name), "expectedCanonicalByteCount"))
    }

    func canonicalDigest(_ name: String) throws -> String {
        try string(in: dictionary("objects", name), "expectedSha256Hex")
    }

    func artifactCanonical(_ name: String) throws -> Data {
        try decodeHex(string(in: dictionary("artifacts", name), "expectedCanonicalHex"))
    }

    func artifactCanonicalByteCount(_ name: String) throws -> Int {
        Int(try uint64(in: dictionary("artifacts", name), "expectedCanonicalByteCount"))
    }

    func artifactDigest(_ name: String) throws -> String {
        try string(in: dictionary("artifacts", name), "expectedSha256Hex")
    }

    func publicKey(_ name: String) throws -> P256.Signing.PublicKey {
        try P256.Signing.PublicKey(x963Representation: keyData(name, "publicKeyX963Hex"))
    }

    func keyData(_ name: String, _ key: String) throws -> Data {
        try decodeHex(string(in: dictionary("keys", name), key))
    }

    func operationStrings(_ key: String) throws -> [String] {
        guard let operations = root["operations"] as? [[String: Any]] else {
            throw CandidateSharedVectorFixtureError.invalidValue("operations")
        }
        return try operations.map { try string(in: $0, key) }
    }

    func mutationIds() throws -> [String] {
        guard let mutations = root["mutations"] as? [[String: Any]] else {
            throw CandidateSharedVectorFixtureError.invalidValue("mutations")
        }
        return try mutations.map { try string(in: $0, "id") }
    }

    private func uint64(in dictionary: [String: Any], _ key: String) throws -> UInt64 {
        guard let value = dictionary[key] as? NSNumber else {
            throw CandidateSharedVectorFixtureError.invalidValue(key)
        }
        return value.uint64Value
    }

    private func decodeHex(_ value: String) throws -> Data {
        guard value.count.isMultiple(of: 2),
              value.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
            throw CandidateSharedVectorFixtureError.invalidHex(value)
        }
        var output = Data()
        output.reserveCapacity(value.count / 2)
        var index = value.startIndex
        while index < value.endIndex {
            let next = value.index(index, offsetBy: 2)
            guard let byte = UInt8(value[index..<next], radix: 16) else {
                throw CandidateSharedVectorFixtureError.invalidHex(value)
            }
            output.append(byte)
            index = next
        }
        return output
    }
}
