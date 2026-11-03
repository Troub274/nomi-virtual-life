const {test}=require('node:test');
const assert=require('node:assert/strict');
globalThis.AIBridgeCLI=require('../extension/bridge-cli.js');
if(!globalThis.crypto)globalThis.crypto=require('node:crypto').webcrypto;
const {Bridge}=require('../extension/engine.js');
let now=1000;
const tab=(site,reply,key)=>({site,reply,replyKey:key,url:'https://'+site+'.example/chat',document:site,seen:now,changed:now-5,ready:true,busy:false,draft:false,complete:true});
function setup(){const b=new Bridge(()=>now);b.running=true;b.mode = 'legacy';b.phase='reply';b.source='g';b.pair=['g','n'];b.baseline='g0';b.startedWait=now;b.stableSeconds=1;b.cliSeen={g:'g0',n:'n0'};b.tabs={g:tab('chatgpt','[bridge send] '+ 'Q'.repeat(1600),'g1'),n:tab('nomi','Hi','n0')};return b;}
function confirm(b){const cmd=b.command;assert.ok(cmd);assert.equal(b.claim(cmd.target,cmd.id).allowed,true);b.acknowledge(cmd.target,{id:cmd.id});}
test('legacy controller: long Nomi message releases one part at a time only when Nomi requests the next',()=>{
 const b=setup();
 b.tick();
 assert.equal(b.outboundQueue.length,2,'first part is active, two remain queued');
 assert.match(b.command.text,/part 1 of 3/);
 assert.ok(b.command.text.length<=750);
 confirm(b);
 assert.equal(b.outboundQueue.length,2);
 assert.equal(b.command,null);
 b.tabs.n=tab('nomi','[next message]','n1');
 b.dispatchPeerCli('n');
 assert.match(b.command.text,/part 2 of 3/);
 confirm(b);
 assert.equal(b.outboundQueue.length,1);
 assert.equal(b.command,null);
 assert.equal(b.source,'g');
 assert.equal(b.outboundCredits.n,0);
});
test('legacy controller: clear queue discards only undelivered parts and never repeats the first',()=>{
 const b=setup();b.tick();
 confirm(b);
 assert.equal(b.deliveredCounts.n,1);
 assert.equal(b.outboundQueue.length,2);
 b.tabs.n=tab('nomi','[clear queue]','n1');
 b.dispatchPeerCli('n');
 assert.equal(b.outboundQueue.length,0);
 assert.equal(b.deliveredCounts.n,1);
 assert.equal(b.command,null,'queue control is silent');
 assert.ok(b.events.some(e=>/Discarded 2 undelivered queue items/.test(e.text)));
});
test('legacy controller: short forms parse on their own line',()=>{assert.equal(globalThis.AIBridgeCLI.parse('[next message]').command,'next-message');assert.equal(globalThis.AIBridgeCLI.parse('[clear queue]').command,'clear-queue');});
