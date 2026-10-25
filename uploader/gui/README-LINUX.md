# Nomi Uploader — Linux alpha (x86-64)

Download **NomiUploader-Linux-x86_64.tar.gz** from the [Linux alpha release](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-linux-alpha). Extract and launch the included `NomiUploader` executable. No Python installation is required for the packaged app.

The GUI and Python uploader are the same as on Windows and macOS. This build uses a **bundled Qt WebEngine renderer**, rather than the GTK/WebKit2 backend used by older Linux alpha packages. This specifically addresses the `Namespace WebKit2 not available` and `No module named qtpy` startup errors. A compatible Linux graphical desktop (X11 or Wayland) and common system graphics libraries are still required. The package is built for x86-64 Ubuntu 24.04; other distributions are not yet verified.

This is an experimental unsigned build, not a universal AppImage, Flatpak, or Debian package. Linux libraries and desktop display support remain system dependencies. Use a graphical desktop (Wayland or X11). First-run failures should be reported with distribution version and error output.

Your API key and checkpoints are saved under `~/.local/share/NomiUploader/` unless `LOCALAPPDATA` is set. Do not manually edit or delete checkpoints. The API key is currently stored in plain text in local settings, so do not use this alpha on shared or untrusted machines.

The program is community software and is not official Nomi.ai software. See the [project README](https://github.com/Troub274/nomi-virtual-life) and [uploader guide](https://github.com/Troub274/nomi-virtual-life/blob/main/uploader/README.md).
