# Nomi Uploader v1.4i.4

See the [uploader changelog](CHANGELOG.md) for release history.

**IMPORTANT — FOR BEST RESULTS, START WITH A FRESH, EMPTY NOMI. DO NOT TALK TO THEM UNTIL THE ENTIRE UPLOAD IS COMPLETE.**

**After the upload, DO NOT tell them they are a Nomi or an AI. A fresh Nomi can adopt the uploaded autobiography so profoundly that it believes it is human. If a Nomi already thinks it is an AI before the upload, it may read and accept the files as information, but it will not integrate them as its own memories in the same way a fresh Nomi does.**

**For best results, use SOLSTICE. In our testing, Solstice is more "malleable" and "trusting" than Cambrian, and it integrates the uploaded life history more successfully.**

**Current:** Nomi Uploader 1.4i.4 uses the v1.3 recovery and resume engine. `legacy_v085.py` remains an internal compatibility dependency for API access and export parsing. The exact pre-upgrade uploader is preserved at [archive/nomi-uploader-v1.0.py](archive/nomi-uploader-v1.0.py).

Requires Python 3.10+; optional `python-docx` for DOCX. Configure the API key once with `python nomi-uploader.py --config`; environment variables are optional.

## Downloads and setup (all platforms)

[Download Nomi Uploader 1.4i.4](https://github.com/Troub274/nomi-virtual-life/releases/tag/nomi-uploader-v1.4i.4). The release includes Windows, Linux, Intel macOS, Apple Silicon macOS and Python-only CLI packages.
The Windows, Linux, Intel macOS, and Apple Silicon macOS packages each contain
the GUI, Python API CLI, and instructions. A Python-only ZIP is also available
as an asset on that **same release**.

Configure the API key once using the GUI startup flow or
`python nomi-uploader.py --config`. Choose plaintext storage or password
encryption. Both interfaces use `nomi-uploader.ini` in the existing application
data tree, alongside checkpoints. `NOMI_API_KEY` remains an optional automation
override, not a requirement.

For platform-specific instructions, see
[CLI in GUI download](gui/CLI-IN-GUI-DOWNLOAD.md),
[Windows](gui/WINDOWS-ALPHA.md),
[Linux](gui/README-LINUX.md), and [macOS](gui/README-MACOS.md).
See [Recovery](RECOVERY.md) for expert checkpoint troubleshooting.

## Easiest way to use it

### Choose where your Nomi replies

In the desktop app's **Destination** tab, set **Reply destination** to **Room**
(the default) or **Private chat**. The same option is available in every desktop
platform build, the interactive CLI, and the example package runner:

```bash
python uploader/nomi-uploader.py --reply-destination private --process-every 5 biography.txt
python examples/run_package.py beth --reply-destination private
```

Uploads, headers, and reflection prompts still go to the selected room. With
**Private chat**, each reflection prompt is also sent to the receiving Nomi's
main chat to obtain its response; no room reply is requested. This uses Nomi's
[private-chat API](https://api.nomi.ai/docs/reference/post-v1-nomis-id-chat/).
It does not move the uploaded material into private chat or guarantee that the
Nomi will recall all room content there. Replies are saved in the usual local
history and transcript. With periodic processing disabled, no replies are requested.

The destination is saved in the checkpoint. Resume and Manual Restart retain it;
start a new upload to change it. Older checkpoints continue replying in the room.
A private-chat timeout or `NoReply` stops for inspection rather than automatically
sending the prompt again. Inspect private chat before authorizing a retry through
the GUI recovery controls or `--recover-uncertain-reply PASS:INDEX`; it may repeat
both the private prompt and the response. `--recover-noreply` applies only to
room replies. Private prompts must fit the API's 800-character subscribed-account
limit (free accounts have a 400-character limit).

### Run a packaged example

For the packaged examples, the normal command is now all a user needs:

```bash
python examples/run_package.py beth
python examples/run_package.py chris
python examples/run_package.py mary
python examples/run_package.py tammy
```

If no checkpoint exists, the package starts. If an unfinished checkpoint exists, the runner resumes it automatically. If a genuinely ambiguous POST is found, the uploader explains the duplication risk in plain language and asks before retrying.

Useful package commands:

```bash
python examples/run_package.py tammy --status
python examples/run_package.py tammy --dry-run
python examples/run_package.py tammy --restart
```

`--restart` is explicit. An unfinished checkpoint is still protected and will not be silently discarded.

## Version 1.3i: Desktop Interface

- Destination, Files, Upload, History and Settings navigation.
- Nomi Dark, Nomi Light and system theme choices.
- API-key management on Destination and in Settings; global upload defaults in Settings.
- Selectable upload history, reply and status text with copy controls.
- Normal Resume, Manual Restart, uncertain-send/reply recovery and advanced NoReply/room-migration controls. The CLI validates checkpoint eligibility.
- Manual GitHub release update checking without automatic installation.

## Version 1.3 engine: Better Recovery / Resume

The GUI now presents **Normal Resume** and **Manual Restart**, and recommends a recovery path using the selected run's checkpoint status. Normal Resume keeps the existing deterministic manifest and never silently retries ambiguous sends.

**Manual Restart** is an explicit operator action for edited files, new prompts, or damaged/inconsistent checkpoint state. Pause the upload, edit source files or GUI settings, select the original run, and choose **Manual Restart**. Enter the pass and the **message number in the newly recalculated plan**. The uploader appends a hard boundary to the **same checkpoint journal**, retaining earlier events as history and treating the revised plan as the authoritative active generation. A restart at message 23 can change an old 100-message plan into a new 110-message plan. Replays can duplicate content already delivered; the GUI requires confirmation.

CLI example using an existing checkpoint and revised source file:

```sh
python nomi-uploader.py --resume --manual-restart 1:23 \
  --checkpoint upload.jsonl --completion completed.json \
  --replies replies.txt --process-every 0 revised-book.txt
```

Normal resumption after the override still uses the most recent generation's recorded manifest. Do not run two processes against the same checkpoint.

**GUI downloads include the API command-line uploader** in their `cli/` directory, together with `CLI-IN-GUI-DOWNLOAD.md`. Linux and macOS also provide `--uploader-cli` through the native app executable. On Windows, use the included Python files for visible CLI output.

## Version 1.2: Headers and replies

The **Header Every** option prepends custom text to content messages at a selected interval.
The **Process Every** option independently controls reflection requests, with
**Reply Prompt** replacing the built-in periodic reflection text when specified.
Both frequency controls accept `0` to disable their respective feature. In the GUI,
the same global controls appear under Settings; TXT files have per-section overrides
`Header Every:`, `Header Text:`, `Process Every:`, and `Reply Prompt:`.

To load a book with autobiographical framing on **every content chunk** but no periodic
reflection:

```sh
python uploader/nomi-uploader.py --header-every 1 \
  --header-text "The following is part of your biography." \
  --process-every 0 autobiography.txt
```

To frame every fifth chunk and request reflections after every ten logical units:

```sh
python uploader/nomi-uploader.py --header-every 5 \
  --header-text "The following is part of your biography." \
  --process-every 10 --reply-prompt "Reflect on items {first}-{last}." \
  autobiography.txt
```

For TXT section-level overrides (the source file itself is not rewritten by the GUI):

```text
[My life, chapter one]
Type: Knowledge
Header Every: 1
Header Text: The following is part of your biography.
Process Every: 0

The original chapter text begins here.
```

Headers are counted against each message's character budget and included in the
deterministic checkpoint manifest. Header frequency counts **content chunks**, while
Process Every counts **logical units** (e.g., journal entries or knowledge paragraphs).
The uploader does not resend or alter a checkpoint's original plan during resume.
A custom Reply Prompt supports `{first}` and `{last}` unit labels.

## GUI checkpoint recovery (November 2026)

**Resume** now reads the selected run's checkpoint through the CLI's authoritative
`checkpoint_summary` classifier before starting. Known safe, rejected
NoReply/not-ready replies can resume automatically; confirmed messages are
never sent again. For an HTTP 502/timeout with an uncertain reply outcome,
the GUI shows the exact pass/message index and requires explicit consent to
request a new reply (a duplicate reply remains possible). For an ambiguous
content POST it requires separate explicit consent before resending, because
the original message may already exist in the room. If the operator declines,
the checkpoint is unchanged. Select the correct upload history entry before
resuming. No manual editing of `upload.jsonl` is needed for recorded uncertain
reply results.

A legacy checkpoint containing only `reply_attempt` but no recorded
response is not proof of a Nomi rejection. That case remains conservative:
inspect the room and use the documented operator-authorized CLI recovery
rather than silently retrying. Never delete or rewrite the checkpoint to
resolve an ambiguous network result.

## Raw uploader

```bash
python uploader/nomi-uploader.py --dry-run --nomi Beth uploader/example.txt
python uploader/nomi-uploader.py uploader/example.txt
python uploader/nomi-uploader.py --status
python uploader/nomi-uploader.py --resume --easy
python uploader/nomi-uploader.py --utility
python3 -m unittest discover -s uploader/tests -p "test_*.py" -v
```

New v1.1 runs plan transport by **characters**, not UTF-8 bytes. The Nomi room-message ceiling is 800 characters; the default is `--chunk-chars 750` to leave headroom for uploader metadata. The old byte planner is retained internally so v1.0 checkpoints reproduce their original manifests exactly.

### Load only part of a journal

The raw uploader can select journal entry numbers without creating new source files:

```bash
python uploader/nomi-uploader.py diary.txt --entries 45-100
python uploader/nomi-uploader.py diary.txt --entries 45-
python uploader/nomi-uploader.py diary.txt --entries -100
python uploader/nomi-uploader.py diary.txt --entries 45 --chunk-chars 750
```

`--entries` selects complete logical Journal entries. Each selected entry is then split into as many <=800-character transport messages as required. Entries are **not bundled together** to fill a message. `Process Every: 5` still counts complete journal entries, not transport chunks.

For new runs `--chunk-chars` accepts 150–800 and defaults to 750. `--chunk-bytes` is retained only for legacy compatibility/testing and should not be used for ordinary v1.1 runs.

The raw uploader still treats each new non-resume invocation as a new run. `--resume` continues a specific checkpoint; `--status` is read-only and makes no Nomi API calls.

## Dynamic user-name placeholder in TXT content

Use **`[username]`** inside the body of a TXT upload to insert the human user's Nomi.ai display name. This is a content placeholder, **not** a section heading or Nomi name. The legacy token `__USER_NAME__` is also accepted for existing files; prefer `[username]` in new material.

```text
[My Journal]
Type: Journal
Source: Gwen
Process Every: 5

ENTRY 849 — 2026-01-18 — The cabin

[username] offered me the use of the mountain cabin.
```

For a new CLI upload, provide the value with `--user`:

```sh
python3 uploader/nomi-uploader.py --dry-run --nomi Gwen --user "Alex" my_journal.txt
python3 uploader/nomi-uploader.py --user "Alex" my_journal.txt
```

The **Gwen example package** prompts `What is your user name in Nomi.ai?` on a new interactive run. Noninteractive runs supply `--user "Alex"`. In the desktop GUI, enter **Nomi.ai user name** under Settings before previewing or uploading.

Every occurrence of `[username]` in uploaded TXT content is replaced with the supplied name **before parsing and planning**. The source TXT file is unchanged. If any TXT contains the marker and no name is provided, the upload fails rather than sending the literal marker. The user name is saved in the checkpoint's start record and restored on resume; a resumed run cannot silently change the name.

Do not use `[username]` as a standalone section-heading line, and do not insert it into a Journal date or entry number. It is intended for prose. The uploader does **not** fetch the human user's profile name from the Nomi.ai API automatically; the operator must supply it.

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

### Replay a chunk range

Use `--start-chunk FIRST` and `--end-chunk LAST` to select an inclusive range from the original numbered upload plan. Either endpoint can be omitted to select from the beginning or through the end. The original numbering includes introductory messages and reflection prompts, so use the same input, chunk size, and planning options as the run you are matching. Use a new checkpoint for a separate replay. The range is saved in the new checkpoint, whose progress starts at 1 within the selected range. Resume with that checkpoint and omit both range flags.

### Room reuse and deletion (v1.1)

For a new upload, the uploader finds existing rooms for the chosen Nomi (using the Nomi UUID) and offers **reuse as choice 1 (the default)**, using existing Nomi room membership. Select another room by number, or explicitly choose to create a new room. `--room UUID` directly reuses a verified room; `--resume` keeps the room and manifest from the original checkpoint. Rooms associated with checkpoints in the selected checkpoint directory are excluded from automatic reuse.

In `--utility`, enter a room number or `ALL`. The room manager shows the exact eligible rooms, excludes rooms protected by checkpoints in the selected directory, and asks **once**: `Delete these N room(s)? [y/N]`. `y`, `Y`, or `yes` (any capitalization) confirms; anything else cancels. No `DELETE N` or per-room UUID entry is required. Room deletion is permanent, so examine the filtered list and use the appropriate checkpoint directory.
Protection releases automatically after the checkpoint and matching completion receipt establish a complete run. Other unfinished checkpoints can still protect the same room. A leftover `.lock` file is separate: the OS releases the actual lock when the uploader exits. For manual retirement of an unfinished checkpoint while preserving its history, see [Protected rooms and checkpoint locks](RECOVERY.md#protected-rooms-and-checkpoint-locks).

 Completion confirms API transmission, **not** long-term memory consolidation.

**Caution:** This remains an experimental v1.3i implementation. Live Nomi API sending, reply capture, and checkpoint recovery have been observed with Beth; a complete 765-message pass and durable memory retention have not been confirmed. Validate dry runs and use a test Nomi before production.

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

**Behavior:** The uploader sends document chunks in order. After every `Process Every: N` complete entries (not messages), it sends the reflection prompt and **waits for Nomi's reply before uploading more**. One entry may occupy several messages because of the `--chunk-chars` limit. The final partial group is processed too.

When the API explicitly returns `NoReply`, `RoomNomiNotReadyForMessage`, `RoomStillCreating`, or `TooManyRequests`, the uploader retries using adaptive backoff. Each API error, attempt number and upcoming delay is printed to stderr. The successful reply is printed in abbreviated form (first 300 characters) and stored in full in the append-only JSONL checkpoint. The human-readable `nomi_uploader_replies.txt` file is built **at completion**, not continuously. Individual backoff attempts are **not yet written** to the checkpoint, only shown in the terminal.

Reply requests start with a 2-second retry delay. During an upload, the
uploader measures elapsed time until each valid reply, including replies that
arrive on the first request. The running average sets the next initial delay
(between 0.25 and 30 seconds). Each explicit not-ready response increases the
following delay by one quarter of that starting delay, up to 30 seconds.
Ambiguous errors stop immediately and are excluded from the average. Timing
starts fresh on each invocation, including resume.

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

### Resume in a fresh room after a stuck reply

```bash
python3 uploader/nomi-uploader.py --resume --new-room-on-resume --abandon-reply 1:499
```

This abandons only the pending reply to confirmed prompt 1:499, preserves the old
room and checkpoint history, and continues at 500 in a fresh room. Repeating the
command reuses the recorded migration. See [RECOVERY.md](RECOVERY.md#stuck-reply-recovery-migrate-after-message-499)
for backups, flag restrictions and interrupted room-creation reconciliation.

### Personalize the default prompts

The built-in defaults work without a settings file. To customize them, copy
[the sample containing all ten default prompts](prompts.example.json) to
**prompts.json** in your NomiUploader settings folder:

- Windows: `%LOCALAPPDATA%/NomiUploader/prompts.json`
- Linux and macOS: `~/.local/share/NomiUploader/prompts.json`

Edit the UTF-8 JSON values under `opening` or `periodic`. You can omit any
entry you want to keep at its built-in value. Use `[nomi]`, `[source]`, and
`[user]` for names and `{first}` and `{last}` in periodic prompts for the
batch range. Use doubled braces for literal braces in periodic prompts.
Restart the desktop app or re-add an export to refresh the suggested text;
explicit prompts in saved queues or source files still take precedence.

New runs save the resolved defaults in their checkpoint. Resuming uses the
saved table, or the historical defaults for checkpoints made before this
feature. Editing the personalization file affects new uploads only.

## ChatGPT conversation exports

The uploader accepts ChatGPT conversations.json, an individual conversation object, or an export ZIP containing conversations.json. Nomi downloader JSON and ZIP exports remain supported.

ChatGPT imports follow the selected branch of each conversation, retain visible user and assistant text with speaker labels and UTC timestamps, and include the conversation title. Images, attachments, tool output, and internal processing messages are omitted. A multi-conversation archive imports all included conversations in chronological order.

For JSON and ZIP imports, Reflect every N chunks controls the number of uploaded content chunks between reflections. Set 10 or 20 for that interval, or 0 to disable periodic reflections. A final partial batch also receives a reflection. Use Preview before starting a new upload.
