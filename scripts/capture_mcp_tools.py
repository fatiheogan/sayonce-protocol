"""Capture real MCP tool definitions for the "mcp" benchmark workload.

Starts each MCP server over stdio, sends `initialize` and `tools/list` as plain
newline-delimited JSON-RPC (the MCP stdio transport) and stores what the server
returned. The result is src/sayonce/bench/data/mcp_tools.json.

The servers need no real account to list their tools; placeholder credentials
are passed only so that servers which check their environment at start-up do
not exit. No server is ever asked to call a tool.

Setup (any folder outside the repository):

    npm init -y
    npm install @modelcontextprotocol/server-filesystem@2.1.0 @modelcontextprotocol/server-memory@2.0.1 \\
        @modelcontextprotocol/server-sequential-thinking@2.0.0 @playwright/mcp@0.0.84 \\
        @notionhq/notion-mcp-server@2.6.1 @upstash/context7-mcp@4.5.0 firecrawl-mcp@3.36.1 \\
        @sentry/mcp-server@0.42.0
    python -m venv venv && venv/bin/pip install mcp-server-git==2026.10.28 \\
        mcp-server-fetch==2026.10.28 mcp-server-time==2026.10.28
    python -m venv venv_atl && venv_atl/bin/pip install mcp-atlassian==0.23.1   # needs mcp<2

Then, from the repository root:

    python scripts/capture_mcp_tools.py --servers-dir <that folder>
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import subprocess
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "sayonce" / "bench" / "data" / "mcp_tools.json"

# Order matters: the workload adds tools in this order until the context reaches
# its target size, so a small context looks like a minimal developer setup and a
# large one like an agent with many integrations.
NODE = {  # name: (npm package, licence, extra args)
    "filesystem": ("@modelcontextprotocol/server-filesystem", "MIT", ["{ws}"]),
    "sequential-thinking": ("@modelcontextprotocol/server-sequential-thinking", "MIT", []),
    "memory": ("@modelcontextprotocol/server-memory", "MIT", []),
    "context7": ("@upstash/context7-mcp", "MIT", []),
    "playwright": ("@playwright/mcp", "Apache-2.0", []),
    "sentry": ("@sentry/mcp-server", "FSL-1.1-ALv2", ["--access-token=placeholder"]),
    "notion": ("@notionhq/notion-mcp-server", "MIT", []),
    "firecrawl": ("firecrawl-mcp", "MIT", []),
}
PYTHON = {  # name: (pip distribution, licence, venv folder, extra args)
    "time": ("mcp-server-time", "MIT", "venv", []),
    "fetch": ("mcp-server-fetch", "MIT", "venv", []),
    "git": ("mcp-server-git", "MIT", "venv", ["--repository", "{ws}"]),
    "atlassian": ("mcp-atlassian", "MIT", "venv_atl", []),
}
ORDER = ["time", "fetch", "filesystem", "git", "sequential-thinking", "memory", "context7",
         "playwright", "sentry", "notion", "firecrawl", "atlassian"]

PLACEHOLDER_ENV = {
    "OPENAPI_MCP_HEADERS": '{"Authorization":"Bearer placeholder","Notion-Version":"2022-06-28"}',
    "NOTION_TOKEN": "placeholder", "FIRECRAWL_API_KEY": "fc-placeholder", "SENTRY_ACCESS_TOKEN": "placeholder",
    "JIRA_URL": "https://example.atlassian.net", "JIRA_USERNAME": "user@example.com", "JIRA_API_TOKEN": "placeholder",
    "CONFLUENCE_URL": "https://example.atlassian.net/wiki", "CONFLUENCE_USERNAME": "user@example.com",
    "CONFLUENCE_API_TOKEN": "placeholder",
}


def command(name: str, root: Path, ws: Path) -> tuple[list[str], str, str, str]:
    """Command line, package, version and licence of one server."""
    if name in NODE:
        pkg, lic, extra = NODE[name]
        pj = json.loads((root / "node_modules" / pkg / "package.json").read_text())
        b = pj["bin"] if isinstance(pj["bin"], str) else next(iter(pj["bin"].values()))
        cmd = ["node", str(root / "node_modules" / pkg / b)]
        version = pj["version"]
    else:
        pkg, lic, venv, extra = PYTHON[name]
        vbin = root / venv / ("Scripts" if os.name == "nt" else "bin")
        cmd = [str(vbin / pkg)]
        version = subprocess.run([str(vbin / "python"), "-c",
                                  f"import importlib.metadata as m; print(m.version({pkg!r}))"],
                                 capture_output=True, text=True, check=True).stdout.strip()
    return cmd + [a.format(ws=ws) for a in extra], pkg, version, lic


async def list_tools(cmd: list[str], cwd: Path, timeout: float = 60) -> tuple[dict, list[dict]]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **PLACEHOLDER_ENV}, cwd=str(cwd), limit=2**25)

    async def call(i: int, method: str, params: dict) -> dict:
        proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}) + "\n").encode())
        await proc.stdin.drain()
        while True:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout)
            if not line:
                raise RuntimeError("server exited: " + (await proc.stderr.read()).decode()[-500:])
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # some servers log to stdout
            if msg.get("id") == i:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    try:
        init = await call(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                             "clientInfo": {"name": "sayonce-capture", "version": "1"}})
        proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        await proc.stdin.drain()
        tools, cursor, i = [], None, 2
        while True:
            res = await call(i, "tools/list", {"cursor": cursor} if cursor else {})
            tools += res["tools"]
            cursor, i = res.get("nextCursor"), i + 1
            if not cursor:
                return init.get("serverInfo", {}), tools
    finally:
        if proc.returncode is None:
            proc.kill()


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--servers-dir", type=Path, required=True, help="folder with node_modules/, venv/ and venv_atl/")
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    ws = Path(tempfile.mkdtemp(prefix="mcp-ws-"))
    subprocess.run(["git", "init", "-q", str(ws)], check=True)  # mcp-server-git needs a repository

    servers = []
    for name in ORDER:
        cmd, pkg, version, lic = command(name, a.servers_dir.resolve(), ws)
        info, tools = await list_tools(cmd, ws)
        # Keep what an agent forwards to its LLM for each tool: name, description, input schema.
        kept = [{"name": t["name"], "description": t.get("description", ""), "inputSchema": t["inputSchema"]}
                for t in tools]
        servers.append({"server": name, "package": pkg, "version": version, "license": lic,
                        "serverInfo": info, "tools": kept})
        size = len(json.dumps(kept, separators=(",", ":"), ensure_ascii=False).encode())
        print(f"{name:20s} {pkg}@{version:<12s} {len(kept):3d} tools {size / 1024:6.1f} KB")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"captured": datetime.date.today().isoformat(), "method": "MCP stdio initialize + tools/list",
           "servers": servers}
    a.out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {a.out} ({a.out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    asyncio.run(main())
