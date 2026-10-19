# Nomi Uploader v1.0

**Current:** Nomi Uploader 1.0. `legacy_v085.py` is an internal compatibility dependency for API access and export parsing; use `nomi-uploader.py` for all operations.

Requires Python 3.10+; optional `python-docx` for DOCX. Set `NOMI_API_KEY` before live uploads.

```bash
python uploader/nomi-uploader.py --dry-run --nomi Beth uploader/example.txt
python uploader/nomi-uploader.py uploader/example.txt
python uploader/nomi-uploader.py --passes 3 uploader/example.txt
python uploader/nomi-uploader.py --resume
python uploader/nomi-uploader.py --utility
python3 -m unittest discover -s uploader/tests -p "test_*.py" -v
```

Each new invocation creates a fresh upload run; repeated documents are intentional. `--resume` continues a specific checkpoint. To begin a new run after completion, use a new checkpoint path (e.g. `--checkpoint second_run.jsonl`), or archive the previous checkpoint. This distinction prevents accidental duplicate sends during recovery.

## Input

```text
[Physics]
Type: Knowledge
Source: Research
Nomi: Summarize entries 1-2.

Gravity curves spacetime.

[Preferences]
Type: Instructions
Source: Yehoshua
Date: July 20

Do not call Yehoshua Captain.

[Childhood]
Type: Journal
Source: Beth

ENTRY 001 — October 11, 1998
I turned ten today.

[Conversation]
Type: Chat
Date: 10/13/2026

Yehoshua: Good morning.
Beth: Morning!
```

Type defaults to Knowledge; source defaults to System except Journal (selected Nomi). Date required for Journal and text Chat; optional for Knowledge and Instructions. ISO and written dates accepted. Numeric dates follow OS locale unless `--date-format US|EU` overrides. Omitted years use the run's year; two-digit years use 70–99 => 1970–1999 and 00–69 => 2000–2069.

`Nomi:` instructions are additive by default; `Nomi Mode: Replace` suppresses the type-specific default. Range prompts like `entries 1-24` execute after entry 24. Nomi JSON/ZIP exports use the internal compatibility export parser.

Rooms persist after upload. `--utility` lists and explicitly deletes selected rooms; no automatic deletion.

### Room reuse and deletion (v1.0)

For a new upload, the uploader finds existing rooms for the chosen Nomi (using the Nomi UUID) and offers **reuse as choice 1 (the default)**, using existing Nomi room membership. Select another room by number, or explicitly choose to create a new room. `--room UUID` directly reuses a verified room; `--resume` keeps the room and manifest from the original checkpoint. Rooms associated with checkpoints in the selected checkpoint directory are excluded from automatic reuse.

In `--utility`, enter a room number or `ALL`. The room manager shows the exact eligible rooms, excludes rooms protected by checkpoints in the selected directory, and asks **once**: `Delete these N room(s)? [y/N]`. `y`, `Y`, or `yes` (any capitalization) confirms; anything else cancels. No `DELETE N` or per-room UUID entry is required. Room deletion is permanent, so examine the filtered list and use the appropriate checkpoint directory.
 Completion confirms API transmission, **not** long-term memory consolidation.

**Caution:** This remains an experimental v1.0 implementation. Live Nomi API sending, reply capture, and checkpoint recovery have been observed with Beth; a complete 765-message pass and durable memory retention have not been confirmed. Validate dry runs and use a test Nomi before production.

## Type-aware processing and response capture

Use `--process-every N` to ask for an analysis or recollection after every N complete units. A section's `Process Every: N` **overrides** the command-line `--process-every N` default; `0` disables automatic processing for that section. A trailing partial group is also processed. Knowledge and Instructions are grouped by nonempty paragraphs, Journal by dated entries, and Chat by dated conversation episodes. The instruction varies with the type and source: personal journals are autobiographical, third-party journals remain attributed to their authors, conversations preserve speaker attribution, knowledge is summarized, and instructions are reviewed for application.

```text
[My diary]
Type: Journal
Source: Beth
Process Every: 5

ENTRY 001 — October 11, 1998
Today I turned ten.

[Reference facts]
Type: Knowledge
Source: System
Process Every: 10

First fact.

Second fact.
```

Custom `Nomi:` prompts remain independent of the automatic interval and can be scheduled with `episodes 1-5` / `entries 1-5`. `Nomi Mode: Replace` suppresses the default introductory prompt, not explicit periodic processing; use `Process Every: 0` to suppress the latter.

Every processing prompt triggers a separate `/rooms/{room}/chat/request` call. Successful responses are recorded in the append-only checkpoint with the full API payload. At completion, `--replies` (default `nomi_uploader_replies.txt`) receives a readable transcript. A send or reply request with an uncertain outcome halts without retrying the POST. On resume, completed prompt replies are not requested again.

**Release status:** Partial live Nomi API integration has been verified through Beth's test upload and recovery. The full-pass result remains pending; do not treat transmission as guaranteed long-term memory retention.

## Interactive operation and room management

Running `python uploader/nomi-uploader.py` in an interactive terminal now opens a text menu for upload, resume, dry-run and room management. `--utility` opens the room manager directly. The manager can list all rooms, filter by Nomi, filter abandoned/inactive/failed statuses, inspect individual rooms and delete one or many with explicit confirmation and one confirmation of the displayed deletion list. Incomplete upload checkpoints found in the selected checkpoint directory protect their rooms from deletion. **Protection is directory-scoped:** keep all checkpoint files in that directory and do not use bulk deletion with checkpoints stored elsewhere.

