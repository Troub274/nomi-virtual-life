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
                    # Use source journal labels in reflection prompts, not per-file positions.
                    first_label=(units[first-1].get("label") or str(first)) if kind=="journal" else first
                    last_label=label if kind=="journal" else idx
                    custom=[p for p in section["prompts"] if not re.search(r"\\b(?:entries|episodes)\\s+\\d+\\s*[-–]\\s*\\d+\\b",p,re.I)]
                    template=custom[0] if len(custom)==1 else PERIODIC_PROMPTS[default_key]
                    prompt=render_prompt(template.format(first=first_label,last=last_label),nomi,user,source)
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
                elif not interval:
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

def request_reply_with_backoff(room, nomi_uuid, attempts=None, base_delay=1.0):
    """Wait through explicit Nomi not-ready responses; stop on ambiguous errors."""
    delay=base_delay
    n=0
    while True:
        n+=1
        status,payload=legacy.api_request("/rooms/"+room+"/chat/request","POST",
                                          {"nomiUuid":nomi_uuid})
        if legacy.ok(status):
            return status,payload
        error=legacy.err_text("request reply",status,payload)
        if (status is not None and legacy.err_type(payload) in
                ("NoReply","RoomNomiNotReadyForMessage","RoomStillCreating","TooManyRequests")):
            if attempts is not None and n>=attempts:
                print("Nomi API error: %s; test retry limit reached"%error,
                      file=sys.stderr,flush=True)
                return status,payload
            print("Nomi API error: %s; %s attempt %d; retry in %.1fs"%
                  (error,legacy.err_type(payload),n,delay),file=sys.stderr,flush=True)
            time.sleep(delay)
            delay=min(delay*2,30)
            continue
        print("Nomi API error: %s; request outcome uncertain; not retrying"%error,
              file=sys.stderr,flush=True)
        return status,payload


def create_upload_room(nomi):
    name="UPLOADER::%s::%s"%(nomi["name"],dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    s,p=legacy.api_request("/rooms","POST",{"name":name,"note":"Nomi Uploader v1.0 — persistent processing room","backchannelingEnabled":True,"nomiUuids":[nomi["uuid"]]})
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
        else: room=select_or_create_room(nomi, cp.parent)
        record(cp,{"event":"start","run_id":str(uuid.uuid4()),"nomi_uuid":nomi["uuid"],"nomi_name":nomi["name"],"room_uuid":room,"year":year,"order":order,"files":files,"passes":passes,"messages_per_pass":len(messages),"manifest":manifest,"user":args.user,"chunk_bytes":args.chunk_bytes,"process_every":args.process_every})
        old=records(cp)
    attempts={(r["pass"],r["index"]) for r in old if r.get("event")=="attempt"}
    confirmed={(r["pass"],r["index"]) for r in old if r.get("event")=="confirmed"}
    reply_attempts={(r["pass"],r["index"]) for r in old if r.get("event")=="reply_attempt"}
    reply_committed={(r["pass"],r["index"]) for r in old if r.get("event")=="reply_committed"}
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
        if key not in reply_attempts or key not in confirmed or key in reply_committed:
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
        if key not in confirmed or key not in reply_attempts or key in reply_committed:
            raise ValueError("No pending confirmed reflection at %s"%token)
        if not any(r.get("event")=="reply_uncertain" and
                   (r.get("pass"),r.get("index"))==key for r in old):
            raise ValueError("No recorded uncertain reply result at %s"%token)
        recovery.add(key)
        record(cp,{"event":"reply_operator_override","pass":key[0],"index":key[1],
                   "reason":"operator authorized retry after ambiguous reply outcome"})
    # Earlier versions incorrectly treated explicit Nomi readiness errors as
    # ambiguous. The recorded HTTP response proves the request was rejected.
    known_wait_errors={"NoReply","RoomNomiNotReadyForMessage",
                       "RoomStillCreating","TooManyRequests"}
    retryable_previous={
        (r["pass"],r["index"]) for r in old
        if r.get("event")=="reply_uncertain"
        and r.get("http_status") is not None
        and legacy.err_type(r.get("api_response")) in known_wait_errors
    }
    recovery |= retryable_previous & reply_attempts & confirmed
    uncertain=(uncertain_sends-send_retry_authorized)|(reply_attempts-reply_committed-recovery)
    if uncertain:
        raise RuntimeError("Uncertain send/reply request(s) %s. Inspect room before manual checkpoint repair; no automatic retry."%sorted(uncertain))
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
                s,response=request_reply_with_backoff(room,nomi["uuid"])
                if not legacy.ok(s):
                    record(cp,{"event":"reply_uncertain","pass":p,"index":i,
                               "http_status":s,"api_response":response})
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
    Path(args.completion).write_text(json.dumps({"version":VERSION,"room_uuid":room,"nomi":nomi["name"],"passes":passes,"messages_per_pass":len(messages),"manifest":manifest,"completed_at":dt.datetime.now(dt.timezone.utc).isoformat()},indent=2),encoding="utf-8")
    print("Complete. Room retained:",room)

def active_room_ids(checkpoint_dir="."):
    protected=set()
    for path in Path(checkpoint_dir).glob("*.jsonl"):
        try:
            events=records(path)
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
            if prompt_positions <= replied:
                for marker in path.parent.glob("*completed.json"):
                    try:
                        data = json.loads(marker.read_text(encoding="utf-8"))
                        expected = start.get("passes", 0) * data.get("messages_per_pass", 0)
                        if (expected and len(confirmed) == expected
                                and data.get("room_uuid") == start["room_uuid"]
                                and data.get("manifest") == start.get("manifest")
                                and data.get("passes") == start.get("passes")
                                and (not start.get("messages_per_pass") or
                                     data.get("messages_per_pass") == start["messages_per_pass"])):
                            completed = True
                            break
                    except (OSError, ValueError):
                        continue
            if not completed:
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
    parser=argparse.ArgumentParser(description="Nomi Uploader v1.0")
    parser.add_argument("files",nargs="*")
    parser.add_argument("--version",action="version",version=VERSION)
    parser.add_argument("--utility",action="store_true")
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--recover-noreply",action="append",default=[],metavar="PASS:INDEX",help="Authorize retry of a legacy checkpoint reply known to have returned NoReply")
    parser.add_argument("--recover-uncertain-reply",action="append",default=[],metavar="PASS:INDEX",help="Explicitly authorize retry after ambiguous reply POST; duplicate reply possible")
    parser.add_argument("--retry-uncertain-send",action="append",default=[],metavar="PASS:INDEX",help="Operator-authorized resend of one unconfirmed POST after a 502/timeout; duplicate message possible")
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
    if (args.recover_noreply or args.recover_uncertain_reply or args.retry_uncertain_send) and not args.resume: parser.error("recovery flags require --resume")
    if args.utility: utilities()
    else: upload(args)

if __name__=="__main__":
    try: main()
    except (RuntimeError,ValueError,OSError) as exc:
        print("ERROR:",exc,file=sys.stderr); sys.exit(1)
