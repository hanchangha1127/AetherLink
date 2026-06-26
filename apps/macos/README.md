# AetherLink Runtime

Current macOS implementation of the AetherLink runtime host for local backend mediation.

v0.1 responsibilities:

- Report AetherLink Runtime status and readiness.
- Own the local runtime process and advertise it for pairing.
- Present QR pairing and manage trusted client devices.
- Report backend health for Ollama and LM Studio.
- List local models available through runtime-host backends.
- Stream chat responses.
- Cancel generation.
- Expose menu bar and toolbar actions for common runtime controls.

The runtime host is the only component that should call Ollama or LM Studio. Client apps must use the AetherLink runtime protocol and must not call local backend URLs directly.

## macOS Local Network Permission

macOS may ask for Local Network access when AetherLink starts advertising or pairing on the local network. Allow this permission so client devices can discover AetherLink Runtime through Bonjour and complete pairing.

If the permission is denied, the app can still show local status, but local discovery and same-network pairing may fail until Local Network access is enabled again in macOS System Settings > Privacy & Security > Local Network. This permission is for the current local-direct development path, not the final different-network connection model.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../../LICENSE).
