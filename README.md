# Nomi Virtual Life

Tools for Nomi.ai virtual environments, autobiographical replay and conversational continuity.
Nomi Uploader is the supported entry point. See the [uploader guide](uploader/README.md),
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

Only `uploader/nomi-uploader.py` is a supported executable. Its internal compatibility
module preserves API, journal-heading and conversation-export behavior. It is not a
separate application. Historical commits remain available through Git history.

## Existing runs

Keep existing checkpoints, completion receipts, reply files and original input paths.
Resume uploader runs using their original unchanged inputs and checkpoint. Do not point
an old importer checkpoint at the uploader: the formats differ. Inspect the original
run and remote room before planning a new upload; replay can duplicate content.

## Project status

Experimental community software, not official Nomi.ai software. A completed transmission
does not establish durable memory retention. Virtual-world engines and Nomi bridges
are planned areas, not included implementations. Keep keys, private journals, exports
and runtime data out of this public repository.
