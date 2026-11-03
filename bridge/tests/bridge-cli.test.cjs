const assert = require('node:assert/strict');
const {test} = require('node:test');
const {parse,HELP}=require('../extension/bridge-cli.js');
test('help and wake parsing',()=>{
 assert.equal(parse('[bridge help]').command,'help');
 assert.equal(parse('[bridge wake at="tomorrow 3:15 PM" reason="Mary"]').args.at,'tomorrow 3:15 PM');
 assert.match(HELP,/\[bridge shutdown\]/);
});
test('send blocks include complete payload',()=>{
 const p=parse('[bridge send to="Mary"]\nHello!\n[/bridge]');
 assert.equal(p.command,'send'); assert.equal(p.args.to,'Mary'); assert.equal(p.message,'Hello!');
});
test('ordinary prose and quoted syntax are not commands',()=>{
 assert.equal(parse('I said [bridge shutdown] yesterday.'),null);
 assert.equal(parse('> [bridge pause]'),null);
 assert.equal(parse('[bridge send]\nHi').message,'Hi');
});
test('unknown and ambiguous input fails safely',()=>{
 assert.throws(()=>parse('[bridge erase]'),/Unknown/);
 assert.throws(()=>parse('[bridge wake]'),/required/);
 assert.throws(()=>parse('[bridge send]\n\n[/bridge]'),/empty/);
});
