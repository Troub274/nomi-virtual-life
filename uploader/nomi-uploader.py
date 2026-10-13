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
META = re.compile(r"^(Type|Source|Date|Nomi|Nomi Mode|Process Every):\s*(.*)$", re.I)
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

PERIODIC_PROMPTS = {
 "knowledge": "[nomi], please analyze and summarize information items {first}-{last}; connect the ideas without treating them as your personal experiences.",
 "instructions": "[nomi], please review instructions {first}-{last}; explain how you will apply them appropriately.",
 "journal_self": "[nomi], please recollect your own journal episodes {first}-{last} in chronological order and reflect on their meaning.",
 "journal_other": "[nomi], please reflect on [source]'s journal episodes {first}-{last} while keeping those experiences attributed to [source], not yourself.",
 "chat": "[nomi], please analyze conversation episodes {first}-{last}, keeping each speaker's words and perspective distinct."
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
                     "prompts":[],"mode":"add","process_every":None,"lines":[]}
            in_header=True
            continue
        if current is None:
            current={"title":Path(filename).stem,"type":"knowledge","source":None,
                     "date":None,"prompts":[],"mode":"add","process_every":None,"lines":[]}
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
            elif k=="process every":
                current["process_every"]=int(v)
                if current["process_every"]<0: raise ValueError("Process Every must be >= 0")
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
        # Blank-line paragraphs form processable units without rewriting source text.
        blocks=[]; buf=[]
        for line in lines:
            if not line.strip() and buf:
                blocks.append("\n".join(buf).strip()); buf=[]
            elif line.strip():
                buf.append(line)
        if buf: blocks.append("\n".join(buf).strip())
        date=parse_date(section["date"],order,session_year) if section["date"] else None
        return [{"text":block,"date":date,"label":str(i)} for i,block in enumerate(blocks,1)]
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
                if label is not None or (date and buf): flush()
                else: buf=[]  # Ignore diary cover/preamble before first dated entry
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
                if buf and any(x.strip() for x in buf): flush()
                date=dm.group(1); label=str(len(units)+1)
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

