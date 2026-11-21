# Nomi Uploader changelog

## Unreleased

- Replace the split file editor with explicit upload type, source, date, Header and Reply prompt boxes, adjacent 0–1000 count fields, and a sample below.
- Make every existing prompt type editable in Settings with automatic persistence and a Return to defaults button that restores application defaults.
- Autosave virtual file headers in the project and use them for upload planning. Save header writes a readable `.upldhdr` sidecar without changing the original body. Load existing headers, sidecars, and saved project edits into the fields.
- Apply the same visible file controls to TXT, DOCX, Nomi exports, and ChatGPT JSON/ZIP exports. Preserve compatibility with existing saved upload plans.

## 1.4i.6 — 2026-11-19

- Interactive CLI Resume now asks whether uncertain private replies arrived. Enter confirms without pasted text; paste, wait, and explicitly confirmed retry options are also available. Noninteractive recovery keeps its existing behavior.
- Add a Resume dialog for uncertain private replies: optionally paste the received reply, press Enter to confirm receipt and continue, keep waiting, or explicitly retry. Empty confirmations never save placeholder text as a reply.
- Add a local source-CLI recovery action for private replies explicitly verified by the user. Preserve a checkpoint backup and record an append-only receipt so Normal Resume can continue after that reflection.


## 1.4i.5 — 2026-11-19

- Use one reflection interval field in the same position for TXT and JSON/ZIP files. Hide inapplicable controls and distinguish repeated headers from reflections.
- Add source dates or date ranges to periodic reflection prompts for new uploads and regenerated plans. Normal Resume preserves the saved wording.
- Add private-chat request wait/return timing diagnostics and a delayed-response simulator regression.

## 1.4i.4 — 2026-11-18

- Added Room / Private chat reply destination across desktop platforms, the CLI, and example package runner. Uploads remain in the room; private replies send the reflection prompt to the receiving Nomi's main chat.
- Persist reply destinations through checkpoint recovery and manual restart. Private-chat timeouts require explicit recovery to avoid silently duplicating prompts.

## 1.4i.3 — 2026-11-18

- Prevent overlapping GUI status polls from accumulating threads while large checkpoints are scanned.
- Share one cached checkpoint snapshot between status and recovery, refreshing it when the journal changes.
- Bound in-memory activity logs and recent replies, and read only the start record when listing run history.
- Add large-checkpoint, concurrent polling, and timer-overlap regressions.

## 1.4i.2 — 2026-11-18

- Added ChatGPT JSON and ZIP text imports with selected-branch traversal, speaker labels, conversation titles, and timestamps. Nomi downloader exports remain supported.
- Fixed literal bracketed transcript headings changing Chat files into Knowledge sections.
- Fixed valid pass and message numbers being rejected by Manual Restart and advanced recovery.

- Show the effective reflection interval and inheritance on the Files Prompts tab.
- Bundle declared uploader dependencies on Linux and macOS as well as Windows.

## 1.4i.1 — 2026-11-17

- Fixed Word document uploads in the Windows executable by bundling the uploader's Python dependencies, including `python-docx`.
- Includes the date parser and macOS update-check fixes first distributed in rebuilt 1.4i packages.

## 1.4i builds — 2026-11-16

- Later builds under the same 1.4i tag recognized more date formats during upload planning and used a verified CA bundle for GitHub update checks on macOS.
- The initial 1.4i build added a preview of the actual upload plan, including opening prompts, headers, content chunks, and reply prompts. Invalid inputs show formatting help.
- Settings and per-file views show which personalized prompt templates and defaults apply.
- Live History filters prompts, replies, and errors. Saved replies show their full text and pass/message position.
- Added bundled offline uploader and recovery help, improved update checking, and updated Ubuntu source-launch instructions and file picker support.

[1.4i release notes](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-v1.4i)

## 1.3i rebuilds — 2026-11-03 to 2026-11-14

- November 3: fixed Windows UTF-8 preview and upload-log output, including emoji and non-Latin text.
- November 7: added inclusive replay chunk ranges to the shared uploader CLI.
- November 9: documented automatic release of completed-room protection and checkpoint retirement.
- November 14: distributed adaptive reply retry delays and personalized opening and periodic prompt templates.

[Unified release build history](https://github.com/Troub274/nomi-virtual-life/actions/workflows/release-nomi-uploader-unified.yml?query=branch%3Amain)

## 1.3i — 2026-11-02

- Introduced the production desktop interface on top of the 1.3 upload engine and checkpoint format. Added Destination, Files, Upload, History, and Settings tabs, plus light, dark, and system appearance.
- Added destination and credential management, per-file options, upload defaults, copyable diagnostics, advanced recovery controls, and manual update checks.
- Published one release with Windows, Linux, Intel and Apple Silicon macOS, and standalone Python CLI downloads. The native app packages also include the source CLI.

[1.3i release notes](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-v1.3i)

## 1.3 engine — 2026-11-02

- Added Normal Resume with safe retry classification and Manual Restart with an explicit append-only checkpoint boundary and a recalculated upload plan.
- Shared API-key setup and storage between the GUI and CLI, with optional password-based encryption.
- Added verified CA certificates for macOS Finder launches and standalone CLI use.

## 1.2 and desktop alphas — 2026-10-24 to 2026-10-29

- The first GUI host wrapped the existing command-line uploader. Early builds added file queues and previews, editable text metadata and ZIP/JSON prompts, Nomi selection by UUID, and room management.
- Added portable Windows, macOS, and Linux alpha packages and a standalone Python CLI download. Linux packaging moved to Qt WebEngine.
- Added cooperative pause, history clearing, configurable per-chunk headers and reflection prompts, and user display-name substitution through `[username]`.

[Windows alpha](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-windows-alpha) · [macOS alpha](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-macos-alpha) · [Linux alpha](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-linux-alpha) · [CLI alpha](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-cli-alpha)

## 1.1 — 2026-10-21 to 2026-10-23

- Added character-based planning and entry-range support while preserving compatibility with existing upload plans and checkpoints.
- Recorded content completion before requesting a reply, making the resume boundary explicit.

## 1.0 — 2026-10-13 to 2026-10-19

- Introduced the v1 uploader with native Nomi exports, typed content and reflection prompts, reply transcripts, and a durable resume journal. Preserved the v0.85 engine for legacy CLI compatibility.
- Added room inspection and deletion controls, protected incomplete runs, and released protection for completed runs.
- Added operator-controlled recovery for ambiguous content sends and replies, plus recovery documentation.

[Uploader Git history](https://github.com/Troub274/nomi-virtual-life/commits/main/uploader/)
