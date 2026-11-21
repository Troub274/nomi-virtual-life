"""Nomi Uploader v1.3 desktop controller.

The pywebview JavaScript interface delegates upload planning and recovery to
nomi-uploader.py. GUI settings and run selection are persisted separately
from the append-only checkpoint journal; do not edit checkpoint events here.
The API credential is shared with the CLI via legacy_v085 credential helpers.
"""
import json
import re
import os
import runpy
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

GUI_VERSION = "1.4i.6"
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
        self.lines = deque(maxlen=1000)
        self.lock = threading.Lock()
        self._checkpoint_lock = threading.Lock()
        self._checkpoint_cache = None
        self._checkpoint_module = None
        self.project = {"queue": [], "nomi": "", "process": 5, "reply_wait": 900, "header_every": 0, "header_text": "", "reply_prompt": "", "reply_destination": "room", "user_name": ""}
        if CONFIG.exists():
            try: self.project.update(json.loads(CONFIG.read_text(encoding="utf-8")))
            except (OSError, ValueError): pass
        sys.path.insert(0,str(UPLOADER.parent))
        import legacy_v085
        old_key=self.project.pop("key",None)
        if old_key and not legacy_v085.credential_status()["configured"]:
            legacy_v085.save_api_key(old_key)
        if old_key:
            CONFIG.write_text(json.dumps(self.project,ensure_ascii=False,indent=2),encoding="utf-8")

    def save(self, project):
        """Persist GUI project settings without overwriting active run identity."""
        if self.proc and self.proc.poll() is None: raise RuntimeError("Cannot modify a running upload.")
        # The active checkpoint belongs to the backend, not the browser's stale copy.
        active=self.project.get("active_run")
        self.project = dict(project)
        self.project.pop("key",None)
        if active is not None:
            self.project["active_run"]=active
        CONFIG.write_text(json.dumps(self.project, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def auth_status(self):
        """Read shared credential configuration status."""
        import legacy_v085
        return legacy_v085.credential_status()

    def auth_unlock(self, password=None):
        """Unlock the configured API key for this GUI process."""
        import legacy_v085
        legacy_v085.unlock_api_key(password)
        return True

    def auth_save(self, key, encrypt=False, password=None):
        """Store a new API key and remove any legacy GUI key copy."""
        import legacy_v085
        legacy_v085.save_api_key(key,password if encrypt else None)
        self.project.pop("key",None)
        CONFIG.write_text(json.dumps(self.project,ensure_ascii=False,indent=2),encoding="utf-8")
        return True

    def list_nomis(self, key):
        """Fetch Nomis through the shared API client without logging the key."""
        sys.path.insert(0, str(UPLOADER.parent))
        import legacy_v085
        from legacy_v085 import get_nomis
        old = os.environ.get("NOMI_API_KEY")
        try:
            os.environ["NOMI_API_KEY"] = str(key or legacy_v085.resolved_api_key() or "").strip()
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
        import legacy_v085
        from legacy_v085 import api_request, list_rooms, get_nomis, room_contains_nomi, ok, err_text
        if self.proc and self.proc.poll() is None and action != "list":
            raise RuntimeError("Room modifications are disabled during an upload.")
        old = os.environ.get("NOMI_API_KEY")
        try:
            os.environ["NOMI_API_KEY"] = str(key or legacy_v085.resolved_api_key() or "").strip()
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
        """Open a file chooser to add source material to the queue."""
        import webview
        dialog = webview.FileDialog.OPEN if hasattr(webview, "FileDialog") else webview.OPEN_DIALOG
        paths = webview.windows[0].create_file_dialog(dialog, allow_multiple=True,
                         file_types=("Uploader files (*.txt;*.docx;*.json;*.zip)", "All files (*.*)"))
        return list(paths or [])

    def read_help(self, guide):
        """Read a bundled guide by name from the source or packaged application."""
        filename = {"uploader": "README.md", "recovery": "RECOVERY.md"}.get(guide)
        if filename is None:
            return {"error": "Unknown help guide."}
        try:
            return {"text": UPLOADER.with_name(filename).read_text(encoding="utf-8")}
        except OSError as exc:
            return {"error": str(exc)}

    def app_version(self):
        return GUI_VERSION

    def check_updates(self):
        """Fetch public release metadata outside the local-file webview."""
        from legacy_v085 import api_ssl_context

        request = urllib.request.Request(
            "https://api.github.com/repos/Troub274/nomi-virtual-life/releases?per_page=20",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "NomiUploader"})
        try:
            context = api_ssl_context()
            with urllib.request.urlopen(request, timeout=10, context=context) as response:
                return {"releases": json.load(response)}
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                return self._public_release_fallback(context)
            return {"error": str(exc)}
        except (OSError, ValueError, RuntimeError) as exc:
            return {"error": str(exc)}

    @staticmethod
    def _public_release_fallback(context):
        base = "https://github.com/Troub274/nomi-virtual-life/releases/"
        try:
            with urllib.request.urlopen(base + "latest", timeout=10, context=context) as response:
                url = response.geturl()
            match = re.fullmatch(re.escape(base) + r"tag/(nomi-uploader-v[0-9][A-Za-z0-9.-]*)", url)
            if match:
                return {"releases": [{"tag_name": match[1], "html_url": url, "draft": False}]}
        except (OSError, ValueError):
            pass
        return {"error": "GitHub is limiting update checks. Open the releases page to check manually."}

    def prompt_defaults(self):
        """Return the same personalized templates that the CLI uses."""
        sys.path.insert(0, str(UPLOADER.parent))
        try:
            return runpy.run_path(str(UPLOADER))["load_prompt_table"](DATA)
        finally:
            sys.path.pop(0)

    def save_prompt_defaults(self, table=None, reset=False):
        """Persist editable Settings prompts; reset restores application templates."""
        if reset:
            (DATA/"prompts.json").unlink(missing_ok=True)
        else:
            builtins=runpy.run_path(str(UPLOADER))["BUILTIN_PROMPTS"]
            if not isinstance(table,dict) or set(table)!=set(builtins):
                raise ValueError("Invalid prompt settings")
            for phase, values in builtins.items():
                if not isinstance(table[phase],dict) or set(table[phase])!=set(values):
                    raise ValueError("Invalid prompt types")
                if any(not isinstance(v,str) for v in table[phase].values()):
                    raise ValueError("Prompts must be text")
            with tempfile.TemporaryDirectory(prefix="nomi-prompt-validation-") as directory:
                self._write_json(Path(directory)/"prompts.json",table)
                runpy.run_path(str(UPLOADER))["load_prompt_table"](Path(directory))
            self._write_json(DATA/"prompts.json",table)
        return self.prompt_defaults()

    @staticmethod
    def _write_json(path, value):
        temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
        try:
            temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
            os.replace(temporary,path)
        finally:
            temporary.unlink(missing_ok=True)

    def inspect_file(self, filename):
        info=self._inspect_file(filename)
        source=Path(filename)
        sidecar=Path(str(source)+".upldhdr")
        if sidecar.exists():
            saved=self._inspect_file(str(sidecar))
            if not saved.get("existing"):
                raise ValueError("Invalid upload header: "+str(sidecar))
            info["header"]=saved["header"]
        fields=dict(info.get("header") or {})
        fields.setdefault("type","Chat" if source.suffix.lower() in (".json",".zip") else "Knowledge")
        fields.setdefault("title",source.stem)
        for prop in ("source","date"):
            fields.setdefault(prop,"")
        kind=str(fields["type"]).lower()
        key=("journal_other" if fields.get("source") and fields["source"].casefold()!=str(self.project.get("nomi","")).casefold()
             else "journal_self") if kind=="journal" else kind
        table=self.prompt_defaults()
        legacy_export=info.get("export",False)
        fields.setdefault("headerPrompt",fields.get("intro") if legacy_export else fields.get("headerText") or table["opening"].get(key,""))
        if not fields.get("replyPrompt"):
            fields["replyPrompt"]=fields.get("periodic") if legacy_export else fields.get("prompts") or table["periodic"].get(key,"")
        if fields.get("process") in (None,""):
            fields["process"]=self.project.get("process",5)
        if fields.get("headerEvery") in (None,""):
            fields["headerEvery"]=self.project.get("header_every",0)
        info.update(header=fields,editable=True,sidecar=str(sidecar))
        return info

    def save_file_header(self, item):
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("Cannot modify a running upload.")
        source=Path(item["path"])
        if not source.is_file():
            raise ValueError("Missing source file: "+str(source))
        text=self._header_text(source,item["fields"])
        sidecar=Path(str(source)+".upldhdr")
        temporary=sidecar.with_name(sidecar.name+"."+uuid.uuid4().hex+".tmp")
        try:
            temporary.write_text(text+"\n",encoding="utf-8")
            os.replace(temporary,sidecar)
        finally:
            temporary.unlink(missing_ok=True)
        return str(sidecar)

    def file_sample(self,item):
        source=Path(item["path"])
        body=self._inspect_file(str(source)).get("preview","")
        return self._header_text(source,item["fields"])+"\n\n"+body[:12000]

    @staticmethod
    def _header_text(source, fields):
        kind=str(fields.get("type") or "Knowledge").lower()
        if kind not in ("knowledge","instructions","journal","chat"):
            raise ValueError("Invalid content Type")
        title=str(fields.get("title") or source.stem).strip()
        if any(c in title for c in "\r\n[]"):
            raise ValueError("Invalid section title")
        lines=["["+title+"]","Type: "+kind.title()]
        for label,prop in (("Source","source"),("Date","date"),("Header Every","headerEvery"),("Process Every","process")):
            value=str(fields.get(prop,"")).strip()
            if prop in ("headerEvery","process"):
                if not value.isdecimal() or not 0<=int(value)<=1000:
                    raise ValueError(label+" must be a whole number from 0 to 1000")
            elif "\n" in value or "\r" in value:
                raise ValueError(label+" must be a single line")
            lines.append(label+": "+value)
        lines.append("Nomi Mode: Replace")
        if int(fields["process"]) and not str(fields.get("replyPrompt","")).strip():
            raise ValueError("Enter a reply prompt or set Reply every to 0")
        if int(fields["headerEvery"]) and not str(fields.get("headerPrompt","")).strip():
            raise ValueError("Enter a header prompt or set Repeat every to 0")
        for label,prop in (("Header Prompt","headerPrompt"),("Reply Prompt","replyPrompt")):
            for line in str(fields.get(prop,"")).split("\n"):
                lines.append(label+": "+line.rstrip("\r"))
        return "\n".join(lines)

    def _inspect_file(self, filename):
        """Read TXT metadata and a preview without modifying the source file."""
        source = Path(filename)
        if source.suffix.lower() in (".zip", ".json"):
            sys.path.insert(0, str(UPLOADER.parent))
            import legacy_v085 as legacy
            prompts = self.prompt_defaults()
            name, rows=legacy.load_conversation(source)
            preview="\n".join(str(x.get("date",""))+" "+str(x.get("sender",""))+": "+str(x.get("message","")) for x in rows[:30])
            return {"editable": False, "export": True, "header": {"mode":"Replace","intro":prompts["opening"]["chat"],"periodic":prompts["periodic"]["chat"],"process":""}, "preview": preview[:12000], "existing": False, "count":len(rows), "nomi_name":name}
        if source.suffix.lower()==".docx":
            from docx import Document
            raw="\n".join(p.text for p in Document(str(source)).paragraphs)
        else:
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
                m = re.match(r"^(Type|Source|Date|Process Every|Header Every|Header Text|Header Prompt|Reply Prompt|Nomi Mode|Nomi):\s*(.*)$", lines[i].strip(), re.I)
                if m:
                    k,v = m.group(1).lower(), m.group(2).strip()
                    key = {"type":"type","source":"source","date":"date","process every":"process","header every":"headerEvery","header text":"headerText","header prompt":"headerPrompt","reply prompt":"replyPrompt","nomi mode":"mode","nomi":"prompts"}[k]
                    if key == "prompts": prompts.append(v)
                    elif key in ("headerPrompt","replyPrompt","headerText") and key in header:
                        header[key]+="\n"+v
                    else: header[key] = v
                    content_start = i + 1
                elif not lines[i].strip():
                    content_start = i + 1
                else: break
            header["prompts"] = "\n".join(prompts)
        content = "".join(lines[content_start:])
        return {"editable": True, "header": header, "preview": content[:120000], "truncated": len(content)>120000, "existing": existing}

    def _build_txt(self, source, item):
        """Prepare a working TXT copy without modifying the selected original."""
        info = self._inspect_file(str(source))
        if "fields" not in item:
            return source.read_text(encoding="utf-8-sig")
        fields = item["fields"]
        raw = source.read_text(encoding="utf-8-sig") if source.suffix.lower()==".txt" else "\n".join(p.text for p in __import__("docx").Document(str(source)).paragraphs)
        if info["existing"]:
            # Remove only the first section's existing metadata. Preserve original source.
            lines = raw.splitlines(keepends=True)
            first = next(i for i, x in enumerate(lines) if x.strip())
            pos = first + 1
            while pos < len(lines):
                line = lines[pos].strip()
                if not line or re.match(r"^(Type|Source|Date|Process Every|Header Every|Header Text|Header Prompt|Reply Prompt|Nomi Mode|Nomi):", line, re.I):
                    pos += 1
                else: break
            body = "".join(lines[pos:])
        else:
            body = raw
        if "headerPrompt" in fields:
            header=self._header_text(source,fields).splitlines()
        else:
            header=None
        title = str(fields.get("title") or source.stem).strip()
        kind = str(fields.get("type") or "Knowledge").strip().lower()
        if kind not in ("knowledge","instructions","journal","chat"):
            raise ValueError("Invalid content Type")
        mode = str(fields.get("mode") or "Add").strip().lower()
        if mode not in ("add","replace"): raise ValueError("Invalid Nomi Mode")
        explicit_header=header
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
        # Bracketed transcript lines are content unless they introduce an
        # explicitly typed uploader section. Escape them in the working copy.
        lines = body.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if not re.fullmatch(r"\[[^\]\n]+\]", line.strip()):
                continue
            typed = False
            for following in lines[index + 1:]:
                value = following.strip()
                if re.match(r"^Type:", value, re.I):
                    typed = True
                    break
                if value and not re.match(
                    r"^(Source|Date|Process Every|Header Every|Header Text|Reply Prompt|Nomi Mode|Nomi):",
                    value, re.I
                ):
                    break
            if not typed:
                lines[index] = line.replace("[", r"\[", 1)
        return "\n".join(explicit_header if explicit_header is not None else header) + "\n\n" + "".join(lines)

    def _paths(self, run_dir, queue=None):
        """Resolve checkpoint, completion and reply paths for a run directory."""
        out = []
        for i, item in enumerate(self.project.get("queue", []) if queue is None else queue):
            source = Path(item["path"])
            if not source.is_file(): raise ValueError("Missing source file: " + str(source))
            suffix = source.suffix.lower()
            if suffix not in (".txt", ".docx", ".json", ".zip"):
                raise ValueError("Unsupported file type: " + str(source))
            if suffix in (".txt",".docx") and item.get("fields"):
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

    @staticmethod
    def _export_options(queue):
        result={x["path"]: {"mode":x["export_fields"].get("mode","Replace"),
                                 "intro":x["export_fields"].get("intro",""),
                                 "periodic":x["export_fields"].get("periodic",""),
                                 "process_every":x["export_fields"].get("process",""),
                                 "header_every":x["export_fields"].get("headerEvery",""),
                                 "header_text":x["export_fields"].get("headerText",None)}
                      for x in queue if x.get("export_fields") and Path(x["path"]).suffix.lower() in (".zip",".json")}
        for item in queue:
            if Path(item["path"]).suffix.lower() not in (".zip",".json") or "headerPrompt" not in item.get("fields",{}):
                continue
            fields=item["fields"]
            API._header_text(Path(item["path"]),fields)
            result[item["path"]]={"mode":"Replace","intro":fields["headerPrompt"],
                "periodic":fields["replyPrompt"],"process_every":fields["process"],
                "header_every":fields["headerEvery"],"header_text":fields["headerPrompt"],
                "type":fields["type"],"source":fields.get("source",""),"date":fields.get("date","")}
        return result

    def preview_file(self, item, options):
        """Return expected validation failures for inline display in Preview."""
        try:
            return self._preview_file(item, options)
        except (ValueError, OSError) as exc:
            message = str(exc)
            if "dated chat content required" in message or "Chat section needs speaker-labelled turns" in message:
                message += (
                    "\n\nFor Chat, set a date in Metadata or add a Date: line "
                    "to each conversation block. Start conversation lines with a speaker name and colon."
                    "\n\nExample:\n[Conversation]\nType: Chat\nDate: 2026-11-16"
                    "\n\nSteve: How did your day go?\nTammy: It went well."
                    "\n\nIf this file is informational prose, choose Knowledge instead of Chat."
                )
            elif "dated journal content required" in message:
                message += (
                    "\n\nFor Journal, start each entry with an entry number and date. "
                    "Use YYYY-MM-DD to avoid ambiguity. For a single dated entry, "
                    "you can also set the date in Metadata."
                    "\n\nExample:\n[Tammy’s Journal]\nType: Journal"
                    "\n\nENTRY 001 — 2026-11-16\nI wrote about my first day at work."
                    "\n\nENTRY 002 — 2026-11-17\nI wrote about my second day."
                )
            return {"error": message}

    def _preview_file(self, item, options):
        """Generate the selected file's upload plan without credentials or API calls."""
        sys.path.insert(0, str(UPLOADER.parent))
        try:
            cli = runpy.run_path(str(UPLOADER))
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory(prefix="nomi-preview-") as directory:
            files = self._paths(Path(directory), [item])
            user = str(options.get("user_name") or "").strip()
            for path in files:
                if Path(path).suffix.lower() == ".txt" and not user:
                    raw = Path(path).read_text(encoding="utf-8-sig")
                    if "[username]" in raw or "__USER_NAME__" in raw:
                        raise ValueError("Enter your Nomi.ai user name to preview this file.")
            plan = cli["plan_text"](
                files, options.get("nomi") or "Nomi", user,
                cli["regional_order"](), cli["dt"].date.today().year,
                cli["DEFAULT_CHUNK_CHARS"], int(options.get("process", 5)),
                chunk_mode="chars", export_options=self._export_options([item]),
                header_every=int(options.get("header_every", 0)),
                header_text=options.get("header_text", ""),
                reply_prompt=options.get("reply_prompt", ""),
                prompt_table=cli["load_prompt_table"](DATA),include_prompt_dates=True)
        return {"count": len(plan), "text": "\n\n".join(
            f"── Message {i} · {row['kind']} ──\n{row['text']}"
            for i, row in enumerate(plan, 1))}

    def _cli(self, args):
        """Construct the Python uploader subprocess invocation."""
        return ([sys.executable, "--uploader-cli"] if FROZEN else [sys.executable, str(UPLOADER)]) + args

    def _run(self, args):
        """Start the uploader subprocess while retaining its status output."""
        if self.proc and self.proc.poll() is None: raise RuntimeError("An upload is already running.")
        self.lines = deque(maxlen=1000)
        env = os.environ.copy()
        import legacy_v085
        env["NOMI_API_KEY"] = legacy_v085.resolved_api_key() or env.get("NOMI_API_KEY", "")
        if not env["NOMI_API_KEY"] and "--dry-run" not in args and "--status" not in args:
            raise ValueError("Enter your Nomi API key in Settings.")
        env["NOMI_GUI_TARGET_NOMI"] = self.project.get("nomi","")
        env["NOMI_GUI_TARGET_UUID"] = self.project.get("nomi_uuid","")
        self.proc = subprocess.Popen(self._cli(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                     bufsize=1, cwd=str(DATA),
                     env={**env, "PYTHONUNBUFFERED":"1", "PYTHONIOENCODING":"utf-8:backslashreplace",
                          "PYTHONUTF8":"1"}, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        def reader():
            for line in self.proc.stdout:
                with self.lock: self.lines.append(line.rstrip())
        threading.Thread(target=reader, daemon=True).start()
        return True

    def _active_dir(self):
        """Find the selected upload run's on-disk directory."""
        token=self.project.get("active_run")
        if not token:
            return DATA  # Preserve access to pre-upgrade checkpoints.
        if not re.fullmatch(r"[0-9a-f]{32}",str(token)):
            raise ValueError("Invalid run identifier")
        return DATA / "runs" / token

    def _has_checkpoint(self, directory):
        """Check whether a run directory has checkpoint evidence."""
        cp=directory / "upload.jsonl"
        return cp.is_file() and cp.stat().st_size>0

    def begin(self, dry=False, restart=None):
        """Start a new upload or dry run with the current GUI project options."""
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("Upload already running")
        destination = self.project.get("reply_destination", "room")
        if destination not in ("room", "private"):
            raise ValueError("Reply destination must be room or private")
        token=uuid.uuid4().hex
        directory=self._active_dir() if restart else DATA / ("previews" if dry else "runs") / token
        if restart:
            if dry: raise ValueError("Manual restart cannot be a dry run.")
            if not self._has_checkpoint(directory): raise ValueError("Select a checkpoint first.")
            info=self.recovery_status()
            if info["state"]=="NO_CHECKPOINT": raise ValueError("Missing checkpoint.")
            if self.project.get("nomi_uuid") and self.project["nomi_uuid"]!=info.get("nomi_uuid"):
                raise ValueError("Selected Nomi differs from checkpoint. Choose the correct Nomi.")
            workdir=directory/"revisions"/token
            workdir.mkdir(parents=True,exist_ok=False)
        else:
            directory.mkdir(parents=True,exist_ok=False)
            workdir=directory
        paths=self._paths(workdir)
        # Persist an exact input manifest for inspection and incident recovery.
        manifest={"source_files":[x.get("path") for x in self.project.get("queue",[])],
                  "processed_files":paths,"nomi_uuid":self.project.get("nomi_uuid"),
                  "room_uuid":self.project.get("room_uuid")}
        (workdir/"gui-input-manifest.json").write_text(
            json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        args = (["--resume","--manual-restart",restart] if restart
                else ([] if not dry else ["--dry-run", "--nomi", self.project.get("nomi") or "Nomi"]))
        needs_name=any(("[username]" in Path(p).read_text(encoding="utf-8-sig") or "__USER_NAME__" in Path(p).read_text(encoding="utf-8-sig"))
                       for p in paths if Path(p).suffix.lower()==".txt")
        user_name=str(self.project.get("user_name") or "").strip()
        if needs_name and not user_name:
            raise ValueError("Enter your Nomi.ai user name before uploading this file.")
        if user_name:
            if any(c in user_name for c in "\r\n[]"):
                raise ValueError("Invalid Nomi.ai user name.")
            args += ["--user", user_name]
        if not dry and not restart:
            room = str(self.project.get("room_uuid") or "").strip()
            if not room: raise ValueError("Select or create an upload room first.")
            if not self.project.get("nomi_uuid"): raise ValueError("Load Nomis and choose a Nomi from the list before uploading.")
            args += ["--room", room, "--nomi-uuid", str(self.project["nomi_uuid"])]
        if any(Path(x["path"]).suffix.lower() in (".zip",".json") and x.get("export_fields") for x in self.project.get("queue",[])):
            settings=self._export_options(self.project["queue"])
            opts=workdir/"export-options.json"
            opts.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding="utf-8")
            args += ["--export-options",str(opts)]
        args += ["--header-every",str(int(self.project.get("header_every",0))),
                 "--header-text",str(self.project.get("header_text","")),
                 "--reply-prompt",str(self.project.get("reply_prompt",""))]
        args += ["--process-every", str(int(self.project.get("process", 5))),
                 "--reply-max-wait", str(float(self.project.get("reply_wait", 900)))]
        if not restart:
            args += ["--reply-destination", destination]
        args += ["--checkpoint", str(directory / "upload.jsonl"),
                 "--completion", str(directory / "completed.json"),
                 "--replies", str(directory / "replies.txt")]
        args += paths
        if restart:
            Path(str(directory/"upload.jsonl")+".pause").unlink(missing_ok=True)
            return self._run(args)
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

    def manual_restart(self, pass_number, message_number):
        """Explicit operator override in the SAME append-only journal."""
        p=int(pass_number); i=int(message_number)
        if p<1 or i<1: raise ValueError("Pass and message number must be positive.")
        return self.begin(False,f"{p}:{i}")

    def pause(self):
        """Stop the current uploader subprocess without discarding its checkpoint."""
        if not self.proc or self.proc.poll() is not None:
            raise RuntimeError("No running upload to pause.")
        marker=Path(str(self._active_dir()/"upload.jsonl")+".pause")
        marker.write_text("pause",encoding="utf-8")
        return "Pause requested; completing the current API operation."

    def clear_history(self):
        """Clear eligible saved history after checking for an active upload."""
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
            with cp.open(encoding="utf-8") as history:
                for line in history:
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
        """Select a saved run for status or recovery without changing its journal."""
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("Cannot switch runs during upload.")
        directory=DATA if run_id=="legacy" else DATA/"runs"/str(run_id)
        if run_id!="legacy" and not re.fullmatch(r"[0-9a-f]{32}",str(run_id)):
            raise ValueError("Invalid run ID")
        if not self._has_checkpoint(directory): raise ValueError("Run has no checkpoint")
        self.project["active_run"]=None if run_id=="legacy" else run_id
        self.save(self.project)
        self.lines=deque(maxlen=1000)
        self.proc=None
        return True

    def _checkpoint_view(self):
        """Share one bounded status snapshot for each checkpoint revision."""
        lock=self.__dict__.setdefault("_checkpoint_lock",threading.Lock())
        with lock:
            cp=self._active_dir()/"upload.jsonl"
            try:
                stat=cp.stat()
                signature=(str(cp),stat.st_ino,stat.st_mtime_ns,stat.st_size)
            except FileNotFoundError:
                stat=None
                signature=(str(cp),None)
            cached=getattr(self,"_checkpoint_cache",None)
            if cached is not None and cached[0]==signature:
                return cached[1]
            view={"confirmed":0,"total":0,"replies":[],
                  "recovery":{"state":"NO_CHECKPOINT","uncertain_sends":[],"ambiguous_replies":[]}}
            if stat is not None and stat.st_size:
                module=getattr(self,"_checkpoint_module",None)
                if module is None:
                    import importlib.util
                    if str(UPLOADER.parent) not in sys.path:
                        sys.path.insert(0,str(UPLOADER.parent))
                    spec=importlib.util.spec_from_file_location("nomi_uploader_gui_checkpoint",str(UPLOADER))
                    module=importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self._checkpoint_module=module
                events=module.active_records(cp)
                recovery=module.checkpoint_summary(cp,events=events)
                recovery["recommendation"]=(
                    "Normal Resume" if recovery["state"]=="SAFE_TO_RESUME"
                    else "Review uncertain operation, then Resume" if recovery["state"] in ("AMBIGUOUS_SEND","AMBIGUOUS_REPLY")
                    else "No resume needed" if recovery["state"]=="COMPLETE"
                    else "Manual Restart if you intentionally changed the plan")
                replies=deque(maxlen=50)
                for row in events:
                    if row.get("event")=="reply_committed" and not row.get("synthetic"):
                        reply=row.get("reply") or {}
                        body=reply.get("messageText") or reply.get("text") or reply.get("content")
                        replies.append({"pass":row.get("pass"),"index":row.get("index"),
                                        "prompt":row.get("prompt",""),
                                        "reply":body or "No reply text was recorded."})
                view={"confirmed":recovery.get("confirmed",0),"total":recovery.get("expected",0),
                      "replies":list(replies),"recovery":recovery}
            self._checkpoint_cache=(signature,view)
            return view

    def recovery_status(self):
        """Classify the selected checkpoint using the shared status snapshot."""
        return self._checkpoint_view()["recovery"]

    def private_reply_recovery(self):
        status=self.recovery_status()
        cp=self._active_dir()/"upload.jsonl"
        module=getattr(self,"_checkpoint_module",None)
        if module is None:
            return []
        events=module.active_records(cp)
        if not events or events[0].get("reply_destination","room")!="private":
            return []
        pending={tuple(p) for p in status.get("ambiguous_replies",[])}
        result=[]
        for key in sorted(pending):
            attempt=next((e for e in reversed(events) if e.get("event")=="reply_attempt"
                          and (e.get("pass"),e.get("index"))==key),{})
            confirmed=next((e for e in reversed(events) if e.get("event")=="confirmed"
                            and (e.get("pass"),e.get("index"))==key),{})
            sent=(confirmed.get("api_response") or {}).get("sentMessage") or {}
            result.append({"position":":".join(map(str,key)),"checkpoint":str(cp),
                           "prompt":attempt.get("prompt") or sent.get("text") or sent.get("messageText") or "Prompt text unavailable",
                           "time":attempt.get("sent_at") or attempt.get("ts") or attempt.get("timestamp") or ""})
        return result

    def accept_received_reply(self, checkpoint, position, text=""):
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("Stop the active upload before recovery.")
        cp=self._active_dir()/"upload.jsonl"
        if str(cp)!=checkpoint:
            raise ValueError("Selected run changed. Reopen Resume.")
        self.recovery_status()
        return self._checkpoint_module.accept_private_reply(cp,position,text.strip(),allow_empty=True)

    def recover_resume(self, send_tokens=None, reply_tokens=None):
        """Explicitly authorized recovery; preserve the checkpoint as the source of truth."""
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("Upload already running.")
        status=self.recovery_status()
        sends={":".join(map(str,p)) for p in status.get("uncertain_sends",[])}
        replies={":".join(map(str,p)) for p in status.get("ambiguous_replies",[])}
        send_tokens=list(send_tokens or [])
        reply_tokens=list(reply_tokens or [])
        if set(send_tokens)-sends or set(reply_tokens)-replies:
            raise ValueError("Checkpoint changed. Refresh recovery status before authorizing.")
        if status["state"]=="COMPLETE":
            raise ValueError("This upload has already completed.")
        if status["state"]=="NO_CHECKPOINT":
            raise ValueError("No checkpoint exists for this run.")
        directory=self._active_dir()
        args=["--resume","--checkpoint",str(directory/"upload.jsonl"),
              "--completion",str(directory/"completed.json"),
              "--replies",str(directory/"replies.txt")]
        for token in send_tokens:
            args.extend(["--retry-uncertain-send",token])
        for token in reply_tokens:
            args.extend(["--recover-uncertain-reply",token])
        Path(str(directory/"upload.jsonl")+".pause").unlink(missing_ok=True)
        return self._run(args)

    def advanced_resume(self, operation, position):
        """Expose legacy reply recovery and room migration through validated CLI flags.

        The CLI checks checkpoint evidence and room protection; GUI does not
        synthesize journal events or override an ambiguous operation.
        """
        flags={
            "noreply": ["--recover-noreply"],
            "migrate": ["--new-room-on-resume", "--abandon-reply"],
        }
        if operation not in flags:
            raise ValueError("Unsupported advanced recovery operation.")
        if self.proc and self.proc.poll() is None:
            raise RuntimeError("Stop the active upload before recovery.")
        if not re.fullmatch(r"[1-9]\\d*:[1-9]\\d*", str(position)):
            raise ValueError("Position must be PASS:INDEX (positive integers).")
        directory=self._active_dir()
        if not self._has_checkpoint(directory):
            raise ValueError("No selected checkpoint to recover.")
        status=self.recovery_status()
        if status["state"] in ("COMPLETE", "NO_CHECKPOINT"):
            raise ValueError("The selected run cannot be resumed.")
        args=["--resume", "--checkpoint", str(directory/"upload.jsonl"),
              "--completion",str(directory/"completed.json"),
              "--replies",str(directory/"replies.txt")]
        if operation=="noreply":
            args.extend(["--recover-noreply",position])
        else:
            args.extend(["--new-room-on-resume","--abandon-reply",position])
        # Only the CLI may decide if this operation matches checkpoint evidence.
        Path(str(directory/"upload.jsonl")+".pause").unlink(missing_ok=True)
        return self._run(args)

    def resume(self):
        """Resume the current selected run using backend recovery checks."""
        directory=self._active_dir()
        if not self._has_checkpoint(directory):
            raise ValueError("No checkpoint exists for the selected run.")
        Path(str(directory/"upload.jsonl")+".pause").unlink(missing_ok=True)
        return self._run(["--resume","--checkpoint",str(directory/"upload.jsonl"),
                          "--completion",str(directory/"completed.json"),
                          "--replies",str(directory/"replies.txt")])

    def status(self):
        """Return process state and the shared checkpoint snapshot."""
        directory=self._active_dir()
        view=self._checkpoint_view()
        with self.lock:
            recent=list(self.lines)[-250:]
        running=bool(self.proc and self.proc.poll() is None)
        return {"running":running,"exit_code":None if running or not self.proc else self.proc.returncode,
                "confirmed":view["confirmed"],"total":view["total"],"log":recent,
                "replies":view["replies"],"project":self.project,
                "can_resume":self._has_checkpoint(directory),
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
