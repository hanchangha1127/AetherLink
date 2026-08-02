import CryptoKit
import Foundation

struct SplitMix64V1: Equatable {
    private(set) var state: UInt64

    init(seed: UInt64) {
        state = seed
    }

    mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var value = state
        value = (value ^ (value >> 30)) &* 0xBF58_476D_1CE4_E5B9
        value = (value ^ (value >> 27)) &* 0x94D0_49BB_1331_11EB
        return value ^ (value >> 31)
    }

    mutating func nextInt(upperBound: Int) -> Int {
        precondition(upperBound > 0)
        return Int(next() % UInt64(upperBound))
    }

    mutating func nextByte() -> UInt8 {
        UInt8(truncatingIfNeeded: next())
    }
}

enum DocumentMutationFormat: String, CaseIterable {
    case txt
    case xml
    case html
    case rtf
    case pdf
    case docx
    case epub
    case webarchive

    var pathExtension: String { rawValue }

    var mimeType: String {
        switch self {
        case .txt:
            return "text/plain"
        case .xml:
            return "application/xml"
        case .html:
            return "text/html"
        case .rtf:
            return "application/rtf"
        case .pdf:
            return "application/pdf"
        case .docx:
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        case .epub:
            return "application/epub+zip"
        case .webarchive:
            return "application/x-webarchive"
        }
    }
}

enum DocumentMutationOperator: String, CaseIterable {
    case identity
    case truncate
    case deleteSpan = "delete_span"
    case insertSpan = "insert_span"
    case overwriteSpan = "overwrite_span"
    case flipBit = "flip_bit"
    case flipHighBits = "flip_high_bits"
    case duplicateSpan = "duplicate_span"
    case spliceSeed = "splice_seed"
    case reverseSpan = "reverse_span"
    case padExact4096 = "pad_exact_4096"
    case padPlusOne4097 = "pad_plus_one_4097"

    static let secondaryCases: [DocumentMutationOperator] = [
        .truncate,
        .deleteSpan,
        .insertSpan,
        .overwriteSpan,
        .flipBit,
        .flipHighBits,
        .duplicateSpan,
        .spliceSeed,
        .reverseSpan,
    ]
}

struct DocumentMutationCase: Equatable {
    let index: Int
    let rootSeed: UInt64
    let caseSeed: UInt64
    let format: DocumentMutationFormat
    let operators: [DocumentMutationOperator]
    let data: Data

    var fileName: String {
        String(format: "mutation-%03d.%@", index, format.pathExtension)
    }

    var markerLine: String {
        let operatorList = operators.map(\.rawValue).joined(separator: ",")
        return String(
            format: "AETHERLINK_DOCUMENT_MUTATION_V1 case=%03d total=%03d generator=splitmix64-v1 root=%016llx seed=%016llx format=%@ operators=%@ bytes=%d sha256=%@",
            index,
            DocumentIngestionMutationCorpus.caseCount,
            rootSeed,
            caseSeed,
            format.rawValue,
            operatorList,
            data.count,
            documentMutationSHA256(data)
        )
    }
}

enum DocumentIngestionMutationCorpus {
    static let rootSeed: UInt64 = 0xA37E_2C91_5B04_D8F6
    static let inputLimit = 4_096
    static let maximumCaseBytes = inputLimit + 1
    static let caseCount = 96

    static let pdfFixtureSHA256 =
        "e4d8b9617bd06a50886910a05bed8d079f7eb6566fca8a71f5de205d011c33ea"
    static let docxFixtureSHA256 =
        "8f39f24fa7a829448184c335d2efb7d7e6723f2dc8204c0706111150089f52c1"
    static let epubFixtureSHA256 =
        "809a5a4722567c667ea7d7004e2b05c4328b3d7d29dbe9ff525601fefb2a6295"
    static let webarchiveFixtureSHA256 =
        "2797711acb471b98220b2a7409fc0ec8712f311db400cc176888be30efaaff2c"

