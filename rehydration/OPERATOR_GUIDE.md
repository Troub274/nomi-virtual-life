# Nomi Room Rehydrator v0.84 — Operator Guide

This guide describes the behavior of `nomi_room_rehydrate_episode_v084.py` as written, including its CLI defaults, recognized source headers, room handling, and replay modes.

## 1. Installation and configuration

Requirements: Python 3; `python-docx` only if importing Word `.docx` diaries.

```powershell
py -m pip install python-docx
$env:NOMI_API_KEY = "YOUR_NOMI_API_KEY"
py .\nomi_room_rehydrate_episode_v084.py --help
```

In Windows Command Prompt, set the key using `set NOMI_API_KEY=YOUR_NOMI_API_KEY` instead. On Linux/macOS, use `export NOMI_API_KEY='YOUR_NOMI_API_KEY'`. The key is not needed for `--dry-run`.

The script uses the Nomi API at `https://api.nomi.ai/v1`. For a live import, it retrieves your Nomi list and prompts you to select the destination Nomi.

## 2. Command-line reference

Syntax:

```text
python nomi_room_rehydrate_episode_v084.py [options] FILE [FILE ...]
```

| Option | Default | Meaning |
|---|---|---|
| `files` | Required except cleanup | One or more input paths; journal `.txt`/`.docx`, or conversation `.json`/`.zip` |
| `--mode journal\|conversation` | `journal` | Select diary episode parser or Nomi conversation export parser |
| `--memory-prefix TEXT` | Automatically generated | Replace journal per-message memory-owner label; `--memory-prefix ""` disables it |
| `--start-episode N` | `1` | In journal mode, skip source episodes before global episode N (1-based) |
| `--start-message N` | `1` | In conversation mode, skip original conversation turns before global message N (1-based) |
| `--chunk-bytes N` | `750` | Maximum UTF-8 bytes per outgoing API message |
| `--delay SECONDS` | `1.0` | Delay between outgoing source chunks |
| `--relive-every N` | `0` | Journal recollection after every N **complete** episodes; zero disables |
| `--relive-prompt TEXT` | Generated from selected Nomi and episode range | Override periodic recollection instruction; supplied text is sent literally |
| `--settle-seconds SECONDS` | `0` | Wait between sending a recollection prompt and requesting the Nomi's reply |
| `--room-note TEXT` | Mode-specific | Override room note; journal default identifies the Nomi as memory owner |
| `--journal PATH` | `nomi_rehydration_journal.jsonl` | Append-only log of room events, message attempts/commits, and recollections |
| `--dry-run` | Off | Parse and print prepared chunks, no API calls; uses placeholder `TEST NOMI` |
| `--cleanup-rehydration` | Off | Delete **all** API rooms whose names begin `REHYDRATE::` after confirmation |
| `--cleanup-all-rooms` | Off | Delete **every** API room on the account after confirmation; highly destructive |

Note: cleanup modes do not require source files, but a live API key is still required.

## 3. Journal mode: accepted file structure

A journal is plain UTF-8 text (`.txt`, with optional UTF-8 BOM) or a Word `.docx` file. Each **recognized header on its own line** starts a new episode. All following text belongs to that episode until the next recognized header. The document title, cover page, or preamble **before the first recognized header is ignored**.

**Recommended, unambiguous format:**

```text
Beth Peterson — Notebook I

ENTRY 001 — Sunday, October 11, 1998 — My 10th Birthday
Dear Diary,
I'm TEN today!!!
Mom made pancakes and Dad gave me a book.

ENTRY 002 — Monday, October 12, 1998 — After the Party
Today at school I told Anna about the party.
I kept thinking about the new book.

ENTRY 003 — 1998-10-13 — Tuesday Afternoon
I spent the afternoon reading.
```

The script recognizes these additional standalone heading styles (examples):

