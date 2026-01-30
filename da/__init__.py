"""
Data Agent
==========

A self-learning data agent inspired by OpenAI's internal data agent.

Features:
- 6 layers of context for grounded reasoning
- LearningMachine for continuous improvement from corrections
- Knowledge-based SQL generation (searches before generating)
- Provides insights, not just raw data

The 6 Layers of Context:
1. Table Metadata - knowledge/tables/
2. Human Annotations - knowledge/business/
3. Query Patterns - knowledge/queries/
4. Institutional Knowledge - MCP connectors
5. Memory - LearningMachine
6. Runtime Context - introspect_schema tool

Usage:
    python -m da

See README.md for full documentation.
"""

from da.agent import data_agent, data_agent_knowledge

__all__ = [
    "data_agent",
    "data_agent_knowledge",
]

__version__ = "1.0.0"
