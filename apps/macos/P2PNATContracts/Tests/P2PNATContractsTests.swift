import CryptoKit
import Foundation
@testable import P2PNATContracts
import XCTest

final class P2PNATContractsTests: XCTestCase {
    private let session = String(repeating: "ab", count: 16)
    private let digest = String(repeating: "cd", count: 32)
    private let nonce = String(repeating: "12", count: 16)

    func testPublishedLimitsAreExact() {
        XCTAssertEqual(P2PNATLimits.sealedBytes, 16_384)
        XCTAssertEqual(P2PNATLimits.candidateBlobBytes, 8_192)
        XCTAssertEqual(P2PNATLimits.candidateBatchBytes, 8_291)
        XCTAssertEqual(P2PNATLimits.relayCapabilityBytes, 404)
        XCTAssertEqual(P2PNATLimits.identityTranscriptBytes, 532)
        XCTAssertEqual(P2PNATLimits.pathReceiptBytes, 300)
        XCTAssertEqual(P2PNATLimits.candidates, 32)
        XCTAssertEqual(P2PNATLimits.ttlMilliseconds, 600_000)
        XCTAssertEqual(P2PNATLimits.clockSkewMilliseconds, 30_000)
        XCTAssertEqual(P2PNATLimits.replayEntries, 128)
        XCTAssertEqual(P2PNATLimits.attemptsPerPair, 2)
        XCTAssertEqual(P2PNATLimits.globalAttempts, 32)
        XCTAssertEqual(P2PNATLimits.retries, 4)
    }

    func testCandidateBatchCanonicalRoundTripAndHeader() throws {
        let batch = try CandidateBatch(sessionId: session, generation: 1, sequence: 0, expires: 5,
                                       role: .client, candidates: [candidate(priority: 9), candidate(priority: 8, address: [8,8,8,8])])
        let bytes = batch.canonicalBytes()
        XCTAssertEqual(Array(bytes.prefix(6)), Array("ALP1".utf8) + [1, 1])
        XCTAssertEqual(try CandidateBatch(canonicalBytes: bytes), batch)
    }

    func testCandidateBatchRejectsNonCanonicalCandidates() throws {
        XCTAssertThrowsError(try CandidateBatch(sessionId: session,generation:1,sequence:0,expires:1,role:.client,
                                                 candidates:[candidate(priority:1),candidate(priority:2,address:[8,8,8,8])]))
        let duplicate = try candidate(priority: 1)
        XCTAssertThrowsError(try CandidateBatch(sessionId: session,generation:1,sequence:0,expires:1,role:.client,candidates:[duplicate,duplicate]))
        XCTAssertThrowsError(try CandidateBatch(sessionId: session,generation:1,sequence:0,expires:1,role:.client,candidates:[]))
    }

    func testCandidateValidationRejectsBadPortFoundationAndAddress() {
        XCTAssertThrowsError(try P2PNATCandidate(kind:.host,family:.ipv4,port:1023,priority:1,foundation:Data(repeating:0,count:8),address:Data(repeating:1,count:4)))
        XCTAssertThrowsError(try P2PNATCandidate(kind:.host,family:.ipv6,port:1024,priority:1,foundation:Data(repeating:0,count:7),address:Data(repeating:1,count:16)))
        XCTAssertThrowsError(try P2PNATCandidate(kind:.host,family:.ipv4,port:1024,priority:1,foundation:Data(repeating:0,count:8),address:Data(repeating:1,count:16)))
    }

    func testStrictDecoderRejectsMalformedEnvelopeShapes() throws {
        let valid = try CandidateBatch(sessionId:session,generation:1,sequence:0,expires:5,role:.client,candidates:[candidate(priority:1)]).canonicalBytes()
        var wrongMagic=valid;wrongMagic[0]=0;XCTAssertThrowsError(try CandidateBatch(canonicalBytes:wrongMagic))
        var wrongVersion=valid;wrongVersion[5]=2;XCTAssertThrowsError(try CandidateBatch(canonicalBytes:wrongVersion))
        var omitted=valid;omitted.removeSubrange(6..<43);XCTAssertThrowsError(try CandidateBatch(canonicalBytes:omitted))
        var duplicate=valid;duplicate[6]=2;XCTAssertThrowsError(try CandidateBatch(canonicalBytes:duplicate))
        var unknown=valid;unknown[6]=99;XCTAssertThrowsError(try CandidateBatch(canonicalBytes:unknown))
        var trailing=valid;trailing.append(0);XCTAssertThrowsError(try CandidateBatch(canonicalBytes:trailing))
        var invalidLength=valid;invalidLength[7...10]=Data([0xff,0xff,0xff,0xff]);XCTAssertThrowsError(try CandidateBatch(canonicalBytes:invalidLength))
    }

