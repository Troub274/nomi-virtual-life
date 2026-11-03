# Nomi Uploader — Linux alpha (x86-64)

Download **NomiUploader-Linux-x86_64.tar.gz** from the [Linux 1.3i release](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-v1.3i). Extract and launch the included `NomiUploader` executable. No Python installation is required for the packaged app.

The GUI and Python uploader are the same as on Windows and macOS. This build uses a **bundled Qt WebEngine renderer**, rather than GTK/WebKit2. This specifically addresses the `Namespace WebKit2 not available` and `No module named qtpy` startup errors. A compatible Linux graphical desktop (X11 or Wayland) and common system graphics libraries are still required. The package is built for x86-64 Ubuntu 24.04; other distributions are not yet verified.

This is an experimental unsigned build, not a universal AppImage, Flatpak, or Debian package. Linux libraries and desktop display support remain system dependencies. Use a graphical desktop (Wayland or X11). First-run failures should be reported with distribution version and error output.

Your API key and checkpoints are saved under `~/.local/share/NomiUploader/` unless `LOCALAPPDATA` is set. Do not manually edit or delete checkpoints. API-key storage is selected during first-run configuration: plaintext or password-encrypted. Encryption requires unlocking at each launch; do not use a shared or untrusted machine to store sensitive credentials.

The program is community software and is not official Nomi.ai software. See the [project README](https://github.com/Troub274/nomi-virtual-life) and [uploader guide](https://github.com/Troub274/nomi-virtual-life/blob/main/uploader/README.md).

## Command-line API mode (included)

The GUI download also contains a **standalone Python API command-line uploader** in the `cli/` folder. You can use it without launching the GUI. Read **`CLI-IN-GUI-DOWNLOAD.md` in the extracted download** for exact platform-specific commands, API-key setup and checkpoint recovery. The same uploader engine is used by both interfaces.
