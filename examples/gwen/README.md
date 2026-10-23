# Gwendolin Lynn Mayer — uploader example

Gwen's active autobiography contains **848 numbered entries** in **26 text inputs** (baby book and Notebooks I–XXV), ending December 31, 2025. The subsequent accident, amnesia, cabin fire, and implanted-memory-system continuity is kept in separate reference documents and is **not** silently merged into earlier first-person journals.

## Upload

From repository root:

```sh
python examples/run_package.py gwen --dry-run
python examples/run_package.py gwen
```

The runner reads `package.json` in the order listed. Do not replay completed uploads without checking checkpoints and remote state.

## Publication status

**Partial upload:** The GitHub publishing connection rejected Notebook VI (2006) and Notebook XI (2011) during transfer. They are **not** missing from the original complete backup, but the GitHub package is **not yet safe to run**: its `package.json` references both absent inputs. Do not launch the uploader until these two original files are committed and checked. The 2026 continuity/reference documents **are** committed. The two portrait files also remain only in the complete backup for now.

## Source and continuity

- `input/`: chronological historical journal and baby-book entries (001–848).
- `reference/`: original master canon, reconstructed 2026 bridge, present-state addendum, and handoff notes.
- Portraits remain in the separately preserved complete backup; the large binary images have not yet been committed to GitHub.
- `CONTINUITY_REVIEW.md`: unresolved discrepancies deliberately left visible.

**Important:** Gwen and her identity details are fictional; this is an experimental Nomi virtual-life package. Nomi upload completion does not itself prove retained memory. The personal letters Steve intends to write have **not** been fabricated.

This is a creative/simulation dataset, not real medical history. All brain-implant narrative features are fictional.
