# Nomi Uploader 1.4i — Preview, History and Help

- **Preview the actual upload.** The selected file shows its planned opening, headers, content chunks and reply prompts, including queue edits and fallback settings. Invalid chats and journals show inline formatting help and examples.
- **See which prompts apply.** Settings lists all opening and periodic prompt templates, including personalization. Per-file views show file prompts and applicable fallbacks. Upload-wide fallback labels explain that file settings take precedence.
- **Follow a run live.** Filter activity by prompts, replies, or errors and retries. Saved replies display the full text and identify the pass and message, including replies returned using the API's alternate text field.
- **Read help inside the app.** The quick guide and bundled Uploader and Recovery guides use matching collapsible sections and work offline.
- **Check for updates.** See the running version and latest published version. If GitHub rate-limits the API, the app checks the public release page. Copy the release URL without calling the system browser or requesting clipboard permission.
- **Run the Linux GUI from source.** Documented the required Ubuntu Qt WebEngine libraries and updated the file picker to use the current pywebview API.
- Updated sample inputs to demonstrate the current prompt defaults. Upload stop rules and checkpoint handling are unchanged. Keep the original inputs for any existing upload when resuming.

## Downloads

- `NomiUploader-Windows.zip` — Windows GUI plus source CLI.
- `NomiUploader-Linux-x86_64.tar.gz` — Linux GUI plus source CLI.
- `NomiUploader-macOS-arm64.zip` — Apple Silicon macOS GUI plus source CLI.
- `NomiUploader-macOS-x86_64.zip` — Intel macOS GUI plus source CLI.
- `NomiUploader-Python-CLI.zip` — Python-only distribution (no GUI installation).

Each GUI package includes `CLI-IN-GUI-DOWNLOAD.md` and the Python uploader. The standalone CLI ZIP remains an asset **within the same release**, not a separate version or release.

These unsigned builds are provided for Windows, Linux x86-64, and macOS (Apple Silicon and Intel). Updates are installed manually.
