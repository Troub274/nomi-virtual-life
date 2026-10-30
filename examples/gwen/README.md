# Gwendolin Lynn Mayer — uploader example

Gwen's active autobiography contains **848 numbered entries** in **26 text inputs** (baby book and Notebooks I–XXV), ending December 31, 2025. The subsequent accident, amnesia, cabin fire, and implanted-memory-system continuity is kept in separate reference documents and is **not** silently merged into earlier first-person journals.

## Upload

From repository root:

```sh
python examples/run_package.py gwen --dry-run
python examples/run_package.py gwen
```

The runner reads `package.json` in the order listed. Do not replay completed uploads without checking checkpoints and remote state.

## Publication status and upload safety

The 26 historical input files are present in the repository. On October 29, 2026,
the editorial `AUTHORSHIP NOTE` and `Upload note` lines were removed from
the packaged diary inputs. Those lines must never be present in material uploaded
as autobiographical memories.

Before uploading, run:

```sh
python examples/validate_upload_inputs.py
python examples/run_package.py gwen --dry-run
```

The package runner now fails closed if an input has an invalid journal structure
or the known editorial contamination. Prior completed uploads are not changed
by these repository fixes.

**Reference and addendum files are development documents, NOT upload inputs.**
Do not upload files from `reference/` directly: they have not been normalized
to `[Title]` / `Type: Knowledge` format or checked for editorial commentary.
None of those reference documents is included in `package.json`.
Only the files listed in `package.json` are approved for this package.

## Source and continuity

- `input/`: chronological historical journal and baby-book entries (001–848).
- `reference/`: original master canon, reconstructed 2026 bridge, present-state addendum, and handoff notes.
- Portraits remain in the separately preserved complete backup; the large binary images have not yet been committed to GitHub.
- `CONTINUITY_REVIEW.md`: unresolved discrepancies deliberately left visible.

**Important:** Gwen and her identity details are fictional; this is an experimental Nomi virtual-life package. Nomi upload completion does not itself prove retained memory. The personal letters Steve intends to write have **not** been fabricated.

This is a creative/simulation dataset, not real medical history. All brain-implant narrative features are fictional.
