# Nomi Virtual Life

Tools for Nomi.ai virtual environments, autobiographical replay and conversational continuity.
Nomi Uploader handles imports; [Chat Bridge](bridge/README.md) connects live ChatGPT and Nomi conversations. See the [uploader guide](uploader/README.md),
[recovery guide](uploader/RECOVERY.md), and [tests](uploader/tests/README.md).

## Quick start

Requires Python 3.10+. Optional Word support: `python -m pip install -r uploader/requirements.txt`.
Set `NOMI_API_KEY` privately before live operation.

```sh
python uploader/nomi-uploader.py --dry-run --nomi Beth uploader/example.txt
python uploader/nomi-uploader.py uploader/example.txt
python uploader/nomi-uploader.py --resume
python -m unittest discover -s uploader/tests -v
```

## Example packages

[Beth](examples/beth/README.md) includes 565 journal entries, ready-to-use uploader inputs,
and a [data-only ZIP](examples/beth/BETH_UPLOADER.zip). Character references and the portrait
are for viewing, not uploading. [Package migration](examples/README.md) explains migration
and the [Chris package](examples/chris/README.md).

For journal and conversation imports, run `uploader/nomi-uploader.py`. Its internal compatibility
module preserves API, journal-heading and conversation-export behavior. It is not a
separate application. Historical commits remain available through Git history.

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