JSON/ZIP Nomi exports now receive Chat introductory and periodic processing prompts as well as the internal compatibility conversation turn parsing. Automatic room creation uses a single POST rather than retrying uncertain creation requests.

### Remaining release gates

The implementation remains experimental. Run the offline suite using the command below. Full-pass live verification and durable memory retention remain separate release checks.


### Recover an uncertain content POST (`--retry-uncertain-send`)

Use this option **only** when `--resume` reports an attempted but unconfirmed **content message**. In the October 15 Christine upload (1,865 planned API messages), message 1,065 returned HTTP 502 `Bad Gateway`, and plain resume correctly stopped with:

```text
ERROR: Uncertain send/reply request(s) [(1, 1065)].
```

The operator accepted the possibility of a duplicate and ran, from the repository root:

```bash
git pull --ff-only origin main
python3 uploader/nomi-uploader.py --resume --retry-uncertain-send 1:1065
```

The uploader printed `Authorized resend: pass 1 message 1065 (duplicate possible)`, then confirmed messages 1065, 1066, and onward. Previously confirmed messages 1–1064 were **not** replayed.

**Option:** `--retry-uncertain-send PASS:INDEX` must be used with `--resume`. Supply the exact pair from the error; it is a **pass number and planned API-message index**, not a diary-entry number. The checkpoint must contain an `attempt` without a `confirmed` for that index. The uploader writes `send_retry_authorized`, repeats that one POST and continues normally. Because the original POST may have reached Nomi despite the 502, this **may duplicate the remote message**. Each later uncertain message needs separate operator approval. Already confirmed or never-attempted indices are rejected.

Use the **same original checkpoint and unchanged TXT files**. For a custom checkpoint, add `--checkpoint PATH`. Resume restores filenames, room, Nomi, chunk size, and planning options from its saved manifest; don't start a fresh upload or edit the JSONL. For the next ordinary interruption after successful recovery, use just `--resume` (plus the custom checkpoint path, if any).

**Do not confuse content retries with reflection-reply retries:**

| Problem | Command |
| --- | --- |
| Ordinary interruption, no uncertain request | `--resume` |
| Unconfirmed diary/content POST, duplicate acceptable | `--resume --retry-uncertain-send PASS:INDEX` |
| Confirmed reflection prompt, known old `NoReply` | `--resume --recover-noreply PASS:INDEX` |
| Confirmed reflection prompt, recorded ambiguous reply request | `--resume --recover-uncertain-reply PASS:INDEX` (after investigation; duplicate reply possible) |

For safe diagnosis, checkpoint evidence, and the real recovery transcript, see [RECOVERY.md](RECOVERY.md).

## Live operation and recovery (October 2026)

**Behavior:** The uploader sends document chunks in order. After every `Process Every: N` complete entries (not messages), it sends the reflection prompt and **waits for Nomi's reply before uploading more**. One entry may occupy several messages because of the `--chunk-bytes` limit. The final partial group is processed too.

When the API explicitly returns `NoReply`, `RoomNomiNotReadyForMessage`, `RoomStillCreating`, or `TooManyRequests`, the reply request is repeated with exponential backoff: **1, 2, 4, 8, 16, then 30 seconds, capped at 30 seconds thereafter, until a reply arrives**. Each API error, attempt number and upcoming delay is printed to stderr. The successful reply is printed in abbreviated form (first 300 characters) and stored in full in the append-only JSONL checkpoint. The human-readable `nomi_uploader_replies.txt` file is built **at completion**, not continuously. Individual backoff attempts are **not yet written** to the checkpoint, only shown in the terminal.

**Safety:** Successful document sends are checkpointed and are not resent on resume. Ambiguous reply failures (transport timeout, unexpected HTTP errors, malformed successful response) stop the upload rather than automatically repeating a possibly successful POST. `NoReply` is an explicit absence of a returned response; it does not prove the model completed internal processing. Waiting for a returned response is the uploader's configured synchronization rule.

**Recovering an older interrupted `NoReply` run:** If the checkpoint contains a `reply_attempt` without a result, and the operator **knows from the original terminal output** that the failure was explicitly `NoReply`, resume with:

```bash
python3 uploader/nomi-uploader.py --resume --recover-noreply 1:9
```

Replace `1:9` with the affected `PASS:INDEX`. This authorizes retrying that reply request without resending the confirmed prompt. **Never use this override for an uncertain network failure.** A normal interruption after a confirmed reply needs only `--resume`.

**Beth live test:** A live run with an existing Beth Nomi and five converted diary volumes reported 765 planned messages. At message 9, the reflection prompt for entries 1–5 was confirmed, but the API returned `NoReply`. Explicit recovery received Beth's reflection and the uploader continued from message 10. This establishes a successful partial live recovery, **not** completion of the full pass or guaranteed durable Nomi memory.

**Tests:** Run the offline unit and mocked integration suite from the repository root:

```bash
python3 -m unittest discover -s uploader/tests -p "test_*.py" -v
```

**Known limitations:** The public API routes exercised here provide room metadata but not a verified room chat-history GET endpoint. Retain the checkpoint as the local send/reply audit record. A durable per-retry event log, long-running reply timeout controls, and full-pass live verification remain future improvements.

**Checkpoint recovery for recorded readiness errors:** When an earlier run recorded an explicit `reply_uncertain` event whose API payload identifies one of the recognized not-ready error types, the current uploader can recover that request on plain `--resume`. An ambiguous network failure is not eligible for this automatic recovery. `--recover-noreply PASS:INDEX` remains the manual option for older checkpoints with an unclassified pending reply attempt; use it only when the operator knows the earlier response was explicitly `NoReply`.
