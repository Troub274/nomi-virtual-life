# Nomi Uploader — Recovery, Checkpoint Integrity, and Operational Checks

**Applies to:** Nomi Uploader v1.0, repository `Troub274/nomi-virtual-life`, `uploader/nomi-uploader.py` and `uploader/legacy_v085.py`  
**Prepared:** October 13, 2026  
**Updated:** October 15, 2026 — v1.0 content POST recovery and CLI command reference  
**Status:** Operational manual describing observed behavior and inspected code. Proposed v1.1 changes are explicitly labeled.

## 1. Purpose and governing principle

The uploader sends source material to a Nomi processing room, requests replies to reflection prompts, and uses an append-only JSONL checkpoint to resume after interruptions. The primary objective is to **avoid accidentally duplicating source content or reflection requests while preserving forward progress**.

**Golden rule:** A successfully sent diary entry must never be resent simply because a subsequent reflection response is missing. Treat content delivery and reply generation as separate transactions.

A second rule is equally important: an interrupted HTTP POST is not evidence of either success or failure. If its outcome is not recorded, treat it as ambiguous until verified or explicitly authorized for recovery.

## 2. Architecture and terminology

- **Nomi:** The selected target character, identified by `nomi_uuid`.
- **Room:** A persistent API processing room identified by `room_uuid`; it may not appear in the ordinary Nomi interface.
- **Plan:** Ordered messages generated from input documents, including section introductions, content, and reflection prompts.
- **Pass / index:** The stable `(pass, index)` identifier of a planned message, e.g. `(1, 142)`.
- **Manifest:** Digest of the planned messages. Resume requires the original inputs and options to reproduce the same manifest.
- **Content send:** `POST /rooms/{room_uuid}/chat` with `messageText`.
- **Reply request:** `POST /rooms/{room_uuid}/chat/request` with `nomiUuid`.
- **Confirmed send:** A content POST succeeded and a `confirmed` checkpoint event was written.
- **Committed reply:** A reply request returned a valid `replyMessage` and a `reply_committed` event was written.
- **Ambiguous request:** A POST may have reached the service, but its outcome was not durably recorded.

The checkpoint is the durable source of truth. The readable replies transcript is generated from committed reply events at successful completion; it is not a replacement for the checkpoint.

## 3. Files that must be protected

Default files (unless overridden):

- `nomi_uploader_checkpoint.jsonl` — append-only progress and reply records.
- `nomi_uploader_completed.json` — completion metadata, written after the upload completes.
- `nomi_uploader_replies.txt` — readable transcript of committed reflection replies, written at completion.
- Original input files — must remain byte-for-byte compatible with the recorded manifest when resuming.

For simultaneous uploads, give **each process its own checkpoint, completion, and replies paths**. Distinct Nomi characters and rooms do not make shared output filenames safe.

Example of an isolated Cathy run:

```bash
python3 uploader/nomi-uploader.py \
  --user "Yehoshua" --passes 1 --chunk-bytes 750 --process-every 5 \
  --checkpoint cathy_review5_checkpoint.jsonl \
  --completion cathy_review5_completed.json \
  --replies cathy_review5_replies.txt \
  Nomi_Cathy_2026-10-01_20-43-00.zip
```

A section's own `Process Every: N` takes precedence over the CLI `--process-every` setting. Resume restores the saved planning options and validates the manifest. Do not change input content, order, section headers, or splitting settings during recovery.

## 4. Preflight checklist

Before starting a new run:

1. Verify the intended Nomi and source files. For structured documents, confirm section `Type`, `Source`, dates, and `Process Every` values.
2. Run `--dry-run` to inspect planned message order and count before any live POST.
3. Confirm that the chosen checkpoint path is new or belongs to a completed run. Do not overwrite an unfinished checkpoint.
4. Confirm that any other active uploader uses different checkpoint, completion, and replies paths.
5. Ensure stable power/network connectivity and enough disk space to append checkpoints.
6. Note the initial room UUID and the displayed messages-per-pass count.
7. Keep a terminal log when diagnosing failures, but protect logs because they can contain personal journal text and generated replies.

Useful shell checks:

