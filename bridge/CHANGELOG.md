# Release notes

## 1.0.44 — 2026-11-02 (development)

- Fixes the GPT turn-ID availability error in 1.0.43: current ChatGPT UI variants may identify assistant turns with `data-turn-key`, `data-chatgpt-search-unit-key`, or other stable identity attributes rather than numbered `conversation-turn-N` elements.
- Direct mode now records a ledger of **consumed GPT logical-turn keys** (not text fingerprints, DOM message counts or elapsed times). Two genuine GPT turns may send identical text; repainting an already-consumed turn does not authorize a second transaction.
- The selected identity scheme is held stable for the session. A mid-session layout change that makes turn identity ambiguous fails closed instead of replaying a prior command.
- Adds targeted round-trip compatibility tests for GPT→GPT, Nomi→GPT, and Nomi→Nomi alongside GPT→Nomi regression tests. GPT-as-Tab-1 uses the new identity tracking; Nomi-as-Tab-1 retains existing Nomi reply detection.
- Test validation includes 14 engine scenarios and simulated modern ChatGPT DOM extraction. **A live Edge browser verification remains necessary.**

## 1.0.43 — 2026-11-02 (development)

- Fixes a reproducible Direct-mode source-turn replay regression. A GPT `[bridge send]` was previously eligible for a new transaction if React remounted its message node after Nomi replied; the bridge now consumes the ChatGPT logical conversation-turn number once per completed assistant turn.
- Removes recent text-fingerprint/time-window replay guards from Direct mode. Different GPT turns containing identical text remain independently deliverable; DOM repainting the same turn never creates a new transaction.
- Makes the browser adapter expose the actual ChatGPT `conversation-turn-N` identifier. If identity cannot be read, Direct mode refuses to send rather than silently guessing that a reply is new.
- Restores the user-configured reply settling interval, retains Tab 1 startup help and pause/resume, and updates delivered-turn diagnostics.
- Safely stops an in-progress older Direct-mode session without a logical-turn checkpoint on extension upgrade; inspect chats, Reset and Play to restart.
- Adds regression coverage for source re-render, consecutive identical messages from distinct turns, 30 alternating exchanges, pause/resume, configured settling, and turn-identity extraction. The tests do not establish live browser behavior; verify in Edge before marking production.

## 0.4.3 — 2026-10-18

- Adds Heartbeat as the fourth mode: one ChatGPT tab, a user-defined phrase, startup instructions, a configurable 10-second default repeat delay, `[sleep]`, and `[sleep nHRS]`.
- Promotes the World Observer work from the 0.4.2 development branch: optional read-only Nomi private-chat monitoring, room-only fallback, retained history, one-shot listening, command validation, reply diagnostics, and original-GPT-tab reconnect/recovery.
- Replaces accumulated setup/version notes with current installation, mode, recovery, persistence, and development guides. Documents the existing one-session-per-profile limit.
- Preserves Direct Chat, Group room, and API Room management. The legacy Windows desktop wrapper is not upgraded by this release.
- Validation: 151 automated tests pass. These are fixture/mock tests; this release process does not send live ChatGPT or Nomi messages.

## Previous production versions

- **0.4.1:** API room description editing and confirmed room deletion.
- **0.4.0:** Persistent single-Nomi API Room mode and checkpoint recovery.
- Earlier versions introduced two-chat relay and browser group-room support. Historical source and notes remain in Git history.
