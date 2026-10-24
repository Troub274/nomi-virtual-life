# Nomi Uploader for Windows — Alpha

**Early test build. Not code-signed.** The Windows executable bundles the JavaScript interface and Python uploader. Please report bugs and unexpected behavior in [GitHub Issues](https://github.com/Troub274/nomi-virtual-life/issues).

## Download / install (no terminal, no Python required)

1. Visit the [Windows alpha download page](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-windows-alpha).
2. Under **Assets**, download **NomiUploader-Windows.zip**.
3. Extract the ZIP into a normal folder.
4. Open **NomiUploader.exe**. Do **not** open `index.html`.

A GitHub Actions build artifact is not the recommended user download; the Release ZIP is.

## Getting started

1. Enter your Nomi API key and click **Load Nomis**.
2. Choose your Nomi and click **Refresh rooms**.
3. Select an existing room or create a new one. Review the room name and description.
4. Add TXT, DOCX, JSON or Nomi export ZIP files to the queue.
5. Select each file and inspect its processing settings. TXT headers and ZIP/JSON introduction/reflection prompts can be configured in the editor.
6. Click **Preview / dry run** before doing a live upload, then **Start upload**.

**Automatic reflection:** Set **Process Every** to **0**, both globally and in any individual file where it is overridden. Remove explicit prompt lines or set export-specific prompts accordingly if you want a content-only import.

**Existing uploads:** Do not switch executable versions or change source files while an upload is active. The checkpoint is important for safe recovery; do not delete or hand-edit it.

## Windows warnings — unsigned alpha

This executable is **not yet code signed**. New, unsigned applications often encounter Windows reputation-based warnings. A warning does not prove that software is malicious, but successful compilation is not a security audit either. Only use the official release from this repository and consider scanning the ZIP or executable first.

### A. Microsoft Defender SmartScreen: “Windows protected your PC”

This is typically the blue warning about an unrecognized app. If you trust the file and the prompt offers this choice:

1. Click **More info**.
2. Verify the application is **NomiUploader.exe** and the publisher is listed as **Unknown publisher** (expected for this alpha).
3. Click **Run anyway**.

This is a **per-launch choice**, not a need to turn off Defender antivirus.

If the warning instead says the app contains malware or has been quarantined, **do not assume this is just a reputation warning**. Check **Windows Security → Virus & threat protection → Protection history** for the specific detection and report it to the project. Do not disable real-time antivirus scanning.

### B. Smart App Control: “Smart App Control blocked this app”

On supported Windows 11 installations Smart App Control may deny an unsigned app **without a Run anyway button**. Microsoft states there is **no per-app override**. The preferred fix for distributed software is trusted code signing; this early alpha is not signed.

If you nevertheless decide to switch it off on **your own testing device**:

1. Open **Settings → Privacy & security → Windows Security**.
2. Select **App & browser control → Smart App Control settings**.
3. Choose **Off**, confirm, then try the app again.

**Important:** This changes protection **system-wide**. It is not a per-file exception, and re-enabling it may depend on your Windows build and configuration. Check Microsoft's documentation before changing this setting:
- [Smart App Control FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions)
- [App & browser control](https://support.microsoft.com/en-us/windows/security/windows-security/app-browser-control-in-the-windows-security-app)

### C. Edge download warning

If Microsoft Edge warns about a downloaded ZIP or executable, verify the URL, filename and source first. Edge download reputation warnings differ from the SmartScreen launch prompt. Follow its on-screen review options if available; don't disable global web/download protection as a shortcut.

## Known alpha limitations

- The app is unsigned and may be blocked by Windows.
- File header editing is currently TXT-focused. ZIP/JSON exports have separate configurable introduction and periodic reflection prompts.
- Room editing is subject to Nomi API support; changes are not automatically retried after unclear network results.
- Advanced ambiguous-send recovery still requires care. No automatic duplicate POST on uncertain responses.
- The API key is saved in the GUI's local settings file; it is **not yet stored using Windows Credential Manager**. Do not use this alpha on an untrusted or shared machine.
- This build is not yet security-audited, nor validated across all Windows installations.

## Development

The GUI lives at `uploader/gui/` and delegates uploads to `uploader/nomi-uploader.py`. The existing CLI remains authoritative. Windows builds use GitHub Actions and PyInstaller.
