#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
arch="${1:?Specify arm64 or x86_64}"
python -m pip install --upgrade pyinstaller pywebview certifi cryptography
icon_args=()
if [[ -f uploader/assets/icon.icns ]]; then
  icon_args=(--icon uploader/assets/icon.icns)
else
  echo "WARNING: uploader/assets/icon.icns missing; default macOS application icon will be used." >&2
fi
python -m PyInstaller --noconfirm --clean --windowed --name NomiUploader "${icon_args[@]}" \
  --paths uploader \
  --hidden-import legacy_v085 \
  --collect-data certifi \
  --collect-submodules webview \
  --add-data 'uploader/nomi-uploader.py:uploader' \
  --add-data 'uploader/legacy_v085.py:uploader' \
  --add-data 'uploader/gui/index.html:uploader/gui' \
  uploader/gui/app.py
test -d dist/NomiUploader.app
mkdir -p dist/cli
cp uploader/nomi-uploader.py uploader/legacy_v085.py uploader/requirements.txt uploader/README.md uploader/RECOVERY.md dist/cli/
cp uploader/gui/CLI-IN-GUI-DOWNLOAD.md dist/CLI-IN-GUI-DOWNLOAD.md
cd dist
mkdir -p macos-package
cp -R NomiUploader.app macos-package/
cp -R cli macos-package/
cp CLI-IN-GUI-DOWNLOAD.md macos-package/
ditto -c -k --keepParent macos-package "NomiUploader-macOS-${arch}.zip"
shasum -a 256 "NomiUploader-macOS-${arch}.zip"
