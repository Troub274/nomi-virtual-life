# Tammy — complete long-form journal package

This package contains Tammy Lynn Mercer's complete 1,000-entry first-person journal, from age nine through October 20, 2026, plus private life-reference documents and photographs.

The journal is split into ten ordered files of 100 entries each. Every input section uses `Type: Journal`, `Source: Tammy`, and `Process Every: 5`.

The private reference folder contains Tammy's family dates, contacts, addresses, finances, property, preferences, relationships, education, work, and current-life details.

Run from the repository root:

```sh
python examples/run_package.py tammy --dry-run
python examples/run_package.py tammy
python examples/run_package.py tammy --resume
```

For a clean restoration load, start with a fresh Tammy profile, use the portrait and selected traits from `SETUP.md`, avoid unrelated chat before loading, and load the ten journal files in `package.json` order.
