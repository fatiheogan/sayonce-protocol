"""Reproducible multi-round workloads.

A workload is the list of client messages for one conversation: each round has
an intent, the message content and a small client-side delta. The same seed
always gives the same workload, and every system receives exactly the same one.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..agents import _text, sample_context
from ..messages import DeltaOp, Intent


@dataclass
class Round:
    intent: Intent
    content: Any
    delta: list = field(default_factory=list)
    task_id: int | None = None


@dataclass
class Workload:
    name: str
    context: dict
    dictionary: list[str]
    rounds: list[Round]


def travel_planning(context_kb: int, rounds: int, seed: int = 0, msg_words: int = 20) -> Workload:
    """A client agent iteratively refines a trip with a worker agent.

    Most rounds are REQUESTs; every 5th round is an INFORM (new constraint);
    every round adjusts one shared variable via a delta.
    """
    ctx, dictionary = sample_context(context_kb, seed=seed)
    rng = random.Random(seed + 1)
    out = []
    for i in range(rounds):
        if i % 5 == 4:
            intent = Intent.INFORM
            content = "New constraint: " + _text(rng, msg_words // 2)
        else:
            intent = Intent.REQUEST
            content = f"Step {i + 1}: " + _text(rng, msg_words)
        delta = [[DeltaOp.SET, ["vars", "budget"], 500 - 5 * i]]
        out.append(Round(intent=intent, content=content, delta=delta, task_id=i))
    return Workload(name="travel", context=ctx, dictionary=dictionary, rounds=out)


# ---------------------------------------------------------------------- real MCP tools

_MCP_DATA = Path(__file__).parent / "data" / "mcp_tools.json"

MCP_SYSTEM_PROMPT = (
    "You are a software engineering assistant working in the user's repository. Use the available tools "
    "to read and change files, inspect git history, search documentation, check error reports and "
    "update tickets. Prefer small, verifiable steps. Before changing a file, read it. After a change, "
    "say what you changed and why. If a tool fails, report the error instead of guessing. Ask before "
    "deleting data, pushing commits or editing tickets that belong to other people. Keep answers short "
    "and include file paths and line numbers when you refer to code."
)

MCP_REQUESTS = [
    "Read src/app/server.py and list every endpoint that does not check authentication.",
    "Show the last ten commits on main and tell me which ones touched the payment module.",
    "Search the repository for TODO comments older than this release and group them by folder.",
    "Open the Sentry issue for the checkout timeout and summarise the stack trace.",
    "Find the Jira ticket about the login redirect loop and add a comment with the root cause.",
    "Fetch the changelog of the HTTP client library and check whether version 2.4 breaks our retry code.",
    "Create a branch called fix/session-timeout and update the default timeout in config/settings.yaml.",
    "Run a diff between the staging and production configuration files and highlight risky changes.",
    "Look up the React documentation for useEffect cleanup and compare it with our hook in web/useSocket.ts.",
    "Take a screenshot of the signup page on staging and check that the new consent checkbox is visible.",
    "Write a unit test for parse_invoice that covers an empty line items list.",
    "Summarise the Notion page with the incident review from last Tuesday in five bullet points.",
    "List open pull requests that change database migrations and note which ones conflict.",
    "Check the error rate of the orders service in the last 24 hours and compare it with last week.",
    "Rename the function calc_total to compute_order_total everywhere and update the imports.",
    "Scrape the pricing page of the vendor and extract the per-seat price for the team plan.",
    "Open docs/architecture.md and add a section that explains the new cache layer.",
    "Find which commit introduced the flaky test test_concurrent_refunds and show its author.",
    "Move the Jira tickets with label tech-debt that are older than 90 days to the backlog.",
    "Read the failing CI log for build 1842 and tell me which step failed and why.",
]

MCP_CONSTRAINTS = [
    "Do not modify anything under migrations/ without asking first.",
    "The release branch is frozen until Friday, so commit only to feature branches.",
    "Use the staging environment; production credentials are not available in this session.",
    "Keep the public API of the payments package unchanged.",
    "Tickets in the SEC project are confidential; do not quote them in comments elsewhere.",
]

MCP_FILES = ["src/app/server.py", "config/settings.yaml", "web/useSocket.ts", "src/billing/invoice.py",
             "docs/architecture.md", "tests/test_refunds.py", "src/orders/service.py"]


def mcp_tools(path: Path = _MCP_DATA) -> list[tuple[str, dict]]:
    """All captured tools as (server__tool, definition) in the order of the data file."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [(f"{s['server']}__{t['name']}", {"description": t["description"], "inputSchema": t["inputSchema"]})
            for s in doc["servers"] for t in s["tools"]]


def mcp_context(size_kb: int) -> tuple[dict, list[str]]:
    """A coding-agent context of roughly size_kb kilobytes built from real MCP tool definitions.

    Tools are added in the data file's order (a minimal developer setup first,
    then more integrations) until the context reaches the target size, the same
    rule sample_context uses for its generated tools.
    """
    target = size_kb * 1024
    tools: dict = {}
    for name, spec in mcp_tools():
        if len(json.dumps({"sys": MCP_SYSTEM_PROMPT, "tools": tools}, separators=(",", ":"))) >= target:
            break
        tools[name] = spec
    else:
        if len(json.dumps({"sys": MCP_SYSTEM_PROMPT, "tools": tools}, separators=(",", ":"))) < target:
            raise ValueError(f"only {target // 1024} KB requested but not enough captured tools")
    ctx = {"sys": MCP_SYSTEM_PROMPT, "tools": tools, "hist": [],
           "vars": {"active_file": MCP_FILES[0], "status": "new"}}
    dictionary = ["sys", "tools", "hist", "vars", "active_file", "status", "last_task",
                  "description", "inputSchema", *tools.keys()]
    return ctx, dictionary


def mcp_agent(context_kb: int, rounds: int, seed: int = 0) -> Workload:
    """A client agent drives a coding agent whose context holds real MCP tool definitions.

    Same shape as travel_planning (every 5th round an INFORM, one small delta per
    round) so the two workloads differ only in the data.
    """
    ctx, dictionary = mcp_context(context_kb)
    rng = random.Random(seed + 1)
    out = []
    for i in range(rounds):
        if i % 5 == 4:
            intent, content = Intent.INFORM, "New constraint: " + rng.choice(MCP_CONSTRAINTS)
        else:
            intent, content = Intent.REQUEST, f"Step {i + 1}: " + rng.choice(MCP_REQUESTS)
        delta = [[DeltaOp.SET, ["vars", "active_file"], rng.choice(MCP_FILES)]]
        out.append(Round(intent=intent, content=content, delta=delta, task_id=i))
    return Workload(name="mcp", context=ctx, dictionary=dictionary, rounds=out)


WORKLOADS = {"travel": travel_planning, "mcp": mcp_agent}
