
#!/usr/bin/env python3
"""Run an example package with automatic checkpoint/resume handling."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_upload_inputs import check


PACKAGES = ['beth', 'chris', 'mary', 'tammy', 'gwen']


def state_paths(root, package):
    state = root/'.local-runs'/package
    return state, state/'checkpoint.jsonl', state/'completed.json', state/'replies.txt'


def command(package, dry_run=False, resume=False, restart=False, status=False, delay=None, user=None):
    root = Path(__file__).resolve().parents[1]
    folder = root/'examples'/package
    config = json.loads((folder/'package.json').read_text(encoding='utf-8'))
    state, checkpoint, completion, replies = state_paths(root, package)

    args = [sys.executable, str(root/'uploader/nomi-uploader.py'),
            '--checkpoint', str(checkpoint),
            '--completion', str(completion),
            '--replies', str(replies)]

    # Only override the uploader's delay when explicitly requested.
    if delay is not None:
        args += ['--delay', str(delay)]

    if status:
        return args + ['--status']

    # Normal users do not need to know about --resume. If a checkpoint exists,
    # continue it automatically and let the uploader explain only genuinely
    # ambiguous cases in plain language.
    if resume or (not restart and not dry_run and checkpoint.exists() and checkpoint.stat().st_size):
        return args + ['--resume', '--easy']

    args += ['--date-format', config['date_format']]
    if user:
        args += ['--user', user]
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
    parser.add_argument('--user', default=None, help='Nomi.ai display name of the person uploading (required for Gwen)')
    parser.add_argument('--delay', type=float, default=None,
                        help='Delay in seconds between requests; defaults to uploader setting')

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

    # Fail closed: validate even on resume/restart; status remains read-only.
    if not args.status:
        folder = root/'examples'/args.package
        cfg = json.loads((folder/'package.json').read_text(encoding='utf-8'))
        problems = []
        seen = set()
        for name in cfg['inputs']:
            file = (folder/name).resolve()
            if folder.resolve() not in file.parents or not file.is_file():
                problems.append(f'{name}: missing or invalid input path')
                continue
            issues, ids = check(file)
            problems.extend(f'{name}: {issue}' for issue in issues)
            for number in ids:
                if number in seen:
                    problems.append(f'{name}: repeated diary ENTRY {number} across inputs')
                seen.add(number)
        if problems:
            print('BLOCKED: example package failed upload safety validation:')
            for issue in problems:
                print('  '+issue)
            print('No upload started; fix the source inputs before retrying.')
            return 2

    if (not args.dry_run and not args.resume and not args.restart and not args.status
            and checkpoint.exists() and checkpoint.stat().st_size and completion.exists()):
        print('%s\'s previous upload is complete.' % args.package.capitalize())
        print('Use --status to inspect it or --restart to begin a new run.')
        return 0

    selected_user = args.user
    # The saved checkpoint retains the original name on resume. No re-prompt.
    resuming = args.resume or (not args.dry_run and not args.restart and checkpoint.exists() and checkpoint.stat().st_size > 0)
    if args.package == 'gwen' and not args.status and not resuming:
        if not selected_user:
            if not sys.stdin.isatty():
                parser.error('Gwen requires --user "Nomi.ai Display Name" in noninteractive mode')
            selected_user = input('What is your user name in Nomi.ai? ').strip()
        if not selected_user or any(c in selected_user for c in (chr(10), chr(13), '[', ']')):
            parser.error('A valid Nomi.ai user name is required')
    cmd = command(args.package, args.dry_run, args.resume, args.restart, args.status,
                  delay=args.delay, user=selected_user)
    if not args.dry_run and not args.status:
        state.mkdir(parents=True, exist_ok=True)
    return subprocess.call(cmd)


if __name__ == '__main__':
    sys.exit(main())
