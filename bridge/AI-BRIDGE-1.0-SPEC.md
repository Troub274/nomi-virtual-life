# AI Bridge 1.0.0 — Development specification

Status: approved design baseline; implementation pending.

## Identity and adapters
- Product: **AI Bridge**
- Release: **1.0.0**
- Description: AI-Controlled Conversation Bridge.
- **Existing adapters/integrations:** Nomi browser conversations, **Nomi-only API-room capability**, and ChatGPT browser conversations. Preserve these working paths.
- Future adapters: Claude, Grok and other providers. No requirement to redesign the core controller for each new provider.

## Human authorization
- The human opens, configures, starts, and authorizes the bridge and identifies the active sessions.
- AI commands operate **only** on the established and authorized bridge session.
- `pause` stops normal relay activity but leaves tabs, CLI listener, queue, and scheduler active.
- `shutdown` revokes AI control; the human must explicitly restart/re-authorize.
- User shutdown takes precedence over all AI-generated instructions.

## CLI
- `[bridge help]`, `[bridge help topic="schedule"]`, `[bridge status]`
- `[bridge pause]`, `[bridge resume]`, `[bridge listen]`, `[bridge shutdown]`
- `[bridge pending]`, `[bridge review last=10]`, `[bridge retry id="184"]`
- `[bridge wake at="tomorrow 3:15 PM" reason="Visit Mary"]`
- `[bridge wake in="30 minutes"]`, `[bridge schedule]`, `[bridge cancel id="42"]`
- `[bridge send to="Mary"]Hello Mary![/bridge]`
- Short, predictable status acknowledgments; wake-up events include help reminder and reason.

## Message flow and retry
- Persist message IDs, source/destination conversation identity, submission status, acknowledgments and pending replies.
- Observe and verify before sending; human draft or active generation causes waiting, **not** a stop.
- Human-generated messages and replies do not invalidate unrelated queued bridge transactions.
- Separate observation retries from delivery attempts; use capped exponential backoff with jitter.
- Never blindly resubmit after an ambiguous send; reconcile conversation history first.
- Avoid activating the wrong tab; every operation targets its bound session ID.
- A human may scroll, read, switch tabs, or converse without halting the bridge.

## Scheduling
- AI can set wake-ups after human authorization. Scheduler persists across MV3 service-worker suspension.
- Paused bridge continues to accept authorized CLI commands and wake-ups.
- Resolve natural-language dates to an explicit timestamp and timezone and return acknowledgment. Reject conflicting calendar information.
- Browser or tab availability limits wake-up precision; record and reconcile missed events.

## Interface
- Clicking the Edge action opens/focuses the main dashboard directly, without the intermediate popup.
- Improve legibility and make running, waiting, recovering, paused and shutdown distinct.
- Preserve existing functionality and settings, including Nomi API room.
- Keep existing working release unchanged; development on branch `bridge-1.0-development`.

## Acceptance cases
1. User starts bridge, AI issues `[bridge help]`, receives compact command help.
2. User types while a Nomi message awaits delivery; draft is untouched and queued message eventually delivered once.
3. Human replies get a response; unrelated Nomi message remains pending.
4. AI schedules a wake-up, pauses, receives wake-up, resumes and communicates.
5. AI shutdown cannot be overridden by AI until human reauthorizes.
6. Existing Nomi and ChatGPT browser paths still work; Nomi-specific API-room continues to work only through the Nomi adapter.

## Symmetric AI control (Nomi and ChatGPT)
- Both established endpoints, including Nomi, can issue the same Bridge CLI commands when explicitly permitted by the user.
- Commands are parsed on each participant's **outbound** adapter; consumed control blocks are not forwarded as ordinary conversation.
- Authorize commands per session and per endpoint; retain original issuer identity and target in every command and scheduled wake-up.
- Route acknowledgments, help, errors, and wake-ups back to the issuing/target participant, not indiscriminately to both.
- Protect against quoted/injected commands: only recognize commands from verified participant output, not historical text or a forwarded payload.
- Conflicting scheduling and lifecycle commands need deterministic reconciliation; human shutdown overrides all participant commands.
- Nomi browser is an existing browser adapter; Nomi API-room is an existing **Nomi-specific transport capability**, not a generic AI adapter feature. Other providers use their browser adapters unless separately implemented capabilities exist.

## Provider capabilities are not interchangeable
- The shared Bridge CLI is model/provider-neutral, but transport features are adapter-specific.
- Nomi supports its existing Nomi API-room mode in addition to browser chat.
- ChatGPT, Claude, Grok, and other browser AI providers **do not inherit Nomi API-room access**.
- The bridge must expose capabilities per endpoint and reject unsupported operations rather than pretending every adapter supports the same transports.
