#!/usr/bin/env python3
"""Read-only preflight for Nomi example package inputs. Exit nonzero on unsafe content."""
import argparse
import json
import re
import sys
from pathlib import Path

BAD_LINES = re.compile(
    r"(?im)^\s*(?:AUTHORSHIP NOTE:|Upload note:|EDITORIAL NOTE:|"
    r"DEVELOPER NOTE:|WRITER.?S NOTE:|"
    r"(?:this|these) (?:diary|journal|entries|memories) (?:is|are) fictional\b|"
    r"this (?:is a|is an) (?:fictional|simulated|AI-generated)\b)"
)
BAD_PHRASES = re.compile(
    r"(?i)\b(?:fictional (?:first.person diary|character|memory|biography|"
    r"personal history|family|identity)|"
    r"(?:provisional|invented) unless (?:established|approved)|"
    r"(?:created|written|generated) (?:for|by) (?:a )?(?:nomi|ai) (?:uploader|experiment)|"
    r"this is (?:an? )?(?:ai|nomi) (?:simulation|character))\b"
)
HEADER = re.compile(r"^\[[^\]\n]+\]$")
META = re.compile(r"^(Type|Source|Date|Nomi|Nomi Mode|Process Every):\s*(.*)$", re.I)
ENTRY = re.compile(r"(?m)^\s*ENTRY\s+(\d+)\b")

def check(path):
    problems = []
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or not HEADER.fullmatch(lines[0]):
        problems.append("line 1: missing [section title]")
        return problems, []
    typ = None
    for number, line in enumerate(lines[1:], 2):
        m = META.match(line)
        if m and m.group(1).lower() == "type":
            typ = m.group(2).strip().lower()
            break
    if typ not in {"journal", "knowledge", "instructions", "chat"}:
        problems.append("missing valid Type: Journal/Knowledge/Instructions/Chat")
    for number, line in enumerate(lines, 1):
        if BAD_LINES.search(line) or BAD_PHRASES.search(line):
            problems.append(f"line {number}: out-of-world/editorial text: {line[:150]}")
    entry_ids = [int(x) for x in ENTRY.findall(text)]
    if typ == "journal" and not entry_ids:
        problems.append("journal lacks ENTRY headings")
    if len(entry_ids) != len(set(entry_ids)):
        problems.append("repeated ENTRY numbers")
    return problems, entry_ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    ns = ap.parse_args()
    root = Path(ns.root).resolve()
    base = root / "examples"
    if not base.exists():
        base = root
    errors = 0
    for manifest in sorted(base.glob("*/package.json")):
        config = json.loads(manifest.read_text(encoding="utf-8"))
        print(f"PACKAGE {manifest.parent.name}")
        entries = []
        for f in config["inputs"]:
            path = manifest.parent / f
            if not path.is_file():
                print(f"  ERROR missing: {f}")
                errors += 1
                continue
            problems, nums = check(path)
            entries.extend(nums)
            for item in problems:
                print(f"  ERROR {f}: {item}")
            errors += len(problems)
            if not problems:
                print(f"  OK {f} ({len(nums)} diary entries)")
        if len(entries) != len(set(entries)):
            print("  ERROR: duplicate journal entry numbers across files")
            errors += 1
    print(f"Preflight complete: {errors} errors")
    return int(errors != 0)

if __name__ == "__main__":
    sys.exit(main())
