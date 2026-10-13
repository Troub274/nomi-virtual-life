#!/usr/bin/env python3
"""Nomi Uploader 1.0 — source-aware, resumable room uploader."""
import argparse
import datetime as dt
import hashlib
import json
import locale
import os
from pathlib import Path
import re
import sys
import time
import uuid
import zipfile

try:
    from . import legacy_v085 as legacy
except ImportError:
    import legacy_v085 as legacy

VERSION = "1.0"
TYPES = {"knowledge", "instructions", "journal", "chat"}
HEADING = re.compile(r"^\[([^\]\n]+)\]\s*$")
META = re.compile(r"^(Type|Source|Date|Nomi|Nomi Mode):\s*(.*)$", re.I)
ENTRY = re.compile(r"^(?:ENTRY|EPISODE|JOURNAL ENTRY|DIARY ENTRY)\s*#?\s*(\d+)\b.*$", re.I)
SPEAKER = re.compile(r"^([^:\n]{1,70}):\s+(.+)$")
MONTHS = {m.lower():i for i,m in enumerate(("January","February","March","April","May","June","July","August","September","October","November","December"),1)}
MONTHS.update({m[:3]:i for m,i in list(MONTHS.items())})
DATE_RX = re.compile(r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?|(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{1,2}(?:,?\s*'?\d{2,4})?|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)(?:\s+\d{2,4})?)\b",re.I)
DEFAULT_PROMPTS = {
 "knowledge": "[nomi], please learn, summarize, and understand the following information.",
 "instructions": "[nomi], please read, understand, and apply the following instructions when relevant.",
 "journal_self": "[nomi], please revisit these dated entries from your own journal in chronological order.",
 "journal_other": "[nomi], please learn about [source]'s life and understand these experiences as [source]'s, not your own.",
 "chat": "[nomi], please review this conversation, preserving speakers, sequence, and context."
}

def regional_order(override="AUTO"):
    if override != "AUTO": return override
    try:
        locale.setlocale(locale.LC_TIME, "")
        if hasattr(locale,"nl_langinfo"):
            fmt=locale.nl_langinfo(locale.D_FMT).lower()
        elif sys.platform=="win32":
            import ctypes
            buf=ctypes.create_unicode_buffer(128)
            # LOCALE_SSHORTDATE
            ctypes.windll.kernel32.GetLocaleInfoEx(None,0x1F,buf,128)
            fmt=buf.value.lower()
        else: fmt=""
        tokens=re.findall(r"%[dmy]|[dmy]+",fmt)
        tokens=[t.lstrip("%")[0] for t in tokens]
        if "d" in tokens and "m" in tokens:
            return "EU" if tokens.index("d") < tokens.index("m") else "US"
    except Exception: pass
    return "US"

def year_value(y, session_year):
    if y is None: return session_year
    y=int(str(y).lstrip("'"))
    if y < 100: return 1900+y if y>=70 else 2000+y
    return y

def parse_date(value, order, session_year):
    value=value.strip().strip("—–,; ")
    m=DATE_RX.search(value)
    if not m: raise ValueError("No recognizable date in: "+value)
    s=m.group()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}",s):
        y,mo,d=map(int,s.split("-"))
    elif re.fullmatch(r"\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?",s):
        p=re.split(r"[/.\-]",s)
        a,b=int(p[0]),int(p[1])
        if a>12 and b<=12: d,mo=a,b
        elif b>12 and a<=12: mo,d=a,b
        elif order=="EU": d,mo=a,b
        else: mo,d=a,b
        y=year_value(p[2] if len(p)>2 else None,session_year)
    else:
        words=s.replace(","," ").split()
        if words[0].lower()[:3] in MONTHS:
            mo=MONTHS[words[0].lower()[:3]]
            d=int(words[1]); y=year_value(words[2] if len(words)>2 else None,session_year)
        else:
            d=int(words[0]); mo=MONTHS[words[1].lower()[:3]]
            y=year_value(words[2] if len(words)>2 else None,session_year)
    return dt.date(y,mo,d).isoformat()

def read_text(path):
    if path.suffix.lower()==".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(path).paragraphs)
    return path.read_text(encoding="utf-8-sig")

def parse_sections(text, filename):
    sections=[]; current=None; in_header=False
    for line in text.splitlines():
        match=HEADING.fullmatch(line.strip())
        if match:
            if current: sections.append(current)
            current={"title":match.group(1),"type":"knowledge","source":None,"date":None,
                     "prompts":[],"mode":"add","lines":[]}
            in_header=True
            continue
        if current is None:
            current={"title":Path(filename).stem,"type":"knowledge","source":None,
                     "date":None,"prompts":[],"mode":"add","lines":[]}
            in_header=True
        meta=META.match(line.strip()) if in_header else None
        if meta:
            k,v=meta.group(1).lower(),meta.group(2).strip()
            if k=="type":
                if v.lower() not in TYPES: raise ValueError("Unknown type: "+v)
                current["type"]=v.lower()
            elif k=="source": current["source"]=v
            elif k=="date": current["date"]=v
            elif k=="nomi": current["prompts"].append(v)
            elif k=="nomi mode":
                if v.lower() not in ("add","replace"): raise ValueError("Nomi Mode must be Add or Replace")
                current["mode"]=v.lower()
        else:
            if line.strip(): in_header=False
            current["lines"].append(line)
    if current: sections.append(current)
    return sections

def split_units(section, order, session_year):
    kind=section["type"]
    lines=section["lines"]
    if kind in ("knowledge","instructions"):
        return [{"text":"\n".join(lines).strip(),"date":parse_date(section["date"],order,session_year) if section["date"] else None}]
    units=[]; buf=[]; date=section["date"]; label=None
    def flush():
        nonlocal buf
        text="\n".join(buf).strip()
        if text:
            if not date:
                raise ValueError("%s / %s: dated %s content required"%(section["title"],label or "entry",kind))
            units.append({"text":text,"date":parse_date(date,order,session_year),"label":label})
        buf=[]
    if kind=="journal":
        for line in lines:
            em=ENTRY.match(line.strip())
            dm=re.match(r"^Date:\s*(.+)$",line.strip(),re.I)
            heading_date=DATE_RX.search(line) if (em or dm or legacy.is_episode_header(line)) else None
            if em or dm or (legacy.is_episode_header(line) and heading_date):
                flush()
                label=em.group(1) if em else str(len(units)+1)
                if dm: date=dm.group(1)
                elif heading_date: date=heading_date.group()
            buf.append(line)
        flush()
    else:
        # User-created chat: session date or date marker, speaker turns preserved.
        for line in lines:
            dm=re.match(r"^Date:\s*(.+)$",line.strip(),re.I)
            if dm:
                flush(); date=dm.group(1); label=str(len(units)+1)
            else: buf.append(line)
        flush()
        for unit in units:
            if not any(SPEAKER.match(line) for line in unit["text"].splitlines()):
                raise ValueError("Chat section needs speaker-labelled turns: "+section["title"])
    return units

def split_budget(text, budget):
    if len(text.encode("utf-8"))<=budget: return [text]
    result=[]; remaining=text
    while remaining:
        if len(remaining.encode("utf-8"))<=budget:
            result.append(remaining); break
        low,high=1,len(remaining)
        while low<high:
            mid=(low+high+1)//2
            if len(remaining[:mid].encode("utf-8"))<=budget: low=mid
            else: high=mid-1
        if low<1: raise ValueError("Chunk budget too small")
        candidate=remaining[:low]
        cut=max(candidate.rfind("\n\n"),candidate.rfind("\n"),candidate.rfind(". "),candidate.rfind(" "))
        if cut>low//3: low=cut+(2 if candidate[cut:cut+2]==". " else 1)
        result.append(remaining[:low]); remaining=remaining[low:]
    return result

def render_prompt(prompt, nomi, user, source):
    return prompt.replace("[nomi]",nomi).replace("[user]",user or "the user").replace("[source]",source)

def plan_text(files, nomi, user, order, year, chunk_bytes):
    messages=[]
    for filename in files:
        path=Path(filename)
        if path.suffix.lower() in (".zip",".json"):
            # Existing export parser is retained verbatim in legacy_v085.
            raise ValueError("Nomi ZIP/JSON exports: use --legacy --mode conversation for now; v1 native export adapter is pending")
        for section in parse_sections(read_text(path),filename):
            source=section["source"] or (nomi if section["type"]=="journal" else "System")
            units=split_units(section,order,year)
            if not units or not any(u["text"] for u in units): continue
            kind=section["type"]
            default_key="journal_self" if kind=="journal" and source.casefold()==nomi.casefold() else ("journal_other" if kind=="journal" else kind)
            prompts=[] if section["mode"]=="replace" else [DEFAULT_PROMPTS[default_key]]
            intro="\n".join(render_prompt(p,nomi,user,source) for p in prompts)
            intro += "\nSection: %s\nType: %s\nSource: %s"%(section["title"],kind.title(),source)
            messages.append({"text":intro.strip(),"kind":"intro","file":filename,"section":section["title"]})
            for idx,unit in enumerate(units,1):
                label=unit.get("label") or str(idx)
                prefix="Section: %s\nType: %s\nSource: %s\nEntry: %s"%(section["title"],kind.title(),source,label)
                if unit.get("date"): prefix+="\nDate: "+unit["date"]
                room=max(50,chunk_bytes-len((prefix+"\nPart: 999/999\n").encode("utf-8")))
                fragments=split_budget(unit["text"],room)
                for j,frag in enumerate(fragments,1):
                    body=prefix+"\nPart: %d/%d\n"%(j,len(fragments))+frag
                    if len(body.encode("utf-8"))>chunk_bytes:
                        raise ValueError("Chunk exceeds byte limit; increase --chunk-bytes")
                    messages.append({"text":body,"kind":"content","file":filename,"section":section["title"],"entry":idx})
                # Schedule explicitly ranged instructions at their last referenced entry.
                for prompt in section["prompts"]:
                    nums=re.search(r"\b(?:entries|episodes)\s+(\d+)\s*[-–]\s*(\d+)\b",prompt,re.I)
                    if nums and int(nums.group(2))==idx:
                        messages.append({"text":render_prompt(prompt,nomi,user,source),"kind":"prompt","file":filename,"section":section["title"]})
            for prompt in section["prompts"]:
                nums=re.search(r"\b(?:entries|episodes)\s+(\d+)\s*[-–]\s*(\d+)\b",prompt,re.I)
                if nums:
                    if int(nums.group(1))<1 or int(nums.group(2))>len(units):
                        raise ValueError("Prompt range outside section: "+prompt)
                else:
                    messages.append({"text":render_prompt(prompt,nomi,user,source),"kind":"prompt","file":filename,"section":section["title"]})
    return messages

def digest(messages):
    raw=json.dumps(messages,sort_keys=True,ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def record(path, obj):
    with open(path,"a",encoding="utf-8") as f:
        f.write(json.dumps(obj,ensure_ascii=False)+"\n")
        f.flush(); os.fsync(f.fileno())

def records(path):
    if not path.exists(): return []
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]

def create_upload_room(nomi):
    name="UPLOADER::%s::%s"%(nomi["name"],dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    s,p=legacy.api_request_retry("/rooms","POST",{"name":name,"note":"Nomi Uploader v1.0 — persistent processing room","backchannelingEnabled":True,"nomiUuids":[nomi["uuid"]]})
    if not legacy.ok(s): raise RuntimeError(legacy.err_text("create room",s,p))
    rid=p.get("uuid") or p.get("room",{}).get("uuid")
    if not rid: raise RuntimeError("Room create returned no UUID")
    legacy.wait_for_room(rid)
    return rid

def upload(args):
    cp=Path(args.checkpoint)
    old=records(cp) if args.resume else []
    if args.resume and not old: raise ValueError("No checkpoint to resume")
    if old:
        init=old[0]
        nomi={"uuid":init["nomi_uuid"],"name":init["nomi_name"]}
        year=init["year"]; order=init["order"]; room=init["room_uuid"]
        files=init["files"]; passes=init["passes"]
    else:
        nomi=legacy.choose_nomi(legacy.get_nomis()) if not args.dry_run else {"name":args.nomi or "Nomi","uuid":"DRYRUN"}
        year=dt.date.today().year; order=regional_order(args.date_format)
        files=args.files; passes=args.passes; room=None
    if not files: raise ValueError("Specify at least one document")
    messages=plan_text(files,nomi["name"],args.user,order,year,args.chunk_bytes)
    manifest=digest(messages)
    if old and manifest!=init["manifest"]: raise ValueError("Manifest changed: resume requires identical content and options")
    print("Nomi:",nomi["name"],"Date order:",order,"Year:",year,"Messages per pass:",len(messages),"Passes:",passes)
    if args.dry_run:
        for i,m in enumerate(messages,1): print("%4d %-8s %s / %s: %s"%(i,m["kind"],m["file"],m["section"],m["text"][:130].replace("\n"," | ")))
        return
    if not old:
        if args.room:
            room=args.room
            r=legacy.get_room(room)
            if not legacy.room_contains_nomi(r,nomi["uuid"]):
                raise ValueError("Room is not associated with selected Nomi")
        else: room=create_upload_room(nomi)
        record(cp,{"event":"start","run_id":str(uuid.uuid4()),"nomi_uuid":nomi["uuid"],"nomi_name":nomi["name"],"room_uuid":room,"year":year,"order":order,"files":files,"passes":passes,"manifest":manifest})
        old=records(cp)
    attempts={(r["pass"],r["index"]) for r in old if r.get("event")=="attempt"}
    confirmed={(r["pass"],r["index"]) for r in old if r.get("event")=="confirmed"}
    uncertain=attempts-confirmed
    if uncertain: raise RuntimeError("Uncertain POST(s) %s. Inspect room before manual checkpoint repair; no automatic resend."%sorted(uncertain))
    for p in range(1,passes+1):
        for i,m in enumerate(messages,1):
            if (p,i) in confirmed: continue
            record(cp,{"event":"attempt","pass":p,"index":i,"sha256":hashlib.sha256(m["text"].encode()).hexdigest()})
            s,response=legacy.api_request("/rooms/"+room+"/chat","POST",{"messageText":m["text"]})
            if not legacy.ok(s):
                raise RuntimeError("POST outcome uncertain: "+legacy.err_text("send",s,response))
            record(cp,{"event":"confirmed","pass":p,"index":i})
            print("Pass %d/%d message %d/%d"%(p,passes,i,len(messages)))
            if args.delay: time.sleep(args.delay)
    Path(args.completion).write_text(json.dumps({"version":VERSION,"room_uuid":room,"nomi":nomi["name"],"passes":passes,"messages_per_pass":len(messages),"manifest":manifest,"completed_at":dt.datetime.now(dt.timezone.utc).isoformat()},indent=2),encoding="utf-8")
    print("Complete. Room retained:",room)

def utilities():
    rooms=legacy.list_rooms()
    for i,r in enumerate(rooms,1):
        print("%3d  %-45s %s"%(i,r.get("name",""),r.get("uuid","")))
    selection=input("Room number to inspect/delete (Enter to exit): ").strip()
    if not selection: return
    i=int(selection)-1
    if i<0 or i>=len(rooms): raise ValueError("Invalid room number")
    r=rooms[i]; print(json.dumps(r,indent=2,ensure_ascii=False))
    if input("Type DELETE to delete this room, or Enter to keep: ").strip()!="DELETE": return
    if input("Confirm UUID %s: "%r["uuid"]).strip()!=r["uuid"]: return
    legacy.delete_room(r["uuid"])
    print("Deleted",r["uuid"])

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if "--legacy" in argv:
        argv.remove("--legacy")
        return legacy.main(argv)
    parser=argparse.ArgumentParser(description="Nomi Uploader v1.0")
    parser.add_argument("files",nargs="*")
    parser.add_argument("--version",action="version",version=VERSION)
    parser.add_argument("--utility",action="store_true")
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--nomi",help="Dry-run Nomi name")
    parser.add_argument("--user",default="")
    parser.add_argument("--room",help="Reuse existing room UUID")
    parser.add_argument("--passes",type=int,default=1)
    parser.add_argument("--chunk-bytes",type=int,default=750)
    parser.add_argument("--date-format",choices=["AUTO","US","EU"],default="AUTO")
    parser.add_argument("--delay",type=float,default=1)
    parser.add_argument("--checkpoint",default="nomi_uploader_checkpoint.jsonl")
    parser.add_argument("--completion",default="nomi_uploader_completed.json")
    args=parser.parse_args(argv)
    if args.passes<1 or args.chunk_bytes<150: parser.error("passes >=1 and chunk-bytes >=150 required")
    if args.utility: utilities()
    else: upload(args)

if __name__=="__main__":
    try: main()
    except (RuntimeError,ValueError,OSError) as exc:
        print("ERROR:",exc,file=sys.stderr); sys.exit(1)
