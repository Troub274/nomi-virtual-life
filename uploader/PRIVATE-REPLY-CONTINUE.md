# Continue after a private reply arrives late

If the API returns an error but the Nomi's reply appears in private chat shortly
afterward, use **Reply received — Continue** in Run controls. This action is
separate from Normal Resume and does not request the pending reply again.

1. Wait until you can see the reply in private chat.
2. Select the matching upload run in History, if necessary.
3. Click **Reply received — Continue**. The uploader selects the pending
   checkpoint message automatically and shows its prompt for comparison.
4. Confirm only if that prompt received the reply you saw. Pasting the reply is
   optional. Choose **Keep waiting** if it has not arrived.

Confirmation records a received-reply receipt in the checkpoint, then continues
past that reply. Its prompt and already confirmed source text are not resent.
Future scheduled reflection prompts are still processed normally. If another
uncertain operation remains, continuation stops rather than authorizing a retry.
The uploader does not automatically read or verify the private-chat page.

The button is available when the selected private-chat run has a pending
uncertain reply and the uploader is stopped. Confirm each pending reply if more
than one is listed. You do not need to enter a pass or message number.

Advanced recovery still uses `PASS:INDEX` to identify an exact checkpoint
operation. Pass is the upload repetition, usually `1`; index is the planned
message number, including headers and reflection prompts. For example, `1:499`
means message 499 on the first pass. It is not a paragraph or conversation-turn
count. Those advanced retry controls are not needed to acknowledge an existing
private reply.
