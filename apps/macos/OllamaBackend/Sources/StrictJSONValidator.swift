import Foundation

public enum StrictJSONValidationError: Error, Equatable, Sendable {
    case malformed
    case duplicateObjectKey
    case nestingTooDeep
}

public enum StrictJSONValidator {
    public static func validateNoDuplicateObjectKeys(in data: Data) throws {
        var parser = Parser(bytes: Array(data), maximumDepth: 128)
        try parser.parseDocument()
    }
}

private struct Parser {
    private let bytes: [UInt8]
    private let maximumDepth: Int
    private var index = 0

    init(bytes: [UInt8], maximumDepth: Int) {
        self.bytes = bytes
        self.maximumDepth = maximumDepth
    }

    mutating func parseDocument() throws {
        skipWhitespace()
        try parseValue(depth: 0)
        skipWhitespace()
        guard index == bytes.count else {
            throw StrictJSONValidationError.malformed
        }
    }

    private mutating func parseValue(depth: Int) throws {
        guard index < bytes.count else {
            throw StrictJSONValidationError.malformed
        }
        switch bytes[index] {
        case CharacterByte.objectStart:
            try parseObject(depth: depth)
        case CharacterByte.arrayStart:
            try parseArray(depth: depth)
        case CharacterByte.quote:
            _ = try scanStringToken()
        case CharacterByte.trueStart:
            try consumeLiteral([0x74, 0x72, 0x75, 0x65])
        case CharacterByte.falseStart:
            try consumeLiteral([0x66, 0x61, 0x6c, 0x73, 0x65])
        case CharacterByte.nullStart:
            try consumeLiteral([0x6e, 0x75, 0x6c, 0x6c])
        case CharacterByte.minus, CharacterByte.zero...CharacterByte.nine:
            try parseNumber()
        default:
            throw StrictJSONValidationError.malformed
        }
    }

    private mutating func parseObject(depth: Int) throws {
        guard depth < maximumDepth else {
            throw StrictJSONValidationError.nestingTooDeep
        }
        index += 1
        skipWhitespace()
        if consume(CharacterByte.objectEnd) {
            return
        }

        var keys = Set<String>()
        while true {
            guard index < bytes.count, bytes[index] == CharacterByte.quote else {
                throw StrictJSONValidationError.malformed
            }
            let keyRange = try scanStringToken()
            let key: String
            do {
                key = try JSONDecoder().decode(String.self, from: Data(bytes[keyRange]))
            } catch {
                throw StrictJSONValidationError.malformed
            }
            guard keys.insert(key).inserted else {
                throw StrictJSONValidationError.duplicateObjectKey
            }

            skipWhitespace()
            guard consume(CharacterByte.colon) else {
                throw StrictJSONValidationError.malformed
            }
            skipWhitespace()
            try parseValue(depth: depth + 1)
            skipWhitespace()
            if consume(CharacterByte.objectEnd) {
                return
            }
            guard consume(CharacterByte.comma) else {
                throw StrictJSONValidationError.malformed
            }
            skipWhitespace()
        }
    }

    private mutating func parseArray(depth: Int) throws {
        guard depth < maximumDepth else {
            throw StrictJSONValidationError.nestingTooDeep
        }
        index += 1
        skipWhitespace()
        if consume(CharacterByte.arrayEnd) {
            return
        }

        while true {
            try parseValue(depth: depth + 1)
            skipWhitespace()
            if consume(CharacterByte.arrayEnd) {
                return
            }
            guard consume(CharacterByte.comma) else {
                throw StrictJSONValidationError.malformed
            }
            skipWhitespace()
        }
    }