    func testDecoderRejectsMalformedASCIIAndIntegerWidth() throws {
        var bytes=try CandidateBatch(sessionId:session,generation:1,sequence:0,expires:5,role:.client,candidates:[candidate(priority:1)]).canonicalBytes()
        bytes[11]=0xff
        XCTAssertThrowsError(try CandidateBatch(canonicalBytes:bytes))
        bytes=try CandidateBatch(sessionId:session,generation:1,sequence:0,expires:5,role:.client,candidates:[candidate(priority:1)]).canonicalBytes()
        let generationTag=43
        bytes[generationTag+1...generationTag+4]=Data([0,0,0,7])
        bytes.remove(at:generationTag+5)
        XCTAssertThrowsError(try CandidateBatch(canonicalBytes:bytes))
    }

    func testAllContractTypesRoundTrip() throws {
        let key=p256G
        let sealed=try SealedRouteRecord(sessionId:session,pairDigest:digest,role:.runtime,generation:2,sequence:3,expires:9,nonce:nonce,ephemeralKey:key,sealNonce:Data(repeating:1,count:12),ciphertext:Data([9]))
        XCTAssertEqual(try SealedRouteRecord(canonicalBytes:sealed.canonicalBytes()),sealed)
        let relay=try RelayCapability(sessionId:session,pairDigest:digest,clientFingerprint:digest,runtimeFingerprint:digest,relayServiceDigest:digest,expires:9,quotaBytes:1,nonce:nonce)
        XCTAssertEqual(try RelayCapability(canonicalBytes:relay.canonicalBytes()),relay)
        let transcript=try IdentitySessionTranscript(sessionId:session,pairDigest:digest,clientFingerprint:digest,runtimeFingerprint:digest,clientKey:key,runtimeKey:key,generation:1,pathReceiptDigest:digest,transport:.direct,fallback:.none)
        XCTAssertEqual(try IdentitySessionTranscript(canonicalBytes:transcript.canonicalBytes()),transcript)
        let receipt=try PathValidationReceipt(sessionId:session,generation:1,candidatePairDigest:digest,transport:.relay,clientObserved:digest,runtimeObserved:digest,validatedAt:1,expires:2)
        XCTAssertEqual(try PathValidationReceipt(canonicalBytes:receipt.canonicalBytes()),receipt)
    }

    func testSealedRouteBoundsAndFixedLengths() throws {
        let key=p256G
        let oneByte=try SealedRouteRecord(sessionId:session,pairDigest:digest,role:.runtime,generation:1,sequence:0,expires:1,nonce:nonce,ephemeralKey:key,sealNonce:Data(repeating:0,count:12),ciphertext:Data([0])).canonicalBytes()
        let maximumCiphertext=P2PNATLimits.sealedBytes-(oneByte.count-1)
        let exact=try SealedRouteRecord(sessionId:session,pairDigest:digest,role:.runtime,generation:1,sequence:0,expires:1,nonce:nonce,ephemeralKey:key,sealNonce:Data(repeating:0,count:12),ciphertext:Data(repeating:0,count:maximumCiphertext))
        XCTAssertEqual(exact.canonicalBytes().count,P2PNATLimits.sealedBytes)
        XCTAssertThrowsError(try SealedRouteRecord(sessionId:session,pairDigest:digest,role:.runtime,generation:1,sequence:0,expires:1,nonce:nonce,ephemeralKey:key,sealNonce:Data(repeating:0,count:12),ciphertext:Data(repeating:0,count:maximumCiphertext+1)))
        XCTAssertThrowsError(try SealedRouteRecord(sessionId:session,pairDigest:digest,role:.client,generation:1,sequence:0,expires:1,nonce:nonce,ephemeralKey:key,sealNonce:Data(repeating:0,count:12),ciphertext:Data()))
        XCTAssertThrowsError(try SealedRouteRecord(sessionId:session,pairDigest:digest,role:.client,generation:1,sequence:0,expires:1,nonce:nonce,ephemeralKey:Data(repeating:3,count:65),sealNonce:Data(repeating:0,count:12),ciphertext:Data([1])))
        XCTAssertThrowsError(try SealedRouteRecord(sessionId:session,pairDigest:digest,role:.client,generation:1,sequence:0,expires:1,nonce:nonce,ephemeralKey:Data([4])+Data(repeating:0,count:64),sealNonce:Data(repeating:0,count:12),ciphertext:Data([1])))
    }

