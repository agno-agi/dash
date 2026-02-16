"""
Dash API
========

Production deployment entry point for Dash.

Run:
    python -m app.main
"""

from os import getenv
from pathlib import Path

from agno.os import AgentOS
from agno.os.interfaces.slack import Slack

from dash.agents import dash, dash_knowledge, reasoning_dash
from dash.slack_agent import slack_dash
from db import get_postgres_db

# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agent_os = AgentOS(
    name="Dash",
    tracing=True,
    db=get_postgres_db(),
    agents=[dash, reasoning_dash, slack_dash],
    knowledge=[dash_knowledge],
    config=str(Path(__file__).parent / "config.yaml"),
    interfaces=[Slack(agent=slack_dash, reply_to_mentions_only=True)],
)

app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(
        app="main:app",
        reload=getenv("RUNTIME_ENV", "prd") == "dev",
    )
