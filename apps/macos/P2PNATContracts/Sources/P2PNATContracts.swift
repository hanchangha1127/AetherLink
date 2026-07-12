import CryptoKit
import Foundation

public enum P2PNATLimits {
    public static let sealedBytes = 16_384
    public static let candidateBlobBytes = 8_192
    public static let candidateBatchBytes = 8_291
    public static let relayCapabilityBytes = 404
    public static let identityTranscriptBytes = 532
    public static let pathReceiptBytes = 300
    public static let candidates = 32
    public static let ttlMilliseconds: UInt64 = 600_000
    public static let clockSkewMilliseconds: UInt64 = 30_000
    public static let replayEntries = 128
    public static let attemptsPerPair = 2
    public static let globalAttempts = 32
    public static let retries = 4
}

public enum P2PNATFreshness {
    public static func isFresh(expires: UInt64, now: UInt64) -> Bool {
        guard expires > 0 else { return false }
        let lowerBound = now > P2PNATLimits.clockSkewMilliseconds
            ? now - P2PNATLimits.clockSkewMilliseconds
            : 0
        let allowance = P2PNATLimits.ttlMilliseconds + P2PNATLimits.clockSkewMilliseconds
        let upperBound = now > UInt64.max - allowance ? UInt64.max : now + allowance
        return expires > lowerBound && expires <= upperBound
    }

    public static func isPathValidationFresh(validatedAt: UInt64, expires: UInt64, now: UInt64) -> Bool {
        guard validatedAt > 0, expires > validatedAt,
              expires - validatedAt <= P2PNATLimits.ttlMilliseconds else { return false }
        let validationUpperBound = now > UInt64.max - P2PNATLimits.clockSkewMilliseconds
            ? UInt64.max
            : now + P2PNATLimits.clockSkewMilliseconds
        return validatedAt <= validationUpperBound && isFresh(expires: expires, now: now)
    }
}

public enum P2PNATContractError: Error, Equatable {
    case invalidHeader
    case invalidObjectType
    case invalidVersion
    case invalidField
    case invalidFieldOrder
    case duplicateField
    case unknownField
    case trailingBytes
    case invalidLength
    case invalidInteger
    case invalidText
    case invalidValue
    case limitExceeded
    case candidatesNotCanonical
}

public enum P2PNATRole: String, Sendable { case client, runtime }
public enum P2PNATTransport: String, Sendable { case direct, relay }
public enum P2PNATFallback: String, Sendable { case none, direct_failed, consent_lost }

public enum CandidateKind: UInt8, Sendable { case host = 1, srflx = 2, prflx = 3, relay = 4 }
public enum CandidateFamily: UInt8, Sendable { case ipv4 = 4, ipv6 = 6 }
public enum CandidateTransport: UInt8, Sendable { case udp = 1 }

public struct P2PNATCandidate: Equatable, Hashable, Sendable {
    public let kind: CandidateKind
    public let family: CandidateFamily
    public let transport: CandidateTransport
    public let port: UInt16
    public let priority: UInt32
    public let foundation: Data
    public let address: Data

    public init(kind: CandidateKind, family: CandidateFamily, transport: CandidateTransport = .udp,
                port: UInt16, priority: UInt32, foundation: Data, address: Data) throws {
        guard port >= 1024, foundation.count == 8,
              address.count == (family == .ipv4 ? 4 : 16) else { throw P2PNATContractError.invalidValue }
        self.kind = kind
        self.family = family
        self.transport = transport
        self.port = port
        self.priority = priority
        self.foundation = foundation
        self.address = address
    }

    public var encodedBytes: Data {
        var data = Data([kind.rawValue, family.rawValue, transport.rawValue])
        data.appendBE(port); data.appendBE(priority); data.append(foundation)
        data.append(UInt8(address.count)); data.append(address)
        return data
    }
}

public struct CandidateBatch: Equatable, Sendable {
    public static let objectType: UInt8 = 1
    public let sessionId: String
    public let generation: UInt64
    public let sequence: UInt64
    public let expires: UInt64
    public let role: P2PNATRole
    public let candidates: [P2PNATCandidate]

