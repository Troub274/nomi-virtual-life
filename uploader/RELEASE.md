# Nomi Uploader 1.4i.3

- Fixed GUI freezes and excessive thread and memory growth when monitoring large upload checkpoints, including after an upload finishes.
- Prevented the status timer from launching overlapping checkpoint scans.
- Status and recovery now share a cached snapshot that refreshes when the journal changes.
- Bounded in-memory activity logs and recent replies. Run History reads the opening record of each journal instead of loading the whole file.
- Added regressions with 31,000-message checkpoints, concurrent status requests, 1,000 overlapping timer ticks, and cache refresh after append and Manual Restart.

Install this version and open your existing project or select the saved run in History to inspect its progress and completion.

## Downloads

- `NomiUploader-Windows.zip` — Windows GUI plus source CLI.
- `NomiUploader-Linux-x86_64.tar.gz` — Linux GUI plus source CLI.
- `NomiUploader-macOS-arm64.zip` — Apple Silicon macOS GUI plus source CLI.
- `NomiUploader-macOS-x86_64.zip` — Intel macOS GUI plus source CLI.
- `NomiUploader-Python-CLI.zip` — Python-only distribution (no GUI installation).

Each GUI package includes `CLI-IN-GUI-DOWNLOAD.md` and the Python uploader. The standalone CLI ZIP remains an asset **within the same release**, not a separate version or release.

These unsigned builds are provided for Windows, Linux x86-64, and macOS (Apple Silicon and Intel). Updates are installed manually.
