# Nomi Uploader — macOS alpha

This is the same Nomi Uploader GUI and authoritative Python upload engine as Windows/Linux, packaged as a native macOS **.app**. No separate Python installation should be needed.

## Downloads

Visit the [macOS alpha release](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-macos-alpha).

- **NomiUploader-macOS-arm64.zip** for Apple Silicon (M1/M2/M3/M4 and later).
- **NomiUploader-macOS-x86_64.zip** for Intel Macs.

Extract the ZIP and move **NomiUploader.app** to Applications (or another folder), then open it.

## HTTPS certificates and Finder launch

The macOS GUI now bundles a maintained certificate authority (CA) file using
`certifi`. The **app and its uploader subprocess** automatically use that
bundle for HTTPS connections to the Nomi API when running as a packaged macOS
app. Launch normally by double-clicking **NomiUploader.app** in Finder: you
should **not** need to export `SSL_CERT_FILE`, run `Install Certificates.command`,
or open Terminal to establish HTTPS connectivity.

This addresses a Python TLS certificate-store issue, **separate from Apple's
app-signing / Gatekeeper warning**. HTTPS server certificates and hostnames
remain fully verified; no `verify=False` or unverified SSL context is used.

If a managed network uses an organization-specific HTTPS-inspection CA, that
private CA may not exist in the bundled public CA store. Contact the network
administrator about a trusted CA configuration rather than disabling TLS
verification. Report the full error type and message (without your API key)
if connection still fails after installing the latest build.

## Unsigned / unnotarized application

This early alpha is **not signed with an Apple Developer ID** and has **not been notarized**. macOS Gatekeeper may warn or block it. Only run a copy downloaded from this repository and only if you trust its source.

On current macOS versions: try to open the app once, then open **System Settings → Privacy & Security**, scroll to the blocked-app message and use **Open Anyway** when available. You may need to authenticate and confirm again. Apple's instructions and availability of this choice vary with macOS version:

[Apple: Safely open apps on your Mac](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac).

Do **not** disable Gatekeeper system-wide, disable malware protection, or apply recursive quarantine-removal commands.

## Data and limitations

The application saves settings, checkpoints, prepared copies and replies in `~/.local/share/NomiUploader/` by default (unless `LOCALAPPDATA` is set). The API key is currently saved as plaintext in the settings file; avoid shared or untrusted computers. Preserve checkpoints when updating. The app is community software, not official Nomi.ai software.

This is an **experimental** build; Apple Silicon and Intel packages are independently built. Releases depend on successful GitHub Actions builds, and compatibility still needs testing on actual macOS installations.

## Command-line API mode (included)

The GUI download also contains a **standalone Python API command-line uploader** in the `cli/` folder. You can use it without launching the GUI. Read **`CLI-IN-GUI-DOWNLOAD.md` in the extracted download** for exact platform-specific commands, API-key setup and checkpoint recovery. The same uploader engine is used by both interfaces.