    public init(sessionId: String, generation: UInt64, sequence: UInt64, expires: UInt64,
                role: P2PNATRole, candidates: [P2PNATCandidate]) throws {
        try validateHex(sessionId, count: 32)
        guard generation > 0, expires > 0, (1...P2PNATLimits.candidates).contains(candidates.count) else {
            throw P2PNATContractError.invalidValue
        }
        let encodings = candidates.map(\.encodedBytes)
        guard Set(encodings).count == encodings.count,
              zip(candidates, candidates.dropFirst()).allSatisfy({ lhs, rhs in
                  lhs.priority > rhs.priority || (lhs.priority == rhs.priority && lhs.encodedBytes.lexicographicallyPrecedes(rhs.encodedBytes))
              }) else { throw P2PNATContractError.candidatesNotCanonical }
        guard Self.encodeBlob(candidates).count <= P2PNATLimits.candidateBlobBytes else { throw P2PNATContractError.limitExceeded }
        self.sessionId = sessionId; self.generation = generation; self.sequence = sequence
        self.expires = expires; self.role = role; self.candidates = candidates
    }

    public func canonicalBytes() -> Data {
        CanonicalEncoder(type: Self.objectType).encode([
            .init(1, ascii(sessionId)), .init(2, be(generation)), .init(3, be(sequence)),
            .init(4, be(expires)), .init(5, ascii(role.rawValue)), .init(6, Self.encodeBlob(candidates))
        ])
    }

    public init(canonicalBytes data: Data) throws {
        guard data.count <= P2PNATLimits.candidateBatchBytes else { throw P2PNATContractError.limitExceeded }
        let f = try CanonicalDecoder(data, type: Self.objectType, tags: Array(1...6)).fields
        try self.init(sessionId: try text(f[0], asciiOnly: true), generation: try uint64(f[1]),
                      sequence: try uint64(f[2]), expires: try uint64(f[3]),
                      role: try enumValue(f[4], P2PNATRole.self), candidates: try Self.decodeBlob(f[5]))
    }

    public init(freshCanonicalBytes data: Data, now: UInt64) throws {
        try self.init(canonicalBytes: data)
        guard P2PNATFreshness.isFresh(expires: expires, now: now) else { throw P2PNATContractError.invalidValue }
    }

    private static func encodeBlob(_ candidates: [P2PNATCandidate]) -> Data {
        var data = Data(); data.appendBE(UInt16(candidates.count)); candidates.forEach { data.append($0.encodedBytes) }; return data
    }

    private static func decodeBlob(_ data: Data) throws -> [P2PNATCandidate] {
        guard data.count <= P2PNATLimits.candidateBlobBytes else { throw P2PNATContractError.limitExceeded }
        var cursor = ByteCursor(data)
        let count: UInt16 = try cursor.readBE()
        guard (1...P2PNATLimits.candidates).contains(Int(count)) else { throw P2PNATContractError.invalidValue }
        var result: [P2PNATCandidate] = []
        for _ in 0..<count {
            guard let kind = CandidateKind(rawValue: try cursor.byte()),
                  let family = CandidateFamily(rawValue: try cursor.byte()),
                  let transport = CandidateTransport(rawValue: try cursor.byte()) else { throw P2PNATContractError.invalidValue }
            let port: UInt16 = try cursor.readBE(); let priority: UInt32 = try cursor.readBE()
            let foundation = try cursor.read(8); let addressLength = Int(try cursor.byte())
            guard addressLength == (family == .ipv4 ? 4 : 16) else { throw P2PNATContractError.invalidLength }
            result.append(try P2PNATCandidate(kind: kind, family: family, transport: transport, port: port,
                                              priority: priority, foundation: foundation, address: try cursor.read(addressLength)))
        }
        guard cursor.isAtEnd else { throw P2PNATContractError.trailingBytes }
        return result
    }
}

