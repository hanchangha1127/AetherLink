# AetherLink Client App

Current Android implementation of the AetherLink client/controller. Product traffic goes through a paired companion runtime rather than directly to model backends.

v0.1 responsibilities:

- Pair/connect to the companion runtime with a QR-based first-run flow.
- Show connection status.
- List runtime-mediated local backend models from Ollama and LM Studio.
- Send chat messages through the companion runtime.
- Render streamed responses, including preserved reasoning when available.
- Cancel generation.
- Provide a ChatGPT-like sidebar for chat history and settings.
- Support localized UI strings, suggested follow-up questions, and haptic feedback.

The client app must not ask the user to manually enter backend URLs. It never calls Ollama or LM Studio directly; all model, chat, and generation control traffic goes through the paired companion runtime.
Release builds hide manual host/port tools. Debug builds expose USB reverse, emulator bridge, and manual route fields only behind Developer routes diagnostics.

## Physical Device Development

For a USB-connected client device, use the local runtime endpoint through `adb reverse`.

1. Start the runtime host and Android install flow:

   ```bash
   ./script/android_usb_smoke.sh
   ```

2. If the script reports `unauthorized`, unlock the phone and approve the USB debugging prompt.

3. In a debug build of the client app, open Settings -> Connection diagnostics -> Developer routes, then use the `USB reverse` preset. It connects to `127.0.0.1:43170`, which is forwarded by adb to the companion runtime. This is not an Ollama or LM Studio URL and is not the normal product connection model.
