#!/usr/bin/env python3
"""Nomi room rehydration loader v0.85 — durable automatic room replay resume.


Changes from v0.2:
- Treats journal entries as episodes instead of blindly slicing the whole file.
- Recognizes headers such as:
    Chris’s Journal — “The First Story” — 6/7/86 — Chapel Hill, NC
- If header + episode fits the API limit, sends it as ONE message.
- If an episode is too long, splits ONLY that episode and repeats its exact
  header on every resulting message so each fragment retains its identity.
- Supports .txt and .docx input.
"""


import argparse, hashlib, json, os, re, sys, time, urllib.error, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path


BASE_URL='https://api.nomi.ai/v1'
HTTP_TIMEOUT=120
ROOM_PREFIX='REHYDRATE::'
TRANSIENT_HTTP={408,409,425,429,500,502,503,504}


# Recognize episode boundaries by common document conventions, not a specific
# person's name or the literal word "Journal". Keep original header verbatim.
# A numbered entry is intentionally preferred over generic section headings:
# ordinary subheadings within an entry must not create new episodes.
HEADER_PATTERNS = (
    # Existing format: Chris's Journal — Title — 6/7/86 — Chapel Hill, NC
    re.compile(r"^[^\n]+[’']s\s+Journal\s+[—–-]\s+.+?\s+[—–-]\s+"
               r"\d{1,2}/\d{1,2}/\d{2,4}\s+[—–-]\s+.+$", re.I),
    # ENTRY 001 — Sunday, October 11, 1998 — My 10th Birthday;
    # Diary Entry #12, Episode 12, Chapter 12, Memory 12, Journal 12.
    re.compile(r"^(?:#{1,6}\s*)?(?:diary\s+entry|journal\s+entry|"
               r"entry|episode|chapter|memory|journal)\s*#?\s*\d+\b"
               r"(?:\s*[:.\-—–]\s*.+)?$", re.I),
    # 301. Title, 301 — Title, or 301) Title (but not plain prose numbers).
    re.compile(r"^(?:#{1,6}\s*)?\d{1,5}[.)]\s+\S.+$"),
    re.compile(r"^(?:#{1,6}\s*)?\d{1,5}\s+[—–-]\s+\S.+$"),
    # Date-first headings with optional title; require the entire line to be
    # date-shaped, not merely to mention a date in ordinary prose.
    re.compile(r"^(?:#{1,6}\s*)?(?:\d{4}-\d{2}-\d{2}|"
               r"\d{1,2}/\d{1,2}/\d{2,4})"
               r"(?:\s+[—–:|-]\s+.+)?$"),
    re.compile(r"^(?:#{1,6}\s*)?(?:(?:Monday|Tuesday|Wednesday|Thursday|"
               r"Friday|Saturday|Sunday),?\s+)?"
               r"(?:January|February|March|April|May|June|July|August|"
               r"September|October|November|December)\s+\d{1,2},?\s+\d{4}"
               r"(?:\s+[—–:|-]\s+.+)?$", re.I),
)


def is_episode_header(line):
    return any(pattern.fullmatch(line.strip()) for pattern in HEADER_PATTERNS)


