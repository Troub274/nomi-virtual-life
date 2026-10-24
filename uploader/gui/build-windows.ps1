$ErrorActionPreference = 'Stop'
Push-Location (Resolve-Path "$PSScriptRoot/../..")
try {
  python -m pip install --upgrade pyinstaller pywebview
  if ($LASTEXITCODE -ne 0) { throw 'Dependencies failed' }
  python -m PyInstaller --noconfirm --clean --onefile --windowed --name NomiUploader `
     --paths uploader `
     --hidden-import legacy_v085 `
     --collect-submodules webview `
     --add-data 'uploader/nomi-uploader.py;uploader' `
     --add-data 'uploader/legacy_v085.py;uploader' `
     --add-data 'uploader/gui/index.html;uploader/gui' `
     uploader/gui/app.py
  if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
  Write-Host 'Build complete: dist/NomiUploader.exe'
} finally { Pop-Location }