    static func makeCases() -> [DocumentMutationCase] {
        let formats = DocumentMutationFormat.allCases
        let primaryOperators = DocumentMutationOperator.allCases
        precondition(formats.count * primaryOperators.count == caseCount)

        return (0..<caseCount).map { index in
            let format = formats[index % formats.count]
            let primaryOperator = primaryOperators[index / formats.count]
            var seedGenerator = SplitMix64V1(
                seed: rootSeed &+ UInt64(index)
            )
            let caseSeed = seedGenerator.next()
            var generator = SplitMix64V1(seed: caseSeed)
            var bytes = [UInt8](fixture(for: format))
            var operators: [DocumentMutationOperator] = []

            if primaryOperator != .padExact4096 &&
                primaryOperator != .padPlusOne4097 {
                let secondaryCount = generator.nextInt(upperBound: 4)
                for _ in 0..<secondaryCount {
                    let mutation = DocumentMutationOperator.secondaryCases[
                        generator.nextInt(
                            upperBound: DocumentMutationOperator.secondaryCases.count
                        )
                    ]
                    apply(mutation, to: &bytes, using: &generator)
                    operators.append(mutation)
                }
            }

            apply(primaryOperator, to: &bytes, using: &generator)
            operators.append(primaryOperator)
            precondition(operators.count >= 1 && operators.count <= 4)
            precondition(bytes.count <= maximumCaseBytes)

            return DocumentMutationCase(
                index: index,
                rootSeed: rootSeed,
                caseSeed: caseSeed,
                format: format,
                operators: operators,
                data: Data(bytes)
            )
        }
    }

    static func markerManifest(for cases: [DocumentMutationCase]) -> Data {
        Data((cases.map(\.markerLine).joined(separator: "\n") + "\n").utf8)
    }

    static func summaryLine(for cases: [DocumentMutationCase]) -> String {
        String(
            format: "AETHERLINK_DOCUMENT_MUTATION_SUMMARY_V1 total=%03d root=%016llx manifest_sha256=%@",
            caseCount,
            rootSeed,
            documentMutationSHA256(markerManifest(for: cases))
        )
    }

