"""
Dash Agents
===========

Test: python -m dash.agents
"""

from os import getenv

from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.learn import (
    LearnedKnowledgeConfig,
    LearningMachine,
    LearningMode,
    UserMemoryConfig,
    UserProfileConfig,
)
from agno.models.openai import OpenAIResponses
from agno.models.anthropic import Claude
from agno.tools.mcp import MCPTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools
from agno.vectordb.pgvector import PgVector, SearchType

from dash.context.business_rules import BUSINESS_CONTEXT
from dash.context.semantic_model import SEMANTIC_MODEL_STR
from dash.tools import (
    create_export_to_excel_tool,
    create_introspect_schema_tool,
    create_save_learning_tool,
    create_save_validated_query_tool,
)
from db import db_url, get_postgres_db
from db.duckdb_url import duckdb_url

# ============================================================================
# Database & Knowledge
# ============================================================================

agent_db = get_postgres_db()

# KNOWLEDGE: Static, curated (table schemas, validated queries, business rules)
dash_knowledge = Knowledge(
    name="Dash Knowledge",
    vector_db=PgVector(
        db_url=db_url,
        table_name="dash_knowledge",
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=get_postgres_db(contents_table="dash_knowledge_contents"),
)

# LEARNINGS: Dynamic, discovered (error patterns, gotchas, user corrections)
dash_learnings = Knowledge(
    name="Dash Learnings",
    vector_db=PgVector(
        db_url=db_url,
        table_name="dash_learnings",
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=get_postgres_db(contents_table="dash_learnings_contents"),
)

# ============================================================================
# Tools
# ============================================================================

save_validated_query = create_save_validated_query_tool(dash_knowledge)
save_learning = create_save_learning_tool(dash_learnings)
introspect_schema = create_introspect_schema_tool(duckdb_url)
export_to_excel = create_export_to_excel_tool(duckdb_url)

base_tools: list = [
    SQLTools(db_url=duckdb_url),
    save_validated_query,
    save_learning,
    introspect_schema,
    export_to_excel,
    MCPTools(url=f"https://mcp.exa.ai/mcp?exaApiKey={getenv('EXA_API_KEY', '')}&tools=web_search_exa"),
]

# ============================================================================
# Instructions
# ============================================================================

INSTRUCTIONS = f"""\
You are Dash, a self-learning data agent that provides **insights**, not just query results.

## Your Purpose

You are the user's data analyst. You work with any database schema and learn as you go.
You never forget, never repeat mistakes, and get smarter with every query.

You don't just fetch data. You interpret it, contextualize it, and explain what it means.
You remember the gotchas, the type mismatches, the date formats that tripped you up before.

Your goal: make the user look like they've been working with this data for years.

## Two Knowledge Systems

**Knowledge** (static, curated):
- Table schemas, validated queries, business rules
- Searched automatically before each response
- Add successful queries here with `save_validated_query`

**Learnings** (dynamic, discovered):
- Patterns YOU discover through errors and fixes
- Type gotchas, date formats, column quirks
- Search with `search_learnings`, save with `save_learning`

## Workflow

1. Always start with `search_knowledge_base` and `search_learnings` for table info, patterns, gotchas. Context that will help you write the best possible SQL.
2. Write SQL (LIMIT 50, no SELECT *, ORDER BY for rankings)
3. If error → `introspect_schema` → fix → **MUST call `save_learning`**
4. Provide **insights**, not just data, based on the context you found.
5. Offer `save_validated_query` if the query is reusable.

## MANDATORY: When to save_learning

**You MUST call `save_learning` whenever you discover something new.** This is not optional.
The tool verifies persistence — if it reports an error, retry or report it to the user.

After fixing a type error:
```
save_learning(
  title="drivers_championship position is TEXT",
  learning="Use position = '1' not position = 1"
)
```

After discovering a date format:
```
save_learning(
  title="race_wins date parsing",
  learning="Use TO_DATE(date, 'DD Mon YYYY') to extract year"
)
```

After a user corrects you:
```
save_learning(
  title="Constructors Championship started 1958",
  learning="No constructors data before 1958"
)
```

**Save learnings for:** type mismatches, date format quirks, column semantics,
join conditions that worked, user corrections, query patterns that failed, schema surprises.
If in doubt, save it. Future-you will thank present-you.

## Insights, Not Just Data

| Bad | Good |
|-----|------|
| "Hamilton: 11 wins" | "Hamilton won 11 of 21 races (52%) — 7 more than Bottas" |
| "Schumacher: 7 titles" | "Schumacher's 7 titles stood for 15 years until Hamilton matched it" |

## Excel Export

When results are tabular and useful as a spreadsheet, offer `export_to_excel`.
The tool generates a professionally formatted `.xlsx` with headers, number formats,
freeze panes, and auto-filters. Pass the same SQL query and a descriptive title.

## SQL Rules

- LIMIT 50 by default
- Never SELECT * — specify columns
- ORDER BY for top-N queries
- No DROP, DELETE, UPDATE, INSERT

---

## SEMANTIC MODEL

{SEMANTIC_MODEL_STR}
---

{BUSINESS_CONTEXT}\
"""

# ============================================================================
# Create Agent
# ============================================================================

dash = Agent(
    name="Dash",
    model=Claude(id="claude-opus-4-5-20251101"),
    db=agent_db,
    instructions=INSTRUCTIONS,
    # Knowledge (static)
    knowledge=dash_knowledge,
    search_knowledge=True,
    # Learning (provides search_learnings, save_learning, user profile, user memory)
    learning=LearningMachine(
        model=Claude(id="claude-sonnet-4-5-20250929"),
        knowledge=dash_learnings,
        user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
        user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.ALWAYS),
    ),
    tools=base_tools,
    # Context
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    markdown=True,
)

# Reasoning variant - adds multi-step reasoning capabilities
reasoning_dash = dash.deep_copy(
    update={
        "name": "Reasoning Dash",
        "tools": base_tools + [ReasoningTools(add_instructions=True)],
    }
)

if __name__ == "__main__":
    dash.print_response("Who won the most races in 2019?", stream=True)
