"""Infra-agent tool bridge — Agno @tool wrappers for the Dockhand infra-agent portal API.

Provides Ops Dash with the ability to:
- Submit infrastructure jobs (deploy, healthcheck, scan, etc.)
- Query job status and history
- Retrieve drift balance and health scores
- List active durable workflows
- Fetch platform knowledge

Each tool makes a synchronous HTTP call to the infra-agent's /portal/* endpoints.
The factory function `create_infra_agent_tools` returns a list of @tool-decorated
callables that can be added directly to the Agno agent's tools list.
"""

import json

import httpx
from agno.tools import tool
from agno.utils.log import logger


def create_infra_agent_tools(base_url: str, secret: str) -> list:
    """Create infra-agent tool set with connection details injected.

    Args:
        base_url: Base URL of the infra-agent (e.g. "http://infra-agent:8042").
        secret: Portal secret for X-Portal-Secret header authentication.

    Returns:
        List of @tool-decorated functions ready for Agno agent consumption.
    """
    _headers = {
        "X-Portal-Secret": secret,
        "Content-Type": "application/json",
    }
    _timeout = httpx.Timeout(30.0, connect=10.0)

    def _get(path: str, params: dict | None = None) -> dict:
        """Make authenticated GET to infra-agent."""
        url = f"{base_url.rstrip('/')}{path}"
        resp = httpx.get(url, headers=_headers, params=params, timeout=_timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(path: str, payload: dict | None = None) -> dict:
        """Make authenticated POST to infra-agent."""
        url = f"{base_url.rstrip('/')}{path}"
        resp = httpx.post(url, headers=_headers, json=payload or {}, timeout=_timeout)
        resp.raise_for_status()
        return resp.json()

    # ── Tool: submit_infra_job ──────────────────────────────────

    @tool
    def submit_infra_job(
        kind: str,
        args: str = "{}",
        requested_by: str = "ops-dash",
    ) -> str:
        """Submit an infrastructure job to the platform's job queue.

        Use this to trigger deployments, scans, healthchecks, ETL runs, or any
        other infrastructure operation. The job goes through the policy engine
        and may require human approval before execution.

        Args:
            kind: Job kind (e.g. "dokploy.redeploy", "platform_updates_scan",
                  "ops_warehouse_etl", "wordpress_weekly_cycle", "service_healthcheck").
            args: JSON string of job arguments (e.g. '{"project": "ghost-blog", "host": "prod"}').
            requested_by: Actor identifier for audit trail.

        Returns:
            Job submission result with job_id, status, and approval info.
        """
        try:
            parsed_args = json.loads(args) if isinstance(args, str) else args
        except json.JSONDecodeError:
            return f"Error: Invalid JSON in args: {args}"

        try:
            result = _post(
                "/portal/jobs",
                {
                    "kind": kind,
                    "args": parsed_args,
                    "requested_by": requested_by,
                },
            )
            lines = [
                f"**Job Submitted:** {result.get('job_id', 'unknown')}",
                f"- Status: {result.get('status', 'unknown')}",
                f"- Approval Required: {result.get('approval_required', False)}",
            ]
            if result.get("approval_id"):
                lines.append(f"- Approval ID: {result['approval_id']}")
            if result.get("message"):
                lines.append(f"- Message: {result['message']}")
            return "\n".join(lines)
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                detail = e.response.text[:200]
            logger.error("submit_infra_job failed: %s %s", e.response.status_code, detail)
            return f"Error ({e.response.status_code}): {detail}"
        except httpx.RequestError as e:
            logger.error("submit_infra_job connection error: %s", e)
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: get_job_status ────────────────────────────────────

    @tool
    def get_job_status(job_id: str) -> str:
        """Get the current status of an infrastructure job.

        Args:
            job_id: The job ID returned from submit_infra_job.

        Returns:
            Job status with summary, result details, and artifact paths.
        """
        try:
            result = _get(f"/portal/jobs/{job_id}")
            lines = [
                f"**Job {result.get('job_id', job_id)}**",
                f"- Status: {result.get('status', 'unknown')}",
            ]
            if result.get("summary"):
                lines.append(f"- Summary: {result['summary']}")
            if result.get("error"):
                lines.append(f"- Error: {result['error']}")
            if result.get("result"):
                # Truncate large results
                result_str = json.dumps(result["result"], indent=2)
                if len(result_str) > 500:
                    result_str = result_str[:500] + "\n... (truncated)"
                lines.append(f"- Result:\n```json\n{result_str}\n```")
            if result.get("artifact_paths"):
                lines.append(f"- Artifacts: {', '.join(result['artifact_paths'])}")
            return "\n".join(lines)
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): Job not found or unavailable"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: list_infra_jobs ───────────────────────────────────

    @tool
    def list_infra_jobs(
        status: str | None = None,
        kind: str | None = None,
        limit: int = 20,
    ) -> str:
        """List recent infrastructure jobs, optionally filtered.

        Args:
            status: Filter by status (queued, running, succeeded, failed, waiting_approval).
            kind: Filter by job kind (e.g. "dokploy.redeploy", "ops_warehouse_etl").
            limit: Max results (default 20, max 100).

        Returns:
            Formatted list of recent jobs with status and timestamps.
        """
        params: dict = {"limit": min(limit, 100)}
        if status:
            params["status"] = status
        if kind:
            params["kind"] = kind

        try:
            result = _get("/portal/jobs", params=params)
            jobs = result.get("jobs", [])
            if not jobs:
                return "No jobs found matching the criteria."

            lines = [f"**Recent Jobs** ({result.get('count', len(jobs))} results)", ""]
            for j in jobs:
                emoji = {"succeeded": "+", "failed": "!", "running": "~", "waiting_approval": "?"}.get(
                    j.get("status", ""), " "
                )
                lines.append(
                    f"[{emoji}] {j.get('job_id', '?')[:8]}.. "
                    f"| {j.get('kind', '?')} "
                    f"| {j.get('status', '?')} "
                    f"| {j.get('created_at', '?')[:16]}"
                )
                if j.get("summary"):
                    lines.append(f"    {j['summary']}")
            return "\n".join(lines)
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): {e.response.text[:200]}"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: get_drift_balance ─────────────────────────────────

    @tool
    def get_drift_balance() -> str:
        """Get the platform's drift balance sheet and health score.

        Returns the current drift debt (risk-weighted configuration drift),
        individual drift items ranked by severity, and the composite
        platform health score (0-100).

        No arguments required — pulls from the latest ETL run.

        Returns:
            Drift balance sheet with scored items and health score.
        """
        try:
            result = _get("/portal/warehouse/drift-balance")
            health = result.get("health_score", {})
            items = result.get("drift_items", [])

            lines = [
                "**Platform Drift Balance**",
                "",
                f"Health Score: **{health.get('score', '?')}/100**",
            ]

            deductions = health.get("deductions", {})
            if deductions:
                lines.append("Deductions:")
                for k, v in deductions.items():
                    if v > 0:
                        lines.append(f"  - {k.replace('_', ' ').title()}: -{v}")

            lines.append(f"\nTotal Drift Debt: **{result.get('drift_debt_total', 0)}**")

            if items:
                lines.extend(["", "Top Drift Items:", ""])
                for item in items[:10]:
                    lines.append(
                        f"- [{item.get('severity', '?')}] {item.get('service_name', '?')} "
                        f"on {item.get('environment', '?')} — "
                        f"debt: {item.get('debt_score', 0)} "
                        f"({item.get('category', 'unknown')})"
                    )
            else:
                lines.append("\nNo drift items — platform is in full compliance.")

            if result.get("etl_timestamp"):
                lines.append(f"\n_Data from ETL run: {result['etl_timestamp']}_")

            return "\n".join(lines)
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): {e.response.text[:200]}"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: get_platform_health ───────────────────────────────

    @tool
    def get_platform_health() -> str:
        """Get a comprehensive platform health overview.

        Combines warehouse status (ETL details, service counts) with the
        drift balance health score. Use this for a quick operational pulse.

        Returns:
            Platform health summary with service counts, drift, and ETL status.
        """
        try:
            warehouse = _get("/portal/warehouse/status")
            drift = _get("/portal/warehouse/drift-balance")
            health = drift.get("health_score", {})

            lines = [
                "**Platform Health Overview**",
                "",
                f"Health Score: **{health.get('score', '?')}/100**",
                "",
                f"- Actual Services: {warehouse.get('actual_services', '?')}",
                f"- Desired Services: {warehouse.get('desired_services', '?')}",
                f"- Drift Observations: {warehouse.get('drift_observations', '?')}",
                f"- Update Status Entries: {warehouse.get('update_status', '?')}",
                f"- Drift Debt Total: {drift.get('drift_debt_total', 0)}",
            ]

            etl = warehouse.get("last_etl", {})
            if etl.get("job_id"):
                lines.extend(
                    [
                        "",
                        f"Last ETL: {etl.get('status', '?')} at {etl.get('timestamp', '?')}",
                        f"  {etl.get('summary', '')}",
                    ]
                )

            return "\n".join(lines)
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): {e.response.text[:200]}"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: list_workflows ────────────────────────────────────

    @tool
    def list_workflows() -> str:
        """List active durable infrastructure workflows.

        Durable workflows (Monty scripts) are multi-step operations that
        persist across pauses — e.g., deploy-and-verify pipelines that
        wait for health checks and TLS certificate validation.

        Returns:
            List of active workflows with their current step and status.
        """
        try:
            result = _get("/portal/workflows")
            workflows = result.get("workflows", [])

            if not workflows:
                return "No active durable workflows."

            lines = [f"**Active Workflows** ({result.get('total', len(workflows))})", ""]
            for wf in workflows:
                lines.append(
                    f"- {wf.get('workflow_id', '?')[:12]}.. "
                    f"| step: {wf.get('step', '?')} "
                    f"| wake: {wf.get('wake_type', '?')} "
                    f"| next: {str(wf.get('next_check_at', '?'))[:16]}"
                )
            return "\n".join(lines)
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): {e.response.text[:200]}"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: search_platform_knowledge ─────────────────────────

    @tool
    def search_platform_knowledge(query: str, limit: int = 10) -> str:
        """Search the platform's infrastructure knowledge base.

        Finds runbooks, architecture docs, service documentation, and
        operational procedures. Use this when you need context about
        how the platform is configured or how to resolve issues.

        Args:
            query: Search terms (e.g. "traefik TLS", "wordpress backup", "ghost deploy").
            limit: Max results (default 10).

        Returns:
            Matching knowledge documents with titles and paths.
        """
        try:
            result = _get("/portal/knowledge/search", params={"q": query, "limit": limit})
            docs = result.get("results", [])

            if not docs:
                return f"No knowledge documents found for: {query}"

            lines = [f'**Knowledge Search:** "{query}" ({result.get("count", len(docs))} results)', ""]
            for doc in docs:
                size_kb = round(doc.get("size_bytes", 0) / 1024, 1)
                lines.append(f"- [{doc.get('kind', '?')}] **{doc.get('title', doc.get('path', '?'))}** ({size_kb}KB)")
                lines.append(f"  path: {doc.get('path', '?')}")
            return "\n".join(lines)
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): {e.response.text[:200]}"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: prometheus_query ────────────────────────────────

    @tool
    def prometheus_query(query: str, time_range: str = "1h") -> str:
        """Run a PromQL query against the platform's Prometheus instance.

        Use this to check metrics like CPU usage, memory, request rates,
        error rates, and container health. Results come from a job submitted
        to the infra-agent, not a direct Prometheus connection.

        Args:
            query: PromQL expression (e.g. 'up', 'rate(http_requests_total[5m])').
            time_range: Lookback window (e.g. '1h', '30m', '6h'). Default '1h'.

        Returns:
            Query result with metric values and labels.
        """
        try:
            result = _post(
                "/portal/jobs",
                {
                    "kind": "prometheus.query",
                    "args": {"query": query, "time_range": time_range},
                    "requested_by": "ops-dash",
                    "sync": True,
                },
            )
            if result.get("result"):
                data = result["result"]
                return json.dumps(data, indent=2, default=str)[:2000]
            return f"Job submitted: {result.get('job_id', '?')} — status: {result.get('status', '?')}"
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): {e.response.text[:200]}"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: loki_query ─────────────────────────────────────

    @tool
    def loki_query(query: str, limit: int = 100, time_range: str = "1h") -> str:
        """Run a LogQL query against the platform's Loki instance.

        Use this to search application logs, error messages, and operational
        events. Results come from a job submitted to the infra-agent.

        Args:
            query: LogQL expression (e.g. '{container="traefik"} |= "error"').
            limit: Max log lines to return (default 100).
            time_range: Lookback window (e.g. '1h', '30m', '6h'). Default '1h'.

        Returns:
            Matching log lines with timestamps and labels.
        """
        try:
            result = _post(
                "/portal/jobs",
                {
                    "kind": "loki.query",
                    "args": {"query": query, "limit": limit, "time_range": time_range},
                    "requested_by": "ops-dash",
                    "sync": True,
                },
            )
            if result.get("result"):
                data = result["result"]
                return json.dumps(data, indent=2, default=str)[:2000]
            return f"Job submitted: {result.get('job_id', '?')} — status: {result.get('status', '?')}"
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): {e.response.text[:200]}"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: grafana_alerts ─────────────────────────────────

    @tool
    def grafana_alerts() -> str:
        """Get current Grafana alert statuses across the platform.

        Returns all active, pending, and recently resolved alerts from
        Grafana's unified alerting system. Use this to understand what
        alerting conditions are currently firing or recently cleared.

        Returns:
            Alert list with names, states, severity, and affected services.
        """
        try:
            result = _post(
                "/portal/jobs",
                {
                    "kind": "grafana.alerts",
                    "args": {},
                    "requested_by": "ops-dash",
                    "sync": True,
                },
            )
            if result.get("result"):
                alerts = result["result"]
                if isinstance(alerts, list):
                    if not alerts:
                        return "No active Grafana alerts."
                    lines = [f"**Grafana Alerts** ({len(alerts)})", ""]
                    for a in alerts[:20]:
                        state = a.get("state", "?")
                        lines.append(
                            f"- [{state}] {a.get('name', '?')} "
                            f"({a.get('severity', 'unknown')})"
                        )
                    return "\n".join(lines)
                return json.dumps(alerts, indent=2, default=str)[:2000]
            return f"Job submitted: {result.get('job_id', '?')} — status: {result.get('status', '?')}"
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): {e.response.text[:200]}"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    # ── Tool: docker_state ───────────────────────────────────

    @tool
    def docker_state(host: str = "platform-core") -> str:
        """Get Docker container and service state for a managed host.

        Returns running containers, Docker Swarm services, resource usage,
        and health status. Use this to check what's running and whether
        services are healthy.

        Args:
            host: Host name (e.g. 'platform-core', 'prod'). Default 'platform-core'.

        Returns:
            Docker state summary with services, containers, and resource usage.
        """
        try:
            result = _post(
                "/portal/jobs",
                {
                    "kind": "docker.status",
                    "args": {"host": host},
                    "requested_by": "ops-dash",
                    "sync": True,
                },
            )
            if result.get("result"):
                data = result["result"]
                if isinstance(data, dict):
                    services = data.get("services", [])
                    containers = data.get("containers", [])
                    lines = [
                        f"**Docker State — {host}**",
                        "",
                        f"Services: {len(services)} | Containers: {len(containers)}",
                        "",
                    ]
                    for svc in services[:15]:
                        lines.append(
                            f"- {svc.get('name', '?')} "
                            f"({svc.get('replicas', '?')}) "
                            f"[{svc.get('image', '?')}]"
                        )
                    return "\n".join(lines)
                return json.dumps(data, indent=2, default=str)[:2000]
            return f"Job submitted: {result.get('job_id', '?')} — status: {result.get('status', '?')}"
        except httpx.HTTPStatusError as e:
            return f"Error ({e.response.status_code}): {e.response.text[:200]}"
        except httpx.RequestError as e:
            return f"Error: Could not connect to infra-agent — {e}"

    return [
        submit_infra_job,
        get_job_status,
        list_infra_jobs,
        get_drift_balance,
        get_platform_health,
        list_workflows,
        search_platform_knowledge,
        prometheus_query,
        loki_query,
        grafana_alerts,
        docker_state,
    ]
