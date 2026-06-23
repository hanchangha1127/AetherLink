# AetherLink macOS Companion

Mac companion runtime for AetherLink's local backend mediation.

v0.1 responsibilities:

- Report AetherLink companion status and readiness.
- Own the local runtime process and advertise it for pairing.
- Present QR pairing and manage trusted Android devices.
- Report backend health for Ollama and LM Studio.
- List local models available through the Mac backends.
- Stream chat responses.
- Cancel generation.
- Expose menu bar and toolbar actions for common companion controls.

The Mac companion is the only component that should call Ollama or LM Studio. Android must use the AetherLink runtime protocol and must not call local backend URLs directly.

## macOS Local Network Permission

macOS may ask for Local Network access when AetherLink starts advertising or pairing on the local network. Allow this permission so Android can discover the Mac companion through Bonjour and complete pairing.

If the permission is denied, the app can still show local status, but Android discovery and same-network pairing may fail until Local Network access is enabled again in macOS System Settings > Privacy & Security > Local Network.