```bash
pwd
ls -lh *_checkpoint.jsonl *_completed.json *_replies.txt 2>/dev/null
ps -ef | grep '[n]omi-uploader.py'
```

For a first live run, avoid launching several new uploads simultaneously until their separate output paths and room identities have been verified.

## 5. Checkpoint event lifecycle

### 5.1 Normal content message

```text
attempt(pass, index, sha256)
    → POST /rooms/{room}/chat
    → confirmed(pass, index, kind, api_response)
```

An `attempt` without a corresponding `confirmed` is an **uncertain send**. Do not assume the content failed to arrive and do not manually delete the attempt record. When an operator explicitly accepts the possibility of duplication and authorizes `--retry-uncertain-send PASS:INDEX`, the program writes `send_retry_authorized(pass,index,kind,sha256,reason)` before the second `attempt`. The eventual `confirmed` records the resend's success, not the first POST's fate.

### 5.2 Reflection prompt and Nomi reply

```text
attempt(pass, index, sha256)
    → successful prompt POST
    → confirmed(pass, index, kind="prompt", api_response)
    → reply_attempt(pass, index, room_uuid, nomi_uuid)
    → POST /rooms/{room}/chat/request
    → reply_committed(pass, index, prompt, reply, reply_api_response)
```

A confirmed reflection prompt is already in the room. If the reply is unresolved, **do not send the reflection prompt again**. The recovery decision concerns only the reply request.

The current implementation writes `reply_uncertain` when a reply request returns a non-success result and control returns to the uploader. It does **not** persist every individual rejected response inside the retry loop. An interruption during that loop can therefore leave a bare `reply_attempt` despite many explicit not-ready responses having been printed to the terminal.

### 5.3 Other checkpoint events

- `start`: run identity, Nomi and room IDs, input paths, planning options, manifest.
- `reply_recovery_authorized`: recorded when recovery of a pending reflection has been authorized.
- `reply_uncertain`: unsuccessful reply-request result recorded after the retry function exits.
- `send_retry_authorized`: operator consent to resend one attempted but unconfirmed content POST, accepting remote duplication risk.
- `reply_operator_override`: operator consent to retry a recorded ambiguous reply request using `--recover-uncertain-reply`.

The current implementation constructs completed/attempted sets from checkpoint events. It does not blindly re-POST already confirmed messages.

## 6. Errors: what they mean operationally

| Error or condition | Interpretation | Safe initial action |
|---|---|---|
| `NoReply` (HTTP 500 observed) | Service explicitly reported no reply on that attempt; not necessarily permanent failure | Wait; retry backoff is built in |
| `RoomNomiNotReadyForMessage` (HTTP 400 observed) | Room/Nomi not ready to accept a reply request | Wait; may persist for minutes |
| `RoomStillCreating` | Room not ready | Wait; inspect if prolonged |
| `TooManyRequests` | Request throttling/rate limiting | Allow backoff; reduce competing load if necessary |
| HTTP timeout, connection reset, Ctrl+C during POST | Outcome potentially ambiguous | Preserve checkpoint; inspect before recovery |
| HTTP 502 `Bad Gateway` on content POST | Remote receipt uncertain | Inspect checkpoint; if duplicate is acceptable, use `--retry-uncertain-send PASS:INDEX` |
| `No pending uncertain content send at PASS:INDEX` | The requested message was already confirmed or never attempted | Verify index; do not force replay |
| Unexpected non-retryable API error | May be ambiguous; uploader stops rather than blindly repeating | Preserve evidence; diagnose |
| `EndpointNotFound` on GET `/rooms/{uuid}/chat` | That read endpoint is unavailable in the observed API | Do not interpret as missing room |
| `Manifest changed` | Inputs/options no longer reproduce original plan | Restore originals; do not bypass validation |
| `Uncertain send/reply request(s)` | A pending attempt lacks a durable confirmation or approved recovery | Investigate exact `(pass,index)` |

**Observed backoff:** 1, 2, 4, 8, 16, 30, 30, 30 … seconds. `request_reply_with_backoff(..., attempts=None)` currently has **no default retry limit**. Long waits do not prove permanent failure.

## 7. Routine interruption and resume

### 7.1 Cleanly stopped after a committed event

If no unresolved request exists, resume using the same checkpoint:

