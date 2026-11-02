/* AI Bridge 1.0 command grammar. Pure parser; no browser side effects.
 * Accept commands only from a trusted adapter's NEW assistant message.
 * Never parse forwarded text, historical transcripts or human inputs.
 */
(function(root) {
  const SINGLE = new Set(['help','status','pause','resume','listen','shutdown','pending','review','retry','wake','schedule','cancel']);
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
    const block=s.match(/^\[bridge send(?:\s+([^\]\r\n]*))?\]\s*\n([\s\S]*?)\n\[\/bridge\]$/i);
    if(block) {
      const {args,rest}=argsOf(block[1]||'');
      if(rest) throw Error('Unrecognized send arguments: '+rest);
      if(!block[2].trim()) throw Error('Message is empty');
      if(block[2].length>12000) throw Error('Message exceeds limit');
      return {command:'send',args,message:block[2],requiresAuthorization:true};
    }
    const match=s.match(/^\[bridge\s+([a-z]+)(?:\s+([^\]\r\n]*))?\]$/i);
    if(!match)return null;
    const command=match[1].toLowerCase();
    if(!SINGLE.has(command))throw Error('Unknown bridge command: '+command);
    const {args,rest}=argsOf(match[2]||'');
    if(command==='wake'){
      if(rest && !/^(?:in|at)\s+.+$/i.test(rest))throw Error('Use wake at="time" or wake in="duration"');
      if(!args.at&&!args.in&&!rest)throw Error('Wake time required');
    }else if(command==='help') {
      if(rest)throw Error('Use help topic="schedule"');
    } else if(rest && !((command==='review'&&/^\d+$/.test(rest))||(command==='retry'&&/^\S+$/.test(rest))||(command==='cancel'&&/^\S+$/.test(rest)))) {
      throw Error('Unexpected CLI arguments');
    }
    return {command,args,rest,requiresAuthorization:true,highImpact:DANGEROUS.has(command)};
  }
  const HELP=[
    "AI Bridge CLI — one command per reply; no surrounding prose.",
    "SEND MESSAGE TO OTHER SELECTED TAB:",
    "[bridge send to=\"ChatGPT\"]",
    "Your message to ChatGPT",
    "[/bridge]",
    "Or, when the other tab is Nomi:",
    "[bridge send to=\"Nomi\"]",
    "Your message to Nomi",
    "[/bridge]",
    "The send block must be the ENTIRE reply. Text outside it is not sent.",
    "Ordinary conversation is NOT an explicit send.",
    "OTHER COMMANDS (each alone on one line):",
    "[bridge help]",
    "[bridge status]",
    "[bridge pending]",
    "[bridge pause]",
    "[bridge resume]",
    "[bridge listen]",
    "[bridge review last=10]",
    "[bridge shutdown]",
    "NOT YET ACTIVE: [bridge wake], [bridge schedule], [bridge cancel], [bridge retry].",
    "Each command must be the whole AI reply; never embed it in other text."
  ].join('\n');
  const api={parse,HELP};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.AIBridgeCLI=api;
})(globalThis);
