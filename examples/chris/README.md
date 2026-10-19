# Chris / Christine Sue Norman — uploader package

The supplied `CHRISTINE_COMPLETE_1000_V1.zip` was already in uploader Journal format.
Its ten notebooks (1,000 entries) are preserved byte-for-byte in `input/`.
Original author documentation, source audit and manifest remain in `reference/` as
provenance. The original manifest's message counts are historical estimates; use the
current dry run. `manifest.json` records the source archive and extracted file hashes.

From the repository root:

```sh
python examples/run_package.py chris --dry-run
python examples/run_package.py chris
python examples/run_package.py chris --resume
```

Live operation requires `NOMI_API_KEY`; select Christine interactively. Journal Source
is intentionally omitted, so memories belong to the selected Nomi. Each notebook has
100 chronological dated entries and `Process Every: 5`. The package runner uses an
isolated `.local-runs/chris/` checkpoint, receipt and reply transcript. It does not use
or modify existing files in your development checkout. For an existing run, continue
with the original uploader command, checkpoint and unchanged input paths instead.

The data-only `CHRIS_UPLOADER.zip` includes inputs, configuration and references;
extract before use. Never pass a diary bootstrap ZIP directly to the uploader, which
interprets ZIP arguments as Nomi conversation exports. Do not upload reference files.
Use the [recovery guide](../../uploader/RECOVERY.md) for uncertain sends and replies.
Completion confirms transmission, not durable memory retention.