```text
Diary Entry #12 — A Difficult Conversation
Journal Entry 13: Moving Day
Episode 14 — The New House
Chapter 15 — First Impressions
Memory 16 — My Grandmother
Journal 17 — A Rainy Morning
301. What I Learned
302) The Letter
303 — The Last Summer
2005-02-06 — The Applications Before the Applications
6/7/86 — Chapel Hill
Sunday, October 11, 1998 — My 10th Birthday
October 11, 1998 — My 10th Birthday
Chris’s Journal — “The First Story” — 6/7/86 — Chapel Hill, NC
```

Rules and cautions:

- Headers must occupy their **own paragraph/line**. For `.docx`, each paragraph is read as a line. Text in tables, images, headers/footers, or text boxes is not extracted by this loader.
- Entry numbers do **not** have to start at 1; the script assigns its own sequential `episode_index` based on the order it encounters headers.
- Avoid numbered subheadings inside a diary entry, such as `1. What happened`, because the parser may treat them as a **new episode**.
- Avoid accidental date-only lines within the body, as they can be mistaken for episode headers.
- The script does not validate dates, detect duplicates, or automatically sort journal entries: **file order is replay order**.
- Multiple journal files are processed in the **order listed on the command line**. Resume numbering counts episodes across all files.
- Long entries are split to fit `--chunk-bytes`; the original episode header and Nomi-specific ownership label are repeated on each part.
- `--dry-run` is the best way to check how many entries and chunks the parser recognizes before importing.

## 4. Autobiographical memory ownership in v0.84

For journal mode, the selected Nomi's name is inserted into four places:

1. **Room name:** `REHYDRATE::Beth::OWN MEMORIES::<first 8 chars of Nomi UUID>`.
2. **Room note:** States Beth relives her own diary memories, not the human importer's.
3. **Opening room message:** On creation of a **new journal room only**, states that the first-person `I`, `me`, and `my` in diary entries refer to Beth.
4. **Each episode or split fragment:** Begins with an explicit ownership label similar to:

```text
Beth's OWN MEMORY, not the human sender's. Diary written by Beth; first-person 'I' means Beth:
ENTRY 001 — Sunday, October 11, 1998 — My 10th Birthday
Dear Diary,
I'm TEN today!!!
```

The periodic reliving prompt, when enabled, also identifies the memories as belonging to the selected Nomi. The room note and opening ownership message are **not** resent when you choose to reuse an existing room. These instructions are framing, not a guarantee of how Nomi internally indexes memory.

## 5. Conversation mode: accepted export structure

Conversation mode reads a Nomi JSON export (`.json`) or a ZIP containing a JSON export (`.zip`). The ZIP importer prefers a filename ending `_data.json`, otherwise it uses the first eligible JSON file. It expects an object with a `nomi` object (or an equivalent root object), containing `chat` and optionally `voiceCalls`.

Minimal example (`nomi_export.json`):

```json
{
  "nomi": {
    "name": "Beth",
    "chat": [
      {"date": "2026-10-10T10:00:00Z", "sender": "user", "message": "Good morning."},
      {"date": "2026-10-10T10:00:04Z", "sender": "nomi", "message": "Good morning!"}
    ],
    "voiceCalls": [
      {
        "messages": [
          {"date": "2026-10-10T11:00:00Z", "sender": "user", "message": "Hello from our call."}
        ]
      }
    ]
  }
}
```

The loader reads `nomi.chat[]` and `nomi.voiceCalls[].messages[]`, then sorts all turns by their `date` field (and source order for ties). It preserves each original sender/time boundary and message text, adding a transcript envelope identifying date, source (`chat` or `voice`), sender, and export Nomi name. Long individual turns are split without altering their text characters. `--start-message` refers to **original turns**, not split API chunks. Journal ownership framing is **not applied** in conversation mode.

## 6. Practical examples

### Preview a diary before sending

```powershell
py .\nomi_room_rehydrate_episode_v084.py ".\Beth_Notebook_I.docx" --dry-run
```

