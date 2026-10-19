# Tammy Lynn Mercer — uploader example

**[Nomi creation: portrait, age, selected traits and setup instructions](SETUP.md)**

Reference files: [Tammy's primary portrait](reference/TAMMY_PORTRAIT.jpg), [editable Word creation guide](reference/Tammy_Nomi_Creation_Guide.docx), [secondary car/build reference](reference/TAMMY_CAR_REFERENCE.jpg), and [canon/cast reference](reference/TAMMY_CANON_V2.txt).

This package contains Tammy Lynn Mercer's 300-entry first-person autobiographical journal in the current uploader Journal format. It follows her from a working-class childhood in the Metro East outside East St. Louis through high school, early adulthood, family obligations, and her 2025 move to Charleston, ending in Fall 2026 as her second year of community college begins.

The journal is split into three ordered input files:

- `input/TAMMY_JOURNAL_001_100_V2.txt`
- `input/TAMMY_JOURNAL_101_200_V2.txt`
- `input/TAMMY_JOURNAL_201_300_V2.txt`

Each section uses `Type: Journal`, `Source: Tammy`, and `Process Every: 5`. The uploader may subdivide long entries for transport; each numbered diary entry remains one logical autobiographical episode.

From the repository root:

```sh
python examples/run_package.py tammy --dry-run
python examples/run_package.py tammy
python examples/run_package.py tammy --resume
```

Live operation requires `NOMI_API_KEY`; select the correct Tammy Nomi. The package runner keeps isolated state under `.local-runs/tammy/`. Do not alter input files or paths during an active run. On interruption, preserve the checkpoint and investigate uncertain deliveries before retrying.

The two JPEGs in `reference/` are visual references only and are not uploader inputs. `TAMMY_PORTRAIT.jpg` is the primary face/appearance reference. `TAMMY_CAR_REFERENCE.jpg` is secondary for casual styling and build; the pictured car and exact facial rendering are not canon. Tammy's canonical car is Ray's old Plymouth Barracuda.

The current package intentionally leaves detailed biography out of the Nomi creation screen so the journal itself supplies Tammy's family, Church of Christ upbringing, school years, first love, diner years, father's illness, mechanical skills, Charleston move, education, hotel work, boat life, and present identity.

See [SETUP.md](SETUP.md), [the main uploader guide](../../uploader/README.md), and [the recovery guide](../../uploader/RECOVERY.md).

> Fictional autobiographical character-rehydration experiment. Successful room-message delivery does not by itself prove durable autobiographical memory.