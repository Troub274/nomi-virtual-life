#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python -m pip install --upgrade pyinstaller "pywebview[qt]" PyQt6-WebEngine
python -m PyInstaller --noconfirm --clean --onefile --windowed --name NomiUploader \
  --paths uploader \
  --hidden-import legacy_v085 \
  --hidden-import qtpy \
  --collect-all PyQt6.QtWebEngineCore \
  --collect-all PyQt6.QtWebEngineWidgets \
  --collect-submodules webview \
  --add-data 'uploader/nomi-uploader.py:uploader' \
  --add-data 'uploader/legacy_v085.py:uploader' \
  --add-data 'uploader/gui/index.html:uploader/gui' \
  uploader/gui/app.py
mkdir -p dist/linux-package
cp dist/NomiUploader dist/linux-package/NomiUploader
cp uploader/gui/README-LINUX.md dist/linux-package/README-LINUX.md
chmod +x dist/linux-package/NomiUploader
tar -C dist/linux-package -czf dist/NomiUploader-Linux-x86_64.tar.gz .
sha256sum dist/NomiUploader-Linux-x86_64.tar.gz
