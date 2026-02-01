"""
Data Agent API
==============

Production deployment entry point for the Data Agent.

Run:
    python -m app.main
"""

from os import getenv
from pathlib import Path

from agno.os import AgentOS

from dash.agent import data_agent, data_agent_knowledge
from db import get_postgres_db

# ============================================================================
# Create AgentOS
# ============================================================================
agent_os = AgentOS(
    name="Data Agent",
    tracing=True,
    db=get_postgres_db(),
    agents=[data_agent],
    knowledge=[data_agent_knowledge],
    config=str(Path(__file__).parent / "config.yaml"),
)

app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(
        app="main:app",
        reload=getenv("RUNTIME_ENV", "prd") == "dev",
    )
