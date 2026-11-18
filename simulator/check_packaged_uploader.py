"""Check bundled dependencies and export planning through the frozen CLI entry."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from regression_fixtures import write_chatgpt, write_nomi


def check(executable):
    from docx import Document

    with tempfile.TemporaryDirectory(prefix="nomi-packaged-regression-") as directory:
        root = Path(directory)
        docx = root / "facts.docx"
        document = Document()
        document.add_paragraph("[Facts]")
        document.add_paragraph("Type: Knowledge")
        document.add_paragraph("")
        document.add_paragraph("Synthetic Word document.")
        document.save(docx)
        gpt = write_chatgpt(root / "chatgpt.json")
        nomi = write_nomi(root / "nomi.json")
        archive = root / "chatgpt.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.write(gpt, "conversations.json")
        environment = {**os.environ, "LOCALAPPDATA": str(root / "appdata"), "NOMI_API_KEY": ""}
        for source in (docx, gpt, nomi, archive):
            result = subprocess.run(
                [str(executable), "--uploader-cli", "--dry-run", "--nomi", "Simulator",
                 "--process-every", "10", "--checkpoint", str(root / "checkpoint.jsonl"),
                 str(source)], cwd=root, env=environment, input="", capture_output=True,
                text=True, encoding="utf-8", timeout=90)
            if result.returncode:
                raise RuntimeError(f"{source.name} failed\n{result.stdout}\n{result.stderr}")
            kinds = re.findall(r"^\s*\d+\s+(intro|content|prompt)\s", result.stdout, re.MULTILINE)
            if "content" not in kinds:
                raise AssertionError(f"{source.name}: no content was planned")
            if source != docx:
                pending = 0
                batches = []
                for kind in kinds:
                    if kind == "content":
                        pending += 1
                    elif kind == "prompt":
                        batches.append(pending)
                        pending = 0
                if (not batches or pending or any(n != 10 for n in batches[:-1])
                        or not 1 <= batches[-1] <= 10):
                    raise AssertionError(f"{source.name}: wrong reflection cadence {batches}")
                if "DISCARDED BRANCH" in result.stdout:
                    raise AssertionError("An unselected ChatGPT branch was imported")
            print(f"{source.name}: packaged dry run passed", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    check(args.executable.resolve())


if __name__ == "__main__":
    main()
