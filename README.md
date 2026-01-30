# Data Agent

A self-learning data agent that provides **insights**, not just query results.

Inspired by [OpenAI's internal data agent](https://openai.com/index/how-openai-built-its-data-agent/) that serves 3.5k users across 600 PB of data.

[What is AgentOS?](https://docs.agno.com/agent-os/introduction) · [Agno Docs](https://docs.agno.com) · [Discord](https://agno.com/discord)

## The 6 Layers of Context

| Layer | Purpose | Implementation |
|-------|---------|----------------|
| **1. Table Metadata** | Schema, columns, types | `knowledge/tables/*.json` |
| **2. Human Annotations** | Business rules, gotchas | `knowledge/business/*.json` |
| **3. Query Patterns** | Validated SQL | `knowledge/queries/*.sql` |
| **4. Institutional Knowledge** | External context | MCP connectors (optional) |
| **5. Memory** | Corrections, preferences | Agno's `LearningMachine` |
| **6. Runtime Context** | Live schema inspection | `introspect_schema` tool |

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone and configure

```sh
git clone https://github.com/agno-agi/data-agent.git
cd data-agent

cp example.env .env
# Add your OPENAI_API_KEY to .env or export via `export OPENAI_API_KEY=sk-...`
```

### 2. Start locally

```sh
docker compose up -d --build
```

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs

### 3. Connect to control plane

1. Open [os.agno.com](https://os.agno.com)
2. Click "Add OS" → "Local"
3. Enter `http://localhost:8000`

## Deploy to Railway

### Prerequisites

- [Railway CLI](https://docs.railway.com/guides/cli)
- `OPENAI_API_KEY` set in your environment

### Deploy

```sh
railway login
./scripts/railway_up.sh
```

The script provisions PostgreSQL, configures environment variables, and deploys your application.

### Connect to control plane

1. Open [os.agno.com](https://os.agno.com)
2. Click "Add OS" → "Live"
3. Enter your Railway domain

### Manage deployment

```sh
railway logs --service data-agent      # View logs
railway open                         # Open dashboard
railway up --service data-agent -d     # Update after changes
```

---

## The Data Agent

The Data Agent answers questions about your data with insights, not just raw results.

**Try it:**
```
Who has won the most F1 World Championships?
How many races has Lewis Hamilton won?
Who won the most races in 2019?
What tables are in the database?
```

**How it works:**
- **6 layers of context** for grounded SQL generation
- **LearningMachine** remembers corrections and improves over time
- **Knowledge base** stores validated queries for reuse

**Load F1 sample data:**
```sh
# Local
docker exec -it data-agent-api python -m da.scripts.load_data

# Railway
railway run python -m da.scripts.load_data
```

---

## Add Your Own Data

### 1. Create table metadata

```json
// knowledge/tables/my_table.json
{
  "table_name": "users",
  "table_description": "User accounts",
  "table_columns": [
    {"name": "id", "type": "INTEGER", "description": "Primary key"},
    {"name": "email", "type": "TEXT", "description": "User email"}
  ],
  "data_quality_notes": [
    "Email is always stored lowercase"
  ]
}
```

### 2. Add business rules

```json
// knowledge/business/my_rules.json
{
  "metrics": [
    {
      "name": "Active User",
      "definition": "User with login in last 30 days",
      "table": "users"
    }
  ],
  "common_gotchas": [
    {
      "issue": "Timezone handling",
      "tables_affected": ["users"],
      "solution": "All timestamps are UTC"
    }
  ]
}
```

### 3. Load your data

```sh
# Load CSV/Parquet into the database
docker exec -it data-agent-api python -c "
import pandas as pd
from sqlalchemy import create_engine
from db import db_url

df = pd.read_csv('/path/to/data.csv')
engine = create_engine(db_url)
df.to_sql('my_table', engine, if_exists='replace', index=False)
"
```

---

## Local Development

For development without Docker:

```sh
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup environment
./scripts/venv_setup.sh
source .venv/bin/activate

# Start PostgreSQL (required)
docker compose up -d data-agent-db

# Load sample data
python -m da.scripts.load_data

# Run the app
python -m app.main
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `EXA_API_KEY` | No | - | Exa API key for web research (Layer 4) |
| `PORT` | No | `8000` | API server port |
| `DB_HOST` | No | `localhost` | Database host |
| `DB_PORT` | No | `5432` | Database port |
| `DB_USER` | No | `ai` | Database user |
| `DB_PASS` | No | `ai` | Database password |
| `DB_DATABASE` | No | `ai` | Database name |
| `RUNTIME_ENV` | No | `prd` | Set to `dev` for auto-reload |

---

## Learn More

- [OpenAI Data Agent Article](https://openai.com/index/how-openai-built-its-data-agent/)
- [Agno Documentation](https://docs.agno.com)
- [AgentOS Documentation](https://docs.agno.com/agent-os/introduction)
- [Discord Community](https://agno.com/discord)

