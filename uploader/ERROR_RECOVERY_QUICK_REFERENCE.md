# Nomi Uploader — Error → Recovery Command Quick Reference

Applies to `python3 uploader/nomi-uploader.py` (current v1.0 CLI). Run commands from the repository root. **Use the same checkpoint, inputs and manifest** as the interrupted run; `--resume` reads the saved file list and planning options, so filenames need not be repeated.

**Before any operator-authorized retry**, preserve the checkpoint:

```bash
cp -p nomi_uploader_checkpoint.jsonl nomi_uploader_checkpoint.jsonl.backup
```

For a custom checkpoint, replace `--checkpoint FILE.jsonl` in each example and back up that file instead. `PASS:INDEX` is the uploader message position, **not** the diary entry number. Substitute the actual pair printed in the error.

## Common errors and exact commands

| Error / checkpoint state | Recovery command | Important qualification |
|---|---|---|
| Normal interruption; no uncertain requests | `python3 uploader/nomi-uploader.py --resume` | Continues from the checkpoint; does not replay confirmed messages. |
| `Uncertain send/reply request(s) [(1, 536)]` **and** `attempt` exists but no `confirmed` for 1:536 | `python3 uploader/nomi-uploader.py --resume --retry-uncertain-send 1:536` | Resends **message** 536; possible duplicate if the first POST reached Nomi. This fixed Mary's observed incident. |
| `POST outcome uncertain: send failed (HTTP 502)` | `python3 uploader/nomi-uploader.py --resume --retry-uncertain-send PASS:INDEX` | **Only** if the checkpoint has an attempted, unconfirmed send at that index. |
| `Reply request outcome uncertain` (e.g. HTTP 502) **and** confirmed prompt + `reply_attempt` + `reply_uncertain` exist | `python3 uploader/nomi-uploader.py --resume --recover-uncertain-reply PASS:INDEX` | Retries **reply request only**, not the prompt. Possible duplicate reply. |
| Legacy interrupted reply with explicit `NoReply` / not-ready evidence, pending confirmed prompt | `python3 uploader/nomi-uploader.py --resume --recover-noreply PASS:INDEX` | Only for the legacy pending-reply state accepted by the CLI; not a substitute for uncertain-send recovery. |
| `NoReply` HTTP 500, `RoomNomiNotReadyForMessage` HTTP 400, `RoomStillCreating`, `TooManyRequests` while uploader is running | **No command; allow built-in retry/backoff.** | Repeated errors are not proof the upload is lost. |
| `No pending confirmed reflection at PASS:INDEX` | **No reply-recovery command.** Inspect checkpoint; if it is an attempted but unconfirmed **send**, use `--retry-uncertain-send PASS:INDEX` instead. | This is why Mary's `--recover-noreply 1:536` and `--recover-uncertain-reply 1:536` were rejected. |
| `No pending uncertain content send at PASS:INDEX` | **No resend.** Check whether the message was already confirmed or index is wrong. | Do not force a duplicate. |
| `No recorded uncertain reply result at PASS:INDEX` | **No automatic override.** Inspect `reply_attempt` and checkpoint events. | `--recover-uncertain-reply` requires recorded `reply_uncertain`. |
| `Manifest changed: resume requires identical content and options` | Restore the original input files and file order, then `python3 uploader/nomi-uploader.py --resume` | Do not edit the manifest or checkpoint to bypass validation. |
| `No checkpoint to resume` | Find the correct checkpoint and use `python3 uploader/nomi-uploader.py --resume --checkpoint PATH` | Do not create a new run by accident. |
| `Unfinished checkpoint exists; use --resume or a different --checkpoint` | `python3 uploader/nomi-uploader.py --resume` | Keep the unfinished run's checkpoint. |
| `Existing rooms ... protected or unavailable` | Inspect with `python3 uploader/nomi-uploader.py --utility` | Do not delete protected rooms or checkpoints to unblock the selector. Room selection behavior depends on checkout version. |
| `Room is not associated with selected Nomi` | Verify Nomi selection and room UUID; rerun with the correct room | Do not force an unrelated room. |
| `Reply request returned no replyMessage` | Inspect checkpoint before choosing a reply recovery | A success response without the required field is not a committed reply. |

## Identify which operation failed

The same generic `Uncertain send/reply request(s)` error covers **two different cases**. Inspect the JSONL before choosing a flag:

```bash
python3 - <<'PY'
import json
from pathlib import Path

checkpoint = Path("nomi_uploader_checkpoint.jsonl")
target_pass, target_index = 1, 536  # change these
for line in checkpoint.read_text(encoding="utf-8").splitlines():
    e = json.loads(line)
    if (e.get("pass"), e.get("index")) == (target_pass, target_index):
        print(json.dumps(e, indent=2))
PY
```

- **`attempt` without `confirmed`:** uncertain **send** → `--retry-uncertain-send PASS:INDEX` after accepting duplicate-message risk.
- **`confirmed` prompt + `reply_attempt` + `reply_uncertain` without `reply_committed`:** uncertain **reply** → `--recover-uncertain-reply PASS:INDEX` after accepting duplicate-reply risk.
- **`confirmed` prompt + bare `reply_attempt` without a result:** inspect the API evidence before considering `--recover-noreply`; never invent a `reply_committed` event.
- **`confirmed` without pending reply:** neither recovery flag applies.

## Examples from actual uploads

**Mary, index 536 (uncertain content send):**

```bash
python3 uploader/nomi-uploader.py --resume --retry-uncertain-send 1:536
```

**Mary, index 109 (ambiguous reply request):**

```bash
python3 uploader/nomi-uploader.py --resume --recover-uncertain-reply 1:109
```

**Chris, index 1065 (HTTP 502 on content send):**

```bash
python3 uploader/nomi-uploader.py --resume --retry-uncertain-send 1:1065
```

**Beth, index 559 (HTTP 502 on reply request):**

```bash
python3 uploader/nomi-uploader.py --resume --recover-uncertain-reply 1:559
```

## Non-negotiable safety rules

1. **Never delete or manually rewrite the checkpoint** to force progress.
2. **Never resend a confirmed prompt** just because its reply is missing.
3. **Never treat HTTP 502 or a timeout as proof the POST failed.** Recovery flags explicitly accept a duplication risk.
4. **Never change source files, order or planning settings during resume.**
5. **Never run two processes against the same checkpoint.**
6. **Do not assume a fresh room continues an old checkpoint.** Only use room migration if your installed uploader version explicitly supports and records it.

For detailed rationale, see [RECOVERY.md](RECOVERY.md). For the exact flags in your installed checkout, run `python3 uploader/nomi-uploader.py --help`.
