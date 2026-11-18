# Local Nomi API simulator

Start the server with `nomi_simulator.py`. Use `run_test_harness.py` to
launch the real uploader against it. Harness options such as `--ini` go
before `--`; uploader options and input files go after it. Only the harness
redirects requests. The shipped uploader has no simulator flags.

Run from the repository root with Python 3.11 or later. Use synthetic input
and fresh checkpoint paths. The simulator binds only to `127.0.0.1`, requires
the dummy key `simulator-only-key`, and does not contact Nomi. State and request
history stay in memory until the simulator exits.

```bash
python3 simulator/nomi_simulator.py slow-then-fast
```

In a second terminal, run the real source uploader through the simulator
launcher. This example uses a separate directory and a fixture with two
reflection batches:

```bash
repo="$PWD"
scratch=$(mktemp -d)
cd "$scratch"
printf '[Facts]\nType: Knowledge\n\nFirst example.\n\nSecond example.\n' > facts.txt
python3 "$repo/simulator/run_test_harness.py" -- --nomi-uuid 22222222-2222-2222-2222-222222222222 --room 12345678-1234-1234-1234-123456789012 --process-every 1 --delay 0 facts.txt
curl -fsS -H 'Authorization: simulator-only-key' http://127.0.0.1:8765/__events
```

The event log shows timestamps, request bodies, status, acceptance, and even
responses intentionally dropped after acceptance. Never use private uploads as
fixtures: the local log contains the message bodies.

| Scenario | Scripted behavior |
|---|---|
| `normal` | Content accepted, replies returned immediately. |
| `slow-then-fast` | First three reply requests return explicit not-ready responses after a configurable server delay; later requests succeed. Inspect timestamps for backoff and verify that content isn't replayed. |
| `outage` | Second content POST returns HTTP 503 before simulated acceptance. |
| `lost-send` | Second content POST is accepted, then the socket closes without a response. |
| `lost-reply` | First reply POST is accepted, then the socket closes without a response. |
| `malformed-reply` | First reply request returns HTTP 200 without a replyMessage. |
| `lost-create` | First room-creation POST creates a room, then the socket closes. The room remains visible in the catalog. |

For recovery testing, keep the simulator running and restart the client with
`--resume`. For `lost-send`, confirm an ordinary resume refuses to retry. Then
test `--resume --retry-uncertain-send 1:2` with the same fixture. The log will
show the deliberately authorized duplicate for that position and no replay
of position 1. For `lost-reply`, inspect the checkpoint for the pending prompt
position before using the uploader's explicit reply recovery option.

### Try command-line modes

From the scratch directory above, use a fresh checkpoint for each separate
live experiment. A dry run previews the plan without contacting the server:

```bash
python3 "$repo/simulator/run_test_harness.py" -- --dry-run --nomi Simulator facts.txt
```

For a live range, add `--start-chunk 2 --end-chunk 2` to the uploader arguments.
Check `/__events` to confirm only the selected chunk was sent. Restart the
simulator between independent scenarios to reset request counts. Leave it
running during a resume so the simulated room and request history survive.

For Bridge API Room mode, create a separate unpacked extension directory:

```bash
python3 simulator/run_test_harness.py --bridge-copy /tmp/nomi-bridge-simulator
```

Load that copy in a separate test browser profile. Set its key to
`simulator-only-key`, and select Simulator and Simulator room. Only the Nomi API
endpoint is simulated; the Bridge still interacts with the selected ChatGPT
tab. Use a disposable conversation for manual Bridge tests. Production source,
extension files, credentials, and release packages are unchanged.

Run the automated HTTP recovery check with
`python3 -m unittest discover -s simulator` from the repository root.

### Test credential loading

The uploader launcher reads the included dummy-key INI by default. Pass
`--ini /path/to/test.ini` before the `--` separator to use another file.
Try a copy of `simulator.example.ini` for success, a nonexistent path or
empty `api_key` for missing credentials, and a wrong dummy value for HTTP
401. The launcher ignores the inherited `NOMI_API_KEY`, rejects the normal
production INI path, and substitutes a fake invalid key for any nonmatching
credential before sending it. The Bridge still uses its test profile's
extension storage, rather than an INI.

Set `endpoint = http://127.0.0.1:8765/v1` under `[nomi]` to select the
simulator API base URL. The clients append the room-specific reply request
path to it. A missing endpoint uses port 8765; `--port` overrides it for
temporary test servers. The same endpoint setting applies to Bridge copies.
Non-loopback endpoints are rejected.


## Regression baseline

The harness starts from the released 1.4i.2 behavior. Run the uploader unit
tests, JavaScript control checks, and HTTP simulator tests together with:

    python3 -m pip install -r uploader/requirements.txt
    python3 simulator/run_regressions.py

The HTTP checks call the GUI's real preparation, preview, start, resume, and
manual restart methods, then run the actual source uploader against the local
server. They compare the outgoing message text and HTTP request order with the
planned upload.

Coverage includes both ChatGPT and Nomi downloader exports, selected ChatGPT
branches, inherited intervals and file overrides, disabled reflections,
bracketed TXT conversation content, Unicode, and message size limits. Recovery
checks cover cooperative pause, saved settings on resume, an explicit manual
restart with a revised interval, lost sends and replies, ambiguous room
creation, rejected sends, malformed successful replies, and delayed readiness.

For a built executable, run the separate dependency and planning smoke check:

    python3 simulator/check_packaged_uploader.py /absolute/path/to/NomiUploader.exe

It runs the frozen executable's dry-run entry with synthetic DOCX, Nomi JSON,
ChatGPT JSON, and ChatGPT ZIP files. The Windows CI job builds a fresh executable
and runs this check. The source and HTTP suite runs on Windows, Linux, and macOS
in .github/workflows/uploader-regression.yml.

The JavaScript checks exercise the recovery validators and effective prompt
display logic. Actual pywebview rendering and native file dialogs still need
desktop UI verification. These automated runs use temporary data directories
and synthetic messages.
