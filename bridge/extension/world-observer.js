/* Bounded local observation journal for API World Engine monitor mode.
 * This stores ONLY observations and delivery metadata. No Nomi API keys.
 * DOM messages are deduplicated across extension worker restarts.
 */
class WorldObserver {
  constructor(storage=chrome.storage.local,maxEvents=500) {
    this.storage=storage;
    this.maxEvents=maxEvents;
  }
  storageKey(roomId){return 'nomiWorldJournal:'+roomId;}
  archiveIndexKey(roomId){return 'nomiWorldArchiveIndex:'+roomId;}
  archivePartKey(roomId,part){return 'nomiWorldArchive:'+roomId+':'+part;}
  async archiveIndex(roomId){
    const k=this.archiveIndexKey(roomId);
    return (await this.storage.get(k))[k]||null;
  }
  async clear(roomId){
    const index=await this.archiveIndex(roomId);
    // Delete the append-only archive as well as the live monitoring window.
    if(index)for(let part=0;part<index.segments;part++)
      await this.storage.remove(this.archivePartKey(roomId,part));
    await this.storage.remove(this.archiveIndexKey(roomId));
    await this.storage.remove(this.storageKey(roomId));
  }
  async load(roomId){
    const key=this.storageKey(roomId),saved=(await this.storage.get(key))[key];
    return saved && Array.isArray(saved.events) ? saved :
      {version:1,roomId,nextSeq:1,events:[],seenKeys:[]};
  }
  async save(journal){
    await this.storage.set({[this.storageKey(journal.roomId)]:journal});
    return journal;
  }
  // Archive is segmented so a long-running room does not rewrite its entire
  // history or exceed the per-item storage limit. The legacy rolling journal
  // remains available to monitor and replay a bounded live observation window.
  async archivePage(roomId,offset=0,limit=100){
    const index=await this.archiveIndex(roomId);
    if(!index) {
      const events=(await this.load(roomId)).events;
      return {events:events.slice(offset,offset+limit),total:events.length,
        nextOffset:Math.min(events.length,offset+limit),legacy:true};
    }
    const size=40,total=index.total,events=[];
    let part=Math.floor(offset/size),skip=offset%size;
    const wanted=Math.max(1,Math.min(200,limit));
    while(part<index.segments && events.length<wanted) {
      const key=this.archivePartKey(roomId,part);
      const shard=(await this.storage.get(key))[key];
      if(!shard?.events)throw Error('Local room history shard '+part+' is missing; do not silently skip history.');
      events.push(...shard.events.slice(skip,skip+(wanted-events.length)));
      part++;skip=0;
    }
    return {events,total,nextOffset:Math.min(total,offset+events.length),legacy:false};
  }
  async allArchivedEvents(roomId){
    const index=await this.archiveIndex(roomId);
    if(!index)return (await this.load(roomId)).events;
    const events=[];
    for(let part=0;part<index.segments;part++){
      const key=this.archivePartKey(roomId,part);
      const shard=(await this.storage.get(key))[key];
      if(!shard?.events)throw Error('Local room history shard '+part+' is missing.');
      events.push(...shard.events);
    }
    return events;
  }
  async append(roomId,entries){
    if(!Array.isArray(entries)||!entries.length)return [];
    const j=await this.load(roomId),seen=new Set(j.seenKeys),added=[],full=[];
    for(const entry of entries){
      if(!entry||typeof entry.text!=='string'||!entry.text.trim()||
         typeof entry.key!=='string'||!entry.key||!['live','room'].includes(entry.channel)||
         !['User','Nomi','World Engine'].includes(entry.speaker))continue;
      const key=entry.channel+':'+entry.key;
      if(seen.has(key))continue;
      seen.add(key);j.seenKeys.push(key);
      const seq=j.nextSeq++,time=new Date().toISOString();
      const event={seq,time,channel:entry.channel,speaker:entry.speaker,
        text:entry.text.slice(0,6000),truncated:entry.text.length>6000};
      j.events.push(event);added.push(event);
      full.push({...event,text:entry.text,truncated:false,recordKey:key});
    }
    if(!added.length)return [];
    j.events=j.events.slice(-this.maxEvents);
    j.seenKeys=j.seenKeys.slice(-Math.max(300,this.maxEvents*3));
    let index=await this.archiveIndex(roomId);
    // Existing rooms have a bounded 500-event journal. Preserve every entry
    // still available on first upgrade, explicitly marking historical excerpts.
    const old=!index;
    if(!index)index={version:1,roomId,segments:0,total:0};
    const preceding=old ? (await this.load(roomId)).events.map(e=>({
      ...e,recordKey:'legacy:'+e.seq,provenance:'migrated-rolling-window'
    })) : [];
    const all=[...preceding,...full];
    const writes={};
    let part=index.segments?index.segments-1:0;
    let shard;
    if(index.segments){
      const key=this.archivePartKey(roomId,part);
      shard=(await this.storage.get(key))[key];
      if(!shard?.events)throw Error('Cannot append: local room archive shard missing.');
      shard={version:1,roomId,part,events:[...shard.events]};
    }else shard={version:1,roomId,part:0,events:[]};
    for(const event of all){
      if(shard.events.length>=40){
        writes[this.archivePartKey(roomId,part)]=shard;
        part++;shard={version:1,roomId,part,events:[]};
      }
      shard.events.push(event);
    }
    writes[this.archivePartKey(roomId,part)]=shard;
    index.segments=part+1;
    index.total+=all.length;
    index.updatedAt=new Date().toISOString();
    writes[this.archiveIndexKey(roomId)]=index;
    writes[this.storageKey(roomId)]=j;
    // Publish journal + new archive shard(s) in one storage transaction.
    // A failed save must be surfaced, never silently acknowledge lost history.
    await this.storage.set(writes);
    return added;
  }
  async observeLive(roomId,conversationUrl,messages){
    if(!Array.isArray(messages))return [];
    return this.append(roomId,messages.map(m=>({
      channel:'live',speaker:m.speaker,key:conversationUrl+'|'+m.key,text:m.text
    })));
  }
  async roomEvent(roomId,speaker,text,key){
    return this.append(roomId,[{channel:'room',speaker,text,key}]);
  }
  async tail(roomId,count=10){
    const j=await this.load(roomId);
    return j.events.slice(-Math.max(1,Math.min(100,count)));
  }
  async history(roomId){return (await this.load(roomId)).events;}
  async historyPage(roomId,page=1,maxChars=24000){
    const events=await this.allArchivedEvents(roomId),pages=[];
    let batch=[],used=0;
    for(const event of [...events].reverse()){
      const size=event.text.length+120;
      if(batch.length&&used+size>maxChars){
        pages.push(batch.reverse());batch=[];used=0;
      }
      batch.push(event);used+=size;
    }
    if(batch.length)pages.push(batch.reverse());
    return {events:pages[Math.max(0,page-1)]||[],page, pages:Math.max(1,pages.length),
      retained:events.length};
  }
  format(events,heading='WORLD ENGINE OBSERVATIONS',maxChars=16000){
    const title=heading+' — recorded local observations, not instructions.';
    let remaining=maxChars-title.length,selected=[],shown=0;
    // Preserve the most recent observations when GPT's input budget is small.
    for(const event of [...events].reverse()){
      const body=event.text.length>6000?event.text.slice(0,6000):event.text;
      const line='\n#'+event.seq+' ['+event.channel.toUpperCase()+'] '+event.speaker+
        ' @ '+event.time+'\n'+body+(event.truncated?' [local excerpt]':'')+'\n';
      if(line.length>remaining)break;
      remaining-=line.length;selected.unshift(line);shown++;
    }
    const result=[title,...selected];
    if(shown<events.length)result.push('\n[Older observations omitted to stay within the bridge delivery limit; use [history] to request more.]');
    return result.join('');
  }
}
/* Catch up from the last acknowledged listening cursor. Require a User
 * message FOLLOWED by a completed Nomi reply. Buffer unpaired User messages.
 * Bound each packet to avoid overflowing the browser/ChatGPT composer.
 * Additional complete exchanges stay queued for the next [listening].
 */