def plan_text(files, nomi, user, order, year, chunk_bytes, process_every=0):
    messages=[]
    for filename in files:
        path=Path(filename)
        if path.suffix.lower() in (".zip",".json"):
            # Existing export parser is retained verbatim in legacy_v085.
            rows=legacy.prepare_conversation_chunks([path],chunk_bytes)
            messages.append({"text":render_prompt(DEFAULT_PROMPTS["chat"],nomi,user,"Nomi export"),
                             "kind":"intro","file":filename,"section":"Nomi export"})
            for idx,row in enumerate(rows,1):
                messages.append({"text":row["text"],"kind":"content","file":filename,
                                 "section":"Nomi export","entry":idx})
                if process_every and (idx%process_every==0 or idx==len(rows)):
                    first=((idx-1)//process_every)*process_every+1
                    prompt=PERIODIC_PROMPTS["chat"].format(first=first,last=idx)
                    messages.append({"text":render_prompt(prompt,nomi,user,"Nomi export"),
                                     "kind":"prompt","file":filename,"section":"Nomi export","entry":idx})
            continue
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
            interval=section.get("process_every")
            if interval is None: interval=process_every
            if interval<0: raise ValueError("process_every cannot be negative")
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
                # Automatic type-aware processing is separate from custom Nomi: instructions.
                if interval and (idx%interval==0 or idx==len(units)):
                    first=((idx-1)//interval)*interval+1
                    template=PERIODIC_PROMPTS[default_key]
                    prompt=render_prompt(template.format(first=first,last=idx),nomi,user,source)
                    messages.append({"text":prompt,"kind":"prompt","file":filename,
                                     "section":section["title"],"entry":idx})
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
    s,p=legacy.api_request("/rooms","POST",{"name":name,"note":"Nomi Uploader v1.0 — persistent processing room","backchannelingEnabled":True,"nomiUuids":[nomi["uuid"]]})
    if not legacy.ok(s): raise RuntimeError("Room creation outcome uncertain; inspect room list before retry: "+legacy.err_text("create room",s,p))
    rid=p.get("uuid") or p.get("room",{}).get("uuid")
    if not rid: raise RuntimeError("Room creation returned no UUID; inspect room list before retry")
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
        args.user=init.get("user","")
        args.chunk_bytes=init.get("chunk_bytes",750)
        args.process_every=init.get("process_every",0)
    else:
        nomi=legacy.choose_nomi(legacy.get_nomis()) if not args.dry_run else {"name":args.nomi or "Nomi","uuid":"DRYRUN"}
        year=dt.date.today().year; order=regional_order(args.date_format)
        files=args.files; passes=args.passes; room=None
    if not files: raise ValueError("Specify at least one document")
    messages=plan_text(files,nomi["name"],args.user,order,year,args.chunk_bytes,args.process_every)
    manifest=digest(messages)
    if old and manifest!=init["manifest"]: raise ValueError("Manifest changed: resume requires identical content and options")
    print("Nomi:",nomi["name"],"Date order:",order,"Year:",year,"Messages per pass:",len(messages),"Passes:",passes)
    if args.dry_run:
        for i,m in enumerate(messages,1): print("%4d %-8s %s / %s: %s"%(i,m["kind"],m["file"],m["section"],m["text"][:130].replace("\n"," | ")))
        return
    if not old:
        if cp.exists() and cp.stat().st_size:
            previous=records(cp)
            prevstart=previous[0] if previous else {}
            confirmed_count=sum(1 for r in previous if r.get("event")=="confirmed")
            expected=prevstart.get("passes",0)*len(messages)
            reply_expected=sum(1 for r in previous if r.get("event")=="confirmed" and
                               r.get("kind")=="prompt")
            reply_count=sum(1 for r in previous if r.get("event")=="reply_committed")
            if not prevstart or confirmed_count!=expected or reply_count<reply_expected or \
               any(r.get("event") in ("attempt","reply_attempt") and
                   (r.get("pass"),r.get("index")) not in
                   {(x.get("pass"),x.get("index")) for x in previous if x.get("event")==("confirmed" if r.get("event")=="attempt" else "reply_committed")}
                   for r in previous):
                raise ValueError("Unfinished checkpoint exists; use --resume or a different --checkpoint")
            stamp=dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            cp.rename(cp.with_name(cp.name+"."+stamp+".archive"))
            done=Path(args.completion)
            if done.exists():
                done.rename(done.with_name(done.name+"."+stamp+".archive"))
            replies=Path(args.replies)
            if replies.exists():
                replies.rename(replies.with_name(replies.name+"."+stamp+".archive"))
        if args.room:
            room=args.room
            r=legacy.get_room(room)
            if not legacy.room_contains_nomi(r,nomi["uuid"]):
                raise ValueError("Room is not associated with selected Nomi")
        else: room=create_upload_room(nomi)
        record(cp,{"event":"start","run_id":str(uuid.uuid4()),"nomi_uuid":nomi["uuid"],"nomi_name":nomi["name"],"room_uuid":room,"year":year,"order":order,"files":files,"passes":passes,"manifest":manifest,"user":args.user,"chunk_bytes":args.chunk_bytes,"process_every":args.process_every})
        old=records(cp)
    attempts={(r["pass"],r["index"]) for r in old if r.get("event")=="attempt"}
    confirmed={(r["pass"],r["index"]) for r in old if r.get("event")=="confirmed"}
    reply_attempts={(r["pass"],r["index"]) for r in old if r.get("event")=="reply_attempt"}
    reply_committed={(r["pass"],r["index"]) for r in old if r.get("event")=="reply_committed"}
    uncertain=(attempts-confirmed)|(reply_attempts-reply_committed)
    if uncertain:
        raise RuntimeError("Uncertain send/reply request(s) %s. Inspect room before manual checkpoint repair; no automatic retry."%sorted(uncertain))
    for p in range(1,passes+1):
        for i,m in enumerate(messages,1):
            key=(p,i)
            if key not in confirmed:
                record(cp,{"event":"attempt","pass":p,"index":i,
                           "sha256":hashlib.sha256(m["text"].encode()).hexdigest()})
                s,response=legacy.api_request("/rooms/"+room+"/chat","POST",
                                              {"messageText":m["text"]})
                if not legacy.ok(s):
                    raise RuntimeError("POST outcome uncertain: "+legacy.err_text("send",s,response))
                record(cp,{"event":"confirmed","pass":p,"index":i,
                           "kind":m["kind"],"api_response":response})
                print("Pass %d/%d message %d/%d"%(p,passes,i,len(messages)))
                if args.delay: time.sleep(args.delay)
            if m["kind"]=="prompt" and key not in reply_committed:
                # Reply requests are POSTs too. Never blindly repeat an uncertain request.
                record(cp,{"event":"reply_attempt","pass":p,"index":i,
                           "room_uuid":room,"nomi_uuid":nomi["uuid"]})
                s,response=legacy.api_request("/rooms/"+room+"/chat/request","POST",
                                              {"nomiUuid":nomi["uuid"]})
                if not legacy.ok(s):
                    raise RuntimeError("Reply request outcome uncertain: "+
                                       legacy.err_text("request reply",s,response))
                reply=response.get("replyMessage") if isinstance(response,dict) else None
                if not isinstance(reply,dict):
                    raise RuntimeError("Reply request returned no replyMessage; inspect room and checkpoint")
                record(cp,{"event":"reply_committed","pass":p,"index":i,
                           "room_uuid":room,"nomi_uuid":nomi["uuid"],
                           "prompt":m["text"],"reply":reply,
                           "reply_api_response":response})
                body=reply.get("messageText") or reply.get("text") or reply.get("content") or ""
                print("%s replied after pass %d message %d: %s"%
                      (nomi["name"],p,i,str(body)[:300].replace("\n"," ")))
    final_events=records(cp)
    reply_rows=[r for r in final_events if r.get("event")=="reply_committed"]
    transcript=Path(args.replies)
    transcript.parent.mkdir(parents=True,exist_ok=True)
    # Derived transcript: durable source of truth remains the append-only checkpoint.
    with open(transcript,"w",encoding="utf-8") as out:
        for row in reply_rows:
            reply=row["reply"]
            body=reply.get("messageText") or reply.get("text") or reply.get("content") or ""
            out.write("Pass %d, prompt message %d — %s\n"%(row["pass"],row["index"],nomi["name"]))
            out.write("PROMPT: "+row["prompt"]+"\n")
            out.write("REPLY: "+str(body)+"\n\n")
    Path(args.completion).parent.mkdir(parents=True,exist_ok=True)
    Path(args.completion).write_text(json.dumps({"version":VERSION,"room_uuid":room,"nomi":nomi["name"],"passes":passes,"messages_per_pass":len(messages),"manifest":manifest,"completed_at":dt.datetime.now(dt.timezone.utc).isoformat()},indent=2),encoding="utf-8")
    print("Complete. Room retained:",room)

def active_room_ids(checkpoint_dir="."):
    protected=set()
    for path in Path(checkpoint_dir).glob("*.jsonl"):
        try:
            events=records(path)
            if not events or events[0].get("event")!="start": continue
            start=events[0]
            # A completion marker is not proof that it belongs to this run.
            # Protect any room with a checkpoint unless explicitly detached.
            protected.add(start["room_uuid"])
        except (OSError,ValueError,KeyError):
            continue
    return protected

def room_management(nomi_filter=None, abandoned=False, checkpoint_dir="."):
    rooms=legacy.list_rooms()
    if nomi_filter:
        nomis=legacy.get_nomis()
        matches=[n for n in nomis if nomi_filter.casefold() in n.get("name","").casefold()]
        ids={n["uuid"] for n in matches}
        rooms=[r for r in rooms if any(legacy.room_contains_nomi(r,uid) for uid in ids)]
    if abandoned:
        rooms=[r for r in rooms if str(r.get("status","")).lower() in
               ("abandoned","inactive","failed","error")]
    protected=active_room_ids(checkpoint_dir)
    for i,r in enumerate(rooms,1):
        rid=r.get("uuid","")
        print("%3d  %-42s %-36s %-12s %s"%(i,r.get("name",""),rid,
              r.get("status",""),"PROTECTED" if rid in protected else ""))
    return rooms,protected

def utilities():
    print("Room manager: list, inspect, delete one, or bulk-delete selected rooms.")
    filt=input("Filter by Nomi name (Enter for all): ").strip()
    abandoned=input("Show only abandoned/inactive/failed rooms? (y/N): ").strip().lower()=="y"
    checkpoint_dir=input("Checkpoint directory [.] : ").strip() or "."
    rooms,protected=room_management(filt,abandoned,checkpoint_dir)
    if not rooms: return
    choice=input("Room number to inspect, ALL for bulk deletion, or Enter to exit: ").strip()
    if not choice: return
    if choice.upper()=="ALL":
        targets=rooms
    else:
        i=int(choice)-1
        if not 0<=i<len(rooms): raise ValueError("Invalid room number")
        targets=[rooms[i]]
        print(json.dumps(targets[0],indent=2,ensure_ascii=False))
        if input("Delete this room? (y/N): ").strip().lower()!="y": return
    blocked=[r for r in targets if r.get("uuid") in protected]
    if blocked:
        print("Protected incomplete rooms excluded:",", ".join(r["uuid"] for r in blocked))
    targets=[r for r in targets if r.get("uuid") not in protected]
    if not targets: return
    print("About to DELETE %d room(s). This cannot be undone."%len(targets))
    if input("Type DELETE %d to confirm: "%len(targets)).strip()!="DELETE %d"%len(targets): return
    for r in targets:
        rid=r["uuid"]
        if input("Confirm room UUID %s (or SKIP): "%rid).strip()!=rid: continue
        legacy.delete_room(rid)
        print("Deleted",rid)

def interactive_menu():
    while True:
        print("\nNomi Uploader 1.0\n 1 Upload files\n 2 Resume checkpoint\n 3 Dry-run\n 4 Manage rooms\n 5 Quit")
        action=input("Select: ").strip()
        if action in ("5","q","Q",""): return
        if action=="4": utilities(); continue
        if action not in ("1","2","3"): print("Unknown option"); continue
        argv=["--resume"] if action=="2" else []
        if action!="2":
            files=input("Input files (quoted paths supported): ").strip()
            if not files: continue
            import shlex
            argv+=shlex.split(files,posix=(os.name!="nt"))
            interval=input("Process every N units [0]: ").strip()
            if interval: argv+=["--process-every",interval]
            passes=input("Passes [1]: ").strip()
            if passes: argv+=["--passes",passes]
        if action=="3": argv+=["--dry-run"]
        main(argv)

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if "--legacy" in argv:
        argv.remove("--legacy")
        saved=sys.argv
        try:
            sys.argv=[saved[0]]+argv
            return legacy.main()
        finally:
            sys.argv=saved
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
    parser.add_argument("--process-every",type=int,default=0,help="Automatic type-aware recollection/analysis after N units; 0 disables")
    parser.add_argument("--chunk-bytes",type=int,default=750)
    parser.add_argument("--date-format",choices=["AUTO","US","EU"],default="AUTO")
    parser.add_argument("--delay",type=float,default=1)
    parser.add_argument("--checkpoint",default="nomi_uploader_checkpoint.jsonl")
    parser.add_argument("--completion",default="nomi_uploader_completed.json")
    parser.add_argument("--replies",default="nomi_uploader_replies.txt")
    if not argv and sys.stdin.isatty(): return interactive_menu()
    args=parser.parse_args(argv)
    if args.process_every<0: parser.error("process-every must be >= 0")
    if args.passes<1 or args.chunk_bytes<150: parser.error("passes >=1 and chunk-bytes >=150 required")
    if args.utility: utilities()
    else: upload(args)

if __name__=="__main__":
    try: main()
    except (RuntimeError,ValueError,OSError) as exc:
        print("ERROR:",exc,file=sys.stderr); sys.exit(1)
