"""Run the source CLI against a simulator, or make an isolated Bridge test copy."""
import argparse
import configparser
import re
from pathlib import Path
import json
import os
import runpy
import shutil
import sys

from nomi_simulator import DUMMY_KEY

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, help="Override the port from the test INI")
    parser.add_argument("--bridge-copy", type=Path)
    parser.add_argument("--ini", type=Path, help="Simulator-only INI; a missing file tests no saved key")
    parser.add_argument("uploader_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "uploader"))
    import legacy_v085
    ini = (args.ini or Path(__file__).with_name("simulator.example.ini")).resolve()
    if ini == legacy_v085.credential_file().resolve():
        parser.error("Use a separate simulator INI, not the production credential file")
    settings = configparser.ConfigParser()
    try:
        settings.read(ini, encoding="utf-8")
        endpoint = settings.get("nomi", "endpoint", fallback="http://127.0.0.1:8765/v1")
    except configparser.Error as exc:
        parser.error(f"Invalid simulator INI ({type(exc).__name__})")
    match = re.fullmatch(r"http://127\.0\.0\.1:([0-9]{1,5})/v1", endpoint)
    if not match or not 1 <= int(match[1]) <= 65535:
        parser.error("endpoint must be http://127.0.0.1:PORT/v1")
    port = args.port if args.port is not None else int(match[1])
    if not 1 <= port <= 65535:
        parser.error("invalid port")
    origin = f"http://127.0.0.1:{port}"
    if args.bridge_copy:
        manifest = ROOT / "bridge/extension/manifest.json"
        shutil.copytree(manifest.parent, args.bridge_copy)
        target = args.bridge_copy / manifest.name
        data = json.loads(target.read_text(encoding="utf-8"))
        data["name"] += " (Simulator)"
        data["host_permissions"].remove("https://api.nomi.ai/*")
        data["host_permissions"].append("http://127.0.0.1/*")
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        driver = args.bridge_copy / "api-room.js"
        source = driver.read_text(encoding="utf-8")
        driver.write_text(source.replace("https://api.nomi.ai/v1", origin + "/v1"), encoding="utf-8")
        return
    legacy_v085.BASE_URL = origin + "/v1"
    os.environ.pop("NOMI_API_KEY", None)
    legacy_v085.credential_file = lambda: ini
    # Never transmit a production credential accidentally copied to the test INI.
    original_resolve = legacy_v085.resolved_api_key
    def resolve_fixture_key():
        key = original_resolve()
        return key if key in (None, DUMMY_KEY) else "simulator-invalid-key"
    legacy_v085.resolved_api_key = resolve_fixture_key
    argv = args.uploader_args
    if argv[:1] == ["--"]:
        argv = argv[1:]
    try:
        runpy.run_path(str(ROOT / "uploader/nomi-uploader.py"))["main"](argv)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
