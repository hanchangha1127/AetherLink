import Foundation

enum RuntimeApprovalReviewText {
    static let maximumUTF8Bytes = 512
    static let fallbackDeviceName = "Trusted device"
    private static let maximumProjectionPasses = 4
    private static let joinsFollowingPattern = try? NSRegularExpression(
        pattern: "\\A(?:\\p{Joining_Type=Dual_Joining}|\\p{Joining_Type=Left_Joining})\\z"
    )
    private static let joinsPrecedingPattern = try? NSRegularExpression(
        pattern: "\\A(?:\\p{Joining_Type=Dual_Joining}|\\p{Joining_Type=Right_Joining})\\z"
    )
    private static let joiningTransparentPattern = try? NSRegularExpression(
        pattern: "\\A\\p{Joining_Type=Transparent}\\z"
    )
    private static let extendedPictographicPattern = try? NSRegularExpression(
        pattern: "\\A\\p{Extended_Pictographic}\\z"
    )

    static func canonicalDeviceName(_ value: String) -> String {
        canonicalDisplayString(value) ?? fallbackDeviceName
    }

    static func isCanonicalDisplayString(_ value: String) -> Bool {
        guard let canonical = canonicalDisplayString(value) else {
            return false
        }
        return value.utf8.elementsEqual(canonical.utf8)
    }

    static func isCanonicalKeyFingerprint(_ value: String) -> Bool {
        let scalars = Array(value.unicodeScalars)
        guard scalars.count == 17 else { return false }
        return scalars.enumerated().allSatisfy { index, scalar in
            if index % 3 == 2 {
                return scalar.value == 0x3A
            }
            return (0x30...0x39).contains(scalar.value)
                || (0x41...0x46).contains(scalar.value)
        }
    }

    private static func canonicalDisplayString(_ value: String) -> String? {
        var candidate = value
        for _ in 0..<maximumProjectionPasses {
            guard let projected = projectDisplayString(candidate) else {
                return nil
            }
            if projected.utf8.elementsEqual(candidate.utf8) {
                return projected
            }
            candidate = projected
        }
        guard let stable = projectDisplayString(candidate),
              stable.utf8.elementsEqual(candidate.utf8) else {
            return nil
        }
        return stable
    }

    private static func projectDisplayString(_ value: String) -> String? {
        let normalized = value.precomposedStringWithCanonicalMapping
        let sourceScalars = Array(normalized.unicodeScalars)
        let approvedSubdivisionTags = approvedSubdivisionTagPositions(in: sourceScalars)
        var safeScalars: [Unicode.Scalar] = []

        for (index, scalar) in sourceScalars.enumerated() {
            guard !CharacterSet.newlines.contains(scalar),
                  !isBidirectionalFormattingScalar(scalar),
                  !isUnsupportedDisplayScalar(scalar) else {
                continue
            }
            if scalar.properties.isDefaultIgnorableCodePoint {
                guard isContextualDefaultIgnorable(
                    at: index,
                    in: sourceScalars,
                    approvedSubdivisionTags: approvedSubdivisionTags
                ) else {
                    continue
                }
            } else if CharacterSet.controlCharacters.contains(scalar) {
                continue
            }
            safeScalars.append(scalar)
        }

        let cleaned = String(String.UnicodeScalarView(safeScalars))
            .precomposedStringWithCanonicalMapping
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard cleaned.unicodeScalars.contains(where: isVisibleBase) else {
            return nil
        }

        var bounded = ""
        for character in cleaned {
            let candidate = bounded + String(character)
            guard candidate.utf8.count <= maximumUTF8Bytes else {
                break
            }
            bounded = candidate
        }
        let canonical = bounded
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .precomposedStringWithCanonicalMapping
        guard canonical.utf8.count <= maximumUTF8Bytes,
              canonical.unicodeScalars.contains(where: isVisibleBase) else {
            return nil
        }
        return canonical
    }

    private static func isVisibleBase(_ scalar: Unicode.Scalar) -> Bool {
        guard !scalar.properties.isDefaultIgnorableCodePoint,
              !CharacterSet.whitespacesAndNewlines.contains(scalar),
              !isUnsupportedDisplayScalar(scalar) else {
            return false
        }
        switch scalar.properties.generalCategory {
        case .control, .format, .surrogate, .privateUse, .unassigned,
             .nonspacingMark, .spacingMark, .enclosingMark,
             .spaceSeparator, .lineSeparator, .paragraphSeparator:
            return false
        default:
            return true
        }
    }

    private static func isUnsupportedDisplayScalar(_ scalar: Unicode.Scalar) -> Bool {
        switch scalar.properties.generalCategory {
        case .surrogate, .privateUse, .unassigned:
            return true
        default:
            return scalar.value == 0x2800
        }
    }