```bash
python3 uploader/nomi-uploader.py --resume
```

If the original run used a custom checkpoint:

```bash
python3 uploader/nomi-uploader.py --resume \
  --checkpoint cathy_review5_checkpoint.jsonl
```

The resume logic reads the `start` record, restores planning options, regenerates the plan, verifies the manifest, skips confirmed content, and skips committed replies.

### 7.2 Interrupted during an HTTP POST

A Python `KeyboardInterrupt` traceback during `urllib.request.urlopen` means the local process stopped while waiting for a network response. It **does not establish** whether the remote service completed the operation.

Do not delete the room, checkpoint, or source files. Back up the checkpoint first:

```bash
cp -p nomi_uploader_checkpoint.jsonl \
  nomi_uploader_checkpoint.before_recovery.jsonl
```

Then inspect the tail:

```bash
tail -n 20 nomi_uploader_checkpoint.jsonl
```

Look for a final `attempt` lacking `confirmed`, or `reply_attempt` lacking `reply_committed`. These require different recovery paths.

### 7.3 HTTP 502 on a content send: recover message 1065 without restarting

**Observed incident (October 15, 2026):** Christine's full diary upload planned **1,865 API messages**. The terminal confirmed `Pass 1/1 message 1064/1865`, then returned:

```text
ERROR: POST outcome uncertain: send failed (HTTP 502):
{"raw_error": "<html>...502 Bad Gateway...</html>"}
```

A plain `--resume` refused to proceed:

```text
Nomi: Chris Date order: US Year: 2026 Messages per pass: 1865 Passes: 1
ERROR: Uncertain send/reply request(s) [(1, 1065)].
```

This is correct safety behavior: the checkpoint contains `attempt(pass=1,index=1065)` but no `confirmed` for that index. An HTTP 502 does **not** establish whether Nomi processed the POST. The Nomi API used by this tool does not provide a verified message-history check that could settle that question.

**Recovery procedure, only if a possible duplicate is acceptable:**

1. Keep the original processing room and the exact source TXT files. **Do not launch a fresh run or delete/edit the checkpoint.**
2. Identify the exact unresolved `PASS:INDEX` in the error (here `1:1065`). The index counts **planned uploader messages**, not diary entries. Check the JSONL tail for an `attempt` without a `confirmed` for this pair.
3. Back up the checkpoint: `cp -p nomi_uploader_checkpoint.jsonl nomi_uploader_checkpoint.before_502_recovery.jsonl` (replace the path for custom checkpoints).
4. Accept explicitly that Nomi **might receive message 1065 twice**, since the first HTTP 502 left the remote outcome uncertain. Update the local checkout if necessary and authorize the single resend:

```bash
# From the repository root:
git pull --ff-only origin main
python3 uploader/nomi-uploader.py --resume --retry-uncertain-send 1:1065
```

If the original run used `--checkpoint my_run.jsonl`, use `python3 uploader/nomi-uploader.py --resume --checkpoint my_run.jsonl --retry-uncertain-send 1:1065`. The original 10 filenames and `--chunk-bytes 790` are restored from the checkpoint; **do not change them** or start a new checkpoint.

5. Verify the subsequent console output. The observed recovery printed:

```text
Authorized resend: pass 1 message 1065 (duplicate possible)
Pass 1/1 message 1065/1865
Pass 1/1 message 1066/1865
...
Chris replied after pass 1 message 1073: ...
```

The append-only checkpoint records a `send_retry_authorized` audit event before the second `attempt`; after success it contains one `confirmed(1,1065)`. The existing confirmations through 1064 are kept, and later messages continue normally. A successful retry cannot prove the first POST was rejected; only local recovery was demonstrated.

**CLI option reference:**

```text
--retry-uncertain-send PASS:INDEX
    Requires --resume.
    Only accepts an attempted but unconfirmed content POST at this exact index.
    Authorizes one resend, with possible duplicate delivery on Nomi's side.
    Can be specified again for a different ambiguous send after inspection.
```