    private mutating func scanStringToken() throws -> Range<Int> {
        let start = index
        guard consume(CharacterByte.quote) else {
            throw StrictJSONValidationError.malformed
        }

        while index < bytes.count {
            let byte = bytes[index]
            index += 1
            switch byte {
            case CharacterByte.quote:
                return start..<index
            case CharacterByte.escape:
                guard index < bytes.count else {
                    throw StrictJSONValidationError.malformed
                }
                let escape = bytes[index]
                index += 1
                switch escape {
                case CharacterByte.quote, CharacterByte.escape, CharacterByte.slash,
                     CharacterByte.backspaceEscape, CharacterByte.formFeedEscape,
                     CharacterByte.newlineEscape, CharacterByte.carriageReturnEscape,
                     CharacterByte.tabEscape:
                    break
                case CharacterByte.unicodeEscape:
                    guard index + 4 <= bytes.count,
                          bytes[index..<(index + 4)].allSatisfy(Self.isHexDigit) else {
                        throw StrictJSONValidationError.malformed
                    }
                    index += 4
                default:
                    throw StrictJSONValidationError.malformed
                }
            case 0x00...0x1f:
                throw StrictJSONValidationError.malformed
            default:
                break
            }
        }
        throw StrictJSONValidationError.malformed
    }

    private mutating func parseNumber() throws {
        _ = consume(CharacterByte.minus)
        guard index < bytes.count else {
            throw StrictJSONValidationError.malformed
        }

        if consume(CharacterByte.zero) {
            // A leading zero is complete unless a fraction or exponent follows.
        } else {
            guard bytes[index] >= CharacterByte.one, bytes[index] <= CharacterByte.nine else {
                throw StrictJSONValidationError.malformed
            }
            index += 1
            consumeDigits()
        }

        if consume(CharacterByte.decimalPoint) {
            guard consumeDigit() else {
                throw StrictJSONValidationError.malformed
            }
            consumeDigits()
        }

        if consume(CharacterByte.lowerExponent) || consume(CharacterByte.upperExponent) {
            _ = consume(CharacterByte.plus) || consume(CharacterByte.minus)
            guard consumeDigit() else {
                throw StrictJSONValidationError.malformed
            }
            consumeDigits()
        }
    }

    private mutating func consumeLiteral(_ literal: [UInt8]) throws {
        guard index + literal.count <= bytes.count,
              Array(bytes[index..<(index + literal.count)]) == literal else {
            throw StrictJSONValidationError.malformed
        }
        index += literal.count
    }

    private mutating func consumeDigits() {
        while consumeDigit() {}
    }

    private mutating func consumeDigit() -> Bool {
        guard index < bytes.count,
              bytes[index] >= CharacterByte.zero,
              bytes[index] <= CharacterByte.nine else {
            return false
        }
        index += 1
        return true
    }

    private mutating func skipWhitespace() {
        while index < bytes.count {
            switch bytes[index] {
            case 0x20, 0x09, 0x0a, 0x0d:
                index += 1
            default:
                return
            }
        }
    }

    private mutating func consume(_ byte: UInt8) -> Bool {
        guard index < bytes.count, bytes[index] == byte else {
            return false
        }
        index += 1
        return true
    }

    private static func isHexDigit(_ byte: UInt8) -> Bool {
        (byte >= 0x30 && byte <= 0x39)
            || (byte >= 0x41 && byte <= 0x46)
            || (byte >= 0x61 && byte <= 0x66)
    }
}

private enum CharacterByte {
    static let quote: UInt8 = 0x22
    static let plus: UInt8 = 0x2b
    static let comma: UInt8 = 0x2c
    static let minus: UInt8 = 0x2d
    static let decimalPoint: UInt8 = 0x2e
    static let slash: UInt8 = 0x2f
    static let zero: UInt8 = 0x30
    static let one: UInt8 = 0x31
    static let nine: UInt8 = 0x39
    static let colon: UInt8 = 0x3a
    static let arrayStart: UInt8 = 0x5b
    static let escape: UInt8 = 0x5c
    static let arrayEnd: UInt8 = 0x5d
    static let falseStart: UInt8 = 0x66
    static let newlineEscape: UInt8 = 0x6e
    static let nullStart: UInt8 = 0x6e
    static let carriageReturnEscape: UInt8 = 0x72
    static let trueStart: UInt8 = 0x74
    static let tabEscape: UInt8 = 0x74
    static let unicodeEscape: UInt8 = 0x75
    static let objectStart: UInt8 = 0x7b
    static let objectEnd: UInt8 = 0x7d
    static let lowerExponent: UInt8 = 0x65
    static let upperExponent: UInt8 = 0x45
    static let backspaceEscape: UInt8 = 0x62
    static let formFeedEscape: UInt8 = 0x66
}
