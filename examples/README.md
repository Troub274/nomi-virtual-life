# Uploader example packages

[Beth](beth/README.md) has 565 entries; [Chris / Christine](chris/README.md) has 1,000; [Mary](mary/README.md) has 200; [Tammy](tammy/README.md) has 300; [Tammy](tammy/README.md) is the long-form V3 rebuild and currently includes its first 100 detailed entries plus a full continuity/reference pack.
Beth and Chris include data-only ZIPs; all packages provide ordered input lists and the current uploader configuration.

From the repository root, preview any package:

```sh
python examples/run_package.py beth --dry-run
python examples/run_package.py chris --dry-run
python examples/run_package.py mary --dry-run
python examples/run_package.py tammy --dry-run
python examples/run_package.py tammy --dry-run
```

Remove `--dry-run` for a new live run after setting `NOMI_API_KEY`, and select the
correct Nomi. Add `--resume` to continue the package runner's checkpoint. Keep all
inputs and their paths unchanged during active runs. The runner keeps per-character
state in `.local-runs/`. It never migrates or overwrites an existing development run.

Beth's original diary bytes, canon and portrait are preserved with hashes in
`beth/source/`. Character setup instructions now use the uploader. Obsolete bundled
executables and launchers were removed; the former archive remains in Git history.
Chris's supplied archive was already uploader-compatible; its source text and author
reference materials are preserved without edits. All extracted source hashes and the
original Chris archive hash are recorded in the manifests.

Mary's package contains 200 chronological first-person entries in two uploader-ready
files, with reflection every five entries. Her chronology was reviewed before publication;
unverified Steve encounter dates are kept as present-day reflections rather than invented history.

Tammy's original package contains 300 chronological first-person entries in three
uploader-ready files, with reflection every five entries. Her reference folder includes
the cast/canon file and two clothed visual references; the primary fireplace portrait
governs facial likeness.

Tammy is the separate long-form V3 rebuild. Its first checked-in notebook contains
100 substantially longer first-person entries, and its reference pack locks the revised
chronology, family, finances, preferences, relationships, current Charleston life, and
visual references. V3 is intended to grow past 1,000 entries; append notebooks in order
rather than mixing V2 and V3 in one fresh test.

## Existing checkpoints

Use the original input paths and `--resume --checkpoint ORIGINAL_PATH` for existing
uploader runs, rather than starting a package runner session. Standalone importer
checkpoints are not uploader checkpoints: keep them unchanged, inspect the original
run and remote room, and decide any replay range explicitly to avoid duplicates.