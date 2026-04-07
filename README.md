# Dash

A **self-learning data agent** that lives in Slack. It grounds answers in 6 layers of context and improves with every query. Chat with Dash via Slack, the terminal, or the [AgentOS](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) web UI.

> Inspired by [OpenAI's in-house data agent](https://openai.com/index/inside-our-in-house-data-agent/).

## Quick Start

```sh
# Clone the repo
git clone https://github.com/agno-agi/dash.git && cd dash

# Add OPENAI_API_KEY
cp example.env .env
# Edit .env and add your key

# Start the application
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

## Slack

Slack gives Dash two capabilities: receiving messages from users in Slack threads, and proactively posting to channels.

See [docs/SLACK_CONNECT.md](docs/SLACK_CONNECT.md) for the full setup guide with the app manifest.

### 1. Get a public URL

For local development, use [ngrok](https://ngrok.com/download/mac-os):

```sh
ngrok http 8000
```

Copy the `https://` URL (e.g. `https://abc123.ngrok-free.app`).

### 2. Create app from manifest

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App → From a manifest**
2. Select your workspace, switch to **JSON**
3. Paste the manifest from [docs/SLACK_CONNECT.md](docs/SLACK_CONNECT.md) — replace `YOUR_URL_HERE` with your URL
4. Click **Create**

### 3. Install and get credentials

1. **Install to Workspace** and authorize
2. Copy **Bot User OAuth Token** (`xoxb-...`) → `SLACK_TOKEN`
3. Go to **Basic Information → App Credentials**, copy **Signing Secret** → `SLACK_SIGNING_SECRET`

### 4. Add to `.env` and restart

```env
SLACK_TOKEN="xoxb-your-bot-token"
SLACK_SIGNING_SECRET="your-signing-secret"
```

```sh
docker compose up -d --build
```

Thread timestamps map to session IDs, so each Slack thread gets its own conversation context.

## Why Text-to-SQL Breaks in Practice

Our goal is simple: ask a question in english, get a correct, meaningful answer. But raw LLMs writing SQL hit a wall fast:

- **Schemas lack meaning.**
- **Types are misleading.**
- **Tribal knowledge is missing.**
- **No way to learn from mistakes.**
- **Results generally lack interpretation.**

The root cause is missing context and missing memory.

Dash solves this with **6 layers of grounded context**, a **self-learning loop** that improves with every query, and a focus on **understanding your question** to deliver insights you can act on.

## The Six Layers of Context

| Layer | Purpose | Source |
|------|--------|--------|
| **Table Usage** | Schema, columns, relationships | `knowledge/tables/*.json` |
| **Human Annotations** | Metrics, definitions, and business rules | `knowledge/business/*.json` |
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

Dash reasons about what makes an answer useful, not just technically correct.

**Question:**
What's our churn rate by plan?

| Basic SQL Agent | Dash |
|------------------|------|
| `Starter: 12%, Pro: 7%, Enterprise: 4%` | Starter has 12% monthly churn — 3x higher than Enterprise (4%). Usage drops 60% in the week before cancellation, suggesting a usage-based early warning system could help. |

## Data Model (SaaS Metrics)

Synthetic B2B SaaS dataset (~500 customers, 2 years of data):

| Table | Description |
|-------|-------------|
| `customers` | Company info, industry, size, acquisition source, status |
| `subscriptions` | Plan, MRR, seats, billing cycle, lifecycle status |
| `plan_changes` | Upgrades, downgrades, cancellations with MRR impact |
| `invoices` | Billing records, payment status, billing periods |
| `usage_metrics` | Daily API calls, active users, storage, reports |
| `support_tickets` | Priority, category, resolution time, satisfaction |

## Deploy to Railway

Railway deployment uses `.env.production` to keep production credentials separate from local dev.

### First-time setup

```sh
# Create .env.production with your production values
cp example.env .env.production
# Edit .env.production — set OPENAI_API_KEY, SLACK_TOKEN, etc.

# Login and deploy
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
# Load data and knowledge
railway run python scripts/generate_data.py
railway run python scripts/load_knowledge.py

# View logs
railway logs --service dash

# CLI mode
railway run python -m dash

# Open dashboard
railway open
```

### Secure your deployment

See [Security](#security) below for setup — you'll need to connect your OS at [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) and add a `JWT_VERIFICATION_KEY` to your environment.

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
    "signup_date is UTC",
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

## Local Development

```sh
./scripts/venv_setup.sh && source .venv/bin/activate
docker compose up -d dash-db
python scripts/generate_data.py
python scripts/load_knowledge.py
python -m dash            # CLI mode
python -m app.main        # AgentOS mode (web UI at os.agno.com)
```

## Architecture

### Dual Schema

Dash enforces a structural boundary between company data and agent-managed data:

| Schema | Owner | Access |
|--------|-------|--------|
| `public` | Company (loaded externally) | Read-only — never modified by agents |
| `dash` | Engineer agent | Views, summary tables, computed data |

The Engineer builds reusable data assets (`dash.monthly_mrr`, `dash.customer_health_score`, `dash.churn_risk`) and records them to knowledge. The Analyst discovers and prefers these views over raw table queries.

### Agent Team

```
AgentOS (app/main.py)  [scheduler=True, tracing=True]
 ├── FastAPI / Uvicorn
 ├── Slack Interface (optional — requires SLACK_TOKEN + SLACK_SIGNING_SECRET)
 └── Dash Team (dash/team.py, coordinate mode)
     ├─ Analyst (dash/agents/analyst.py)        reads public + dash
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
     Leader tools: SlackTools (optional — requires SLACK_TOKEN)
     Knowledge:    dash_knowledge (table schemas, queries, business rules, dash views)
     Learnings:    dash_learnings (error patterns, type gotchas, fixes)
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

## A Note on This Project

This project was largely built with Claude. If you find a mistake, please open an [issue](https://github.com/agno-agi/dash/issues) or submit a pull request.

<p align="center">Built on <a href="https://github.com/agno-agi/agno">Agno</a> · the runtime for agentic software</p>
