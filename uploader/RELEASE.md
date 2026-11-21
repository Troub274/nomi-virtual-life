# Nomi Uploader 1.4i.7

- Files now has one explicit editor for upload type, source, date, Header prompt, and Reply prompt. Each prompt has a small adjacent count field from 0 to 1000; 0 disables repetition or replies.
- Changing upload type loads that type's default prompts. The prompt boxes can be edited or pasted over. This version replaces the displayed prompts when you change type, including custom wording.
- The sample below the fields shows the edited header and source body. An expandable upload preview shows the actual planned messages.
- Virtual header edits autosave with the project and apply to new uploads without a separate file save. Save header writes a readable sidecar such as journal.txt.upldhdr beside the original file; the original body is unchanged.
- Loading a source file populates the fields from its saved project settings, matching sidecar, or embedded header. Missing values come from Settings. Old empty project placeholders no longer override an existing file header.
- Settings exposes editable Header and Reply defaults separately for Knowledge, Instructions, Chat, and both journal variants. Changes persist automatically. Return to defaults restores the application's built-in prompts.
- Prompt boxes appear immediately, even before API-key setup. The desktop app loads personalized defaults before authentication. Opening the HTML directly allows inspection; saving requires the desktop app.
- TXT, DOCX, Nomi exports, and ChatGPT JSON/ZIP exports use the same file controls. Existing checkpoints retain their saved plans during Normal Resume; file edits apply to new uploads or Manual Restart.

## Downloads

- `NomiUploader-Windows.zip` — Windows GUI plus source CLI.
- `NomiUploader-Linux-x86_64.tar.gz` — Linux GUI plus source CLI.
- `NomiUploader-macOS-arm64.zip` — Apple Silicon macOS GUI plus source CLI.
- `NomiUploader-macOS-x86_64.zip` — Intel macOS GUI plus source CLI.
- `NomiUploader-Python-CLI.zip` — Python-only distribution.

All five packages are part of this release. GUI packages include the Python CLI and its usage instructions. These unsigned builds are installed manually. Pause an active upload and close the app before replacing the executable, then select the saved run and use Normal Resume.
