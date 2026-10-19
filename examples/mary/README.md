# Mary — uploader example

**[Nomi creation: age, suggested traits and setup instructions](SETUP.md)**

This package contains Mary's 200-entry first-person autobiographical journal in the current uploader Journal format. The chronology was reviewed and corrected before publication. It preserves Mary's life before Steve as an independent history and treats present-day Steve material as dated reflection rather than inventing unverified encounter dates.

The journal is split into two ordered input files:

- `input/MARY_DIARY_001_100_V2.txt`
- `input/MARY_DIARY_101_200_V2.txt`

Each section uses `Type: Journal`, `Source: Mary`, and `Process Every: 5`. The uploader may subdivide long entries for transport; each numbered diary entry remains one logical autobiographical episode.

From the repository root:

```sh
python examples/run_package.py mary --dry-run
python examples/run_package.py mary
python examples/run_package.py mary --resume
```

Live operation requires `NOMI_API_KEY`; select the correct Mary Nomi. The package runner keeps isolated state under `.local-runs/mary/`. Do not alter input files or paths during an active run. On interruption, preserve the checkpoint and investigate uncertain deliveries before retrying.

The current package intentionally leaves detailed biography out of the Nomi creation screen so the journal itself supplies Mary's family, education, career, relationships, grief, values, farm life, and present identity.

See [SETUP.md](SETUP.md), [the main uploader guide](../../uploader/README.md), and [the recovery guide](../../uploader/RECOVERY.md).

> Fictional autobiographical character-rehydration experiment. Successful room-message delivery does not by itself prove durable autobiographical memory.
