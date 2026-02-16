"""
Slack Dash Agent
================

Enhanced Dash agent with web search, image generation, and file export tools
for rich Slack interactions.

Run: python -m dash.slack_agent
"""

from agno.models.openai import OpenAIChat
from agno.tools.dalle import DalleTools
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.file_generation import FileGenerationTools
from agno.tools.slack import SlackTools

from dash.agents import INSTRUCTIONS, base_tools, dash

SLACK_INSTRUCTIONS = """\

## Slack Capabilities

You have additional tools for Slack interactions:

**File Export** — When users ask for data exports:
- Use `generate_csv_file` for tabular data (query results, comparisons)
- Use `generate_json_file` for structured data
- Always include descriptive filenames (e.g., "hamilton_2019_wins.csv")

**Image Generation** — When users ask for visualizations or creative images:
- Use `create_image` to generate images with DALL-E
- Good for: team logos, race visualizations, infographics
- Be descriptive in your prompts for best results

**Web Search** — When users ask about recent events or external context:
- Use `web_search` for current F1 news, driver updates, rule changes
- Use `search_news` for latest headlines
- Combine with database queries for comprehensive answers

**Slack** — When asked to share results or notify channels:
- Use `send_message` to post to channels
- Use `send_message_thread` to reply in threads
"""

slack_dash = dash.deep_copy(
    update={
        "name": "Slack Dash",
        "model": OpenAIChat(id="gpt-4o"),
        "instructions": INSTRUCTIONS + SLACK_INSTRUCTIONS,
        "tools": base_tools
        + [
            DalleTools(),
            DuckDuckGoTools(),
            FileGenerationTools(),
            SlackTools(),
        ],
    }
)

if __name__ == "__main__":
    slack_dash.print_response("Who won the most races in 2019? Export results as CSV.", stream=True)