public struct SealedRouteRecord: Equatable, Sendable {
    public static let objectType: UInt8 = 2
    public static let suite = "aetherlink-p2p-v1"
    public let sessionId: String; public let pairDigest: String; public let role: P2PNATRole
    public let generation: UInt64; public let sequence: UInt64; public let expires: UInt64
    public let nonce: String; public let ephemeralKey: Data; public let sealNonce: Data; public let ciphertext: Data

    public init(sessionId: String, pairDigest: String, role: P2PNATRole, generation: UInt64, sequence: UInt64,
                expires: UInt64, nonce: String, ephemeralKey: Data, sealNonce: Data, ciphertext: Data) throws {
        try validateHex(sessionId, count: 32); try validateHex(pairDigest, count: 64); try validateHex(nonce, count: 32)
        guard generation > 0, expires > 0, isValidP256Key(ephemeralKey),
              sealNonce.count == 12, !ciphertext.isEmpty else { throw P2PNATContractError.invalidValue }
        let encodedSize = 6 + (11 * 5) + Self.suite.utf8.count + sessionId.utf8.count + pairDigest.utf8.count
            + role.rawValue.utf8.count + 24 + nonce.utf8.count + ephemeralKey.count + sealNonce.count + ciphertext.count
        guard encodedSize <= P2PNATLimits.sealedBytes else { throw P2PNATContractError.limitExceeded }
        self.sessionId=sessionId; self.pairDigest=pairDigest; self.role=role; self.generation=generation
        self.sequence=sequence; self.expires=expires; self.nonce=nonce; self.ephemeralKey=ephemeralKey
        self.sealNonce=sealNonce; self.ciphertext=ciphertext
    }

    public func canonicalBytes() -> Data { CanonicalEncoder(type: Self.objectType).encode([
        .init(1, ascii(Self.suite)), .init(2, ascii(sessionId)), .init(3, ascii(pairDigest)), .init(4, ascii(role.rawValue)),
        .init(5, be(generation)), .init(6, be(sequence)), .init(7, be(expires)), .init(8, ascii(nonce)),
        .init(9, ephemeralKey), .init(10, sealNonce), .init(11, ciphertext)]) }

    public init(canonicalBytes d: Data) throws {
        guard d.count <= P2PNATLimits.sealedBytes else { throw P2PNATContractError.limitExceeded }
        let f = try CanonicalDecoder(d, type: Self.objectType, tags: Array(1...11)).fields
        guard try text(f[0], asciiOnly: true) == Self.suite else { throw P2PNATContractError.invalidValue }
        try self.init(sessionId: text(f[1], asciiOnly: true), pairDigest: text(f[2], asciiOnly: true), role: enumValue(f[3], P2PNATRole.self),
                      generation: uint64(f[4]), sequence: uint64(f[5]), expires: uint64(f[6]), nonce: text(f[7], asciiOnly: true),
                      ephemeralKey: f[8], sealNonce: f[9], ciphertext: f[10])
    }

    public init(freshCanonicalBytes d: Data, now: UInt64) throws {
        try self.init(canonicalBytes: d)
        guard P2PNATFreshness.isFresh(expires: expires, now: now) else { throw P2PNATContractError.invalidValue }
    }
}

public struct RelayCapability: Equatable, Sendable {
    public static let objectType: UInt8 = 3; public static let suite = "aetherlink-p2p-v1"
    public let sessionId: String; public let pairDigest: String; public let clientFingerprint: String
    public let runtimeFingerprint: String; public let relayServiceDigest: String; public let expires: UInt64
    public let quotaBytes: UInt64; public let nonce: String

