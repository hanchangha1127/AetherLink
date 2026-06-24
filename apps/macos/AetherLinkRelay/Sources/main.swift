import Foundation
import RelayServerCore

var host = "0.0.0.0"
var port: UInt16 = 43171
var arguments = Array(CommandLine.arguments.dropFirst())

func usage(exitCode: Int32) -> Never {
    let output = exitCode == 0 ? FileHandle.standardOutput : FileHandle.standardError
    output.write(Data("""
    Usage: AetherLinkRelay [--host <host>] [--port <port>]

    Runs the AetherLink development connectivity relay. This relay pairs one
    runtime and one client by relay_id, sends AETHERLINK_RELAY ready, then
    blindly forwards bytes. It is not a production P2P, DHT, TURN, or AI backend.

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
    case "-h", "--help":
        usage(exitCode: 0)
    default:
        usage(exitCode: 2)
    }
}

do {
    let server = RelayServer(configuration: RelayServerConfiguration(host: host, port: port))
    try server.run()
} catch {
    FileHandle.standardError.write(Data("[relay] failed: \(error)\n".utf8))
    exit(1)
}
