import Foundation
import P2PNATContracts

public enum CandidatePolicyError: Error, Equatable { case invalidAddress, forbiddenAddress, duplicate, excess }

public struct CandidatePolicy: Sendable {
    public let allowPrivateSameLink: Bool
    public init(allowPrivateSameLink: Bool = false) { self.allowPrivateSameLink = allowPrivateSameLink }

    public func validate(_ candidates: [P2PNATCandidate]) throws {
        guard (1...P2PNATLimits.candidates).contains(candidates.count) else { throw CandidatePolicyError.excess }
        guard Set(candidates).count == candidates.count else { throw CandidatePolicyError.duplicate }
        for candidate in candidates { try validateAddress(candidate.address, family: candidate.family) }
    }

    public func validateAddress(_ address: Data, family: CandidateFamily) throws {
        guard address.count == (family == .ipv4 ? 4 : 16) else { throw CandidatePolicyError.invalidAddress }
        let b = [UInt8](address)
        let forbidden: Bool
        if family == .ipv4 {
            let unspecified=b.allSatisfy{$0==0};let loopback=b[0]==127;let multicast=(224...239).contains(b[0])
            let linkLocal=b[0]==169&&b[1]==254;let broadcast=b.allSatisfy{$0==255}
            let privateAddress=b[0]==10||(b[0]==172&&(16...31).contains(b[1]))||(b[0]==192&&b[1]==168)
            forbidden=unspecified||loopback||multicast||linkLocal||broadcast||(privateAddress && !allowPrivateSameLink)
        } else {
            let unspecified=b.allSatisfy{$0==0};let loopback=b.dropLast().allSatisfy{$0==0}&&b.last==1
            let multicast=b[0]==0xff;let linkLocal=b[0]==0xfe&&(b[1]&0xc0)==0x80
            let mapped=b[0..<10].allSatisfy{$0==0}&&b[10]==0xff&&b[11]==0xff
            let privateAddress=(b[0]&0xfe)==0xfc
            forbidden=unspecified||loopback||multicast||linkLocal||mapped||(privateAddress && !allowPrivateSameLink)
        }
        if forbidden { throw CandidatePolicyError.forbiddenAddress }
    }
}

public enum ReplayDecision: Equatable { case accepted, stale, duplicate, expired, capacityExceeded, invalid }

public struct ReplayWindow: Sendable {
    private struct Scope: Hashable, Sendable { let pairDigest:String;let role:P2PNATRole }
    private struct Entry: Sendable { let scope:Scope;let generation:UInt64;let sequence:UInt64;let expires:UInt64 }
    private var entries:[String:Entry]=[:]
    public init() {}
    public mutating func count(now:UInt64)->Int{entries=entries.filter{$0.value.expires>now};return entries.count}

    public mutating func admit(pairDigest:String,role:P2PNATRole,generation:UInt64,sequence:UInt64,nonce:String,expires:UInt64,now:UInt64)->ReplayDecision {
        entries=entries.filter{$0.value.expires>now}
        guard isLowerHex(pairDigest,count:64),generation>0,isLowerHex(nonce,count:32) else{return .invalid}
        guard expires>now,P2PNATFreshness.isFresh(expires:expires,now:now) else{return .expired}
        if entries[nonce] != nil { return .duplicate }
        let scope=Scope(pairDigest:pairDigest,role:role)
        let scoped=entries.values.filter{$0.scope==scope}
        if let old=scoped.max(by:{($0.generation,$0.sequence)<($1.generation,$1.sequence)}) {
            guard generation>=old.generation else{return .stale}
            if generation==old.generation {
                guard sequence>=old.sequence else{return .stale}
                guard sequence>old.sequence else{return .duplicate}
            }
        }
        guard entries.count<P2PNATLimits.replayEntries else{return .capacityExceeded}
        entries[nonce]=Entry(scope:scope,generation:generation,sequence:sequence,expires:expires)
        return .accepted
    }
}

public enum ReadinessStage:Int,Equatable,Sendable { case idle,attemptStarted,pathReachable,identityVerified,keyConfirmed,applicationReady,failed }
public enum ReadinessEvent:Sendable { case pathReachable,identityVerified,keyConfirmed,applicationReady }

public struct ReadinessGate: Sendable {
    private var attemptsByPair:[String:Int]=[:]
    private var globalAttempts=0
    private var retries=0
    public private(set) var pairDigest:String?
    public private(set) var generation:UInt64?
    public private(set) var stage:ReadinessStage = .idle
    public init(){}
    @discardableResult public mutating func beginAttempt(pairDigest:String,generation:UInt64)->Bool {
        guard isLowerHex(pairDigest,count:64),generation>0 else{return fail()}
        if let current=generationValue, generation<=current{return fail()}
        let pairAttempts=attemptsByPair[pairDigest,default:0]
        guard pairAttempts<P2PNATLimits.attemptsPerPair,globalAttempts<P2PNATLimits.globalAttempts else{return fail()}
        attemptsByPair[pairDigest]=pairAttempts+1;globalAttempts+=1;self.pairDigest=pairDigest
        self.generation=generation;retries=0;stage = .attemptStarted;return true
    }
    @discardableResult public mutating func apply(_ event:ReadinessEvent,generation:UInt64)->Bool {
        guard generation==self.generation else{return fail()}
        let required:ReadinessStage;let next:ReadinessStage
        switch event {case .pathReachable:(required,next)=(.attemptStarted,.pathReachable);case .identityVerified:(required,next)=(.pathReachable,.identityVerified);case .keyConfirmed:(required,next)=(.identityVerified,.keyConfirmed);case .applicationReady:(required,next)=(.keyConfirmed,.applicationReady)}
        guard stage==required else{return fail()};stage=next;return true
    }
    @discardableResult public mutating func retry(generation:UInt64)->Bool {
        guard generation==self.generation,stage != .idle,stage != .applicationReady,stage != .failed,retries<P2PNATLimits.retries else{return fail()}
        retries+=1;stage = .attemptStarted;return true
    }
    @discardableResult public mutating func resetForFallback(pairDigest:String,generation:UInt64)->Bool {
        guard pairDigest==self.pairDigest,let current=self.generation,generation>current else{return fail()}
        return beginAttempt(pairDigest:pairDigest,generation:generation)
    }
    private var generationValue:UInt64?{generation}
    private mutating func fail()->Bool{stage = .failed;return false}
}

private func isLowerHex(_ value:String,count:Int)->Bool {
    value.utf8.count==count && value.utf8.allSatisfy{($0>=48&&$0<=57)||($0>=97&&$0<=102)}
}
