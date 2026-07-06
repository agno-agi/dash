#!/bin/bash

############################################################################
#
#    MCP Smoke Check
#
#    Proves the AgentOS MCP endpoint end to end: handshake, tool count,
#    then one run_team call against Dash. The default question tells the
#    team to skip its tools, so the whole check finishes in seconds. Runs
#    the client inside the container.
#
#    Usage:
#      ./scripts/mcp_check.sh                              # quick default probe
#      ./scripts/mcp_check.sh "What tables can you query?" # your own question
#
############################################################################

set -e

DEFAULT_QUESTION="Without querying the database, describe what you can answer in two short sentences."
QUESTION="${1:-$DEFAULT_QUESTION}"

echo "MCP check — http://localhost:8000/mcp (client runs inside dash-api)"

docker compose exec -T dash-api python -u - "$QUESTION" <<'PY'
import asyncio
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main() -> None:
    print("  connecting...", flush=True)
    async with streamablehttp_client("http://localhost:8000/mcp", timeout=180) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"MCP OK — {len(tools.tools)} tools", flush=True)
            print("  asking dash (run_team)...", flush=True)
            start = time.perf_counter()
            result = await session.call_tool(
                "run_team",
                {"team_id": "dash", "message": sys.argv[1]},
                read_timeout_seconds=None,
            )
            elapsed = time.perf_counter() - start
            # run_team returns a trimmed ToolResult: content[0].text is the plain
            # answer, and structuredContent carries {run_id, session_id, status}.
            print(f"TEAM RESPONSE ({elapsed:.1f}s):\n", flush=True)
            print(result.content[0].text, flush=True)


asyncio.run(main())
PY
