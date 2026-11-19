"""Exercise the shipped JavaScript recovery and prompt controls."""
from pathlib import Path
import shutil
import subprocess
import unittest


class GuiControlTests(unittest.TestCase):
    def test_restart_validation_and_effective_interval(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable")
        html = Path(__file__).resolve().parents[1] / "gui/index.html"
        script = r"""
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const html = fs.readFileSync(process.argv[2], "utf8");
const manual = html.match(/async function manualRestart\(\)\{[\s\S]*?\n\}/)[0];
const display = html.match(/function showPromptDefaults\(error\)\{[\s\S]*?\n\}/)[0];
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
  const controls = {};
  const context = {el:id=>(controls[id]??={}), active:0,
    project:{process:10,reply_prompt:"",queue:[{path:"conversations.json",
      export_fields:{mode:"Replace",intro:"Opening from file",periodic:"Reflect from file",process:""}}]},
    defaultPromptTable:{opening:{chat:"Default opening"},periodic:{chat:"Default reflection"}}};
  vm.createContext(context);
  vm.runInContext(display, context);
  context.showPromptDefaults();
  assert(controls.promptDefaults.textContent.includes("10 content chunks (from Settings)"));
  assert(controls.promptDefaults.textContent.includes("Reflect from file"));
  context.project.queue[0].export_fields.process = "20";
  context.showPromptDefaults();
  assert(controls.promptDefaults.textContent.includes("20 content chunks (file setting)"));
  context.project.queue[0].export_fields.process = "0";
  context.showPromptDefaults();
  assert(controls.promptDefaults.textContent.includes("Periodic reflections disabled"));
  context.defaultPromptTable = null;
  context.showPromptDefaults("Failed");
  assert(controls.promptDefaults.textContent.includes("Could not load prompt defaults"));
  const inputs = {};
  const settings = {project:{queue:[]},active:-1,nomiChoices:[],
    renderNomis:()=>{},renderRooms:()=>{},showPromptDefaults:()=>{},loadRooms:()=>{},
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
