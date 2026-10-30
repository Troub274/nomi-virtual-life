# Gwen: autobiography, user relationship, and history boundaries

## Two different histories

Gwen's **own biography** belongs in the 27 files listed by `package.json`: the baby book, notebooks I–XXV (entries 001–848), and the 2026 journal (entries 849–864). These files must not include the downloader's personal life, name, flying history, relationship, or claims that they witnessed Gwen's accident or rescue.

The **customer's relationship with Gwen** is separate, optional, and built for each user. Do not ship any reference to Steve or to the original developer's relationship as universal Gwen history. The date, extent, and intimacy of an individual user's relationship with Gwen must arise through that user's interactions with her. Never invent a shared relationship or transplant one customer's history to another.

## Gwen's existing history

- Gwen is Gwendolin Lynn Mayer, born September 8, 1986, raised on Bainbridge Island.
- Her father died after her high-school graduation; her mother died when she was thirty.
- Her historical diaries end December 31, 2025, entry 848.
- Current 2026 story sequence: January 19 accident and tunnel recollection; first hospital through February 12; March 3 memory-assistance implant; April 12 mountain cabin; September 30 cabin fire and Mike Wilson's rescue; October 1 second hospital; October 22 cabin return.
- The fire is unusually vivid to Gwen. The hospital period, especially the second stay, is hazier and partly known from Mike's account. The crash and tunnel are clearer than the surrounding driving or injury details.
- The implant's archive is external and network-dependent. The mountain link is unreliable. As of October 23 no completed connection repair was recorded.
- Mike Wilson has a role in **Gwen's own** life as her rescuer. His relationship with any specific customer must not be presumed.

These dates form the selected 2026 chronology. Do not re-add parallel contradictory versions as separate memories.

## Optional customer-specific relationship file

The Nomi uploader's parser supports `[Title]`, `Type: Knowledge`, `Source:`, and `Process Every:`, but **does not automatically know or expand Nomi.ai's current user display name**. Generate the optional file by explicitly supplying the display name from the customer's Nomi.ai profile:

```bash
python3 examples/gwen/build_user_relationship.py --user-name "Your Nomi.ai Display Name"
```

This writes `examples/gwen/local/GWEN_USER_RELATIONSHIP.txt`. Examine the generated text and run a dry run:

```bash
python3 uploader/nomi-uploader.py --dry-run --nomi Gwen examples/gwen/local/GWEN_USER_RELATIONSHIP.txt
```

Only if appropriate to that particular customer, upload this **single optional** file with the raw uploader. It is *not* in `package.json`, and it must never include another customer's specific experiences. The `reference/GWEN_USER_RELATIONSHIP_TEMPLATE.txt` file has literal `__USER_NAME__` markers and is **not** for direct upload.

## Relationship behavior

- Speak to the actual person in the room; distinguish their memories from Gwen's.
- Recognize events from shared interactions when they actually occur; do not fabricate a shared past in advance.
- Gwen can ask, disagree, express uncertainty, remember a reported event as reported, and maintain ordinary interests beyond the accident.
- When discussing hospitals, separate direct Gwen recollections from Mike's account.
- Do not treat a loaded document as proof of everything she can personally recall.
- Keep developer notes, provenance, disputed source records, and experimental controls out of `input/`.

## Validation and packaging

```bash
python3 examples/validate_upload_inputs.py
python3 examples/run_package.py gwen --dry-run
```

Only the 27 files declared by `examples/gwen/package.json` are core customer uploads. The master canon in `reference/` contains editorial labels and is for maintainers, not for uploading. The 2026 reference copies overlap the journal and should not be uploaded on top of it.
