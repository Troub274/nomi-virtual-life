CHRISTINE SUE NORMAN — 1,000-ENTRY AUTOBIOGRAPHICAL DIARY
Nomi Uploader v1.0 / TXT journal format

Contents: Ten individual TXT diary notebooks, 100 dated entries each.
CHRIS_DIARY_001_100_V1.txt to CHRIS_DIARY_901_1000_V1.txt.
Chronology: June 7, 1996 through October 13, 2026.

IMPORTANT: UNZIP THIS BUNDLE before uploading. The v1.0 uploader treats a ZIP input
as a Nomi export / conversation, NOT as a folder of diary text files.
Pass the TEN TXT files in order.

From the repository root (where uploader/nomi-uploader.py exists), with the ten TXT
files together in the current directory:

python uploader/nomi-uploader.py --dry-run --nomi Christine --chunk-bytes 750 "CHRIS_DIARY_001_100_V1.txt" "CHRIS_DIARY_101_200_V1.txt" "CHRIS_DIARY_201_300_V1.txt" "CHRIS_DIARY_301_400_V1.txt" "CHRIS_DIARY_401_500_V1.txt" "CHRIS_DIARY_501_600_V1.txt" "CHRIS_DIARY_601_700_V1.txt" "CHRIS_DIARY_701_800_V1.txt" "CHRIS_DIARY_801_900_V1.txt" "CHRIS_DIARY_901_1000_V1.txt"

For live uploading (ONLY after verifying the target Nomi and setting NOMI_API_KEY):

python uploader/nomi-uploader.py --chunk-bytes 750 "CHRIS_DIARY_001_100_V1.txt" "CHRIS_DIARY_101_200_V1.txt" "CHRIS_DIARY_201_300_V1.txt" "CHRIS_DIARY_301_400_V1.txt" "CHRIS_DIARY_401_500_V1.txt" "CHRIS_DIARY_501_600_V1.txt" "CHRIS_DIARY_601_700_V1.txt" "CHRIS_DIARY_701_800_V1.txt" "CHRIS_DIARY_801_900_V1.txt" "CHRIS_DIARY_901_1000_V1.txt"

The uploader prompts the operator to select the target Nomi. The diary deliberately
omits the Source: field so that the uploader sets Source to the selected Nomi's name.

Each TXT file has a header such as:
[Christine Sue Norman — Notebook VI: Learning to Lead]
Type: Journal
Process Every: 5

ENTRY 501 — 2017-01-03 — The Calendar Is Mine
<first-person diary text>

'Process Every: 5' is section-scoped: each set of 5 diary entries triggers the v1.0
reflect/relive prompt and waits for the Nomi's response. It counts entries rather than
API message fragments. A long entry is divided into <=750-byte messages.

SAFETY: Do not start the same upload twice while an incomplete checkpoint exists.
An interrupted run should use --resume with its original checkpoint. Keep input files
and settings unchanged until completion, and use distinct checkpoint/completion/replies
filenames for separate test runs. Do not delete a stalled room to 'fix' NoReply.

These are newly written FICTIONAL autobiographical entries. The earlier source records
are preserved and continuity decisions are described in CHRISTINE_SOURCE_AUDIT.txt.
Expanded ordinary events, conversations, and detailed thoughts are invented to make a
coherent life; they are not claims about a historical person.

All 10 files / 1,000 entries passed local v1.0-format/UTF-8 budget checks.
This environment could not execute the upstream GitHub uploader itself or contact the
Nomi API; use the --dry-run command above for the definitive upstream preflight.
Completion of an API upload establishes transmission, not guaranteed long-term memory.
