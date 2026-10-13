@echo off
setlocal
cd /d "%~dp0"
set "RELIVE_EVERY=%~1"
if "%RELIVE_EVERY%"=="" set "RELIVE_EVERY=5"
if not exist beth_v1\manifest.json (
  py -3 prepare_v1.py BETHBOOT_V085.ZIP --output beth_v1 --relive-every %RELIVE_EVERY%
  if errorlevel 1 exit /b 1
)
if "%NOMI_API_KEY%"=="" (
  echo ERROR: Set NOMI_API_KEY in your environment before upload.
  exit /b 1
)
py -3 ..\..\uploader\nomi-uploader.py --date-format US --checkpoint beth_v1\beth_v1_checkpoint.jsonl --completion beth_v1\beth_v1_completed.json --replies beth_v1\beth_v1_replies.txt beth_v1\BETH01_V1.TXT beth_v1\BETH02_V1.TXT beth_v1\BETH03_V1.TXT beth_v1\BETH04_V1.TXT beth_v1\BETH05_V1.TXT
