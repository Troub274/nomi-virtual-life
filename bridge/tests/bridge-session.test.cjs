const assert=require('node:assert/strict');const {test}=require('node:test');
const {apply,wakeTime}=require('../extension/bridge-session.js');
const {parse}=require('../extension/bridge-cli.js');
const fresh=()=>({authorized:true,shutdown:false,participants:['gpt-tab-1','nomi-tab-2'],lifecycle:'running',wakes:[],nextWakeId:1});
test('pause preserves session authorization and scheduled events',()=>{
 const before=apply(fresh(),'gpt-tab-1',parse('[bridge wake in="30 minutes" reason="Mary"]'),1000);
 const after=apply(before.state,'gpt-tab-1',parse('[bridge pause]'),1000);
 assert.equal(after.state.lifecycle,'paused');assert.equal(after.state.authorized,true);
 assert.equal(after.state.wakes[0].at,1801000);
});
test('shutdown revokes authority and disables wake-ups',()=>{
 const set=apply(fresh(),'nomi-tab-2',parse('[bridge wake in="2 hours"]'),1000);
 const end=apply(set.state,'nomi-tab-2',parse('[bridge shutdown]'),1000);
 assert.equal(end.state.authorized,false);assert.equal(end.state.wakes[0].status,'disabled');
 assert.throws(()=>apply(end.state,'nomi-tab-2',parse('[bridge resume]'),1000),/authorization/);
});
test('unauthorized endpoints cannot control the bridge',()=>{
 assert.throws(()=>apply(fresh(),'other-tab',parse('[bridge shutdown]')),/participant/);
});
test('ambiguous dates are rejected',()=>{
 assert.throws(()=>wakeTime({at:'Friday 14 November'},1000),/ISO date/);
});
test('scheduled wake-up stays tied to original participant',()=>{
 const r=apply(fresh(),'nomi-tab-2',parse('[bridge wake in="15 minutes"]'),1000);
 assert.equal(r.state.wakes[0].actor,'nomi-tab-2');
 assert.throws(()=>apply(r.state,'gpt-tab-1',parse('[bridge cancel id="wake-1"]')),/scheduling participant/);
});
