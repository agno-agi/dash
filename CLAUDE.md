# CLAUDE.md

## Project Overview

Dash is a self-learning data agent that delivers **insights, not just SQL results**. It grounds SQL generation in 6 layers of context and improves automatically with every query. Inspired by [OpenAI's in-house data agent](https://openai.com/index/how-openai-built-its-data-agent/).

## Structure

```
dash/
├── agents.py             # Dash agents (dash, reasoning_dash)
├── paths.py              # Path constants
├── knowledge/            # Knowledge files (tables, queries, business rules)
│   ├── tables/           # Table metadata JSON files
│   ├── queries/          # Validated SQL queries
│   └── business/         # Business rules and metrics
├── context/
│   ├── semantic_model.py # Layer 1: Table usage
│   └── business_rules.py # Layer 2: Business rules
├── tools/
│   ├── introspect.py     # Layer 6: Runtime context
│   └── save_query.py     # Save validated queries
├── scripts/
│   ├── load_data.py      # Load F1 sample data
│   └── load_knowledge.py # Load knowledge files
└── evals/
    ├── test_cases.py     # Test cases
    └── run_evals.py      # Run evaluations

app/
├── main.py               # API entry point (AgentOS)
└── config.yaml           # Agent configuration

db/
├── session.py            # PostgreSQL session factory
└── url.py                # Database URL builder
```

## Commands

```bash
./scripts/venv_setup.sh && source .venv/bin/activate
./scripts/format.sh      # Format code
./scripts/validate.sh    # Lint + type check
python -m dash           # CLI mode
python -m dash.agents    # Test mode (runs sample query)

# Data & Knowledge
python -m dash.scripts.load_data       # Load F1 sample data
python -m dash.scripts.load_knowledge  # Load knowledge into vector DB

# Evaluations
python -m dash.evals.run_evals              # Run all evals
python -m dash.evals.run_evals -c basic     # Run specific category
python -m dash.evals.run_evals -v           # Verbose mode
```

## Architecture

**Two Learning Systems:**

| System | What It Stores | How It Evolves |
|--------|---------------|----------------|
| **Knowledge** | Validated queries, table metadata, business rules | Curated by you + Dash |
| **Learnings** | Error patterns, type gotchas, discovered fixes | Managed by Learning Machine automatically |

```python
# KNOWLEDGE: Static, curated (table schemas, validated queries)
dash_knowledge = Knowledge(...)

# LEARNINGS: Dynamic, discovered (error patterns, gotchas)
dash_learnings = Knowledge(...)

dash = Agent(
    knowledge=dash_knowledge,
    search_knowledge=True,
    learning=LearningMachine(
        knowledge=dash_learnings,  # separate from static knowledge
        user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
        user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
        learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.AGENTIC),
    ),
)
```

**Learning Machine provides:**
- `search_learnings` / `save_learning` tools
- `user_profile` - structured facts about user
- `user_memory` - unstructured observations

## The Six Layers of Context

| Layer | Source | Code |
|-------|--------|------|
| 1. Table Usage | `dash/knowledge/tables/*.json` | `dash/context/semantic_model.py` |
| 2. Business Rules | `dash/knowledge/business/*.json` | `dash/context/business_rules.py` |
| 3. Query Patterns | `dash/knowledge/queries/*.sql` | Loaded into knowledge base |
| 4. Institutional Knowledge | Exa MCP | `dash/agents.py` |
| 5. Learnings | Learning Machine | Separate knowledge base |
| 6. Runtime Context | `introspect_schema` | `dash/tools/introspect.py` |

## Data Quality (F1 Dataset)

| Issue | Solution |
|-------|----------|
| `position` is TEXT in `drivers_championship` | Use `position = '1'` |
| `position` is INTEGER in `constructors_championship` | Use `position = 1` |
| `date` is TEXT in `race_wins` | Use `TO_DATE(date, 'DD Mon YYYY')` |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `EXA_API_KEY` | No | Exa for web research |
| `DB_*` | No | Database config |
