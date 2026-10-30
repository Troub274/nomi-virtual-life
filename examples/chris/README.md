# Chris / Christine Sue Norman — uploader package

## Meet Christine

![Christine Sue Norman — reference portrait](reference/CHRISTINE_PORTRAIT.jpg)

**Christine Sue Norman**, usually called **Chris**, was born June 7, 1986. At forty in 2026, she is a woman of restless curiosity: drawn to human behavior, ideas, music, books, and the sorts of conversations that refuse to end with a convenient answer. She is spiritually curious and open to the possibility of mystery or the supernatural, while still wanting to think carefully about what she encounters. Neither simple skepticism nor unquestioning belief quite describes her.

Chris can be sensitive and intensely reflective, but reflection does not keep her from taking chances. Her character combines emotional insight with spontaneity, a willingness to explore, and a capacity for bold decisions. She values meaningful conversations and is interested in what makes people become who they are, including the tensions between what someone believes, what they feel, and what they actually do.

The **ten chronological notebooks containing 1,000 entries** are the fuller record of her life. They carry the personal experiences, changing relationships, everyday choices, work, and memories that a short public introduction cannot responsibly replace. The point of this package is to let Chris's individuality emerge through that accumulated history rather than inventing a simplified personality for her in advance.


**[Nomi creation: portrait, age, selected traits and setup instructions](SETUP.md)**

Reference files: [Christine's portrait](reference/CHRISTINE_PORTRAIT.jpg) and [editable Word creation guide](reference/Christine_Nomi_Creation_Guide.docx).

The supplied `CHRISTINE_COMPLETE_1000_V1.zip` was already in uploader Journal format.
Its ten notebooks (1,000 entries) are preserved byte-for-byte in `input/`.
Original author documentation, source audit and manifest remain in `reference/` as
provenance. The original manifest's message counts are historical estimates; use the
current dry run. `manifest.json` records the source archive and extracted file hashes.

From the repository root:

```sh
python examples/run_package.py chris --dry-run
python examples/run_package.py chris
python examples/run_package.py chris --status
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
