# Command-line uploader included with GUI downloads

**The GUI release also contains the Python API command-line uploader.** You do not need to open the GUI to run it. Each download includes a `cli/` directory with `nomi-uploader.py`, `legacy_v085.py`, `requirements.txt`, `README.md`, and `RECOVERY.md`.

## Windows

Extract the Windows ZIP, open PowerShell inside the extracted directory, and run:

```powershell
py -3 -m pip install -r .\cli\requirements.txt
py -3 .\cli\nomi-uploader.py --help
py -3 .\cli\nomi-uploader.py --dry-run --nomi Mary .\my-book.txt
py -3 .\cli\nomi-uploader.py .\my-book.txt
```

Python 3.10+ is required for the **source CLI**, but not for the GUI application. The GUI executable is built with the Windows windowed subsystem; do not expect `NomiUploader.exe --uploader-cli` to display output in PowerShell. Use the bundled Python CLI files shown above.

## Linux

Extract the `tar.gz` and run from its directory:

```sh
./NomiUploader --uploader-cli --help
./NomiUploader --uploader-cli --dry-run --nomi Mary my-book.txt
./NomiUploader --uploader-cli my-book.txt
```

This invokes the exact Python uploader **embedded in the packaged GUI executable** without launching its GUI. Alternatively, run `python3 cli/nomi-uploader.py` after installing `cli/requirements.txt` (Python 3.10+).

## macOS

Extract the ZIP, then from Terminal in the directory containing `NomiUploader.app`:

```sh
./NomiUploader.app/Contents/MacOS/NomiUploader --uploader-cli --help
./NomiUploader.app/Contents/MacOS/NomiUploader --uploader-cli --dry-run --nomi Mary my-book.txt
./NomiUploader.app/Contents/MacOS/NomiUploader --uploader-cli my-book.txt
```

The ZIP also includes the standalone `cli/` directory; `python3 cli/nomi-uploader.py` works with Python 3.10+ and the optional requirements installed.

## macOS TLS certificates

The standalone Python CLI uses the same verified `certifi` CA bundle as the
packaged macOS app. Run `python3 -m pip install -r cli/requirements.txt`
once in your Python environment. **No `SSL_CERT_FILE` export is needed**
for normal public HTTPS connections, whether using `python3 cli/nomi-uploader.py`
or the embedded `--uploader-cli` executable. An explicitly configured
`SSL_CERT_FILE` still works for custom trust stores.

## Shared API-key configuration (v1.3)

The GUI and Python CLI use the same initialization file in the uploader's
application-data directory, next to the checkpoint hierarchy:
`nomi-uploader.ini`. There is no required API-key environment export.

To configure or replace the key using the Python CLI, run:

```sh
python3 cli/nomi-uploader.py --config
```

Enter the API key when prompted, then choose either **plaintext** or
**password encryption**. For the encrypted option, the uploader uses a random
salt, password-derived key (scrypt), and authenticated AES-GCM encryption.
The password is not saved; every new GUI launch or interactive CLI command
requiring API access asks for it. If forgotten, use the GUI's Reset API Key
control or run `--config` again and provide the API key anew. Journals and
projects are unaffected.

For direct Linux/macOS executable CLI usage, replace the command above with
`./NomiUploader --uploader-cli --config` or
`./NomiUploader.app/Contents/MacOS/NomiUploader --uploader-cli --config`.
The old `NOMI_API_KEY` environment setting remains optional for automation.

## API key and recovery

For **live** uploads, set the `NOMI_API_KEY` environment variable in the terminal (PowerShell: `$env:NOMI_API_KEY="..."`; POSIX shells: `export NOMI_API_KEY="..."`). Avoid putting the key in command history or scripts shared with others.

Useful flags:

```text
--status --checkpoint <path>     Inspect checkpoint (no API call)
--resume --checkpoint <path>     Resume existing checkpoint
--manual-restart 1:23            Operator-selected restart (requires --resume)
--process-every 0                Disable periodic replies/reflection
--header-every 1 --header-text "The following is your biography."
--reply-prompt "Review entries {first}-{last}."
```

The CLI and GUI use the **same upload engine** but do **not automatically share checkpoint paths**. Always pass the intended checkpoint path explicitly when resuming a GUI-created run. Do not run two uploaders against the same room/checkpoint concurrently.

See `cli/README.md` and `cli/RECOVERY.md` for full usage and recovery precautions.
