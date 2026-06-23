# Examples

This directory is for small AetherLink protocol fixtures and manual test notes.

Keep examples focused on the v0.1 Android-to-Mac loop:

- QR pairing payloads.
- `runtime.health`, `models.list`, `chat.send`, `chat.delta`, `chat.done`, and `chat.cancel` messages.
- Structured `error` messages for pairing, authentication, backend, and cancellation failures.

Do not add examples where Android calls Ollama or LM Studio directly. Backend-specific URLs belong behind the Mac companion runtime, not in Android-facing fixtures.
