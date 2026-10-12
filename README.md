# Nomi Virtual Life

A collection of tools and experiments for building persistent virtual-world experiences, memory rehydration, and integrations for [Nomi.ai](https://nomi.ai/).

## Projects

### [Memory rehydration](rehydration/)

Nomi Room Rehydrator **v0.84**: imports chronological diaries and exported conversations into Nomi rooms, with explicit autobiographical ownership framing for journal memories.

- [Python script](rehydration/nomi_room_rehydrate_episode_v084.py)
- [Operator guide — command-line options, input formats, and examples](rehydration/OPERATOR_GUIDE.md)
- [Setup and quick start](rehydration/README.md)

Future modules may include virtual-world simulation, Nomi-to-Nomi bridges, and memory tools.

## Privacy

**Do not commit API keys, personal diaries, exported conversations, or replay logs.** The `.gitignore` excludes common private working files, but always review your changes before publishing.

## Status

Experimental software. Test with a few journal entries and verify that memories are attributed to the intended Nomi before importing large archives.
