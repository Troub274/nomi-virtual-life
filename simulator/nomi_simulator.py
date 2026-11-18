"""Loopback-only, in-memory Nomi API fixtures. No upstream connection."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socket
import time
import uuid

NOMI = "22222222-2222-2222-2222-222222222222"
ROOM = "12345678-1234-1234-1234-123456789012"
SCENARIOS = ("normal", "slow-then-fast", "outage", "lost-send", "lost-reply", "lost-create", "malformed-reply")
DUMMY_KEY = "simulator-only-key"


class Simulator(HTTPServer):
    def __init__(self, port=0, scenario="normal", delay=0.2):
        super().__init__(("127.0.0.1", port), Handler)
        self.scenario, self.delay = scenario, delay
        self.rooms = {ROOM: self.room(ROOM, "Simulator room")}
        self.events = []
        self.counts = {}

    @staticmethod
    def room(uid, name):
        return {"uuid": uid, "name": name, "status": "Ready", "nomiUuids": [NOMI],
                "note": "", "backchannelingEnabled": True}

    def dispatch(self, method, path, body):
        kind = (method, path)
        count = self.counts[kind] = self.counts.get(kind, 0) + 1
        if path == "/nomis" and method == "GET":
            return 200, {"nomis": [{"uuid": NOMI, "name": "Simulator"}]}, False
        if path == "/nomis/" + NOMI + "/chat" and method == "POST":
            if self.scenario == "malformed-reply" and count == 1:
                return 200, {"sentMessage": {"text": body.get("messageText")}}, False
            if self.scenario == "slow-then-fast" and count <= 3:
                time.sleep(self.delay)
                return 409, {"type": "NomiStillResponding"}, False
            return 200, {
                "sentMessage": {"uuid": str(uuid.uuid4()), "text": body.get("messageText")},
                "replyMessage": {"uuid": str(uuid.uuid4()), "text": "Private reply %d." % count}
            }, self.scenario == "lost-reply" and count == 1
        if path == "/rooms":
            if method == "GET":
                return 200, {"rooms": list(self.rooms.values())}, False
            if method == "POST":
                uid = str(uuid.uuid4())
                result = self.rooms[uid] = self.room(uid, body.get("name", "Simulator room"))
                return 200, result, self.scenario == "lost-create" and count == 1
        parts = path.split("/")
        if len(parts) >= 3 and parts[1] == "rooms" and parts[2] in self.rooms:
            suffix = "/".join(parts[3:])
            if method == "GET" and not suffix:
                return 200, self.rooms[parts[2]], False
            if method == "POST" and suffix == "chat":
                if self.scenario == "outage" and count == 2:
                    return 503, {"type": "Unavailable"}, False
                return 200, {"uuid": str(uuid.uuid4())}, self.scenario == "lost-send" and count == 2
            if method == "POST" and suffix == "chat/request":
                if self.scenario == "malformed-reply" and count == 1:
                    return 200, {"unexpected": "missing replyMessage"}, False
                if self.scenario == "slow-then-fast" and count <= 3:
                    time.sleep(self.delay)
                    error = "NoReply" if count <= 2 else "RoomNomiNotReadyForMessage"
                    return (500 if count <= 2 else 400), {"type": error}, False
                return 200, {"replyMessage": {"uuid": str(uuid.uuid4()),
                    "messageText": "Simulated reply %d." % count}}, self.scenario == "lost-reply" and count == 1
        return 404, {"type": "NotFound"}, False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_api(self):
        if self.headers.get("Authorization") != DUMMY_KEY:
            self.send_error(401, "Use the simulator dummy key")
            return
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 <= size <= 65536:
                raise ValueError("Invalid request length")
            body = json.loads(self.rfile.read(size)) if size else {}
            if not isinstance(body, dict):
                raise ValueError("Expected object")
        except ValueError:
            self.send_error(400)
            return
        if self.path == "/__events" and self.command == "GET":
            status, result, drop = 200, self.server.events, False
        else:
            status, result, drop = self.server.dispatch(self.command, self.path.removeprefix("/v1"), body)
            self.server.events.append({"method": self.command, "path": self.path, "body": body,
                "time": time.monotonic(), "status": status, "accepted": status < 300,
                "response_dropped": drop})
        if drop:
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        data = json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = handle_api


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()
    if args.delay < 0:
        parser.error("--delay must be nonnegative")
    with Simulator(args.port, args.scenario, args.delay) as server:
        print(f"{args.scenario}: http://127.0.0.1:{server.server_port}/v1", flush=True)
        server.serve_forever()
