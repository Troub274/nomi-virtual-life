/* AI Bridge 1.0 — session-side CLI policy and durable wake records.
 * Storage and DOM transport are supplied by the existing Edge controller.
 * No commands run unless an established, human-authorized session is passed in.
 */
(function(root) {
  const scheduleHelp='wake at="2026-11-03T15:10:00-05:00" or wake in="30 minutes"; use schedule to list and cancel id="..."';
  function duration(text) {
    const m=String(text||'').trim().match(/^(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)$/i);
    if(!m)throw Error('Use a duration such as "30 minutes"');
    const unit=m[2].toLowerCase();
    const ms=Number(m[1])*(unit.startsWith('sec')?1000:unit.startsWith('min')?60000:unit.startsWith('h')?3600000:86400000);
    if(!Number.isFinite(ms)||ms<1000||ms>30*86400000)throw Error('Wake duration must be between 1 second and 30 days');
    return ms;
  }
  function wakeTime(args,now) {
    if(!!args.at===!!args.in)throw Error('Specify exactly one of at= or in=');
    if(args.in)return now+duration(args.in);
    // Avoid silently interpreting ambiguous dates such as "Friday 14 November".
    if(!/^\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?(?:Z|[+-]\d\d:\d\d)$/.test(args.at))
      throw Error('Use an ISO date and timezone offset for now. '+scheduleHelp);
    const ms=Date.parse(args.at);
    if(!Number.isFinite(ms)||new Date(ms).toISOString().startsWith('NaN')||ms<=now||ms>now+30*86400000)
      throw Error('Wake time must be in the next 30 days');
    return ms;
  }
  function apply(state,actor,parsed,now=Date.now()){
    if(!state?.authorized||state.shutdown)throw Error('Human authorization required');
    if(!state.participants?.includes(String(actor)))throw Error('Not an authorized session participant');
    const command=parsed?.command;
    if(!command)throw Error('No command');
    const s={...state,events:[...(state.events||[])],wakes:[...(state.wakes||[])]};
    const response={command,ok:true};
    switch(command){
      case 'help':response.text=root.AIBridgeCLI?.HELP||'Use [bridge help] to view the CLI';break;
      case 'status':response.text=JSON.stringify({lifecycle:s.lifecycle||'running',pending:s.pending?.length||0,nextWake:s.wakes.filter(w=>w.status==='armed').sort((a,b)=>a.at-b.at)[0]?.at||null});break;
      case 'pause':s.lifecycle='paused';response.text='Paused. CLI and scheduled wake-ups remain active.';break;
      case 'listen':s.lifecycle='listening';response.text='Listening. Authorized control remains active.';break;
      case 'resume':s.lifecycle='running';response.text='Resumed.';break;
      case 'shutdown':s.shutdown=true;s.authorized=false;s.lifecycle='shutdown';s.wakes=s.wakes.map(w=>({...w,status:'disabled'}));response.text='Shutdown. Human reauthorization required.';break;
      case 'wake':{
        const at=wakeTime(parsed.args||{},now),id='wake-'+(s.nextWakeId||1);
        s.nextWakeId=(s.nextWakeId||1)+1;
        s.wakes.push({id,at,actor:String(actor),reason:parsed.args.reason||'',status:'armed'});
        response.id=id;response.at=new Date(at).toISOString();break;
      }
      case 'schedule':response.events=s.wakes.filter(w=>w.status==='armed');break;
      case 'cancel':{
        const id=parsed.args?.id||parsed.rest;
        const found=s.wakes.find(w=>w.id===id&&w.status==='armed');
        if(!found)throw Error('Scheduled event not found');
        if(found.actor!==String(actor))throw Error('Only the scheduling participant or human may cancel');
        found.status='cancelled';response.id=id;break;
      }
      case 'pending':response.messages=s.pending||[];break;
      default:throw Error('Command not yet implemented by controller: '+command);
    }
    s.events.push({at:now,actor:String(actor),command});
    s.events=s.events.slice(-100);
    return {state:s,response};
  }
  const api={apply,wakeTime,duration};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.AIBridgeSession=api;
})(globalThis);
