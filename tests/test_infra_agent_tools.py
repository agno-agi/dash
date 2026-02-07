"""Tests for the infra-agent tool bridge (Phase 5.2).

These tests mock httpx.get/post to verify that the Agno @tool functions
correctly call the infra-agent portal API and format responses for LLM
consumption. No real infra-agent server is needed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Import infra_agent module directly to avoid dash/__init__.py which
# eagerly imports agents that connect to Postgres at module level.
_module_path = Path(__file__).resolve().parent.parent / "dash" / "tools" / "infra_agent.py"
_spec = importlib.util.spec_from_file_location("dash.tools.infra_agent", _module_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["dash.tools.infra_agent"] = _mod
_spec.loader.exec_module(_mod)
create_infra_agent_tools = _mod.create_infra_agent_tools


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_URL = "http://infra-agent:8042"
SECRET = "test-portal-secret"


@pytest.fixture
def tools():
    """Create the tool set with test credentials."""
    return create_infra_agent_tools(BASE_URL, SECRET)


@pytest.fixture
def tool_map(tools):
    """Map tool entrypoint functions by name for easy lookup.

    Agno's @tool decorator wraps functions into pydantic Function objects.
    We use `.name` for the key and `.entrypoint` for the callable.
    """
    return {fn.name: fn.entrypoint for fn in tools}


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = json.dumps(json_data)
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        error = httpx.HTTPStatusError(f"{status_code} error", request=MagicMock(), response=resp)
        resp.raise_for_status.side_effect = error
    return resp


# ---------------------------------------------------------------------------
# Test: create_infra_agent_tools returns correct number of tools
# ---------------------------------------------------------------------------


class TestToolCreation:
    def test_returns_list_of_tools(self, tools):
        assert isinstance(tools, list)
        assert len(tools) == 11

    def test_tool_names(self, tool_map):
        expected = {
            "submit_infra_job",
            "get_job_status",
            "list_infra_jobs",
            "get_drift_balance",
            "get_platform_health",
            "list_workflows",
            "search_platform_knowledge",
            "prometheus_query",
            "loki_query",
            "grafana_alerts",
            "docker_state",
        }
        assert set(tool_map.keys()) == expected

    def test_empty_secret_returns_empty_list(self):
        """When secret is empty, the factory should still create tools.
        The agent module guards this — factory always returns tools."""
        tools = create_infra_agent_tools(BASE_URL, "")
        assert len(tools) == 11


# ---------------------------------------------------------------------------
# Test: submit_infra_job
# ---------------------------------------------------------------------------


class TestSubmitInfraJob:
    @patch("httpx.post")
    def test_submit_success(self, mock_post, tool_map):
        mock_post.return_value = _mock_response(
            {
                "job_id": "job-123",
                "status": "queued",
                "approval_required": False,
                "message": "Job dokploy.redeploy queued",
            }
        )

        result = tool_map["submit_infra_job"](
            kind="dokploy.redeploy",
            args='{"project": "ghost-blog", "host": "prod"}',
        )

        assert "job-123" in result
        assert "queued" in result
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "/portal/jobs" in call_args[0][0]
        assert call_args[1]["headers"]["X-Portal-Secret"] == SECRET

    @patch("httpx.post")
    def test_submit_with_approval(self, mock_post, tool_map):
        mock_post.return_value = _mock_response(
            {
                "job_id": "job-456",
                "status": "waiting_approval",
                "approval_required": True,
                "approval_id": "apr-789",
                "message": "Needs approval",
            }
        )

        result = tool_map["submit_infra_job"](kind="platform_updates_apply")
        assert "Approval Required: True" in result
        assert "apr-789" in result

    @patch("httpx.post")
    def test_submit_invalid_kind(self, mock_post, tool_map):
        resp = _mock_response({"detail": "Unknown job kind: 'bogus'"}, 400)
        mock_post.return_value = resp

        result = tool_map["submit_infra_job"](kind="bogus")
        assert "Error (400)" in result
        assert "Unknown job kind" in result

    def test_submit_invalid_json_args(self, tool_map):
        result = tool_map["submit_infra_job"](kind="test", args="not-json{")
        assert "Error: Invalid JSON" in result

    @patch("httpx.post")
    def test_submit_connection_error(self, mock_post, tool_map):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        result = tool_map["submit_infra_job"](kind="test")
        assert "Could not connect" in result


# ---------------------------------------------------------------------------
# Test: get_job_status
# ---------------------------------------------------------------------------


class TestGetJobStatus:
    @patch("httpx.get")
    def test_success(self, mock_get, tool_map):
        mock_get.return_value = _mock_response(
            {
                "job_id": "job-123",
                "status": "succeeded",
                "summary": "Deployed ghost-blog",
                "result": {"deploy_time": 42},
                "artifact_paths": ["artifacts/deploy_2025.json"],
            }
        )

        result = tool_map["get_job_status"](job_id="job-123")
        assert "succeeded" in result
        assert "Deployed ghost-blog" in result
        assert "deploy_time" in result
        assert "artifacts/deploy_2025.json" in result

    @patch("httpx.get")
    def test_not_found(self, mock_get, tool_map):
        mock_get.return_value = _mock_response({"detail": "Job not found"}, 404)
        result = tool_map["get_job_status"](job_id="nonexistent")
        assert "Error (404)" in result


# ---------------------------------------------------------------------------
# Test: list_infra_jobs
# ---------------------------------------------------------------------------


class TestListInfraJobs:
    @patch("httpx.get")
    def test_list_all(self, mock_get, tool_map):
        mock_get.return_value = _mock_response(
            {
                "jobs": [
                    {
                        "job_id": "job-1",
                        "kind": "dokploy.redeploy",
                        "status": "succeeded",
                        "source": "portal",
                        "summary": "Deployed ghost",
                        "created_at": "2025-01-15T10:00:00",
                        "requested_by": "admin",
                    },
                    {
                        "job_id": "job-2",
                        "kind": "ops_warehouse_etl",
                        "status": "running",
                        "source": "scheduler",
                        "summary": "ETL run",
                        "created_at": "2025-01-15T11:00:00",
                        "requested_by": "scheduler",
                    },
                ],
                "count": 2,
            }
        )

        result = tool_map["list_infra_jobs"]()
        assert "2 results" in result
        assert "dokploy.redeploy" in result
        assert "ops_warehouse_etl" in result

    @patch("httpx.get")
    def test_list_filtered(self, mock_get, tool_map):
        mock_get.return_value = _mock_response({"jobs": [], "count": 0})
        result = tool_map["list_infra_jobs"](status="failed", kind="dokploy.redeploy")
        assert "No jobs found" in result

        call_args = mock_get.call_args
        assert call_args[1]["params"]["status"] == "failed"
        assert call_args[1]["params"]["kind"] == "dokploy.redeploy"

    @patch("httpx.get")
    def test_list_empty(self, mock_get, tool_map):
        mock_get.return_value = _mock_response({"jobs": [], "count": 0})
        result = tool_map["list_infra_jobs"]()
        assert "No jobs found" in result


# ---------------------------------------------------------------------------
# Test: get_drift_balance
# ---------------------------------------------------------------------------


class TestGetDriftBalance:
    @patch("httpx.get")
    def test_with_drift(self, mock_get, tool_map):
        mock_get.return_value = _mock_response(
            {
                "drift_items": [
                    {
                        "service_name": "traefik",
                        "severity": "high",
                        "environment": "platform-core",
                        "category": "version_drift",
                        "debt_score": 25.0,
                    },
                    {
                        "service_name": "ghost-blog",
                        "severity": "medium",
                        "environment": "prod",
                        "category": "config_drift",
                        "debt_score": 5.0,
                    },
                ],
                "drift_debt_total": 30.0,
                "health_score": {"score": 68.0, "deductions": {"drift_debt": 30.0, "update_backlog": 2.0}},
                "etl_timestamp": "2025-01-15T10:00:00Z",
            }
        )

        result = tool_map["get_drift_balance"]()
        assert "68.0/100" in result
        assert "30.0" in result
        assert "traefik" in result
        assert "ghost-blog" in result

    @patch("httpx.get")
    def test_no_drift(self, mock_get, tool_map):
        mock_get.return_value = _mock_response(
            {
                "drift_items": [],
                "drift_debt_total": 0,
                "health_score": {"score": 100, "deductions": {}},
            }
        )

        result = tool_map["get_drift_balance"]()
        assert "100/100" in result
        assert "full compliance" in result


# ---------------------------------------------------------------------------
# Test: get_platform_health
# ---------------------------------------------------------------------------


class TestGetPlatformHealth:
    @patch("httpx.get")
    def test_health_overview(self, mock_get, tool_map):
        # get_platform_health makes two GET calls: warehouse/status and warehouse/drift-balance
        mock_get.side_effect = [
            _mock_response(
                {
                    "actual_services": 12,
                    "desired_services": 14,
                    "drift_observations": 3,
                    "update_status": 5,
                    "last_etl": {
                        "job_id": "etl-1",
                        "status": "succeeded",
                        "timestamp": "2025-01-15T10:00:00Z",
                        "summary": "ETL complete: 12 services, 3 drift",
                    },
                }
            ),
            _mock_response(
                {
                    "drift_debt_total": 15.0,
                    "health_score": {"score": 83.0, "deductions": {"drift_debt": 15.0}},
                }
            ),
        ]

        result = tool_map["get_platform_health"]()
        assert "83.0/100" in result
        assert "Actual Services: 12" in result
        assert "Desired Services: 14" in result
        assert "ETL complete" in result


# ---------------------------------------------------------------------------
# Test: list_workflows
# ---------------------------------------------------------------------------


class TestListWorkflows:
    @patch("httpx.get")
    def test_active_workflows(self, mock_get, tool_map):
        mock_get.return_value = _mock_response(
            {
                "workflows": [
                    {
                        "workflow_id": "wf-deploy-ghost",
                        "step": "health_check",
                        "wake_type": "CONDITION",
                        "next_check_at": "2025-01-15T10:05:00Z",
                    },
                ],
                "total": 1,
            }
        )

        result = tool_map["list_workflows"]()
        assert "1" in result
        assert "wf-deploy-gh" in result
        assert "CONDITION" in result

    @patch("httpx.get")
    def test_no_workflows(self, mock_get, tool_map):
        mock_get.return_value = _mock_response({"workflows": [], "total": 0})
        result = tool_map["list_workflows"]()
        assert "No active" in result


# ---------------------------------------------------------------------------
# Test: search_platform_knowledge
# ---------------------------------------------------------------------------


class TestSearchPlatformKnowledge:
    @patch("httpx.get")
    def test_search_results(self, mock_get, tool_map):
        mock_get.return_value = _mock_response(
            {
                "results": [
                    {
                        "path": "docs/services/ghost.md",
                        "kind": "service",
                        "title": "Ghost Blog Service",
                        "size_bytes": 2048,
                    },
                    {
                        "path": "docs/runbooks/ghost-down.md",
                        "kind": "runbook",
                        "title": "Ghost Down Troubleshooting",
                        "size_bytes": 1024,
                    },
                ],
                "count": 2,
            }
        )

        result = tool_map["search_platform_knowledge"](query="ghost deploy")
        assert "Ghost Blog Service" in result
        assert "ghost-down.md" in result
        assert "2 results" in result

        call_args = mock_get.call_args
        assert call_args[1]["params"]["q"] == "ghost deploy"

    @patch("httpx.get")
    def test_search_no_results(self, mock_get, tool_map):
        mock_get.return_value = _mock_response({"results": [], "count": 0})
        result = tool_map["search_platform_knowledge"](query="nonexistent-thing")
        assert "No knowledge documents found" in result


# ---------------------------------------------------------------------------
# Test: Authentication headers
# ---------------------------------------------------------------------------


class TestAuthHeaders:
    @patch("httpx.get")
    def test_secret_in_headers(self, mock_get, tool_map):
        mock_get.return_value = _mock_response({"workflows": [], "total": 0})
        tool_map["list_workflows"]()

        call_args = mock_get.call_args
        assert call_args[1]["headers"]["X-Portal-Secret"] == SECRET

    @patch("httpx.post")
    def test_post_secret_in_headers(self, mock_post, tool_map):
        mock_post.return_value = _mock_response(
            {
                "job_id": "j-1",
                "status": "queued",
                "approval_required": False,
            }
        )
        tool_map["submit_infra_job"](kind="test")

        call_args = mock_post.call_args
        assert call_args[1]["headers"]["X-Portal-Secret"] == SECRET
        assert call_args[1]["headers"]["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# Test: URL construction
# ---------------------------------------------------------------------------


class TestUrlConstruction:
    def test_trailing_slash_stripped(self):
        """Factory should strip trailing slash from base_url."""
        tools = create_infra_agent_tools("http://agent:8042/", "secret")
        tool_map = {fn.name: fn.entrypoint for fn in tools}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _mock_response({"workflows": [], "total": 0})
            tool_map["list_workflows"]()

            url = mock_get.call_args[0][0]
            assert url == "http://agent:8042/portal/workflows"
            assert "//" not in url.replace("http://", "")
