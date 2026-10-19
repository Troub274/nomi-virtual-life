# Uploader example packages

[Beth](beth/README.md) has 565 entries; [Chris / Christine](chris/README.md) has 1,000.
Both include data-only ZIPs, ordered input lists and the current uploader configuration.

From the repository root, preview either package:

```sh
python examples/run_package.py beth --dry-run
python examples/run_package.py chris --dry-run
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

## Existing checkpoints

Use the original input paths and `--resume --checkpoint ORIGINAL_PATH` for existing
uploader runs, rather than starting a package runner session. Standalone importer
checkpoints are not uploader checkpoints: keep them unchanged, inspect the original
run and remote room, and decide any replay range explicitly to avoid duplicates.
