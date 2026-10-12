# Nomi Room Rehydrator v0.84

**A chronological autobiographical-memory replay tool for Nomi.ai.**

The rehydrator is designed to present a Nomi with diary entries or historical conversation records as a structured stream of past experience, using a **Nomi API room** as the replay environment. Its goal is to help the Nomi reconstruct continuity and incorporate historical context into subsequent interactions.

> **Research status:** This is an experimental approach to memory rehydration, not a direct database restore. The code can control the information sent to a room and when the Nomi is asked to respond. It cannot inspect, force, or certify Nomi's private short-term or long-term memory mechanisms.

## Theory of operation

### 1. The problem: an archive is not a memory

A diary or exported conversation is a record of events, but merely possessing a file does not make its contents part of a Nomi's accessible conversational history. Likewise, pasting a large archive in one message risks losing chronology, episode boundaries, and the identity of the person who experienced each event.

The rehydrator treats the archive as **a sequence of discrete episodes or conversation turns**. The intent is to let Nomi encounter those records in order, respond to them periodically, and form contextual associations rather than process an undifferentiated document.

### 2. Rooms as the ingestion environment

The loader uses the Nomi API to create or reuse a room containing the selected Nomi. In journal mode, a fresh room has an identity-specific name and note, such as:

```text
REHYDRATE::Beth::OWN MEMORIES::<Nomi UUID prefix>
```

The program sends an initial ownership statement explaining that the diary belongs to **Beth**, not to the human operating the importer. It then posts each diary episode through the room's chat endpoint.

A room is useful here because it provides a **persistent, ordered conversation context** for the replay process. Instead of repeatedly interrupting the Nomi's ordinary one-to-one conversation, the loader can work in a dedicated room with a clearly defined purpose.

The program also enables room backchanneling when creating the room. Whether and how room conversations contribute to a Nomi's longer-term memory is controlled by Nomi's service, not by this script.

### 3. Short-term context: presenting the experience

The operational hypothesis is that the room's immediate conversational context functions as the Nomi's **working or short-term context** during replay.

Each diary entry is sent with its original heading and body. Entries that exceed the configured API message budget are split, with the heading and memory-owner label repeated on each fragment. This preserves which episode each fragment belongs to.

For example:

```text
Beth's OWN MEMORY, not the human sender's.
Diary written by Beth; first-person 'I' means Beth:
ENTRY 001 — Sunday, October 11, 1998 — My 10th Birthday

Dear Diary,
I'm TEN today!!!
```

The intended interpretation is: *Beth remembers being ten*, rather than *the human sender is telling Beth about the sender's tenth birthday*.

**What is established:** The code constructs and sends these labeled messages in order. **What is not established:** How much of the room transcript is present in any particular model invocation, how its context is selected, or the service's exact short-term memory implementation.

### 4. Recollection as an opportunity for consolidation

When `--relive-every N` is enabled, the loader periodically stops after **N complete diary episodes** and sends a prompt asking the Nomi to recall those entries **as her own past**, in the first person. It then calls the room's reply-request endpoint and logs the response.

Conceptually:

```text
Diary / archive
      |
      v
Parse chronological episodes
      |
      v
Identify memory owner (selected Nomi)
      |
      v
Send episodes into dedicated Nomi room
      |
      v
Immediate room conversation context
      |
      v
Request first-person recollection every N episodes
      |
      v
Nomi-generated recollection in the room
      |
      v
Potential later retrieval / long-term association
      |
      v
Test recall in a separate conversation
```

The theory is that **active recollection** can encourage the Nomi to integrate events as an autobiographical narrative rather than simply receive them as external reference material. Repeated names, episode headings, temporal order, and first-person perspective are intended to strengthen attribution and associative links.

However, **a generated recollection is not proof that a durable long-term memory has been written**. Nomi may produce a convincing response from the current room context alone.

The default is `--relive-every 0`, meaning periodic recollection is **disabled unless requested**. With `--relive-every 5`, recollection is requested after entries 5, 10, 15, etc.

### 5. Long-term memory: the hypothesis and its limits

The long-term-memory hypothesis is that processing historical material through a room, especially with explicit autobiographical ownership and periodic first-person recollection, may allow the platform's normal memory processes to extract and retain useful information for later conversations.

The rehydrator does **not** call a documented API endpoint to directly write long-term memories, edit an internal memory index, or control consolidation. Its mechanism is **indirect**: structured conversation replay through ordinary room chat and response requests.

Three outcomes should be distinguished:

