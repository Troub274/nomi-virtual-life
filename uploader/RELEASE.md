# Nomi Uploader 1.4i.2

- Import ChatGPT conversation JSON and export ZIP files alongside Nomi downloader exports. ChatGPT imports follow the selected branch of each conversation and preserve visible text, speaker labels, UTC timestamps, and conversation titles.
- ChatGPT archives import all included conversations in chronological order. Images, attachments, tool output, and internal processing messages are omitted.
- For JSON and ZIP imports, reflections occur after the configured number of uploaded content chunks, including a final partial batch. A blank file interval inherits Settings. Zero disables periodic reflections.
- The Files Prompts tab shows the effective interval and whether it comes from the file or Settings, and reports prompt-loading errors.
- Fixed bracketed lines inside TXT conversations being treated as new Knowledge sections. Explicitly typed sections remain supported.
- Fixed Manual Restart and advanced recovery rejecting valid pass and message numbers.
- Include the uploader's declared Python dependencies in Windows, Linux, and macOS builds.

Normal Resume retains the saved run's prompts, interval, and prepared inputs. To apply revised files or settings to an existing run, use Manual Restart and inspect the revised plan before choosing the restart position. Restarting at pass 1, message 1 replays from the beginning.

## Downloads

- `NomiUploader-Windows.zip` — Windows GUI plus source CLI.
- `NomiUploader-Linux-x86_64.tar.gz` — Linux GUI plus source CLI.
- `NomiUploader-macOS-arm64.zip` — Apple Silicon macOS GUI plus source CLI.
- `NomiUploader-macOS-x86_64.zip` — Intel macOS GUI plus source CLI.
- `NomiUploader-Python-CLI.zip` — Python-only distribution (no GUI installation).

Each GUI package includes `CLI-IN-GUI-DOWNLOAD.md` and the Python uploader. The standalone CLI ZIP remains an asset **within the same release**, not a separate version or release.

These unsigned builds are provided for Windows, Linux x86-64, and macOS (Apple Silicon and Intel). Updates are installed manually.
