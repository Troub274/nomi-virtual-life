# Chat Bridge changelog

## Main branch changes — 2026-11-14

- API Room reply retry delays now adapt to the observed average reply time. Stop, ambiguous-error recovery, and content delivery rules are unchanged.

## 0.4.3 — 2026-10-18

- Adds Heartbeat as the fourth mode: one ChatGPT tab, a user-defined phrase, startup instructions, a configurable 10-second default repeat delay, `[sleep]`, and `[sleep nHRS]`.
- Promotes the World Observer work from the 0.4.2 development branch: optional read-only Nomi private-chat monitoring, room-only fallback, retained history, one-shot listening, command validation, reply diagnostics, and original-GPT-tab reconnect/recovery.
- Replaces accumulated setup/version notes with current installation, mode, recovery, persistence, and development guides. Documents the existing one-session-per-profile limit.
- Preserves Direct Chat, Group room, and API Room management. The legacy Windows desktop wrapper is not upgraded by this release.
- Validation: 151 automated tests pass. These are fixture/mock tests; this release process does not send live ChatGPT or Nomi messages.

## Earlier production versions

- **0.4.1:** API room description editing and confirmed room deletion.
- **0.4.0:** Persistent single-Nomi API Room mode and checkpoint recovery.
- Earlier versions introduced two-chat relay and browser group-room support. Historical source and notes remain in Git history.

## Unified interface development branch — November 2026

This history comes from the separate `bridge-unified-interface` branch. The development builds have their own version labels.

- Added a shared Window 1 command interface and private status, help, pending, and lifecycle responses across Direct, Group, and API Room modes.
- Added optional raw forwarding with AI-CLI disabled, and recorded the authorization for raw API Room sends in the checkpoint.
- Added Nomi private-chat Heartbeat as a configurable target alongside ChatGPT.
- The 1.0.45 development work repaired controller dispatch, ensured command-looking Nomi replies are forwarded as data, and added a one-time Direct peer reply timeout and regression coverage for sequential commands.

[Unified interface branch history](https://github.com/Troub274/nomi-virtual-life/commits/bridge-unified-interface/bridge/)