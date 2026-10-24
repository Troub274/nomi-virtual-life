#!/usr/bin/env python3
"""Nomi Uploader 1.1 — source-aware, resumable room uploader."""
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

VERSION = "1.1"
MAX_API_CHARS = 800
DEFAULT_CHUNK_CHARS = 750
KNOWN_WAIT_ERRORS = {"NoReply","RoomNomiNotReadyForMessage","RoomStillCreating","TooManyRequests"}
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
 "journal_self": "[nomi], please live and experience these entries as yourself.",
 "journal_other": "[nomi], please learn about [source]'s life and understand these experiences as [source]'s, not your own.",
 "chat": "[nomi], please live and experience these conversations as yourself."
}

PERIODIC_PROMPTS = {
 "knowledge": "[nomi], please analyze and summarize information items {first}-{last}; connect the ideas without treating them as your personal experiences.",
 "instructions": "[nomi], please review instructions {first}-{last}; explain how you will apply them appropriately.",
 "journal_self": "[nomi], please live and experience the entries {first}-{last} as yourself.",
 "journal_other": "[nomi], please reflect on [source]'s journal episodes {first}-{last} while keeping those experiences attributed to [source], not yourself.",
 "chat": "[nomi], please live and experience the conversations {first}-{last} as yourself."
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
    """Legacy v1.0 UTF-8 byte splitter. Kept for old checkpoint compatibility."""
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

def split_char_budget(text, budget):
    """Split text by Unicode characters, respecting the Nomi 800-character API ceiling."""
    if budget<1: raise ValueError("Chunk character budget must be positive")
    if len(text)<=budget: return [text]
    result=[]; remaining=text
    while remaining:
        if len(remaining)<=budget:
            result.append(remaining); break
        candidate=remaining[:budget]
        cut=max(candidate.rfind("\n\n"),candidate.rfind("\n"),candidate.rfind(". "),candidate.rfind(" "))
        use=budget
        if cut>budget//3:
            use=cut+(2 if candidate[cut:cut+2]==". " else 1)
        if use<1: use=budget
        result.append(remaining[:use])
        remaining=remaining[use:]
    return result

def parse_entry_range(value):
    """Return (start,end), with None for an open side; accepts 45, 45-100, 45-, -100, all."""
    if value is None: return None
    value=str(value).strip()
    if not value or value.casefold()=="all": return None
    if re.fullmatch(r"[1-9][0-9]*",value):
        n=int(value); return (n,n)
    match=re.fullmatch(r"([1-9][0-9]*)?\s*-\s*([1-9][0-9]*)?",value)
    if not match or (not match.group(1) and not match.group(2)):
        raise ValueError("--entries expects N, START-END, START-, -END, or all")
    start=int(match.group(1)) if match.group(1) else None
    end=int(match.group(2)) if match.group(2) else None
    if start is not None and end is not None and start>end:
        raise ValueError("--entries start must be <= end")
    return (start,end)

def entry_range_text(entry_range):
    if entry_range is None: return None
    start,end=entry_range
    if start==end and start is not None: return str(start)
    return "%s-%s"%("" if start is None else start,"" if end is None else end)

def select_entry_units(units, entry_range):
    if entry_range is None: return units
    start,end=entry_range
    selected=[]
    for unit in units:
        label=str(unit.get("label") or "").strip()
        if not re.fullmatch(r"[0-9]+",label):
            raise ValueError("--entries requires numeric journal entry labels")
        number=int(label)
        if start is not None and number<start: continue
        if end is not None and number>end: continue
        selected.append(unit)
    return selected


def render_prompt(prompt, nomi, user, source):
    return prompt.replace("[nomi]",nomi).replace("[user]",user or "the user").replace("[source]",source)

def plan_text(files, nomi, user, order, year, chunk_limit, process_every=0,
              entry_range=None, chunk_mode="bytes", export_options=None):
    """Create the deterministic message plan.

    chunk_mode='bytes' reproduces v1.0 planning for old checkpoints and direct
    compatibility calls. New v1.1 runs use chunk_mode='chars'.
    """
    messages=[]
    export_options=export_options or {}
    if chunk_mode not in ("bytes","chars"):
        raise ValueError("chunk_mode must be bytes or chars")
    if chunk_mode=="chars" and chunk_limit>MAX_API_CHARS:
        raise ValueError("Nomi API messages cannot exceed %d characters"%MAX_API_CHARS)
    splitter=split_char_budget if chunk_mode=="chars" else split_budget

    def add(message):
        if chunk_mode=="chars" and len(message["text"])>chunk_limit:
            raise ValueError("Planned %s message exceeds %d-character limit"%
                             (message.get("kind","message"),chunk_limit))
        messages.append(message)

    for filename in files:
        path=Path(filename)
        if path.suffix.lower() in (".zip",".json"):
            if entry_range is not None:
                raise ValueError("--entries applies to Journal text/DOCX input, not Nomi export ZIP/JSON")
            rows=legacy.prepare_conversation_chunks([path],chunk_limit)
            opts=export_options.get(str(path),{})
            mode=str(opts.get("mode","Add")).lower()
            if mode not in ("add","replace"): raise ValueError("Export Nomi Mode must be Add or Replace")
            opening=str(opts.get("intro","")).strip()
            base=DEFAULT_PROMPTS["chat"] if mode=="add" else ""
            intro="\n".join(p for p in (base,opening) if p)
            interval=opts.get("process_every")
            interval=process_every if interval in (None,"") else int(interval)
            if interval<0: raise ValueError("Process Every must be >= 0")
            if intro:
                add({"text":render_prompt(intro,nomi,user,"Nomi export"),
                 "kind":"intro","file":filename,"section":"Nomi export"})
            for idx,row in enumerate(rows,1):
                add({"text":row["text"],"kind":"content","file":filename,
                     "section":"Nomi export","entry":idx})
                if interval and (idx%interval==0 or idx==len(rows)):
                    first=((idx-1)//interval)*interval+1
                    prompt=str(opts.get("periodic") or PERIODIC_PROMPTS["chat"]).format(first=first,last=idx)
                    add({"text":render_prompt(prompt,nomi,user,"Nomi export"),
                         "kind":"prompt","file":filename,"section":"Nomi export","entry":idx})
            continue
        for section in parse_sections(read_text(path),filename):
            source=section["source"] or (nomi if section["type"]=="journal" else "System")
            all_units=split_units(section,order,year)
            kind=section["type"]
            units=select_entry_units(all_units,entry_range) if kind=="journal" else all_units
            if not units or not any(u["text"] for u in units): continue
            default_key="journal_self" if kind=="journal" and source.casefold()==nomi.casefold() else ("journal_other" if kind=="journal" else kind)
            prompts=[] if section["mode"]=="replace" else [DEFAULT_PROMPTS[default_key]]
            intro="\n".join(render_prompt(p,nomi,user,source) for p in prompts)
            intro += "\nSection: %s\nType: %s\nSource: %s"%(section["title"],kind.title(),source)
            add({"text":intro.strip(),"kind":"intro","file":filename,"section":section["title"]})
            interval=section.get("process_every")
            if interval is None: interval=process_every
            if interval<0: raise ValueError("process_every cannot be negative")
            for idx,unit in enumerate(units,1):
                label=unit.get("label") or str(idx)
                prefix="Section: %s\nType: %s\nSource: %s\nEntry: %s"%(section["title"],kind.title(),source,label)
                if unit.get("date"): prefix+="\nDate: "+unit["date"]
                reserve=(prefix+"\nPart: 999/999\n" if chunk_mode=="bytes"
                         else prefix+"\nPart: 99999/99999\n")
                overhead=len(reserve) if chunk_mode=="chars" else len(reserve.encode("utf-8"))
                room=chunk_limit-overhead
                if chunk_mode=="bytes":
                    room=max(50,room)
                elif room<50:
                    raise ValueError("Section metadata leaves too little room under --chunk-chars")
                fragments=splitter(unit["text"],room)
                for j,frag in enumerate(fragments,1):
                    body=prefix+"\nPart: %d/%d\n"%(j,len(fragments))+frag
                    size=len(body) if chunk_mode=="chars" else len(body.encode("utf-8"))
                    if size>chunk_limit:
                        unit_name="character" if chunk_mode=="chars" else "byte"
                        raise ValueError("Chunk exceeds %s limit; adjust chunk setting"%unit_name)
                    msg={"text":body,"kind":"content","file":filename,
                         "section":section["title"],"entry":idx}
                    if chunk_mode=="chars":
                        msg.update({"entry_label":str(label),"part":j,"parts":len(fragments)})
                    add(msg)
                if interval and (idx%interval==0 or idx==len(units)):
                    first=((idx-1)//interval)*interval+1
                    first_label=(units[first-1].get("label") or str(first)) if kind=="journal" else first
                    last_label=label if kind=="journal" else idx
                    if chunk_mode=="bytes" and entry_range is None:
                        # Preserve v1.0's historical double-escaped detector exactly;
                        # old checkpoint manifests depend on that behavior.
                        custom=[p for p in section["prompts"] if not re.search(r"\\b(?:entries|episodes)\\s+\\d+\\s*[-–]\\s*\\d+\\b",p,re.I)]
                    else:
                        custom=[p for p in section["prompts"] if not re.search(r"\b(?:entries|episodes)\s+\d+\s*[-–]\s*\d+\b",p,re.I)]
                    template=custom[0] if len(custom)==1 else PERIODIC_PROMPTS[default_key]
                    prompt=render_prompt(template.format(first=first_label,last=last_label),nomi,user,source)
                    msg={"text":prompt,"kind":"prompt","file":filename,
                         "section":section["title"],"entry":idx}
                    if chunk_mode=="chars" and kind=="journal":
                        msg["entry_label"]=str(last_label)
                    add(msg)
                for prompt in (section["prompts"] if interval else []):
                    nums=re.search(r"\b(?:entries|episodes)\s+(\d+)\s*[-–]\s*(\d+)\b",prompt,re.I)
                    if nums:
                        target=int(nums.group(2))
                        if chunk_mode=="bytes" and entry_range is None:
                            current=idx
                        else:
                            current=int(label) if kind=="journal" and re.fullmatch(r"\d+",str(label)) else idx
                        if target==current:
                            add({"text":render_prompt(prompt,nomi,user,source),"kind":"prompt",
                                 "file":filename,"section":section["title"]})
            for prompt in (section["prompts"] if interval else []):
                nums=re.search(r"\b(?:entries|episodes)\s+(\d+)\s*[-–]\s*(\d+)\b",prompt,re.I)
                if nums:
                    if entry_range is None or kind!="journal":
                        if int(nums.group(1))<1 or int(nums.group(2))>len(units):
                            raise ValueError("Prompt range outside section: "+prompt)
                elif not interval:
                    add({"text":render_prompt(prompt,nomi,user,source),"kind":"prompt",
                         "file":filename,"section":section["title"]})
    return messages


def digest(messages):
    raw=json.dumps(messages,sort_keys=True,ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def record(path, obj):
    with open(path,"a+b") as f:
        if f.tell():
            f.seek(-1,os.SEEK_END)
            if f.read(1)!=b"\n":
                raise ValueError("Incomplete checkpoint tail; preserve file and inspect before repair")
        f.write((json.dumps(obj,ensure_ascii=False)+"\n").encode("utf-8"))
        f.flush(); os.fsync(f.fileno())

def records(path):
    if not path.exists(): return []
    raw=path.read_text(encoding="utf-8")
    if raw and not raw.endswith("\n"):
        raise ValueError("Incomplete checkpoint tail; preserve file and inspect before repair")
    return [json.loads(s) for s in raw.splitlines() if s.strip()]

def request_reply_with_backoff(room, nomi_uuid, attempts=None, base_delay=1.0,
                               max_wait=0):
    """Wait through explicit Nomi not-ready responses; stop on ambiguous errors.

    max_wait is seconds; 0 means unlimited. Reaching max_wait returns the last
    explicit rejection, which is safe to continue waiting on a later resume.
    """
    delay=base_delay
    n=0
    started=time.monotonic()
    while True:
        n+=1
        status,payload=legacy.api_request("/rooms/"+room+"/chat/request","POST",
                                          {"nomiUuid":nomi_uuid})
        if legacy.ok(status):
            return status,payload
        error=legacy.err_text("request reply",status,payload)
        if status is not None and legacy.err_type(payload) in KNOWN_WAIT_ERRORS:
            elapsed=time.monotonic()-started
            if attempts is not None and n>=attempts:
                print("Nomi API error: %s; test retry limit reached"%error,
                      file=sys.stderr,flush=True)
                return status,payload
            if max_wait and elapsed>=max_wait:
                print("Nomi API error: %s; reply wait limit reached after %.1fs"%
                      (error,elapsed),file=sys.stderr,flush=True)
                return status,payload
            wait=delay
            if max_wait:
                wait=min(wait,max(0,max_wait-elapsed))
                if wait<=0: return status,payload
            print("Nomi API error: %s; %s attempt %d; retry in %.1fs; elapsed %.1fs"%
                  (error,legacy.err_type(payload),n,wait,elapsed),file=sys.stderr,flush=True)
            time.sleep(wait)
            delay=min(delay*2,30)
            continue
        print("Nomi API error: %s; request outcome uncertain; not retrying"%error,
              file=sys.stderr,flush=True)
        return status,payload


def create_upload_room(nomi):
    name="UPLOADER::%s::%s"%(nomi["name"],dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    s,p=legacy.api_request("/rooms","POST",{"name":name,"note":"Nomi Uploader v%s — persistent processing room"%VERSION,"backchannelingEnabled":True,"nomiUuids":[nomi["uuid"]]})
    if not legacy.ok(s): raise RuntimeError("Room creation outcome uncertain; inspect room list before retry: "+legacy.err_text("create room",s,p))
    rid=p.get("uuid") or p.get("room",{}).get("uuid")
    if not rid: raise RuntimeError("Room creation returned no UUID; inspect room list before retry")
    legacy.wait_for_room(rid)
    return rid


def select_or_create_room(nomi, checkpoint_dir="."):
    """Reuse a suitable existing room by Nomi UUID, as in the v0.85 workflow."""
    uid = str(nomi["uuid"])
    rooms = legacy.list_rooms()
    candidates = legacy.matching_rooms(nomi, rooms)
    seen = {str(r.get("uuid", "")) for r in candidates}
    for room in rooms:
        rid = str(room.get("uuid", ""))
        if (rid and rid not in seen
                and str(room.get("name", "")).startswith("UPLOADER::")
                and legacy.room_contains_nomi(room, uid)):
            candidates.append(room)
            seen.add(rid)

    protected = active_room_ids(checkpoint_dir)
    eligible = [
        r for r in candidates
        if r.get("uuid") and str(r["uuid"]) not in protected
        and str(r.get("status", "")).lower() not in (
            "creating", "waiting", "failed", "error",
            "abandoned", "inactive", "deleting")
    ]
    eligible.sort(key=lambda r: str(r.get("created", r.get("createdAt", ""))), reverse=True)
    if not eligible:
        if candidates:
            raise RuntimeError(
                "Existing rooms for %s are protected or unavailable. "
                "Inspect the checkpoints before using --room UUID." % nomi["name"])
        print("No existing processing room for %s; creating one." % nomi["name"])
        return create_upload_room(nomi)

    print("\nExisting processing rooms for %s:" % nomi["name"])
    for index, room in enumerate(eligible, 1):
        print("  %d. Reuse %s [%s] (%s)" % (
            index, room.get("name", ""), room["uuid"], room.get("status", "")))
    new_option = len(eligible) + 1
    print("  %d. Create a new room" % new_option)
    while True:
        answer = input("Room choice [1 = reuse, recommended]: ").strip() or "1"
        try:
            choice = int(answer)
        except ValueError:
            choice = 0
        if 1 <= choice <= len(eligible):
            rid = str(eligible[choice - 1]["uuid"])
            full_room = legacy.get_room(rid)
            if not legacy.room_contains_nomi(full_room, uid):
                raise ValueError("Room is not associated with selected Nomi")
            print("Reusing room:", eligible[choice - 1].get("name", ""), rid)
            return rid
        if choice == new_option:
            return create_upload_room(nomi)
        print("Enter a number from 1 through %d." % new_option)

def migration_room(events):
    room=events[0]["room_uuid"]
    for e in events:
        if e.get("event")=="room_migrated":
            if e["from_room_uuid"]!=room: raise ValueError("Invalid migration chain")
            room=e["to_room_uuid"]
    return room


def migrate_resume(cp, old, nomi, room):
    intents=[e for e in old if e.get("event")=="room_migration_intent"]
    if intents:
        intent=intents[-1]
        if any(e.get("event")=="room_migrated" and e.get("migration_id")==intent["migration_id"] for e in old):
            return room
        matches=[r for r in legacy.list_rooms() if r.get("name")==intent["room_name"]]
        if len(matches)!=1:
            raise RuntimeError("Migration creation outcome uncertain; inspect rooms for "+intent["room_name"]+"; no automatic create retry")
        if not legacy.room_contains_nomi(matches[0],nomi["uuid"]):
            raise ValueError("Migration room is not associated with selected Nomi")
        rid=matches[0]["uuid"]
    else:
        mid=str(uuid.uuid4())
        intent={"event":"room_migration_intent","migration_id":mid,
                "from_room_uuid":room,"room_name":"UPLOADER::MIGRATION::"+mid,
                "time":dt.datetime.now(dt.timezone.utc).isoformat()}
        record(cp,intent)
        status,payload=legacy.api_request("/rooms","POST",{
            "name":intent["room_name"],"note":"Nomi Uploader resume migration",
            "backchannelingEnabled":True,"nomiUuids":[nomi["uuid"]]})
        if not legacy.ok(status):
            raise RuntimeError("Migration creation outcome uncertain; resume to reconcile; no create retry")
        rid=payload.get("uuid") or payload.get("room",{}).get("uuid")
        if not rid: raise RuntimeError("Migration returned no UUID; resume to reconcile")
    if rid==room: raise ValueError("Migration destination must be a fresh room")
    record(cp,{"event":"room_migrated","migration_id":intent["migration_id"],
               "from_room_uuid":room,"to_room_uuid":rid,
               "time":dt.datetime.now(dt.timezone.utc).isoformat()})
    return rid


def checkpoint_summary(path):
    cp=Path(path)
    old=records(cp)
    if not old:
        return {"state":"NO_CHECKPOINT","checkpoint":str(cp)}
    init=old[0]
    if init.get("event")!="start":
        raise ValueError("Checkpoint must begin with start event")
    attempts={(r.get("pass"),r.get("index")) for r in old if r.get("event")=="attempt"}
    confirmed={(r.get("pass"),r.get("index")) for r in old if r.get("event")=="confirmed"}
    reply_attempts={(r.get("pass"),r.get("index")) for r in old if r.get("event")=="reply_attempt"}
    reply_committed={(r.get("pass"),r.get("index")) for r in old if r.get("event")=="reply_committed"}
    abandoned={(r.get("pass"),r.get("index")) for r in old if r.get("event")=="reply_abandoned"}
    retryable={
        (r.get("pass"),r.get("index")) for r in old
        if r.get("event")=="reply_uncertain"
        and r.get("http_status") is not None
        and legacy.err_type(r.get("api_response")) in KNOWN_WAIT_ERRORS
    }
    uncertain_sends=attempts-confirmed
    pending_replies=reply_attempts-reply_committed-abandoned
    ambiguous_replies=pending_replies-retryable
    expected=int(init.get("passes",1))*int(init.get("messages_per_pass",0))
    prompts={(r.get("pass"),r.get("index")) for r in old
             if r.get("event")=="confirmed" and r.get("kind")=="prompt"}
    complete=bool(expected) and len(confirmed)==expected and prompts <= (reply_committed|abandoned)
    if uncertain_sends: state="AMBIGUOUS_SEND"
    elif ambiguous_replies: state="AMBIGUOUS_REPLY"
    elif complete: state="COMPLETE"
    else: state="SAFE_TO_RESUME"
    last_event=None
    for r in old:
        if r.get("event")=="confirmed":
            last_event=r
    next_key=None
    if expected:
        for p in range(1,int(init.get("passes",1))+1):
            for i in range(1,int(init.get("messages_per_pass",0))+1):
                if (p,i) not in confirmed:
                    next_key=(p,i); break
            if next_key: break
    return {
        "state":state,"checkpoint":str(cp),"nomi":init.get("nomi_name"),
        "room_uuid":migration_room(old),"run_id":init.get("run_id"),
        "confirmed":len(confirmed),"expected":expected,
        "last_confirmed":max(confirmed) if confirmed else None,
        "last_entry":last_event.get("entry_label") if last_event else None,
        "last_part":last_event.get("part") if last_event else None,
        "last_parts":last_event.get("parts") if last_event else None,
        "next":next_key,
        "uncertain_sends":sorted(uncertain_sends),
        "ambiguous_replies":sorted(ambiguous_replies),
        "retryable_replies":sorted(pending_replies & retryable),
        "entry_range":init.get("entry_range"),
        "chunk_mode":init.get("chunk_mode","bytes"),
        "chunk_limit":init.get("chunk_limit",init.get("chunk_chars",init.get("chunk_bytes",750)))
    }

def print_checkpoint_status(path):
    info=checkpoint_summary(path)
    if info["state"]=="NO_CHECKPOINT":
        print("No checkpoint found.")
        return info
    print("%s upload"%((info.get("nomi") or "Nomi")))
    print("="*(len(info.get("nomi") or "Nomi")+7))
    print("State:      ",info["state"])
    print("Progress:   %d / %d messages"%(info["confirmed"],info["expected"]))
    if info.get("entry_range"): print("Entries:    ",info["entry_range"])
    if info.get("last_confirmed"):
        line="Last safe:   pass %d message %d"%tuple(info["last_confirmed"])
        if info.get("last_entry"):
            line+=" — entry %s"%info["last_entry"]
            if info.get("last_part"): line+=" part %s/%s"%(info["last_part"],info["last_parts"])
        print(line)
    if info.get("next"): print("Next:        pass %d message %d"%tuple(info["next"]))
    if info["state"]=="SAFE_TO_RESUME":
        print("Safe action: resume.")
    elif info["state"]=="COMPLETE":
        print("Safe action: none; this run is complete.")
    elif info["state"]=="AMBIGUOUS_SEND":
        print("Attention: a content POST may or may not have reached Nomi:",info["uncertain_sends"])
    elif info["state"]=="AMBIGUOUS_REPLY":
        print("Attention: a reply request has an unknown outcome:",info["ambiguous_replies"])
    return info


def upload(args):
    # Advisory locks are released by the OS on process termination. Never unlink
    # this file: doing so could allow two processes to lock different inodes.
    lockpath=Path(str(args.checkpoint)+".lock")
    lockpath.parent.mkdir(parents=True,exist_ok=True)
    with open(lockpath,"a+b") as lock:
        if os.name=="nt":
            import msvcrt
            if lockpath.stat().st_size==0:
                lock.write(b"0"); lock.flush()
            lock.seek(0)
            try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            except OSError: raise RuntimeError("Checkpoint in use by another uploader")
        else:
            import fcntl
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError: raise RuntimeError("Checkpoint in use by another uploader")
        return _upload_locked(args)


def _upload_locked(args):
    migrating=getattr(args,"new_room_on_resume",False)
    tokens=getattr(args,"abandon_reply",[]) or []
    if (migrating or tokens) and not args.resume: raise ValueError("migration flags require --resume")
    if bool(tokens)!=bool(migrating): raise ValueError("--new-room-on-resume and --abandon-reply must be used together")
    if migrating and (args.room or args.dry_run or getattr(args,"recover_noreply",[]) or getattr(args,"recover_uncertain_reply",[]) or getattr(args,"retry_uncertain_send",[])):
        raise ValueError("migration cannot be combined with --room, --dry-run or recovery flags")
    cp=Path(args.checkpoint)
    old=records(cp) if args.resume else []
    if args.resume and not old: raise ValueError("No checkpoint to resume")
    if old:
        init=old[0]
        if init.get("event")!="start": raise ValueError("Checkpoint must begin with start event")
        nomi={"uuid":init["nomi_uuid"],"name":init["nomi_name"]}
        year=init["year"]; order=init["order"]; room=migration_room(old)
        if args.room and args.room!=room: raise ValueError("--room cannot override checkpoint room")
        files=init["files"]; passes=init["passes"]
        args.user=init.get("user","")
        args.process_every=init.get("process_every",0)
        if init.get("chunk_mode")=="chars" or "chunk_chars" in init:
            chunk_mode="chars"
            chunk_limit=int(init.get("chunk_limit",init.get("chunk_chars",DEFAULT_CHUNK_CHARS)))
        else:
            chunk_mode="bytes"
            chunk_limit=int(init.get("chunk_limit",init.get("chunk_bytes",750)))
        entry_range=parse_entry_range(init.get("entry_range"))
    else:
        if args.dry_run:
            nomi={"name":args.nomi or "Nomi","uuid":"DRYRUN"}
        elif args.nomi_uuid:
            matches=[n for n in legacy.get_nomis() if str(n.get("uuid","")).casefold()==args.nomi_uuid.casefold()]
            if len(matches)!=1:
                raise ValueError("Selected Nomi UUID is not available on this API account. Reload Nomis in the GUI.")
            nomi=matches[0]
        else:
            nomi=legacy.choose_nomi(legacy.get_nomis())
        year=dt.date.today().year; order=regional_order(args.date_format)
        files=args.files; passes=args.passes; room=None
        entry_range=parse_entry_range(getattr(args,"entries",None))
        legacy_bytes=getattr(args,"chunk_bytes",None)
        char_limit=getattr(args,"chunk_chars",None)
        if legacy_bytes is not None:
            chunk_mode="bytes"; chunk_limit=int(legacy_bytes)
        else:
            chunk_mode="chars"; chunk_limit=int(char_limit or DEFAULT_CHUNK_CHARS)
    if not files: raise ValueError("Specify at least one document")
    if old:
        export_options=init.get("export_options",{})
    else:
        export_options=json.loads(Path(args.export_options).read_text(encoding="utf-8")) if args.export_options else {}
    messages=plan_text(files,nomi["name"],args.user,order,year,chunk_limit,
                       args.process_every,entry_range,chunk_mode,export_options)
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
            expected=prevstart.get("passes",0)*prevstart.get("messages_per_pass",len(messages))
            reply_expected=sum(1 for r in previous if r.get("event")=="confirmed" and
                               r.get("kind")=="prompt")
            reply_count=sum(1 for r in previous if r.get("event") in ("reply_committed","reply_abandoned"))
            if not prevstart or confirmed_count!=expected or reply_count<reply_expected or \
               any(r.get("event") in ("attempt","reply_attempt") and
                   (r.get("pass"),r.get("index")) not in
                   {(x.get("pass"),x.get("index")) for x in previous if x.get("event") in (("confirmed",) if r.get("event")=="attempt" else ("reply_committed","reply_abandoned"))}
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
        else: room=select_or_create_room(nomi, cp.parent)
        start_event={"event":"start","version":VERSION,"run_id":str(uuid.uuid4()),
                     "nomi_uuid":nomi["uuid"],"nomi_name":nomi["name"],
                     "room_uuid":room,"year":year,"order":order,"files":files,
                     "passes":passes,"messages_per_pass":len(messages),
                     "manifest":manifest,"user":args.user,
                     "process_every":args.process_every,"export_options":export_options,
                     "chunk_mode":chunk_mode,"chunk_limit":chunk_limit,
                     "entry_range":entry_range_text(entry_range)}
        if chunk_mode=="chars": start_event["chunk_chars"]=chunk_limit
        else: start_event["chunk_bytes"]=chunk_limit
        record(cp,start_event)
        old=records(cp)
    attempts={(r["pass"],r["index"]) for r in old if r.get("event")=="attempt"}
    confirmed={(r["pass"],r["index"]) for r in old if r.get("event")=="confirmed"}
    reply_attempts={(r["pass"],r["index"]) for r in old if r.get("event")=="reply_attempt"}
    reply_committed={(r["pass"],r["index"]) for r in old if r.get("event")=="reply_committed"}
    abandoned={(r["pass"],r["index"]) for r in old if r.get("event")=="reply_abandoned"}
    if migrating or abandoned:
        positions={(p,i) for p in range(1,passes+1) for i in range(1,len(messages)+1)}
        if not (attempts | confirmed | reply_attempts | reply_committed | abandoned) <= positions:
            raise ValueError("Checkpoint positions outside the saved plan")
        prefix=set(sorted(positions)[:len(confirmed)])
        if confirmed!=prefix: raise ValueError("Migration requires a contiguous confirmed prefix")
        prompts={k for k in confirmed if messages[k[1]-1]["kind"]=="prompt"}
        if not abandoned <= (prompts & reply_attempts)-reply_committed:
            raise ValueError("Invalid abandoned reply state")
    requested=set()
    for token in tokens:
        if not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*",token): raise ValueError("--abandon-reply expects PASS:INDEX")
        key=tuple(map(int,token.split(":")))
        if (key[0]>passes or key[1]>len(messages) or messages[key[1]-1]["kind"]!="prompt" or key not in confirmed or key not in reply_attempts or key in reply_committed):
            raise ValueError("No pending confirmed reflection at "+token)
        requested.add(key)
    if migrating:
        if any(e.get("event")=="room_migrated" for e in old) and requested-abandoned:
            raise ValueError("This recovery migration is already complete")
        pending={(p,i) for p,i in confirmed if messages[i-1]["kind"]=="prompt"}-reply_committed-abandoned
        if attempts-confirmed or pending-requested: raise ValueError("Resolve all uncertain sends and pending replies before migration")
        for p,i in sorted(requested-abandoned):
            record(cp,{"event":"reply_abandoned","pass":p,"index":i,"room_uuid":room,
                       "nomi_uuid":nomi["uuid"],"run_id":old[0].get("run_id"),
                       "time":dt.datetime.now(dt.timezone.utc).isoformat(),
                       "reason":"operator abandoned stuck reply; prompt remains confirmed"})
        abandoned |= requested
    migration_pending=bool(abandoned) and not any(e.get("event")=="room_migrated" for e in old)
    if migration_pending:
        pending={(p,i) for p,i in confirmed if messages[i-1]["kind"]=="prompt"}-reply_committed-abandoned
        if attempts-confirmed or pending:
            raise ValueError("Finish authorizing all pending replies before interrupted migration; no room created")
    # A send with a failed/ambiguous POST cannot be retried automatically.
    # The operator must explicitly authorize each unconfirmed message by pass/index.
    uncertain_sends=attempts-confirmed
    send_retry_authorized=set()
    for token in getattr(args,"retry_uncertain_send",[]) or []:
        try:
            p_str,i_str=token.split(":",1)
            key=(int(p_str),int(i_str))
        except (ValueError,TypeError):
            raise ValueError("--retry-uncertain-send expects PASS:INDEX, e.g. 1:1065")
        if key not in uncertain_sends:
            raise ValueError("No pending uncertain content send at %s" % token)
        send_retry_authorized.add(key)
    # Never infer NoReply from a bare reply_attempt. Require an explicit
    # operator acknowledgement for legacy checkpoints lacking a result event.
    recovery=set()
    for token in getattr(args,"recover_noreply",[]) or []:
        try:
            p_str,i_str=token.split(":",1)
            key=(int(p_str),int(i_str))
        except (ValueError,TypeError):
            raise ValueError("--recover-noreply expects PASS:INDEX, e.g. 1:9")
        if key not in reply_attempts or key not in confirmed or key in reply_committed or key in abandoned:
            raise ValueError("No pending confirmed reflection at %s"%token)
        if any(r.get("event")=="reply_uncertain" and
               (r.get("pass"),r.get("index"))==key and
               legacy.err_type(r.get("api_response")) not in
               ("NoReply","RoomNomiNotReadyForMessage","RoomStillCreating","TooManyRequests") for r in old):
            raise ValueError("Cannot recover ambiguous reply outcome at %s"%token)
        recovery.add(key)
    # Explicit operator-authorized recovery for an ambiguous reply POST, such as
    # an HTTP 502. This can cause a duplicate reply; never repeat the prompt.
    for token in getattr(args,"recover_uncertain_reply",[]) or []:
        try:
            p_str,i_str=token.split(":",1)
            key=(int(p_str),int(i_str))
        except (ValueError,TypeError):
            raise ValueError("--recover-uncertain-reply expects PASS:INDEX, e.g. 1:559")
        if key not in confirmed or key not in reply_attempts or key in reply_committed or key in abandoned:
            raise ValueError("No pending confirmed reflection at %s"%token)
        if not any(r.get("event")=="reply_uncertain" and
                   (r.get("pass"),r.get("index"))==key for r in old):
            raise ValueError("No recorded uncertain reply result at %s"%token)
        recovery.add(key)
        record(cp,{"event":"reply_operator_override","pass":key[0],"index":key[1],
                   "reason":"operator authorized retry after ambiguous reply outcome"})
    # Earlier versions incorrectly treated explicit Nomi readiness errors as
    # ambiguous. The recorded HTTP response proves the request was rejected.
    retryable_previous={
        (r["pass"],r["index"]) for r in old
        if r.get("event")=="reply_uncertain"
        and r.get("http_status") is not None
        and legacy.err_type(r.get("api_response")) in KNOWN_WAIT_ERRORS
    }
    recovery |= retryable_previous & reply_attempts & confirmed
    recovery -= abandoned

    if getattr(args,"easy",False) and sys.stdin.isatty():
        for key in sorted(uncertain_sends-send_retry_authorized):
            print("\nThe previous upload stopped while sending pass %d message %d."%key)
            print("It may already have reached Nomi. Resending could create one duplicate.")
            if input("Resend that message and continue? [y/N]: ").strip().lower() in ("y","yes"):
                send_retry_authorized.add(key)
        pending_reply=reply_attempts-reply_committed-recovery-abandoned
        for key in sorted(pending_reply):
            print("\nNomi's last reflection request has an unknown outcome at pass %d message %d."%key)
            print("The diary content is already confirmed. Retrying may create an extra reply.")
            if input("Retry the reply request and continue? [y/N]: ").strip().lower() in ("y","yes"):
                recovery.add(key)
                record(cp,{"event":"reply_operator_override","pass":key[0],"index":key[1],
                           "reason":"friendly operator authorized retry after ambiguous reply outcome"})

    uncertain=(uncertain_sends-send_retry_authorized)|(reply_attempts-reply_committed-recovery-abandoned)
    if uncertain:
        raise RuntimeError("Uncertain send/reply request(s) %s. Inspect room before manual checkpoint repair; no automatic retry."%sorted(uncertain))
    if migrating or migration_pending: room=migrate_resume(cp,records(cp),nomi,room)
    if any(e.get("event")=="room_migrated" for e in records(cp)): legacy.wait_for_room(room)
    for p,i in sorted(recovery):
        record(cp,{"event":"reply_recovery_authorized","pass":p,"index":i,
                   "reason":"explicit Nomi not-ready response or operator-verified NoReply"})
        print("Resuming reflection after explicit Nomi not-ready response: pass %d message %d"%(p,i),flush=True)
    for p in range(1,passes+1):
        for i,m in enumerate(messages,1):
            key=(p,i)
            if key not in confirmed:
                if key in send_retry_authorized:
                    record(cp,{"event":"send_retry_authorized","pass":p,"index":i,
                               "kind":m["kind"],
                               "sha256":hashlib.sha256(m["text"].encode()).hexdigest(),
                               "reason":"operator authorized repeat of ambiguous POST; duplicate possible"})
                    print("Authorized resend: pass %d message %d (duplicate possible)" % (p,i),flush=True)
                transport={k:m[k] for k in ("entry_label","part","parts") if k in m}
                record(cp,{"event":"attempt","pass":p,"index":i,
                           "sha256":hashlib.sha256(m["text"].encode()).hexdigest(),
                           **transport})
                s,response=legacy.api_request("/rooms/"+room+"/chat","POST",
                                              {"messageText":m["text"]})
                if not legacy.ok(s):
                    raise RuntimeError("POST outcome uncertain: "+legacy.err_text("send",s,response))
                record(cp,{"event":"confirmed","pass":p,"index":i,
                           "kind":m["kind"],"api_response":response,
                           **transport})
                detail=""
                if m.get("entry_label"):
                    detail=" — entry %s"%m["entry_label"]
                    if m.get("part"): detail+=" part %s/%s"%(m["part"],m["parts"])
                print("Pass %d/%d message %d/%d%s"%(p,passes,i,len(messages),detail))
                if args.delay: time.sleep(args.delay)
            if m["kind"]=="prompt" and key not in reply_committed and key not in abandoned:
                # IMPORTANT: KEEP THE CONTENT-COMPLETION BOUNDARY.
                #
                # Steve identified a live execution-flow discrepancy between this
                # uploader and the browser bridge: the old uploader proceeded
                # directly from posting the final prompt chunk to requesting a
                # reply within the same processing loop. The bridge explicitly
                # transitions from confirmed content to awaiting_reply first.
                # After introducing this durable transition, live uploads were
                # reported to run MUCH faster; remaining readiness errors
                # typically cleared in 15-20 seconds rather than long stalls.
                #
                # Do NOT "optimize away" this checkpoint or collapse content
                # completion into reply_attempt without a controlled regression
                # test. It is an intentional phase marker, not redundant logging.
                # The exact underlying scheduling mechanism remains unverified:
                # this record call does not itself exit the Python loop or yield
                # the thread. See CONTENT_COMPLETION_CHANGE_2026-10.md.
                record(cp,{"event":"content_complete","pass":p,"index":i,
                           "room_uuid":room,"nomi_uuid":nomi["uuid"]})
                # Reply requests are POSTs too. Never blindly repeat an uncertain request.
                record(cp,{"event":"reply_attempt","pass":p,"index":i,
                           "room_uuid":room,"nomi_uuid":nomi["uuid"]})
                s,response=request_reply_with_backoff(
                    room,nomi["uuid"],
                    max_wait=getattr(args,"reply_max_wait",0) or 0)
                if not legacy.ok(s):
                    record(cp,{"event":"reply_uncertain","pass":p,"index":i,
                               "http_status":s,"api_response":response})
                    if s is not None and legacy.err_type(response) in KNOWN_WAIT_ERRORS:
                        raise RuntimeError(
                            "Nomi is still not ready after the reply wait limit; "
                            "the checkpoint is safe to resume.")
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
                      (nomi["name"],p,i,str(body)))
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
    Path(args.completion).write_text(json.dumps({
        "version":VERSION,"room_uuid":room,
        "abandoned_replies":[list(k) for k in sorted(abandoned)],
        "nomi":nomi["name"],"passes":passes,
        "messages_per_pass":len(messages),"manifest":manifest,
        "entry_range":entry_range_text(entry_range),
        "chunk_mode":chunk_mode,"chunk_limit":chunk_limit,
        "completed_at":dt.datetime.now(dt.timezone.utc).isoformat()
    },indent=2),encoding="utf-8")
    print("Complete. Room retained:",room)

def active_room_ids(checkpoint_dir="."):
    protected=set()
    for path in Path(checkpoint_dir).glob("*.jsonl"):
        try:
            # A torn append must never release rooms. Recover only the readable
            # prefix for protection; upload itself refuses the damaged file.
            events=[]
            damaged=False
            for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
                try:
                    if not line.endswith("\n"): raise ValueError("torn tail")
                    if line.strip(): events.append(json.loads(line))
                except ValueError:
                    damaged=True
                    break
            if not events or events[0].get("event")!="start": continue
            start=events[0]
            # Release only runs with a matching completion marker AND a fully
            # confirmed checkpoint. Other runs using the same room stay protected.
            confirmed = {(e.get("pass"), e.get("index")) for e in events
                         if e.get("event") == "confirmed"}
            replied = {(e.get("pass"), e.get("index")) for e in events
                       if e.get("event") == "reply_committed"}
            prompt_positions = {(e.get("pass"), e.get("index")) for e in events
                                if e.get("event") == "confirmed"
                                and e.get("kind") == "prompt"}
            completed = False
            abandoned={(e.get("pass"),e.get("index")) for e in events if e.get("event")=="reply_abandoned"}
            rooms={start["room_uuid"]}
            for e in events:
                if e.get("event")=="room_migrated": rooms.update((e["from_room_uuid"],e["to_room_uuid"]))
                if e.get("event")=="room_migration_intent" and not any(x.get("event")=="room_migrated" and x.get("migration_id")==e["migration_id"] for x in events):
                    rooms.update(r["uuid"] for r in legacy.list_rooms() if r.get("name")==e["room_name"])
            if not damaged and prompt_positions <= replied | abandoned:
                for marker in path.parent.glob("*completed.json"):
                    try:
                        data = json.loads(marker.read_text(encoding="utf-8"))
                        expected = start.get("passes", 0) * data.get("messages_per_pass", 0)
                        if (expected and len(confirmed) == expected
                                and data.get("room_uuid") == migration_room(events)
                                and (not abandoned or data.get("abandoned_replies")==[list(k) for k in sorted(abandoned)])
                                and data.get("manifest") == start.get("manifest")
                                and data.get("passes") == start.get("passes")
                                and (not start.get("messages_per_pass") or
                                     data.get("messages_per_pass") == start["messages_per_pass"])):
                            completed = True
                            break
                    except (OSError, ValueError):
                        continue
            if not completed:
                protected.update(rooms)
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
    filt = input("Filter by Nomi name (Enter for all): ").strip()
    abandoned = input("Show only abandoned/inactive/failed rooms? (y/N): ").strip().lower() == "y"
    checkpoint_dir = input("Checkpoint directory [.] : ").strip() or "."
    rooms, protected = room_management(filt, abandoned, checkpoint_dir)
    if not rooms:
        return
    choice = input("Room number to inspect, ALL for bulk deletion, or Enter to exit: ").strip()
    if not choice:
        return
    if choice.upper() == "ALL":
        targets = rooms
    else:
        try:
            index = int(choice) - 1
        except ValueError:
            print("Invalid room number.")
            return
        if not 0 <= index < len(rooms):
            print("Invalid room number.")
            return
        targets = [rooms[index]]
        print(json.dumps(targets[0], indent=2, ensure_ascii=False))

    blocked = [r for r in targets if str(r.get("uuid", "")) in protected]
    if blocked:
        print("Protected rooms excluded:", ", ".join(str(r["uuid"]) for r in blocked))
    targets = [r for r in targets if str(r.get("uuid", "")) not in protected]
    if not targets:
        print("No eligible rooms to delete.")
        return

    print("\nRooms to delete:")
    for room in targets:
        print("  %s  %s" % (room.get("name", ""), room["uuid"]))
    print("This action cannot be undone.")
    answer = input("Delete these %d room(s)? [y/N]: " % len(targets)).strip().lower()
    if answer not in ("y", "yes"):
        print("Deletion cancelled.")
        return
    for room in targets:
        rid = str(room["uuid"])
        legacy.delete_room(rid)
        print("Deleted", rid)

def interactive_menu():
    while True:
        print("\nNomi Uploader %s\n 1 Upload files\n 2 Resume checkpoint\n 3 Dry-run\n 4 Manage rooms\n 5 Quit"%VERSION)
        action=input("Select: ").strip()
        if action in ("5","q","Q",""): return
        if action=="4": utilities(); continue
        if action not in ("1","2","3"): print("Unknown option"); continue
        argv=["--resume","--easy"] if action=="2" else []
        if action!="2":
            files=input("Input files (quoted paths supported): ").strip()
            if not files: continue
            import shlex
            argv+=shlex.split(files,posix=(os.name!="nt"))
            entries=input("Journal entries [all, e.g. 45-100]: ").strip()
            if entries: argv+=["--entries",entries]
            chars=input("Maximum characters per API message [750]: ").strip()
            if chars: argv+=["--chunk-chars",chars]
            interval=input("Process every N units [0]: ").strip()
            if interval: argv+=["--process-every",interval]
            passes=input("Passes [1]: ").strip()
            if passes: argv+=["--passes",passes]
        if action=="3": argv+=["--dry-run"]
        main(argv)

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    parser=argparse.ArgumentParser(description="Nomi Uploader v1.1")
    parser.add_argument("files",nargs="*")
    parser.add_argument("--version",action="version",version=VERSION)
    parser.add_argument("--utility",action="store_true")
    parser.add_argument("--status",action="store_true",
                        help="Read-only checkpoint status; makes no Nomi API calls")
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--easy",action="store_true",
                        help="Friendly recovery prompts for genuinely ambiguous checkpoint states")
    parser.add_argument("--new-room-on-resume",action="store_true",help="Move a stuck-reply run to a fresh room; requires --abandon-reply")
    parser.add_argument("--abandon-reply",action="append",default=[],metavar="PASS:INDEX",help="Abandon only a confirmed prompt's pending reply; requires --new-room-on-resume")
    parser.add_argument("--recover-noreply",action="append",default=[],metavar="PASS:INDEX",help="Authorize retry of a legacy checkpoint reply known to have returned NoReply")
    parser.add_argument("--recover-uncertain-reply",action="append",default=[],metavar="PASS:INDEX",help="Explicitly authorize retry after ambiguous reply POST; duplicate reply possible")
    parser.add_argument("--retry-uncertain-send",action="append",default=[],metavar="PASS:INDEX",help="Operator-authorized resend of one unconfirmed POST after a 502/timeout; duplicate message possible")
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--nomi",help="Dry-run Nomi name")
    parser.add_argument("--user",default="")
    parser.add_argument("--room",help="Reuse existing room UUID")
    parser.add_argument("--nomi-uuid",help="Select Nomi by API UUID without an interactive prompt")
    parser.add_argument("--export-options",help="JSON map of ZIP/JSON paths to prompt options")
    parser.add_argument("--passes",type=int,default=1)
    parser.add_argument("--entries",
                        help="Journal entry selection: N, START-END, START-, -END, or all")
    parser.add_argument("--process-every",type=int,default=0,help="Automatic type-aware recollection/analysis after N units; 0 disables")
    parser.add_argument("--chunk-chars",type=int,default=None,
                        help="Maximum characters in a new-run API message (default 750; hard maximum 800)")
    parser.add_argument("--chunk-bytes",type=int,default=None,
                        help="Legacy v1.0 byte planner; retained for compatibility/testing")
    parser.add_argument("--reply-max-wait",type=float,default=900,
                        help="Seconds to wait through explicit Nomi not-ready replies before cleanly stopping; 0 = unlimited")
    parser.add_argument("--date-format",choices=["AUTO","US","EU"],default="AUTO")
    parser.add_argument("--delay",type=float,default=1)
    parser.add_argument("--checkpoint",default="nomi_uploader_checkpoint.jsonl")
    parser.add_argument("--completion",default="nomi_uploader_completed.json")
    parser.add_argument("--replies",default="nomi_uploader_replies.txt")
    if not argv and sys.stdin.isatty(): return interactive_menu()
    args=parser.parse_args(argv)
    if args.status:
        print_checkpoint_status(args.checkpoint)
        return
    if args.process_every<0: parser.error("process-every must be >= 0")
    if args.passes<1: parser.error("passes must be >= 1")
    if args.chunk_chars is not None and args.chunk_bytes is not None:
        parser.error("use --chunk-chars or legacy --chunk-bytes, not both")
    if args.chunk_chars is not None and not (150<=args.chunk_chars<=MAX_API_CHARS):
        parser.error("--chunk-chars must be between 150 and %d"%MAX_API_CHARS)
    if args.chunk_bytes is not None and args.chunk_bytes<150:
        parser.error("--chunk-bytes must be >= 150")
    if args.reply_max_wait<0: parser.error("--reply-max-wait must be >= 0")
    try:
        parse_entry_range(args.entries)
    except ValueError as exc:
        parser.error(str(exc))
    if (args.recover_noreply or args.recover_uncertain_reply or args.retry_uncertain_send) and not args.resume:
        parser.error("recovery flags require --resume")
    if args.utility and (args.new_room_on_resume or args.abandon_reply):
        parser.error("migration cannot be combined with --utility")
    if args.utility: utilities()
    else: upload(args)

if __name__=="__main__":
    try: main()
    except (RuntimeError,ValueError,OSError) as exc:
        print("ERROR:",exc,file=sys.stderr); sys.exit(1)
