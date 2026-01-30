# Dash

A self-learning data agent inspired by [OpenAI's in-house data agent](https://openai.com/index/inside-our-in-house-data-agent/).

## Why Text-to-SQL Fails

Raw LLMs writing SQL hit a wall fast. They hallucinate column names, miss type quirks, and ignore the tribal knowledge that makes queries actually work. The problem isn't model capability, it's missing context.

Dash solves this with **6 layers of grounded context** and a **self-learning knowledge loop**.

## The 6 Layers

| Layer | What It Provides | Source |
|-------|------------------|--------|
| **Table Metadata** | Schema, columns, relationships | `knowledge/tables/*.json` |
| **Business Rules** | Metric definitions, gotchas | `knowledge/business/*.json` |
| **Query Patterns** | Validated SQL that works | `knowledge/queries/*.sql` |
| **Institutional Knowledge** | External docs, wikis | MCP (optional) |
| **Memory** | Patterns discovered through errors | Agno's `LearningMachine` |
| **Runtime Context** | Live schema when things change | `introspect_schema` tool |

The agent retrieves relevant context at query time via hybrid search, then generates SQL grounded in patterns that already work.

## Self-Improving Loop

```
User Question
     ↓
Retrieve Context (schemas, patterns, gotchas)
     ↓
Generate SQL (grounded in working examples)
     ↓
Execute & Analyze
     ↓
 ┌───┴───┐
 ↓       ↓
Success  Error
 ↓       ↓
Offer    Learn
to save  from it
```

When a query fails, the agent introspects the schema, fixes the issue, and saves the learning. Next time, it won't make the same mistake. No model retraining—just better retrieval knowledge.

## Quick Start

```sh
git clone https://github.com/agno-agi/data-agent.git && cd data-agent
cp example.env .env  # Add OPENAI_API_KEY

# Start
docker compose up -d --build
docker exec -it data-agent-api python -m da.scripts.load_data
docker exec -it data-agent-api python -m da.scripts.load_knowledge
```

| Endpoint | URL |
|----------|-----|
| API | http://localhost:8000 |
| Docs | http://localhost:8000/docs |
| Control Plane | [os.agno.com](https://os.agno.com) → Add OS → Local → `http://localhost:8000` |

**Try it** (sample F1 dataset):
```
Who won the most F1 World Championships?
How many races has Lewis Hamilton won?
Compare Ferrari vs Mercedes points 2015-2020
```

## Adding Knowledge

The knowledge base stores what makes your data unique, the context an LLM can't infer from schema alone.

```
knowledge/
├── tables/      # What each table contains
├── queries/     # SQL patterns that work
└── business/    # How your org talks about data
```

### Table Metadata

Describe tables beyond what's in the schema:

```json
{
  "table_name": "orders",
  "table_description": "Customer orders with line items denormalized",
  "use_cases": ["Revenue reporting", "Customer analytics"],
  "data_quality_notes": [
    "created_at is UTC",
    "status can be: pending, completed, refunded",
    "amount is in cents, not dollars"
  ]
}
```

### Query Patterns

Validated SQL the agent can learn from:

```sql
-- <query name>monthly_revenue</query name>
-- <query description>
-- Monthly revenue calculation.
-- Handles: cents to dollars, excludes refunds
-- </query description>
-- <query>
SELECT
    DATE_TRUNC('month', created_at) AS month,
    SUM(amount) / 100.0 AS revenue_dollars
FROM orders
WHERE status = 'completed'
GROUP BY 1
ORDER BY 1 DESC
-- </query>
```

### Business Rules

Map organizational language to data:

```json
{
  "metrics": [
    {"name": "MRR", "definition": "Sum of active subscription amounts, excluding trials"},
    {"name": "Churn", "definition": "Subscriptions cancelled / total subscriptions at period start"}
  ],
  "common_gotchas": [
    {"issue": "Revenue double-counting", "solution": "Use completed orders only, not pending"}
  ]
}
```

### Load It

```sh
python -m da.scripts.load_knowledge            # Upsert changes
python -m da.scripts.load_knowledge --recreate # Fresh start
```

## Local Development

```sh
./scripts/venv_setup.sh && source .venv/bin/activate
docker compose up -d data-agent-db
python -m da.scripts.load_data
python -m da  # CLI mode
```

## Deploy

```sh
railway login && ./scripts/railway_up.sh
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `EXA_API_KEY` | No | Web search for institutional knowledge |
| `DB_*` | No | Database config (defaults to localhost) |

## Links

- [OpenAI's In-House Data Agent](https://openai.com/index/inside-our-in-house-data-agent/) — the inspiration
- [Self-Improving SQL Agent](https://www.ashpreetbedi.com/articles/sql-agent) — deep dive on an earlier architecture
- [Agno Docs](https://docs.agno.com)
- [Discord](https://agno.com/discord)
