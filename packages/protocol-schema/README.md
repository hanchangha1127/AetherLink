# Protocol Schema

`protocol.schema.json` defines the v1 message envelope and active v0.1 payload shapes for the client-to-runtime protocol.

`docs/protocol.md` remains the source of behavioral semantics, transport sequencing, and future extension rules. The schema is intentionally limited to active runtime messages. Basic `memory.list`, `memory.upsert`, and `memory.delete` are active; advanced memory search/reflection plus roadmap namespaces such as skills, MCP, and web search stay out of the active enum until implemented.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../../LICENSE).