    public init(sessionId: String, pairDigest: String, clientFingerprint: String, runtimeFingerprint: String,
                relayServiceDigest: String, expires: UInt64, quotaBytes: UInt64, nonce: String) throws {
        try validateHex(sessionId,count:32); for value in [pairDigest,clientFingerprint,runtimeFingerprint,relayServiceDigest] { try validateHex(value,count:64) }
        try validateHex(nonce,count:32); guard expires > 0, quotaBytes > 0 else { throw P2PNATContractError.invalidValue }
        self.sessionId=sessionId; self.pairDigest=pairDigest; self.clientFingerprint=clientFingerprint
        self.runtimeFingerprint=runtimeFingerprint; self.relayServiceDigest=relayServiceDigest; self.expires=expires
        self.quotaBytes=quotaBytes; self.nonce=nonce
    }
    public func canonicalBytes() -> Data { CanonicalEncoder(type: Self.objectType).encode([
        .init(1,ascii(Self.suite)),.init(2,ascii(sessionId)),.init(3,ascii(pairDigest)),.init(4,ascii(clientFingerprint)),
        .init(5,ascii(runtimeFingerprint)),.init(6,ascii(relayServiceDigest)),.init(7,be(expires)),.init(8,be(quotaBytes)),.init(9,ascii(nonce))]) }
    public init(canonicalBytes d: Data) throws { guard d.count <= P2PNATLimits.relayCapabilityBytes else { throw P2PNATContractError.limitExceeded }; let f=try CanonicalDecoder(d,type:Self.objectType,tags:Array(1...9)).fields
        guard try text(f[0],asciiOnly:true)==Self.suite else { throw P2PNATContractError.invalidValue }
        try self.init(sessionId:text(f[1],asciiOnly:true),pairDigest:text(f[2],asciiOnly:true),clientFingerprint:text(f[3],asciiOnly:true),
                      runtimeFingerprint:text(f[4],asciiOnly:true),relayServiceDigest:text(f[5],asciiOnly:true),expires:uint64(f[6]),quotaBytes:uint64(f[7]),nonce:text(f[8],asciiOnly:true)) }
    public init(freshCanonicalBytes d:Data,now:UInt64)throws{try self.init(canonicalBytes:d);guard P2PNATFreshness.isFresh(expires:expires,now:now) else{throw P2PNATContractError.invalidValue}}
}

public struct IdentitySessionTranscript: Equatable, Sendable {
    public static let objectType: UInt8=4; public static let suite="aetherlink-p2p-v1"
    public let sessionId:String; public let pairDigest:String; public let clientFingerprint:String; public let runtimeFingerprint:String
    public let clientKey:Data; public let runtimeKey:Data; public let generation:UInt64; public let pathReceiptDigest:String
    public let transport:P2PNATTransport; public let fallback:P2PNATFallback; public let protocolFloor:UInt32
    public init(sessionId:String,pairDigest:String,clientFingerprint:String,runtimeFingerprint:String,clientKey:Data,runtimeKey:Data,
                generation:UInt64,pathReceiptDigest:String,transport:P2PNATTransport,fallback:P2PNATFallback,protocolFloor:UInt32=1) throws {
        try validateHex(sessionId,count:32); for v in [pairDigest,clientFingerprint,runtimeFingerprint,pathReceiptDigest] { try validateHex(v,count:64) }
        guard isValidP256Key(clientKey),isValidP256Key(runtimeKey),generation>0,protocolFloor==1 else { throw P2PNATContractError.invalidValue }
        self.sessionId=sessionId;self.pairDigest=pairDigest;self.clientFingerprint=clientFingerprint;self.runtimeFingerprint=runtimeFingerprint
        self.clientKey=clientKey;self.runtimeKey=runtimeKey;self.generation=generation;self.pathReceiptDigest=pathReceiptDigest
        self.transport=transport;self.fallback=fallback;self.protocolFloor=protocolFloor
    }
    public func canonicalBytes()->Data { CanonicalEncoder(type:Self.objectType).encode([
        .init(1,ascii(Self.suite)),.init(2,ascii(sessionId)),.init(3,ascii(pairDigest)),.init(4,ascii(clientFingerprint)),.init(5,ascii(runtimeFingerprint)),
        .init(6,clientKey),.init(7,runtimeKey),.init(8,be(generation)),.init(9,ascii(pathReceiptDigest)),.init(10,ascii(transport.rawValue)),
        .init(11,ascii(fallback.rawValue)),.init(12,be(protocolFloor))]) }
    public var digest:Data { Data(SHA256.hash(data:canonicalBytes())) }
    public func keyConfirmation(key:Data,role:P2PNATRole)throws->Data { guard key.count==32 else { throw P2PNATContractError.invalidLength }
        let input=canonicalBytes()+ascii("aetherlink-p2p-v1:key-confirmation:"+role.rawValue)
        return Data(HMAC<SHA256>.authenticationCode(for:input,using:SymmetricKey(data:key))) }
    public init(canonicalBytes d:Data)throws { guard d.count <= P2PNATLimits.identityTranscriptBytes else { throw P2PNATContractError.limitExceeded }; let f=try CanonicalDecoder(d,type:Self.objectType,tags:Array(1...12)).fields
        guard try text(f[0],asciiOnly:true)==Self.suite else { throw P2PNATContractError.invalidValue }
        try self.init(sessionId:text(f[1],asciiOnly:true),pairDigest:text(f[2],asciiOnly:true),clientFingerprint:text(f[3],asciiOnly:true),runtimeFingerprint:text(f[4],asciiOnly:true),clientKey:f[5],runtimeKey:f[6],generation:uint64(f[7]),pathReceiptDigest:text(f[8],asciiOnly:true),transport:enumValue(f[9],P2PNATTransport.self),fallback:enumValue(f[10],P2PNATFallback.self),protocolFloor:uint32(f[11])) }
}

