#!/usr/bin/env python3
"""Serve EventPilot and bridge its chat API to a local Ollama instance."""

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
SYSTEM_PROMPT = (
    "You are Pilot, a warm, practical event-planning assistant inside EventPilot. "
    "Help people plan celebrations, parties, dinners, and gatherings. Be upbeat and "
    "specific, ask one useful follow-up question when details are missing, and keep "
    "answers clear and easy to act on. Never claim you booked, purchased, or contacted "
    "anyone; offer plans and suggestions only."
)


class EventPilotHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json_response(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/models":
            try:
                with urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as response:
                    data = json.load(response)
                models = [item["name"] for item in data.get("models", []) if "name" in item]
                self._json_response(200, {"models": models})
            except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
                self._json_response(502, {"error": f"Could not connect to Ollama: {error}"})
            return
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/chat":
            self._json_response(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 100_000:
                self._json_response(413, {"error": "The chat request is empty or too large."})
                return
            payload = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._json_response(400, {"error": "Invalid chat request."})
            return

        if not isinstance(payload, dict):
            self._json_response(400, {"error": "Invalid chat request."})
            return
        model = payload.get("model")
        messages = payload.get("messages")
        if not isinstance(model, str) or not isinstance(messages, list) or not messages:
            self._json_response(400, {"error": "Choose a model and send a message."})
            return
        if len(messages) > 80 or any(
            not isinstance(item, dict)
            or item.get("role") not in ("user", "assistant")
            or not isinstance(item.get("content"), str)
            for item in messages
        ):
            self._json_response(400, {"error": "The chat history is invalid."})
            return
        if any(len(item["content"]) > 4000 for item in messages):
            self._json_response(400, {"error": "Messages must be 4,000 characters or fewer."})
            return

        try:
            with urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as response:
                available_models = {
                    item["name"] for item in json.load(response).get("models", []) if "name" in item
                }
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            self._json_response(502, {"error": f"Could not connect to Ollama: {error}"})
            return
        if model not in available_models:
            self._json_response(400, {"error": "That model is not installed in Ollama. Refresh the page and choose an available model."})
            return

        request_data = json.dumps(
            {
                "model": model,
                "stream": False,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            }
        ).encode("utf-8")
        request = Request(
            f"{OLLAMA_URL}/api/chat",
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=300) as response:
                result = json.load(response)
            content = result.get("message", {}).get("content")
            if not isinstance(content, str):
                self._json_response(502, {"error": "Ollama returned an invalid reply."})
                return
            self._json_response(200, {"message": content})
        except HTTPError as error:
            detail = error.read(4096).decode("utf-8", errors="replace")
            self._json_response(502, {"error": f"Ollama could not answer: {detail or error.reason}"})
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            self._json_response(502, {"error": f"Could not get a reply from Ollama: {error}"})

    def log_message(self, format, *args):
        print(f"EventPilot: {format % args}")


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer((host, port), EventPilotHandler)
    print(f"EventPilot is running at http://{host}:{port} (Ollama: {OLLAMA_URL})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping EventPilot.")
    finally:
        server.server_close()
