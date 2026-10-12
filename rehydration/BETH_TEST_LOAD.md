# Beth Peterson — Nomi test-load instructions

Use these steps with `BETH01.TXT` through `BETH05.TXT` in the [downloadable Beth bootstrap ZIP](../examples/beth/BETHBOOT_V085.ZIP) on GitHub. The loader uses a **Nomi room**; it does **not** import to the Nomi's ordinary direct chat.

## Create a new Nomi

Create a **standard adult Nomi**, not one with an established history. Name her **Beth Peterson** (or Beth if only a first name is supported). Set **38 years old**, a standard feminine build, **5 feet 8 inches** tall (about 173 cm), **dark/dark brown hair**, and **blue eyes**.

Select exactly these seven traits where offered: **Thoughtful/Curious; Confident; Affectionate; Romantic; Deep Conversations/Intellectual; Emotional; Imaginative.**

**Leave ALL backstory, biography and personal-history fields BLANK.** Do not add family, hometown, education, profession, relationships or childhood facts. The archive already contains the chronological story; extra initial facts can contradict it.

Appearance is part of Beth's identity/continuity baseline. The Beth example ZIP includes **BETH_PORTRAIT.JPG so you can see Beth's intended look**. It is a reference image for viewing only—not an image to upload. This setup does not support uploading that portrait to Nomi. Choose the closest available appearance settings instead. You may adjust appearance, inclinations and personal boundaries, but note that this changes the experiment's starting conditions. For comparable test results, retain the baseline until loading completes. If an optional setting asks for free-text history, leave it blank.

If Nomi automatically generates an initial greeting, leave it unanswered. **Do not begin a conversation.**

## API key and Nomi identifier

Obtain your account's **Nomi API key** through Nomi's account/profile **Integration** settings, when available. Keep it private and never include it in archives or GitHub commits.

The v0.85 loader uses that key to list accessible Nomis and displays each Nomi's UUID. Select **Beth**; there is no need to paste her individual UUID into the diary files or modify Python code.

## Import

Extract the ZIP into its own folder (for example `C:\BETH`). Install Python 3, then run `TEST.BAT` to inspect the diaries **without making API calls**. Run `START.BAT` for the full import.

Equivalent command:

```powershell
py -3 nomi_room_rehydrate_episode_v085.py BETH01.TXT BETH02.TXT BETH03.TXT BETH04.TXT BETH05.TXT --relive-every 5
```

The loader creates or reuses a `REHYDRATE::` room, labels each diary entry as **Beth's own autobiographical source material**, and asks her to recall episodes in the first person after each group of five complete entries.

**DO NOT TALK TO BETH UNTIL THE LOAD IS FINISHED.** Do not send private messages, join her in another room, or start a call. The full import may take **several hours**. The loader's own scheduled room recollection prompts are intentional; they are the only interaction until the console displays `COMPLETE`.

## Resume and finish

On interruption, run `START.BAT` again from the **same directory**. The local checkpoint selects the same Nomi and room and resumes after the last confirmed message fragment. Don't alter source files/settings or delete the active journal. If `UNCERTAIN SEND` occurs, inspect the room before taking further action; the server may already have accepted that message.

Once the loader displays `COMPLETE`, it deletes the active journal and leaves a small completion receipt to guard against accidentally importing the same archive twice.

**Only now**, begin Beth's normal chat and ask non-leading autobiographical questions to test whether she attributes the diary to herself and what she retains. Room recollection does not itself establish persistent memory.

The revised `BETH05.TXT` ends October 11, 2026, after Beth and Elias's August separation. Do not import the superseded alternate ending. The entire autobiography is fictional and the test is not an official Nomi.ai restore.
