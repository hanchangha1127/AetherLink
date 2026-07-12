import Foundation
import P2PNATContracts
@testable import P2PNATConformance
import XCTest

final class P2PNATConformanceTests:XCTestCase {
    func testCandidatePolicyRejectsForbiddenIPv4Classes() {
        let addresses:[[UInt8]]=[[0,0,0,0],[127,0,0,1],[224,0,0,1],[169,254,1,1],[255,255,255,255],[10,0,0,1],[172,16,0,1],[192,168,0,1]]
        for address in addresses { XCTAssertThrowsError(try CandidatePolicy().validateAddress(Data(address),family:.ipv4),"\(address)") }
        XCTAssertNoThrow(try CandidatePolicy().validateAddress(Data([8,8,8,8]),family:.ipv4))
    }

    func testCandidatePolicyRejectsForbiddenIPv6Classes() {
        let values:[Data]=[
            Data(repeating:0,count:16),Data(repeating:0,count:15)+Data([1]),Data([0xff])+Data(repeating:0,count:15),
            Data([0xfe,0x80])+Data(repeating:0,count:14),Data(repeating:0,count:10)+Data([0xff,0xff,1,2,3,4]),
            Data([0xfd])+Data(repeating:0,count:15)
        ]
        for value in values { XCTAssertThrowsError(try CandidatePolicy().validateAddress(value,family:.ipv6)) }
        XCTAssertNoThrow(try CandidatePolicy().validateAddress(Data([0x20,1])+Data(repeating:0,count:14),family:.ipv6))
    }

    func testPrivateSameLinkExceptionDoesNotPermitOtherForbiddenClasses() {
        let policy=CandidatePolicy(allowPrivateSameLink:true)
        XCTAssertNoThrow(try policy.validateAddress(Data([10,0,0,1]),family:.ipv4))
        XCTAssertNoThrow(try policy.validateAddress(Data([0xfd])+Data(repeating:0,count:15),family:.ipv6))
        XCTAssertThrowsError(try policy.validateAddress(Data([127,0,0,1]),family:.ipv4))
        XCTAssertThrowsError(try policy.validateAddress(Data([0xfe,0x80])+Data(repeating:0,count:14),family:.ipv6))
    }

    func testCandidatePolicyRejectsDuplicateAndExcess() throws {
        let c=try candidate(1)
        XCTAssertThrowsError(try CandidatePolicy().validate([])) { XCTAssertEqual($0 as? CandidatePolicyError,.excess) }
        XCTAssertThrowsError(try CandidatePolicy().validate([c,c])) { XCTAssertEqual($0 as? CandidatePolicyError,.duplicate) }
        let many=try (0...32).map { try candidate(UInt32($0),last:UInt8($0+1)) }
        XCTAssertThrowsError(try CandidatePolicy().validate(many)) { XCTAssertEqual($0 as? CandidatePolicyError,.excess) }
    }

    func testReplayWindowRequiresAdvancingGenerationOrSequenceAndFreshNonce() {
        var window=ReplayWindow()
        XCTAssertEqual(admit(&window,pair:pairA,role:.client,generation:1,sequence:1,nonce:nonce(1)),.accepted)
        XCTAssertEqual(admit(&window,pair:pairA,role:.client,generation:1,sequence:1,nonce:nonce(2)),.duplicate)
        XCTAssertEqual(admit(&window,pair:pairA,role:.client,generation:1,sequence:2,nonce:nonce(1)),.duplicate)
        XCTAssertEqual(admit(&window,pair:pairA,role:.client,generation:1,sequence:2,nonce:nonce(2)),.accepted)
        XCTAssertEqual(admit(&window,pair:pairB,role:.client,generation:1,sequence:0,nonce:nonce(3)),.accepted)
        XCTAssertEqual(admit(&window,pair:pairA,role:.runtime,generation:1,sequence:0,nonce:nonce(4)),.accepted)
        XCTAssertEqual(admit(&window,pair:pairB,role:.runtime,generation:1,sequence:0,nonce:nonce(1)),.duplicate)
        XCTAssertEqual(admit(&window,pair:pairA,role:.client,generation:0,sequence:99,nonce:nonce(5)),.invalid)
        XCTAssertEqual(admit(&window,pair:pairA,role:.client,generation:2,sequence:0,nonce:nonce(5)),.accepted)
    }

