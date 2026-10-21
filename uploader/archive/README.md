# Archived uploader versions

`nomi-uploader-v1.0.py` is an exact copy of the production uploader immediately before the v1.1 upgrade.

It is retained as a recovery/reference implementation. Do not use it for new runs unless you are deliberately reproducing v1.0 behavior.

Nomi Uploader v1.1 keeps the v1.0 byte-based planning path internally when resuming a checkpoint created by v1.0, so normal old checkpoints should continue through the current `nomi-uploader.py`.
