"""Exercise the shipped JavaScript recovery and prompt controls."""
from pathlib import Path
import shutil
import subprocess
import unittest


class GuiControlTests(unittest.TestCase):
    def test_loading_headers_preserves_file_metadata_and_saved_project_edits(self):
        node=shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable")
        html=Path(__file__).resolve().parents[1]/"gui/index.html"
        script=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[2],'utf8');
const source=html.slice(html.indexOf('async function loadSelected(){'),html.indexOf('let previewToken='));
(async()=>{
 const fileHeader={type:'Chat',headerPrompt:'Opening from header',replyPrompt:'Reply from header',process:0,headerEvery:0,date:'2026-11-21',source:'Ava'};
 for(const fields of [undefined,{title:'chat',type:'Knowledge',mode:'Add',source:'',date:'',process:'',prompts:''},
                      {...fileHeader,headerPrompt:'Saved project opening'}]){
  const item={path:'chat.txt',fields};
  const context={active:0,selectionToken:0,project:{queue:[item]},
   call:async()=>({header:fileHeader}),scheduleProjectSave:()=>{},renderFileFields:()=>{},refreshSample:async()=>{},el:()=>({})};
  vm.createContext(context);vm.runInContext(source,context);await context.loadSelected();
  assert.equal(item.fields.type,'Chat');assert.equal(item.fields.process,0);
  assert.equal(item.fields.headerPrompt,fields?.headerPrompt||'Opening from header');
 }
})().catch(e=>{console.error(e);process.exit(1)});
"""
        result=subprocess.run([node,"-",str(html)],input=script,text=True,encoding="utf-8",capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_restart_validation_and_reply_destination(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable")
        html = Path(__file__).resolve().parents[1] / "gui/index.html"
        script = r"""
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const html = fs.readFileSync(process.argv[2], "utf8");
const manual = html.match(/async function manualRestart\(\)\{[\s\S]*?\n\}/)[0];
(async () => {
  for (const values of [["1","1"],[" 1 "," 1 "],["0","1"],["1.5","1"]]) {
    const input = [...values], calls = [];
    const context = {confirm:()=>true, prompt:()=>input.shift(), alert:()=>{},
      editSettings:()=>{}, save:async()=>{}, el:()=>({}), call:async(...args)=>calls.push(args)};
    vm.createContext(context);
    vm.runInContext(manual, context);
    await context.manualRestart();
    if (values[0].trim() === "1") assert.deepStrictEqual(calls, [["manual_restart",1,1]]);
    else assert.equal(calls.length,0);
  }
  const inputs = {};
  const settings = {project:{queue:[]},active:-1,nomiChoices:[],
    renderNomis:()=>{},renderRooms:()=>{},renderFileFields:()=>{},scheduleProjectSave:()=>{},loadRooms:()=>{},
    el:id=>{
      if(!inputs[id]) {
        const input={style:{}};
        Object.defineProperty(input,"value",{
          get(){return this._value??""},set(value){this._value=String(value)}
        });
        inputs[id]=input;
      }
      return inputs[id];
    }};
  vm.createContext(settings);
  vm.runInContext(html.match(/function draw\(\)\{[\s\S]*?\n\}/)[0]+"\n"+
    html.match(/function editSettings\(\)\{[\s\S]*?\n\}/)[0],settings);
  settings.draw();
  assert.equal(inputs.replyDestination.value,"room");
  inputs.replyDestination.value="private";
  settings.editSettings();
  assert.equal(settings.project.reply_destination,"private");
  settings.draw();
  assert.equal(inputs.replyDestination.value,"private");
})().catch(error=>{console.error(error);process.exit(1)});
"""
        result = subprocess.run([node, "-", str(html)], input=script, text=True,
                                encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


    def test_status_timer_never_overlaps_pending_poll_and_recovers_after_error(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable")
        html = Path(__file__).resolve().parents[1] / "gui/index.html"
        script = r"""
