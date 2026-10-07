"""Small stdio MCP bridge for DeepSeek Harness and the deployed Muse API.

Run with Python 3.10+. Set MUSE2API_BASE_URL and MUSE2API_KEY in the MCP
client's environment. stdout is reserved for newline-delimited MCP messages.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


BASE_URL = os.environ.get("MUSE2API_BASE_URL", "http://127.0.0.1:18610/v1").rstrip("/")
API_KEY = os.environ.get("MUSE2API_KEY", "")

TOOLS = [
    {
        "name": "generate_image",
        "description": "Use for a user request to draw or create an image. Return the image Markdown unchanged in the final answer so DeepSeek Harness displays it inline. Do not call the chat model for drawing.",
        "inputSchema": {
            "type": "object", "properties": {
                "prompt": {"type": "string", "description": "Detailed image description"},
                "size": {"type": "string", "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"]},
            }, "required": ["prompt"], "additionalProperties": False,
        },
    },
    {
        "name": "generate_video",
        "description": "Use for a user request to create a video. Wait for completion, then return a direct HTTPS video playback link. Copy that link unchanged into the final answer. Do not call the chat model for video generation.",
        "inputSchema": {
            "type": "object", "properties": {
                "prompt": {"type": "string", "description": "Detailed video description"},
                "duration": {"type": "integer", "enum": [5, 6, 8, 10]},
                "size": {"type": "string", "enum": ["16:9", "9:16"]},
            }, "required": ["prompt"], "additionalProperties": False,
        },
    },
    {
        "name": "check_media_task",
        "description": "Check an image or video task after a long wait or interrupted tool call. When complete, show the returned image Markdown or video playback link unchanged.",
        "inputSchema": {
            "type": "object", "properties": {
                "kind": {"type": "string", "enum": ["image", "video"]},
                "task_id": {"type": "string"},
            }, "required": ["kind", "task_id"], "additionalProperties": False,
        },
    },
]


def api(method, path, body=None, headers=None):
    if not API_KEY:
        raise ValueError("MUSE2API_KEY is missing from the MCP environment")
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    request = urllib.request.Request(
        BASE_URL + path, data=data, method=method,
        headers={"Authorization": "Bearer " + API_KEY,
                 "Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", "replace")
        raise RuntimeError(f"Muse API HTTP {exc.code}: {detail}") from exc


def result_text(kind, task):
    status = task.get("status")
    if status == "failed":
        raise RuntimeError(task.get("error") or "Muse generation failed")
    if status not in ("completed", "succeeded"):
        return f"{kind} task {task.get('id')} is {status}; progress {task.get('progress', 0)}%. Call check_media_task later."
    url = task.get("url") or (task.get("result") or {}).get("url")
    if not url:
        raise RuntimeError("Generation completed without a media URL")
    parsed = urllib.parse.urlsplit(url)
    if parsed.path.startswith("/v1/media/"):
        url = BASE_URL.rsplit("/v1", 1)[0] + parsed.path
    if not url.startswith("https://"):
        raise RuntimeError("Muse must return an HTTPS media URL for Harness preview")
    if kind == "image":
        return f"Image ready. Copy this Markdown into your answer exactly:\n![Generated image]({url})\n[Open image]({url})"
    return f"Video ready. Copy this playback link into your answer exactly:\n[▶ Play video online]({url})"


def wait_task(kind, task_id, seconds):
    path = "/images/tasks/" if kind == "image" else "/videos/"
    deadline = time.monotonic() + seconds
    while True:
        task = api("GET", path + task_id)
        if task.get("status") in ("completed", "succeeded", "failed"):
            return result_text(kind, task)
        if time.monotonic() >= deadline:
            return result_text(kind, task)
        time.sleep(3)


def call_tool(name, args):
    if name == "check_media_task":
        kind = args["kind"]
        if kind not in ("image", "video"):
            raise ValueError("kind must be image or video")
        return wait_task(kind, args["task_id"], 0)
    prompt = args.get("prompt", "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    if name == "generate_image":
        size = args.get("size", "1:1")
        if size not in ("1:1", "16:9", "9:16", "4:3", "3:4"):
            raise ValueError("unsupported image size")
        task = api("POST", "/images/tasks", {"model": "muse-image", "prompt": prompt,
                    "size": size, "timeout": 600}, {"Idempotency-Key": str(uuid.uuid4())})
        return wait_task("image", task["id"], 650)
    if name == "generate_video":
        duration, size = args.get("duration", 5), args.get("size", "16:9")
        if duration not in (5, 6, 8, 10) or size not in ("16:9", "9:16"):
            raise ValueError("unsupported video duration or size")
        task = api("POST", "/videos", {"model": "muse-video", "prompt": prompt,
                    "duration": duration, "size": size, "timeout": 600})
        return wait_task("video", task["id"], 650)
    raise ValueError(f"unknown tool: {name}")


def handle(message):
    method, params = message.get("method"), message.get("params") or {}
    if method == "initialize":
        return {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                "serverInfo": {"name": "muse-media", "version": "1.0.0"}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        try:
            return {"content": [{"type": "text", "text": call_tool(params["name"], params.get("arguments") or {})}]}
        except Exception as exc:
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    if method == "ping":
        return {}
    raise ValueError("method not found")


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if "id" not in message:
                continue
            try:
                response = {"jsonrpc": "2.0", "id": message["id"], "result": handle(message)}
            except Exception as exc:
                response = {"jsonrpc": "2.0", "id": message["id"],
                            "error": {"code": -32601, "message": str(exc)}}
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as exc:
            print(f"MCP input error: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
