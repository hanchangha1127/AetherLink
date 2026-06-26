# Shared Protocol

Protocol definitions shared by AetherLink clients and runtime hosts.

The working protocol notes live in [docs/protocol.md](../../docs/protocol.md). The versioned JSON schema lives in [packages/protocol-schema/protocol.schema.json](../../packages/protocol-schema/protocol.schema.json).

v0.1 protocol scope:

- JSON message envelope.
- Connection and pairing messages.
- Model list messages.
- Streaming chat messages.
- Cancel generation messages.
- Basic runtime-owned memory messages.
- Error messages.

MCP, skills, web search, advanced memory search/reflection, and other future roadmap namespaces are reserved only. They are not active protocol capabilities yet.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../../LICENSE).
