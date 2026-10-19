# Bridge repository migration

The maintained home is now `Troub274/nomi-virtual-life`, under `bridge/`.
Current extension v0.4.3, desktop wrapper, tests and guides were imported from
`Troub274/nomi-bridge` commit `ea096e7793697ae31cc8e94c517edb99b4ab4f93`.
`IMPORT.json` records the original paths and SHA256 hashes. Runtime code and tests
were copied without behavioral changes. The top-level README and development guide
were updated for the new repository. Historical ZIPs, backups and one-off patch scripts
remain available in the old repository and its history; they are not current build inputs.

## Existing browser installations

Stop the bridge before updating. Keep the existing Edge profile, extension ID and
Loaded from folder when an API room checkpoint or observation journal is active.
Moving an unpacked extension to a different folder can create a different extension
identity and separate storage. Loading a second copy does not migrate the API key,
selectors, checkpoints or journals. Do not uninstall the old copy to fix a pending send.

To preserve identity, copy the contents of the new `bridge/extension/` folder into
the extension's existing Loaded from folder, then Reload it at `edge://extensions`.
Do not replace or delete browser profile folders. Reload clears transient sessions;
inspect unresolved API requests using the recovery guide before resuming. Persistent
API room checkpoints remain in extension local storage. Existing desktop profile
locations under `%LOCALAPPDATA%/ChatBridge/profiles` are unchanged.

For a fresh installation, Load unpacked from `bridge/extension/`. Browser modes need
no server, Python or npm dependencies. Only API Room mode requires a Nomi API key.

## Development

```sh
git clone https://github.com/Troub274/nomi-virtual-life.git
cd nomi-virtual-life/bridge
node --test tests/*.test.cjs
```

Use Node.js 22. Desktop builds still run from `bridge/desktop/` with that folder's
requirements and build script. The uploader remains independent under `uploader/`;
bridge browser checkpoints and uploader JSONL checkpoints have different formats.
Report new issues and submit bridge changes to `nomi-virtual-life`.
