#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
arch="${1:?Specify arm64 or x86_64}"
python -m pip install --upgrade pyinstaller pywebview
python -m PyInstaller --noconfirm --clean --windowed --name NomiUploader \
  --paths uploader \
  --hidden-import legacy_v085 \
  --collect-submodules webview \
  --add-data 'uploader/nomi-uploader.py:uploader' \
  --add-data 'uploader/legacy_v085.py:uploader' \
  --add-data 'uploader/gui/index.html:uploader/gui' \
  uploader/gui/app.py
test -d dist/NomiUploader.app
cd dist
ditto -c -k --keepParent NomiUploader.app "NomiUploader-macOS-${arch}.zip"
shasum -a 256 "NomiUploader-macOS-${arch}.zip"
