const assert = require('node:assert/strict');
const {test} = require('node:test');
globalThis.AIBridgeCLI = require('../extension/bridge-cli.js');
if (!globalThis.crypto) globalThis.crypto = require('node:crypto').webcrypto;
const {Bridge}=require('../extension/engine.js');
test('shutdown sends acknowledgment before revoking session',()=>{
 const t=1000, b=new Bridge(()=>t);
 b.running=true;b.mode='direct';b.pair=['g','n'];b.source='g';b.phase='reply';
 b.stableSeconds=1;b.startedWait=t;b.baseline='prior';
 b.tabs={g:{site:'chatgpt',ready:true,busy:false,draft:false,complete:true,seen:t,changed:t-2,reply:'[bridge shutdown]',replyKey:'shut',url:'https://chatgpt.com/c/one',document:'doc-g'},n:{site:'nomi',ready:true,busy:false,draft:false,complete:true,seen:t,changed:t-2,reply:'hello',replyKey:'n',url:'https://nomi.ai/chats/one',document:'doc-n'}};
 b.tick();assert.equal(b.running,true);assert.equal(b.phase,'send');assert.equal(b.command.shutdownAfterAck,true);
 const cmd=b.command;assert.equal(cmd.target,'g');assert.match(cmd.text,/shutdown acknowledgment/);
 assert.equal(b.claim('g',cmd.id).allowed,true);
 b.acknowledge('g',{id:cmd.id});assert.equal(b.running,false);assert.equal(b.cliShutdown,true);assert.equal(b.phase,'shutdown');
 assert.equal(b.claim('g',cmd.id).allowed,false);
});