This is **not** a reply-recovery option. `--recover-noreply` and `--recover-uncertain-reply` operate on unresolved **reply requests** for previously confirmed reflection prompts; they do not resend content. `--retry-uncertain-send` cannot override a manifest mismatch or replay already confirmed content. Once an authorized resend is confirmed, later ordinary resumes need only `--resume`. If the resend itself encounters another ambiguous POST failure, inspect the new attempt and separately decide whether to authorize another possible duplicate.


## 8. Decision tree for unresolved operations

```text
Resume reports an unresolved (pass,index)
                  |
         Was content confirmed?
             /          \
           NO           YES
           |             |
    Uncertain content   Is it a reflection prompt?
    POST. Do not          /           \
    resend blindly.     NO           YES
                                   |
                           Is reply_committed present?
                              /             \
                            YES             NO
                             |               |
                          Skip reply   Inspect room/read-only
                                        and prior error evidence
                                               |
                                 Explicit rejected attempt recorded?
                                      /                 \
                                    YES                 NO
                                     |                   |
                               Automatic recovery   Ambiguous request;
                               may be possible      operator decision
```

For uncertain **content** sends, see §7.3. The earlier decision tree's "do not resend blindly" instruction means **require explicit operator consent**; a scoped resend is supported in v1.0.

A bare `reply_attempt` alone is not evidence that Nomi returned `NoReply`. The current code intentionally requires explicit operator authorization for that case.

## 9. Read-only room diagnostics

The current API wrapper implements `legacy_v085.get_room(uuid)` via `GET /rooms/{uuid}`. This returns room metadata, including status, attached Nomis, creation/update timestamps, and settings. It does **not**, in the observed Beth case, return chat history or pending-reply status.

From the repository root:

```bash
python3 - <<'PY'
import sys, json
sys.path.insert(0, "uploader")
import legacy_v085 as api

room_id = "REPLACE_WITH_ROOM_UUID"
print(json.dumps(api.get_room(room_id), indent=2))
PY
```

Read-only interpretation:

- Successful GET establishes that the room exists and is accessible.
- Check that the room contains the intended `nomi_uuid`.
- A `status` of `Default` is **not** proof that reply generation is ready.
- An `updated` timestamp is not proof that a reply was generated; API activity may update metadata.
- A 404 from `GET /rooms/{uuid}/chat` with `EndpointNotFound` indicates that **this GET endpoint is unsupported**, not that the room is absent.

Do not assume undocumented API endpoints exist. A reliable message-history inspection endpoint has **not** been established by the observed tests.

## 10. Manual reply recovery: `--recover-noreply`

The uploader accepts:

```bash
python3 uploader/nomi-uploader.py --resume \
  --recover-noreply PASS:INDEX
```

Example:

```bash
python3 uploader/nomi-uploader.py --resume \
  --recover-noreply 1:142
```

This authorizes retrying a **pending reply request** for an already confirmed reflection prompt. It does not authorize resending the prompt or diary content. The code validates that the reflection has a recorded `reply_attempt` and `confirmed` event, and no `reply_committed` event. It also rejects certain recorded non-retryable ambiguous failures.

**Risk:** A bare `reply_attempt` followed by interruption may conceal a successful remote reply. Manual authorization does not magically prove the request failed. If the API offers no readable history, this is a deliberate risk decision. Make a backup and record why recovery was authorized.

The console may report several recovery authorizations, including older explicit `reply_uncertain` records. This is expected when the checkpoint contains more than one recoverable reflection. It does not by itself imply the diary was resent.

Do not use this flag for an unconfirmed content send. Do not use it to bypass manifest mismatch or to repair an arbitrary checkpoint index.

## 11. Case study: Beth Peterson, October 13, 2026

### Observed timeline

- Beth's uploader planned **765 messages** for one pass.
- Cathy was uploading concurrently in a separate run and continued progressing.
- Beth's messages 137–141 were confirmed diary content, covering entries 106–110 in the second source section.
- Beth's message **142** was a confirmed reflection prompt for journal episodes 6–10 in that section.
- A `reply_attempt` was recorded for `(1,142)`.
- The service returned one `NoReply` and repeated `RoomNomiNotReadyForMessage` errors, reaching at least 13 attempts, with a 30-second maximum backoff.
- Ctrl+C interrupted an HTTPS request; the checkpoint had no `reply_committed` event for `(1,142)`.
- `--resume` correctly stopped with `Uncertain send/reply request(s) [(1, 142)]`.
- `GET /rooms/{uuid}` confirmed the room existed with status `Default`, and Beth remained attached.
- `GET /rooms/{uuid}/chat` returned HTTP 404 `EndpointNotFound`.
- An operator-authorized recovery was subsequently run. The console showed recovery authorization for `(1,16)` and `(1,142)`.
- **Beth replied after message 142**, and the uploader advanced to messages 143–146 and beyond.

