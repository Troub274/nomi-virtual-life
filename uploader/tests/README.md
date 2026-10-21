# Nomi Uploader v1.1 — Test Suite

This suite uses Python's standard-library `unittest` and does **not** require Nomi credentials.

## Run locally

From the repository root:

```powershell
python -m py_compile uploader/nomi-uploader.py uploader/legacy_v085.py examples/beth/prepare_v1.py
python -m unittest discover -s uploader/tests -p "test_*.py" -v
```

The CI workflow `.github/workflows/nomi-uploader-tests.yml` runs the same tests on Windows, macOS, and Ubuntu using Python 3.11 and 3.13.

## Coverage

| File | Tests |
| --- | --- |
| `test_uploader.py` | Dates, sections, journal/chat parsing, Beth converter, prompt intervals, export planning, protected rooms, legacy compatibility |
| `test_specification.py` | Every type/source processing instruction, local/global intervals, ranged prompts, invalid input, multi-session chat, Unicode byte boundaries, export delegation |
| `test_integration.py` | Mocked room creation, complete upload, Nomi reply capture, checkpoint durability, resumed completion, uncertain POST handling, malformed replies, changed manifest, repeated passes, output files |
| `test_packages.py` | Shipped Beth and Chris ZIPs, source hashes, 565/1,000 entries, legacy byte planning, isolated package checkpoints, obsolete CLI rejection |\n| `test_v11.py` | Entry ranges, character-based splitting, 800-character ceiling, checkpoint classification, and exact v1.0 planner compatibility |

### Offline vs live

The offline tests verify deterministic uploader behavior and simulated Nomi API responses. They do **not** establish that the production Nomi API currently accepts every request or guarantees durable memory retention. A separate live test with a disposable Nomi and room is required before a production release.

### Safety invariants

- Never automatically retry a POST after an ambiguous outcome; v1.1 friendly mode requires explicit user authorization.
- Never resume when the content manifest changed.
- Never repeat a confirmed Nomi response request.
- Preserve source and speaker attribution.
- Never delete a room protected by an unfinished checkpoint in the selected directory; completed runs release their rooms.
- Never silently claim a successful run when a reply is missing.

### Known limits

Tests do not yet cover every real-world Nomi export variation, network timeouts from a real service, or a complete live Beth ZIP replay. Local offline results and GitHub Actions results are separate checks.
