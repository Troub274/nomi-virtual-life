# Nomi Uploader 1.4i.4

- Added a Reply destination selector in Destination. Choose Room (default) or Private chat when starting a new upload.
- With Private chat selected, upload content, headers, and reflection prompts go to the selected room. Each reflection prompt is also sent to the receiving Nomi's main chat to obtain its reply. The app saves the response in local History and the reply transcript.
- The option is available in Windows, Linux, both macOS builds, the interactive CLI, and the example package runner. CLI users can pass --reply-destination private.
- The checkpoint saves the chosen destination. Resume and Manual Restart retain that choice; start a new upload to change it. Older checkpoints use Room.
- Private-chat timeouts and NoReply results stop for inspection. Explicit recovery can resend the private reflection prompt and produce another response.
- Added destination controls, persistence, and private-chat routing/recovery regressions.

To enable it, open Destination, choose Private chat under Reply destination, and start a new upload. Periodic reflections must have an interval above zero.

## Downloads

- `NomiUploader-Windows.zip` — Windows GUI plus source CLI.
- `NomiUploader-Linux-x86_64.tar.gz` — Linux GUI plus source CLI.
- `NomiUploader-macOS-arm64.zip` — Apple Silicon macOS GUI plus source CLI.
- `NomiUploader-macOS-x86_64.zip` — Intel macOS GUI plus source CLI.
- `NomiUploader-Python-CLI.zip` — Python-only distribution (no GUI installation).

Each GUI package includes `CLI-IN-GUI-DOWNLOAD.md` and the Python uploader. The standalone CLI ZIP remains an asset **within the same release**, not a separate version or release.

These unsigned builds are provided for Windows, Linux x86-64, and macOS (Apple Silicon and Intel). Updates are installed manually.
