"""Optional pywebview front end to the existing Nomi uploader CLI."""
import json
import re
import os
import runpy
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
UPLOADER = ROOT / "uploader" / "nomi-uploader.py"
INDEX = ROOT / "uploader" / "gui" / "index.html"
DATA = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "NomiUploader"
DATA.mkdir(parents=True, exist_ok=True)
CONFIG = DATA / "settings.json"

class API:
    def __init__(self):
        self.proc = None
        self.lines = []
        self.lock = threading.Lock()
        self.project = {"queue": [], "nomi": "", "process": 5, "reply_wait": 900, "header_every": 0, "header_text": "", "reply_prompt": "", "user_name": ""}
        if CONFIG.exists():
            try: self.project.update(json.loads(CONFIG.read_text(encoding="utf-8")))
            except (OSError, ValueError): pass

    def save(self, project):
        if self.proc and self.proc.poll() is None: raise RuntimeError("Cannot modify a running upload.")
        # The active checkpoint belongs to the backend, not the browser's stale copy.
        active=self.project.get("active_run")
        self.project = dict(project)
        if active is not None:
            self.project["active_run"]=active
        CONFIG.write_text(json.dumps(self.project, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def list_nomis(self, key):
        sys.path.insert(0, str(UPLOADER.parent))
        """Fetch real Nomis using the uploader's own API client; never log the key."""
        from legacy_v085 import get_nomis
        old = os.environ.get("NOMI_API_KEY")
        try:
            os.environ["NOMI_API_KEY"] = str(key).strip()
            if not os.environ["NOMI_API_KEY"]:
                raise ValueError("Enter an API key first.")
            nomis = get_nomis()
            return [{"name": n.get("name", ""), "uuid": n.get("uuid", "")}
                    for n in nomis if n.get("name") and n.get("uuid")]
        finally:
            if old is None: os.environ.pop("NOMI_API_KEY", None)
            else: os.environ["NOMI_API_KEY"] = old

    def room_action(self, action, key, nomi_uuid="", room_uuid="", name="", note=""):
        """Nomi room management; no automatic retries for writes."""
        import uuid
        sys.path.insert(0, str(UPLOADER.parent))
        from legacy_v085 import api_request, list_rooms, get_nomis, room_contains_nomi, ok, err_text
        if self.proc and self.proc.poll() is None and action != "list":
            raise RuntimeError("Room modifications are disabled during an upload.")
        old = os.environ.get("NOMI_API_KEY")
        try:
            os.environ["NOMI_API_KEY"] = str(key).strip()
            if not os.environ["NOMI_API_KEY"]: raise ValueError("Enter an API key.")
            if not nomi_uuid: raise ValueError("Select a Nomi first.")
            uuid.UUID(str(nomi_uuid))
            if action == "list":
                return [{"uuid": str(r.get("uuid","")), "name": r.get("name",""),
                         "note": r.get("note",""), "status": r.get("status","")}
                        for r in list_rooms() if room_contains_nomi(r, nomi_uuid)]
            if action in ("edit", "delete"):
                uuid.UUID(str(room_uuid))
                rooms = list_rooms()
                if not any(str(r.get("uuid"))==room_uuid and room_contains_nomi(r, nomi_uuid) for r in rooms):
                    raise ValueError("Room not found for selected Nomi; refresh the room list.")
            if action == "create":
                if not name.strip() or len(name)>100 or len(note)>1000:
                    raise ValueError("Room name required (max 100 characters), note max 1000 characters.")
                path,method,body = "/rooms","POST",{"name":name.strip(),"note":note,
                    "backchannelingEnabled":True,"nomiUuids":[nomi_uuid]}
            elif action == "edit":
                if not name.strip() or len(name)>100 or len(note)>1000:
                    raise ValueError("Room name required (max 100 characters), note max 1000 characters.")
                path,method,body = "/rooms/"+room_uuid,"PUT",{"name":name.strip(),"note":note}
            elif action == "delete":
                cp=self._active_dir()/"upload.jsonl"
                if cp.exists():
                    events=[]
                    for line in cp.read_text(encoding="utf-8").splitlines():
                        try: events.append(json.loads(line))
                        except ValueError: pass
                    starts=[r for r in events if r.get("event")=="start"]
                    if starts and starts[-1].get("room_uuid")==room_uuid and not (self._active_dir()/"completed.json").exists():
                        raise ValueError("Room belongs to an unfinished checkpoint. Resolve the upload before deleting it.")
                path,method,body = "/rooms/"+room_uuid,"DELETE",None
            else: raise ValueError("Unknown room action")
            status,payload=api_request(path,method,body)
            if not ok(status):
                raise RuntimeError(err_text(action,status,payload)+"; inspect rooms before retrying.")
            return {"ok":True,"room":payload}
        finally:
            if old is None: os.environ.pop("NOMI_API_KEY",None)
            else: os.environ["NOMI_API_KEY"]=old

    def choose(self):
        import webview
        paths = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True,
                         file_types=("Uploader files (*.txt;*.docx;*.json;*.zip)", "All files (*.*)"))
        return list(paths or [])

    def inspect_file(self, filename):
        """Read TXT metadata and a preview without modifying the source file."""
        source = Path(filename)
        if source.suffix.lower() in (".zip", ".json"):
            sys.path.insert(0, str(UPLOADER.parent))
            import legacy_v085 as legacy
            name, rows=legacy.load_conversation(source)
            preview="\n".join(str(x.get("date",""))+" "+str(x.get("sender",""))+": "+str(x.get("message","")) for x in rows[:30])
            return {"editable": False, "export": True, "header": {"mode":"Replace","intro":"[nomi], please live and experience these conversations as yourself.","periodic":"[nomi], please live and experience the conversations {first}-{last} as yourself.","process":""}, "preview": preview[:12000], "existing": False, "count":len(rows), "nomi_name":name}
        if source.suffix.lower() != ".txt":
            return {"editable": False, "preview": "Metadata editor is available for TXT and Nomi ZIP/JSON exports."}
        raw = source.read_text(encoding="utf-8-sig")
        lines = raw.splitlines(keepends=True)
        header_start = next((i for i, line in enumerate(lines) if line.strip()), None)
        if header_start is None:
            return {"editable": True, "header": {"title": source.stem, "type": "Knowledge", "source": "", "date": "", "process": "", "headerEvery": "", "headerText": "", "replyPrompt": "", "mode": "Add", "prompts": ""}, "preview": "", "existing": False}
        existing = bool(re.fullmatch(r"\[[^\]\n]+\]", lines[header_start].strip()))
        header = {"title": source.stem, "type": "Knowledge", "source": "", "date": "", "process": "", "mode": "Add", "prompts": ""}
        content_start = header_start
        if existing:
            header["title"] = lines[header_start].strip()[1:-1]
            content_start = header_start + 1
            prompts = []
            for i in range(content_start, len(lines)):
                m = re.match(r"^(Type|Source|Date|Process Every|Header Every|Header Text|Reply Prompt|Nomi Mode|Nomi):\s*(.*)$", lines[i].strip(), re.I)
                if m:
                    k,v = m.group(1).lower(), m.group(2).strip()
                    key = {"type":"type","source":"source","date":"date","process every":"process","header every":"headerEvery","header text":"headerText","reply prompt":"replyPrompt","nomi mode":"mode","nomi":"prompts"}[k]
                    if key == "prompts": prompts.append(v)
                    else: header[key] = v
                    content_start = i + 1
                elif not lines[i].strip():
                    content_start = i + 1
                else: break
            header["prompts"] = "\n".join(prompts)
        content = "".join(lines[content_start:])
        return {"editable": True, "header": header, "preview": content[:120000], "truncated": len(content)>120000, "existing": existing}

    def _build_txt(self, source, item):
        info = self.inspect_file(str(source))
        if "fields" not in item:
            return source.read_text(encoding="utf-8-sig")
        fields = item["fields"]
        raw = source.read_text(encoding="utf-8-sig")
        if info["existing"]:
            # Remove only the first section's existing metadata. Preserve original source.
            lines = raw.splitlines(keepends=True)
            first = next(i for i, x in enumerate(lines) if x.strip())
            pos = first + 1
            while pos < len(lines):
                line = lines[pos].strip()
                if not line or re.match(r"^(Type|Source|Date|Process Every|Header Every|Header Text|Reply Prompt|Nomi Mode|Nomi):", line, re.I):
                    pos += 1
                else: break
            body = "".join(lines[pos:])
        else:
            body = raw
        title = str(fields.get("title") or source.stem).strip()
        kind = str(fields.get("type") or "Knowledge").strip().lower()
        if kind not in ("knowledge","instructions","journal","chat"):
            raise ValueError("Invalid content Type")
        mode = str(fields.get("mode") or "Add").strip().lower()
        if mode not in ("add","replace"): raise ValueError("Invalid Nomi Mode")
        header = ["[" + title + "]", "Type: " + kind.title()]
        for key, prop in (("Source", "source"), ("Date", "date"), ("Process Every", "process"), ("Header Every", "headerEvery"), ("Header Text", "headerText"), ("Reply Prompt", "replyPrompt")):
            v = str(fields.get(prop) or "").strip()
            if v:
                if prop in ("process","headerEvery") and (not v.isdecimal() or int(v) < 0):
                    raise ValueError("Process Every must be a nonnegative integer")
                header.append(key + ": " + v)
        header.append("Nomi Mode: " + mode.title())
        for prompt in str(fields.get("prompts") or "").splitlines():
            if prompt.strip(): header.append("Nomi: " + prompt.strip())
        return "\n".join(header) + "\n\n" + body

    def _paths(self, run_dir):
        out = []
        for i, item in enumerate(self.project.get("queue", [])):
            source = Path(item["path"])
            if not source.is_file(): raise ValueError("Missing source file: " + str(source))
            suffix = source.suffix.lower()
            if suffix not in (".txt", ".docx", ".json", ".zip"):
                raise ValueError("Unsupported file type: " + str(source))
            if suffix == ".txt" and item.get("fields"):
                generated = run_dir / ("prepared-%04d.txt" % i)
                generated.write_text(self._build_txt(source, item), encoding="utf-8")
                out.append(str(generated))
            elif suffix == ".txt" and item.get("header"):
                generated = run_dir / ("prepared-%04d.txt" % i)
                content = source.read_text(encoding="utf-8-sig")
                if content.lstrip().startswith("["):
                    raise ValueError("File already has structured headers; edit its original header rather than adding a second one: " + str(source))
                generated.write_text(item["header"].strip()+"\n\n"+content, encoding="utf-8")
                out.append(str(generated))
            else:
                out.append(str(source))
        if not out: raise ValueError("Select at least one file.")
        return out

    def _cli(self, args):
        return ([sys.executable, "--uploader-cli"] if FROZEN else [sys.executable, str(UPLOADER)]) + args

    def _run(self, args):
        if self.proc and self.proc.poll() is None: raise RuntimeError("An upload is already running.")
        self.lines = []
        env = os.environ.copy()
        env["NOMI_API_KEY"] = self.project.get("key", "").strip() or env.get("NOMI_API_KEY", "")
        if not env["NOMI_API_KEY"] and "--dry-run" not in args and "--status" not in args:
            raise ValueError("Enter your Nomi API key in Settings.")
        env["NOMI_GUI_TARGET_NOMI"] = self.project.get("nomi","")
        env["NOMI_GUI_TARGET_UUID"] = self.project.get("nomi_uuid","")
        self.proc = subprocess.Popen(self._cli(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=str(DATA),
                     env={**env, "PYTHONUNBUFFERED":"1"}, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        def reader():
            for line in self.proc.stdout:
                with self.lock: self.lines.append(line.rstrip())
        threading.Thread(target=reader, daemon=True).start()
        return True

    def _active_dir(self):
        token=self.project.get("active_run")
        if not token:
            return DATA  # Preserve access to pre-upgrade checkpoints.
        if not re.fullmatch(r"[0-9a-f]{32}",str(token)):
            raise ValueError("Invalid run identifier")
        return DATA / "runs" / token

    def _has_checkpoint(self, directory):
        cp=directory / "upload.jsonl"
        return cp.is_file() and cp.stat().st_size>0

    def begin(self, dry=False):
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("Upload already running")
        token=uuid.uuid4().hex
        directory=DATA / ("previews" if dry else "runs") / token
        directory.mkdir(parents=True,exist_ok=False)
        paths = self._paths(directory)
        # Persist an exact input manifest for inspection and incident recovery.
        manifest={"source_files":[x.get("path") for x in self.project.get("queue",[])],
                  "processed_files":paths,"nomi_uuid":self.project.get("nomi_uuid"),
                  "room_uuid":self.project.get("room_uuid")}
        (directory/"gui-input-manifest.json").write_text(
            json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        args = ([] if not dry else ["--dry-run", "--nomi", self.project.get("nomi") or "Nomi"])
        needs_name=any("__USER_NAME__" in Path(p).read_text(encoding="utf-8-sig")
                       for p in paths if Path(p).suffix.lower()==".txt")
        user_name=str(self.project.get("user_name") or "").strip()
        if needs_name and not user_name:
            raise ValueError("Enter your Nomi.ai user name before uploading this file.")
        if user_name:
            if any(c in user_name for c in "\r\n[]"):
                raise ValueError("Invalid Nomi.ai user name.")
            args += ["--user", user_name]
        if not dry:
            room = str(self.project.get("room_uuid") or "").strip()
            if not room: raise ValueError("Select or create an upload room first.")
            if not self.project.get("nomi_uuid"): raise ValueError("Load Nomis and choose a Nomi from the list before uploading.")
            args += ["--room", room, "--nomi-uuid", str(self.project["nomi_uuid"])]
        if any(Path(x["path"]).suffix.lower() in (".zip",".json") and x.get("export_fields") for x in self.project.get("queue",[])):
            settings={x["path"]: {"mode":x["export_fields"].get("mode","Replace"),
                                 "intro":x["export_fields"].get("intro",""),
                                 "periodic":x["export_fields"].get("periodic",""),
                                 "process_every":x["export_fields"].get("process",""),
                                 "header_every":x["export_fields"].get("headerEvery",""),
                                 "header_text":x["export_fields"].get("headerText",None)}
                      for x in self.project["queue"] if x.get("export_fields") and Path(x["path"]).suffix.lower() in (".zip",".json")}
            opts=directory/"export-options.json"
            opts.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding="utf-8")
            args += ["--export-options",str(opts)]
        args += ["--header-every",str(int(self.project.get("header_every",0))),
                 "--header-text",str(self.project.get("header_text","")),
                 "--reply-prompt",str(self.project.get("reply_prompt",""))]
        args += ["--process-every", str(int(self.project.get("process", 5))),
                 "--reply-max-wait", str(float(self.project.get("reply_wait", 900)))]
        args += ["--checkpoint", str(directory / "upload.jsonl"),
                 "--completion", str(directory / "completed.json"),
                 "--replies", str(directory / "replies.txt")]
        args += paths
        if not dry:
            prior=self.project.get("active_run")
            self.project["active_run"]=token
            self.save(self.project)
            try:
                return self._run(args)
            except Exception:
                self.project["active_run"]=prior
                self.save(self.project)
                raise
        return self._run(args)

    def pause(self):
        if not self.proc or self.proc.poll() is not None:
            raise RuntimeError("No running upload to pause.")
        marker=Path(str(self._active_dir()/"upload.jsonl")+".pause")
        marker.write_text("pause",encoding="utf-8")
        return "Pause requested; completing the current API operation."

    def clear_history(self):
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("Cannot clear history while an upload is running.")
        # Hide completed run history; never delete checkpoints or source data.
        found=self.list_runs()
        ids=[r["id"] for r in found if r["completed"]]
        hidden=set(self.project.get("hidden_run_ids",[]))
        hidden.update(ids)
        self.project["hidden_run_ids"]=sorted(hidden)
        CONFIG.write_text(json.dumps(self.project,ensure_ascii=False,indent=2),encoding="utf-8")
        return len(ids)

    def list_runs(self):
        """Read-only history; legacy alpha checkpoint remains selectable."""
        found=[]
        roots=[("legacy",DATA)]
        runs=DATA/"runs"
        if runs.exists():
            roots.extend((p.name,p) for p in runs.iterdir() if p.is_dir() and re.fullmatch(r"[0-9a-f]{32}",p.name))
        for token,directory in roots:
            cp=directory/"upload.jsonl"
            if not cp.exists() or not cp.stat().st_size: continue
            start=None
            for line in cp.read_text(encoding="utf-8").splitlines():
                try: row=json.loads(line)
                except ValueError: continue
                if row.get("event")=="start": start=row; break
            found.append({"id":token,"nomi":start.get("nomi_name","Unknown") if start else "Not started",
                "room":start.get("room_uuid","") if start else "",
                "completed":(directory/"completed.json").exists(),
                "modified":cp.stat().st_mtime})
        hidden=set(self.project.get("hidden_run_ids",[]))
        return sorted((r for r in found if r["id"] not in hidden),key=lambda r:r["modified"],reverse=True)

    def select_run(self, run_id):
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("Cannot switch runs during upload.")
        directory=DATA if run_id=="legacy" else DATA/"runs"/str(run_id)
        if run_id!="legacy" and not re.fullmatch(r"[0-9a-f]{32}",str(run_id)):
            raise ValueError("Invalid run ID")
        if not self._has_checkpoint(directory): raise ValueError("Run has no checkpoint")
        self.project["active_run"]=None if run_id=="legacy" else run_id
        self.save(self.project)
        self.lines=[]
        self.proc=None
        return True

    def resume(self):
        directory=self._active_dir()
        if not self._has_checkpoint(directory):
            raise ValueError("No checkpoint exists for the selected run.")
        Path(str(directory/"upload.jsonl")+".pause").unlink(missing_ok=True)
        return self._run(["--resume","--checkpoint",str(directory/"upload.jsonl"),
                          "--completion",str(directory/"completed.json"),
                          "--replies",str(directory/"replies.txt")])

    def status(self):
        directory=self._active_dir()
        cp = directory / "upload.jsonl"
        confirmed = 0
        total = 0
        replies = []
        recent = []
        if cp.exists():
            for raw in cp.read_text(encoding="utf-8").splitlines():
                try: row = json.loads(raw)
                except ValueError: continue
                if row.get("event") == "start":
                    total = int(row.get("messages_per_pass",0)) * int(row.get("passes",1))
                if row.get("event") == "confirmed": confirmed += 1
                if row.get("event") == "reply_committed":
                    replies.append({"prompt":row.get("prompt",""),"reply":row.get("reply",{}).get("messageText","")})
        with self.lock: recent = self.lines[-250:]
        running = bool(self.proc and self.proc.poll() is None)
        return {"running":running,"exit_code":None if running or not self.proc else self.proc.returncode,
                "confirmed":confirmed,"total":total,"log":recent,"replies":replies[-50:],
                "project":self.project,"can_resume":self._has_checkpoint(directory),
                "completed":(directory/"completed.json").exists()}

if __name__ == "__main__":
    if "--uploader-cli" in sys.argv:
        at = sys.argv.index("--uploader-cli")
        sys.argv = [str(UPLOADER)] + sys.argv[at+1:]
        sys.path.insert(0, str(UPLOADER.parent))
        import builtins
        import legacy_v085
        # GUI uploads select the Nomi through --nomi-uuid in the uploader.
        # Never silently fall back to name matching (Beth and beth can coexist).
        def gui_input(prompt=""):
            raise RuntimeError("Unexpected interactive uploader prompt: "+str(prompt)+
                               " (GUI must supply the required arguments).")
        builtins.input = gui_input
        runpy.run_path(str(UPLOADER), run_name="__main__")
    else:
        import webview
        api = API()
        webview.create_window("Nomi Uploader", INDEX.as_uri(), js_api=api, width=1150, height=830)
        webview.start(gui="qt" if sys.platform.startswith("linux") else None)
