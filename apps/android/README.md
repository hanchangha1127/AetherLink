# AetherLink Client App

Current Android implementation of the AetherLink client/controller. Product traffic goes through a paired runtime host rather than directly to model backends.

v0.1 responsibilities:

- Pair/connect to the runtime host with a QR-based first-run flow.
- Show connection status.
- List runtime-mediated local backend models from Ollama and LM Studio.
- Send chat messages through the runtime host.
- Render streamed responses, including preserved reasoning when available.
- Cancel generation.
- Provide a ChatGPT-like sidebar for chat history and settings.
- Support localized UI strings, suggested follow-up questions, and haptic feedback.

The client app must not ask the user to manually enter backend URLs. It never calls Ollama or LM Studio directly; all model, chat, and generation control traffic goes through the paired runtime host.
Release builds hide manual host/port tools. Debug builds expose USB reverse, emulator bridge, and manual route fields only behind Developer routes diagnostics.

## Physical Device Development

For a USB-connected client device, use the local runtime endpoint through `adb reverse`.

1. Start the runtime host and Android install flow:

   ```bash
   ./script/android_usb_smoke.sh
   ```

2. If the script reports `unauthorized`, unlock the phone and approve the USB debugging prompt.

3. In a debug build of the client app, open Settings -> Connection troubleshooting -> Developer routes, then use the `USB reverse` preset. It connects to `127.0.0.1:43170`, which is forwarded by adb to AetherLink Runtime. This is not an Ollama or LM Studio URL and is not the normal product connection model.

For QR/deeplink pairing smoke tests, use:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./script/android_pairing_deeplink_smoke.sh --relay
```

To extend that physical-device smoke through chat streaming, generation cancel,
and saved-route reconnect, use:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
  ./script/android_pairing_deeplink_smoke.sh \
  --relay \
  --expect-chat-cancel \
  --expect-reconnect
```

This still injects the QR URI through Android's VIEW intent. It validates the
post-scan app path on a physical device, not optical camera recognition.

To run the same physical UI path against real Mac-side Ollama + LM Studio
providers instead of the fast development mock backend, add `--live-backend`
and allow a longer first-token wait:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
  ./script/android_pairing_deeplink_smoke.sh \
  --relay \
  --live-backend \
  --expect-chat-cancel \
  --expect-reconnect \
  --chat-delta-timeout 180
```

Android still connects only to AetherLink Runtime. Ollama and LM Studio remain
hidden behind the runtime host.

For a closer different-network smoke, provide a relay that the phone can reach
without `adb reverse`:

```bash
JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
  ./script/android_pairing_deeplink_smoke.sh \
  --relay \
  --external-relay-host <relay-host> \
  --external-relay-port 43171
```

The external relay mode still injects the QR URI over USB, but the runtime route
inside that URI points at the provided relay address. The app must reach that
relay over normal networking.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../../LICENSE).
