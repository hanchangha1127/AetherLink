# Examples

This directory is for small AetherLink protocol fixtures and manual test notes.

Keep examples focused on the v0.1 client-to-runtime loop:

- QR pairing payloads.
- `runtime.health`, `models.list`, `chat.send`, `chat.delta`, `chat.done`, and `chat.cancel` messages.
- Structured `error` messages for pairing, authentication, backend, and cancellation failures.

Do not add examples where the client calls Ollama or LM Studio directly. Backend-specific URLs belong behind AetherLink Runtime, not in client-facing fixtures.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../LICENSE).