    private static func isContextualDefaultIgnorable(
        at index: Int,
        in scalars: [Unicode.Scalar],
        approvedSubdivisionTags: [Bool]
    ) -> Bool {
        let scalar = scalars[index]
        switch scalar.value {
        case 0x200C:
            return isViramaJoinControlContext(at: index, in: scalars)
                || isJoiningZWNJContext(at: index, in: scalars)
        case 0x200D:
            return isViramaJoinControlContext(at: index, in: scalars)
                || isEmojiZWJContext(at: index, in: scalars)
        case 0xFE00...0xFE0D:
            return index > 0 && scalars[index - 1].properties.isIdeographic
        case 0xFE0E, 0xFE0F:
            guard index > 0 else { return false }
            let base = scalars[index - 1]
            return base.properties.isEmoji || base.properties.isIdeographic
        case 0xE0020...0xE007F:
            return approvedSubdivisionTags[index]
        case 0xE0100...0xE01EF:
            return index > 0 && scalars[index - 1].properties.isIdeographic
        default:
            return false
        }
    }

    private static func isViramaJoinControlContext(
        at index: Int,
        in scalars: [Unicode.Scalar]
    ) -> Bool {
        index > 0 && scalars[index - 1].properties.canonicalCombiningClass == .virama
    }

    private static func isJoiningZWNJContext(
        at index: Int,
        in scalars: [Unicode.Scalar]
    ) -> Bool {
        guard let before = joiningScalar(before: index, in: scalars),
              let after = joiningScalar(after: index, in: scalars) else {
            return false
        }
        return matches(joinsFollowingPattern, scalar: before)
            && matches(joinsPrecedingPattern, scalar: after)
    }

    private static func joiningScalar(
        before index: Int,
        in scalars: [Unicode.Scalar]
    ) -> Unicode.Scalar? {
        guard index > 0 else { return nil }
        for scalar in scalars[..<index].reversed() {
            if matches(joiningTransparentPattern, scalar: scalar) { continue }
            return scalar
        }
        return nil
    }

    private static func joiningScalar(
        after index: Int,
        in scalars: [Unicode.Scalar]
    ) -> Unicode.Scalar? {
        guard index + 1 < scalars.count else { return nil }
        for scalar in scalars[(index + 1)...] {
            if matches(joiningTransparentPattern, scalar: scalar) { continue }
            return scalar
        }
        return nil
    }

    private static func isEmojiZWJContext(
        at index: Int,
        in scalars: [Unicode.Scalar]
    ) -> Bool {
        guard index > 0, index + 1 < scalars.count,
              matches(extendedPictographicPattern, scalar: scalars[index + 1]) else {
            return false
        }
        var before = index - 1
        while before > 0,
              scalars[before].properties.isGraphemeExtend
                || scalars[before].properties.isEmojiModifier {
            before -= 1
        }
        return matches(extendedPictographicPattern, scalar: scalars[before])
    }

    private static func approvedSubdivisionTagPositions(
        in scalars: [Unicode.Scalar]
    ) -> [Bool] {
        var approved = [Bool](repeating: false, count: scalars.count)
        var cursor = 0
        while cursor < scalars.count {
            guard scalars[cursor].value == 0x1F3F4 else {
                cursor += 1
                continue
            }
            let payloadStart = cursor + 1
            var terminator = payloadStart
            while terminator < scalars.count,
                  (0xE0020...0xE007E).contains(scalars[terminator].value) {
                terminator += 1
            }
            guard terminator < scalars.count,
                  scalars[terminator].value == 0xE007F else {
                cursor = terminator
                continue
            }
            if terminator - payloadStart == 5 {
                let payload = scalars[payloadStart..<terminator].map(\.value)
                if isApprovedSubdivisionTagPayload(payload) {
                    for position in payloadStart...terminator {
                        approved[position] = true
                    }
                }
            }
            cursor = terminator + 1
        }
        return approved
    }

    private static func isApprovedSubdivisionTagPayload(
        _ payload: [UInt32]
    ) -> Bool {
        payload == [0xE0067, 0xE0062, 0xE0065, 0xE006E, 0xE0067]
            || payload == [0xE0067, 0xE0062, 0xE0073, 0xE0063, 0xE0074]
            || payload == [0xE0067, 0xE0062, 0xE0077, 0xE006C, 0xE0073]
    }

    private static func matches(
        _ pattern: NSRegularExpression?,
        scalar: Unicode.Scalar
    ) -> Bool {
        guard let pattern else { return false }
        let value = String(scalar)
        let range = NSRange(location: 0, length: (value as NSString).length)
        return pattern.firstMatch(in: value, range: range) != nil
    }

    private static func isBidirectionalFormattingScalar(_ scalar: Unicode.Scalar) -> Bool {
        switch scalar.value {
        case 0x061C, 0x200E...0x200F, 0x202A...0x202E, 0x2066...0x2069:
            return true
        default:
            return false
        }
    }
}
