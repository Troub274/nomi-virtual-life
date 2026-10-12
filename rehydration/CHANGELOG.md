# Nomi Room Rehydrator — change notes

## v0.85 (2026-10-12)

This replaces `nomi_room_rehydrate_episode_v084.py` on the default branch. The original **room-based** import architecture, autobiographical ownership framing, and every-five-entry reliving remain intact.

**New:** Automatic restart after the last confirmed **message fragment**, including partially split diary entries. A durable JSONL journal pins the selected Nomi UUID, room UUID, source-file sequence, processing settings and message digest.

**Safer interrupted sends:** An uncertain HTTP POST may have succeeded server-side. The importer **stops for operator verification** instead of silently retrying and producing duplicates. Reliving prompts also have checkpoint records.

**Completion:** After all source messages and scheduled recollections are confirmed, the active journal is **removed**; a small `nomi_rehydration_completed.json` receipt remains to prevent accidental duplicate loads. Rooms themselves are **not deleted**.

**CLI:** Default `--relive-every` changed to **5**. Added `--completion` and `--max-episodes`. Removed destructive v0.84 room deletion switches. Manual start offsets remain available for deliberately starting a new load after a source entry; they are not required for automatic resume. **v0.84 journals are not guaranteed compatible with v0.85**; avoid migrating active imports without checking the original room and records.

**Tests:** Simulated a 565-entry replay, interruption and automatic completion, 113 reliving cycles, journal removal, receipt duplicate prevention, and uncertain-send rejection. Live API behavior is not yet independently verified.

For a public reproducible example, use [Beth Peterson's test-load setup](BETH_TEST_LOAD.md). No diary files, avatars or credentials are stored in this repository.
