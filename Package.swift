// swift-tools-version: 5.9
import PackageDescription

let macCompanionTarget = "LocalAgentBridge"

let package = Package(
    name: "AetherLink",
    defaultLocalization: "en",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "AetherLink", targets: [macCompanionTarget]),
        .executable(name: "RuntimeDevServer", targets: ["RuntimeDevServer"]),
        .executable(name: "AetherLinkRelay", targets: ["AetherLinkRelay"])
    ],
    targets: [
        .target(
            name: "P2PNATContracts",
            path: "apps/macos/P2PNATContracts/Sources"
        ),
        .target(
            name: "P2PNATConformance",
            dependencies: ["P2PNATContracts"],
            path: "apps/macos/P2PNATConformance/Sources"
        ),
        .target(
            name: "RelayServerCore",
            dependencies: ["BridgeProtocol"],
            path: "apps/macos/RelayServerCore/Sources"
        ),
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
            dependencies: ["BridgeProtocol", "TrustedDevices"],
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
            name: "DocumentIngestion",
            path: "apps/macos/DocumentIngestion/Sources"
        ),
        .target(
            name: "CompanionCore",
            dependencies: [
                "BridgeProtocol",
                "TrustedDevices",
                "Pairing",
                "Transport",
                "OllamaBackend",
                "LMStudioBackend",
                "DocumentIngestion"
            ],
            path: "apps/macos/CompanionCore/Sources",
            linkerSettings: [.linkedLibrary("sqlite3")]
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
                "DocumentIngestion",
                "LMStudioBackend",
                "OllamaBackend",
                "Transport"
            ],
            path: "apps/macos/RuntimeDevServer/Sources"
        ),
        .executableTarget(
            name: "AetherLinkRelay",
            dependencies: ["RelayServerCore"],
            path: "apps/macos/AetherLinkRelay/Sources"
        ),
        .testTarget(
            name: "P2PNATContractsTests",
            dependencies: ["P2PNATContracts"],
            path: "apps/macos/P2PNATContracts/Tests"
        ),
        .testTarget(
            name: "P2PNATConformanceTests",
            dependencies: ["P2PNATConformance", "P2PNATContracts"],
            path: "apps/macos/P2PNATConformance/Tests"
        ),
        .testTarget(
            name: "RelayServerCoreTests",
            dependencies: ["RelayServerCore"],
            path: "apps/macos/RelayServerCore/Tests"
        ),
        .testTarget(
            name: "BridgeProtocolTests",
            dependencies: ["BridgeProtocol"],
            path: "apps/macos/Protocol/Tests"
        ),
        .testTarget(
            name: "TrustedDevicesTests",
            dependencies: ["TrustedDevices"],
            path: "apps/macos/TrustedDevices/Tests"
        ),
        .testTarget(
            name: "PairingTests",
            dependencies: ["Pairing"],
            path: "apps/macos/Pairing/Tests"
        ),
        .testTarget(
            name: "OllamaBackendTests",
            dependencies: ["OllamaBackend"],
            path: "apps/macos/OllamaBackend/Tests"
        ),
        .testTarget(
            name: "TransportTests",
            dependencies: ["Transport"],
            path: "apps/macos/Transport/Tests"
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
        ),
        .testTarget(
            name: "LocalAgentBridgeTests",
            dependencies: [.target(name: macCompanionTarget)],
            path: "apps/macos/LocalAgentBridgeApp/Tests"
        ),
        .testTarget(
            name: "DocumentIngestionTests",
            dependencies: ["DocumentIngestion"],
            path: "apps/macos/DocumentIngestion/Tests"
        )
    ]
)