const fs=require("fs"),vm=require("vm"),assert=require("assert");
const html=fs.readFileSync(process.argv[2],"utf8");
const source=html.slice(html.indexOf("async function poll()"),html.indexOf("async function changeApiKey()"));
(async()=>{
 const controls={},calls=[];
 let finish;
 const pending=new Promise(resolve=>finish=resolve);
 const recovery={state:"COMPLETE"};
 const status={total:31000,confirmed:31000,running:false,exit_code:0,replies:[],log:[]};
 const context={ready:true,activityLines:[],el:id=>(controls[id]??={}),
  renderRecoveryOptions:()=>{},renderActivity:()=>{},
  call:async name=>{calls.push(name);return name==="recovery_status"?pending:status;}};
 vm.createContext(context);
 vm.runInContext("let polling=false;"+source,context);
 const first=context.poll();
 const extra=Array.from({length:1000},()=>context.poll());
 assert.deepStrictEqual(calls,["recovery_status"]);
 finish(recovery);
 await Promise.all([first,...extra]);
 assert.deepStrictEqual(calls,["recovery_status","status"]);
 context.call=async name=>{calls.push(name);return name==="recovery_status"?recovery:status;};
 await context.poll();
 assert.equal(calls.length,4);
 context.call=async()=>{throw Error("temporary failure")};
 await context.poll();
 assert(controls.state.textContent.includes("temporary failure"));
 context.call=async name=>name==="recovery_status"?recovery:status;
 await context.poll();
 assert.equal(controls.state.textContent,"Uploader exited with code 0");
})().catch(error=>{console.error(error);process.exit(1)});
"""
        result = subprocess.run([node, "-", str(html)], input=script, text=True,
                                encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


    def test_file_prompt_fields_edit_all_formats_and_load_type_defaults(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable")
        html = Path(__file__).resolve().parents[1] / "gui/index.html"
        script = r"""
const fs=require("fs"),vm=require("vm"),assert=require("assert");
const html=fs.readFileSync(process.argv[2],"utf8");
assert.equal((html.match(/id="processField"/g)||[]).length,1);
assert(!html.includes('id="exportProcess"'));
const source=html.slice(html.indexOf("function filePromptKey("),html.indexOf("function scheduleProjectSave("))+
 html.slice(html.indexOf("function renderFileFields("),html.indexOf("function scheduleSample("));
const controls={};let saves=0,previews=0;
const fields={type:"Chat",source:"",date:"2026-11-21",headerPrompt:"Opening",replyPrompt:"Reply",headerEvery:0,process:10};
const model={nomi:"Ava",queue:[{path:"chat.json",fields},{path:"facts.docx",fields:{...fields,type:"Knowledge",process:0}}]};
const context={active:0,project:model,scheduleProjectSave:()=>saves++,scheduleSample:()=>previews++,
 defaultPromptTable:{opening:{journal_self:"Journal header"},periodic:{journal_self:"Journal reply"}},
 el:id=>(controls[id]??={value:"",textContent:"",disabled:false})};
vm.createContext(context);vm.runInContext(source,context);
context.renderFileFields();
assert.equal(controls.processField.value,10);
assert.equal(controls.headerEveryField.value,0);
controls.typeField.value="Journal";context.changeFileType();
assert.equal(fields.type,"Journal");assert.equal(fields.headerPrompt,"Journal header");assert.equal(fields.replyPrompt,"Journal reply");
controls.headerPromptField.value="Custom header\nSecond line";
controls.replyPromptField.value="Custom reply";controls.processField.value="0";
context.updateFields();
assert.equal(fields.headerPrompt,"Custom header\nSecond line");assert.equal(fields.replyPrompt,"Custom reply");assert.equal(fields.process,"0");
assert.equal(saves,2);assert.equal(previews,2);
context.active=1;context.renderFileFields();
assert.equal(controls.processField.value,0);assert(!controls.headerPromptField.disabled);
assert(/id="headerEveryField" type="number" min="0" max="1000"/.test(html));
assert(/id="processField" type="number" min="0" max="1000"/.test(html));

"""
        result = subprocess.run([node, "-", str(html)], input=script, text=True,
                                encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
