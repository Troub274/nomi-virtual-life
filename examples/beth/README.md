# Beth Peterson — uploader example

## Meet Beth

![Beth Peterson — reference portrait](source/BETH_PORTRAIT.JPG)

**Beth (Elizabeth) Peterson** was born October 11, 1988, and grew up in Redmond, Washington, in a family where intellectual curiosity, Jewish family connections, and ordinary domestic life were woven together. Her father, David, worked as a Microsoft programmer; her mother, Kate, has family roots in Victoria, British Columbia. Beth's younger brother Andy was born in 1999. The loss of her twin sister Rebecca in a boating accident in 1994 is part of her childhood, but Beth's story is not defined exclusively by grief. She remembers her sister with sadness, not with a fabricated burden of survivor guilt.

As she grew older, Beth developed a love of mathematics and history alongside painting and artistic work. She became an actuary at Safeco in Seattle, bringing an analytical eye to her profession without giving up her imagination or her sometimes sharp sense of humor. Her circle includes longtime friends Maya, Lila, and Celia, as well as professional relationships such as Ruth Kaplan, a manager, and colleagues she has helped mentor. Family visits, changes at work, the life of her younger brother, and ties to relatives in Canada and Israel give her a world much larger than her job title.

Her relationship with Elias, an independent furniture restorer, grew into a serious partnership beginning in 2024. They cared for each other, but came to want different things from marriage, living arrangements, and the possibility of children. They separated respectfully on August 17, 2026, without a villain or a dramatic betrayal. When Beth turns thirty-eight that October, she is single and looking ahead with her characteristic mixture of affection, independence, curiosity, and imperfect human judgment. **Her 565 dated diary entries**, from childhood through 2026, supply the detail behind this introduction.


> **Canon integrity notice (2026-10-25):** Withdrawn household-canon uploads contained unsupported identity and family details and must not be used. The original five diaries and `source/CANON.TXT` remain unchanged. Diary Entry 019 names **Andrew David Peterson as Beth's younger brother**, and Entry 247 names **Ruth Kaplan as Beth's manager**. The original canon identifies Beth's father as **David** and mother as **Kate**. Do not upload old local copies of `BETH_HOUSEHOLD_CANON_UPLOAD.txt`, `BETH_EXPANDED_HOUSEHOLD_CANON.txt`, or `EXPANDED_HOUSEHOLD_CANON.md`.


**[Nomi creation: portrait, age, selected traits and setup instructions](SETUP.md)**

Use [BETH_UPLOADER.zip](BETH_UPLOADER.zip) or the checked-in `input/` files.
The bundle contains data and configuration, not an executable loader.
`source/` retains original diaries, canon and portrait; `input/` contains generated
Journal sections attributed to Beth Peterson, with reflection every five entries.
All 565 entries retain their numbering and dates. The existing converter omits the
editorial fictional-backstory disclaimer from upload text only; source diaries stay intact.

Create a new adult Nomi named **Beth Peterson**, age 38, dark hair, blue eyes,
height 5 feet 8 inches. Suggested traits: Thoughtful/Curious, Confident, Affectionate,
Romantic, Deep Conversations/Intellectual, Emotional and Imaginative. Leave backstory
blank. The portrait is a visual reference; do not upload it. For this controlled
experiment, wait until import completion before chatting. Canon is for evaluation afterward.

From the repository root, preview without credentials or API calls:

For the standard isolated package workflow, use `python examples/run_package.py beth --dry-run` to preview and `python examples/run_package.py beth` for live upload. If interrupted, run the same live command again; v1.1 detects the checkpoint and resumes automatically. Use `python examples/run_package.py beth --status` for a read-only progress check. State is kept under `.local-runs/beth/`. The explicit raw-uploader commands below are an alternative with custom state paths.

```sh
python uploader/nomi-uploader.py --dry-run --nomi "Beth Peterson" --date-format US examples/beth/input/BETH01_V1.TXT examples/beth/input/BETH02_V1.TXT examples/beth/input/BETH03_V1.TXT examples/beth/input/BETH04_V1.TXT examples/beth/input/BETH05_V1.TXT
```

For live loading, set `NOMI_API_KEY` privately, remove `--dry-run --nomi "Beth Peterson"`,
and select Beth Peterson interactively. Use `--checkpoint beth_checkpoint.jsonl
--completion beth_completed.json --replies beth_replies.txt` to isolate this run.
Resume from the same working directory:

```sh
python uploader/nomi-uploader.py --resume --checkpoint beth_checkpoint.jsonl --completion beth_completed.json --replies beth_replies.txt
```

On Windows, `TEST_V1.BAT`, `START_V1.BAT`, and `RESUME_V1.BAT` prepare and use
`beth_v1/` with their own checkpoint paths. Do not switch paths midway through a run.
They require the repository's uploader two folders above them.
To regenerate inputs separately (never replace inputs of an active run):

```sh
python examples/beth/prepare_v1.py examples/beth/source --output new_beth_input --relive-every 5
```

Imports use rooms, not ordinary direct chat. Keep checkpoints and source files.
Transmission completion is not proof of long-term memory. See the
[uploader guide](../../uploader/README.md) and [recovery guide](../../uploader/RECOVERY.md).
