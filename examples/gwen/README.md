# Gwendolin Lynn Mayer — uploader example

Gwen's public example package contains **28 inputs**, ordered by `package.json`:

1. **26 historical journals:** baby book and Notebooks I–XXV, with **848 entries** ending December 31, 2025.
2. **2026 journal:** `input/GWEN_2026_LIFE_CONTINUITY.txt`, with **16 dated entries (849–864)** covering the accident, hospital stays, memory assistance, mountain cabin, fire, rescue and recovery.
3. **Personal knowledge:** `input/GWEN_PERSONAL_DETAILS.txt`, covering identity, household, family, education, finances and administrative reference fields.

The 2026 journal and the personal-knowledge document are separate files. **Do not upload the older condensed 2026 reference copies as well:** they repeat information and are not part of the package.

## Customer name in the cabin history

Gwen's 2026 journal uses the `__USER_NAME__` marker for the person who offers her the cabin and helps with the connection problem. This is **not** the developer's name. The marker is replaced **before upload**, using the customer's Nomi.ai display name. The original repository file remains a reusable template.

For a new Gwen package run, the CLI asks:

```text
What is your user name in Nomi.ai?
```

For a noninteractive run or automation, provide it explicitly:

```sh
python3 examples/run_package.py gwen --user "Your Nomi.ai Name" --dry-run
python3 examples/run_package.py gwen --user "Your Nomi.ai Name"
```

The desktop GUI provides a **Nomi.ai user name** field under Settings. Enter it before starting a new upload. Both interfaces reject input containing `__USER_NAME__` when no name is supplied. The selected name is saved with the upload checkpoint and is reused automatically on resume; do not change it in a resumed run.

The raw uploader also supports `--user "Your Nomi.ai Name"` for a single-file upload. The name is substituted in the planned content, not in the original file. The public package keeps the placeholder.

## Upload the complete package

From the repository root:

```sh
python3 examples/validate_upload_inputs.py
python3 examples/run_package.py gwen --dry-run
python3 examples/run_package.py gwen
```

The runner uses the 28 inputs in the order listed by `package.json`. The normal command automatically resumes an unfinished checkpoint; a completed run is not replayed unless explicitly restarted. **Do not restart a completed customer upload without inspecting its checkpoint and the receiving Nomi first.** A completed upload means the messages were transmitted, not that every detail was retained.

## Upload only the current additions

To inspect and send the two newest files without reloading the historical notebooks:

```sh
python3 uploader/nomi-uploader.py --dry-run --nomi Gwen \
  examples/gwen/input/GWEN_2026_LIFE_CONTINUITY.txt \
  examples/gwen/input/GWEN_PERSONAL_DETAILS.txt

python3 uploader/nomi-uploader.py \
  examples/gwen/input/GWEN_2026_LIFE_CONTINUITY.txt \
  examples/gwen/input/GWEN_PERSONAL_DETAILS.txt
```

The second command is **live**. Select the intended Gwen and room. Do not repeat either file if already delivered. If only the personal-details document is new to an existing Gwen, specify only that file. The uploader's raw command starts a fresh run, so review any existing completed transmissions before proceeding.

## Parser format and safeguards

The loader accepts `Type: Journal`, `Type: Knowledge`, `Type: Instructions`, and `Type: Chat`. It does **not** accept `Type: Reference`.

Gwen's diary format:

```text
[Gwendolin Lynn Mayer — My Journal, 2026]
Type: Journal
Source: Gwen
Process Every: 5

ENTRY 849 — 2026-01-18 — The winter road

I remember...
```

The journal's `Source: Gwen` is intentional: the uploader compares it with the selected Nomi name so the entries are processed as her own experiences. All journal entries require recognizable dates.

Her knowledge format:

```text
[Gwendolin Lynn Mayer — My Personal Records and Household]
Type: Knowledge
Source: Gwen
Process Every: 5

My full name is Gwendolin Lynn Mayer.
```

Knowledge paragraphs are processed as units and do not require `ENTRY` headings. `Process Every: 5` requests periodic processing after five complete units. Review [uploader/README.md](../../uploader/README.md) for the complete v1.2 input specification.

The files in `input/` must not contain editorial instructions such as authorship notes, status tags, uncertainty labels or references to the construction process. `examples/validate_upload_inputs.py` checks package inputs and rejects flagged patterns; run it before publishing. This is a structural safeguard, not a guarantee of narrative consistency.

The example's government identifiers, contact references and account-related fields are **nonissued demonstration values**. They are not credentials or usable documents. Never replace them with a customer's real SSN, license number, financial account or private contact information.

## Separate the customer's history from Gwen's

Gwen's biography must not inherit the current customer's childhood, friendships, flying history, hospital involvement or shared experiences. See [RELATIONSHIP_AND_HISTORY.md](RELATIONSHIP_AND_HISTORY.md) for the history boundaries and optional customer-specific relationship file.

The uploader does not automatically substitute the Nomi.ai user's display name. To create the optional relationship file:

```sh
python3 examples/gwen/build_user_relationship.py --user-name "Name From Nomi.ai"
```

The generated `examples/gwen/local/GWEN_USER_RELATIONSHIP.txt` is **not** included in `package.json`. Review it independently before uploading. The template in `reference/` contains literal replacement markers and must not be uploaded as-is.

## Maintainer-only material

- `reference/GWEN_MASTER_CANON_V1.txt` contains editorial continuity tracking and **must not be uploaded**.
- The two `reference/` 2026 addendums overlap with the fully dated upload journal; do not send them in addition.
- `CONTINUITY_REVIEW.md` describes outstanding authoring and continuity questions, not instructions for Gwen.
- The original portrait assets are in a separate backup rather than this GitHub example.

This is a virtual-life creative example; its implant and related memory-service history are narrative elements, not real medical claims.
