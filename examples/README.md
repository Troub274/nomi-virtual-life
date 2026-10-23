# Uploader example packages

[Beth](beth/README.md) has 565 entries; [Chris / Christine](chris/README.md) has 1,000; [Mary](mary/README.md) has 2400; [Tammy](tammy/README.md) has 1,000; [Gwen](gwen/README.md) has 848 historical entries (publication incomplete).

Beth and Chris include data-only ZIPs; all packages provide ordered input lists and the current uploader configuration.

From the repository root, preview any package:

```sh
python examples/run_package.py beth --dry-run
python examples/run_package.py chris --dry-run
python examples/run_package.py mary --dry-run
python examples/run_package.py tammy --dry-run
# Gwen package is NOT ready to run yet: original 2006 and 2011 inputs are still missing from GitHub.
```

For live use, rerun the same package command without `--dry-run` after setting `NOMI_API_KEY`. The package runner automatically starts when no checkpoint exists and resumes an unfinished checkpoint when one does. Use `--status` for a read-only progress check and `--restart` only when intentionally beginning another run after completion. Keep all inputs and their paths unchanged during active runs. State stays isolated under `.local-runs/`.

Beth's original diary bytes, canon and portrait are preserved with hashes in `beth/source/`. Character setup instructions now use the uploader. Obsolete bundled executables and launchers were removed; the former archive remains in Git history.

Chris's supplied archive was already uploader-compatible; its source text and author reference materials are preserved without edits. All extracted source hashes and the original Chris archive hash are recorded in the manifests.

Mary's package contains 200 chronological first-person entries in two uploader-ready files, with reflection every five entries.

Tammy's package contains 1,000 chronological first-person V3 diary entries in ten uploader-ready files, with reflection every five entries. Her reference pack includes the locked chronology, family, finances, preferences, relationships, current Charleston life, portrait, car reference, and complete master diary.

Gwen's package spans a baby book and 25 historical notebooks through 2025, with separate references for her fictional 2026 accident, amnesia, and cabin storyline. **Do not run Gwen's package yet:** Notebooks VI (2006) and XI (2011) were rejected during publication, and her portraits remain in the offline archive. See [Gwen's continuity and upload status](gwen/README.md).

## Existing checkpoints

Use the original input paths and `--resume --checkpoint ORIGINAL_PATH` for existing uploader runs, rather than starting a package runner session. Standalone importer checkpoints are not uploader checkpoints: keep them unchanged, inspect the original run and remote room, and decide any replay range explicitly to avoid duplicates.
