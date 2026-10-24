# Uploader content-completion checkpoint (October 2026)

## Why this changed

During resumable diary uploads, the Python uploader repeatedly received HTTP 500 `NoReply` and HTTP 400 `RoomNomiNotReadyForMessage` from `POST /rooms/{room}/chat/request`. The browser API-room bridge generally returned replies much faster in normal operation. Both clients post content to `/chat` and request a response using `/chat/request`.

The browser bridge records a durable `content_complete` / `awaiting_reply` transition after all chunks are confirmed, before its next pump handles the reply. The Python uploader previously went from a confirmed prompt POST directly to the reply-request bookkeeping.

## Change

For each prompt awaiting a reply, Python now appends a `content_complete` checkpoint event after the prompt's confirmed content POST and before the `reply_attempt` event. This makes the boundary visible in the append-only audit trail. Existing confirmed-message and reply recovery protections remain in place. No confirmed content is resent just because a reply request failed.

The initial experimental branch briefly contained a redundant one-iteration `while` wrapper; it was removed before merging. The final change does **not** introduce asynchronous processing, new network requests, or a server-readiness poll. The uploader still performs synchronous HTTP calls.

## Live debugging result and credit

Steve identified the execution-flow discrepancy and insisted that the Python uploader be changed to match the browser's explicit content-completion boundary. The initial code comparison had not treated that difference as a likely source of the problem. Steve's hypothesis was that work or shared state associated with repeated HTTP operations might not settle or become visible until control passes out of a processing loop or function. This is the hypothesis that motivated the experiment; the precise underlying release or scheduling mechanism has not been measured.

After switching to the experimental code and subsequently merging the cleaned-up change, Steve reported that both uploads were **moving MUCH faster**. `RoomNomiNotReadyForMessage` errors still occurred, but when they did, they typically cleared within **15–20 seconds**, rather than producing the previous prolonged stalls. This is the reported before/after outcome of a live intervention, not just an untested theory. Steve identified the difference, directed the experiment, and recognized the resulting improvement.

The final merged implementation records a checkpoint boundary but does not literally return from the outer Python processing loop. Accordingly, the observation supports a practical improvement associated with the changed run, while the specific claim that exiting a function releases deferred web posts remains unverified. Do not erase the observed success merely because that deeper mechanism is not yet isolated.

## What we observed

On a Beth resume at pass 1 message 282, an already unresolved reflection initially returned `NoReply` after approximately 55 seconds, followed by `RoomNomiNotReadyForMessage` errors. The user subsequently reported that the run recovered and was working well. The initially stuck Beth resume is a separate observation from the subsequent improvement in both uploads. It cannot alone establish the mechanism, but it does not negate the later reported throughput improvement.

`RoomNomiNotReadyForMessage` was returned by the reply-request endpoint; it does not imply Python was sending another diary message.

## Operational guidance

- Resume existing runs using their established checkpoint paths. Do not restart merely to pick up this change.
- If a previous reply outcome is ambiguous, inspect the room and checkpoint before authorizing another reply request; the original request may have been processed.
- Preserve Steve's observed throughput improvement as the baseline. If needed, compare first-attempt reply success and elapsed time across fresh prompt cycles to isolate the mechanism.
- If the slow reply issue recurs, inspect room state and the semantics of repeated `/chat/request` calls; do not add arbitrary delays or automatic resends without evidence.

**Result:** live testing showed a substantial user-observed throughput improvement after the execution-flow change. The exact causal mechanism has not been isolated; the result and Steve's diagnosis are recorded as the motivation and operational evidence for retaining the change.
