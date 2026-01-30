# CLAUDE.md

Project instructions for Claude Code.

## Project Overview

Data Agent - A self-learning data agent inspired by OpenAI's internal data agent. Implements 6 layers of context for grounded SQL generation.

## Architecture

```
da/                              # The Data Agent
├── agent.py                     # Main agent with all 6 layers
├── context/                     # Context builders (Layers 1-3)
│   ├── semantic_model.py        # Layer 1: Table metadata
│   ├── business_rules.py        # Layer 2: Business rules
│   └── query_patterns.py        # Layer 3: Query patterns
├── tools/                       # Agent tools
│   ├── analyze.py               # Result analysis
│   ├── introspect.py            # Layer 6: Runtime schema
│   └── save_query.py            # Save validated queries
└── evals/                       # Evaluation suite

knowledge/                       # Static knowledge files
├── tables/                      # Table metadata (JSON)
├── business/                    # Business rules (JSON)
└── queries/                     # Validated SQL patterns
```

## Key Files

| File | Purpose |
|------|---------|
| `da/agent.py` | Main agent with 6 layers, LearningMachine, gpt-5.2 |
| `knowledge/tables/*.json` | Table metadata with data quality notes |
| `knowledge/business/*.json` | Metrics, rules, common gotchas |
| `app/main.py` | AgentOS entry point |

## Commands

```bash
# Start locally
docker compose up -d --build

# Load F1 data
docker exec -it data-agent-api python -m da.scripts.load_data

# Run evaluations
docker exec -it data-agent-api python -m da.evals.run_evals --stats

# Format & validate
./scripts/format.sh
./scripts/validate.sh
```

## The 6 Layers of Context

| Layer | Source | Code |
|-------|--------|------|
| 1. Table Metadata | `knowledge/tables/*.json` | `da/context/semantic_model.py` |
| 2. Human Annotations | `knowledge/business/*.json` | `da/context/business_rules.py` |
| 3. Query Patterns | `knowledge/queries/*.sql` | `da/context/query_patterns.py` |
| 4. Institutional Knowledge | MCP (optional) | Configured in `da/agent.py` |
| 5. Memory | LearningMachine | Configured in `da/agent.py` |
| 6. Runtime Context | `introspect_schema` tool | `da/tools/introspect.py` |

## Data Quality Gotchas (F1 Dataset)

| Issue | Tables | Solution |
|-------|--------|----------|
| `position` is TEXT | `drivers_championship` | Use `position = '1'` (string) |
| `position` is INTEGER | `constructors_championship` | Use `position = 1` (number) |
| `date` is TEXT | `race_wins` | Use `TO_DATE(date, 'DD Mon YYYY')` |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `EXA_API_KEY` | No | - | Enables MCP (Layer 4) |
| `PORT` | No | `8000` | API server port |
| `DB_HOST` | No | `localhost` | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |

## Adding Knowledge

Table metadata (`knowledge/tables/`):
```json
{
  "table_name": "my_table",
  "table_description": "Description",
  "table_columns": [{"name": "id", "type": "INTEGER", "description": "Primary key"}],
  "data_quality_notes": ["Important notes"]
}
```

Business rules (`knowledge/business/`):
```json
{
  "metrics": [{"name": "Metric", "definition": "...", "table": "..."}],
  "common_gotchas": [{"issue": "...", "tables_affected": ["..."], "solution": "..."}]
}
```

## Agno Reference

```python
from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.learn import LearningMachine, LearningMode

agent = Agent(
    id="my-agent",
    model=OpenAIResponses(id="gpt-5.2"),
    knowledge=my_knowledge,
    learning=LearningMachine(...),
)
```

Docs: https://docs.agno.com/llms.txt