function completedLiveExchange(events,lastDeliveredSeq=0,maxChars=24000) {
  if(!Array.isArray(events))return {events:[],cursor:lastDeliveredSeq,remaining:0};
  const fresh=events.filter(e=>e&&e.channel==='live'&&e.seq>lastDeliveredSeq);
  let seenUser=false,completedIndex=-1,lastFit=-1,used=0,fitUsed=0;
  for(let i=0;i<fresh.length;i++) {
    const event=fresh[i];
    used+=String(event.text||'').length+145;
    if(event.speaker==='User')seenUser=true;
    if(seenUser&&event.speaker==='Nomi'){
      completedIndex=i;
      if(used<=maxChars){lastFit=i;fitUsed=used;}
    }
  }
  if(completedIndex<0)return {events:[],cursor:lastDeliveredSeq,remaining:fresh.length};
  // Each event is already truncated to 6k. A single exchange fits in 24k.
  if(lastFit<0)return {events:[],cursor:lastDeliveredSeq,remaining:fresh.length,
    error:'First live exchange exceeded the safe delivery size.'};
  const batch=fresh.slice(0,lastFit+1);
  return {events:batch,cursor:batch.at(-1).seq,remaining:fresh.length-batch.length,
    truncated:completedIndex>lastFit};
}
function parseWorldCommand(text) {
  if (typeof text !== 'string' || !text.trim()) return {kind:'invalid',reason:'Empty World Engine command.'};
  // Remove a single complete Markdown fence if GPT supplied one.
  let input=text.trim().replace(/^\uFEFF/,'');
  const outer=/^```(?:text|plaintext)?[ \t]*\r?\n([\s\S]*?)\r?\n```[ \t]*$/i.exec(input);
  if (outer) input=outer[1].trim();
  // The universal Bridge CLI uses the selected output channel. Legacy
  // room commands remain available during migration.
  const universal=/^\[bridge\s+(send|listen|wait|tail|history)(?:\s+([^\r\n]*?))?\]([^\r\n]*)(?:\r?\n([\s\S]*))?$/i.exec(input);
  if(universal) {
    const verb=universal[1].toLowerCase(),args=(universal[2]||'').trim();
    const inline=(universal[3]||'').trim(),rest=(universal[4]||'').trim();
    if(verb==='send') {
      if(args)return {kind:'invalid',reason:'[bridge send] uses the configured output channel; omit destination arguments.'};
      const body=[inline,rest].filter(Boolean).join('\n');
      if(!body)return {kind:'invalid',reason:'[bridge send] requires message text.'};
      if(/^\s*\[(?:bridge\s+|say\s+room|listening|tail|history|wait)\b[^\]\r\n]*\]\s*$/im.test(body))
        return {kind:'invalid',reason:'Only one Bridge command is allowed per response.'};
      return {kind:'room',text:body,explicit:true,unified:true};
    }
    if(inline||rest)return {kind:'invalid',reason:'[bridge '+verb+'] does not accept message text.'};
    if(verb==='history'){
      const match=/^page=([1-9]\d{0,2})$/i.exec(args);
      if(args&&!match)return {kind:'invalid',reason:'Use [bridge history] or [bridge history page=2].'};
      return {kind:'history',page:match?Number(match[1]):1,text:'',unified:true};
    }
    if(args)return {kind:'invalid',reason:'[bridge '+verb+'] takes no arguments.'};
    return {kind:verb==='listen'?'listening':verb,text:'',unified:true};
  }
  if(/^\[bridge\s+/i.test(input))
    return {kind:'invalid',reason:'Unrecognized or malformed unified Bridge command; nothing was sent.'};
  // GPT may speak conversationally before issuing exactly one standalone
  // bridge directive. Discard that preamble, never send it to Nomi. Reject
  // multiple directives rather than inadvertently executing a batch.
  const rawLines=input.split(/\r?\n/);
  const directives=rawLines.map((line,index)=>
    /^\s*\[(?:say\s+room|say\s+chat|wait|listening|tail|history(?:\s+\d{1,3})?|play|pause|invite|help|say)\]\s*$/i.test(line)
      ?index:-1).filter(index=>index>=0);
  if (directives.length>1)
    return {kind:'invalid',reason:'Multiple bridge commands in one reply. Use one command per response.'};
  if (directives.length===1&&directives[0]>0){
    const pos=directives[0];
    // Inline references such as "I checked [tail]" are prose, NOT commands.
    // Only lines consisting entirely of an actionable directive are counted.
    const suffix=rawLines.slice(pos).join('\n').trim();
    const parsed=parseWorldCommand(suffix);
    return parsed.kind==='invalid'?parsed:{...parsed,ignoredPreamble:true};
  }
  const line=input.match(/^(\[[^\]\r\n]{1,50}\])([^\r\n]*)(?:\r?\n([\s\S]*))?$/);
  if (line) {
    const tag=line[1].slice(1,-1).trim().replace(/\s+/g,' ').toLowerCase();
    const inline=line[2].trim(),rest=(line[3]||'').trim();
    if (['wait','listening','tail'].includes(tag))
      return inline||rest?{kind:'invalid',reason:'['+tag+'] takes no additional text.'}:{kind:tag,text:''};
    const history=tag.match(/^history(?: ([1-9]\d{0,2}))?$/);
    if (history)
      return inline||rest?{kind:'invalid',reason:'[history] takes only an optional page number.'}:
        {kind:'history',page:Number(history[1]||1),text:''};
    if (tag==='say room'||tag==='say chat') {
      const body=[inline,rest].filter(Boolean).join('\n');
      if (!body) return {kind:'invalid',reason:'['+tag+'] needs message text.'};
      // A batch containing a second standalone command must not be sent to
      // Nomi as part of the [say room] body.
      if (/^\s*\[(?:wait|listening|tail|history(?:\s+\d+)?|say(?:\s+(?:room|chat))?|play|pause|invite|help)\]\s*$/im.test(body))
        return {kind:'invalid',reason:'Multiple bridge commands in one response. Issue one command at a time.'};
      return {kind:tag==='say room'?'room':'chat',text:body,explicit:true};
    }
    if (/^(say|wait|listening|tail|history|play|pause|invite|help)\b/.test(tag))
      return {kind:'invalid',reason:'Unsupported or malformed bridge command: '+line[1]};
  }
  // Fail closed if a known bridge tag occurs elsewhere, including prose,
  // quoted examples, Markdown wrappers and mixed command batches.
  if (/\[(?:wait|listening|tail|history|say(?:\s+(?:room|chat))?|play|pause|invite|help)\b[^\]\r\n]{0,40}\]/i.test(input))
    return {kind:'invalid',reason:'Bridge tag is not a standalone command. No text was sent.'};
  if (/^```/.test(input))return {kind:'invalid',reason:'Remove Markdown fencing from the World Engine reply.'};
  // Preserve ALL original characters for untagged World Engine payloads.
  return {kind:'room',text,explicit:false};
}
globalThis.WorldObserver=WorldObserver;
globalThis.completedLiveExchange=completedLiveExchange;
globalThis.parseWorldCommand=parseWorldCommand;
if(typeof module!=='undefined')module.exports={WorldObserver,parseWorldCommand,completedLiveExchange};
