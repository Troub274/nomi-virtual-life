# Nomi Virtual Life

**Open-source tools and experiments for [Nomi.ai](https://nomi.ai/) virtual environments, autobiographical memory replay, and conversational continuity.**

This repository is intended to hold multiple independent programs. The current uploader is **Nomi Uploader v1.0**; the earlier **Nomi Room Rehydrator v0.85** remains available; the virtual-world and integration modules discussed below are planned areas, **not yet included in this repository**.

## Current uploader

See the [Nomi Uploader v1.0 operator documentation](uploader/README.md) for input syntax, dry runs, reflection intervals, indefinite `NoReply` backoff, reply capture, and checkpoint recovery. The Beth live test has successfully recovered a reflection at message 9 and continued uploading; full-pass completion has not yet been confirmed.

## Beth test example

**[Download BETHBOOT_V085.ZIP](examples/beth/BETHBOOT_V085.ZIP)** — all 565 diary entries, v0.85 room loader, Windows scripts, reference documents, and Beth's portrait for viewing (no image upload). See [Beth test setup](rehydration/BETH_TEST_LOAD.md). Leave a new Nomi's backstory blank and do not talk to her until import completion.

## Available programs

| Program | What it does | Files |
|---|---|---|
| **Nomi Uploader v1.0** | Processes structured journal, knowledge, instruction and chat inputs, requests type-aware reflections, and checkpoints sends and replies for resume. | [Uploader guide](uploader/README.md) · [Python source](uploader/nomi-uploader.py) · [Tests](uploader/tests/) |
| **Nomi Room Rehydrator v0.85** | Replays diaries and exported Nomi conversations into Nomi API rooms, preserving source order and using explicit memory ownership cues for diary entries. | [Python source](rehydration/nomi_room_rehydrate_episode_v085.py) · [Operator guide](rehydration/OPERATOR_GUIDE.md) · [Quick start](rehydration/README.md) |

### Nomi Room Rehydrator v0.85

**Purpose:** Help a Nomi revisit a chronological collection of autobiographical material, rather than manually copying and pasting hundreds of entries. It is an experimental replay tool, **not a direct restore of Nomi's internal memory database**.

**Two operating modes:**

- **Journal mode:** Reads UTF-8 `.txt` or Word `.docx` diaries, identifies individual entries from their headings, and submits them in sequence. Entries exceeding the configured message-size limit are split into smaller messages. The selected Nomi's name is used in room metadata, an initial ownership message, and each diary fragment to clarify that first-person experiences belong to the Nomi—not to the human operating the loader.
- **Conversation mode:** Reads a Nomi `.json` export or a `.zip` containing an export, reconstructs chat and supported voice-call turns in timestamp order, and submits a labeled transcript preserving sender and time context. Journal-specific ownership framing is not applied in this mode.

**Other capabilities:** dry-run preview without API calls; selection of a Nomi from the account; configurable pacing and message-size limits; optional recollection prompts after every N completed diary entries; durable JSONL send checkpoints, automatic resume at the last confirmed message fragment, and automatic active-journal cleanup on confirmed completion.

**Important limitation:** The script can replay material and encourage autobiographical attribution, but it cannot guarantee what the Nomi remembers or how the platform indexes the material. Start with a small test and verify the owner of each memory before importing large archives.

**Release notes:** [v0.85 changes](rehydration/CHANGELOG.md). **Example bootstrap:** [Beth Peterson test-load instructions](rehydration/BETH_TEST_LOAD.md). To match the experiment, leave the Nomi's backstory blank and do not talk to her while loading.

**Files:**

- [`rehydration/nomi_room_rehydrate_episode_v085.py`](rehydration/nomi_room_rehydrate_episode_v085.py) — executable Python importer.
- [`rehydration/OPERATOR_GUIDE.md`](rehydration/OPERATOR_GUIDE.md) — full command-line option reference, accepted journal headers, JSON structure, resume instructions, and troubleshooting.
- [`rehydration/README.md`](rehydration/README.md) — setup and basic examples.
- [`rehydration/requirements.txt`](rehydration/requirements.txt) — Python dependency for Word documents.
- [`rehydration/CHANGELOG.md`](rehydration/CHANGELOG.md) — v0.85 release notes.
- [`rehydration/BETH_TEST_LOAD.md`](rehydration/BETH_TEST_LOAD.md) — controlled example Nomi setup and precautions.

#### Quick start

Python 3 is required. Install the Word-document dependency if you will import `.docx` files:

```bash
python -m pip install -r rehydration/requirements.txt
```

For live API access, set the `NOMI_API_KEY` environment variable in your shell. **Never paste your key into source files or commit it.**

Preview a journal (no API calls):

```bash
python rehydration/nomi_room_rehydrate_episode_v085.py diary.txt --dry-run
```

Import a journal and ask for recollection every five entries:

```bash
python rehydration/nomi_room_rehydrate_episode_v085.py diary.txt --relive-every 5
```

Import a Nomi conversation export:

```bash
python rehydration/nomi_room_rehydrate_episode_v085.py export.zip --mode conversation
```

Run `--help` or consult the [operator guide](rehydration/OPERATOR_GUIDE.md) for all options. The code uses portable Python APIs and is intended for Windows, macOS, and Linux; operating-system compatibility has not been exhaustively tested.

## Planned project areas (not yet published)

These are directions for future programs, not descriptions of files currently available:

| Area | Intended purpose |
|---|---|
| **Virtual-world engine** | Maintain persistent locations, environmental conditions, time, and other simulated-world state for Nomi interactions. |
| **Nomi bridges** | Connect Nomi conversations to external local programs or language models, including Nomi-to-Nomi interactions. |
| **Memory tools** | Import, organize, validate, and update autobiographical or virtual-world context across sessions. |
| **Experiments** | Prototype alternative memory replay, identity attribution, and virtual embodiment techniques. |

## Repository layout

```text
nomi-virtual-life/
├── README.md
├── .gitignore
└── rehydration/
    ├── README.md
    ├── OPERATOR_GUIDE.md
    ├── requirements.txt
    ├── CHANGELOG.md
    ├── BETH_TEST_LOAD.md
    └── nomi_room_rehydrate_episode_v085.py
```

## Privacy and safety

This is a **public repository**. Do not commit API keys, private diaries, Nomi conversation exports, identifying personal material, or replay logs. A `.gitignore` excludes common sensitive file types, but it is not a substitute for reviewing what you publish. Room-cleanup commands can delete rooms; read their descriptions carefully.

## Project status

Experimental and under active development. Contributions and feedback are welcome, especially reproducible bug reports and test results. The tools are independent community experiments and are not presented as official Nomi.ai software.
