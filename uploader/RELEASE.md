# Nomi Uploader 1.4i.5

- Moved the reflection interval to one consistent field at the top of Files > Prompts for TXT and JSON/ZIP files.
- Hide controls that do not apply to the selected format. Blank intervals show their Settings default, and explicit 0 is identified as disabled.
- Renamed header repetition controls to distinguish them from reflection intervals. Word metadata and interval controls identify their document/Settings source.
- Add source conversation or entry dates to periodic reflection prompts for new standard uploads. Batches spanning multiple dates include a date range.
- Normal Resume preserves existing saved prompt wording. Manual Restart regenerates the plan with source-date labels.
- Private-chat logs now identify the send-and-wait operation, returned HTTP status, and elapsed time. Added a delayed private-response simulator check.

Private-chat API NoReply errors continue to stop the run for recovery. These diagnostics help distinguish an API error from a successfully returned reply.

## Downloads

- `NomiUploader-Windows.zip` — Windows GUI plus source CLI.
- `NomiUploader-Linux-x86_64.tar.gz` — Linux GUI plus source CLI.
- `NomiUploader-macOS-arm64.zip` — Apple Silicon macOS GUI plus source CLI.
- `NomiUploader-macOS-x86_64.zip` — Intel macOS GUI plus source CLI.
- `NomiUploader-Python-CLI.zip` — Python-only distribution (no GUI installation).

Each GUI package includes `CLI-IN-GUI-DOWNLOAD.md` and the Python uploader. The standalone CLI ZIP remains an asset **within the same release**, not a separate version or release.

These unsigned builds are provided for Windows, Linux x86-64, and macOS (Apple Silicon and Intel). Updates are installed manually.
