# Dash Zero-Knowledge Evaluation

**Principle:** Evaluate agent capability WITHOUT dataset-specific knowledge

## The Right Way to Evaluate

### ❌ What We Don't Include (Cheating)
- Table-specific schemas
- Dataset-specific query patterns
- Business rules for specific domain
- Pre-configured column mappings

### ✅ What We Include (Fair Game)
- **Generic SQL best practices** (revenue = price × (1 - discount))
- **Generic query patterns** (aggregation, joins, date ranges)
- **Agent tools** (introspect_schema, list_tables)
- **Learning system** (save_learning, search_learnings)

## How Dash Learns (The Right Way)

```
User Question: "What is the total revenue?"
       ↓
1. Search generic knowledge → finds "revenue calculation pattern"
       ↓
2. list_tables → discovers "lineitem" table
       ↓
3. introspect_schema(table='lineitem') → learns columns
       ↓
4. Generates SQL based on discovered schema
       ↓
5. Executes → if error, diagnoses and saves learning
       ↓
6. Returns insight
       ↓
7. Next similar query → uses saved learning
```

## Zero-Knowledge Results (5-Query Sample)

| Query | Score | Status |
|-------|-------|--------|
| Q1: Pricing Summary | 45% | ✅ Good |
| Q3: Shipping Priority | 25% | ⚠️ Partial |
| Q5: Local Supplier Volume | 50% | ✅ Good |
| Q6: Forecasting Revenue | 0% | ❌ Failed (validation issue) |
| Q14: Promotion Effect | 100% | ⭐ Perfect |
| **Average** | **44%** | **Decent** |

## Comparison: Knowledge vs Zero-Knowledge

| Query | With TPC-H Hints | Zero Knowledge | Delta |
|-------|------------------|----------------|-------|
| Q1 | 35% | 45% | +10% (!!) |
| Q14 | 100% | 100% | 0% |
| Average (5 queries) | ~53% | ~44% | -9% |

**Finding:** Only 9% score difference! Agent handles unknown schemas well.

## What Makes This Fair

1. **Agent must discover schema** - Uses `list_tables`, `describe_table`, `introspect_schema`
2. **Agent must reason** - No pre-configured query patterns to copy
3. **Agent must learn** - Errors trigger `save_learning` for future queries
4. **Agent must generalize** - Generic patterns must work across any database

## How to Improve (The Right Way)

### ✅ Acceptable Improvements
1. **Better generic patterns** - More SQL examples that work anywhere
2. **Smarter discovery** - Improve schema introspection logic
3. **Learning retention** - Save more learnings, retrieve better
4. **Error recovery** - Better diagnosis and fix strategies

### ❌ Unacceptable (Cheating)
1. Pre-loading TPC-H table schemas
2. Adding TPC-H query patterns
3. Hardcoding business rules
4. Domain-specific optimizations

## The Self-Learning Test

**Hypothesis:** Agent should improve over time through learnings

**Test Plan:**
1. Run Q1 (cold start - no knowledge)
2. Run Q1 again (should use learnings)
3. Run similar query (should apply pattern)
4. Check: Did learning happen? Did it help?

## True Evaluation Principle

> "The best data agent is one that can walk into ANY database,
> discover the schema, learn the patterns, and deliver insights -
> without pre-configuration."

This is what we're testing.
