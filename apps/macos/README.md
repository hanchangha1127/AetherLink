# AetherLink macOS Companion

Placeholder module for the Mac companion runtime.

v0.1 responsibilities:

- Own the local runtime process.
- Pair/connect trusted Android devices.
- Talk to Ollama and LM Studio locally on the Mac.
- List models.
- Stream chat responses.
- Cancel generation.

The Mac companion is the only component that should call Ollama or LM Studio. Android must use the AetherLink runtime protocol and must not call local backend URLs directly.

## macOS Local Network Permission

macOS may ask for Local Network access when AetherLink starts advertising or pairing on the local network. Allow this permission so Android can discover the Mac companion through Bonjour and complete pairing.

If the permission is denied, the app can still show local status, but Android discovery and same-network pairing may fail until Local Network access is enabled again in macOS System Settings > Privacy & Security > Local Network.
