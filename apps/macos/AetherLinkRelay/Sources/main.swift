import Foundation
import RelayServerCore

var host = "0.0.0.0"
var port: UInt16 = 43171
var requiresAllocation = false
var allocationStorePath = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_ALLOCATION_STORE"]
var allocationToken = ProcessInfo.processInfo.environment["AETHERLINK_RELAY_ALLOCATION_TOKEN"]
var usesEphemeralAllocations = false
var arguments = Array(CommandLine.arguments.dropFirst())

func usage(exitCode: Int32) -> Never {
    let output = exitCode == 0 ? FileHandle.standardOutput : FileHandle.standardError
    output.write(Data("""
    Usage: AetherLinkRelay [--host <host>] [--port <port>] [--require-allocation] [--allocation-token <token>] [--allocation-store <path>] [--ephemeral-allocations]

    Runs the AetherLink development connectivity relay. This relay pairs one
    runtime and one client by relay_id, sends AETHERLINK_RELAY ready, then
    blindly forwards bytes. It also accepts
    AETHERLINK_RELAY allocate <route_token> [relay_secret] to issue or renew
    stable relay route material for QR development flows.
    With --require-allocation, runtime/client handshakes for unknown or expired
    relay IDs are rejected.
    With --allocation-token, allocation requests must include the same token;
    this keeps a public development relay from issuing route material to
    unrelated callers.
    Allocation tickets persist to ~/.aetherlink-relay/allocations.json by
    default so issued QR route material can survive relay process restarts.
    Use --ephemeral-allocations to keep the old in-memory behavior.
    It is not a production P2P, DHT, TURN, or AI backend.

    """.utf8))
    exit(exitCode)
}

while !arguments.isEmpty {
    let argument = arguments.removeFirst()
    switch argument {
    case "--host":
        guard let value = arguments.first, !value.isEmpty else { usage(exitCode: 2) }
        host = value
        arguments.removeFirst()
    case "--port":
        guard let value = arguments.first, let parsed = UInt16(value) else { usage(exitCode: 2) }
        port = parsed
        arguments.removeFirst()
    case "--require-allocation":
        requiresAllocation = true
    case "--allocation-store":
        guard let value = arguments.first, !value.isEmpty else { usage(exitCode: 2) }
        allocationStorePath = value
        arguments.removeFirst()
    case "--allocation-token":
        guard let value = arguments.first, !value.isEmpty else { usage(exitCode: 2) }
        allocationToken = value
        arguments.removeFirst()
    case "--ephemeral-allocations":
        usesEphemeralAllocations = true
    case "-h", "--help":
        usage(exitCode: 0)
    default:
        usage(exitCode: 2)
    }
}

do {
    let allocationStoreURL = usesEphemeralAllocations ? nil : URL(
        fileURLWithPath: (
            allocationStorePath?.takeIfNotEmpty()
                ?? "~/.aetherlink-relay/allocations.json"
        ).expandingTildeInPath()
    )
    let server = RelayServer(configuration: RelayServerConfiguration(
        host: host,
        port: port,
        requiresAllocation: requiresAllocation,
        allocationStoreURL: allocationStoreURL,
        allocationToken: allocationToken?.takeIfNotEmpty()
    ))
    try server.run()
} catch {
    FileHandle.standardError.write(Data("[relay] failed: \(error)\n".utf8))
    exit(1)
}

private extension String {
    func takeIfNotEmpty() -> String? {
        isEmpty ? nil : self
    }

    func expandingTildeInPath() -> String {
        (self as NSString).expandingTildeInPath
    }
}
