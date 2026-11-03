# Nomi Uploader 1.3i — Interface Release

One version and one download page for Windows, macOS, Linux, and Python CLI.

## Downloads

- `NomiUploader-Windows.zip` — Windows GUI plus source CLI.
- `NomiUploader-Linux-x86_64.tar.gz` — Linux GUI plus source CLI.
- `NomiUploader-macOS-arm64.zip` — Apple Silicon macOS GUI plus source CLI.
- `NomiUploader-macOS-x86_64.zip` — Intel macOS GUI plus source CLI.
- `NomiUploader-Python-CLI.zip` — Python-only distribution (no GUI installation).

Each GUI package includes `CLI-IN-GUI-DOWNLOAD.md` and the Python uploader. The standalone CLI ZIP remains an asset **within the same release**, not a separate version or release.

## Unicode output hotfix

- Windows previews and upload logs now use UTF-8, including emoji, non-Latin names, and private-use citation characters from imported ChatGPT transcripts.
- The GUI explicitly decodes the uploader subprocess output as UTF-8, preventing Windows code-page errors from aborting a preview or interrupting its log reader.
- Transcript text, upload planning, and checkpoint compatibility are unchanged.

## Version 1.3i interface highlights

- Nomi-inspired dark/light/system appearance selection.
- Destination, Files, Upload, History and Settings navigation.
- Destination API-key management before Nomi and room selection.
- Global upload defaults under Settings; per-file options under Files.
- Selectable History, replies, status and diagnostic output with copy controls.
- Advanced checkpoint-scoped recovery actions and manual update checking (download only).
- The underlying upload engine and checkpoint format remain v1.3.

## Version 1.3 engine highlights

- Normal Resume, with safe retry classification.
- Manual Restart, an explicit append-only checkpoint boundary, with recalculated plan and revised message counts.
- Shared GUI/CLI API-key initialization, with optional password-based encryption or explicitly chosen plaintext.
- macOS trusted certificate bundle for Finder launches and standalone CLI use.
- CLI mode available from native app downloads.

**Important:** The version 1.3 manual restart may deliberately replay messages. Confirm the chosen pass and index before restarting. See `uploader/README.md` and `uploader/RECOVERY.md` for details.

These are unsigned prerelease builds and have not been validated on every operating system configuration. Do not disable operating-system security protections to launch an untrusted file.
