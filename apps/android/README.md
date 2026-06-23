# Android App

Placeholder module for the Android client/controller.

v0.1 responsibilities:

- Pair/connect to the Mac companion.
- Show connection status.
- List Mac-side Ollama models.
- Send chat messages.
- Render streamed responses.
- Cancel generation.

The Android app must not ask the user to manually enter an Ollama or LM Studio URL.

## Physical Device Development

For a USB-connected Android phone, use the Mac runtime endpoint through `adb reverse`.

1. Start the Mac runtime and Android install flow:

   ```bash
   ./script/android_usb_smoke.sh
   ```

2. If the script reports `unauthorized`, unlock the phone and approve the USB debugging prompt.

3. In the Android app, use the `USB reverse` preset. It connects to `127.0.0.1:43170`, which is forwarded by adb to the Mac companion runtime. This is not an Ollama or LM Studio URL.
