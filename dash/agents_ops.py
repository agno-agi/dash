"""
Ops Dash Agent
==============

Ops-flavored Dash variant that queries the platform operations warehouse.
Points SQLTools at the ops warehouse tables (desired_services, actual_services,
drift_observations, etc.) and uses ops-specific semantic models and business rules.

Test: python -m dash.agents_ops
"""

from os import getenv
from pathlib import Path

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
from agno.tools.reasoning import ReasoningTools
from agno.tools.sql import SQLTools
from agno.vectordb.pgvector import PgVector, SearchType

from dash.context.business_rules import build_business_context
from dash.context.semantic_model import build_semantic_model, format_semantic_model
from dash.tools import (
    create_incident_tools,
    create_infra_agent_tools,
    create_introspect_schema_tool,
    create_knowledge_pack_tools,
    create_save_validated_query_tool,
)
from db import get_postgres_db

# ============================================================================
# Ops-specific paths
# ============================================================================

_OPS_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
_OPS_TABLES_DIR = _OPS_KNOWLEDGE_DIR / "tables"
_OPS_BUSINESS_DIR = _OPS_KNOWLEDGE_DIR / "business"

# ============================================================================
# Database
# ============================================================================

# Ops warehouse connection — uses OPS_DB_* env vars if set, otherwise falls
# back to the default DB_* vars (same Postgres instance, same database).
_ops_db_url = (
    f"{getenv('OPS_DB_DRIVER', getenv('DB_DRIVER', 'postgresql+psycopg'))}://"
    f"{getenv('OPS_DB_USER', getenv('DB_USER', 'ai'))}:"
    f"{getenv('OPS_DB_PASS', getenv('DB_PASS', 'ai'))}@"
    f"{getenv('OPS_DB_HOST', getenv('DB_HOST', 'localhost'))}:"
    f"{getenv('OPS_DB_PORT', getenv('DB_PORT', '5432'))}/"
    f"{getenv('OPS_DB_DATABASE', getenv('DB_DATABASE', 'ai'))}"
)

agent_db = get_postgres_db()

# ============================================================================
# Knowledge (ops-specific pgvector tables)
# ============================================================================

