const assert = require('node:assert/strict');
const {test} = require('node:test');
globalThis.AIBridgeCLI = require('../extension/bridge-cli.js');
if (!globalThis.crypto) globalThis.crypto = require('node:crypto').webcrypto;
const {Bridge} = require('../extension/engine.js');
test('pending after internal status is executed rather than discarded', () => {
  let t = 1000;
  const b = new Bridge(() => t);
  b.mode = 'direct'; b.running = true; b.pair = ['g','n']; b.source = 'g';
  b.phase = 'reply'; b.baseline = 'status-result'; b.stableSeconds = 3; b.startedWait = t;
  b.internalResultTab = 'g'; b.internalResultBaseline = 'prior-command';
  b.tabs = {
    g: {site:'chatgpt',ready:true,busy:false,draft:false,complete:true,seen:t,changed:t-10,reply:'[bridge pending]',replyKey:'next-command',url:'https://chatgpt.com/c/test',document:'g-doc'},
    n: {site:'nomi',ready:true,busy:false,draft:false,complete:true,seen:t,changed:t-10,reply:'hello',replyKey:'nomi-old',url:'https://nomi.ai/chat',document:'n-doc'}
  };
  b.tick();
  assert.equal(b.phase,'send');
  assert.equal(b.command?.internalResult,true);
  assert.equal(b.command?.target,'g');
  assert.match(b.command?.text,/AI Bridge pending/);
});
