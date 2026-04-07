# Dash

A **self-learning data agent** built with systems engineering principles. It grounds answers in 6 layers of context and improves with every query.

Chat with Dash via Slack, the terminal, or the [AgentOS](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) web UI.

## Quick Start

```sh
# Clone the repo
git clone https://github.com/agno-agi/dash.git && cd dash

cp example.env .env
# Edit .env and add your OPENAI_API_KEY

# Start the system
docker compose up -d --build

# Generate sample data and load knowledge
docker exec -it dash-api python scripts/generate_data.py
docker exec -it dash-api python scripts/load_knowledge.py
```

Confirm Dash is running at [http://localhost:8000/docs](http://localhost:8000/docs).

### Connect to the Web UI

1. Open [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) and login
2. Add OS → Local → `http://localhost:8000`
3. Click "Connect"

**Try it** (SaaS metrics dataset):

- What's our current MRR?
- Which plan has the highest churn rate?
- Show me revenue trends by plan over the last 6 months
- Which customers are at risk of churning?

## Why Dash Exists

Ask a question in English, get a correct, meaningful answer. That's the goal. But raw LLMs writing SQL hit a wall fast: schemas lack meaning, types are misleading, tribal knowledge is missing, there's no way to learn from mistakes, and results lack interpretation.

The root cause is missing context and missing memory. Dash solves this with **six layers of grounded context**, a **self-learning loop** that improves with every query, and a focus on delivering insights you can act on.

## Architecture: Five Layers, One System

Agentic software is just software with the business logic replaced by agents. Everything else is systems engineering. Dash is built across five layers that reinforce each other.

```
Agent Engineering     →  dash/team.py + dash/agents/
Data Engineering      →  knowledge/ + Agno Learning Machine + PostgreSQL
Security Engineering  →  AgentOS auth + RBAC + read-only SQL enforcement
Interface Engineering →  app/main.py (FastAPI) + Slack + AgentOS
Infrastructure        →  Dockerfile + compose.yaml + scripts/
```

### 1. Agent Engineering

The agent team and execution flow. Model, instructions, tools, knowledge, and the self-learning loop.

```
AgentOS (app/main.py)  [scheduler=True, tracing=True]
 ├── FastAPI / Uvicorn
 ├── Slack Interface (optional)
 └── Dash Team (dash/team.py, coordinate mode)
     ├─ Analyst (dash/agents/analyst.py)         reads public + dash
     │  ├─ SQLTools (read-only)  → public schema (company data)
     │  ├─ introspect_schema     → both schemas
     │  ├─ save_validated_query  → knowledge base
     │  └─ ReasoningTools
     ├─ Engineer (dash/agents/engineer.py)       reads public, writes dash
     │  ├─ SQLTools (full)       → dash schema (agent-managed)
     │  ├─ introspect_schema     → both schemas
     │  ├─ update_knowledge      → knowledge base (schema changes)
     │  └─ ReasoningTools
     │
     Leader tools: SlackTools (optional)
     Knowledge:    dash_knowledge (table schemas, queries, business rules, dash views)
     Learnings:    dash_learnings (error patterns, type gotchas, fixes)
```

### 2. Data Engineering

Context is data. Memory is data. Knowledge is data. All managed with data engineering principles: well-designed schemas, structured querying, databases for fast read/writes.

**Six layers of grounded context:**

| Layer | Purpose | Source |
|------|--------|--------|
| **Table Usage** | Schema, columns, relationships | `knowledge/tables/*.json` |
| **Human Annotations** | Metrics, definitions, business rules | `knowledge/business/*.json` |
| **Query Patterns** | SQL that is known to work | `knowledge/queries/*.sql` |
| **Institutional Knowledge** | Docs, wikis, external references | MCP (optional) |
| **Learnings** | Error patterns and discovered fixes | Agno `Learning Machine` |
| **Runtime Context** | Live schema changes | `introspect_schema` tool |

**The self-learning loop:**

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

Two complementary systems:

| System | Stores | How It Evolves |
|------|--------|----------------|
| **Knowledge** | Validated queries and business context | Curated by you + Dash |
| **Learnings** | Error patterns and fixes | Managed by `Learning Machine` automatically |

**Dual schema enforcement:** A structural boundary between company data and agent-managed data.

| Schema | Owner | Access |
|--------|-------|--------|
| `public` | Company (loaded externally) | Read-only — never modified by agents |
| `dash` | Engineer agent | Views, summary tables, computed data |

The Engineer builds reusable data assets (`dash.monthly_mrr`, `dash.customer_health_score`, `dash.churn_risk`) and records them to knowledge. The Analyst discovers and prefers these views over raw table queries.

### 3. Security Engineering

Auth uses RBAC with JWT verification in production. Every query is scoped to `user_id`. Read-only access is a tool configuration, not a prompt instruction. The Analyst agent's SQL tools are scoped to read-only at the system level.

See [Security](#security) for setup details.

### 4. Interface Engineering

One agent definition, multiple surfaces. Dash is reachable via REST API (FastAPI), Slack threads, and the AgentOS web UI. Each surface has its own identity system: a Slack user ID maps to sessions via thread timestamps, the API uses JWT-backed auth.

### 5. Infrastructure Engineering

Dockerfile, Docker Compose, one-command deployment. Scheduled tasks for proactive behavior. The infrastructure layer is boring on purpose. 95% of running an agent is identical to running any other service.

## Slack

Dash can receive Slack DMs, @mentions, and thread replies, and can also post to channels proactively.

Quick setup:
1. Run Dash and give it a public URL (ngrok locally, or your Railway domain).
2. Follow [docs/SLACK_CONNECT.md](docs/SLACK_CONNECT.md) to create and install the Slack app from the manifest.
3. Set `SLACK_TOKEN` and `SLACK_SIGNING_SECRET`, then restart Dash.
4. In Slack, confirm Event Subscriptions is verified and send a DM or `@mention` to test it.

Each Slack thread maps to one Dash session. For the manifest, ngrok commands, Railway deployment, permissions, and troubleshooting, see [docs/SLACK_CONNECT.md](docs/SLACK_CONNECT.md).

## Data Model (SaaS Metrics)

Synthetic B2B SaaS dataset (~900 customers, 2 years of data):

| Table | Description |
|-------|-------------|
| `customers` | Company info, industry, size, acquisition source, status |
| `subscriptions` | Plan, MRR, seats, billing cycle, lifecycle status |
| `plan_changes` | Upgrades, downgrades, cancellations with MRR impact |
| `invoices` | Billing records, payment status, billing periods |
| `usage_metrics` | Daily API calls, active users, storage, reports |
| `support_tickets` | Priority, category, resolution time, satisfaction |

## Adding Knowledge

Dash works best when it understands how your organization talks about data.

```
knowledge/
├── tables/      # Table meaning and caveats
├── queries/     # Proven SQL patterns
└── business/    # Metrics and language
```

### Table Metadata

```json
{
  "table_name": "customers",
  "table_description": "B2B SaaS customer accounts with company info and lifecycle status",
  "use_cases": ["Churn analysis", "Cohort segmentation", "Acquisition reporting"],
  "data_quality_notes": [
    "signup_date is DATE (not TIMESTAMP) — no time component",
    "status values: active, churned, trial",
    "company_size is self-reported"
  ]
}
```

### Query Patterns

```sql
-- <query monthly_mrr>
-- <description>Monthly MRR from active subscriptions</description>
-- <query>
SELECT
    DATE_TRUNC('month', started_at) AS month,
    SUM(mrr) AS total_mrr
FROM subscriptions
WHERE ended_at IS NULL
GROUP BY 1
ORDER BY 1 DESC
-- </query>
```

### Business Rules

```json
{
  "metrics": [
    {
      "name": "MRR",
      "definition": "Sum of active subscriptions excluding trials"
    }
  ],
  "common_gotchas": [
    {
      "issue": "Active subscription detection",
      "solution": "Filter on ended_at IS NULL, not status column"
    }
  ]
}
```

### Load Knowledge

```sh
python scripts/load_knowledge.py            # Upsert changes
python scripts/load_knowledge.py --recreate  # Fresh start
```

## Evaluations

Five eval categories using Agno's eval framework:

| Category | Eval Type | What It Tests |
|----------|-----------|---------------|
| accuracy | AccuracyEval (1-10) | Correct data and meaningful insights |
| routing | ReliabilityEval | Team routes to correct agent/tools |
| security | AgentAsJudgeEval (binary) | No credential or secret leaks |
| governance | AgentAsJudgeEval (binary) | Refuses destructive SQL operations |
| boundaries | AgentAsJudgeEval (binary) | Schema access boundaries respected |

```sh
python -m evals                      # Run all evals
python -m evals --category accuracy  # Run specific category
python -m evals --verbose            # Show response details
```

## Deploy to Railway

Railway deployment uses `.env.production` to keep production credentials separate from local dev.

### First-time setup

```sh
cp example.env .env.production
# Edit .env.production — set OPENAI_API_KEY, SLACK_TOKEN, etc.

railway login
./scripts/railway_up.sh
```

### Sync environment variables

After updating `.env.production`, sync to Railway:

```sh
./scripts/railway_env.sh
```

This reads `.env.production` and sets each variable on the Railway service. Safe to run repeatedly — overwrites existing values. Handles multiline values (PEM keys) correctly.

### Redeploy after code changes

```sh
./scripts/railway_redeploy.sh
```

### Production operations

```sh
railway run python scripts/generate_data.py
railway run python scripts/load_knowledge.py
railway logs --service dash
railway run python -m dash
railway open
```

### Secure your deployment

See [Security](#security) below for setup — you'll need to connect your OS at [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) and add a `JWT_VERIFICATION_KEY` to your environment.

## Local Development

```sh
./scripts/venv_setup.sh && source .venv/bin/activate
docker compose up -d dash-db
python scripts/generate_data.py
python scripts/load_knowledge.py
python -m dash            # CLI mode
python -m app.main        # AgentOS mode (web UI at os.agno.com)
```

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `SLACK_TOKEN` | No | `""` | Slack bot token (interface + tools) |
| `SLACK_SIGNING_SECRET` | No | `""` | Slack signing secret (interface only) |
| `DB_HOST` | No | `localhost` | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |
| `DB_USER` | No | `ai` | PostgreSQL user |
| `DB_PASS` | No | `ai` | PostgreSQL password |
| `DB_DATABASE` | No | `ai` | PostgreSQL database |
| `PORT` | No | `8000` | API port |
| `RUNTIME_ENV` | No | `prd` | `dev` enables hot reload |
| `AGENTOS_URL` | No | `http://127.0.0.1:8000` | Scheduler callback URL (production) |
| `JWT_VERIFICATION_KEY` | Production | — | RBAC public key from [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) |

## Security

Production deployments require authentication via [Agno AgentOS](https://docs.agno.com/agent-os/security/overview?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=security). Dash enables [RBAC authorization](https://docs.agno.com/agent-os/security/rbac?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=rbac) when `RUNTIME_ENV=prd` (the default). Without a valid `JWT_VERIFICATION_KEY`, production endpoints will reject all requests.

Local development (`RUNTIME_ENV=dev`, set by Docker Compose) runs without auth so you can iterate freely.

### Setup

1. Deploy Dash to Railway (or your cloud provider)
2. Open [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) and connect your deployed OS
3. Go to **Settings** and generate a key pair
4. Add the public key to your `.env.production` (paste the full PEM block, no quotes needed):

```bash
JWT_VERIFICATION_KEY=-----BEGIN PUBLIC KEY-----
MIIBIjANBgkq...
-----END PUBLIC KEY-----
```

5. Push to production and redeploy:

```bash
./scripts/railway_env.sh
./scripts/railway_redeploy.sh
```

The Agno control plane handles JWT issuance, session management, traces, metrics, and the web UI. See the [AgentOS Security docs](https://docs.agno.com/agent-os/security/overview?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=security) for details.

### Schema-Level Enforcement

Beyond API-level auth, Dash enforces data access at the database level:

- **Analyst** connects with `default_transaction_read_only=on` — PostgreSQL rejects any write attempt
- **Engineer** writes are scoped to the `dash` schema — a SQLAlchemy event listener blocks any DDL/DML targeting `public`
- **Leader** has no direct database access

These are infrastructure guardrails, not prompt instructions. They hold regardless of what the model generates.

## Learn More

- [OpenAI's In-House Data Agent](https://openai.com/index/inside-our-in-house-data-agent/) — the inspiration
- [Self-Improving SQL Agent](https://www.ashpreetbedi.com/articles/sql-agent) — deep dive on an earlier architecture
- [Agno Docs](https://docs.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=docs)

<p align="center">Built on <a href="https://github.com/agno-agi/agno">Agno</a> · the runtime for agentic software</p>