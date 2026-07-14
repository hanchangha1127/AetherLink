# Protocol Schema

`protocol.schema.json` defines the v1 message envelope and active v0.1 payload shapes for the client-to-runtime protocol.

`docs/protocol.md` remains the source of behavioral semantics, transport sequencing, and future extension rules. The schema is intentionally limited to active runtime messages. Basic `memory.list`, `memory.upsert`, `memory.delete`, bounded exact `memory.duplicate_suggestions.list`, bounded model-dependent `memory.semantic_duplicate_suggestions.list` pair review, and bounded complete-link `memory.semantic_duplicate_clusters.list` cluster review operations are active; live-model calibration, automatic merge, reflection, and roadmap namespaces such as skills, MCP, and web search stay out of the active enum until implemented.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../../LICENSE).
