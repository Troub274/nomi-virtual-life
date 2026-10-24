# Nomi Uploader — macOS alpha

This is the same Nomi Uploader GUI and authoritative Python upload engine as Windows/Linux, packaged as a native macOS **.app**. No separate Python installation should be needed.

## Downloads

Visit the [macOS alpha release](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-macos-alpha).

- **NomiUploader-macOS-arm64.zip** for Apple Silicon (M1/M2/M3/M4 and later).
- **NomiUploader-macOS-x86_64.zip** for Intel Macs.

Extract the ZIP and move **NomiUploader.app** to Applications (or another folder), then open it.

## Unsigned / unnotarized application

This early alpha is **not signed with an Apple Developer ID** and has **not been notarized**. macOS Gatekeeper may warn or block it. Only run a copy downloaded from this repository and only if you trust its source.

On current macOS versions: try to open the app once, then open **System Settings → Privacy & Security**, scroll to the blocked-app message and use **Open Anyway** when available. You may need to authenticate and confirm again. Apple's instructions and availability of this choice vary with macOS version:

[Apple: Safely open apps on your Mac](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac).

Do **not** disable Gatekeeper system-wide, disable malware protection, or apply recursive quarantine-removal commands.

## Data and limitations

The application saves settings, checkpoints, prepared copies and replies in `~/.local/share/NomiUploader/` by default (unless `LOCALAPPDATA` is set). The API key is currently saved as plaintext in the settings file; avoid shared or untrusted computers. Preserve checkpoints when updating. The app is community software, not official Nomi.ai software.

This is an **experimental** build; Apple Silicon and Intel packages are independently built. Releases depend on successful GitHub Actions builds, and compatibility still needs testing on actual macOS installations.
