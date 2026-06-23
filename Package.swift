// swift-tools-version: 5.9
import PackageDescription

let macCompanionTarget = "LocalAgentBridge"

let package = Package(
    name: "AetherLink",
    defaultLocalization: "en",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "AetherLink", targets: [macCompanionTarget]),
        .executable(name: "RuntimeDevServer", targets: ["RuntimeDevServer"])
    ],
    targets: [
        .target(
            name: "BridgeProtocol",
            path: "apps/macos/Protocol/Sources"
        ),
        .target(
            name: "TrustedDevices",
            path: "apps/macos/TrustedDevices/Sources"
        ),
        .target(
            name: "Pairing",
            dependencies: ["TrustedDevices"],
            path: "apps/macos/Pairing/Sources"
        ),
        .target(
            name: "Transport",
            dependencies: ["BridgeProtocol"],
            path: "apps/macos/Transport/Sources"
        ),
        .target(
            name: "OllamaBackend",
            path: "apps/macos/OllamaBackend/Sources"
        ),
        .target(
            name: "LMStudioBackend",
            dependencies: ["OllamaBackend"],
            path: "apps/macos/LMStudioBackend/Sources"
        ),
        .target(
            name: "CompanionCore",
            dependencies: [
                "BridgeProtocol",
                "TrustedDevices",
                "Pairing",
                "Transport",
                "OllamaBackend",
                "LMStudioBackend"
            ],
            path: "apps/macos/CompanionCore/Sources"
        ),
        .executableTarget(
            name: macCompanionTarget,
            dependencies: ["CompanionCore", "OllamaBackend"],
            path: "apps/macos/LocalAgentBridgeApp/Sources",
            resources: [.process("Resources")]
        ),
        .executableTarget(
            name: "RuntimeDevServer",
            dependencies: [
                "CompanionCore",
                "LMStudioBackend",
                "OllamaBackend",
                "Transport"
            ],
            path: "apps/macos/RuntimeDevServer/Sources"
        ),
        .testTarget(
            name: "BridgeProtocolTests",
            dependencies: ["BridgeProtocol"],
            path: "apps/macos/Protocol/Tests"
        ),
        .testTarget(
            name: "OllamaBackendTests",
            dependencies: ["OllamaBackend"],
            path: "apps/macos/OllamaBackend/Tests"
        ),
        .testTarget(
            name: "LMStudioBackendTests",
            dependencies: ["LMStudioBackend"],
            path: "apps/macos/LMStudioBackend/Tests"
        ),
        .testTarget(
            name: "CompanionCoreTests",
            dependencies: ["CompanionCore"],
            path: "apps/macos/CompanionCore/Tests"
        )
    ]
)
