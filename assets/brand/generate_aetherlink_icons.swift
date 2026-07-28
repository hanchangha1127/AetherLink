#!/usr/bin/env swift
import AppKit
import Foundation

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let brandDir = root.appendingPathComponent("assets/brand", isDirectory: true)
let generatedDir = brandDir.appendingPathComponent("generated", isDirectory: true)
let androidResDir = root.appendingPathComponent("apps/android/app/src/main/res", isDirectory: true)
let macResourcesDir = root.appendingPathComponent("apps/macos/LocalAgentBridgeApp/Sources/Resources", isDirectory: true)
let sourceURL = brandDir.appendingPathComponent("aetherlink_icon_source.png")

func ensureDirectory(_ url: URL) throws {
    try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
}

func removeIfPresent(_ url: URL) throws {
    if FileManager.default.fileExists(atPath: url.path) {
        try FileManager.default.removeItem(at: url)
    }
}

func removeDirectoryIfEmpty(_ url: URL) throws {
    guard FileManager.default.fileExists(atPath: url.path) else {
        return
    }
    if try FileManager.default.contentsOfDirectory(atPath: url.path).isEmpty {
        try FileManager.default.removeItem(at: url)
    }
}

func loadSourceImage() throws -> NSImage {
    guard let image = NSImage(contentsOf: sourceURL), image.isValid else {
        throw NSError(
            domain: "AetherLinkIcon",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "Missing or unreadable source image: \(sourceURL.path)"]
        )
    }
    return image
}

func renderPNG(from image: NSImage, pixelSize: Int, insetRatio: CGFloat = 0, background: NSColor = .clear) throws -> NSBitmapImageRep {
    let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: pixelSize,
        pixelsHigh: pixelSize,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bitmapFormat: .alphaFirst,
        bytesPerRow: 0,
        bitsPerPixel: 0
    )!
    rep.size = NSSize(width: pixelSize, height: pixelSize)

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    NSGraphicsContext.current?.imageInterpolation = .high
    NSGraphicsContext.current?.cgContext.setShouldAntialias(true)

    let canvas = CGRect(x: 0, y: 0, width: pixelSize, height: pixelSize)
    background.setFill()
    canvas.fill()

    let inset = CGFloat(pixelSize) * insetRatio
    let drawRect = canvas.insetBy(dx: inset, dy: inset)
    image.draw(in: drawRect, from: .zero, operation: .sourceOver, fraction: 1, respectFlipped: false, hints: [.interpolation: NSImageInterpolation.high])

    NSGraphicsContext.restoreGraphicsState()
    return rep
}

func writePNG(_ rep: NSBitmapImageRep, to url: URL) throws {
    guard let data = rep.representation(using: .png, properties: [:]) else {
        throw NSError(domain: "AetherLinkIcon", code: 2, userInfo: [NSLocalizedDescriptionKey: "PNG encoding failed"])
    }
    try data.write(to: url, options: .atomic)
}

func run(_ executable: String, _ arguments: [String]) throws {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: executable)
    process.arguments = arguments
    try process.run()
    process.waitUntilExit()
    if process.terminationStatus != 0 {
        throw NSError(domain: "AetherLinkIcon", code: Int(process.terminationStatus), userInfo: [NSLocalizedDescriptionKey: "\(executable) failed"])
    }
}

try ensureDirectory(brandDir)
try ensureDirectory(generatedDir)
try ensureDirectory(macResourcesDir)

let sourceImage = try loadSourceImage()

try writePNG(
    try renderPNG(from: sourceImage, pixelSize: 1024),
    to: brandDir.appendingPathComponent("aetherlink_icon_1024.png")
)

let legacyLauncherDirectories = [
    "mipmap-mdpi",
    "mipmap-hdpi",
    "mipmap-xhdpi",
    "mipmap-xxhdpi",
    "mipmap-xxxhdpi"
]
for directory in legacyLauncherDirectories {
    let outputDir = androidResDir.appendingPathComponent(directory, isDirectory: true)
    try removeIfPresent(outputDir.appendingPathComponent("ic_launcher.png"))
    try removeIfPresent(outputDir.appendingPathComponent("ic_launcher_round.png"))
    try removeDirectoryIfEmpty(outputDir)
}
try removeDirectoryIfEmpty(
    androidResDir.appendingPathComponent("mipmap-anydpi-v26", isDirectory: true)
)

let drawableNoDpiDir = androidResDir.appendingPathComponent("drawable-nodpi", isDirectory: true)
try ensureDirectory(drawableNoDpiDir)
try writePNG(
    try renderPNG(from: sourceImage, pixelSize: 432, insetRatio: 0.10),
    to: drawableNoDpiDir.appendingPathComponent("ic_launcher_foreground.png")
)

try removeIfPresent(androidResDir.appendingPathComponent("drawable/ic_launcher_foreground.xml"))
let monochromeVector = """
<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:fillColor="#FFFFFFFF"
        android:pathData="M54,22 L24,84 L38,84 L54,50 L70,84 L84,84 Z" />
    <path
        android:fillColor="#FFFFFFFF"
        android:pathData="M31,72 C44,62 64,62 77,72 L73,78 C62,70 46,70 35,78 Z" />
    <path
        android:fillColor="#FFFFFFFF"
        android:pathData="M24,30 C13,43 10,60 16,76 L24,72 C20,59 22,46 31,35 Z" />
    <path
        android:fillColor="#FFFFFFFF"
        android:pathData="M84,30 L77,35 C86,46 88,59 84,72 L92,76 C98,60 95,43 84,30 Z" />
</vector>
"""
let monochromeURL = androidResDir.appendingPathComponent("drawable/ic_launcher_monochrome.xml")
try monochromeVector.write(to: monochromeURL, atomically: true, encoding: .utf8)

let iconset = generatedDir.appendingPathComponent("AetherLink.iconset", isDirectory: true)
try? FileManager.default.removeItem(at: iconset)
try ensureDirectory(iconset)
let iconsetFiles: [(String, Int)] = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024)
]
for (name, size) in iconsetFiles {
    try writePNG(try renderPNG(from: sourceImage, pixelSize: size), to: iconset.appendingPathComponent(name))
}

let icns = macResourcesDir.appendingPathComponent("AppIcon.icns")
try? FileManager.default.removeItem(at: icns)
try run("/usr/bin/iconutil", ["-c", "icns", iconset.path, "-o", icns.path])

print("Generated AetherLink icon assets from \(sourceURL.path)")
print("  \(brandDir.appendingPathComponent("aetherlink_icon_1024.png").path)")
print("  \(drawableNoDpiDir.appendingPathComponent("ic_launcher_foreground.png").path)")
print("  \(icns.path)")
