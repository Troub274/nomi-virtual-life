# Nomi Uploader — Linux alpha (x86-64)

Download **NomiUploader-Linux-x86_64.tar.gz** from the [Linux alpha release](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-linux-alpha). Extract and launch the included `NomiUploader` executable. No Python installation is required for the packaged app.

The GUI is the same HTML/JavaScript frontend and Python uploader used in Windows. Linux requires a native WebKitGTK desktop runtime. On Ubuntu/Debian install appropriate WebKitGTK/GTK and GObject Introspection packages from your distribution; on recent Ubuntu releases these are typically `libwebkit2gtk-4.1-0`, `gir1.2-webkit2-4.1`, `gir1.2-gtk-3.0`, and `libgtk-3-0`. Distribution names vary; the binary is built on GitHub's Ubuntu runner and may not run on older distributions or non-x86_64 machines.

This is an experimental unsigned build, not a universal AppImage, Flatpak, or Debian package. Linux libraries and desktop display support remain system dependencies. Use a graphical desktop (Wayland or X11). First-run failures should be reported with distribution version and error output.

Your API key and checkpoints are saved under `~/.local/share/NomiUploader/` unless `LOCALAPPDATA` is set. Do not manually edit or delete checkpoints. The API key is currently stored in plain text in local settings, so do not use this alpha on shared or untrusted machines.

The program is community software and is not official Nomi.ai software. See the [project README](https://github.com/Troub274/nomi-virtual-life) and [uploader guide](https://github.com/Troub274/nomi-virtual-life/blob/main/uploader/README.md).