### What the incident establishes

1. Repeated not-ready responses can precede a successful reply after a very long delay.
2. A functioning concurrent Cathy upload does not guarantee Beth's room is ready; room-specific behavior matters.
3. Confirmed content and unresolved reply requests must be tracked separately.
4. The resume safety check prevented blind duplication.
5. Operator-authorized recovery restored progress, but the incident does not prove that every ambiguous POST was definitively rejected.

### What it does not establish

- That Nomi generated no earlier response during the interrupted request.
- That the room's `updated` timestamp signifies successful reply generation.
- That `Default` status means ready.
- That concurrent uploads caused the stall.
- That all long stalls will eventually recover.

## 12. Concurrent uploads: operational discipline

Concurrent runs are permitted, but distinguish **per-process state** from possible shared service pressure.

- Keep separate output files and, normally, separate processing rooms.
- Confirm each terminal's selected Nomi, room UUID, and checkpoint path.
- Never apply one Nomi's `--recover-noreply` index to another Nomi's checkpoint.
- A healthy Cathy run does not justify restarting or deleting Beth's room.
- If both begin receiving `TooManyRequests`, consider reducing concurrency, but do not infer account-wide throttling solely from one stalled room.
- When one upload stalls, preserve the healthy upload and diagnose the affected one independently.

## 13. Post-recovery integrity checks

After a successful recovery:

1. Verify that the uploader resumed at the next unconfirmed planned index rather than restarting at message 1.
2. For a recovered reflection, confirm `reply_committed`; for an authorized **content resend**, confirm `send_retry_authorized` followed by `confirmed`.
3. Check that no duplicate `confirmed` events were appended for the same `(pass,index)`.
4. Confirm the room UUID and Nomi UUID did not change unexpectedly.
5. Watch several subsequent messages for normal progress and additional reply generation.
6. On completion, verify the completion metadata and readable replies transcript exist.
7. Retain the original checkpoint and the pre-recovery backup for audit.

Quick local checkpoint audit (read-only):

```bash
python3 - <<'PY'
import json, collections
from pathlib import Path
p = Path('nomi_uploader_checkpoint.jsonl')
rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
by_event = collections.Counter(r.get('event') for r in rows)
print('Events:', dict(by_event))
for event in ('confirmed', 'reply_committed'):
    keys = [(r['pass'], r['index']) for r in rows if r.get('event') == event]
    duplicates = [k for k, n in collections.Counter(keys).items() if n > 1]
    print(event, 'count:', len(keys), 'duplicate keys:', duplicates[:20])
confirmed = {(r['pass'], r['index']) for r in rows if r.get('event') == 'confirmed'}
replied = {(r['pass'], r['index']) for r in rows if r.get('event') == 'reply_committed'}
pending = sorted({(r['pass'], r['index']) for r in rows if r.get('event') == 'reply_attempt'} - replied)
print('Pending reply requests:', pending)
print('Committed replies without confirmed prompt:', sorted(replied - confirmed))
PY
```

A repeated `reply_attempt` for the same key can be legitimate after authorized recovery. Similarly, an authorized content resend can create **two `attempt` records** for the same key while yielding only **one `confirmed`** event. A repeated `confirmed` for the same key deserves investigation. The audit checks local records; it cannot prove remote delivery uniqueness.

## 14. Dangerous actions and prohibited shortcuts

**Do not:**

