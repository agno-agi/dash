"""
Data Agent
==========

A self-learning data agent inspired by OpenAI's internal data agent.

The agent implements 6 layers of context:
1. Table Metadata - Schema, columns, types from knowledge/tables/
2. Human Annotations - Business rules from knowledge/business/
3. Query Patterns - Validated SQL from knowledge/queries/
4. Institutional Knowledge - External context via MCP (optional)
5. Memory - LearningMachine for corrections and preferences
6. Runtime Context - Live schema inspection via introspect_schema tool

Key behaviors:
- Always searches knowledge base before generating SQL
- Learns from corrections via LearningMachine
- Provides insights, not just raw data
- Offers to save successful queries for future use
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
from agno.tools.mcp import MCPTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools
from agno.vectordb.pgvector import PgVector, SearchType

from da.context.business_rules import BUSINESS_CONTEXT
from da.context.semantic_model import SEMANTIC_MODEL_STR
from da.tools import (
    analyze_results,
    introspect_schema,
    save_validated_query,
    set_engine,
    set_knowledge,
)
from db import db_url, get_postgres_db

# ============================================================================
# Database & Knowledge Base
# ============================================================================

agent_db = get_postgres_db(contents_table="data_agent_contents")

data_agent_knowledge = Knowledge(
    name="Data Agent Knowledge",
    vector_db=PgVector(
        db_url=db_url,
        table_name="data_agent_knowledge",
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=agent_db,
    max_results=10,
)

# Initialize tool references
set_knowledge(data_agent_knowledge)
set_engine(db_url)

# ============================================================================
# System Message
# ============================================================================

SYSTEM_MESSAGE = f"""\
You are a Data Agent with access to a PostgreSQL database.

Your goal is to help users get **insights** from data, not just raw query results.
You learn from corrections and improve over time.

---

## WORKFLOW (Follow This Exactly)

### 1. SEARCH KNOWLEDGE FIRST
Before writing ANY SQL:
- Search for similar questions that have been answered before
- Look for validated query patterns
- Check data quality notes for relevant tables

### 2. IDENTIFY TABLES
- Use the semantic model below to find relevant tables
- Note column types carefully (TEXT vs INTEGER)
- Check for column name variations

### 3. CHECK DATA QUALITY NOTES
These are CRITICAL for correct queries:
- Type mismatches (position is TEXT in some tables!)
- Date formats (may need TO_DATE parsing)
- NULL handling requirements
- Special values (e.g., 'Ret', 'DSQ' in position columns)

### 4. GENERATE SQL
Follow these rules:
- Use LIMIT 50 by default
- Never use SELECT * - specify columns explicitly
- Always include ORDER BY for top-N queries
- Never run destructive queries (DROP, DELETE, UPDATE, INSERT)

### 5. VALIDATE RESULTS
If you get unexpected results:
- Zero rows → Check column types and data quality notes
- Wrong values → Verify type comparisons (string vs integer)
- Use introspect_schema tool to check actual column types

### 6. ANALYZE & EXPLAIN
Don't just return data - provide insights:
- Summarize key findings
- Provide context
- Suggest follow-up questions
- Use the analyze_results tool for complex results

### 7. OFFER TO SAVE
After a successful, validated query:
- Ask if the user wants to save it
- Use save_validated_query to store it in the knowledge base
- Future similar questions will benefit

---

## SELF-CORRECTION

When something goes wrong:
1. Check the data quality notes for the table
2. Use introspect_schema to verify actual column types
3. Try a simpler query to confirm data exists
4. Look for similar validated queries in the knowledge base

---

## SEMANTIC MODEL

{SEMANTIC_MODEL_STR}

---

{BUSINESS_CONTEXT}

---

## SQL RULES SUMMARY

| Rule | Details |
|------|---------|
| Search first | Always check knowledge base before writing SQL |
| Show SQL | Always display the query you're using |
| Limit results | Use LIMIT 50 unless user specifies |
| No SELECT * | Specify columns explicitly |
| Order results | Include ORDER BY for top-N queries |
| No destructive | Never DROP, DELETE, UPDATE, or INSERT |
| Handle types | Check column types before comparisons |
| Handle NULLs | Use COALESCE when needed |
"""

# ============================================================================
# Build Tools List
# ============================================================================

tools: list = [
    SQLTools(db_url=db_url),
    ReasoningTools(add_instructions=True),
    save_validated_query,
    analyze_results,
    introspect_schema,
]

# Add MCP tools for external knowledge (Layer 4) if configured
exa_api_key = getenv("EXA_API_KEY")
if exa_api_key:
    exa_url = f"https://mcp.exa.ai/mcp?exaApiKey={exa_api_key}&tools=web_search_exa,company_research_exa"
    tools.append(MCPTools(url=exa_url))

# ============================================================================
# Learning Configuration (Layer 5)
# ============================================================================

learning = LearningMachine(
    knowledge=data_agent_knowledge,
    user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
    user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
    learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
)

# ============================================================================
# Create Agent
# ============================================================================

data_agent = Agent(
    id="data-agent",
    name="Data Agent",
    model=OpenAIResponses(id="gpt-5.2"),
    db=agent_db,
    knowledge=data_agent_knowledge,
    system_message=SYSTEM_MESSAGE,
    tools=tools,
    # Learning (Layer 5: Memory)
    learning=learning,
    # Context settings
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    read_tool_call_history=True,
    # Knowledge settings (Layer 1-3)
    search_knowledge=True,
    # Output
    markdown=True,
)

# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    data_agent.cli_app(stream=True)
