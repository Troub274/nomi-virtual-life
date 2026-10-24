# Uploader content-completion checkpoint (October 2026)

## Why this changed

During resumable diary uploads, the Python uploader repeatedly received HTTP 500 `NoReply` and HTTP 400 `RoomNomiNotReadyForMessage` from `POST /rooms/{room}/chat/request`. The browser API-room bridge generally returned replies much faster in normal operation. Both clients post content to `/chat` and request a response using `/chat/request`.

The browser bridge records a durable `content_complete` / `awaiting_reply` transition after all chunks are confirmed, before its next pump handles the reply. The Python uploader previously went from a confirmed prompt POST directly to the reply-request bookkeeping.

## Change

For each prompt awaiting a reply, Python now appends a `content_complete` checkpoint event after the prompt's confirmed content POST and before the `reply_attempt` event. This makes the boundary visible in the append-only audit trail. Existing confirmed-message and reply recovery protections remain in place. No confirmed content is resent just because a reply request failed.

The initial experimental branch briefly contained a redundant one-iteration `while` wrapper; it was removed before merging. The final change does **not** introduce asynchronous processing, new network requests, or a server-readiness poll. The uploader still performs synchronous HTTP calls.

## What we observed

On a Beth resume at pass 1 message 282, an already unresolved reflection initially returned `NoReply` after approximately 55 seconds, followed by `RoomNomiNotReadyForMessage` errors. The user subsequently reported that the run recovered and was working well. Because this was a resume of an already problematic room, the observation does **not** establish that the checkpoint change resolved the errors or unlocked the room.

`RoomNomiNotReadyForMessage` was returned by the reply-request endpoint; it does not imply Python was sending another diary message.

## Operational guidance

- Resume existing runs using their established checkpoint paths. Do not restart merely to pick up this change.
- If a previous reply outcome is ambiguous, inspect the room and checkpoint before authorizing another reply request; the original request may have been processed.
- Compare first-attempt reply success and elapsed time across fresh prompt cycles before attributing improvements to this change.
- If the slow reply issue recurs, inspect room state and the semantics of repeated `/chat/request` calls; do not add arbitrary delays or automatic resends without evidence.

This is a **diagnostic and auditability improvement**, not a proven throughput fix.
