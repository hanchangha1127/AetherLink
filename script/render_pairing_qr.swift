#!/usr/bin/env swift
import CoreGraphics
import CoreImage
import CoreImage.CIFilterBuiltins
import Foundation
import ImageIO
import UniformTypeIdentifiers

enum QRRenderFailure: Error, CustomStringConvertible {
    case usage
    case emptyInput
    case invalidPairingURI
    case invalidScale(String)
    case generationFailed
    case writeFailed(String)

    var description: String {
        switch self {
        case .usage:
            return "Usage: script/render_pairing_qr.swift --input <text-or-file> --output <png-path> [--scale <integer>]"
        case .emptyInput:
            return "QR input was empty."
        case .invalidPairingURI:
            return "QR input must be an aetherlink://pair URI with query parameters."
        case .invalidScale(let value):
            return "Invalid QR scale: \(value)"
        case .generationFailed:
            return "QR image generation failed."
        case .writeFailed(let path):
            return "Could not write QR PNG to \(path)"
        }
    }
}

struct Options {
    var input: String?
    var outputPath: String?
    var scale: Int = 12
}

func parseOptions(_ arguments: [String]) throws -> Options {
    var options = Options()
    var index = 1
    while index < arguments.count {
        let argument = arguments[index]
        switch argument {
        case "--input":
            guard index + 1 < arguments.count else { throw QRRenderFailure.usage }
            options.input = arguments[index + 1]
            index += 2
        case "--output":
            guard index + 1 < arguments.count else { throw QRRenderFailure.usage }
            options.outputPath = arguments[index + 1]
            index += 2
        case "--scale":
            guard index + 1 < arguments.count else { throw QRRenderFailure.usage }
            let value = arguments[index + 1]
            guard let parsed = Int(value), parsed >= 1, parsed <= 64 else {
                throw QRRenderFailure.invalidScale(value)
            }
            options.scale = parsed
            index += 2
        case "-h", "--help":
            throw QRRenderFailure.usage
        default:
            throw QRRenderFailure.usage
        }
    }
    guard options.input != nil, options.outputPath != nil else {
        throw QRRenderFailure.usage
    }
    return options
}

func inputText(from value: String) throws -> String {
    if value == "-" {
        let data = FileHandle.standardInput.readDataToEndOfFile()
        guard let text = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
              !text.isEmpty
        else {
            throw QRRenderFailure.emptyInput
        }
        return text
    }

    if FileManager.default.fileExists(atPath: value) {
        let text = try String(contentsOfFile: value, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { throw QRRenderFailure.emptyInput }
        return text
    }

    let text = value.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !text.isEmpty else { throw QRRenderFailure.emptyInput }
    return text
}

func makeQRImage(text: String, scale: Int) throws -> CGImage {
    guard let components = URLComponents(string: text),
          components.scheme == "aetherlink",
          components.host == "pair",
          !(components.queryItems?.isEmpty ?? true)
    else {
        throw QRRenderFailure.invalidPairingURI
    }

    let filter = CIFilter.qrCodeGenerator()
    filter.message = Data(text.utf8)
    filter.correctionLevel = "M"

    let colorFilter = CIFilter.falseColor()
    colorFilter.inputImage = filter.outputImage
    colorFilter.color0 = CIColor(red: 0, green: 0, blue: 0)
    colorFilter.color1 = CIColor(red: 1, green: 1, blue: 1)

    guard let outputImage = colorFilter.outputImage else {
        throw QRRenderFailure.generationFailed
    }
    let scaledImage = outputImage.transformed(
        by: CGAffineTransform(scaleX: CGFloat(scale), y: CGFloat(scale))
    )
    let context = CIContext(options: [.useSoftwareRenderer: false])
    guard let cgImage = context.createCGImage(scaledImage, from: scaledImage.extent) else {
        throw QRRenderFailure.generationFailed
    }
    return cgImage
}

func writePNG(_ image: CGImage, to path: String) throws {
    let outputURL = URL(fileURLWithPath: path)
    let directory = outputURL.deletingLastPathComponent()
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)

    guard let destination = CGImageDestinationCreateWithURL(
        outputURL as CFURL,
        UTType.png.identifier as CFString,
        1,
        nil
    ) else {
        throw QRRenderFailure.writeFailed(path)
    }
    CGImageDestinationAddImage(destination, image, nil)
    guard CGImageDestinationFinalize(destination) else {
        throw QRRenderFailure.writeFailed(path)
    }
}

do {
    let options = try parseOptions(CommandLine.arguments)
    let text = try inputText(from: options.input!)
    let image = try makeQRImage(text: text, scale: options.scale)
    try writePNG(image, to: options.outputPath!)
} catch {
    fputs("FAILED: \(error)\n", stderr)
    switch error {
    case QRRenderFailure.usage,
        QRRenderFailure.emptyInput,
        QRRenderFailure.invalidPairingURI,
        QRRenderFailure.invalidScale:
        exit(2)
    case QRRenderFailure.generationFailed:
        exit(3)
    case QRRenderFailure.writeFailed:
        exit(4)
    default:
        exit(1)
    }
}
