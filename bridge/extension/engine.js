/* Pure turn engine. State is persisted in extension session storage by the worker. */
const NOMI_MESSAGE_LIMIT = 750;
function isBridgeCommandText(value) {return /^\s*\[(?:bridge\s+|next message\]|clear queue\])/i.test(value||'');}
// API-room data commands share the Bridge CLI spelling but are handled by
// the room transport, not the Direct-mode command processor.
function isApiRoomDataCommand(value) {return /^\s*\[bridge\s+(?:send|listen|wait|tail|history)(?:\s|\])/i.test(value||'');}
const LENGTH_REMINDER = '\n\n[Bridge reminder: Your previous reply exceeded 750 characters and was truncated before Nomi received it. Keep your entire next reply and subsequent replies within 750 characters, including spaces and punctuation.]';
function limitNomiMessage(text) {
  if (text.length <= NOMI_MESSAGE_LIMIT) return text;
  let end = NOMI_MESSAGE_LIMIT;
  if (/[\uD800-\uDBFF]/.test(text[end - 1]) && /[\uDC00-\uDFFF]/.test(text[end])) end--;
  return text.slice(0, end);
}

function nomiByteWindow(text) {
  const encoder=new TextEncoder();
  if(encoder.encode(text).length<=750)return text;
  let result='',bytes=0;
  for(const ch of text) {
    const size=encoder.encode(ch).length;
    if(bytes+size>750)break;
    result+=ch;bytes+=size;
  }
  return result;
}
class Bridge {
  constructor(clock = () => Date.now() / 1000, saved = {}) {
    Object.assign(this, {tabs: {}, running: false, pair: null, source: null, phase: 'idle', command: null,
      baseline: null, remindChatGPT: false, lastDelivery: null, turns: 0, cliTransactions: 0, events: [], stableSeconds: 2, startedWait: 0,
      reason: 'Choose two tabs and press Play.'}, saved);
    this.clock = clock;
    if (saved.pendingNomi?.length) {
      this.running = false; this.phase = 'uncertain'; this.command = null;
      this.reason = 'Updated to one message per turn. Reset before continuing.';
    }
    delete this.pendingNomi;
    // Existing running Direct sessions created before stable turn-key support
    // have no trustworthy source-consumption ledger. Never replay uncertain work.
    if(saved.running && saved.simpleMode && (saved.mode||'direct')==='direct' &&
       (!Array.isArray(saved.simpleConsumedControllerTurns) ||
        (saved.tabs?.[saved.pair?.[0]]?.site==='chatgpt' && !saved.simpleControllerKeyType))) {
      this.running=false;this.phase='uncertain';this.command=null;
      this.reason='Direct-mode turn tracking upgraded. Inspect both conversations, then Stop/Reset and Play. No previous send will be replayed.';
    }
  }
  log(text) {
    this.reason = text;
    this.events.push({time: new Date().toLocaleTimeString(), text});
    this.events = this.events.slice(-100);
  }
  stop(reason = 'Stopped. Press Play to resume.') {this.running = false; this.log(reason);}
  retryGPTTab(id,observedUrl,originalUrl){
    id=String(id);
    const s=this.apiSession;
    if(!this.running||this.mode!=='api-room'||this.pair?.[0]!==id||
       this.source!==this.pair?.[1]||this.phase==='send'||
       !['ready','inflight','delivering','reply_saved'].includes(s?.pendingReply))return false;
    const expectedUrl=this.tabRetry?.expectedUrl||originalUrl||this.tabs[id]?.url;
    if(!expectedUrl||expectedUrl===observedUrl)return false;
    if(!this.tabRetry){
      this.tabRetry={id,expectedUrl,startedAt:this.clock(),attempts:0};
      this.log('Selected ChatGPT tab temporarily left its original conversation. '+
        'Retrying that tab for 120 seconds; Nomi room events remain checkpointed.');
    }
    this.tabRetry.attempts++;
    return true;
  }
  // Append informational events without hiding a terminal stop/uncertain reason.
  note(text) {
    this.events.push({time:new Date().toLocaleTimeString(),text});
    this.events=this.events.slice(-100);
  }
  start(data) {
    if (this.running) throw Error('Already running. Stop before changing tabs.');
    if (this.phase === 'uncertain') throw Error('Delivery was uncertain. Check both chats, then Reset before starting again.');
    const pair = data.tabs || [data.chatgpt, data.nomi];
    if (!Array.isArray(pair) || pair.length !== 2 || !pair[0] || !pair[1] || pair[0] === pair[1]) throw Error('Select two different chat tabs.');
    pair.forEach(id => {
      const tab = this.tabs[id];
      if (!tab || !['chatgpt', 'nomi', 'api-room'].includes(tab.site) || this.clock() - tab.seen > 90) throw Error('Select two connected chat tabs.');
      if (!tab.ready) throw Error(tab.diagnostic || 'Open extension setup and check the chat controls.');
      if (tab.draft) throw Error('Clear the draft in both chats first.');
      if (tab.error) throw Error(tab.error);
    });
    if (JSON.stringify(this.pair) !== JSON.stringify(pair) || this.phase === 'idle') {
      this.pair = pair;
      this.cliControllerTab = String(pair[0]);
      this.source = pair[data.first === 'second' || (!data.tabs && data.first === 'nomi') ? 1 : 0];
      this.phase = 'source'; this.command = null; this.baseline = null; this.remindChatGPT = false; this.turns = 0; this.cliTransactions = 0;
    }
    this.cliControllerTab = String(pair[0]);
    const settle = Number(data.settle ?? 2);
    this.stableSeconds = Number.isFinite(settle) ? Math.max(1, Math.min(60, settle)) : 2;
    if ((this.mode||'direct')==='direct') {
      if(this.tabs[pair[0]]?.site==='chatgpt' && this.tabs[pair[0]].reply &&
         !this.tabs[pair[0]].assistantTurnKey)
        throw Error('ChatGPT logical turn key is unavailable. Check the reply selector before Play.');
      this.pair=pair;this.source=pair[0];this.simpleMode=true;
      this.simplePeerAwait=false;
      this.simpleControllerSeen=this.tabs[pair[0]]?.replyKey;
      this.simplePeerSeen=this.tabs[pair[1]]?.replyKey;
      this.command=null;this.outboundQueue=[];this.waitingCli=[];this.deferredCli=[];
      // The cursor is a ledger of consumed GPT turns, not a text filter.
      // The already-visible assistant turn is a baseline, never a new send.
      const baselineTurn=this.tabs[pair[0]]?.site==='chatgpt'
        ? this.tabs[pair[0]].assistantTurnKey : null;
      this.simpleConsumedControllerTurns=baselineTurn?[baselineTurn]:[];
      this.simpleControllerKeyType=baselineTurn?baselineTurn.split(':',1)[0]:null;
      this.simpleTruncationWarning=null;
      this.outboundCredits={};this.acceptedOutbound={};this.pairNotice=null;
      this.running=true;this.cliPaused=false;this.cliShutdown=false;
      this.phase='reply';this.startedWait=this.clock();
      this.reason='Sending controller startup instructions to Tab 1.';
      const controller=this.tabs[pair[0]];
      this.command={id:crypto.randomUUID(),source:pair[0],target:pair[0],
        text:'[AI Bridge started — Tab 1 controller]\n'+
          'You control this bridge; Tab 2 is conversational only.\n'+
          '[bridge send] Your message to Tab 2 (or put message on next line).\n'+
          '[bridge shutdown] End the session.\n'+
          '[bridge pause] Pause sends.\n'+
          '[bridge resume] Resume sends.\n'+
          'Normal replies stay private. Only one exchange runs at a time.\n'+
          'Messages entering Nomi are limited to 750 UTF-8 bytes; truncation is reported to you in Nomi’s next reply.',
        url:controller.url,document:controller.document,
        sourceReply:controller.reply,sourceKey:controller.replyKey,
        sourceUrl:controller.url,sourceDocument:controller.document,
        baseline:controller.replyKey,created:this.clock(),claimed:false,
        simpleStartup:true};
      this.phase='send';
      return;
    }
    this.cliSeen = Object.fromEntries(pair.map(id=>[id,this.tabs[id]?.replyKey]));
    if (this.command && !this.command.claimed) this.command.created = this.clock();
    this.tabRetry=null;
    this.cliShutdown=false;
    this.shutdownPending=false;
    this.cliPaused=false;
    this.running = true; this.startedWait = this.clock();
    this.log('Running: waiting for a completed reply.');
    if (this.mode !== 'api-room' && this.mode !== 'heartbeat') {
      this.queuePairNotice('start',
        '[Bridge started; running]\n' +
        (globalThis.AIBridgeCLI?.HELP || '[bridge help]') );
    }
    this.tick();
  }
  queuePairNotice(kind, text, requester = null) {
    if (!this.pair || this.pair.length !== 2) return false;
    const targets = requester && this.pair.includes(requester)
      ? [requester, this.pair.find(id => id !== requester)] : [...this.pair];
    this.pairNotice = {kind, text, targets, restoreSource:this.source,
      restoreBaseline:this.baseline};
    return this.queueNextPairNotice();
  }
  queueNextPairNotice() {
    const n = this.pairNotice;
    if (!n || !n.targets.length) return false;
    const target = n.targets[0], tab = this.tabs[target];
    if (!tab || !tab.ready || tab.busy || tab.draft || this.clock()-tab.seen > 70 ||
        !['chatgpt','nomi'].includes(tab.site)) {
      this.log('Unable to deliver ' + n.kind + ' notice to ' + target +
        '; no message was sent to this tab.');
      this.pairNotice=null;
      return false;
    }
    this.command = {id:crypto.randomUUID(),source:target,target,
      text:n.text,url:tab.url,document:tab.document,sourceReply:tab.reply,
      sourceKey:tab.replyKey,sourceUrl:tab.url,sourceDocument:tab.document,
      baseline:tab.replyKey,claimed:false,created:this.clock(),
      internalResult:true,pairNotice:true};
    this.phase='send';
    this.note('Queued ' + n.kind + ' notification for tab ' + target);
    return true;
  }
  reset() {
    if (this.running) throw Error('Stop before resetting.');
    this.cliPaused=false;
    this.cliShutdown=false;
    this.outboundQueue=[];this.outboundCredits={};this.deliveredCounts={};this.waitingCli=[];this.acceptedOutbound={};this.shutdownPending=false;
    this.simpleConsumedControllerTurns=[];this.simpleControllerKeyType=null;this.simpleControllerSeen=null;this.simplePeerSeen=null;this.simpleTruncationWarning=null;
    this.phase = 'idle'; this.pair = null; this.command = null; this.remindChatGPT = false;
    this.log('Reset. Next Play starts with the selected speaker’s latest reply.');
  }
  queueOutbound(source, target, body) {
    this.outboundQueue ||= [];
    const src=this.tabs[source], dst=this.tabs[target];
    const fingerprint=JSON.stringify([source,src.document,src.reply]);
    // Idempotency is established at enqueue time, not at delivery time.
    // Otherwise, once the first queued part is acknowledged and removed,
    // repeated heartbeat/CLI dispatch can enqueue and send the same reply again.
    this.acceptedOutbound ||= {};
    if (this.acceptedOutbound[fingerprint] ||
        this.outboundQueue.some(x=>x.fingerprint===fingerprint) ||
        this.command?.queueItem?.fingerprint===fingerprint) return 0;
    const max=dst.site==='nomi'?580:11000;
    const parts=[];
    let remaining=body;
    while(remaining.length) {
      let take=Math.min(max,remaining.length);
      if(take<remaining.length) {
        const boundary=remaining.lastIndexOf('\n',take);
        if(boundary>take/2)take=boundary+1;
        if(/[\uD800-\uDBFF]/.test(remaining[take-1]) && /[\uDC00-\uDFFF]/.test(remaining[take]))take--;
      }
      parts.push(remaining.slice(0,take));remaining=remaining.slice(take);
    }
    if (parts.length>100) throw Error('Message exceeds 100 queued parts');
    const batch=crypto.randomUUID();
    this.acceptedOutbound[fingerprint]={batch,at:this.clock(),parts:parts.length};
    for(let i=0;i<parts.length;i++)this.outboundQueue.push({
      id:crypto.randomUUID(),batch,part:i+1,parts:parts.length,source,target,
      body:parts[i],fingerprint,sourceDocument:src.document,sourceUrl:src.url,
      sourceReply:src.reply,sourceKey:src.replyKey,created:this.clock()
    });
    this.note('Queued '+parts.length+' part(s) for '+target+'.');
    return parts.length;
  }
  queuedFor(target) {return (this.outboundQueue||[]).filter(x=>x.target===target).length;}
  releaseOutbound(target) {
    if(!this.running || this.shutdownPending || this.cliPaused || this.command || this.phase==='send')return false;
    const items=this.outboundQueue||[], index=items.findIndex(x=>x.target===target);
    if(index<0)return false;
    const dest=this.tabs[target],item=items[index];
    if(!dest || !dest.ready || dest.busy || dest.complete===false || dest.draft || this.clock()-dest.seen>70) {
      const blocker=!dest?'destination unavailable':this.clock()-dest.seen>70?'destination heartbeat stale':
        dest.busy?'recipient generating':dest.complete===false?'recipient reply not marked complete':
        dest.draft?'recipient editor contains a draft':!dest.ready?'destination editor not ready':'waiting';
      this.reason='Queued outbound message waiting: '+blocker+'. Queue preserved; nothing typed.';
      return false;
    }
    const pending=this.queuedFor(target), sequence=(this.deliveredCounts||{})[target]||0;
    const label=item.parts>1
      ? '[Bridge part '+item.part+' of '+item.parts+'; '+(pending-1)+' queued after this]\n'
      : '[Bridge message; '+(pending-1)+' queued after this]\n';
    const footer=pending>1?'\n[Reply [next message] for next; [clear queue] to discard remaining.]':'';
    const text=label+item.body+footer;
    if(dest.site==='nomi' && text.length>750) {
      this.note('Queue formatting exceeds Nomi limit; refusing truncation.');return false;
    }
    items.splice(index,1);
    this.command={id:item.id,source:item.source,target,text,url:dest.url,document:dest.document,
      sourceReply:item.sourceReply,sourceKey:item.sourceKey,
      sourceDocument:item.sourceDocument,sourceUrl:item.sourceUrl,
      baseline:dest.replyKey,created:this.clock(),claimed:false,explicitSend:true,
      queuedOutbound:true,queueItem:item,
      cliRestore:{source:this.source,baseline:this.baseline,phase:'reply'}};
    this.phase='send';this.log('Delivering queued message '+(sequence+1)+' to '+target+'.');
    return true;
  }
  scheduleOutbound(target) {
    this.outboundCredits ||= {};
    this.outboundCredits[target]=(this.outboundCredits[target]||0)+1;
  }
  pumpOutbound() {
    if(!this.running || this.shutdownPending || this.command || this.phase==='send' || this.cliPaused)return;
    for(const target of this.pair||[]) {
      if((this.outboundCredits||{})[target]>0 && this.queuedFor(target)>0 &&
         this.releaseOutbound(target)) {
        this.outboundCredits[target]--;
        return;
      }
    }
  }
  capturePendingCli(id) {
    if (!this.running || !this.pair?.includes(id) || !this.command ||
        this.phase !== 'send') return;
    const tab=this.tabs[id];
    if (!tab?.reply || tab.busy || tab.complete===false ||
        !isBridgeCommandText(tab.reply) ||
         (this.mode==='api-room'&&isApiRoomDataCommand(tab.reply))) return;
    this.cliSeen ||= {};
    if (this.cliSeen[id] === tab.replyKey) return;
    if (this.command.source === id && this.command.sourceReply === tab.reply) return;
    this.waitingCli ||= [];
    const fingerprint=JSON.stringify([id,tab.document,tab.reply]);
    if (this.waitingCli.some(item=>item.fingerprint===fingerprint)) return;
    const queued={id,document:tab.document,url:tab.url,
      text:tab.reply,replyKey:tab.replyKey,fingerprint};
    const isShutdown=/^\\[bridge shutdown\\](?:\\s|$)/i.test(tab.reply.trim());
    if(isShutdown) {
      this.waitingCli.unshift(queued);
      this.shutdownPending=true;
      this.outboundCredits={};
      this.note('Priority shutdown requested; queued conversation deliveries suspended.');
    } else this.waitingCli.push(queued);
    this.cliSeen[id]=tab.replyKey;
    this.note('Queued CLI request from tab '+id+' behind active delivery ('+this.waitingCli.length+' waiting).');
  }
  drainPendingCli() {
    if (!this.running || this.phase==='send' || !this.waitingCli?.length) return;
    const item=this.waitingCli.shift(), tab=this.tabs[item.id];
    if (!tab || tab.document!==item.document || tab.url!==item.url ||
        tab.reply!==item.text) {
      this.deferredCli ||= [];
      this.deferredCli.push(item);
      this.reason='A buffered command was superseded in the conversation before dispatch. '+
        'It is preserved for inspection, not silently replayed.';
      this.note('Preserved superseded CLI command for manual recovery rather than dropping it.');
      return;
    }
    // Dispatch from actual recorded issuer and its current transcript.
    this.cliSeen ||= {};
    delete this.cliSeen[item.id];
    if (/^\\[bridge shutdown\\](?:\\s|$)/i.test(item.text.trim())) this.shutdownPending=false;
    if (item.id === this.source) {
      if (tab.replyKey === this.baseline) this.baseline=null;
      this.tick();
    } else this.dispatchPeerCli(item.id);
  }
  dispatchPeerCli(id) {
    // CLI inspection is independent of conversational turn ownership.
    if (!this.running || !this.pair?.includes(id) || id===this.source ||
        this.phase==='send' || this.phase==='uncertain' || this.pairNotice) return;
    const tab=this.tabs[id], now=this.clock();
    if (!tab || tab.busy || tab.complete===false ||
        now-tab.changed < this.stableSeconds || !isBridgeCommandText(tab.reply) ||
         (this.mode==='api-room'&&isApiRoomDataCommand(tab.reply))) return;
    this.cliSeen ||= {};
    if (this.cliSeen[id]===tab.replyKey) return;
    // Remember this reply before attempting dispatch; never re-execute after a repaint.
    this.cliSeen[id]=tab.replyKey;
    const restoreSource=this.source, restoreBaseline=this.baseline,
      restorePhase=this.phase, restoreWait=this.startedWait;
    this.source=id; this.baseline=null; this.phase='reply'; this.startedWait=now;
    this.tick();
    if (this.command) {
      this.command.cliRestore={source:restoreSource,baseline:restoreBaseline,phase:restorePhase,startedWait:restoreWait};
      if (this.pairNotice) {
        this.pairNotice.restoreSource=restoreSource;
        this.pairNotice.restoreBaseline=restoreBaseline;
      }
    }
    this.source=restoreSource; this.baseline=restoreBaseline;
    if (this.phase!=='send') {this.phase=restorePhase;this.startedWait=restoreWait;}
  }
  heartbeat(id, snapshot) {
    let old = this.tabs[id];
    const changed = !old || old.replyKey !== snapshot.replyKey || old.reply !== snapshot.reply || old.busy !== snapshot.busy || old.complete !== snapshot.complete || old.roomKey !== snapshot.roomKey || old.autoChat !== snapshot.autoChat || old.userTurn !== snapshot.userTurn;
    this.tabs[id] = {...snapshot, id, seen: this.clock(), changed: changed ? this.clock() : old.changed};
    // Keep the original URL across a transient navigation. A snapshot from
    // the wrong conversation must not update the trusted destination URL.
    if(this.tabRetry?.id===String(id)){
      if(snapshot.url===this.tabRetry.expectedUrl && snapshot.ready &&
         !snapshot.busy && !snapshot.draft){
        this.tabRetry=null;
        // The temporary wrong URL must not be interpreted as a NEW
        // navigation away from the just-restored original conversation.
        old={...old,url:snapshot.url};
        this.log('Original ChatGPT conversation reconnected. Resuming the saved Nomi reply.');
      }else{
        this.tick();
        return {};
      }
    }else if(this.running && this.pair?.includes(id) && old &&
          old.url!==snapshot.url && this.retryGPTTab(id,snapshot.url,old.url)){
      this.tick();
      return {};
    }
    if (this.running && this.pair?.includes(id) && this.phase !== 'idle' && old &&
        (old.url !== snapshot.url || old.document !== snapshot.document)) {
      // A harmless reload in API mode is NOT an uncertain Nomi API POST.
      // Never re-use the previous GPT answer after the page reload.
      if (this.mode === 'api-room' && old.url === snapshot.url && this.phase !== 'send') {
        if (this.source === id) {
          this.phase = 'reply';
          this.baseline = snapshot.replyKey;
          this.startedWait = this.clock();
        }
        this.log('Chat tab reloaded at the same conversation URL; retaining the API room.');
      } else {
        this.phase = 'uncertain';
        this.stop('Selected chat reloaded or navigated during a potentially active send. Inspect before Reset.');
      }
    } else if (this.running && this.pair?.includes(id) && snapshot.error) this.stop(snapshot.error);
    if (this.simpleMode && (this.mode||'direct')==='direct') {
      this.simpleTick();
      if(this.running && this.phase==='send' && this.command?.target===id && !this.command.claimed)
        return {command:{...this.command}};
      return {};
    }
    this.tick();
    this.pumpOutbound();
    this.capturePendingCli(id);
    this.dispatchPeerCli(id);
    if (this.running && this.phase === 'send' && this.command?.target === id && !this.command.claimed) return {command: {...this.command}};
    return {};
  }
  consumeSimpleControllerTurn(tab) {
    this.simpleControllerSeen=tab.replyKey;
    if(tab.site==='chatgpt' && tab.assistantTurnKey) {
      this.simpleConsumedControllerTurns ||= [];
      if(!this.simpleConsumedControllerTurns.includes(tab.assistantTurnKey))
        this.simpleConsumedControllerTurns.push(tab.assistantTurnKey);
    }
  }
  simpleTick() {
    if(!this.running || this.phase==='send' || !this.pair)return;
    const controllerId=this.pair[0],peerId=this.pair[1];
    const controller=this.tabs[controllerId];
    if(!controller)return;
    // A conversation turn is the unit of delivery, not a DOM replyKey.
    // Modern GPT turn keys are stable node IDs, not ordered counters.
    // The consumed-turn ledger rejects redraws without rejecting identical
    // messages deliberately produced in distinct GPT turns.
    const controllerFresh=()=>{
      if(controller.site==='chatgpt') {
        const current=controller.assistantTurnKey;
        if(!current) {
          this.reason='Cannot identify current ChatGPT turn key; refusing to reuse an old reply.';
          return false;
        }
        if(this.simpleControllerKeyType && !current.startsWith(this.simpleControllerKeyType+':')) {
          this.reason='ChatGPT changed its turn-identity layout during the bridge session. Stop and Reset before resuming; no message was resent.';
          return false;
        }
        return !(this.simpleConsumedControllerTurns||[]).includes(current);
      }
      return controller.replyKey!==this.simpleControllerSeen;
    };
    if(!controller.busy && controller.complete!==false && controller.reply &&
       this.clock()-controller.changed>=this.stableSeconds && controllerFresh()) {
      const control=globalThis.AIBridgeCLI?.parse(controller.reply);
      if(control?.command==='pause' || control?.command==='resume') {
        this.consumeSimpleControllerTurn(controller);
        this.cliPaused=control.command==='pause';
        this.reason=this.cliPaused?'Bridge paused by Tab 1. [bridge resume] is available.':
          'Bridge resumed by Tab 1.';
        this.note('Tab 1 '+control.command+' accepted without a new conversation send.');
        return;
      }
    }
    if(this.cliPaused) {
      this.reason='Bridge paused. Tab 1 may issue [bridge resume].';
      return;
    }
    const id=this.simplePeerAwait?peerId:controllerId;
    const tab=this.tabs[id],dest=this.tabs[id===controllerId?peerId:controllerId];
    if(!tab || !dest || tab.busy || tab.complete===false ||
       !tab.reply || this.clock()-tab.changed<this.stableSeconds ||
       this.clock()-tab.seen>70 || this.clock()-dest.seen>70)return;
    if(this.simplePeerAwait) {
      if(tab.replyKey===this.simplePeerSeen)return;
    } else if(!controllerFresh())return;

    // Only the controller parses bridge commands. Tab 2 speaks naturally.
    let message=tab.reply,shutdown=false;
    if(!this.simplePeerAwait) {
      const parsed=globalThis.AIBridgeCLI?.parse(tab.reply);
      if(!parsed) {
        this.consumeSimpleControllerTurn(tab);
        this.reason='Tab 1 reply is private. Waiting for [bridge send].';
        return;
      }
      if(parsed.command==='send') {
        const recipient=(parsed.args.to||'').toLowerCase();
        if(recipient && ![dest.site.toLowerCase(),(dest.name||'').toLowerCase(),'nomi','chatgpt','sera','seraphina'].includes(recipient)) {
          this.consumeSimpleControllerTurn(tab);
          this.reason='Recipient does not match selected peer.';
          return;
        }
        message=parsed.message;
      } else if(parsed.command==='shutdown') {
        message='[AI Bridge shutdown] Tab 1 ended this session. No further messages will be forwarded.';
        shutdown=true;
      } else {
        this.consumeSimpleControllerTurn(tab);
        this.reason='Tab 1 control received: '+parsed.command+'.';
        return;
      }
    }
    if(!dest.ready || dest.busy || dest.complete===false || dest.draft) {
      this.reason='Waiting for '+dest.site+' to be idle with an empty editor. Nothing has been typed.';
      return;
    }
    const originalByteLength=new TextEncoder().encode(message).length;
    if(dest.site==='nomi')message=nomiByteWindow(message);
    const truncatedToNomi=dest.site==='nomi' &&
      originalByteLength>new TextEncoder().encode(message).length;
    if(this.simplePeerAwait && this.simpleTruncationWarning) {
      message+='\n\n'+this.simpleTruncationWarning;
      this.simpleTruncationWarning=null;
    }
    if(!this.simplePeerAwait)this.consumeSimpleControllerTurn(tab);
    this.command={id:crypto.randomUUID(),source:id,target:dest.id||this.pair.find(x=>x!==id),
      text:message,url:dest.url,document:dest.document,
      sourceReply:tab.reply,sourceKey:tab.replyKey,sourceUrl:tab.url,
      sourceDocument:tab.document,baseline:dest.replyKey,created:this.clock(),
      claimed:false,simpleSend:true,simpleShutdown:shutdown,
      truncatedToNomi,originalByteLength};
    this.phase='send';this.reason='Sending one message; waiting for confirmation.';
    this.note('Prepared send transaction '+this.command.id+
      ', '+id+' to '+this.command.target+', '+new TextEncoder().encode(message).length+' bytes.');
  }
  tick() {
    if (this.simpleMode && (this.mode||'direct')==='direct') return this.simpleTick();
    if (!this.running) return;
    this.pumpOutbound();
    const now = this.clock();
    if(this.tabRetry){
      const age=Math.max(0,now-this.tabRetry.startedAt);
      if(age>=120){
        this.phase='uncertain';
        this.stop('Original ChatGPT conversation did not reconnect within 120 seconds. '+
          'Do NOT resend the world event or Reset. Restore the original GPT conversation and '+
          'use Recover Reply after the Nomi request completes.');
        return;
      }
      this.reason='Retrying original ChatGPT tab '+this.tabRetry.id+
        ' ('+Math.floor(age)+'/120 seconds; '+this.tabRetry.attempts+
        ' reconnect checks). Nomi reply will be saved until the original conversation returns.';
      return;
    }
    if (this.pair.some(id => !this.tabs[id] || now - this.tabs[id].seen > 120)) {
      if (this.command?.claimed) {
        this.phase = 'uncertain';
        this.stop('A tab disconnected during Send. Check both chats, then Reset.');
      } else if(this.mode==='api-room') {
        // Private-chat observations and GPT replies are read opportunistically.
        // A background/sleeping tab must not kill the World Engine session:
        // resume naturally after its next heartbeat. Never re-send a claimed
        // command or override an uncertain delivery state.
        if(this.command && !this.command.claimed){
          this.command=null;
          this.phase='reply';
          this.baseline=this.tabs[this.source]?.replyKey||this.baseline;
        }
        this.reason='Waiting for a selected chat tab to reconnect. Play remains active; no Nomi API action attempted.';
      } else this.stop('A chat tab disconnected or went to sleep. Reopen it, then press Play.');
      return;
    }
    if (this.phase === 'send') {
      // Once claimed, the content script owns the single draft and may be
      // waiting for the editor's Send control. Never expire that transaction
      // simply because React has not made the button clickable yet.
      if (this.command?.claimed) {
        this.reason = 'Send claimed; waiting for destination UI to accept the existing bridge draft. No duplicate will be submitted.';
      } else if (now - this.command.created > 90) {
        if (this.command.queuedOutbound && this.command.queueItem) {
          const item=this.command.queueItem;
          this.outboundQueue ||= [];
          this.outboundQueue.unshift(item);
          this.outboundCredits ||= {};
          this.outboundCredits[item.target]=(this.outboundCredits[item.target]||0)+1;
          this.command=null;this.phase='reply';
          this.log('Queued delivery was not claimed; safely returned to waiting queue.');
        } else {
          this.phase = 'uncertain';
          this.stop('Send was not claimed within 90 seconds. Check both chats, then Reset.');
        }
      }
      return;
    }
    // Waiting for live activity may intentionally be indefinite; silence is
    // not a reason to issue another Nomi API reply request or stop the bridge.
    if (this.mode === 'api-room' && this.apiSession?.pendingReply === 'live_wait') {
      this.reason = 'Listening for private-chat activity. No Nomi API reply requested.';
      return;
    }
    // The 15-minute idle watchdog belongs to browser chat relay modes.
    // The World Engine may legitimately wait for GPT or a private exchange
    // for hours. In API mode only in-flight sends use safety timeouts.
    if (!this.cliPaused && this.mode !== 'api-room' && now - this.startedWait > 900) {
      this.stop('No completed reply for 15 minutes. Check the chat, then press Play to continue waiting.'); return;
    }
    const source = this.tabs[this.source];
    const speaker = ['nomi', 'api-room'].includes(source.site) ? 'Nomi' : 'ChatGPT';
    if (now - source.seen > 70) {this.reason = 'Waiting for ' + speaker + ' tab to reconnect.'; return;}
    if (source.busy) {
      if(this.mode==='api-room' && source.site==='api-room' &&
         this.apiSession?.pendingReply==='inflight'){
        const s=this.apiSession;
        this.reason=s.replyLastErrorType
          ?'Nomi API room reply pending: last response '+s.replyLastErrorType+
            (s.replyLastHttpStatus==null?'':' (HTTP '+s.replyLastHttpStatus+')')+
            ', attempt '+(s.replyAttemptsInTurn||1)+
            (s.replyNextRetrySeconds==null?'; requesting a new reply.':
              '; next retry in '+s.replyNextRetrySeconds+'s (exponential backoff).')+
            ' World text was already delivered; it is not being resent.'
          :'Waiting for Nomi API room reply request '+(s.replyAttemptsInTurn||1)+
            ' to finish. World text was already delivered.';
      } else this.reason=speaker+' is still generating a reply.';
      return;
    }
    if (source.complete === false) {this.reason = source.completion || ('Waiting for ' + speaker + ' to finish its response.'); return;}
    if (!source.reply) {this.reason = 'No ' + speaker + ' reply detected. Check its reply preview.'; return;}
    if (this.phase === 'reply' && source.replyKey === this.baseline) {
      // A completed API-room -> GPT delivery is not proof that GPT actually
      // generated its next turn. Surface this distinct failure mode rather
      // than presenting endless "listening" while new Nomi events accumulate.
      if (this.mode === 'api-room' && source.site === 'chatgpt' &&
          this.lastDelivery?.to === 'chatgpt' && now - this.startedWait >= 45) {
        const others=Object.entries(this.tabs).filter(([id,tab])=>
          id!==this.source&&tab.site==='chatgpt'&&now-tab.seen<90);
        this.reason='ChatGPT has not produced a NEW reply after the last bridge delivery ('+
          Math.floor(now-this.startedWait)+'s). Selected GPT tab: '+this.source+'. '+
          (others.length?'Other ChatGPT tabs are also connected; verify the correct tab is selected. ':'')+
          'The previous [listening] response was already delivered. No further private-chat messages will be forwarded until GPT explicitly issues another [listening].';
      } else this.reason='Waiting for a new '+speaker+' reply. The detected reply has not changed.';
      return;
    }
    if (now - source.changed < this.stableSeconds) {this.reason = 'Detected ' + speaker + ' reply; waiting for it to finish changing.'; return;}
    // An internal status/help answer is not a conversation turn to forward.
    if (this.internalResultTab === this.source && this.internalResultBaseline !== source.replyKey &&
        !isBridgeCommandText(source.reply)) {
      this.internalResultTab = null;
      this.internalResultBaseline = null;
      this.baseline = source.replyKey;
      this.phase = 'reply';
      this.startedWait = now;
      this.lastCliFingerprint = null;
      this.log('AI Bridge internal command response consumed; not forwarded.');
      return;
    }
    // A fresh CLI command after an internal result must be processed, not swallowed.
    if (this.internalResultTab === this.source && this.internalResultBaseline !== source.replyKey) {
      this.internalResultTab = null;
      this.internalResultBaseline = null;
    }
    // Explicit-send mode: ChatGPT's ordinary replies remain private to the human.
    // Only a standalone [bridge send ...] block can reach the peer.
    if (this.mode === 'direct' &&
        (source.site === 'chatgpt' || source.site === 'nomi') &&
        !isBridgeCommandText(source.reply)) {
      this.baseline = source.replyKey;
      this.phase = 'reply';
      this.startedWait = now;
      this.lastCliFingerprint = null;
      this.reason = 'Private AI reply retained. Use [bridge send] to contact the peer.';
      return;
    }
    // Idempotency across replyKey changes while ChatGPT re-renders a command.
    // Scope to the source tab, document and exact completed CLI text.
    if (isBridgeCommandText(source.reply) &&
        !(this.mode==='api-room'&&isApiRoomDataCommand(source.reply))) {
      const fingerprint = JSON.stringify([this.source, source.url, source.document, source.reply.trim()]);
      if (this.lastCliFingerprint === fingerprint) {
        this.baseline = source.replyKey;
        this.phase = 'reply';
        this.reason = 'Duplicate CLI observation ignored; no second acknowledgment sent.';
        return;
      }
      this.lastCliFingerprint = fingerprint;
    }
    // AI Bridge 1.0: reserve standalone CLI output before any conversation forwarding.
    // This safety gate prevents control text leaking into Nomi or another AI.
    // It consumes a new reply once by advancing the source checkpoint.
    if (isBridgeCommandText(source.reply) &&
        !(this.mode==='api-room'&&isApiRoomDataCommand(source.reply))) {
      // Either human-selected participant can issue any supported CLI command.
      // The bridge still validates syntax, session state and delivery context.
      let parsed;
      try {parsed = globalThis.AIBridgeCLI?.parse(source.reply);}
      catch(error) {this.log('AI Bridge CLI rejected: ' + error.message);}
      this.baseline = source.replyKey;
      this.phase = 'reply';
      this.startedWait = now;
      if (parsed) {
        const summary = parsed.command === 'status' ?
          'State=' + (this.running ? 'running' : 'stopped') + '; phase=' + this.phase + '; turns=' + this.turns :
          'Command=' + parsed.command;
        this.log('AI Bridge CLI intercepted (' + source.site + '): ' + summary + '.');
        if (parsed.command === 'send') {
          const target = this.pair.find(id => id !== this.source);
          const dest = this.tabs[target];
          const recipient = (parsed.args.to || '').trim();
          let error = '';
          if (this.cliPaused) error = 'Bridge is paused; use [bridge resume] first.';
          else if (!dest) error = 'No connected destination.';
          else if (!['nomi','chatgpt'].includes(dest.site)) error = 'Selected destination does not support direct send.';
          else if (recipient && !([dest.site, 'Nomi', 'ChatGPT', ...(dest.site === 'chatgpt' ? ['Sera', 'Seraphina'] : []), dest.name].filter(Boolean)
              .some(n => n.toLowerCase() === recipient.toLowerCase())))
            error = 'Recipient does not match selected destination: ' + dest.site + '.';
          if (!error) {
            const parts=this.queueOutbound(this.source,target,parsed.message);
            if(parts)this.scheduleOutbound(target);
            // Successful enqueue is silent. An AI should not have to reply
            // to a transport receipt to keep the conversation moving.
            this.note('Queued '+parts+' outbound part(s) silently.');
            this.pumpOutbound();
          } else {
            this.command={id:crypto.randomUUID(),source:this.source,target:this.source,
              text:'[AI Bridge send] REJECTED: '+error,
              url:source.url,document:source.document,sourceReply:source.reply,
              sourceKey:source.replyKey,sourceUrl:source.url,sourceDocument:source.document,
              baseline:source.replyKey,created:now,claimed:false,internalResult:true};
            this.phase='send';
          }
        } else if (true) {
          const pending = this.command;
          const recipientQueue = this.queuedFor(this.source);
          const peerId = this.pair?.find(id => id !== this.source);
          const peer = peerId ? this.tabs[peerId] : null;
          const pendingReport = '[AI Bridge pending]\n' +
            'Delivery state: ' + (pending ? (pending.claimed ? 'claimed; confirmation outstanding' : 'queued; not submitted') :
              (this.phase === 'uncertain' ? 'uncertain; inspect both chats before retry' : 'no pending send')) +
            (pending ? '\nTransaction: ' + pending.id + '\nDestination: ' + (this.tabs[pending.target]?.site || 'unknown') : '') +
            '\nWaiting for: ' + (peer?.site || 'none') +
            '\nQueued for you: '+recipientQueue+'\nMode: ' + (this.mode || 'direct') + '\n[End pending]';
          const rawCount = parsed.args.last ?? parsed.rest ?? '10';
          const reviewCount = Number(rawCount);
          const reviewReport = Number.isInteger(reviewCount) && reviewCount >= 1 && reviewCount <= 50 ?
            '[AI Bridge review — last ' + reviewCount + ' activity events]\n' +
            (this.events.slice(-reviewCount).map(e => e.time + ' ' + e.text).join('\n') || 'No activity recorded.') +
            '\n[End review]\nThis is bridge activity, not a transcript of chat messages.' :
            '[AI Bridge review error] Use last=1 through last=50.';
          const scheduleReport = '[AI Bridge schedule]\n' +
            'Scheduled AI wake-ups: not active in this build.\n' +
            'No AI Bridge wake-ups have been armed.\n' +
            'The existing periodic extension heartbeat is not a user-scheduled wake-up.\n' +
            'Use the dashboard for current bridge controls; wake scheduling requires integration.\n' +
            '[End schedule]';
          if(parsed.command==='clear-queue') {
            const before=this.queuedFor(this.source);
            this.outboundQueue=(this.outboundQueue||[]).filter(m=>m.target!==this.source);
            if(this.outboundCredits)this.outboundCredits[this.source]=0;
            this.note('Discarded '+before+' undelivered queue items for '+this.source+'.');
          }
          if(parsed.command==='next-message' || (parsed.command==='listen' && this.queuedFor(this.source)>0)) this.scheduleOutbound(this.source);
          if (parsed.command === 'shutdown') {
            this.shutdownPending=true;
            this.outboundCredits={};
          }
          if (parsed.command === 'pause') this.cliPaused = true;
          if (parsed.command === 'resume' && !this.cliShutdown) {this.cliPaused = false; this.startedWait = now;}
          const text = parsed.command === 'next-message' ? '[AI Bridge] Next-message request recorded. Waiting: '+this.queuedFor(this.source) :
            parsed.command === 'clear-queue' ? '[AI Bridge] Your undelivered message queue cleared.' :
            parsed.command === 'shutdown' ? '[AI Bridge shutdown acknowledgment]\nAccepted. This is the final bridge message for this session.\nAfter this acknowledgment is submitted, the bridge will stop and revoke AI control. Only a human can restart it.\n[End shutdown acknowledgment]' :
            parsed.command === 'listen' ? '[AI Bridge listen] Listening for the next peer response; no outgoing prompt was sent.' :
            parsed.command === 'pause' ? '[AI Bridge] Paused. Relay forwarding suspended; command listener remains active. [bridge resume] restores it.' :
            parsed.command === 'resume' ? (this.cliShutdown ? '[AI Bridge] DENIED: session is shut down; human must press Play.' : '[AI Bridge] Resumed. Relay forwarding enabled.') :
            parsed.command === 'schedule' ? scheduleReport :
            parsed.command === 'review' ? reviewReport :
            parsed.command === 'pending' ? pendingReport :
            parsed.command === 'help' ? (parsed.args.topic === 'schedule' ? '[AI Bridge schedule help]\nWake scheduler not yet active. Planned syntax: [bridge wake at="2026-11-03T15:10:00-05:00" reason="Visit"] or [bridge wake in="30 minutes"].' : globalThis.AIBridgeCLI.HELP) :
            parsed.command !== 'status' ? '[AI Bridge] NOT_IMPLEMENTED: ' + parsed.command + '. No action was taken.' :
            '[AI Bridge status]\nState: ' + (this.running?'running':'stopped') +
            '\nMode: ' + (this.mode||'direct') + '\nPhase: ' + this.phase +
            '\nConversation turns: ' + this.turns + '\nCLI transactions: ' + (this.cliTransactions||0) + '\nPending send: ' + (this.command?'yes':'no') +
            '\n[End status]\nThis is an internal bridge notification. Reply [bridge listen] to wait.';
          if (['listen','next-message','clear-queue'].includes(parsed.command) &&
              (parsed.command==='clear-queue' || this.queuedFor(this.source)===0)) {
            this.note('Queue control '+parsed.command+' accepted silently.');
            return;
          }
          if ((parsed.command==='next-message' || parsed.command==='listen') && this.queuedFor(this.source)>0 &&
              this.releaseOutbound(this.source)) {
            this.outboundCredits[this.source]=Math.max(0,(this.outboundCredits[this.source]||0)-1);
            this.note('Next queued message released directly; no redundant CLI receipt.');
          } else if (['listen','next-message','clear-queue'].includes(parsed.command)) {
            // Retrieval/clear never produce chat receipts.
            this.note('Queue control processed without a reply.');
          } else if (['pause','resume'].includes(parsed.command)) {
            const stateWord = parsed.command === 'pause' ? 'paused' : 'running';
            this.queuePairNotice(parsed.command,
              '[AI Bridge ' + parsed.command + ']\nState: ' + stateWord +
              '. Requested by ' + source.site + '. Notification delivery in progress.\n[End notice]',
              this.source);
          } else {
            this.command = {id:crypto.randomUUID(),source:this.source,target:this.source,
              text,url:source.url,document:source.document,sourceReply:source.reply,
              sourceKey:source.replyKey,sourceUrl:source.url,sourceDocument:source.document,
              baseline:source.replyKey,claimed:false,created:now,internalResult:true,
              shutdownAfterAck:parsed.command === 'shutdown'};
            this.phase='send';
            this.log('AI Bridge internal ' + parsed.command + ' response queued for the issuing tab.');
          }
        }
      } else if (!this.reason.startsWith('AI Bridge CLI rejected:')) {
        this.log('AI Bridge CLI-looking message blocked; not forwarded.');
      }
      return;
    }
    if (this.cliPaused) {this.reason = 'AI Bridge paused. Waiting for [bridge resume] from the active AI.'; return;}
    const target = this.pair.find(id => id !== this.source);
    const dest = this.tabs[target];
    const receiver = ['nomi', 'api-room'].includes(dest.site) ? 'Nomi' : 'ChatGPT';
    if (now - dest.seen > 70) {this.reason = 'Waiting for ' + receiver + ' tab to reconnect.'; return;}
    if (!dest.ready) {this.reason = receiver + ' cannot receive yet: ' + (dest.diagnostic || 'check its editor and Send button'); return;}
    if (dest.busy) {this.reason = 'Waiting for ' + receiver + ' to finish generating before sending.'; return;}
    let prefilledDraft = false;
    if (dest.draft) {
      // Only an unchanged draft exactly matching the authorized outbound payload may auto-submit.
      // Probe with bounded exponential backoff; resume the queued source reply
      // automatically once the editor becomes empty.
      const expected = dest.site === 'nomi' ? limitNomiMessage(source.reply) : source.reply;
      const matches = dest.draftText === expected.trim();
      const key = JSON.stringify([target, dest.document, source.replyKey, dest.draftText]);
      if (!this.draftBackoff || this.draftBackoff.key !== key)
        this.draftBackoff = {key, attempts:0, next:now, delay:1};
      const backoff = this.draftBackoff;
      if (now >= backoff.next) {
        backoff.attempts++;
        backoff.delay = Math.min(16, Math.pow(2, Math.min(backoff.attempts-1,4)));
        backoff.next = now + backoff.delay;
      }
      if (matches && backoff.attempts >= 4) {
        prefilledDraft = true;
        this.note('Unchanged matching bridge draft verified across 4 checks; submitting existing text.');
      } else {
      this.reason = 'Destination contains a draft; preserving it. Retry check ' +
        backoff.attempts + ' in ' + Math.max(0,Math.ceil(backoff.next-now)) +
        's; delivery resumes when editor clears or matches the queued payload for 4 checks.';
      return;
      }
    }
    this.draftBackoff = null;
    // Defense in depth: if the dashboard is accidentally in Direct mode,
    // do not leak API World Engine control tags to the Nomi private chat.
    if (dest.site === 'nomi' && this.mode !== 'group' &&
        /\[(?:tail|history|wait|listening|say\s+room|say\s+chat)\b[^\]]*\]/i.test(source.reply)) {
      this.stop('Bridge control tag blocked from Nomi private chat. Select API Room mode to use [tail], [history], [wait] or [say room].');
      return;
    }
    const includesReminder = dest.site === 'chatgpt' && this.remindChatGPT;
    const text = dest.site === 'nomi' ? limitNomiMessage(source.reply) : source.reply + (includesReminder ? LENGTH_REMINDER : '');
    const truncated = dest.site === 'nomi' && text.length < source.reply.length;
    if (truncated) this.log(speaker + ' reply shortened to 750 characters for Nomi.');
    this.command = {id: crypto.randomUUID(), target, text, truncated, includesReminder, url: dest.url, document: dest.document,
      claimed: false, created: now, baseline: dest.replyKey, prefilledDraft,
      source: this.source, sourceReply: source.reply, sourceKey: source.replyKey, sourceDocument: source.document, sourceUrl: source.url, previousPhase: this.phase};
    this.phase = 'send'; this.log(`Forwarding ${source.site} → ${dest.site}: read ${source.reply.length} characters; sending ${text.length}.`);
  }
  validateSource(id, snapshot) {
    const cmd = this.command;
    if (!cmd || cmd.id !== id || !this.running || this.phase !== 'send') return false;
    // First notification has already been confirmed. Do not recheck the now-changing
    // origin conversation while sending the second shutdown notice.
    if (cmd.shutdownSecond && this.shutdownFirstAck) return true;
    // A queued message was accepted from a verified participant at enqueue
    // time. Its source may legitimately have produced later replies while it
    // waited; do not require that old reply to remain the newest DOM message.
    if (cmd.queuedOutbound) return !!snapshot && !snapshot.error &&
      snapshot.document===cmd.sourceDocument && snapshot.url===cmd.sourceUrl;
    const valid = snapshot && !snapshot.error && !snapshot.busy && snapshot.complete !== false &&
      snapshot.reply === cmd.sourceReply &&
      snapshot.document === cmd.sourceDocument && snapshot.url === cmd.sourceUrl;
    // replyKey includes DOM message counts and can change during harmless re-renders.
    // The exact reply text plus conversation URL and document identity are the safety boundary.
    if (valid) return true;
    if (cmd.claimed) {
      this.phase = 'uncertain';
      this.stop('The source reply changed before Send. Nothing further will be sent; check the draft and Reset.');
    } else {
      this.phase = cmd.previousPhase || 'reply'; this.command = null;
      if (snapshot && cmd.source) this.heartbeat(cmd.source, snapshot);
      this.reason = 'Reply changed or is still generating. Waiting for the complete reply.';
    }
    return false;
  }
  claim(tab, id, checkOnly = false) {
    const cmd = this.command;
    if (!this.running || this.phase !== 'send' || !cmd || cmd.id !== id || cmd.target !== tab) return {allowed: false};
    if (checkOnly) return {allowed: cmd.claimed};
    if (cmd.claimed) return {allowed: false};
    cmd.claimed = true; return {allowed: true};
  }
  acknowledge(tab, data) {
    const cmd = this.command;
    if (this.phase !== 'send' || !cmd || cmd.id !== data.id || cmd.target !== tab || !cmd.claimed) return {};
    if(cmd.simpleStartup) {
      if(data.error) {
        this.phase='uncertain';
        this.stop('Tab 1 startup message was not confirmed: '+data.error);
      } else {
        this.command=null;this.phase='reply';this.simplePeerAwait=false;
        this.simpleControllerSeen=this.tabs[this.pair[0]]?.replyKey;
        this.reason='Startup help delivered to Tab 1. Waiting for [bridge send].';
      }
      return {};
    }
    if(cmd.simpleSend) {
      this.note('Send transaction '+cmd.id+(data.error?' failed: '+data.error:' confirmed by destination editor.'));
      if(data.error) {
        this.phase='uncertain';
        this.stop('Send uncertain: '+data.error+'. Inspect recipient before restarting.');
      } else {
        if(cmd.source===this.pair[0]) {
          if(cmd.truncatedToNomi) this.simpleTruncationWarning='[Bridge warning: Your previous message was '+cmd.originalByteLength+' UTF-8 bytes. Only the first 750 bytes were delivered to Nomi; the remainder was truncated. Keep future messages to Nomi within 750 UTF-8 bytes.]';
          this.simpleControllerSeen=cmd.sourceKey;
          this.simplePeerSeen=cmd.baseline;
          this.simplePeerAwait=!cmd.simpleShutdown;
        } else {
          this.simplePeerSeen=cmd.sourceKey;
          this.simpleControllerSeen=cmd.baseline;
          this.simplePeerAwait=false;
          this.note('Tab 2 reply delivered. Waiting for a new Tab 1 assistant turn.');
        }
        this.turns=(this.turns||0)+1;
        this.lastDelivery={transactionId:cmd.id,from:this.tabs[cmd.source]?.site,
          to:this.tabs[tab]?.site,sentCharacters:cmd.text.length,
          truncated:!!cmd.truncatedToNomi};
        this.command=null;this.phase='reply';
        if(cmd.simpleShutdown){this.running=false;this.phase='shutdown';}
        else this.reason=this.simplePeerAwait?'Waiting for a new peer response.':'Waiting for a new Tab 1 command.';
      }
      return {};
    }
    if (data.error && cmd.queuedOutbound &&
        data.error === 'Destination began generating before insertion; draft not modified') {
      this.outboundQueue ||= [];
      this.outboundQueue.unshift(cmd.queueItem);
      this.outboundCredits ||= {};
      this.outboundCredits[tab]=(this.outboundCredits[tab]||0)+1;
      this.command=null;this.phase='reply';
      this.reason='Recipient started generating; queued send deferred until idle.';
      return {};
    }
    if (data.error) {
      if(cmd.queuedOutbound)this.failedQueueItem=cmd.queueItem;
      this.phase = 'uncertain';
      this.stop(`Send stopped: ${data.error}. Check both chats, then Reset.`);
    }
    else {
      this.lastDelivery = {from: this.tabs[cmd.source]?.site, to: this.tabs[tab].site,
        readCharacters: cmd.sourceReply?.length, sentCharacters: cmd.text.length,
        truncated: !!cmd.truncated, reminderAdded: !!cmd.includesReminder};
      this.log('Send confirmed: ' + cmd.text.length + ' characters to ' + this.tabs[tab].site + '.');
      if (cmd.truncated && this.tabs[cmd.source]?.site === 'chatgpt') this.remindChatGPT = true;
      if (cmd.includesReminder) this.remindChatGPT = false;
      if (cmd.explicitSend) this.note('Explicit send confirmed to ' + this.tabs[tab].site + '.');
      if (cmd.queuedOutbound) {
        this.deliveredCounts ||= {};
        this.deliveredCounts[tab]=(this.deliveredCounts[tab]||0)+1;
      }
      if (cmd.internalResult) {
        this.cliTransactions = (this.cliTransactions || 0) + 1;
        this.internalResultTab = cmd.target;
        this.internalResultBaseline = cmd.baseline;
      }
      if (cmd.pairNotice) {
        const notice=this.pairNotice;
        if (notice) {
          notice.targets.shift();
          this.note('Confirmed ' + notice.kind + ' notice submitted to ' + tab);
          if (notice.targets.length) {
            this.command=null;
            if (this.queueNextPairNotice()) return {};
            // Do not fall through to ordinary relay acknowledgment if a peer
            // could not receive the notice.
            this.command=null;this.phase='reply';return {};
          } else {
            this.pairNotice=null;
            this.source=notice.restoreSource;
            this.baseline=this.tabs[this.source]?.replyKey || notice.restoreBaseline;
            this.phase='reply';
            this.startedWait=this.clock();
            this.command=null;
            this.log('Both ' + notice.kind + ' notifications submitted.');
            return {};
          }
        }
      }
      if (cmd.shutdownAfterAck && !cmd.shutdownSecond) {
        const peer = this.pair?.find(id => id !== cmd.target);
        const dest = peer && this.tabs[peer];
        if (!dest || !dest.ready || dest.busy || dest.draft || this.clock()-dest.seen > 70 || !['nomi','chatgpt'].includes(dest.site)) {
          this.phase='uncertain'; this.running=false;
          this.log('Shutdown notification reached requester but peer was unavailable. Inspect peer and complete shutdown manually; do not resend automatically.');
          this.command=null; return {};
        }
        this.shutdownFirstAck = {tab:cmd.target,at:this.clock()};
        this.command = {id:crypto.randomUUID(),source:cmd.source,target:peer,
          text:'[AI Bridge shutdown notice] The other participant requested shutdown. This bridge session is ending; no more messages will be forwarded. [End notice]',
          url:dest.url,document:dest.document,sourceReply:cmd.sourceReply,sourceKey:cmd.sourceKey,
          sourceUrl:cmd.sourceUrl,sourceDocument:cmd.sourceDocument,baseline:dest.replyKey,
          claimed:false,created:this.clock(),internalResult:true,shutdownAfterAck:true,shutdownSecond:true};
        this.phase='send';this.log('First shutdown notice confirmed; notifying peer before stopping.');
        return {};
      }
      this.source = cmd.cliRestore?.source || cmd.target;
      this.baseline = cmd.cliRestore?.baseline || cmd.baseline;
      this.phase = cmd.cliRestore?.phase || 'reply';
      if (!cmd.internalResult) this.turns++;
      this.startedWait = this.clock();
      if (cmd.shutdownAfterAck) {
        this.cliShutdown = true;
        this.cliPaused = true;
        this.running = false;
        this.phase = 'shutdown';
        this.log('AI Bridge shutdown notices submitted to both participants. Session stopped; only dashboard Play can reauthorize.');
      } else this.log(`${this.running ? 'Running' : 'Stopped'}: waiting for ${this.tabs[tab].site} to reply.`);
    }
    this.command = null;
    this.drainPendingCli();
    this.pumpOutbound();
    return {};
  }
  state() {
    this.tick();
    if(this.running && this.phase!=='send') {
      const pending=(this.waitingCli||[]).length;
      const deferred=(this.deferredCli||[]).length;
      const outbound=(this.outboundQueue||[]).length;
      if(pending || deferred || outbound) {
        const detail='Bridge queues: '+pending+' inbound commands waiting, '+
          deferred+' superseded commands preserved, '+outbound+' outbound parts waiting.';
        this.reason=detail+(deferred?' Recovery required for superseded commands.':'');
      }
    }
    return {running: this.running, paused: !!this.cliPaused, shutdown: !!this.cliShutdown, cliControllerTab: this.cliControllerTab || this.pair?.[0] || null, phase: this.phase, turns: this.turns, cliTransactions: this.cliTransactions || 0, reason: this.reason, pair: this.pair,
      tabRetry:this.tabRetry?{tabId:this.tabRetry.id,expectedUrl:this.tabRetry.expectedUrl,
        elapsedSeconds:Math.max(0,Math.floor(this.clock()-this.tabRetry.startedAt)),
        reconnectChecks:this.tabRetry.attempts}:null,
      outboundQueueCounts:Object.fromEntries((this.pair||[]).map(id=>[id,this.queuedFor(id)])),incomingQueueCount:(this.waitingCli||[]).length,deferredCommandCount:(this.deferredCli||[]).length,events: this.events, lastDelivery: this.lastDelivery, tabs: Object.values(this.tabs).filter(t => this.clock() - t.seen < 300)
        .map(t => ({...t, connected: this.clock() - t.seen < 90}))};
  }
  serialize() {const {clock, ...data} = this; return data;}
}
if (typeof module !== 'undefined') module.exports = {Bridge, limitNomiMessage};
else globalThis.Bridge = Bridge;

