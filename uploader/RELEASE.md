# Nomi Uploader 1.3 — Better Recovery, Resume & Configuration

One version and one download page for Windows, macOS, Linux, and Python CLI.

## Downloads

- `NomiUploader-Windows.zip` — Windows GUI plus source CLI.
- `NomiUploader-Linux-x86_64.tar.gz` — Linux GUI plus source CLI.
- `NomiUploader-macOS-arm64.zip` — Apple Silicon macOS GUI plus source CLI.
- `NomiUploader-macOS-x86_64.zip` — Intel macOS GUI plus source CLI.
- `NomiUploader-Python-CLI.zip` — Python-only distribution (no GUI installation).

Each GUI package includes `CLI-IN-GUI-DOWNLOAD.md` and the Python uploader. The standalone CLI ZIP remains an asset **within the same release**, not a separate version or release.

## Version 1.3 highlights

- Normal Resume, with safe retry classification.
- Manual Restart, an explicit append-only checkpoint boundary, with recalculated plan and revised message counts.
- Shared GUI/CLI API-key initialization, with optional password-based encryption or explicitly chosen plaintext.
- macOS trusted certificate bundle for Finder launches and standalone CLI use.
- CLI mode available from native app downloads.

**Important:** The version 1.3 manual restart may deliberately replay messages. Confirm the chosen pass and index before restarting. See `uploader/README.md` and `uploader/RECOVERY.md` for details.

These are unsigned prerelease builds and have not been validated on every operating system configuration. Do not disable operating-system security protections to launch an untrusted file.
