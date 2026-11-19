# Nomi Uploader 1.4i.6

- Resume now opens a recovery dialog when a private reflection request timed out or returned an uncertain result. It shows the original prompt, its memory date, and the send time when available.
- If the reply appeared in private chat, press Enter or choose Reply received — Resume. Pasting the reply is optional; Shift+Enter adds a line break.
- Keep waiting leaves the upload paused. Retry prompt requires explicit confirmation because it may produce a duplicate reply.
- Interactive CLI --resume offers the same recovery choices: Enter confirms receipt, P accepts a multiline reply, W waits, and R offers a confirmed retry. Noninteractive runs retain their existing recovery flags.
- Received-reply confirmations back up the checkpoint and append a user-verified receipt, allowing Resume to continue after the completed reflection without resending it. Empty confirmations do not invent reply text.
- Existing checkpoints and saved upload plans remain compatible. No restart of the upload is required.

## Downloads

- `NomiUploader-Windows.zip` — Windows GUI plus source CLI.
- `NomiUploader-Linux-x86_64.tar.gz` — Linux GUI plus source CLI.
- `NomiUploader-macOS-arm64.zip` — Apple Silicon macOS GUI plus source CLI.
- `NomiUploader-macOS-x86_64.zip` — Intel macOS GUI plus source CLI.
- `NomiUploader-Python-CLI.zip` — Python-only distribution.

All five packages are part of this release. GUI packages include the Python CLI and its usage instructions. These unsigned builds are installed manually. Pause an active upload and close the app before replacing the executable, then select the saved run and use Normal Resume.
