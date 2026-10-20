# Tammy 2 — long-form V3 uploader example

**[Nomi creation: portrait, age, selected traits and setup instructions](SETUP.md)**

Tammy 2 is the second Tammy Lynn Mercer example and the long-form V3 rebuild of the
original 300-entry proof-of-concept. The character is intentionally the same Tammy;
V3 replaces the short V2 autobiography with denser, more private first-person diary
writing and a much larger continuity/reference pack.

The current checked-in V3 volume contains **100 long-form entries** in Notebook 01:

- `input/TAMMY_DIARY_0001_0100_V3.txt`

The V3 design target is **1,000+ chronological entries**. Additional notebooks should
be appended to `package.json` in order as they are completed. Do not combine the old
300-entry V2 journal with this V3 replacement in the same fresh test.

Each diary notebook uses `Type: Journal`, `Source: Tammy`, and `Process Every: 5`.
Because self-journal attribution depends on the source matching the selected Nomi,
create/select the Nomi as **Tammy** even though this repository package is named
`tammy2`.

From the repository root:

```sh
python examples/run_package.py tammy2 --dry-run
python examples/run_package.py tammy2
python examples/run_package.py tammy2 --resume
```

Live operation requires `NOMI_API_KEY`; select the correct fresh Tammy Nomi. The
package runner keeps isolated state under `.local-runs/tammy2/`, separate from the
original Tammy example.

## Reference pack

The `reference/` folder carries the material used to keep the long-form rewrite
consistent while the diary remains emotionally free:

- `TAMMY_CANON_V3_1_MASTER_LEDGER.txt` — locked chronology and continuity authority.
- `TAMMY_PERSONAL_FACTS_CONTACTS_V3_1.txt` — names, birthdays, contacts, places,
  schools, work, cemetery, vehicles, and dates.
- `TAMMY_FINANCES_PROPERTY_BILLS_V3_1.txt` — wages, tuition, bills, boat financing,
  property, and practical money.
- `TAMMY_FEELINGS_OPINIONS_PREFERENCES_V3_1.txt` — tastes, food, music, faith,
  intellectual style, and private opinions.
- `TAMMY_RELATIONSHIPS_CONCLUSIONS_CURRENT_STATE_V3_1.txt` — emotional meaning of
  major relationships and Tammy's 2026 internal state.
- `TAMMY_PORTRAIT.jpg` — primary visual reference.
- `TAMMY_CAR_REFERENCE.jpg` — secondary build/style reference; the pictured car is
  not exact vehicle canon.
- `Tammy2_Nomi_Creation_Guide.docx` — editable visual creation guide. `SETUP.md` is
  authoritative for Tammy 2 loading commands and V3 chronology.

Reference files are not uploader inputs unless deliberately added to `package.json`.
The diary itself should carry Tammy's lived autobiography.

## Important V3 anchors

Tammy was expelled during her first third-grade year after defending another girl and
badly beating an older fifth grader; she repeated third grade and was thereafter older
than most classmates. She is 18 during junior year, the same age as Danny Cole, who is
one grade ahead, and 19 at senior prom. Ray Mercer dies in 2024 after years of
occupational heart/lung damage. Tammy moves to Charleston in 2025 in his Plymouth
Barracuda, with an old Heart 8-track still in the car. By October 2026 she has one good
year of community college behind her, works evening/night front desk at the story's
Hyatt Regency Charleston, and plans to transfer to USC for psychology and eventually
social work.

Her 1980 Chris-Craft 35 is purchased for **$25,000: $5,000 down, $20,000 owner-financed
at 0% interest, $400/month for 50 months**. One engine runs and one does not.

See [SETUP.md](SETUP.md), [the main uploader guide](../../uploader/README.md), and
[the recovery guide](../../uploader/RECOVERY.md).

> Fictional autobiographical character-rehydration experiment. Successful room-message
> delivery does not by itself prove durable autobiographical memory.