public struct PathValidationReceipt: Equatable, Sendable {
    public static let objectType:UInt8=5
    public let sessionId:String;public let generation:UInt64;public let candidatePairDigest:String;public let transport:P2PNATTransport
    public let clientObserved:String;public let runtimeObserved:String;public let validatedAt:UInt64;public let expires:UInt64
    public init(sessionId:String,generation:UInt64,candidatePairDigest:String,transport:P2PNATTransport,clientObserved:String,runtimeObserved:String,validatedAt:UInt64,expires:UInt64)throws {
        try validateHex(sessionId,count:32);for v in [candidatePairDigest,clientObserved,runtimeObserved] { try validateHex(v,count:64) }
        guard generation>0,validatedAt>0,expires>validatedAt,expires-validatedAt<=P2PNATLimits.ttlMilliseconds else { throw P2PNATContractError.invalidValue }
        self.sessionId=sessionId;self.generation=generation;self.candidatePairDigest=candidatePairDigest;self.transport=transport
        self.clientObserved=clientObserved;self.runtimeObserved=runtimeObserved;self.validatedAt=validatedAt;self.expires=expires
    }
    public func canonicalBytes()->Data { CanonicalEncoder(type:Self.objectType).encode([.init(1,ascii(sessionId)),.init(2,be(generation)),.init(3,ascii(candidatePairDigest)),.init(4,ascii(transport.rawValue)),.init(5,ascii(clientObserved)),.init(6,ascii(runtimeObserved)),.init(7,be(validatedAt)),.init(8,be(expires))]) }
    public init(canonicalBytes d:Data)throws { guard d.count <= P2PNATLimits.pathReceiptBytes else { throw P2PNATContractError.limitExceeded }; let f=try CanonicalDecoder(d,type:Self.objectType,tags:Array(1...8)).fields
        try self.init(sessionId:text(f[0],asciiOnly:true),generation:uint64(f[1]),candidatePairDigest:text(f[2],asciiOnly:true),transport:enumValue(f[3],P2PNATTransport.self),clientObserved:text(f[4],asciiOnly:true),runtimeObserved:text(f[5],asciiOnly:true),validatedAt:uint64(f[6]),expires:uint64(f[7])) }
    public init(freshCanonicalBytes d:Data,now:UInt64)throws{try self.init(canonicalBytes:d);guard P2PNATFreshness.isPathValidationFresh(validatedAt:validatedAt,expires:expires,now:now) else{throw P2PNATContractError.invalidValue}}
}

