#!/usr/bin/env python3
"""Prepare preserved Beth source diaries for Nomi Uploader.

Reads source/ locally. Never modifies the source diaries.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

EXPECTED_ARCHIVE_SHA256="8139daf9d070120f91b2db27aaa935b639c18f5ba567c799ae987efa7f4fa3af"
ENTRY_LINE=re.compile(r"(?m)^\s*(?:ENTRY|DIARY ENTRY|JOURNAL ENTRY)\s*#?\s*(\d+)\b")
DIARY_NAME=re.compile(r"^BETH0[1-5]\.TXT$",re.I)
DIVIDER="\n"

def diary_sources(archive):
    archive = Path(archive)
    if archive.is_dir():
        return [(name, (archive/name).read_text(encoding="utf-8-sig"))
                for name in ["BETH%02d.TXT" % i for i in range(1, 6)]]
    with zipfile.ZipFile(archive) as z:
        found={}
        for entry in z.infolist():
            name=Path(entry.filename).name.upper()
            if DIARY_NAME.fullmatch(name):
                if name in found: raise ValueError("Duplicate ZIP entry: "+name)
                found[name]=z.read(entry).decode("utf-8-sig")
        required=["BETH%02d.TXT"%i for i in range(1,6)]
        missing=[name for name in required if name not in found]
        if missing: raise ValueError("Missing diary files: "+", ".join(missing))
        return [(name,found[name]) for name in required]

def convert_document(name,text,reflection_every=5):
    # Keep provenance in the manifest, not in content sent to Nomi.
    text="\n".join(
        line for line in text.split("\n")
        if line.strip().casefold() !=
        "this diary is fictional backstory, not the uploader's biography."
    )
    if reflection_every<1: raise ValueError("reflection_every must be >= 1")
    numbers=[int(m.group(1)) for m in ENTRY_LINE.finditer(text)]
    if not numbers: raise ValueError(name+": no numbered diary entries recognized")
    # Keep the original numbering; the uploader's range syntax uses local entry positions.
    if len(numbers)!=len(set(numbers)):
        raise ValueError(name+": duplicate entry numbers")
    # The uploader generates one periodic reflection after every N diary entries.
    # Do not embed episode-specific prompts in the document.
    header=(
        f"[Beth Peterson — {name}]\n"
        "Type: Journal\n"
        "Source: Beth Peterson\n"
        f"Process Every: {reflection_every}\n"
        "Nomi: [nomi], please relive your own journal episodes {first}-{last} "
        "in chronological order. Reflect on the experiences and feelings, "
        "and preserve your memories as your own.\n\n"
    )
    return header+text, numbers

def prepare(archive, output, reflection_every=5, verify_archive=True):
    archive=Path(archive)
    output=Path(output)
    sha=hashlib.sha256(archive.read_bytes()).hexdigest() if archive.is_file() else None
    if verify_archive and archive.is_file() and sha!=EXPECTED_ARCHIVE_SHA256:
        raise ValueError("Unexpected source archive SHA256: "+sha)
    docs=diary_sources(archive)
    converted=[]
    for name,text in docs:
        new_text,numbers=convert_document(name,text,reflection_every)
        converted.append((name,new_text,numbers))
    output.mkdir(parents=True,exist_ok=True)
    manifest={"source_archive":archive.name,"source_sha256":sha,
              "source":"examples/beth/source",
              "reflection_every":reflection_every,
              "files":[]}
    for name,converted_text,numbers in converted:
        dst=output/(name[:-4]+"_V1.TXT")
        dst.write_text(converted_text,encoding="utf-8",newline="\n")
        manifest["files"].append({"file":dst.name,"entry_count":len(numbers),
                                  "first_entry":numbers[0],"last_entry":numbers[-1],
                                  "sha256":hashlib.sha256(dst.read_bytes()).hexdigest()})
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest

def main():
    p=argparse.ArgumentParser(description="Prepare Beth diaries for uploader")
    p.add_argument("archive",nargs="?",default=str(Path(__file__).parent / "source"))
    p.add_argument("--output",default="beth_v1")
    p.add_argument("--relive-every",type=int,default=5)
    p.add_argument("--allow-modified-source",action="store_true",
                   help="Bypass original archive SHA256 check for intentionally modified test archives")
    args=p.parse_args()
    m=prepare(args.archive,args.output,args.relive_every,not args.allow_modified_source)
    print("Prepared %d files, %d entries."%(len(m["files"]),sum(f["entry_count"] for f in m["files"])))
    for f in m["files"]: print("  %s: %d entries"%(f["file"],f["entry_count"]))

if __name__=="__main__":
    main()