    func testHexAndPositiveValueValidation() throws {
        XCTAssertThrowsError(try CandidateBatch(sessionId:session.uppercased(),generation:1,sequence:0,expires:1,role:.client,candidates:[candidate(priority:1)]))
        XCTAssertThrowsError(try CandidateBatch(sessionId:session,generation:0,sequence:0,expires:1,role:.client,candidates:[candidate(priority:1)]))
        XCTAssertThrowsError(try PathValidationReceipt(sessionId:session,generation:1,candidatePairDigest:digest,transport:.direct,clientObserved:digest,runtimeObserved:digest,validatedAt:2,expires:2))
    }

    func testTranscriptDigestAndRoleBoundKeyConfirmation() throws {
        let key=p2562G
        let transcript=try IdentitySessionTranscript(sessionId:session,pairDigest:digest,clientFingerprint:digest,runtimeFingerprint:digest,clientKey:key,runtimeKey:key,generation:1,pathReceiptDigest:digest,transport:.direct,fallback:.none)
        XCTAssertEqual(transcript.digest,Data(SHA256.hash(data:transcript.canonicalBytes())))
        let secret=Data(repeating:5,count:32)
        XCTAssertNotEqual(try transcript.keyConfirmation(key:secret,role:.client),try transcript.keyConfirmation(key:secret,role:.runtime))
        XCTAssertThrowsError(try transcript.keyConfirmation(key:Data(repeating:5,count:31),role:.client))
    }

    func testFreshParsingAndFrameCeilingsFailClosed() throws {
        let now:UInt64=1_000_000
        let expired=try CandidateBatch(sessionId:session,generation:1,sequence:0,expires:now-30_000,role:.client,candidates:[candidate(priority:1)]).canonicalBytes()
        XCTAssertThrowsError(try CandidateBatch(freshCanonicalBytes:expired,now:now))
        let fresh=try CandidateBatch(sessionId:session,generation:1,sequence:0,expires:now+600_000,role:.client,candidates:[candidate(priority:1)]).canonicalBytes()
        XCTAssertNoThrow(try CandidateBatch(freshCanonicalBytes:fresh,now:now))
        XCTAssertThrowsError(try CandidateBatch(canonicalBytes:Data(repeating:0,count:P2PNATLimits.candidateBatchBytes+1)))
        XCTAssertThrowsError(try RelayCapability(canonicalBytes:Data(repeating:0,count:P2PNATLimits.relayCapabilityBytes+1)))
        XCTAssertThrowsError(try IdentitySessionTranscript(canonicalBytes:Data(repeating:0,count:P2PNATLimits.identityTranscriptBytes+1)))
        XCTAssertThrowsError(try PathValidationReceipt(canonicalBytes:Data(repeating:0,count:P2PNATLimits.pathReceiptBytes+1)))
    }

    func testPathReceiptFreshnessBindsValidationTimeAndLifetime() throws {
        let now:UInt64=1_000_000
        XCTAssertThrowsError(try PathValidationReceipt(sessionId:session,generation:1,candidatePairDigest:digest,transport:.direct,clientObserved:digest,runtimeObserved:digest,validatedAt:now,expires:now+600_001))
        let future=try PathValidationReceipt(sessionId:session,generation:1,candidatePairDigest:digest,transport:.direct,clientObserved:digest,runtimeObserved:digest,validatedAt:now+30_001,expires:now+30_002).canonicalBytes()
        XCTAssertThrowsError(try PathValidationReceipt(freshCanonicalBytes:future,now:now))
        XCTAssertTrue(P2PNATFreshness.isPathValidationFresh(validatedAt:now,expires:now+600_000,now:now))
    }

    private func candidate(priority:UInt32,address:[UInt8]=[1,1,1,1]) throws -> P2PNATCandidate {
        try P2PNATCandidate(kind:.host,family:.ipv4,port:1024,priority:priority,foundation:Data(repeating:0,count:8),address:Data(address))
    }

    private var p256G:Data{hexData("046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c2964fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5")}
    private var p2562G:Data{hexData("047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc4766997807775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1")}
    private func hexData(_ value:String)->Data{var result=Data();var index=value.startIndex;while index<value.endIndex{let next=value.index(index,offsetBy:2);result.append(UInt8(value[index..<next],radix:16)!);index=next};return result}
}