    static func fixture(for format: DocumentMutationFormat) -> Data {
        switch format {
        case .txt:
            return Data("AetherLink deterministic text seed 한글 日本語 français\n".utf8)
        case .xml:
            return Data(
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?><document><body><p>AetherLink deterministic XML seed</p></body></document>".utf8
            )
        case .html:
            return Data(
                "<!doctype html><html><body><p>AetherLink deterministic HTML seed</p></body></html>".utf8
            )
        case .rtf:
            return Data(
                "{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Helvetica;}}\\f0\\fs24 AetherLink deterministic RTF seed}".utf8
            )
        case .pdf:
            return decodedFixture(
                "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2JqCjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCAyMDAgMjAwXSAvUmVzb3VyY2VzIDw8IC9Gb250IDw8IC9GMSA0IDAgUiA+PiA+PiAvQ29udGVudHMgNSAwIFIgPj4KZW5kb2JqCjQgMCBvYmoKPDwgL1R5cGUgL0ZvbnQgL1N1YnR5cGUgL1R5cGUxIC9CYXNlRm9udCAvSGVsdmV0aWNhID4+CmVuZG9iago1IDAgb2JqCjw8IC9MZW5ndGggNjUgPj4Kc3RyZWFtCkJUIC9GMSAxMiBUZiAyMCAxMDAgVGQgKEFldGhlckxpbmsgZGV0ZXJtaW5pc3RpYyBQREYgc2VlZCkgVGogRVQKZW5kc3RyZWFtCmVuZG9iagp4cmVmCjAgNgowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMDkgMDAwMDAgbiAKMDAwMDAwMDA1OCAwMDAwMCBuIAowMDAwMDAwMTE1IDAwMDAwIG4gCjAwMDAwMDAyNDEgMDAwMDAgbiAKMDAwMDAwMDMxMSAwMDAwMCBuIAp0cmFpbGVyCjw8IC9TaXplIDYgL1Jvb3QgMSAwIFIgPj4Kc3RhcnR4cmVmCjQyNQolJUVPRgo="
            )
        case .docx:
            return decodedFixture(
                "UEsDBBQAAAAAAAAAIQD9BmMMcQAAAHEAAAARAAAAd29yZC9kb2N1bWVudC54bWw8P3htbCB2ZXJzaW9uPSIxLjAiIGVuY29kaW5nPSJVVEYtOCI/Pjxkb2N1bWVudD48Ym9keT48cD5BZXRoZXJMaW5rIGRldGVybWluaXN0aWMgRE9DWCBzZWVkPC9wPjwvYm9keT48L2RvY3VtZW50PlBLAQIUAxQAAAAAAAAAIQD9BmMMcQAAAHEAAAARAAAAAAAAAAAAAACkgQAAAAB3b3JkL2RvY3VtZW50LnhtbFBLBQYAAAAAAQABAD8AAACgAAAAAAA="
            )
        case .epub:
            return decodedFixture(
                "UEsDBBQAAAAAAAAAIQBiTzYbaQAAAGkAAAATAAAAT0VCUFMvY29udGVudC54aHRtbDw/eG1sIHZlcnNpb249IjEuMCIgZW5jb2Rpbmc9IlVURi04Ij8+PGh0bWw+PGJvZHk+PHA+QWV0aGVyTGluayBkZXRlcm1pbmlzdGljIEVQVUIgc2VlZDwvcD48L2JvZHk+PC9odG1sPlBLAQIUAxQAAAAAAAAAIQBiTzYbaQAAAGkAAAATAAAAAAAAAAAAAACkgQAAAABPRUJQUy9jb250ZW50LnhodG1sUEsFBgAAAAABAAEAQQAAAJoAAAAAAA=="
            )
        case .webarchive:
            return decodedFixture(
                "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPCFET0NUWVBFIHBsaXN0IFBVQkxJQyAiLS8vQXBwbGUvL0RURCBQTElTVCAxLjAvL0VOIiAiaHR0cDovL3d3dy5hcHBsZS5jb20vRFREcy9Qcm9wZXJ0eUxpc3QtMS4wLmR0ZCI+CjxwbGlzdCB2ZXJzaW9uPSIxLjAiPjxkaWN0PjxrZXk+V2ViTWFpblJlc291cmNlPC9rZXk+PGRpY3Q+PGtleT5XZWJSZXNvdXJjZURhdGE8L2tleT48ZGF0YT5QR2gwYld3K1BHSnZaSGsrUVdWMGFHVnlUR2x1YXlCa1pYUmxjbTFwYm1semRHbGpJRmRsWWtGeVkyaHBkbVVnYzJWbFpEd3ZZbTlrZVQ0OEwyaDBiV3crPC9kYXRhPjxrZXk+V2ViUmVzb3VyY2VGcmFtZU5hbWU8L2tleT48c3RyaW5nPjwvc3RyaW5nPjxrZXk+V2ViUmVzb3VyY2VNSU1FVHlwZTwva2V5PjxzdHJpbmc+dGV4dC9odG1sPC9zdHJpbmc+PGtleT5XZWJSZXNvdXJjZVRleHRFbmNvZGluZ05hbWU8L2tleT48c3RyaW5nPlVURi04PC9zdHJpbmc+PGtleT5XZWJSZXNvdXJjZVVSTDwva2V5PjxzdHJpbmc+aHR0cHM6Ly9leGFtcGxlLmludmFsaWQvPC9zdHJpbmc+PC9kaWN0PjwvZGljdD48L3BsaXN0Pgo="
            )
        }
    }

