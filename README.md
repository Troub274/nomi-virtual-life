# Nomi Virtual Life

Tools for Nomi.ai virtual environments, autobiographical replay and conversational continuity.
Nomi Uploader handles imports; [Chat Bridge](bridge/README.md) connects live ChatGPT and Nomi conversations. See the [uploader guide](uploader/README.md),
[recovery guide](uploader/RECOVERY.md), and [tests](uploader/tests/README.md).

## Windows GUI alpha — no Python required

**[Download NomiUploader-Windows.zip from GitHub Releases](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-windows-alpha)**

Extract it, then double-click `NomiUploader.exe`. For setup, unsigned-app warnings,
SmartScreen's **More info → Run anyway**, and Smart App Control, see the
**[Windows alpha instructions](uploader/gui/WINDOWS-ALPHA.md)**.
This is experimental software, not code-signed. Do not disable Defender antivirus to run it.

## Linux GUI alpha — x86-64

**[Linux alpha release](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-linux-alpha)**

Extract `NomiUploader-Linux-x86_64.tar.gz` and launch `NomiUploader` on a supported Linux graphical desktop.
Unlike the Windows EXE, Linux requires system WebKitGTK/GTK libraries. See the
**[Linux install notes](uploader/gui/README-LINUX.md)** for requirements and limitations.

## macOS GUI alpha — Apple Silicon and Intel

**[macOS alpha downloads](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-macos-alpha)**

Download the ZIP for your Mac architecture, extract `NomiUploader.app`, and launch it.
This alpha is unsigned and unnotarized; see the [macOS installation and Gatekeeper guide](uploader/gui/README-MACOS.md).

## Quick start

Requires Python 3.10+. Optional Word support: `python -m pip install -r uploader/requirements.txt`.
Set `NOMI_API_KEY` privately before live operation.

For a packaged example, use the same command every time. It starts a new run when needed and safely resumes an unfinished checkpoint:

```sh
python examples/run_package.py beth
python examples/run_package.py chris
python examples/run_package.py mary
python examples/run_package.py tammy
```

Check progress without API calls with `python examples/run_package.py tammy --status`. Use `--restart` only when intentionally beginning another completed run.

The raw v1.1 uploader supports journal ranges such as `--entries 45-100` and uses a 750-character default transport limit under the Nomi API's 800-character ceiling:

```sh
python uploader/nomi-uploader.py diary.txt --entries 45-100
python uploader/nomi-uploader.py --resume --easy
python -m unittest discover -s uploader/tests -v
```

The exact pre-v1.1 uploader is preserved at `uploader/archive/nomi-uploader-v1.0.py`.

## Example packages

[Beth](examples/beth/README.md) includes 565 journal entries, ready-to-use uploader inputs,
and a [data-only ZIP](examples/beth/BETH_UPLOADER.zip). Character references and the portrait
are for viewing, not uploading. [Package migration](examples/README.md) explains migration
and the [Chris package](examples/chris/README.md).

For journal and conversation imports, run `uploader/nomi-uploader.py`. Its internal compatibility
module preserves API, journal-heading and conversation-export behavior. It is not a
separate application. The archived v1.0 uploader is also retained as a normal repository file,
in addition to Git history.

## Chat Bridge

Load `bridge/extension/` as an unpacked Edge extension. See the [bridge guide](bridge/README.md)
and [migration instructions](bridge/MIGRATION.md) for existing installations. The optional
legacy desktop wrapper is in `bridge/desktop/`. Bridge checks run with Node.js 22:

```sh
cd bridge
node --test tests/*.test.cjs
```

## Existing runs

Keep existing checkpoints, completion receipts, reply files and original input paths.
Resume uploader runs using their original unchanged inputs and checkpoint. Do not point
an old importer checkpoint at the uploader: the formats differ. Inspect the original
run and remote room before planning a new upload; replay can duplicate content.

## Project status

Experimental community software, not official Nomi.ai software. A completed transmission
does not establish durable memory retention. The bridge includes Direct Chat, Group, API Room and Heartbeat modes. Virtual-world
engines remain a planned area. Keep keys, private journals, exports
and runtime data out of this public repository.
