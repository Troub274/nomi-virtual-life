@echo off
setlocal
cd /d "%~dp0"
py -3 ..\..\uploader\nomi-uploader.py --resume --checkpoint beth_v1\beth_v1_checkpoint.jsonl --completion beth_v1\beth_v1_completed.json
