"""Offline smoke test. No API calls or credentials required."""

import muse_harness_mcp as mcp


def fake_api(method, path, body=None, headers=None):
    if method == "POST":
        return {"id": "task_test"}
    suffix = "test.webp" if path.startswith("/images/") else "test.mp4"
    return {"id": "task_test", "status": "completed", "url":
            "https://api.example.com/v1/media/" + suffix}


mcp.BASE_URL = "https://api.example.com/v1"
mcp.api = fake_api
assert "![Generated image](https://api.example.com/v1/media/test.webp)" in mcp.call_tool(
    "generate_image", {"prompt": "cat"})
assert "[▶ Play video online](https://api.example.com/v1/media/test.mp4)" in mcp.call_tool(
    "generate_video", {"prompt": "cat walks"})
assert len(mcp.handle({"method": "tools/list"})["tools"]) == 3
print("MCP bridge OK")
