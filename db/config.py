"""Database configuration: internal DB and optional analytics registries."""

import os

from db.url import db_url as internal_db_url

ANALYTICS_PREFIX = "ANALYTICS_DB_"
ANALYTICS_DESC_SUFFIX = "_DESC"
IMPLICIT_DEFAULT_NAME = "default"


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _iter_explicit_analytics_entries() -> list[tuple[str, str]]:
    """Return explicit ANALYTICS_DB_<NAME>=<url> entries from env vars."""
    entries: list[tuple[str, str]] = []
    for key, value in os.environ.items():
        if not key.startswith(ANALYTICS_PREFIX) or not value:
            continue
        if key.endswith(ANALYTICS_DESC_SUFFIX):
            continue

        raw_name = key[len(ANALYTICS_PREFIX) :]
        name = _normalize_name(raw_name)
        if not name:
            continue
        entries.append((name, value))
    return entries


def get_internal_db_url() -> str:
    """Internal DB URL used by Dash for knowledge/learnings/AgentOS."""
    return internal_db_url


def has_explicit_analytics_dbs() -> bool:
    """True when at least one ANALYTICS_DB_<NAME> URL is configured."""
    return bool(_iter_explicit_analytics_entries())


def get_analytics_registry() -> dict[str, str]:
    """Return analytics DB registry by logical name.

    Behavior:
    - If explicit ANALYTICS_DB_<NAME> variables exist, return those.
    - If none exist, fall back to a single implicit entry to internal DB.
    """
    registry = dict(_iter_explicit_analytics_entries())
    if registry:
        return registry
    return {IMPLICIT_DEFAULT_NAME: internal_db_url}


def get_analytics_descriptions() -> dict[str, str]:
    """Return optional ANALYTICS_DB_<NAME>_DESC descriptions by name."""
    descriptions: dict[str, str] = {}
    for key, value in os.environ.items():
        if (
            not key.startswith(ANALYTICS_PREFIX)
            or not key.endswith(ANALYTICS_DESC_SUFFIX)
            or not value
        ):
            continue

        raw_name = key[len(ANALYTICS_PREFIX) : -len(ANALYTICS_DESC_SUFFIX)]
        name = _normalize_name(raw_name)
        if not name:
            continue
        descriptions[name] = value
    return descriptions
