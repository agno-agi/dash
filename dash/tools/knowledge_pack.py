"""Knowledge Pack Pipeline tools (Phase 5.4).

After each incident resolution, Ops Dash can auto-generate:
- Validated queries: the timeline reconstruction query, saved via save_validated_query()
- Learnings: incident signature (symptom → root cause mapping), saved via save_learning()
- Runbook suggestion: markdown patch for relevant runbook (human-reviewed)

Uses the existing Knowledge and LearningMachine infrastructure to persist
artifacts that make the system smarter with every resolved incident.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from agno.knowledge import Knowledge
from agno.knowledge.reader.text_reader import TextReader
from agno.tools import tool
from agno.utils.log import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, OperationalError


def create_knowledge_pack_tools(
    db_url: str,
    knowledge: Knowledge,
    learnings: Knowledge,
) -> list:
    """Create knowledge pack pipeline tools.

    Args:
        db_url: SQLAlchemy database URL for the ops warehouse.
        knowledge: The ops_knowledge Knowledge instance (for validated queries).
        learnings: The ops_learnings Knowledge instance (for incident signatures).

    Returns:
        List of @tool-decorated functions for knowledge pack generation.
    """
    engine = create_engine(db_url)

    # ── Tool: generate_knowledge_pack ────────────────────────────

    @tool
    def generate_knowledge_pack(incident_id: int) -> str:
        """Generate a knowledge pack from a resolved incident.

        Reads the incident marker, extracts the timeline query, root cause,
        resolution, and affected services, then auto-generates:
        1. A validated query saved to the knowledge base
        2. An incident signature saved as a learning
        3. A runbook suggestion (returned as markdown, not auto-merged)

        Call this AFTER resolving an incident with resolve_incident().

        Args:
            incident_id: The resolved incident's ID.

        Returns:
            Summary of generated knowledge artifacts.
        """
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT id, title, severity, started_at, resolved_at, "
                        "affected_services, root_cause, resolution, "
                        "timeline_query, knowledge_pack "
                        "FROM incident_markers WHERE id = :id"
                    ),
                    {"id": incident_id},
                )
                row = result.fetchone()

            if not row:
                return f"Error: Incident #{incident_id} not found."

            title = row[1]
            severity = row[2]
            started_at = str(row[3]) if row[3] else "unknown"
            resolved_at = str(row[4]) if row[4] else None
            services = row[5] or []
            root_cause = row[6]
            resolution = row[7]
            timeline_query = row[8]
            existing_kp = row[9] or {}

            if not resolved_at:
                return f"Error: Incident #{incident_id} is not yet resolved. Resolve it first."

            if not root_cause or not resolution:
                return (
                    f"Error: Incident #{incident_id} is missing root_cause or resolution. "
                    "Both are required to generate a knowledge pack."
                )

            artifacts = []

            # ── 1. Save validated query ──────────────────────────
            if timeline_query:
                query_name = f"incident_{incident_id}_timeline"
                query_payload = {
                    "type": "validated_query",
                    "name": query_name,
                    "question": f"Reconstruct the timeline for incident #{incident_id}: {title}",
                    "query": timeline_query,
                    "summary": (
                        f"Timeline reconstruction for {severity} incident "
                        f"affecting {', '.join(services)}. "
                        f"Root cause: {root_cause[:100]}"
                    ),
                    "tables_used": ["ops_unified_timeline"],
                    "incident_id": incident_id,
                }
                try:
                    knowledge.insert(
                        name=query_name,
                        text_content=json.dumps(query_payload, ensure_ascii=False, indent=2),
                        reader=TextReader(),
                        skip_if_exists=True,
                    )
                    artifacts.append(f"Validated query '{query_name}' saved")
                except (AttributeError, TypeError, ValueError, OSError) as e:
                    artifacts.append(f"Query save failed: {e}")

            # ── 2. Save incident signature as learning ───────────
            signature = {
                "type": "incident_signature",
                "incident_id": incident_id,
                "title": title,
                "severity": severity,
                "affected_services": services,
                "symptoms": _extract_symptoms(title, root_cause, existing_kp),
                "root_cause": root_cause,
                "resolution": resolution,
                "started_at": started_at,
                "resolved_at": resolved_at,
                "duration_minutes": _compute_duration(row[3], row[4]),
            }

            # Merge any gotchas from the existing knowledge pack
            if isinstance(existing_kp, dict) and existing_kp.get("gotchas"):
                signature["gotchas"] = existing_kp["gotchas"]

            learning_name = f"incident_sig_{incident_id}_{_slugify(title)}"
            try:
                learnings.insert(
                    name=learning_name,
                    text_content=json.dumps(signature, ensure_ascii=False, indent=2),
                    reader=TextReader(),
                    skip_if_exists=True,
                )
                artifacts.append(f"Incident signature '{learning_name}' saved")
            except (AttributeError, TypeError, ValueError, OSError) as e:
                artifacts.append(f"Learning save failed: {e}")

            # ── 3. Generate runbook suggestion ───────────────────
            runbook_md = _generate_runbook_suggestion(
                incident_id=incident_id,
                title=title,
                severity=severity,
                services=services,
                root_cause=root_cause,
                resolution=resolution,
                started_at=started_at,
                resolved_at=resolved_at,
                existing_kp=existing_kp,
            )
            artifacts.append("Runbook suggestion generated (see below)")

            # ── 4. Update incident knowledge_pack with metadata ──
            updated_kp = dict(existing_kp) if isinstance(existing_kp, dict) else {}
            updated_kp["knowledge_pack_generated"] = True
            updated_kp["generated_at"] = datetime.now(timezone.utc).isoformat()
            updated_kp["artifacts"] = {
                "validated_query": query_name if timeline_query else None,
                "learning": learning_name,
            }

            try:
                with engine.connect() as conn:
                    conn.execute(
                        text(
                            "UPDATE incident_markers SET knowledge_pack = :kp "
                            "WHERE id = :id"
                        ),
                        {"id": incident_id, "kp": json.dumps(updated_kp)},
                    )
                    conn.commit()
                artifacts.append("Incident knowledge_pack metadata updated")
            except (OperationalError, DatabaseError) as e:
                artifacts.append(f"Knowledge pack update failed: {e}")

            # ── Build response ───────────────────────────────────
            lines = [
                f"**Knowledge Pack Generated** for Incident #{incident_id}: {title}",
                "",
                "**Artifacts:**",
            ]
            for a in artifacts:
                lines.append(f"- {a}")

            lines.extend(["", "---", "", "**Runbook Suggestion** (review before merging):", "", runbook_md])

            return "\n".join(lines)

        except OperationalError as e:
            logger.error("Knowledge pack generation failed: %s", e)
            return f"Error: Database connection failed — {e}"
        except DatabaseError as e:
            logger.error("Knowledge pack query error: %s", e)
            return f"Error: {e}"

    # ── Tool: get_incident_knowledge_pack ─────────────────────────

    @tool
    def get_incident_knowledge_pack(incident_id: int) -> str:
        """Retrieve the knowledge pack for a resolved incident.

        Returns the full knowledge pack including root cause, resolution,
        gotchas, validated queries, and any learnings generated.

        Args:
            incident_id: The incident ID to look up.

        Returns:
            Formatted knowledge pack contents or error message.
        """
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT id, title, severity, root_cause, resolution, "
                        "affected_services, knowledge_pack, resolved_at "
                        "FROM incident_markers WHERE id = :id"
                    ),
                    {"id": incident_id},
                )
                row = result.fetchone()

            if not row:
                return f"Error: Incident #{incident_id} not found."

            title = row[1]
            severity = row[2]
            root_cause = row[3]
            resolution = row[4]
            services = row[5] or []
            kp = row[6] or {}
            resolved_at = row[7]

            lines = [
                f"**Knowledge Pack** — Incident #{incident_id}: {title}",
                f"- Severity: {severity}",
                f"- Services: {', '.join(services) if services else 'unknown'}",
                f"- Status: {'Resolved' if resolved_at else 'ONGOING'}",
                "",
            ]

            if root_cause:
                lines.append(f"**Root Cause:** {root_cause}")
            if resolution:
                lines.append(f"**Resolution:** {resolution}")

            if isinstance(kp, dict) and kp:
                lines.append("")
                if kp.get("gotchas"):
                    lines.append("**Gotchas:**")
                    for g in kp["gotchas"]:
                        lines.append(f"- {g}")
                if kp.get("artifacts"):
                    lines.append("")
                    lines.append("**Linked Artifacts:**")
                    art = kp["artifacts"]
                    if art.get("validated_query"):
                        lines.append(f"- Query: `{art['validated_query']}`")
                    if art.get("learning"):
                        lines.append(f"- Learning: `{art['learning']}`")
                if kp.get("generated_at"):
                    lines.append(f"\n_Knowledge pack generated: {kp['generated_at']}_")
            else:
                lines.append("\n_No knowledge pack generated yet. Use `generate_knowledge_pack` after resolving._")

            return "\n".join(lines)

        except OperationalError as e:
            logger.error("Knowledge pack retrieval failed: %s", e)
            return f"Error: Database connection failed — {e}"
        except DatabaseError as e:
            logger.error("Knowledge pack query error: %s", e)
            return f"Error: {e}"

    return [generate_knowledge_pack, get_incident_knowledge_pack]


# ── Helpers ──────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    """Convert text to a short, safe slug for naming."""
    slug = text.lower().replace(" ", "_")
    # Keep only alphanumeric and underscores
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    return slug[:40]


def _extract_symptoms(title: str, root_cause: str, kp: dict | None) -> list[str]:
    """Extract symptom keywords from incident data."""
    symptoms = []
    text = f"{title} {root_cause}".lower()

    symptom_patterns = {
        "oom": "Out of memory / OOM kill",
        "crash": "Service crash / restart loop",
        "timeout": "Request timeout",
        "502": "HTTP 502 Bad Gateway",
        "503": "HTTP 503 Service Unavailable",
        "521": "Cloudflare 521 (origin down)",
        "cert": "TLS certificate issue",
        "dns": "DNS resolution failure",
        "disk": "Disk space exhaustion",
        "memory": "Memory pressure",
        "cpu": "CPU saturation",
        "connection refused": "Connection refused",
        "deploy": "Deployment failure",
        "rollback": "Rollback required",
    }

    for pattern, description in symptom_patterns.items():
        if pattern in text:
            symptoms.append(description)

    if isinstance(kp, dict) and kp.get("symptoms"):
        symptoms.extend(kp["symptoms"])

    return list(dict.fromkeys(symptoms))  # deduplicate preserving order


def _compute_duration(started_at, resolved_at) -> int | None:
    """Compute incident duration in minutes."""
    if not started_at or not resolved_at:
        return None
    try:
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        if isinstance(resolved_at, str):
            resolved_at = datetime.fromisoformat(resolved_at)
        delta = resolved_at - started_at
        return max(0, int(delta.total_seconds() / 60))
    except (ValueError, TypeError):
        return None


def _generate_runbook_suggestion(
    incident_id: int,
    title: str,
    severity: str,
    services: list[str],
    root_cause: str,
    resolution: str,
    started_at: str,
    resolved_at: str,
    existing_kp: dict | None,
) -> str:
    """Generate a markdown runbook patch suggestion."""
    svc_str = ", ".join(services) if services else "unknown"
    gotchas = ""
    if isinstance(existing_kp, dict) and existing_kp.get("gotchas"):
        gotchas_list = "\n".join(f"- {g}" for g in existing_kp["gotchas"])
        gotchas = f"\n### Gotchas\n\n{gotchas_list}\n"

    return f"""### Incident #{incident_id}: {title}

**Severity:** {severity}
**Affected Services:** {svc_str}
**Duration:** {started_at} → {resolved_at}

### Root Cause

{root_cause}

### Resolution Steps

{resolution}
{gotchas}
### Prevention

<!-- TODO: Add prevention steps based on root cause analysis -->

### Detection

To detect this issue early, monitor for:
- Timeline query: `incident_{incident_id}_timeline` (saved to knowledge base)
- Similar incidents: `find_similar_incidents(services="{svc_str}")` or keywords from root cause

---
_Auto-generated from incident #{incident_id}. Review before merging into runbooks._"""
