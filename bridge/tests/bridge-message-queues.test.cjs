const {test}=require('node:test');
const assert=require('node:assert/strict');
globalThis.AIBridgeCLI=require('../extension/bridge-cli.js');
if(!globalThis.crypto)globalThis.crypto=require('node:crypto').webcrypto;
const {Bridge}=require('../extension/engine.js');
let now=1000;
const tab=(site,reply,key)=>({site,reply,replyKey:key,url:'https://'+site+'.example/chat',document:site,seen:now,changed:now-5,ready:true,busy:false,draft:false,complete:true});
function setup(){const b=new Bridge(()=>now);b.running=true;b.mode='direct';b.phase='reply';b.source='g';b.pair=['g','n'];b.baseline='g0';b.startedWait=now;b.stableSeconds=1;b.cliSeen={g:'g0',n:'n0'};b.tabs={g:tab('chatgpt','[bridge send] '+ 'Q'.repeat(1600),'g1'),n:tab('nomi','Hi','n0')};return b;}
function confirm(b){const cmd=b.command;assert.ok(cmd);assert.equal(b.claim(cmd.target,cmd.id).allowed,true);b.acknowledge(cmd.target,{id:cmd.id});}
test('long Nomi message is split into bounded parts and next releases only one',()=>{const b=setup();b.tick();assert.equal(b.outboundQueue.length,3);confirm(b);assert.match(b.command.text,/message 1 of 3/);assert.ok(b.command.text.length<=750);confirm(b);assert.equal(b.outboundQueue.length,2);assert.equal(b.phase,'reply');b.tabs.n=tab('nomi','[next message]','n1');b.dispatchPeerCli('n');assert.match(b.command.text,/message 2 of 3/);confirm(b);assert.equal(b.outboundQueue.length,1);assert.equal(b.phase,'reply');assert.equal(b.source,'g');assert.equal(b.outboundCredits.n,0);});
test('clear queue discards only waiting undelivered items',()=>{const b=setup();b.tick();confirm(b);confirm(b);b.tabs.n=tab('nomi','[clear queue]','n1');b.dispatchPeerCli('n');assert.equal(b.outboundQueue.length,0);assert.equal(b.deliveredCounts.n,1);assert.match(b.command.text,/queue cleared/);});
test('short forms parse on their own line',()=>{assert.equal(globalThis.AIBridgeCLI.parse('[next message]').command,'next-message');assert.equal(globalThis.AIBridgeCLI.parse('[clear queue]').command,'clear-queue');});