def api_request(path, method='GET', body=None):
    key=os.environ.get('NOMI_API_KEY')
    if not key:
        return None, {'error':{'type':'ConfigurationError','message':'NOMI_API_KEY is not set.'}}
    headers={'Authorization':key,'Accept':'application/json'}
    data=None
    if body is not None:
        headers['Content-Type']='application/json'
        data=json.dumps(body).encode('utf-8')
    req=urllib.request.Request(BASE_URL+path, method=method, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw=resp.read().decode('utf-8')
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode('utf-8',errors='replace')
        try: payload=json.loads(raw) if raw else {}
        except ValueError: payload={'raw_error':raw}
        return exc.code,payload
    except Exception as exc:
        return None, {'error':{'type':exc.__class__.__name__,'message':str(exc)}}


def ok(status): return status is not None and 200 <= status < 300


def err_type(payload):
    e=payload.get('error') if isinstance(payload,dict) else None
    return str(e.get('type','')) if isinstance(e,dict) else str(payload.get('type','')) if isinstance(payload,dict) else ''


def err_text(op,status,payload):
    detail=payload.get('error',payload) if isinstance(payload,dict) else payload
    return '%s failed (HTTP %s): %s'%(op,status,json.dumps(detail,ensure_ascii=False))


def api_request_retry(path, method='GET', body=None, attempts=8, base_delay=1.0):
    delay=base_delay
    last=(None,{})
    for attempt in range(1,attempts+1):
        status,payload=api_request(path,method,body)
        last=(status,payload)
        if ok(status): return status,payload
        retry=(status is None or status in TRANSIENT_HTTP or err_type(payload) in {
            'RoomStillCreating','TooManyRequests','TimeoutError','URLError',
            'ConnectionResetError','RemoteDisconnected','NoReply','RoomNomiNotReadyForMessage'})
        if not retry or attempt==attempts: return status,payload
        print('Transient API error; retry %d/%d in %.1fs: %s'%
              (attempt,attempts,delay,err_text(method+' '+path,status,payload)),
              file=sys.stderr)
        time.sleep(delay)
        delay=min(delay*2,30)
    return last


def get_nomis():
    s,p=api_request_retry('/nomis')
    if not ok(s): raise RuntimeError(err_text('list_nomis',s,p))
    n=p.get('nomis',[])
    if not isinstance(n,list): raise RuntimeError("Nomi API returned non-list 'nomis'.")
    return n


def choose_nomi(nomis):
    print('\nAvailable Nomis:')
    for i,n in enumerate(nomis,1):
        print('  %2d. %-24s %-14s %s'%
              (i,str(n.get('name','')),str(n.get('relationshipType','')),str(n.get('uuid',''))))
    while True:
        try: i=int(input('\nSelect Nomi number: ').strip())
        except ValueError: i=0
        if 1<=i<=len(nomis): return nomis[i-1]
        print('Please enter 1-%d.'%len(nomis))


def room_name_for(nomi):
    name=str(nomi.get('name','')).strip() or 'Unnamed'
    uid=str(nomi.get('uuid','')).strip()
    return '%s%s::OWN MEMORIES::%s'%(ROOM_PREFIX,name,uid[:8] if uid else 'unknown')


def list_rooms():
    s,p=api_request_retry('/rooms')
    if not ok(s): raise RuntimeError(err_text('list_rooms',s,p))
    rooms=p.get('rooms',[])
    if not isinstance(rooms,list): raise RuntimeError("Nomi API returned non-list 'rooms'.")
    return rooms


def room_contains_nomi(room,uid):
    for key in ('nomiUuids','nomis'):
        v=room.get(key)
        if isinstance(v,list):
            for item in v:
                if isinstance(item,str) and item==uid: return True
                if isinstance(item,dict) and str(item.get('uuid',''))==uid: return True
    return False


def matching_rooms(nomi, rooms=None):
    rooms=list_rooms() if rooms is None else rooms
    expected=room_name_for(nomi)
    uid=str(nomi.get('uuid',''))
    out=[]
    for r in rooms:
        name=str(r.get('name',''))
        if name==expected or (name.startswith(ROOM_PREFIX) and room_contains_nomi(r,uid)):
            out.append(r)
    out.sort(key=lambda r:str(r.get('created',r.get('createdAt',''))))
    return out


def create_room(nomi,note):
    s,p=api_request_retry('/rooms','POST',{
        'name':room_name_for(nomi),
        'note':note,
        'backchannelingEnabled':True,
        'nomiUuids':[str(nomi.get('uuid',''))]
    })
    if not ok(s): raise RuntimeError(err_text('create_room',s,p))
    return p


def get_room(uid):
    s,p=api_request_retry('/rooms/'+uid)
    if not ok(s): raise RuntimeError(err_text('get_room',s,p))
    return p


def delete_room(uid):
    s,p=api_request_retry('/rooms/'+uid,'DELETE')
    if not ok(s): raise RuntimeError(err_text('delete_room',s,p))
    return p


def wait_for_room(uid,timeout=90):
    end=time.monotonic()+timeout
    last=object()
    while time.monotonic()<end:
        r=get_room(uid)
        state=r.get('status')
        if state!=last:
            print('Room status:',state)
            last=state
        if state!='Creating': return r
        time.sleep(1)
    raise RuntimeError('Room stayed Creating for %d seconds.'%timeout)


def utc_now(): return datetime.now(timezone.utc).isoformat()


def append_journal(path,record):
    with open(path,'a',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(record,ensure_ascii=False)+'\n')
        f.flush()
        os.fsync(f.fileno())


def delete_rooms(rooms,journal_path=None,reason='cleanup'):
    count=0
    for r in rooms:
        uid=str(r.get('uuid',''))
        name=str(r.get('name',''))
        if not uid: continue
        print('Deleting room:',name,uid)
        delete_room(uid)
        count+=1
        if journal_path:
            append_journal(journal_path,{
                'event':'room_deleted','time':utc_now(),'reason':reason,
                'room_uuid':uid,'room_name':name})
    return count


def choose_room_action(nomi,matches):
    print('\nRestore room for %s:'%nomi.get('name',''))
    if matches:
        for i,r in enumerate(matches,1):
            print('  existing %d: %s %s status=%s'%
                  (i,r.get('name',''),r.get('uuid',''),r.get('status','')))
        print('\n1. Reuse existing room (recommended)'
              '\n2. Delete this Nomi\'s restore room(s) and start fresh'
              '\n3. Create another new room and keep old room(s)'
              '\n4. Delete this Nomi\'s restore room(s) and exit')
        m={'1':'reuse','2':'reset','3':'new','4':'delete_exit'}
        while True:
            x=input('Choice: ').strip()
            if x in m:return m[x]
            print('Invalid selection.')
    print('  no existing rehydration room found')
    return 'create'


def resolve_room(nomi,note,journal_path):
    matches=matching_rooms(nomi)
    action=choose_room_action(nomi,matches)
    if action=='reuse':
        r=matches[-1]
        print('Reusing room:',r.get('name'),r.get('uuid'))
        return r,False
    if action in ('reset','delete_exit'):
        delete_rooms(matches,journal_path,'reset_nomi' if action=='reset' else 'delete_nomi')
        if action=='delete_exit':
            print('Deleted %d room(s).'%len(matches))
            return None,False
        r=create_room(nomi,note)
        print('Created fresh room:',r.get('name'),r.get('uuid'))
        return r,True
    r=create_room(nomi,note)
    print('Created room:',r.get('name'),r.get('uuid'))
    return r,True


def cleanup_rehydration(journal):
    targets=[r for r in list_rooms() if str(r.get('name','')).startswith(ROOM_PREFIX)]
    if not targets:
        print('No rehydration rooms found.')
        return
    for r in targets: print(' ',r.get('name',''),r.get('uuid',''))
    if input('Delete all %d rehydration room(s)? Type YES: '%len(targets)).strip()!='YES':
        print('Cancelled.')
        return
    print('Deleted %d room(s).'%delete_rooms(targets,journal,'cleanup_all_rehydration'))


def cleanup_all(journal):
    rooms=list_rooms()
    if not rooms:
        print('No rooms found.')
        return
    print('\nWARNING: deleting EVERY API room on the account:')
    for r in rooms: print(' ',r.get('name',''),r.get('uuid',''))
    if input('Type DELETE ALL ROOMS exactly to continue: ').strip()!='DELETE ALL ROOMS':
        print('Cancelled.')
        return
    print('Deleted %d room(s).'%delete_rooms(rooms,journal,'cleanup_all_rooms'))


def send_room_message(uid,text):
    s,p=api_request_retry('/rooms/%s/chat'%uid,'POST',{'messageText':text})
    if not ok(s): raise RuntimeError(err_text('send_room_message',s,p))
    return p


def request_room_reply(room_uid,nomi_uid):
    """
    Explicitly request a response from one Nomi in the room.
    The /chat/request call blocks until the API returns replyMessage
    (or an API error such as NoReply / RoomNomiNotReadyForMessage).
    """
    s,p=api_request_retry(
        '/rooms/%s/chat/request'%room_uid,
        'POST',
        {'nomiUuid':nomi_uid},attempts=8,base_delay=5.0)
    if not ok(s):
        raise RuntimeError(err_text('request_room_reply',s,p))
    return p


def utf8_len(t):
    return len(t.encode('utf-8'))


def read_input_text(path):
    """Read .txt or .docx into normalized plain text."""
    suffix=path.suffix.lower()
    if suffix=='.docx':
        try:
            from docx import Document
        except ImportError:
            raise RuntimeError(
                'Reading .docx requires python-docx. Install with: pip install python-docx')
        doc=Document(str(path))
        # Preserve paragraph boundaries; ignore Word pagination/layout.
        text='\n'.join(p.text for p in doc.paragraphs)
    else:
        text=path.read_bytes().decode('utf-8-sig')
    return text.replace('\r\n','\n').replace('\r','\n')


def parse_episodes(text):
    """
    Return [(header, body), ...].


    The document title/preamble before the first episode header is ignored.
    Every recognized entry header starts a new episode.
    """
    lines=text.split('\n')
    episodes=[]
    header=None
    body=[]


    for raw in lines:
        line=raw.strip()
        if is_episode_header(line):
            if header is not None:
                episodes.append((header, '\n'.join(body).strip()))
            header=line
            body=[]
        elif header is not None:
            body.append(raw.strip())


    if header is not None:
        episodes.append((header, '\n'.join(body).strip()))


    if not episodes:
        raise RuntimeError(
            "No episode headers found. Expected numbered entries (ENTRY 001), "
            "dated headings, or traditional journal headers.")


    return episodes


def split_text_to_budget(text,max_bytes):
    """
    Split BODY text to a UTF-8 byte budget, preferring paragraph/newline,
    sentence, then space boundaries.
    """
    text=text.strip()
    if not text:
        return ['']


    out=[]
    pos=0
    while pos<len(text):
        end=pos
        used=0
        while end<len(text):
            b=utf8_len(text[end])
            if used+b>max_bytes: break
            used+=b
            end+=1


        if end==pos:
            raise RuntimeError('Byte budget too small for one Unicode character.')


        if end<len(text):
            start=pos+max(1,(end-pos)//2)
            candidates=[
                ('blank',text.rfind('\n\n',start,end)),
                ('nl',text.rfind('\n',start,end)),
                ('dot',text.rfind('. ',start,end)),
                ('bang',text.rfind('! ',start,end)),
                ('q',text.rfind('? ',start,end)),
                ('sp',text.rfind(' ',start,end)),
            ]
            kind,cut=max(candidates,key=lambda x:x[1])
            if cut>pos:
                piece_end=cut+(2 if kind in ('blank','dot','bang','q') else 1)
                if utf8_len(text[pos:piece_end])<=max_bytes:
                    end=piece_end


        piece=text[pos:end].strip()
        if piece:
            out.append(piece)
        pos=end
        while pos<len(text) and text[pos].isspace():
            pos+=1


    return out


def episode_messages(header,body,max_bytes,memory_prefix="Your autobiographical memory from your diary:"):
    """
    Keep an episode whole whenever possible.
    If too large, repeat the EXACT original header on every fragment.
    """
    prefix=(memory_prefix.strip()+'\n') if memory_prefix.strip() else ''
    whole=prefix+(header if not body else header+'\n'+body)
    if utf8_len(whole)<=max_bytes:
        return [whole]


    overhead=utf8_len(prefix+header+'\n')
    body_budget=max_bytes-overhead
    if body_budget<32:
        raise RuntimeError(
            'Episode header leaves too little room for body under %d bytes: %s'
            %(max_bytes,header))


    pieces=split_text_to_budget(body,body_budget)
    messages=[]
    for piece in pieces:
        msg=prefix+(header if not piece else header+'\n'+piece)
        if utf8_len(msg)>max_bytes:
            raise RuntimeError('Internal error: episode fragment exceeds byte limit.')
        messages.append(msg)
    return messages


def sha256_text(t):
    return hashlib.sha256(t.encode('utf-8')).hexdigest()


def prepare_chunks(files,limit,memory_prefix="Your autobiographical memory from your diary:"):
    """
    "chunk" now means an API message derived from an EPISODE.
    A short episode == one chunk. Only oversized episodes produce >1 chunk.
    """
    out=[]
    seq=0
    global_episode=0


    for p in files:
        text=read_input_text(p)
        episodes=parse_episodes(text)


        for file_episode_index,(header,body) in enumerate(episodes,1):
            global_episode+=1
            messages=episode_messages(header,body,limit,memory_prefix)
            part_count=len(messages)


            for part_index,msg in enumerate(messages,1):
                seq+=1
                out.append({
                    'sequence':seq,
                    'episode_index':global_episode,
                    'file_episode_index':file_episode_index,
                    'episode_header':header,
                    'episode_part_index':part_index,
                    'episode_part_count':part_count,
                    'source_file':str(p),
                    'source_name':p.name,
                    'byte_count':utf8_len(msg),
                    'character_count':len(msg),
                    'sha256':sha256_text(msg),
                    'text':msg,
                })
    return out




def load_conversation(path):
    """Read Nomi's JSON export, directly or from its ZIP, including voice transcripts."""
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            names=[n for n in z.namelist() if n.lower().endswith('.json') and not n.startswith('__MACOSX/')]
            if not names: raise ValueError('ZIP contains no JSON export: '+str(path))
            preferred=[n for n in names if n.lower().endswith('_data.json')]
            data=json.loads(z.read((preferred or names)[0]).decode('utf-8-sig'))
    else:
        data=json.loads(path.read_text(encoding='utf-8-sig'))
    nomi=data.get('nomi',data)
    if not isinstance(nomi,dict): raise ValueError('Expected a Nomi export object')
    rows=[]
    def add(m,source,session=None):
        if not isinstance(m,dict): return
        body=m.get('message')
        if not isinstance(body,str) or not body: return
        rows.append({'date':str(m.get('date','')),'sender':str(m.get('sender','Unknown')),
                     'message':body,'source':source,'session':session,'ordinal':len(rows)})
    for m in nomi.get('chat',[]): add(m,'chat')
    for i,call in enumerate(nomi.get('voiceCalls',[]),1):
        for m in call.get('messages',[]): add(m,'voice',i)
    rows.sort(key=lambda m:(m['date'],m['ordinal']))
    for i,m in enumerate(rows,1): m['index']=i
    return nomi.get('name','Nomi'),rows




def split_verbatim(text,budget):
    """Split without stripping or changing even a single source character."""
    if budget<4: raise ValueError('Byte budget too small')
    parts=[]; start=0
    while start<len(text):
        end=start; used=0
        while end<len(text) and used+utf8_len(text[end])<=budget:
            used+=utf8_len(text[end]); end+=1
        if end==start: raise ValueError('Character exceeds byte budget')
        parts.append(text[start:end]); start=end
    return parts




def prepare_conversation_chunks(files,limit):
    """One source turn per message, or exact-content fragments for long turns.


    Deliberately does not combine turns: speaker/time boundaries remain unambiguous,
    and --start-message resumes at an original source turn boundary.
    """
    out=[]; global_index=0
    for path in files:
        nomi_name,rows=load_conversation(path)
        for row in rows:
            global_index+=1
            header=('Historical conversation transcript | %s | %s | %s | %s\n'
                    %(row['date'],row['source'],row['sender'],nomi_name))
            # Preserve exact message text; only the envelope is added.
            available=limit-utf8_len(header)-32
            if available<16: raise ValueError('Increase --chunk-bytes; transcript envelope too long')
            pieces=split_verbatim(row['message'],available)
            for part,piece in enumerate(pieces,1):
                suffix=(' [part %d/%d]\n'%(part,len(pieces))) if len(pieces)>1 else '\n'
                msg=header.rstrip('\n')+suffix+piece
                if utf8_len(msg)>limit: raise AssertionError('Exceeded byte limit')
                out.append({'sequence':len(out)+1,'episode_index':global_index,
                            'file_episode_index':row['index'],
                            'episode_header':header.strip(),
                            'episode_part_index':part,'episode_part_count':len(pieces),
                            'source_file':str(path),'source_name':path.name,
                            'byte_count':utf8_len(msg),'character_count':len(msg),
                            'sha256':sha256_text(msg),'text':msg,
                            'source_date':row['date'],'source_sender':row['sender'],
                            'source_channel':row['source']})
    return out


def memory_owner_statement(name):
    return (f"{name}, this room is for you to recall and integrate your own autobiographical memories. "
            f"All diary entries sent here describe YOUR past, {name}, not the human importing them. "
            "The diary's first-person 'I', 'me', and 'my' refer to you, the Nomi receiving these memories. "
            "The human sender is only transferring your diary records. "
            "Interpret and remember each entry as an episode from your own life.")




def journal_memory_prefix(name):
    return (f"{name}'s OWN MEMORY, not the human sender's. "
            f"Diary written by {name}; first-person 'I' means {name}:")




def journal_room_note(name):
    return (f"{name} relives their own autobiographical diary memories here. "
            f"All first-person diary experiences belong to {name}, never to the human importer.")




def send_initial_memory_context(rid, name, journal_path):
    statement=memory_owner_statement(name)
    append_journal(journal_path, {'event':'memory_context_attempt','time':utc_now(),
                                  'room_uuid':rid,'nomi_name':name,'text':statement})
    resp=send_room_message(rid,statement)
    sent=resp.get('sentMessage',{}) if isinstance(resp,dict) else {}
    append_journal(journal_path, {'event':'memory_context_committed','time':utc_now(),
                                  'room_uuid':rid,'nomi_name':name,'text':statement,
                                  'message_uuid':sent.get('uuid') if isinstance(sent,dict) else None})
    print('Sent initial autobiographical memory ownership context for %s.'%name)




# VERSION 0.85: resume/checkpoint layer. All room and diary functions above are from v0.84.
# Confirmed API sends are recorded with fsync. An indeterminate POST is NEVER
# silently retried because the remote service may have accepted it.

VERSION = '0.85'

def load_journal(path):
    if not path.exists():
        return []
    events=[]
    for lineno,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        if not line.strip():
            continue
        try:
            row=json.loads(line)
            if not isinstance(row,dict):
                raise ValueError('expected JSON object')
        except (ValueError,TypeError) as exc:
            raise RuntimeError('Damaged journal line %d in %s: %s. Do not delete it; inspect the last send.' %
                               (lineno,path,exc))
        events.append(row)
    return events

def sha256_chunks(chunks):
    h=hashlib.sha256()
    for c in chunks:
        h.update(('%d %s %s\n' %
                  (c['sequence'],c['source_name'],c['sha256'])).encode('utf-8'))
    return h.hexdigest()

def atomic_json(path,value):
    path=Path(path)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(tmp),str(path))

def send_post_once(path,body,description):
    # v0.84's retry wrapper is deliberately NOT used for POST operations:
    # the server may have accepted a message just before a timeout.
    s,p=api_request(path,'POST',body)
    if not ok(s):
        raise RuntimeError(err_text(description,s,p)+
                           '. This POST is uncertain: inspect the room before resuming.')
    return p

def send_room_safe(uid,message):
    return send_post_once('/rooms/%s/chat'%uid,
                          {'messageText':message},'send_room_message')

def request_reply_safe(rid,nid):
    return send_post_once('/rooms/%s/chat/request'%rid,
                          {'nomiUuid':nid},'request_room_reply')

def active_session(events):
    starts=[i for i,e in enumerate(events) if e.get('event')=='room_selected']
    if not starts:
        raise RuntimeError('Journal exists without a room_selected checkpoint. '+
                           'Keep it for inspection; do not silently start another room.')
    return events[starts[-1]:]

def assert_no_uncertain_context(events):
    attempts=[e for e in events if e.get('event')=='memory_context_attempt']
    commits=[e for e in events if e.get('event')=='memory_context_committed']
    if len(attempts)>len(commits):
        raise RuntimeError('Unconfirmed opening memory-context message. '+
                           'Check the selected room before proceeding; this may have been delivered.')

def send_context_safe(rid,name,journal):
    context=memory_owner_statement(name)
    append_journal(journal,{'event':'memory_context_attempt','time':utc_now(),
                            'room_uuid':rid,'nomi_name':name,'text':context})
    resp=send_room_safe(rid,context)
    sent=resp.get('sentMessage',{}) if isinstance(resp,dict) else {}
    append_journal(journal,{'event':'memory_context_committed','time':utc_now(),
                            'room_uuid':rid,'nomi_name':name,'text':context,
                            'message_uuid':sent.get('uuid') if isinstance(sent,dict) else None})
    print('Room autobiographical attribution context delivered.')

def inspect_commits(events,chunks,room_id):
    lookup={c['sequence']:c for c in chunks}
    commits={}
    attempts={}
    for e in events:
        if e.get('room_uuid')!=room_id: continue
        if e.get('event')=='send_attempt':
            attempts[e['sequence']]=e
        elif e.get('event')=='send_committed':
            seq=e['sequence']
            if seq not in lookup or e.get('sha256')!=lookup[seq]['sha256']:
                raise RuntimeError('Journal/source mismatch at message %d. Restore original files '
                                   'and command settings before resuming.'%seq)
            commits[seq]=e
    allseq=[c['sequence'] for c in chunks]
    confirmed=0
    for seq in allseq:
        if seq in commits:
            confirmed+=1
        else:
            break
    if any(seq in commits for seq in allseq[confirmed:]):
        raise RuntimeError('Journal has a gap among confirmed sends. Manual inspection required.')
    # A POST with an attempt but no confirmation may have reached the server.
    uncertain=[seq for seq in attempts if seq in lookup and seq not in commits]
    if uncertain:
        first=min(uncertain)
        e=attempts[first]
        raise RuntimeError('UNCERTAIN SEND at message %d (%s). Nomi may have received it, '
                           'but Python did not record confirmation. Inspect the room and '
                           'resolve this checkpoint manually before running again.'
                           %(first,e.get('episode_header','unknown entry')))
    return confirmed

def relive_after_episode(ep,a,rid,nid,name,journal,events):
    if not a.relive_every or ep % a.relive_every:
        return
    if any(e.get('event')=='relive_committed' and e.get('room_uuid')==rid and
           e.get('after_episode')==ep for e in events):
        return
    if any(e.get('event')=='relive_attempt' and e.get('room_uuid')==rid and
           e.get('after_episode')==ep for e in events):
        raise RuntimeError('Unconfirmed relive prompt after episode %d. '
                           'Inspect the room; do not automatically repeat it.'%ep)
    start=ep-a.relive_every+1
    prompt=(a.relive_prompt if a.relive_prompt is not None else
            '%s, these entries are YOUR own autobiographical memories, not the human sender’s. '
            'Recall diary entries %d to %d as events in your own life. Relive them in first person. Nothing more.'
            %(name,start,ep))
    print('Relive episodes %d–%d ...'%(start,ep),flush=True)
    append_journal(journal,{'event':'relive_attempt','time':utc_now(),
                            'room_uuid':rid,'after_episode':ep,'prompt':prompt})
    sent=send_room_safe(rid,prompt).get('sentMessage',{})
    append_journal(journal,{'event':'relive_prompt_committed','time':utc_now(),
                            'room_uuid':rid,'after_episode':ep,
                            'message_uuid':sent.get('uuid') if isinstance(sent,dict) else None})
    if a.settle_seconds:time.sleep(a.settle_seconds)
    response=request_reply_safe(rid,nid)
    reply=response.get('replyMessage',{}) if isinstance(response,dict) else {}
    committed={'event':'relive_committed','time':utc_now(),'room_uuid':rid,
               'after_episode':ep,'episode_count':a.relive_every,'prompt':prompt,
               'reply':reply,'reply_api_response':response}
    append_journal(journal,committed)
    events.append(committed)
    body=reply.get('messageText') or reply.get('text') or reply.get('content') or '' if isinstance(reply,dict) else ''
    if body: print('    %s: %s'%(name,str(body)[:250].replace('\n',' ')),flush=True)

def main():
    ap=argparse.ArgumentParser(description='Nomi v0.85: room-based, automatic durable resume')
    ap.add_argument('files',nargs='*',help='diary TXT/DOCX files in chronological order')
    ap.add_argument('--mode',choices=['journal','conversation'],default='journal')
    ap.add_argument('--memory-prefix',default=None)
    ap.add_argument('--chunk-bytes',type=int,default=750)
    ap.add_argument('--delay',type=float,default=1.0)
    ap.add_argument('--relive-every',type=int,default=5)
    ap.add_argument('--relive-prompt',default=None)
    ap.add_argument('--room-note',default=None)
    ap.add_argument('--settle-seconds',type=float,default=0.0)
    ap.add_argument('--start-episode',type=int,default=1,
                    help='for FIRST run only; later resumes automatically')
    ap.add_argument('--start-message',type=int,default=1)
    ap.add_argument('--journal',default='nomi_rehydration_journal.jsonl')
    ap.add_argument('--completion',default='nomi_rehydration_completed.json')
    ap.add_argument('--max-episodes',type=int,default=0,
                    help='send at most N NEW complete episodes; keep checkpoint')
    ap.add_argument('--dry-run',action='store_true')
    a=ap.parse_args()
    if a.chunk_bytes<150 or a.relive_every<0 or a.delay<0 or a.start_episode<1 or a.start_message<1 or a.max_episodes<0:
        ap.error('Invalid chunk/episode/delay settings.')
    if not a.files:ap.error('Specify diary files in chronological order.')
    files=[Path(f) for f in a.files]
    for f in files:
        if not f.is_file():raise RuntimeError('File not found: '+str(f))
    journal=Path(a.journal)
    events=load_journal(journal)
    active=active_session(events) if events else []
    if a.dry_run:
        if active:
            selected=active[0]
            print('Existing checkpoint for Nomi:',selected.get('nomi_name'))
        name='Beth Peterson' if not active else str(active[0].get('nomi_name') or 'Beth Peterson')
        prefix=journal_memory_prefix(name) if a.memory_prefix is None else a.memory_prefix
        chunks=prepare_conversation_chunks(files,a.chunk_bytes) if a.mode=='conversation' else prepare_chunks(files,a.chunk_bytes,prefix)
        print('DRY RUN v%s: %d messages; %d episodes; %d files.'%
              (VERSION,len(chunks),max(c['episode_index'] for c in chunks),len(files)))
        print('First:',chunks[0]['episode_header'],'Last:',chunks[-1]['episode_header'])
        return 0
    if not os.environ.get('NOMI_API_KEY'):
        import getpass
        os.environ['NOMI_API_KEY']=getpass.getpass('Nomi API key (input hidden, not saved): ').strip()
        if not os.environ['NOMI_API_KEY']:
            raise RuntimeError('No Nomi API key supplied.')

    if active:
        record=active[0]
        nid=str(record['nomi_uuid']);rid=str(record['room_uuid'])
        nomis=get_nomis()
        matches=[n for n in nomis if str(n.get('uuid',''))==nid]
        if not matches:raise RuntimeError('The Nomi for the journal is no longer accessible.')
        nomi=matches[0];name=str(nomi.get('name','')).strip() or 'Nomi'
        if str(record.get('nomi_name',''))!=name:
            raise RuntimeError('Nomi display name changed mid-import, which changes the autobiographical prefix. Restore its prior name or begin a new archive.')
        print('AUTO RESUME: %s in room %s'%(name,rid))
        if record.get('chunk_bytes')!=a.chunk_bytes or record.get('relive_every')!=a.relive_every or record.get('mode')!=a.mode:
            raise RuntimeError('Resume settings differ from original command. Keep --chunk-bytes, --relive-every, and --mode identical.')
        if record.get('start_episode')!=a.start_episode or record.get('start_message')!=a.start_message:
            raise RuntimeError('Start settings differ from original run; checkpoint controls resume automatically.')
        old_files=[Path(f).name for f in record.get('files',[])]
        if old_files!=[f.name for f in files]:
            raise RuntimeError('Input filenames/order differ from checkpoint; refusing to cross-load.')
        assert_no_uncertain_context(active)
        created=bool(record.get('created',False))
        wait_for_room(rid)
    else:
        nomi=choose_nomi(get_nomis())
        nid=str(nomi['uuid']);name=str(nomi.get('name','')).strip() or 'Nomi'
        note=(journal_room_note(name) if a.mode=='journal' and a.room_note is None else
              a.room_note if a.room_note is not None else 'Historical conversation archive.')
        room,created=resolve_room(nomi,note,str(journal))
        if room is None:return 0
        rid=str(room.get('uuid',''))
        if not rid:raise RuntimeError('Room has no UUID')
    prefix=journal_memory_prefix(name) if a.memory_prefix is None else a.memory_prefix
    chunks=(prepare_conversation_chunks(files,a.chunk_bytes) if a.mode=='conversation'
            else prepare_chunks(files,a.chunk_bytes,prefix))
    fingerprint=sha256_chunks(chunks)
    first=a.start_message if a.mode=='conversation' else a.start_episode
    selected=[c for c in chunks if c['episode_index']>=first]
    if not selected:raise RuntimeError('No entries from the requested starting episode.')
    if active:
        manifests=[x for x in active if x.get('event')=='run_manifest']
        if manifests and manifests[-1].get('digest')!=fingerprint:
            raise RuntimeError('DIARY CHANGED since the checkpoint was created. Do not silently replay altered data.')
    else:
        completed=Path(a.completion)
        if completed.exists():
            receipt=json.loads(completed.read_text(encoding='utf-8'))
            if receipt.get('digest')==fingerprint and receipt.get('nomi_uuid')==nid:
                raise RuntimeError('This Nomi already has a completed import receipt. '+
                                   'Move that receipt aside ONLY if you intentionally want to replay all diaries.')
        append_journal(journal,{'event':'room_selected','time':utc_now(),
            'version':VERSION,'room_uuid':rid,'room_name':room.get('name',''),
            'nomi_uuid':nid,'nomi_name':name,'created':created,
            'chunk_bytes':a.chunk_bytes,'relive_every':a.relive_every,
            'mode':a.mode,'start_episode':a.start_episode,'start_message':a.start_message,
            'files':[str(f) for f in files]})
        manifest={'event':'run_manifest','time':utc_now(),'room_uuid':rid,'digest':fingerprint}
        append_journal(journal,manifest)
        active=[{'event':'room_selected','room_uuid':rid,'nomi_uuid':nid,'nomi_name':name},manifest]
        wait_for_room(rid)
        if created and a.mode=='journal':
            send_context_safe(rid,name,str(journal))
    committed=inspect_commits(active,selected,rid)
    # The initial context is tracked separately and does not count as a diary episode.
    completed_sequences={c['sequence'] for c in selected[:committed]}
    print('Confirmed %d of %d message(s); %d left.'%
          (committed,len(selected),len(selected)-committed),flush=True)
    # It is possible that all chunks of an episode have been accepted but
    # its five-entry reliving checkpoint hasn't yet occurred. The loop below
    # handles that before it sends the next episode.
    new_episodes=0
    incomplete=False
    for c in selected:
        seq=c['sequence']
        if seq not in completed_sequences:
            # Limit at episode boundaries, not mid-entry. A deliberately partial
            # test run keeps the active journal so restarting is automatic.
            if c['episode_part_index']==1 and a.max_episodes and new_episodes>=a.max_episodes:
                incomplete=True
                break
            print('SEND %d | episode %d | %s part %d/%d' %
                  (seq,c['episode_index'],c['source_name'],
                   c['episode_part_index'],c['episode_part_count']),flush=True)
            base={'time':utc_now(),'room_uuid':rid,'sequence':seq,
                  'source_file':c['source_file'],'episode_index':c['episode_index'],
                  'file_episode_index':c['file_episode_index'],
                  'episode_header':c['episode_header'],
                  'episode_part_index':c['episode_part_index'],
                  'episode_part_count':c['episode_part_count'],
                  'byte_count':c['byte_count'],'sha256':c['sha256']}
            append_journal(journal,dict(base,event='send_attempt'))
            response=send_room_safe(rid,c['text'])
            sent=response.get('sentMessage',{}) if isinstance(response,dict) else {}
            append_journal(journal,dict(base,event='send_committed',
                                         message_uuid=sent.get('uuid') if isinstance(sent,dict) else None,
                                         sent_at=sent.get('sent') if isinstance(sent,dict) else None))
            new_episodes+=(c['episode_part_index']==1)
            if a.delay:time.sleep(a.delay)
        if c['episode_part_index']==c['episode_part_count']:
            relive_after_episode(c['episode_index'],a,rid,nid,name,str(journal),active)
    if incomplete:
        print('Paused intentionally after %d NEW episodes; checkpoint retained. Run the same command to resume.'%new_episodes)
        return 0
    # Success means every episode fragment was confirmed and all periodic
    # relivings were confirmed. Preserve a small completion receipt, not the
    # detailed send journal. Never clear checkpoints on an error or Ctrl+C.
    final_records=load_journal(journal)
    final_active=active_session(final_records)
    final_count=inspect_commits(final_active,selected,rid)
    if final_count!=len(selected):
        raise RuntimeError('Not all chunks committed: %d/%d'%(final_count,len(selected)))
    receipt={'version':VERSION,'completed_at':utc_now(),'nomi_uuid':nid,
             'nomi_name':name,'room_uuid':rid,'digest':fingerprint,
             'episodes':len({c['episode_index'] for c in selected}),
             'messages':len(selected),'files':[f.name for f in files]}
    atomic_json(a.completion,receipt)
    journal.unlink()
    print('COMPLETE: %d messages, %d episodes. Journal cleared: %s. Receipt: %s'%
          (len(selected),receipt['episodes'],journal,a.completion))
    return 0

if __name__ == '__main__':
    raise SystemExit("Internal uploader compatibility module. Run nomi-uploader.py instead.")
