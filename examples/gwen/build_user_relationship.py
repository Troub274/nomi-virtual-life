#!/usr/bin/env python3
"""Render an optional Gwen relationship file for the customer's Nomi profile name.

The uploader does not automatically substitute the Nomi.ai user display name.
Pass that name explicitly. Output stays outside the tracked upload package.
"""
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "reference" / "GWEN_USER_RELATIONSHIP_TEMPLATE.txt"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-name", required=True, help="Name displayed for the user in Nomi.ai")
    parser.add_argument("--output", type=Path, default=HERE / "local" / "GWEN_USER_RELATIONSHIP.txt")
    args = parser.parse_args()
    name = args.user_name.strip()
    if not name or any(c in name for c in "\r\n[]"):
        parser.error("--user-name must be a nonempty single-line name without brackets")
    text = TEMPLATE.read_text(encoding="utf-8")
    assert text.count("__USER_NAME__") >= 2
    text = text.replace("__USER_NAME__", name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print("Created:", args.output)
    print("This file is OPTIONAL and is not in Gwen's package.json.")

if __name__ == "__main__":
    main()
