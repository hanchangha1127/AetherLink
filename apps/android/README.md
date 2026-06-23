# Android App

Android client/controller for paired AetherLink chat through the Mac companion.

v0.1 responsibilities:

- Pair/connect to the Mac companion with a QR-based first-run flow.
- Show connection status.
- List Mac-mediated local backend models from Ollama and LM Studio.
- Send chat messages through the Mac companion.
- Render streamed responses, including preserved reasoning when available.
- Cancel generation.
- Provide a ChatGPT-like sidebar for chat history and settings.
- Support localized UI strings, starter prompts, and haptic feedback.

The Android app must not ask the user to manually enter backend URLs. It never calls Ollama or LM Studio directly; all model, chat, and generation control traffic goes through the paired Mac companion.

## Physical Device Development

For a USB-connected Android phone, use the Mac runtime endpoint through `adb reverse`.

1. Start the Mac runtime and Android install flow:

   ```bash
   ./script/android_usb_smoke.sh
   ```

2. If the script reports `unauthorized`, unlock the phone and approve the USB debugging prompt.

3. In the Android app, use the `USB reverse` preset. It connects to `127.0.0.1:43170`, which is forwarded by adb to the Mac companion runtime. This is not an Ollama or LM Studio URL.
