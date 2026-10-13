@echo off
setlocal
cd /d "%~dp0"
if not exist BETHBOOT_V085.ZIP (
  echo ERROR: BETHBOOT_V085.ZIP is missing.
  exit /b 1
)
set "RELIVE_EVERY=%~1"
if "%RELIVE_EVERY%"=="" set "RELIVE_EVERY=5"
py -3 prepare_v1.py BETHBOOT_V085.ZIP --output beth_v1 --relive-every %RELIVE_EVERY%
if errorlevel 1 exit /b 1
py -3 ..\..\uploader\nomi-uploader.py --dry-run --nomi "Beth Peterson" --date-format US beth_v1\BETH01_V1.TXT beth_v1\BETH02_V1.TXT beth_v1\BETH03_V1.TXT beth_v1\BETH04_V1.TXT beth_v1\BETH05_V1.TXT
