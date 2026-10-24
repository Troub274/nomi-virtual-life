"""Optional pywebview front end to the existing Nomi uploader CLI."""
import json
import os
import runpy
import subprocess
import sys
import threading
import time
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
        self.project = {"queue": [], "nomi": "", "process": 5, "reply_wait": 900}
        if CONFIG.exists():
            try: self.project.update(json.loads(CONFIG.read_text(encoding="utf-8")))
            except (OSError, ValueError): pass

    def save(self, project):
        if self.proc and self.proc.poll() is None: raise RuntimeError("Cannot modify a running upload.")
        self.project = project
        CONFIG.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def choose(self):
        import webview
        paths = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True,
                         file_types=("Uploader files (*.txt;*.docx;*.json;*.zip)", "All files (*.*)"))
        return list(paths or [])

    def _paths(self):
        out = []
        for i, item in enumerate(self.project.get("queue", [])):
            source = Path(item["path"])
            if not source.is_file(): raise ValueError("Missing source file: " + str(source))
            suffix = source.suffix.lower()
            if suffix not in (".txt", ".docx", ".json", ".zip"):
                raise ValueError("Unsupported file type: " + str(source))
            if suffix == ".txt" and item.get("header"):
                generated = DATA / ("prepared-%04d.txt" % i)
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
        return [sys.executable, "--uploader-cli"] + args

    def _run(self, args):
        if self.proc and self.proc.poll() is None: raise RuntimeError("An upload is already running.")
        self.lines = []
        env = os.environ.copy()
        env["NOMI_API_KEY"] = self.project.get("key", "").strip() or env.get("NOMI_API_KEY", "")
        if not env["NOMI_API_KEY"] and "--dry-run" not in args and "--status" not in args:
            raise ValueError("Enter your Nomi API key in Settings.")
        env["NOMI_GUI_TARGET_NOMI"] = self.project.get("nomi","")
        self.proc = subprocess.Popen(self._cli(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=str(DATA),
                     env={**env, "PYTHONUNBUFFERED":"1"}, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        def reader():
            for line in self.proc.stdout:
                with self.lock: self.lines.append(line.rstrip())
        threading.Thread(target=reader, daemon=True).start()
        return True

    def begin(self, dry=False):
        paths = self._paths()
        args = ([] if not dry else ["--dry-run", "--nomi", self.project.get("nomi") or "Nomi"])
        args += ["--process-every", str(int(self.project.get("process", 5))),
                 "--reply-max-wait", str(float(self.project.get("reply_wait", 900)))]
        args += ["--checkpoint", str(DATA / "upload.jsonl"),
                 "--completion", str(DATA / "completed.json"),
                 "--replies", str(DATA / "replies.txt")]
        args += paths
        return self._run(args)

    def resume(self):
        return self._run(["--resume", "--checkpoint", str(DATA / "upload.jsonl"),
                          "--completion", str(DATA / "completed.json"),
                          "--replies", str(DATA / "replies.txt")])

    def status(self):
        cp = DATA / "upload.jsonl"
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
                "project":self.project}

if __name__ == "__main__":
    if "--uploader-cli" in sys.argv:
        at = sys.argv.index("--uploader-cli")
        sys.argv = [str(UPLOADER)] + sys.argv[at+1:]
        sys.path.insert(0, str(UPLOADER.parent))
        import builtins
        import legacy_v085
        target = os.environ.get("NOMI_GUI_TARGET_NOMI", "").casefold().strip()
        def gui_input(prompt=""):
            if "Select Nomi number" in prompt:
                nomis = legacy_v085.get_nomis()
                matches = [i for i, n in enumerate(nomis, 1) if n.get("name","").casefold() == target]
                if len(matches) != 1:
                    raise ValueError("Choose an exact, unique Nomi name in the GUI.")
                return str(matches[0])
            if "Room choice" in prompt:
                return "1"
            raise ValueError("Uploader needs interactive confirmation: " + prompt + ". Use CLI recovery for this case.")
        builtins.input = gui_input
        runpy.run_path(str(UPLOADER), run_name="__main__")
    else:
        import webview
        api = API()
        webview.create_window("Nomi Uploader", INDEX.as_uri(), js_api=api, width=1150, height=830)
        webview.start()