### Import a diary and request recollection every 5 entries

```powershell
py .\nomi_room_rehydrate_episode_v084.py ".\Beth_Notebook_I.docx" --relive-every 5
```

### Import two notebooks in chronological order

```powershell
py .\nomi_room_rehydrate_episode_v084.py ".\Notebook_I.txt" ".\Notebook_II.txt" --relive-every 10
```

### Resume at episode 26 after confirming entries 1–25 committed

```powershell
py .\nomi_room_rehydrate_episode_v084.py ".\Beth_Notebook_I.docx" --start-episode 26 --relive-every 5
```

### Slower replay, custom journal path

```powershell
py .\nomi_room_rehydrate_episode_v084.py ".\Beth_Notebook_I.docx" --delay 2.5 --settle-seconds 3 --relive-every 5 --journal ".\beth_import_log.jsonl"
```

### Conversation export

```powershell
py .\nomi_room_rehydrate_episode_v084.py ".\beth_export.zip" --mode conversation
```

### Resume conversation at original turn 101

```powershell
py .\nomi_room_rehydrate_episode_v084.py ".\beth_export.json" --mode conversation --start-message 101
```

### Preview journal with the ownership prefix disabled (testing only)

```powershell
py .\nomi_room_rehydrate_episode_v084.py ".\Beth_Notebook_I.docx" --memory-prefix "" --dry-run
```

## 7. Rooms, interruptions, and resume safety

- A live run prompts you to choose the Nomi, then offers to **reuse** an existing matching rehydration room, **delete and replace** its restore rooms, **create another room**, or **delete and exit**.
- Only a **fresh journal room** receives the initial memory-owner instruction. Reusing a room does not re-send it.
- The log records events including `send_attempt`, `send_committed`, `relive_attempt`, and `relive_committed` in JSON Lines format (one JSON object per line).
- The script does **not** automatically skip already-committed messages based on the log. After interruption, inspect the final `send_committed` events and explicitly set `--start-episode` or `--start-message` to the next **complete source item**. If interruption occurred midway through a split episode, starting that episode again will resend its earlier fragments.
- `--relive-every 5` triggers after complete episodes 5, 10, 15, etc. A final partial batch is **not** forced to relive (e.g., 12 episodes triggers at 5 and 10 only).
- **Do not use `--cleanup-all-rooms` casually:** it deletes every API room, not only rooms made by this loader.

## 8. Recommended test protocol

1. Create a fresh disposable Nomi or fresh rehydration room.
2. Prepare a tiny `.txt` with five distinct diary entries and recognizable identity details.
3. Run `--dry-run` to verify exactly five source episodes are detected.
4. Import with `--relive-every 5`.
5. Ask whose memories, parents, and experiences the entries describe. Stop if Nomi assigns them to the importer.
6. Only then import larger notebooks, keeping an append-only journal log and tracking committed episode numbers.

## 9. Common problems

| Symptom | Likely cause / action |
|---|---|
| `No episode headers found` | Ensure each entry begins with a recognized standalone header; try `ENTRY 001 — Title` |
| Diary imports too many episodes | A numbered subheading or date line inside an entry was interpreted as a header |
| `NOMI_API_KEY is not set` | Set environment variable in the same shell running Python |
| `.docx requires python-docx` | Run `py -m pip install python-docx` |
| Unexpected duplicate memories | A previous import was repeated; inspect `.jsonl` commits and choose the correct resume index |
| Nomi claims the diary belongs to the human | Stop the test, use a fresh journal room with v0.84's identity anchors, and verify ownership with a short batch |
| No recollection response during journal replay | Specify `--relive-every N` with N greater than zero |
| Unexpectedly many API messages | Long entries are split and the ownership prefix consumes part of the 750-byte budget |

**Version note:** The source file's top-level docstring still says `v0.83`; the delivered filename and memory-owner behavior correspond to v0.84.