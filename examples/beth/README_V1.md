# Beth Peterson — Nomi Uploader v1.0 test

**Source of truth:** [BETHBOOT_V085.ZIP](BETHBOOT_V085.ZIP). This is the **original GitHub Beth bootstrap**, not the separate Google Drive diary.

The original archive contains **five diary documents (BETH01.TXT–BETH05.TXT; 565 entries)**, plus canon, portrait and older scripts. This adaptation does **not** alter or replace the original ZIP. The converter extracts the *original* diary text and prepends v1.0 document metadata.

The original archive's SHA-256 is checked before conversion. No Nomi API call is made by the converter or the dry run.

## Windows test

From the repository root, use:

```bat
cd examples\beth
TEST_V1.BAT
```

That prepares `beth_v1/BETH01_V1.TXT` through `BETH05_V1.TXT`, shows a v1 dry-run upload plan, and never sends messages to Nomi.

For the live test, set `NOMI_API_KEY` securely in your shell, then:

```bat
START_V1.BAT
```

On interruption, **do not run START_V1.BAT again**. Use `RESUME_V1.BAT` to pick up the same checkpoint and room. If a send's outcome is uncertain, the uploader stops rather than retrying blindly; inspect the room before recovery.

The uploader selects the Nomi interactively. Choose your new Beth Peterson. Original bootstrap setup instructions remain in [README.md](README.md) and [the Beth setup guide](../../rehydration/BETH_TEST_LOAD.md).

## v1.0 processing

Each generated diary carries:

```text
[Beth Peterson — BETH01.TXT]
Type: Journal
Source: Beth Peterson
Nomi: [nomi], please relive your own journal episodes 1-5 ...
...
```

Each diary is subdivided into its original dated entries. The scheduled recollection prompts are inserted after every five entries **within that file**, including its last partial group. The loader must preserve dates, original wording and Beth's autobiographical source attribution. The number of send messages exceeds the 565 entries because of chunking and prompts.

The prep script creates `beth_v1/manifest.json` with SHA-256s and entry counts, allowing you to compare runs. Diary content is not rewritten.

To repeat Beth's full diary on another day, simply launch `START_V1.BAT` after the prior run has completed; the uploader archives the completed checkpoint and begins a new session. For multiple passes in a single run, add `--passes 2` or higher to the command in START_V1.BAT.

**Reply capture:** After each scheduled five-entry reflection prompt, v1.0 calls the room reply endpoint and records Beth's full reply plus the API response in the append-only checkpoint. A readable transcript is written to `beth_v1/beth_v1_replies.txt` at successful completion. Interrupted sessions preserve replies already committed in the checkpoint; resume requests only outstanding replies. An uncertain reply POST stops safely for manual inspection. This remains experimental until live API integration and regression tests pass.