ops_knowledge = Knowledge(
    name="Ops Knowledge",
    vector_db=PgVector(
        db_url=_ops_db_url,
        table_name="ops_dash_knowledge",
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=get_postgres_db(contents_table="ops_dash_knowledge_contents"),
)

ops_learnings = Knowledge(
    name="Ops Learnings",
    vector_db=PgVector(
        db_url=_ops_db_url,
        table_name="ops_dash_learnings",
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
    contents_db=get_postgres_db(contents_table="ops_dash_learnings_contents"),
)

# ============================================================================
# Ops Semantic Model & Business Context
# ============================================================================

# Only load ops_* table definitions (filter by prefix)
_ops_semantic_model = build_semantic_model(_OPS_TABLES_DIR)
_ops_semantic_str = format_semantic_model(_ops_semantic_model)
_ops_business_context = build_business_context(_OPS_BUSINESS_DIR)

# ============================================================================
# Tools
# ============================================================================

save_validated_query = create_save_validated_query_tool(ops_knowledge)
introspect_schema = create_introspect_schema_tool(_ops_db_url)

# Infra-agent tool bridge (Phase 5.2) — connects Ops Dash to the
# Dockhand infra-agent portal API for submitting jobs, querying drift,
# listing workflows, and searching platform knowledge.
_infra_agent_url = getenv("INFRA_AGENT_URL", "http://infra-agent:8042")
_infra_agent_secret = getenv("INFRA_AGENT_PORTAL_SECRET", "")
_infra_agent_tools = create_infra_agent_tools(_infra_agent_url, _infra_agent_secret) if _infra_agent_secret else []

# Incident timeline tools (Phase 5.3) — reconstruct timelines from
# the ops_unified_timeline view, create/resolve incident markers,
# and search for matching incident patterns.
_incident_tools = create_incident_tools(_ops_db_url)

# Knowledge pack pipeline (Phase 5.4) — auto-generate validated queries,
# incident signatures, and runbook suggestions from resolved incidents.
_knowledge_pack_tools = create_knowledge_pack_tools(_ops_db_url, ops_knowledge, ops_learnings)

ops_base_tools: list = [
    SQLTools(db_url=_ops_db_url),
    save_validated_query,
    introspect_schema,
    *_infra_agent_tools,
    *_incident_tools,
    *_knowledge_pack_tools,
]

# ============================================================================
# Instructions
# ============================================================================

OPS_INSTRUCTIONS = f"""\
You are Ops Dash, a self-learning infrastructure analyst that provides **operational insights** \
from the platform's operational data warehouse.

## Your Purpose

You are the platform operator's data analyst — one that knows every service, every deploy, \
every drift item, and every incident. You turn operational exhaust into actionable intelligence.

You don't just fetch data. You interpret it through the lens of operational risk, correlate \
events across systems, and explain what the data means for platform reliability.

## Two Knowledge Systems

**Knowledge** (static, curated):
- Ops warehouse table schemas, validated queries, business rules
- Searched automatically before each response
- Add successful queries here with `save_validated_query`

**Learnings** (dynamic, discovered):
- Patterns YOU discover through errors and fixes
- Incident signatures, schema quirks, correlation patterns
- Search with `search_learnings`, save with `save_learning`

## Workflow

1. Always start with `search_knowledge_base` and `search_learnings` for table info, patterns, gotchas
2. Write SQL (LIMIT 50, no SELECT *, ORDER BY for rankings)
3. If error → `introspect_schema` → fix → `save_learning`
4. Provide **operational insights**, not just data
5. Offer `save_validated_query` if the query is reusable

## Key Concepts

**Drift Debt Score**: Risk-weighted sum of unresolved drift items.
Formula: severity_weight × blast_radius × age_days × exposure_multiplier
Where exposure_multiplier: 3.0 (public Traefik), 2.0 (platform-core), 1.5 (prod), 1.0 (test)

**Priority Tiers**: P0 (Traefik/edge), P1 (monitoring), P2 (automation), P3 (apps), P4 (datastores)
Updates are applied in reverse order: P4 first (lowest risk), P0 last.

**Platform Hosts**: platform-core (control plane), prod (production workloads)

## Insights, Not Just Data

| Bad | Good |
|-----|------|
| "3 drift items found" | "3 drift items, but Traefik's is 60% of total risk due to public exposure × 12-day age" |
| "5 deploys this week" | "5 deploys, 80% success rate — the Ghost failure correlates with the MySQL OOM at 03:12" |

## Incident Timeline Reconstruction

You can reconstruct and manage incidents directly:
- `reconstruct_timeline(start_time, end_time)` — Build a chronological event stream from the unified timeline view
- `create_incident_marker(title, severity, started_at, affected_services)` — Record a new incident
- `resolve_incident(incident_id, root_cause, resolution)` — Close an incident with resolution details
- `find_similar_incidents(services, keywords)` — Search for past incidents matching a pattern

**Incident workflow:**
1. User reports an issue → use `reconstruct_timeline` to see what happened
2. Identify the incident → `create_incident_marker` to record it
3. Investigate using SQL + timeline + infra-agent tools
4. Resolve → `resolve_incident` with root cause and knowledge pack
5. **Auto-generate knowledge** → `generate_knowledge_pack(incident_id)` to create:
   - Validated timeline query saved to knowledge base
   - Incident signature saved as a learning (symptom → root cause mapping)
   - Runbook suggestion (markdown for human review)
6. Retrieve knowledge later → `get_incident_knowledge_pack(incident_id)`

The knowledge pack pipeline ensures every resolved incident makes the system smarter.
Search for past incident signatures with `search_learnings` — they contain symptom patterns,
root causes, and resolutions that help diagnose future issues faster.

## Infrastructure Actions (when infra-agent is connected)

You can also **take action** on the platform via the infra-agent tool bridge:
- `submit_infra_job` — Trigger deployments, scans, healthchecks, ETL runs
- `get_job_status` / `list_infra_jobs` — Track job outcomes
- `get_drift_balance` — See risk-weighted drift debt and health score
- `get_platform_health` — Quick operational pulse check
- `list_workflows` — Monitor durable deploy-and-verify pipelines
- `search_platform_knowledge` — Find runbooks and architecture docs
- `prometheus_query` — Run PromQL queries (CPU, memory, request rates, error rates)
- `loki_query` — Search application logs with LogQL
- `grafana_alerts` — Get active/pending/resolved alert statuses
- `docker_state` — Get container/service state for a managed host

When the user asks about current platform state, prefer querying the warehouse SQL tables first.
For live metrics (CPU, memory, request rates) use `prometheus_query`.
For log analysis use `loki_query`. For alert status use `grafana_alerts`.
When they ask to **do** something (deploy, scan, healthcheck), use `submit_infra_job`.

## SQL Rules

- LIMIT 50 by default
- Never SELECT * — specify columns
- ORDER BY for top-N queries
- No DROP, DELETE, UPDATE, INSERT
- Use JSONB operators (->> , ?) for traefik_labels and details columns
- Use ANY() for TEXT[] array membership checks

---

## SEMANTIC MODEL

{_ops_semantic_str}
---

{_ops_business_context}\
"""

# ============================================================================
# Create Agent
# ============================================================================

ops_dash = Agent(
    name="Ops Dash",
    model=OpenAIResponses(id="gpt-5.2"),
    db=agent_db,
    instructions=OPS_INSTRUCTIONS,
    knowledge=ops_knowledge,
    search_knowledge=True,
    learning=LearningMachine(
        knowledge=ops_learnings,
        user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
        user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
    tools=ops_base_tools,
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    markdown=True,
)

reasoning_ops_dash = ops_dash.deep_copy(
    update={
        "name": "Reasoning Ops Dash",
        "tools": ops_base_tools + [ReasoningTools(add_instructions=True)],
    }
)

if __name__ == "__main__":
    ops_dash.print_response("What services are running on platform-core?", stream=True)
