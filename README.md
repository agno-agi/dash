# Dash — a self-learning data agent

Ask a question in English, get a correct, meaningful answer. Raw LLMs writing SQL hit a wall fast: schemas lack meaning, tribal knowledge is missing, and there's no way to learn from mistakes. Dash solves this with layered, grounded context and a self-learning loop that improves with every query — built for teams that want a data agent they can trust with real analytics questions.

## How it works

Dash is a coordinated team of two agents behind [AgentOS](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) (`app/main.py`), backed by PostgreSQL + pgvector:

- **Analyst** (`dash/agents/analyst.py`) — writes and runs SQL against company data (read-only), introspects schemas, and saves validated queries back to knowledge.
- **Engineer** (`dash/agents/engineer.py`) — owns the agent-managed `dash` schema: views, summary tables, pipelines, and knowledge updates.
- **Team leader** (`dash/team.py`) — routes requests, holds per-user memory, and (optionally) posts to Slack.

**Grounded context** comes from five layers:

| Layer | Purpose | Source |
|-------|---------|--------|
| Table usage | Schema, columns, relationships | `knowledge/tables/*.json` |
| Human annotations | Metrics, definitions, business rules | `knowledge/business/*.json` |
| Query patterns | SQL that is known to work | `knowledge/queries/*.sql` |
| Learnings | Error patterns and discovered fixes | Agno Learning Machine |
| Runtime context | Live schema changes | `introspect_schema` tool |

**The self-learning loop:** every query retrieves knowledge + learnings before generating SQL. On errors, the agent diagnoses, fixes, and saves a learning so the mistake is never repeated. Validated queries can be saved back to knowledge.

**Guardrails are infrastructure, not prompts:**

| Schema | Owner | Enforcement |
|--------|-------|-------------|
| `public` | Company data | Analyst connects with `default_transaction_read_only=on`; a SQLAlchemy listener blocks Engineer writes to `public` |
| `dash` | Engineer agent | Full SQL, scoped via `search_path` |

## Quick start

Requires Docker and an OpenAI API key.

```sh
git clone https://github.com/agno-agi/dash.git && cd dash

cp example.env .env
# Edit .env and add your OPENAI_API_KEY

docker compose up -d --build

# Generate the sample dataset and load knowledge
docker exec -it dash-api python scripts/generate_data.py
docker exec -it dash-api python scripts/load_knowledge.py
```

Confirm Dash is running at [http://localhost:8000/docs](http://localhost:8000/docs).

The sample dataset is a synthetic B2B SaaS company (~900 customers, 2 years of data: customers, subscriptions, plan changes, invoices, usage metrics, support tickets). Try:

- What's our current MRR?
- Which plan has the highest churn rate?
- Show me revenue trends by plan over the last 6 months
- Which customers are at risk of churning?

### Local development (without the API container)

```sh
./scripts/venv_setup.sh && source .venv/bin/activate
docker compose up -d dash-db
python scripts/generate_data.py
python scripts/load_knowledge.py
python -m dash          # terminal chat
python -m app.main      # AgentOS server on :8000
```

## Interfaces

- **AgentOS web UI** — open [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos), log in, then Add OS → Local → `http://localhost:8000` → Connect.
- **Slack** — DMs, @mentions, and thread replies; each thread maps to one session. Set `SLACK_TOKEN` and `SLACK_SIGNING_SECRET`, give Dash a public URL, and follow [docs/SLACK_CONNECT.md](docs/SLACK_CONNECT.md) for the app manifest and setup.
- **Terminal** — `python -m dash`.
- **REST API** — FastAPI, with interactive docs at `/docs`.

## Deploy

Dash ships with Railway scripts (`railway.json` + `scripts/railway_*.sh`). Production notes:

- The scheduler requires a **single replica** (`numReplicas: 1` in `railway.json`) — don't scale the app service horizontally.
- Production boot (`RUNTIME_ENV=prd`, the default) enables authorization and **requires `JWT_VERIFICATION_KEY`**; the app crash-loops until it's set.

```sh
cp example.env .env.production
# Edit .env.production — set OPENAI_API_KEY

railway login
./scripts/railway_up.sh        # creates project, pgvector DB, app service, domain
```

Then get your JWT key: open [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) → Add OS → Live → paste your Railway URL → Settings → generate a key pair. Add the public key to `.env.production` (single quotes, including the BEGIN/END lines):

```bash
JWT_VERIFICATION_KEY='-----BEGIN PUBLIC KEY-----
MIIBIjANBgkq...
-----END PUBLIC KEY-----'
```

Push the environment and redeploy:

```sh
./scripts/railway_env.sh       # syncs .env.production → Railway (idempotent, handles PEM keys)
./scripts/railway_redeploy.sh
```

Database scripts must run inside Railway's network (the internal hostname isn't reachable locally):

```sh
railway ssh --service dash
# inside the container:
python scripts/generate_data.py
python scripts/load_knowledge.py
```

## Configuration

Set in `.env` (local) or `.env.production` (Railway). See [example.env](example.env).

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `SLACK_TOKEN` | No | `""` | Slack bot token (interface + leader tools) |
| `SLACK_SIGNING_SECRET` | No | `""` | Slack signing secret (interface) |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_DATABASE` | No | `localhost` / `5432` / `ai` / `ai` / `ai` | PostgreSQL connection (compose sets these) |
| `RUNTIME_ENV` | No | `prd` | `dev` disables auth and enables hot reload (compose sets `dev`) |
| `AGENTOS_URL` | No | `http://127.0.0.1:8000` | Scheduler callback URL (set to your public URL in production) |
| `JWT_VERIFICATION_KEY` | Production | — | RBAC public key from [os.agno.com](https://os.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=agentos) |

### Adding knowledge

Dash works best when it understands how your organization talks about data. Drop files into `knowledge/tables/` (table meaning and caveats, JSON), `knowledge/queries/` (proven SQL patterns), and `knowledge/business/` (metrics and business rules, JSON), then load:

```sh
python scripts/load_knowledge.py             # upsert changes
python scripts/load_knowledge.py --recreate  # fresh start
```

A daily scheduled task (`knowledge-refresh`, 04:00 UTC) re-indexes knowledge files automatically.

## Evals

Five categories using Agno's eval framework — accuracy (AccuracyEval), routing (ReliabilityEval), and security / governance / boundaries (AgentAsJudgeEval, binary). Requires the venv and a running database:

```sh
python -m evals                      # run all categories
python -m evals --category accuracy  # one category
python -m evals --verbose            # show response details

python -m evals smoke                # lightweight smoke tests
python -m evals improve --dry-run    # self-improvement loop (analyze only)
```

See [docs/TEST_QUESTIONS.md](docs/TEST_QUESTIONS.md) for probing questions and [docs/IMPROVE_DASH.md](docs/IMPROVE_DASH.md) for the agent-driven improvement loop.

## Source / links

- [Contributing guide](CONTRIBUTING.md) — dev setup, `./scripts/format.sh`, `./scripts/validate.sh`
- [OpenAI's in-house data agent](https://openai.com/index/inside-our-in-house-data-agent/) — the inspiration
- [Self-improving SQL agent](https://www.ashpreetbedi.com/articles/sql-agent) — deep dive on an earlier architecture
- [Agno docs](https://docs.agno.com?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=docs) · [AgentOS security](https://docs.agno.com/agent-os/security/overview?utm_source=github&utm_medium=example-repo&utm_campaign=agent-example&utm_content=dash&utm_term=security)

<p align="center">Built on <a href="https://github.com/agno-agi/agno">Agno</a> · the runtime for agentic software</p>