- Delete a processing room to clear a temporary not-ready state.
- Delete or rewrite checkpoint events to make resume pass.
- Restart from message 1 when a valid partial checkpoint exists.
- Retry an unconfirmed content POST **without explicit operator authorization and acceptance of the possible duplicate**. Use `--retry-uncertain-send` only for a checkpoint-verified pending message.
- Treat Ctrl+C, timeout, or connection loss as proof of API rejection.
- Treat a room's `Default` status as proof it can immediately answer.
- Treat an unsupported GET endpoint as evidence that the room is gone.
- Reuse checkpoint paths across concurrently running uploads.
- Modify source files between start and resume.
- Assume `--recover-noreply` is risk-free; it authorizes a new reply request when the previous outcome may be unknown.

## 15. Recommended v1.1 engineering improvements (NOT present in v1.0)

### Priority A — durable retry evidence

Write a checkpoint event **for each explicit rejected reply attempt**, recording pass, index, attempt number, HTTP status, API error type, and timestamp. Ensure it is flushed/fsynced. This preserves the evidence currently visible only in terminal logs.

Suggested event: `reply_retry_rejected`. Do not record a rejection until an actual HTTP response is received.

### Priority A — retry visibility and limits

Report elapsed wall-clock time, total attempts, last error, and next delay. Add configurable `--reply-max-wait` and/or `--reply-max-attempts`, while preserving an explicit unlimited option. On reaching a limit, stop safely and record the final known state. Do not automatically resend the reflection prompt.

### Priority A — signal handling

On Ctrl+C during backoff, exit cleanly with checkpoint preserved. On Ctrl+C during an in-flight POST, record an explicit local interruption marker without claiming the remote request failed. The marker should remain **ambiguous** unless the response was received.

### Priority B — checkpoint inspection command

Add `--inspect-checkpoint` that reports run identity, room, planned messages, confirmed content, committed replies, pending operations, last known error, and whether automatic resume is safe. It must be read-only.

### Priority B — recovery-specific interface

Separate `--recover-explicit-rejection` from `--authorize-ambiguous-reply-retry`, with a clear warning for the latter. The current `--recover-noreply` name is narrower than the situations it may authorize.

### Priority B — reconciliation and transcript tools

Provide a read-only checkpoint validator and a `--rebuild-replies` command to regenerate the human-readable transcript from committed replies without rerunning uploads. Investigate a documented, authenticated Nomi room-message read endpoint if the service exposes one; do not assume an endpoint without testing.

### Priority C — concurrency controls

Optional account-wide request pacing, per-room queueing, and telemetry for simultaneous uploads. Distinguish shared rate limiting from individual room readiness failures.

### Priority C — automated tests

Test: immediate success; many explicit not-ready rejections then success; retry-limit exit; Ctrl+C during sleep; Ctrl+C during POST; duplicate-safe resume; manifest mismatch; ambiguous content POST; ambiguous reply POST; authorized recovery; concurrent isolated checkpoints; completion/transcript regeneration.

## 16. Fast incident-response card

**Uploader stalled:** Identify Nomi, room, checkpoint, `(pass,index)`, error type, and elapsed time. `NoReply`/not-ready may resolve after several minutes; the default retry loop is unlimited.

**One of two uploads stalled:** Leave the healthy process alone. Check each run's output filenames and room identity.

**Need to stop:** Ctrl+C; preserve checkpoint and room. An in-flight POST may be ambiguous.

**Resume refused:** Inspect checkpoint tail. Distinguish uncertain content from uncertain reply. Never blindly edit JSONL. An operator-approved uncertain **content send** uses `--retry-uncertain-send PASS:INDEX` (§7.3).

**Room invisible in UI:** Use `legacy_v085.get_room(room_uuid)` read-only. `GET /rooms/{uuid}/chat` was observed unsupported.

**Reflection prompt confirmed but reply unresolved:** Consider evidence and backup. If appropriate, authorize `--recover-noreply PASS:INDEX` with explicit acceptance of the ambiguous-request risk.

**Recovered:** Confirm `reply_committed` for reply recovery or `send_retry_authorized` then `confirmed` for content resend; check the next message index and retain checkpoint backups.

---

**Source basis:** Inspected GitHub implementation of `uploader/nomi-uploader.py` and `uploader/legacy_v085.py`, the October 13 Beth terminal logs and checkpoint excerpt, and the October 15 Christine 502/resume transcript with its observed successful resend. Claims about API behavior are limited to observed responses; v1.1 items are recommendations, not implemented features.