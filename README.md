# Dash

Dash is a **self-learning data agent** that delivers **insights, not just SQL results**.

Instead of guessing queries from scratch, Dash grounds SQL generation in **six layers of context** and improves automatically with every run.

Inspired by [OpenAI's in-house data agent](https://openai.com/index/inside-our-in-house-data-agent/).

## Why Text-to-SQL Breaks in Practice

The dream is simple: ask a question in english, get a correct, meaningful answer. But raw LLMs writing SQL hit a wall fast:

- **Schemas lack meaning.** A column named `status` does not explain valid values or business semantics.
- **Types are misleading.** The same concept might be INTEGER in one table and TEXT in another.
- **Business logic is tribal.** Revenue definitions, exclusions, test filters, and unit conversions rarely live in the schema.
- **Mistakes repeat forever.** Stateless agents relearn the same errors every session.
- **Results lack interpretation.** Returning `Hamilton: 11` is not an answer without context.

The root cause is missing context and missing memory.

Dash solves this with **6 layers of grounded context**, a **self-learning loop** that improves with every query, and a focus on **understanding your question** to deliver insights you can act on.

## The Six Layers of Context

| Layer | Purpose | Source |
|------|--------|--------|
| **Table Usage** | Schema, columns, relationships | `knowledge/tables/*.json` |
| **Business Rules** | Metrics, definitions, and gotchas | `knowledge/business/*.json` |
| **Query Patterns** | SQL that is known to work | `knowledge/queries/*.sql` |
| **Institutional Knowledge** | Docs, wikis, external references | MCP (optional) |
| **Learnings** | Error patterns and discovered fixes | Agno `Learning Machine` |
| **Runtime Context** | Live schema changes | `introspect_schema` tool |

The agent retrieves relevant context at query time via hybrid search, then generates SQL grounded in patterns that already work.

## The Self-Learning Loop

Dash improves without retraining or fine-tuning.

It learns through two complementary systems:

| System | Stores | How It Evolves |
|------|--------|----------------|
| **Knowledge** | Validated queries and business context | Curated by you + dash |
| **Learnings** | Error patterns and fixes | Managed by `Learning Machine` automatically |

```
User Question
     ↓
Retrieve Knowledge + Learnings
     ↓
Reason about intent
     ↓
Generate grounded SQL
     ↓
Execute and interpret
     ↓
 ┌────┴────┐
 ↓         ↓
Success    Error
 ↓         ↓
 ↓         Diagnose → Fix → Save Learning
 ↓                           (never repeated)
 ↓
Return insight
 ↓
Optionally save as Knowledge
```

**Knowledge** is curated—validated queries and business context you want the agent to build on.

**Learnings** is discovered—patterns the agent finds through trial and error. When a query fails because `position` is TEXT not INTEGER, the agent saves that gotcha. Next time, it knows.

## Insights, Not Just Rows

**Question:**
Who won the most races in 2019?

| Typical SQL Agent | Dash |
|------------------|------|
| `Hamilton: 11` | Lewis Hamilton dominated 2019 with **11 wins out of 21 races**, more than double Bottas’s 4 wins. This performance secured his sixth world championship. |

Dash reasons about what makes an answer useful, not just technically correct.

## Quick Start

```sh
git clone https://github.com/agno-agi/dash.git && cd dash
# Add OPENAI_API_KEY by adding to .env file or export OPENAI_API_KEY=sk-***
cp example.env .env

# Start
docker compose up -d --build

# Load sample data and knowledge
docker exec -it dash-api python -m dash.scripts.load_data
docker exec -it dash-api python -m dash.scripts.load_knowledge
```

| Endpoint | URL |
|----------|-----|
| API | http://localhost:8000 |
| Web UI | [os.agno.com](https://os.agno.com) → Add OS → Local → `http://localhost:8000` |

## Connect to the Web UI

1. Open [os.agno.com](https://os.agno.com) and login
2. Add OS → Local → `http://localhost:8000`
3. Click "Connect"

**Try it** (sample F1 dataset):

```
Who won the most F1 World Championships?
How many races has Lewis Hamilton won?
Compare Ferrari vs Mercedes points 2015-2020
```

## Adding Knowledge

Dash works best when it understands how your organization talks about data.

```
knowledge/
├── tables/      # Table meaning and caveats
├── queries/     # Proven SQL patterns
└── business/    # Metrics and language
```

### Table Metadata

```
{
  "table_name": "orders",
  "table_description": "Customer orders with denormalized line items",
  "use_cases": ["Revenue reporting", "Customer analytics"],
  "data_quality_notes": [
    "created_at is UTC",
    "status values: pending, completed, refunded",
    "amount stored in cents"
  ]
}
```

### Query Patterns

```
-- <query name>monthly_revenue</query name>
-- <query description>
-- Monthly revenue calculation.
-- Converts cents to dollars.
-- Excludes refunded orders.
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

```
{
  "metrics": [
    {
      "name": "MRR",
      "definition": "Sum of active subscriptions excluding trials"
    }
  ],
  "common_gotchas": [
    {
      "issue": "Revenue double counting",
      "solution": "Filter to completed orders only"
    }
  ]
}
```

### Load Knowledge

```sh
python -m dash.scripts.load_knowledge            # Upsert changes
python -m dash.scripts.load_knowledge --recreate # Fresh start
```

## Local Development

```sh
./scripts/venv_setup.sh && source .venv/bin/activate
docker compose up -d dash-db
python -m dash.scripts.load_data
python -m dash  # CLI mode
```

## Deploy

```sh
railway login

./scripts/railway_up.sh
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `EXA_API_KEY` | No | Web search for external knowledge |
| `DB_*` | No | Database config (defaults to localhost) |

## Further Reading

- [OpenAI's In-House Data Agent](https://openai.com/index/inside-our-in-house-data-agent/) — the inspiration
- [Self-Improving SQL Agent](https://www.ashpreetbedi.com/articles/sql-agent) — deep dive on an earlier architecture
- [Agno Docs](https://docs.agno.com)
- [Discord](https://agno.com/discord)
