"""Incident timeline reconstruction and management tools (Phase 5.3).

Provides Ops Dash with the ability to:
- Reconstruct incident timelines from the unified event view
- Create incident markers for new incidents
- Search for incidents matching a symptom pattern
- Retrieve and replay stored timeline queries

Uses direct SQL against the ops warehouse (same connection as SQLTools).
"""

import json
from datetime import datetime, timezone

from agno.tools import tool
from agno.utils.log import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, OperationalError


def create_incident_tools(db_url: str) -> list:
    """Create incident management tools with database connection injected.

    Args:
        db_url: SQLAlchemy database URL for the ops warehouse.

    Returns:
        List of @tool-decorated functions for incident management.
    """
    engine = create_engine(db_url)

    # ── Tool: reconstruct_timeline ──────────────────────────────

    @tool
    def reconstruct_timeline(
        start_time: str,
        end_time: str,
        entity_filter: str | None = None,
        limit: int = 200,
    ) -> str:
        """Reconstruct an incident timeline for a given time window.

        Queries the ops_unified_timeline view which merges deploy events,
        docker container events, and incident markers into a single
        chronological stream. This is the primary tool for incident
        investigation and post-mortem analysis.

        Args:
            start_time: Start of time window (ISO 8601, e.g. '2025-01-15T03:00:00Z').
            end_time: End of time window (ISO 8601, e.g. '2025-01-15T04:00:00Z').
            entity_filter: Optional entity name filter (partial match, e.g. 'ghost').
            limit: Maximum events to return (default 200).

        Returns:
            Chronological event list with source, type, entity, and details.
        """
        try:
            with engine.connect() as conn:
                if entity_filter:
                    result = conn.execute(
                        text(
                            "SELECT occurred_at, source, event_type, entity, environment, details "
                            "FROM ops_unified_timeline "
                            "WHERE occurred_at BETWEEN :start AND :end "
                            "AND entity ILIKE :pattern "
                            "ORDER BY occurred_at "
                            "LIMIT :lim"
                        ),
                        {
                            "start": start_time,
                            "end": end_time,
                            "pattern": f"%{entity_filter}%",
                            "lim": min(limit, 500),
                        },
                    )
                else:
                    result = conn.execute(
                        text(
                            "SELECT occurred_at, source, event_type, entity, environment, details "
                            "FROM ops_unified_timeline "
                            "WHERE occurred_at BETWEEN :start AND :end "
                            "ORDER BY occurred_at "
                            "LIMIT :lim"
                        ),
                        {"start": start_time, "end": end_time, "lim": min(limit, 500)},
                    )

                rows = result.fetchall()

            if not rows:
                return f"No events found between {start_time} and {end_time}" + (
                    f" for entity '{entity_filter}'" if entity_filter else ""
                )

            lines = [
                f"**Incident Timeline** ({len(rows)} events)",
                f"Window: {start_time} → {end_time}",
                "",
            ]

            for row in rows:
                ts = str(row[0])[:19] if row[0] else "?"
                source = row[1] or "?"
                etype = row[2] or "?"
                entity = row[3] or "?"
                env = row[4] or "?"

                icon = {"deploy": "D", "docker": "C", "incident": "!"}
                lines.append(f"[{icon.get(source, '?')}] {ts} | {source}/{etype} | {entity} ({env})")

            return "\n".join(lines)

        except OperationalError as e:
            logger.error("Timeline reconstruction failed: %s", e)
            return f"Error: Database connection failed — {e}"
        except DatabaseError as e:
            logger.error("Timeline query error: %s", e)
            return f"Error: {e}"

    # ── Tool: create_incident_marker ────────────────────────────

    @tool
    def create_incident_marker(
        title: str,
        severity: str,
        started_at: str,
        affected_services: str,
        root_cause: str | None = None,
        resolution: str | None = None,
    ) -> str:
        """Create an incident marker in the ops warehouse.

        Records a new incident for tracking and future pattern matching.
        Incident markers anchor timeline reconstructions and link to
        knowledge packs when the incident is resolved.

        Args:
            title: Short incident title (e.g. 'Ghost OOM crash loop').
            severity: Incident severity ('critical', 'warning', 'info').
            started_at: When the incident began (ISO 8601).
            affected_services: Comma-separated service names (e.g. 'ghost-blog,ghost-db').
            root_cause: Root cause analysis (if known).
            resolution: How the incident was resolved (if resolved).

        Returns:
            Confirmation with the new incident ID.
        """
        if severity not in ("critical", "warning", "info"):
            return f"Error: severity must be 'critical', 'warning', or 'info', got '{severity}'"

        services = [s.strip() for s in affected_services.split(",") if s.strip()]
        if not services:
            return "Error: At least one affected service is required."

        # Build the timeline query for this incident
        timeline_sql = (
            "SELECT occurred_at, source, event_type, entity, environment, details "
            "FROM ops_unified_timeline "
            f"WHERE occurred_at BETWEEN '{started_at}'::timestamptz - INTERVAL '15 minutes' "
            f"AND COALESCE(NULL, NOW()) + INTERVAL '15 minutes' "
            "ORDER BY occurred_at"
        )

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "INSERT INTO incident_markers "
                        "(title, severity, started_at, affected_services, root_cause, resolution, timeline_query) "
                        "VALUES (:title, :severity, :started_at, :services, :root_cause, :resolution, :timeline_sql) "
                        "RETURNING id"
                    ),
                    {
                        "title": title,
                        "severity": severity,
                        "started_at": started_at,
                        "services": services,
                        "root_cause": root_cause,
                        "resolution": resolution,
                        "timeline_sql": timeline_sql,
                    },
                )
                incident_id = result.scalar()
                conn.commit()

            return (
                f"**Incident Created:** #{incident_id}\n"
                f"- Title: {title}\n"
                f"- Severity: {severity}\n"
                f"- Started: {started_at}\n"
                f"- Services: {', '.join(services)}\n"
                f"- Timeline query stored for replay"
            )

        except OperationalError as e:
            logger.error("Failed to create incident marker: %s", e)
            return f"Error: Database connection failed — {e}"
        except DatabaseError as e:
            logger.error("Failed to insert incident marker: %s", e)
            return f"Error: {e}"

    # ── Tool: resolve_incident ──────────────────────────────────

    @tool
    def resolve_incident(
        incident_id: int,
        root_cause: str,
        resolution: str,
        knowledge_pack: str = "{}",
    ) -> str:
        """Mark an incident as resolved and store resolution details.

        Updates the incident marker with root cause, resolution, and
        an optional knowledge pack (JSONB) containing gotchas, validated
        queries, and runbook patches discovered during resolution.

        Args:
            incident_id: The incident ID to resolve.
            root_cause: Root cause analysis.
            resolution: How the incident was resolved.
            knowledge_pack: JSON string with resolution artifacts (optional).

        Returns:
            Confirmation with updated incident details.
        """
        try:
            kp = json.loads(knowledge_pack) if knowledge_pack else {}
        except json.JSONDecodeError:
            return f"Error: Invalid JSON in knowledge_pack: {knowledge_pack[:100]}"

        now = datetime.now(timezone.utc).isoformat()

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "UPDATE incident_markers "
                        "SET resolved_at = :now, root_cause = :root_cause, "
                        "resolution = :resolution, knowledge_pack = :kp "
                        "WHERE id = :id AND resolved_at IS NULL "
                        "RETURNING id, title, started_at"
                    ),
                    {
                        "id": incident_id,
                        "now": now,
                        "root_cause": root_cause,
                        "resolution": resolution,
                        "kp": json.dumps(kp),
                    },
                )
                row = result.fetchone()
                conn.commit()

            if not row:
                return f"Error: Incident #{incident_id} not found or already resolved."

            return (
                f"**Incident Resolved:** #{row[0]} — {row[1]}\n"
                f"- Started: {row[2]}\n"
                f"- Resolved: {now}\n"
                f"- Root Cause: {root_cause}\n"
                f"- Resolution: {resolution}\n"
                f"- Knowledge Pack: {'stored' if kp else 'none'}"
            )

        except OperationalError as e:
            logger.error("Failed to resolve incident: %s", e)
            return f"Error: Database connection failed — {e}"
        except DatabaseError as e:
            logger.error("Failed to update incident marker: %s", e)
            return f"Error: {e}"

    # ── Tool: find_similar_incidents ─────────────────────────────

    @tool
    def find_similar_incidents(
        services: str | None = None,
        keywords: str | None = None,
        limit: int = 10,
    ) -> str:
        """Find past incidents matching a symptom pattern.

        Searches incident history by affected services and/or keyword
        matching against title and root cause. Use this to check if
        a current issue matches a known incident pattern before
        improvising a fix.

        Args:
            services: Comma-separated service names to match (e.g. 'ghost-blog,traefik').
            keywords: Keywords to match in title or root_cause (e.g. 'OOM crash').
            limit: Maximum results (default 10).

        Returns:
            Matching incidents with severity, root cause, and resolution.
        """
        if not services and not keywords:
            return "Error: Provide at least services or keywords to search."

        conditions = []
        params: dict = {"lim": min(limit, 50)}

        if services:
            svc_list = [s.strip() for s in services.split(",") if s.strip()]
            conditions.append("affected_services && :svc_arr::TEXT[]")
            params["svc_arr"] = svc_list

        if keywords:
            conditions.append("(root_cause ILIKE :kw_pattern OR title ILIKE :kw_pattern)")
            params["kw_pattern"] = f"%{keywords}%"

        where = " OR ".join(conditions)

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT id, title, severity, started_at, resolved_at, "
                        "affected_services, root_cause, resolution, "
                        "knowledge_pack IS NOT NULL AS has_knowledge_pack "
                        f"FROM incident_markers WHERE {where} "
                        "ORDER BY started_at DESC LIMIT :lim"
                    ),
                    params,
                )
                rows = result.fetchall()

            if not rows:
                return "No matching incidents found." + (
                    f"\nSearched: services={services}, keywords={keywords}" if services or keywords else ""
                )

            lines = [f"**Similar Incidents** ({len(rows)} matches)", ""]
            for row in rows:
                resolved = "resolved" if row[4] else "ONGOING"
                kp = "+" if row[8] else "-"
                lines.append(f"[{kp}] #{row[0]} [{row[2]}] {row[1]} ({resolved})")
                if row[6]:
                    lines.append(f"    Root cause: {row[6][:100]}")
                if row[7]:
                    lines.append(f"    Resolution: {row[7][:100]}")
                lines.append(f"    Services: {', '.join(row[5]) if row[5] else 'unknown'}")
                lines.append("")

            return "\n".join(lines)

        except OperationalError as e:
            logger.error("Incident search failed: %s", e)
            return f"Error: Database connection failed — {e}"
        except DatabaseError as e:
            logger.error("Incident search error: %s", e)
            return f"Error: {e}"

    return [
        reconstruct_timeline,
        create_incident_marker,
        resolve_incident,
        find_similar_incidents,
    ]
