#!/usr/bin/env python3
"""Run an example package with automatic checkpoint/resume handling."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


PACKAGES = ['beth', 'chris', 'mary', 'tammy']


def state_paths(root, package):
    state = root/'.local-runs'/package
    return state, state/'checkpoint.jsonl', state/'completed.json', state/'replies.txt'


def command(package, dry_run=False, resume=False, restart=False, status=False):
    root = Path(__file__).resolve().parents[1]
    folder = root/'examples'/package
    config = json.loads((folder/'package.json').read_text(encoding='utf-8'))
    state, checkpoint, completion, replies = state_paths(root, package)
    args = [sys.executable, str(root/'uploader/nomi-uploader.py'),
            '--checkpoint', str(checkpoint),
            '--completion', str(completion),
            '--replies', str(replies)]

    if status:
        return args + ['--status']

    # Normal users do not need to know about --resume. If a checkpoint exists,
    # continue it automatically and let the uploader explain only genuinely
    # ambiguous cases in plain language.
    if resume or (not restart and not dry_run and checkpoint.exists() and checkpoint.stat().st_size):
        return args + ['--resume', '--easy']

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
    parser = argparse.ArgumentParser(
        description='Run a packaged Nomi diary. Plain PACKAGE starts or safely resumes it.')
    parser.add_argument('package', choices=PACKAGES)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true',
                      help='Preview the message plan without API calls')
    mode.add_argument('--resume', action='store_true',
                      help='Explicit resume; normally unnecessary')
    mode.add_argument('--restart', action='store_true',
                      help='Start a new run after a completed run; unfinished runs are protected')
    mode.add_argument('--status', action='store_true',
                      help='Show checkpoint status without API calls')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    state, checkpoint, completion, replies = state_paths(root, args.package)

    if (not args.dry_run and not args.resume and not args.restart and not args.status
            and checkpoint.exists() and checkpoint.stat().st_size and completion.exists()):
        print('%s\'s previous upload is complete.' % args.package.capitalize())
        print('Use --status to inspect it or --restart to begin a new run.')
        return 0

    cmd = command(args.package, args.dry_run, args.resume, args.restart, args.status)
    if not args.dry_run and not args.status:
        state.mkdir(parents=True, exist_ok=True)
    return subprocess.call(cmd)


if __name__ == '__main__':
    sys.exit(main())
