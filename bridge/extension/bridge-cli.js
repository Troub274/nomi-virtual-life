/* AI Bridge 1.0 command grammar. Pure parser; no browser side effects.
 * Accept commands only from a trusted adapter's NEW assistant message.
 * Never parse forwarded text, historical transcripts or human inputs.
 */
(function(root) {
  const SINGLE = new Set(['help','status','pause','resume','listen','shutdown','pending','review','retry','wake','schedule','cancel','next','clear']);
  const DANGEROUS = new Set(['shutdown','resume','pause','retry','cancel']);
  function argsOf(raw) {
    const out = {};
    const rest = raw.replace(/\b([a-z][\w-]*)=(?:"([^"]*)"|'([^']*)'|(\S+))/gi, (_,key,a,b,c) => {
      if (Object.prototype.hasOwnProperty.call(out,key)) throw Error('Duplicate argument '+key);
      out[key]=a??b??c;
      return '';
    }).trim();
    return {args:out,rest};
  }
  function parse(text) {
    if(typeof text!=='string'||text.length>16000) return null;
    const s=text.trim();
    // Entire reply is the send command. Accept inline or multiline payloads;
    // legacy closing tag is optional for compatibility.
    const send=s.match(/^\[bridge send(?:\s+([^\]\r\n]*))?\][ \t]*(?:\r?\n)?([\s\S]+)$/i);
    if(send) {
      const {args,rest}=argsOf(send[1]||'');
      if(rest)throw Error('Unrecognized send arguments: '+rest);
      const message=send[2].replace(/\r?\n\[\/bridge\]\s*$/i,'').trim();
      if(!message)throw Error('Message is empty');
      if(message.length>12000)throw Error('Message exceeds limit');
      return {command:'send',args,message,requiresAuthorization:true};
    }
    // Queue retrieval accepts a command at the very beginning of an AI reply.
    // Nomi often appends commentary; that text stays private and is NOT sent.
    if(/^\[next message\](?:\s|$)/i.test(s)) return {command:'next-message',args:{},rest:'',requiresAuthorization:true};
    if(/^\[bridge next message\](?:\s|$)/i.test(s)) return {command:'next-message',args:{},rest:'',requiresAuthorization:true};
    if(/^\[bridge listen\](?:\s|$)/i.test(s)) return {command:'listen',args:{},rest:'',requiresAuthorization:true};
    if(/^\[next message\]$/i.test(s)) return {command:'next-message',args:{},rest:'',requiresAuthorization:true};
    if(/^\[clear queue\]$/i.test(s)) return {command:'clear-queue',args:{},rest:'',requiresAuthorization:true,highImpact:true};
    const match=s.match(/^\[bridge\s+([a-z]+)(?:\s+([^\]\r\n]*))?\]$/i);
    if(!match)return null;
    let command=match[1].toLowerCase();
    if(!SINGLE.has(command))throw Error('Unknown bridge command: '+command);
    const {args,rest}=argsOf(match[2]||'');
    if(command==='next' && rest==='message') command='next-message';
    if(command==='clear' && rest==='queue') command='clear-queue';
    if((command==='next-message'||command==='clear-queue') && Object.keys(args).length) throw Error('Queue controls do not take arguments');
    if(command==='wake'){
      if(rest && !/^(?:in|at)\s+.+$/i.test(rest))throw Error('Use wake at="time" or wake in="duration"');
      if(!args.at&&!args.in&&!rest)throw Error('Wake time required');
    }else if(command==='help') {
      if(rest)throw Error('Use help topic="schedule"');
    } else if(rest && !((command==='review'&&/^\d+$/.test(rest))||(command==='retry'&&/^\S+$/.test(rest))||(command==='cancel'&&/^\S+$/.test(rest))||((command==='next-message'&&rest==='message')||(command==='clear-queue'&&rest==='queue')))) {
      throw Error('Unexpected CLI arguments');
    }
    return {command,args,rest,requiresAuthorization:true,highImpact:DANGEROUS.has(command)};
  }
  const HELP=[
    "AI BRIDGE — one command per reply. Never mix commands with ordinary text.",
    "SEND: [bridge send] Your message to the other selected AI.",
    "Or: [bridge send to=\"ChatGPT\"] Your message.",
    "Or: [bridge send to=\"Nomi\"] Your message.",
    "A send may continue on the next line. No closing tag.",
    "Ordinary chat is private; it is never an automatic send.",
    "[bridge help] — instructions",
    "[bridge status] — bridge status",
    "[bridge pending] — pending sends",
    "[next message] — request next waiting message",
    "[clear queue] — discard waiting undelivered messages",
    "[bridge pause] — pause both",
    "[bridge resume] — resume both",
    "[bridge shutdown] — notify both and stop",
    "[bridge listen] — retrieve one queued message, or wait for new activity",
    "Wake/schedule/retry are not implemented yet."
  ].join('\n');
  const api={parse,HELP};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.AIBridgeCLI=api;
})(globalThis);