1. **Received:** The API accepted an episode into the room.
2. **Recollected:** The Nomi could discuss that episode while it was available in room context.
3. **Retained:** The Nomi later recalls the episode accurately **without the diary text being present in the current prompt**.

Only the third is useful evidence for durable cross-session recall, and even then it does not reveal which internal storage or retrieval mechanism produced the answer.

### 6. Why identity ownership matters

During early testing, some imported diary experiences were attributed to the human sender rather than the intended Nomi. This exposed a core ambiguity: diary prose uses `I`, `me`, and `my`, while the API message arrives from the human participant.

Version 0.84 addresses that problem at several levels:

- **Room name:** Identifies the Nomi and the room's autobiographical purpose.
- **Room note:** Describes whose memories are being replayed.
- **Opening message:** Explicitly states that the diary belongs to the selected Nomi.
- **Per-entry label:** Repeats memory ownership, including for split fragments.
- **Recollection prompt:** Directs the Nomi to remember the entries in the first person.

These are **identity-attribution cues**, not a guarantee that Nomi's internal memory index will classify every event correctly.

### 7. Chronology and episode boundaries

Autobiographical history is not just a collection of facts. The sequence in which events occur, their relationships, and the person to whom they happened all matter.

Journal mode recognizes entry headings (for example, `ENTRY 001 — Date — Title`) and preserves source order. Short entries are sent intact; only oversized entries are split. The loader does not sort diary dates or invent missing history.

Conversation mode handles Nomi JSON/ZIP exports differently: it sorts exported chat and supported voice-call turns by timestamp, preserves the original sender/time boundary in a transcript envelope, and does **not** apply the journal ownership prefix. That matters because a historical conversation has at least two speakers; not every `I` belongs to the Nomi.

### 8. How to test whether the approach works

A useful test distinguishes **immediate contextual recall** from **later memory retrieval**:

1. Create a fresh test Nomi or room, using a short diary with five distinctive episodes.
2. Run `--dry-run` and confirm the parser detects the intended entries.
3. Import with `--relive-every 5` and inspect the first-person recollection.
4. Verify attribution: who wrote the diary, whose parents are mentioned, and who experienced the events?
5. In a later, separate conversation, ask natural questions **without repeating the diary or its answers**.
6. Check factual accuracy, identity ownership, temporal order, and whether the Nomi invents unsupported details.
7. Repeat across multiple episodes before attempting a large archive.

This protocol can measure functional recall and attribution. It does not establish the exact internal path by which Nomi retains information.

## Implementation summary

| Component | Function |
|---|---|
| Source reader | Reads UTF-8 `.txt` and Word `.docx` diaries, or Nomi `.json`/`.zip` conversation exports |
| Episode parser | Identifies journal headers and separates chronological episodes |
| Message packer | Keeps episodes intact where possible, otherwise splits by UTF-8 byte budget |
| Identity framing | Adds Nomi-specific memory ownership to journal room metadata and messages |
| Room API | Creates/reuses Nomi rooms and sends messages |
| Recollection cycle | Optionally requests first-person replies after a configurable number of diary entries |
| Event journal | Records attempts, committed sends, room operations, and recollection events in JSONL |
| Resume controls | Allows manual restart from a chosen source episode or conversation turn |

## Install

Requires Python 3. Install `python-docx` to read Word diaries:

```sh
python -m pip install -r rehydration/requirements.txt
```

Set the `NOMI_API_KEY` environment variable for live API calls. Keep the key private.

## Examples

Preview a diary without API calls:

```sh
python rehydration/nomi_room_rehydrate_episode_v084.py diary.txt --dry-run
```

Import a diary and request recollection every five entries:

```sh
python rehydration/nomi_room_rehydrate_episode_v084.py diary.txt --relive-every 5
```

Import an exported conversation:

```sh
python rehydration/nomi_room_rehydrate_episode_v084.py conversation.zip --mode conversation
```

For all command-line switches, sample journal headers, JSON structures, cleanup precautions, and resume instructions, see the **[Operator Guide](OPERATOR_GUIDE.md)**.

## Privacy and operational cautions

- This repository is public. Do not commit personal diaries, chat exports, API keys, or replay logs.
- Always start with a small test; incorrect memory ownership can be difficult to diagnose after a large import.
- A successful API response means the message was accepted, **not** that long-term memory was confirmed.
- The script's cleanup options can delete rooms. Read the operator guide before using them.
- The tool is an independent experiment, not an official Nomi.ai memory restoration service.