private let magic=Data("ALP1".utf8), version:UInt8=1
private struct Field { let tag:UInt8;let value:Data;init(_ tag:UInt8,_ value:Data){self.tag=tag;self.value=value} }
private struct CanonicalEncoder { let type:UInt8;func encode(_ fields:[Field])->Data { var d=magic;d.append(type);d.append(version);for f in fields{d.append(f.tag);d.appendBE(UInt32(f.value.count));d.append(f.value)};return d } }
private struct CanonicalDecoder { let fields:[Data]
    init(_ data:Data,type:UInt8,tags:[Int])throws { var c=ByteCursor(data);guard try c.read(4)==magic else{throw P2PNATContractError.invalidHeader};guard try c.byte()==type else{throw P2PNATContractError.invalidObjectType};guard try c.byte()==version else{throw P2PNATContractError.invalidVersion};var values:[Data]=[]
        for expected in tags { guard !c.isAtEnd else{throw P2PNATContractError.invalidField};let actual=try c.byte();if Int(actual)<expected{throw P2PNATContractError.duplicateField};if Int(actual)>expected{throw (tags.contains(Int(actual)) ? P2PNATContractError.invalidFieldOrder:P2PNATContractError.unknownField)};let n:UInt32=try c.readBE();guard UInt64(n)<=UInt64(Int.max) else{throw P2PNATContractError.invalidLength};values.append(try c.read(Int(n))) }
        guard c.isAtEnd else{throw P2PNATContractError.trailingBytes};fields=values }
}
private struct ByteCursor {
    let data: Data
    var offset = 0
    init(_ d: Data) { data = d }
    var isAtEnd: Bool { offset == data.count }
    mutating func byte()throws->UInt8{guard offset<data.count else{throw P2PNATContractError.invalidLength};defer{offset+=1};return data[offset]}
    mutating func read(_ n:Int)throws->Data{guard n>=0,offset<=data.count-n else{throw P2PNATContractError.invalidLength};defer{offset+=n};return data.subdata(in:offset..<offset+n)}
    mutating func readBE<T:FixedWidthInteger>()throws->T{let bytes=try read(MemoryLayout<T>.size);return bytes.reduce(T.zero){($0<<8)|T($1)}} }
private func ascii(_ s:String)->Data{Data(s.utf8)}
private func text(_ d:Data,asciiOnly:Bool)throws->String{guard let s=String(data:d,encoding:.utf8),Data(s.utf8)==d,(!asciiOnly||d.allSatisfy{$0<128}) else{throw P2PNATContractError.invalidText};return s}
private func enumValue<T:RawRepresentable>(_ d:Data,_ type:T.Type)throws->T where T.RawValue==String{guard let v=T(rawValue:try text(d,asciiOnly:true)) else{throw P2PNATContractError.invalidValue};return v}
private func validateHex(_ s:String,count:Int)throws{guard s.utf8.count==count,s.utf8.allSatisfy({($0>=48&&$0<=57)||($0>=97&&$0<=102)}) else{throw P2PNATContractError.invalidValue}}
private func isValidP256Key(_ data:Data)->Bool{(try? P256.KeyAgreement.PublicKey(x963Representation:data)) != nil}
private func be<T:FixedWidthInteger>(_ v:T)->Data{var d=Data();d.appendBE(v);return d}
private func uint64(_ d:Data)throws->UInt64{guard d.count==8 else{throw P2PNATContractError.invalidInteger};var c=ByteCursor(d);return try c.readBE()}
private func uint32(_ d:Data)throws->UInt32{guard d.count==4 else{throw P2PNATContractError.invalidInteger};var c=ByteCursor(d);return try c.readBE()}
private extension Data { mutating func appendBE<T:FixedWidthInteger>(_ value:T){for shift in stride(from:(MemoryLayout<T>.size-1)*8,through:0,by:-8){append(UInt8(truncatingIfNeeded:value>>T(shift)))}} }
