$ErrorActionPreference = 'Stop'
Push-Location (Resolve-Path "$PSScriptRoot/../..")
try {
  python -m pip install --upgrade pyinstaller pywebview -r uploader/requirements.txt
  if ($LASTEXITCODE -ne 0) { throw 'Dependencies failed' }
  $iconArgs = @()
  if (Test-Path 'uploader/assets/icon.ico') { $iconArgs = @('--icon','uploader/assets/icon.ico') }
  else { Write-Warning 'uploader/assets/icon.ico missing: Windows will use a default executable icon.' }
  # runpy executes the bundled script at runtime, so include it in import analysis explicitly.
  python -m PyInstaller --noconfirm --clean --onefile --windowed --name NomiUploader @iconArgs `
     --paths uploader `
     --hidden-import nomi-uploader `
     --hidden-import legacy_v085 `
     --collect-data docx `
     --collect-submodules webview `
     --add-data 'uploader/nomi-uploader.py;uploader' `
     --add-data 'uploader/legacy_v085.py;uploader' `
     --add-data 'uploader/README.md;uploader' `
     --add-data 'uploader/RECOVERY.md;uploader' `
     --add-data 'uploader/gui/index.html;uploader/gui' `
     uploader/gui/app.py
  if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
  Write-Host 'Build complete: dist/NomiUploader.exe'
} finally { Pop-Location }