    func testReplayWindowCapsAndExpiresEntries() {
        var window=ReplayWindow()
        for i in 0..<P2PNATLimits.replayEntries { XCTAssertEqual(admit(&window,pair:pair(i),role:.client,generation:1,sequence:0,nonce:nonce(i),expires:20,now:1),.accepted) }
        XCTAssertEqual(admit(&window,pair:pair(999),role:.client,generation:1,sequence:0,nonce:nonce(999),expires:20,now:1),.capacityExceeded)
        XCTAssertEqual(admit(&window,pair:pair(999),role:.client,generation:1,sequence:0,nonce:nonce(999),expires:700_001,now:1),.expired)
        XCTAssertEqual(admit(&window,pair:pair(999),role:.client,generation:1,sequence:0,nonce:nonce(999),expires:30,now:20),.accepted)
        XCTAssertEqual(window.count(now:20),1)
        XCTAssertEqual(admit(&window,pair:pair(998),role:.client,generation:1,sequence:0,nonce:nonce(998),expires:20,now:20),.expired)
    }

    func testReadinessRequiresExactOrderPerGeneration() {
        var invalid=ReadinessGate();XCTAssertTrue(invalid.beginAttempt(pairDigest:pairA,generation:4))
        XCTAssertFalse(invalid.apply(.identityVerified,generation:4));XCTAssertEqual(invalid.stage,.failed)
        XCTAssertFalse(invalid.apply(.pathReachable,generation:4))

        var gate=ReadinessGate();XCTAssertTrue(gate.beginAttempt(pairDigest:pairA,generation:4))
        XCTAssertTrue(gate.apply(.pathReachable,generation:4));XCTAssertTrue(gate.apply(.identityVerified,generation:4))
        XCTAssertTrue(gate.apply(.keyConfirmed,generation:4));XCTAssertTrue(gate.apply(.applicationReady,generation:4));XCTAssertEqual(gate.stage,.applicationReady)
    }

    func testFallbackResetAndStaleRaceFailClosed() {
        var gate=ReadinessGate();XCTAssertTrue(gate.beginAttempt(pairDigest:pairA,generation:4))
        XCTAssertTrue(gate.apply(.pathReachable,generation:4));XCTAssertTrue(gate.apply(.identityVerified,generation:4))
        XCTAssertTrue(gate.resetForFallback(pairDigest:pairA,generation:5));XCTAssertEqual(gate.stage,.attemptStarted)
        XCTAssertFalse(gate.apply(.keyConfirmed,generation:4));XCTAssertEqual(gate.stage,.failed)

        var substituted=ReadinessGate();XCTAssertTrue(substituted.beginAttempt(pairDigest:pairA,generation:1))
        XCTAssertFalse(substituted.resetForFallback(pairDigest:pairB,generation:2));XCTAssertEqual(substituted.stage,.failed)
    }

    func testReadinessAttemptAndRetryCapsFailClosed() {
        var pairCap=ReadinessGate();XCTAssertTrue(pairCap.beginAttempt(pairDigest:pairA,generation:1));XCTAssertTrue(pairCap.resetForFallback(pairDigest:pairA,generation:2));XCTAssertFalse(pairCap.resetForFallback(pairDigest:pairA,generation:3))
        var retryCap=ReadinessGate();XCTAssertTrue(retryCap.beginAttempt(pairDigest:pairB,generation:1))
        for _ in 0..<P2PNATLimits.retries { XCTAssertTrue(retryCap.apply(.pathReachable,generation:1));XCTAssertTrue(retryCap.retry(generation:1)) }
        XCTAssertFalse(retryCap.retry(generation:1));XCTAssertEqual(retryCap.stage,.failed)
    }

    private func candidate(_ priority:UInt32,last:UInt8=1)throws->P2PNATCandidate { try P2PNATCandidate(kind:.host,family:.ipv4,port:1024,priority:priority,foundation:Data(repeating:0,count:8),address:Data([8,8,8,last])) }
    private func admit(_ window:inout ReplayWindow,pair:String,role:P2PNATRole,generation:UInt64,sequence:UInt64,nonce:String,expires:UInt64=20,now:UInt64=10)->ReplayDecision { window.admit(pairDigest:pair,role:role,generation:generation,sequence:sequence,nonce:nonce,expires:expires,now:now) }
    private func nonce(_ value:Int)->String{String(value,radix:16).leftPadded(to:32)}
    private func pair(_ value:Int)->String{String(value,radix:16).leftPadded(to:64)}
    private var pairA:String{String(repeating:"a",count:64)}
    private var pairB:String{String(repeating:"b",count:64)}
}

private extension String { func leftPadded(to count:Int)->String{String(repeating:"0",count:max(0,count-self.count))+self} }
