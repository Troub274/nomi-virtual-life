const {test}=require('node:test');
const assert=require('node:assert/strict');
if(!globalThis.crypto)globalThis.crypto=require('node:crypto').webcrypto;
globalThis.AIBridgeCLI=require('../extension/bridge-cli.js');
const {HeartbeatBridge}=require('../extension/heartbeat.js');
let now=1000;
const tab=(site,reply,key,id,turn)=>({id,site,reply,replyKey:key,assistantTurnNumber:site==='chatgpt'?(turn??Number(String(key).split('|')[0])):null,url:'https://'+site+'.test',document:site,seen:now,changed:now-5,matches:Number(String(key).split('|')[0]),ready:true,complete:true,busy:false,draft:false});
function setup(){
 const b=new HeartbeatBridge(()=>now);
 b.tabs={g:tab('chatgpt','Previous','1|g|Previous','g'),n:tab('nomi','Previous','1|n|Previous','n')};
 b.start({mode:'direct',tabs:['g','n'],settle:1});
 deliver(b);return b;
}
function observe(b,id,item) {
 b.heartbeat(id,item);
 now+=2;
 b.heartbeat(id,{...item,seen:now});
}
function deliver(b){const c=b.command;assert.ok(c,'expected an outgoing command');assert.equal(b.claim(c.target,c.id).allowed,true);b.acknowledge(c.target,{id:c.id});return c;}
test('first send after startup happens only once despite repeat heartbeats and DOM repaint',()=>{
 const b=setup();
 observe(b,'g',tab('chatgpt','[bridge send] Hello Nomi','2|g|send','g'));
 const first=deliver(b);assert.equal(first.target,'n');assert.equal(first.text,'Hello Nomi');
 observe(b,'n',tab('nomi','Hello back','2|n|Hello back','n'));deliver(b);
 for(const key of ['3|changed|[bridge send] Hello Nomi','4|changed-again|[bridge send] Hello Nomi']){
  observe(b,'g',tab('chatgpt','[bridge send] Hello Nomi',key,'g',2));
  assert.equal(b.command,null,'duplicate command must not create a new send');
 }
 assert.equal(b.events.filter(e=>/Prepared send transaction/.test(e.text)&&/g to n/.test(e.text)).length,1);
});
test('Tab 1 can resume from a paused bridge',()=>{
 const b=setup();observe(b,'g',tab('chatgpt','[bridge pause]','2|g|pause','g'));
 assert.equal(b.cliPaused,true);
 observe(b,'g',tab('chatgpt','[bridge resume]','3|g|resume','g'));
 assert.equal(b.cliPaused,false);assert.equal(b.command,null);
 observe(b,'g',tab('chatgpt','[bridge send] Back to work','4|g|send','g'));
 assert.equal(b.command?.text,'Back to work');
});
test('Tab 1 can pause and resume while waiting on Tab 2',()=>{
 const b=setup();observe(b,'g',tab('chatgpt','[bridge send] First','2|g|send','g'));deliver(b);
 assert.equal(b.simplePeerAwait,true);
 observe(b,'g',tab('chatgpt','[bridge pause]','3|g|pause','g'));assert.equal(b.cliPaused,true);
 observe(b,'n',tab('nomi','Nomi reply','2|n|reply','n'));assert.equal(b.command,null);
 observe(b,'g',tab('chatgpt','[bridge resume]','4|g|resume','g'));assert.equal(b.cliPaused,false);
 observe(b,'n',tab('nomi','Nomi reply','2|n|reply','n'));assert.equal(b.command?.text,'Nomi reply');
});

test('causal turn barrier blocks FIRST until a new GPT response exists, then sends SECOND',()=>{
 const b=setup();
 observe(b,'g',tab('chatgpt','[bridge send] FIRST','2|first|A','g'));
 assert.equal(deliver(b).text,'FIRST');
 observe(b,'n',tab('nomi','Nomi responds','2|nomi|reply','n'));
 assert.equal(deliver(b).text,'Nomi responds');
 assert.equal(b.simpleControllerTurn,2);
 observe(b,'g',tab('chatgpt','[bridge send] FIRST','2|rerendered|old-command','g',2));
 assert.equal(b.command,null,'stale first command cannot be replayed');
 observe(b,'g',tab('chatgpt','[bridge send] FIRST','3|unstable-DOM|old-command','g',2));
 assert.equal(b.command,null,'even a misleading count change must not replay old command');
 observe(b,'g',tab('chatgpt','[bridge send] SECOND','3|new-assistant|new-command','g'));
 assert.equal(b.command?.text,'SECOND','new GPT assistant reply must be eligible');
 assert.equal(b.events.filter(e=>/Prepared send transaction/.test(e.text)&&/g to n/.test(e.text)).length,2);
});

test('two distinct GPT turns with identical text are both intentionally delivered',()=>{
 const b=setup();
 observe(b,'g',tab('chatgpt','[bridge send] SAME','2|assistant-A|SAME','g',2));
 assert.equal(deliver(b).text,'SAME');
 observe(b,'n',tab('nomi','First response','2|nomi-A|First response','n'));deliver(b);
 observe(b,'g',tab('chatgpt','[bridge send] SAME','3|assistant-B|SAME','g',3));
 assert.equal(deliver(b).text,'SAME');
 assert.equal(b.simpleControllerTurn,3);
 assert.equal(b.events.filter(e=>/Prepared send transaction/.test(e.text)&&/g to n/.test(e.text)).length,2);
});
test('DOM replyKey change cannot redeliver a controller turn while idle',()=>{
 const b=setup();
 observe(b,'g',tab('chatgpt','[bridge send] A','2|original|A','g',2));
 deliver(b);
 observe(b,'n',tab('nomi','Reply','2|n|Reply','n'));deliver(b);
 for(const id of ['2|remount-one|A','19|remount-two|A']) {
   observe(b,'g',tab('chatgpt','[bridge send] A',id,'g',2));
   assert.equal(b.command,null);
 }
 assert.equal(b.simpleControllerTurn,2);
});
test('direct startup honors configured settle seconds',()=>{
 const b=setup();
 assert.equal(b.stableSeconds,1);
});
test('direct refuses to start if GPT conversation cannot identify its turn',()=>{
 const b=new HeartbeatBridge(()=>now);
 b.tabs={g:tab('chatgpt','Old reply','4|old|Old reply','g',null),n:tab('nomi','Old','2|old|Old','n')};
 b.tabs.g.assistantTurnNumber=null;
 assert.throws(()=>b.start({mode:'direct',tabs:['g','n']}),/conversation turn number is unavailable/);
});

test('30-turn alternating run never replays the preceding controller turn after repaints',()=>{
 const b=setup();
 for(let i=1;i<=30;i++) {
   const ordinal=i+1,body='[bridge send] MESSAGE-'+i;
   observe(b,'g',tab('chatgpt',body,ordinal+'|original-'+i+'|message','g',ordinal));
   assert.equal(deliver(b).text,'MESSAGE-'+i);
   observe(b,'n',tab('nomi','ACK-'+i,(i+1)+'|nomi-'+i+'|ack','n'));deliver(b);
   observe(b,'g',tab('chatgpt',body,(ordinal+100)+'|repaint-'+i+'|message','g',ordinal));
   assert.equal(b.command,null,'old GPT turn replayed after Nomi response '+i);
 }
 assert.equal(b.turns,60);
 // Activity is deliberately capped at 100 entries; delivered turn count is durable.
 assert.equal(b.lastDelivery.to,'chatgpt');
});
