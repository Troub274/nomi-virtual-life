# Nomi Uploader — Python command-line release

The CLI is the **authoritative Nomi Uploader v1.2** and works on Windows, macOS and Linux with Python 3.10+.

Download `NomiUploader-CLI-Python.zip` from the [Python CLI release](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-cli-alpha), then extract it.

The ZIP contains `nomi-uploader.py`, its required compatibility module `legacy_v085.py`, `requirements.txt`, and uploader documentation. **Both Python files must stay together.** `legacy_v085.py` is a dependency, not an alternative executable.

From the extracted folder:

```sh
python -m pip install -r requirements.txt
python nomi-uploader.py --dry-run --nomi Beth your-diary.txt
python nomi-uploader.py your-diary.txt
python nomi-uploader.py --status
python nomi-uploader.py --resume --easy
```

Version 1.2 also supports repeating a text header on content chunks without requesting replies:

```sh
python nomi-uploader.py --header-every 1 --header-text "The following is your biography." --process-every 0 book.txt
```

For reflection prompts use `--process-every N` and optional `--reply-prompt "Reflect on items {first}-{last}."`. Both are available in the GUI alongside Header Every and Header Text. Text input supports section-level `Header Every:`, `Header Text:`, `Process Every:`, and `Reply Prompt:` overrides.

Set the `NOMI_API_KEY` environment variable before a live run. DOCX input needs `python-docx` (installed above); ordinary TXT imports can run without it. The uploader uses checkpoints; keep original source files and checkpoint information unchanged when resuming. The default CLI reflection interval is 0; a blank per-file `Process Every` inherits the command-line setting while an explicit 0 disables reflections.

This is a testing release, not an official Nomi.ai product. See `README.md` and `RECOVERY.md` in the ZIP for safety and recovery details.