    private static func apply(
        _ mutation: DocumentMutationOperator,
        to bytes: inout [UInt8],
        using generator: inout SplitMix64V1
    ) {
        switch mutation {
        case .identity:
            break
        case .truncate:
            guard !bytes.isEmpty else {
                bytes.append(generator.nextByte())
                return
            }
            bytes.removeLast(bytes.count - generator.nextInt(upperBound: bytes.count))
        case .deleteSpan:
            guard !bytes.isEmpty else {
                bytes.append(generator.nextByte())
                return
            }
            let start = generator.nextInt(upperBound: bytes.count)
            let length = 1 + generator.nextInt(
                upperBound: min(32, bytes.count - start)
            )
            bytes.removeSubrange(start..<(start + length))
        case .insertSpan:
            let available = maximumCaseBytes - bytes.count
            guard available > 0 else {
                bytes[generator.nextInt(upperBound: bytes.count)] ^= 0x01
                return
            }
            let length = 1 + generator.nextInt(upperBound: min(32, available))
            let insertion = (0..<length).map { _ in generator.nextByte() }
            let index = generator.nextInt(upperBound: bytes.count + 1)
            bytes.insert(contentsOf: insertion, at: index)
        case .overwriteSpan:
            guard !bytes.isEmpty else {
                bytes.append(generator.nextByte())
                return
            }
            let start = generator.nextInt(upperBound: bytes.count)
            let length = 1 + generator.nextInt(
                upperBound: min(32, bytes.count - start)
            )
            for index in start..<(start + length) {
                bytes[index] = generator.nextByte()
            }
        case .flipBit:
            guard !bytes.isEmpty else {
                bytes.append(0x01)
                return
            }
            let index = generator.nextInt(upperBound: bytes.count)
            bytes[index] ^= UInt8(1 << generator.nextInt(upperBound: 8))
        case .flipHighBits:
            guard !bytes.isEmpty else {
                bytes.append(0x80)
                return
            }
            let index = generator.nextInt(upperBound: bytes.count)
            bytes[index] ^= 0xC0
        case .duplicateSpan:
            guard !bytes.isEmpty else {
                bytes.append(generator.nextByte())
                return
            }
            let available = maximumCaseBytes - bytes.count
            guard available > 0 else {
                bytes[generator.nextInt(upperBound: bytes.count)] ^= 0x02
                return
            }
            let start = generator.nextInt(upperBound: bytes.count)
            let length = 1 + generator.nextInt(
                upperBound: min(32, bytes.count - start, available)
            )
            let duplicate = Array(bytes[start..<(start + length)])
            let insertionIndex = generator.nextInt(upperBound: bytes.count + 1)
            bytes.insert(contentsOf: duplicate, at: insertionIndex)
        case .spliceSeed:
            let token = boundaryTokens[
                generator.nextInt(upperBound: boundaryTokens.count)
            ]
            let available = maximumCaseBytes - bytes.count
            if available == 0 {
                guard !bytes.isEmpty else { return }
                let replacement = token.prefix(min(token.count, bytes.count))
                bytes.replaceSubrange(0..<replacement.count, with: replacement)
            } else {
                let insertion = token.prefix(available)
                let index = generator.nextInt(upperBound: bytes.count + 1)
                bytes.insert(contentsOf: insertion, at: index)
            }
        case .reverseSpan:
            guard bytes.count >= 2 else {
                bytes.append(generator.nextByte())
                return
            }
            let start = generator.nextInt(upperBound: bytes.count - 1)
            let length = 2 + generator.nextInt(
                upperBound: min(32, bytes.count - start) - 1
            )
            bytes.replaceSubrange(
                start..<(start + length),
                with: bytes[start..<(start + length)].reversed()
            )
        case .padExact4096:
            resize(&bytes, to: inputLimit, using: &generator)
        case .padPlusOne4097:
            resize(&bytes, to: maximumCaseBytes, using: &generator)
        }
        if bytes.count > maximumCaseBytes {
            bytes.removeLast(bytes.count - maximumCaseBytes)
        }
    }

    private static func resize(
        _ bytes: inout [UInt8],
        to count: Int,
        using generator: inout SplitMix64V1
    ) {
        if bytes.count > count {
            bytes.removeLast(bytes.count - count)
        } else {
            while bytes.count < count {
                bytes.append(generator.nextByte())
            }
        }
    }

    private static let boundaryTokens: [[UInt8]] = [
        [0x00],
        [0xFF],
        Array("<?xml".utf8),
        Array("</document>".utf8),
        Array("<script>".utf8),
        Array("%PDF-".utf8),
        [0x50, 0x4B, 0x03, 0x04],
        Array("{\\rtf1".utf8),
        [0xC0, 0xAF],
        [0xED, 0xA0, 0x80],
    ]

    private static func decodedFixture(_ base64: String) -> Data {
        guard let data = Data(base64Encoded: base64) else {
            preconditionFailure("invalid fixed DocumentIngestion fixture")
        }
        return data
    }
}

func documentMutationSHA256(_ data: Data) -> String {
    SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
}
