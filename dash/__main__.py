"""CLI entry point: python -m dash"""

from dash.agent import data_agent

if __name__ == "__main__":
    data_agent.cli_app(stream=True)
