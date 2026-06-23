# Shared Protocol

Protocol definitions shared by the Android client and macOS companion.

The working protocol notes live in [docs/protocol.md](../../docs/protocol.md). The versioned JSON schema lives in [packages/protocol-schema/protocol.schema.json](../../packages/protocol-schema/protocol.schema.json).

v0.1 protocol scope:

- JSON message envelope.
- Connection and pairing messages.
- Model list messages.
- Streaming chat messages.
- Cancel generation messages.
- Error messages.

MCP, skills, web search, advanced memory, and other future roadmap namespaces are reserved only. They are not active v0.1 protocol capabilities.
