"""Two agents talking over SayOnce on localhost.

Agent B (server) runs a mock LLM. Agent A (client) opens a session with a
shared context, then sends a few requests. The output shows that the context
is sent once and later rounds carry only the new message and small deltas.

    python examples/demo.py --rounds 10 --context-kb 20
"""

from __future__ import annotations

import argparse
import asyncio

from sayonce.agents import WorkerAgent, sample_context
from sayonce.messages import DeltaOp, Intent
from sayonce.session import ClientSession, Server


async def main(rounds: int, context_kb: int) -> None:
    async with Server(WorkerAgent(), agent_id="agent-b") as server:
        ctx, dictionary = sample_context(context_kb)
        client = await ClientSession.open("127.0.0.1", server.port, "agent-a", ctx, dictionary)
        hello_sent = client.conn.stats.bytes_sent
        hello_recv = client.conn.stats.bytes_received
        print(f"HELLO      sent {hello_sent:>7} B   received {hello_recv:>5} B   (context sent once)")

        for i in range(rounds):
            delta = [[DeltaOp.SET, ["vars", "budget"], 500 - 10 * i]]
            res = await client.request(Intent.REQUEST, f"Find option {i} under budget", delta=delta, task_id=i)
            print(
                f"round {i + 1:>3}  sent {res.bytes_sent:>7} B   received {res.bytes_received:>5} B   "
                f"{res.latency_s * 1000:6.2f} ms   {res.content[:40]!r}"
            )

        st = client.conn.stats
        print(f"\ntotal      sent {st.bytes_sent:>7} B   received {st.bytes_received:>5} B")
        print(f"context version {client.store.version}, history turns {len(client.store.ctx['hist'])}")
        await client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rounds", type=int, default=10)
    p.add_argument("--context-kb", type=int, default=20)
    args = p.parse_args()
    asyncio.run(main(args.rounds, args.context_kb))
