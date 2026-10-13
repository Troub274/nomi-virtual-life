# Nomi Uploader v1.0

**Current:** Nomi Uploader 1.0. **Legacy:** v0.85 rehydrator is supported but superseded; its independent script remains under `rehydration/`. The uploader includes a verbatim legacy engine in `legacy_v085.py` and `--legacy` forwards its original CLI.

Requires Python 3.10+; optional `python-docx` for DOCX. Set `NOMI_API_KEY` before live uploads.

```bash
python uploader/nomi-uploader.py --dry-run --nomi Beth uploader/example.txt
python uploader/nomi-uploader.py uploader/example.txt
python uploader/nomi-uploader.py --passes 3 uploader/example.txt
python uploader/nomi-uploader.py --resume
python uploader/nomi-uploader.py --utility
python uploader/nomi-uploader.py --legacy --mode journal diary.txt
python -m unittest discover -s uploader/tests -v
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

`Nomi:` instructions are additive by default; `Nomi Mode: Replace` suppresses the type-specific default. Range prompts like `entries 1-24` execute after entry 24. Nomi JSON/ZIP exports use the preserved v0.85 export parser.

Rooms persist after upload. `--utility` lists and explicitly deletes selected rooms; no automatic deletion. Completion confirms API transmission, **not** long-term memory consolidation.

**Caution:** This is an initial v1.0 implementation. Validate dry runs and use a test Nomi before production. API responses, live room creation, and legacy resume compatibility have not yet been integration-tested against a live Nomi service.

## Type-aware processing and response capture

Use `--process-every N` to ask for an analysis or recollection after every N complete units. A section may override the interval with `Process Every: N`; `0` disables automatic processing for that section. A trailing partial group is also processed. Knowledge and Instructions are grouped by nonempty paragraphs, Journal by dated entries, and Chat by dated conversation episodes. The instruction varies with the type and source: personal journals are autobiographical, third-party journals remain attributed to their authors, conversations preserve speaker attribution, knowledge is summarized, and instructions are reviewed for application.

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

**Release status:** The code has not yet been verified against a live Nomi API. Do not use it for irreplaceable production data until the full mocked API regression suite and a live disposable-Nomi test pass.
