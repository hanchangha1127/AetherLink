# AetherLink Icon Assets

The app icon is based on the user-provided PNG source image.

- `aetherlink_icon_source.png` is the canonical brand source copied from the user-provided image.
- `aetherlink_icon_1024.png` is a 1024px raster copy used for inspection and macOS icon generation.
- `generate_aetherlink_icons.swift` regenerates Android launcher PNGs, the adaptive icon foreground, the macOS iconset, and `AppIcon.icns` without network access.

Run from the repository root:

```sh
swift assets/brand/generate_aetherlink_icons.swift
```

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](../../LICENSE).
