"""Synthetic export fixtures shared by HTTP and packaged-executable checks."""
import json
from pathlib import Path


def write_chatgpt(path):
    def node(parent, role, text):
        return {"parent": parent, "children": [], "message": {
            "author": {"role": role}, "create_time": 1745629158,
            "content": {"content_type": "text", "parts": [text]}}}
    data = [{"title": "Synthetic conversation", "create_time": 1745629158,
             "id": "synthetic-chat", "current_node": "answer",
             "mapping": {
                 "root": {"parent": None, "message": None, "children": ["user"]},
                 "user": node("root", "user", "Hello from the user."),
                 "discarded": node("user", "assistant", "DISCARDED BRANCH"),
                 "answer": node("user", "assistant", "Synthetic reply caf\u00e9 \U0001f60a. " * 800)}}]
    Path(path).write_text(json.dumps(data), encoding="utf-8")
    return Path(path)


def write_nomi(path):
    data = {"nomi": {"name": "Simulator", "chat": [
        {"date": "2025-04-26T00:59:18Z", "sender": "User",
         "message": "Hello from the user."},
        {"date": "2025-04-26T00:59:19Z", "sender": "Simulator",
         "message": "Synthetic reply caf\u00e9 \U0001f60a. " * 800}],
        "voiceCalls": [{"messages": [
            {"date": "2025-04-26T00:59:20Z", "sender": "Simulator",
             "message": "Synthetic voice transcript."}]}]}}
    Path(path).write_text(json.dumps(data), encoding="utf-8")
    return Path(path)
