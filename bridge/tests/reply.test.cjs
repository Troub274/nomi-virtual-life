const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
async function inspect({completed=false,streaming=false,rootStreaming=false,container=true,modern=false,turnNumber=12,hasStableKey=true,hasLegacy=true,unitKey=null}={}) {
 let snapshot;
 const visual={getClientRects:()=>[{}]};
 const modernTurn={getAttribute:()=>completed?"complete":"streaming",querySelectorAll:()=>parts};
 const turn={matches:()=>rootStreaming,querySelectorAll(selector){
  if(selector==='[data-message-author-role="assistant"]')return parts;
  if(selector.startsWith('button'))return completed?[visual]:[];
  return streaming?[visual]:[];
 }};
 const logicalTurn={getAttribute:attr=>attr==='data-testid'?'conversation-turn-'+turnNumber:null};
 const stableTurn={getAttribute:attr=>attr==='data-turn-key'?'stable-node-'+turnNumber:null};
 const unitTurn={getAttribute:attr=>attr==='data-chatgpt-search-unit-key'?unitKey:null};
 const parts=['The whole response begins here.','And ends.'].map(text=>({...visual,innerText:text,getAttribute:()=>null,closest:selector=>
  selector==='[data-chatgpt-search-unit-key]' ? (container&&unitKey?unitTurn:null) :
  selector==='[data-turn-key]' ? (container&&hasStableKey?stableTurn:null) :
  selector==='[data-testid^="conversation-turn-"]' ? (container&&hasLegacy?logicalTurn:null) :
  modern&&selector==='[data-talvt-turn-state]'?modernTurn:
  selector.startsWith('article')&&container?turn:null}));
 const context={location:{hostname:'chatgpt.com',href:'https://chatgpt.com/c/test'},crypto:globalThis.crypto,
 document:{title:'ChatGPT',querySelectorAll:selector=>selector.startsWith('[data-message-author-role=')?parts:[]},
 getComputedStyle:()=>({visibility:'visible'}),setInterval:()=>{},setTimeout,
 chrome:{storage:{local:{get:async()=>({})},onChanged:{addListener:()=>{}}},runtime:{onMessage:{addListener:()=>{}},sendMessage:async m=>{snapshot=m.data.snapshot;return {};}}}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../extension/content.js'),'utf8'),context);
 await new Promise(r=>setImmediate(r));return snapshot;
}
test('reads all assistant blocks of the current response instead of its short final block',async()=>{
 const s=await inspect({completed:true});assert.equal(s.reply,'The whole response begins here.\n\nAnd ends.');assert.equal(s.complete,true);
});
test('no completion control means no completed response, even without a visible Stop button',async()=>{
 const s=await inspect();assert.equal(s.complete,false);
});
test('streaming remains incomplete even if a copy control is present',async()=>{
 const s=await inspect({completed:true,streaming:true});assert.equal(s.complete,false);
});
test('missing response container fails closed',async()=>{
 const s=await inspect({completed:true,container:false});assert.equal(s.complete,false);
});

test('streaming marker on the response container blocks forwarding',async()=>{
 const s=await inspect({completed:true,rootStreaming:true});assert.equal(s.complete,false);
});

test('new ChatGPT layout reads full reply only when the turn is complete',async()=>{
 const done=await inspect({modern:true,completed:true});
 assert.equal(done.reply,'The whole response begins here.\n\nAnd ends.');assert.equal(done.complete,true);
 const streaming=await inspect({modern:true});assert.equal(streaming.complete,false);
});


test('current ChatGPT DOM provides a stable backend turn identity even without numbered wrapper',async()=>{
 const original=await inspect({completed:true,modern:true,turnNumber:17,hasLegacy:false});
 const redraw=await inspect({completed:true,modern:true,turnNumber:17,hasLegacy:false});
 assert.equal(original.assistantTurnKey,'node:stable-node-17');
 assert.equal(redraw.assistantTurnKey,original.assistantTurnKey);
 assert.equal((await inspect({completed:true,modern:true,turnNumber:18,hasLegacy:false})).assistantTurnKey,'node:stable-node-18');
});
test('legacy ChatGPT DOM remains supported by numbered turn wrappers',async()=>{
 const legacy=await inspect({completed:true,turnNumber:9,hasStableKey:false});
 assert.equal(legacy.assistantTurnKey,'legacy:9');
});
test('no logical GPT turn identity fails closed',async()=>{
 const s=await inspect({completed:true,hasStableKey:false,hasLegacy:false});
 assert.equal(s.assistantTurnKey,null);
});

test('assistant unit key is preferred when supplied by the current GPT layout',async()=>{
 const s=await inspect({completed:true,modern:true,unitKey:'response-491:assistant',hasStableKey:false,hasLegacy:false});
 assert.equal(s.assistantTurnKey,'unit:response-491:assistant');
});
