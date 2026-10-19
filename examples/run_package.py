#!/usr/bin/env python3
"""Run the current uploader with an ordered example package and isolated state."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def command(package, dry_run=False, resume=False):
    root = Path(__file__).resolve().parents[1]
    folder = root/'examples'/package
    config = json.loads((folder/'package.json').read_text(encoding='utf-8'))
    state = root/'.local-runs'/package
    args = [sys.executable, str(root/'uploader/nomi-uploader.py'),
            '--checkpoint', str(state/'checkpoint.jsonl'),
            '--completion', str(state/'completed.json'),
            '--replies', str(state/'replies.txt')]
    if resume:
        return args + ['--resume']
    args += ['--date-format', config['date_format']]
    if dry_run:
        args += ['--dry-run', '--nomi', config['nomi']]
    for name in config['inputs']:
        path = (folder/name).resolve()
        if folder.resolve() not in path.parents or not path.is_file():
            raise ValueError('Invalid package input: '+name)
        args.append(str(path))
    return args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', choices=['beth', 'chris', 'mary'])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    cmd = command(args.package, args.dry_run, args.resume)
    if not args.dry_run:
        (Path(__file__).resolve().parents[1]/'.local-runs'/args.package).mkdir(parents=True, exist_ok=True)
    return subprocess.call(cmd)


if __name__ == '__main__':
    sys.exit(main())
