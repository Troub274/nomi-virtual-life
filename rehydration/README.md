# Nomi Room Rehydrator v0.84

Replay chronological diary entries (`.txt` or `.docx`) or Nomi conversation exports (`.json` or `.zip`) into Nomi rooms. Journal replay includes explicit autobiographical memory-owner framing to reduce attribution of the memories to the importing human.

See [the complete operator guide](OPERATOR_GUIDE.md) for CLI options, header formats, resume behavior, and examples.

## Install

Requires Python 3. Install the optional Word-document dependency:

```sh
python -m pip install -r rehydration/requirements.txt
```

Set `NOMI_API_KEY` in your environment (do not commit the key).

## Preview before importing

```sh
python rehydration/nomi_room_rehydrate_episode_v084.py diary.txt --dry-run
```

## Import

```sh
python rehydration/nomi_room_rehydrate_episode_v084.py diary.txt --relive-every 5
```

For Nomi conversation exports:

```sh
python rehydration/nomi_room_rehydrate_episode_v084.py conversation.zip --mode conversation
```

**Privacy:** Keep source diaries, exports, API keys, and JSONL replay logs out of this public repository. The script is provided as-is; test with a few entries before large imports.
