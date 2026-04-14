"""FastAPI dashboard/control-plane API."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from regauto.build import BuildOrchestrator
from regauto.capacity import RunnerCapacityManager
from regauto.config import Settings, VALID_LAYERS, canonical_gate_name, load_repository_config, resolve_branch_policy, resolve_gate_decision
from regauto.db import SessionLocal, create_schema, get_session
from regauto.discovery import TestDiscovery
from regauto.execution import ExecutionEngine
from regauto.models import ExecutionRun, Repository, TestResult
from regauto.persistence import create_run, finalize_run, update_run_status, upsert_repository
from regauto.reporting import ReportWriter, should_fail_gate, summarize
from regauto.source_control import CheckoutRequest, GitRepositoryManager

settings = Settings()
app = FastAPI(title="Enterprise Regression Dashboard API", version="0.1.0")


class RunGateRequest(BaseModel):
    """Request to run a regression layer from the dashboard UI."""

    repo_root: Path = Field(description="Application repository root on this server or runner")
    branch: str | None = Field(default="main", description="Branch policy to apply")
    results_dir: Path | None = Field(default=None, description="Optional output directory")
    trigger: str = "ui"


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Simple API-key guard for enterprise gateway integration."""
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@app.on_event("startup")
def startup() -> None:
    """Create schema in starter deployments. Use Alembic in mature deployments."""
    create_schema()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background: BackgroundTasks,
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, object]:
    body = await request.body()
    if settings.github_webhook_secret:
        if not _verify_github_signature(settings.github_webhook_secret, body, x_hub_signature_256):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")
    event = (x_github_event or "").strip().lower()
    if event and event != "push":
        return {"accepted": False, "reason": f"unsupported_event:{event}"}
    payload = json.loads(body.decode("utf-8") or "{}")
    background.add_task(_handle_github_push, payload)
    return {"accepted": True}


@app.get("/ui", response_class=HTMLResponse)
def dashboard_ui() -> str:
    """Minimal management UI for running gates and viewing latest results."""
    return _DASHBOARD_HTML


@app.get("/repositories", dependencies=[Depends(require_api_key)])
def repositories(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    rows = session.query(Repository).order_by(Repository.name).all()
    return [{"name": row.name, "url": row.url, "owner": row.owner, "default_branch": row.default_branch} for row in rows]


@app.get("/executions/latest", dependencies=[Depends(require_api_key)])
def latest_executions(limit: int = 20, session: Session = Depends(get_session)) -> list[dict[str, object]]:
    rows = session.query(ExecutionRun).order_by(desc(ExecutionRun.started_at)).limit(limit).all()
    return [
        {
            "id": row.id,
            "repository": row.repository,
            "gate": row.gate,
            "trigger": row.trigger,
            "status": row.status,
            "pass_rate": row.pass_rate,
            "total": row.total,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        }
        for row in rows
    ]


@app.get("/executions/{run_id}/results", dependencies=[Depends(require_api_key)])
def execution_results(run_id: int, session: Session = Depends(get_session)) -> dict[str, object]:
    run = session.get(ExecutionRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    results = (
        session.query(TestResult)
        .filter(TestResult.run_id == run_id)
        .order_by(TestResult.service, TestResult.test_id)
        .all()
    )
    return {
        "run": {
            "id": run.id,
            "repository": run.repository,
            "gate": run.gate,
            "trigger": run.trigger,
            "branch": run.branch,
            "commit_sha": run.commit_sha,
            "status": run.status,
            "pass_rate": run.pass_rate,
            "total": run.total,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        },
        "results": [
            {
                "test_id": result.test_id,
                "service": result.service,
                "team": result.team,
                "gate": result.gate,
                "status": result.status,
                "service_type": result.service_type,
                "failure_type": result.failure_type,
                "duration_ms": result.duration_ms,
                "error": result.error,
                "differences": json.loads(result.differences_json or "[]"),
            }
            for result in results
        ],
    }


@app.post("/run/level1", dependencies=[Depends(require_api_key)])
def run_level1(request: RunGateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    return _run_gate("level1", request, session)


@app.post("/run/level2", dependencies=[Depends(require_api_key)])
def run_level2(request: RunGateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    return _run_gate("level2", request, session)


@app.post("/run/level3", dependencies=[Depends(require_api_key)])
def run_level3(request: RunGateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    return _run_gate("level3", request, session)


@app.post("/run/level4", dependencies=[Depends(require_api_key)])
def run_level4(request: RunGateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    return _run_gate("level4", request, session)


@app.post("/run/level5", dependencies=[Depends(require_api_key)])
def run_level5(request: RunGateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    return _run_gate("level5", request, session)


@app.post("/run/gate1", dependencies=[Depends(require_api_key)])
def run_gate1(request: RunGateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    return _run_gate("gate1", request, session)


@app.post("/run/gate2", dependencies=[Depends(require_api_key)])
def run_gate2(request: RunGateRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    return _run_gate("gate2", request, session)


@app.get("/metrics/summary", dependencies=[Depends(require_api_key)])
def management_summary(session: Session = Depends(get_session)) -> dict[str, object]:
    repo_count = session.query(func.count(Repository.id)).scalar() or 0
    run_count = session.query(func.count(ExecutionRun.id)).scalar() or 0
    waiting_runs = session.query(func.count(ExecutionRun.id)).filter(ExecutionRun.status == "waiting").scalar() or 0
    running_runs = session.query(func.count(ExecutionRun.id)).filter(ExecutionRun.status == "running").scalar() or 0
    latest = session.query(ExecutionRun).order_by(desc(ExecutionRun.started_at)).first()
    gate_rates = session.query(ExecutionRun.gate, func.avg(ExecutionRun.pass_rate)).group_by(ExecutionRun.gate).all()
    failing_services = (
        session.query(TestResult.service, func.count(TestResult.id).label("failures"))
        .filter(TestResult.status.in_(["failed", "error"]))
        .group_by(TestResult.service)
        .order_by(desc("failures"))
        .limit(10)
        .all()
    )
    service_type_rates = (
        session.query(TestResult.service_type, TestResult.status, func.count(TestResult.id))
        .group_by(TestResult.service_type, TestResult.status)
        .all()
    )
    failure_breakdown = (
        session.query(TestResult.failure_type, func.count(TestResult.id))
        .filter(TestResult.failure_type.is_not(None))
        .group_by(TestResult.failure_type)
        .all()
    )
    return {
        "repositories_onboarded": repo_count,
        "execution_runs": run_count,
        "runner_slots": settings.runner_slots,
        "running_runs": running_runs,
        "waiting_runs": waiting_runs,
        "gate_pass_rates": {gate: round(rate or 0, 2) for gate, rate in gate_rates},
        "top_failing_microservices": [{"service": service, "failures": count} for service, count in failing_services],
        "rest_vs_jms_health": [
            {"service_type": service_type or "unknown", "status": status, "count": count}
            for service_type, status, count in service_type_rates
        ],
        "build_vs_test_failure_breakdown": [
            {"failure_type": failure_type or "unknown", "count": count}
            for failure_type, count in failure_breakdown
        ],
        "last_execution_summary": None
        if latest is None
        else {
            "repository": latest.repository,
            "gate": latest.gate,
            "status": latest.status,
            "pass_rate": latest.pass_rate,
            "total": latest.total,
        },
    }


def _run_gate(gate: str, request: RunGateRequest, session: Session) -> dict[str, object]:
    repo_root = request.repo_root.resolve()
    gate = canonical_gate_name(gate) or gate
    if not repo_root.exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Repository root not found: {repo_root}")
    repo_config = load_repository_config(repo_root)
    upsert_repository(session, repo_config.repository, repo_config.remote_url, repo_config.owner)
    run = create_run(
        session,
        repository=repo_config.repository,
        gate=gate,
        trigger=request.trigger,
        branch=request.branch,
        status="waiting",
    )
    capacity = RunnerCapacityManager(
        session_factory=SessionLocal,
        runner_slots=settings.runner_slots,
        poll_seconds=settings.queue_poll_seconds,
        timeout_seconds=settings.queue_timeout_seconds,
    )
    if not capacity.wait_for_slot(run.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Run {run.id} timed out while waiting for a runner slot",
        )
    try:
        gate_decision = resolve_gate_decision(repo_root, gate, request.branch)
        if not gate_decision.enabled:
            update_run_status(session, run.id, "skipped")
            return {
                "status": "skipped",
                "run_id": run.id,
                "gate": gate,
                "branch": request.branch,
                "reason": gate_decision.reason or "Gate disabled by policy",
            }
        tests = TestDiscovery().discover(repo_root=repo_root, gate=gate, branch=request.branch)
        if not tests:
            update_run_status(session, run.id, "failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No tests discovered for {gate} on branch {request.branch}",
            )
        results = ExecutionEngine().run(tests)
        output_dir = request.results_dir or repo_root / "regression-results" / gate
        ReportWriter().write(results, output_dir)
        run = finalize_run(session, run.id, results)
        summary = summarize(results)
        return {
            "run_id": run.id,
            "status": "failed" if should_fail_gate(results) else "passed",
            "summary": summary,
            "results_dir": str(output_dir),
        }
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        update_run_status(session, run.id, "failed")
        raise


def _verify_github_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def _handle_github_push(payload: dict[str, object]) -> None:
    ref = str(payload.get("ref") or "")
    if not ref.startswith("refs/heads/"):
        return
    branch = ref.removeprefix("refs/heads/")
    repository = payload.get("repository") or {}
    if not isinstance(repository, dict):
        return
    remote_url = repository.get("clone_url")
    repo_name = repository.get("name")
    if not remote_url or not repo_name:
        return
    remote_url_value = _apply_git_token(str(remote_url))
    commit_sha = str(payload.get("after") or "") or None
    owner = repository.get("owner", {}).get("name") or repository.get("owner", {}).get("login")

    for gate in VALID_LAYERS:
        _checkout_build_run_gate(
            remote_url=remote_url_value,
            directory_name=str(repo_name),
            branch=branch,
            gate=gate,
            commit_sha=commit_sha,
            owner=str(owner) if owner else None,
            repo_name=str(repo_name),
        )


def _set_github_commit_status(
    owner: str | None,
    repo_name: str | None,
    commit_sha: str | None,
    gate: str,
    state: str,
    description: str,
) -> None:
    if not settings.github_token or not owner or not repo_name or not commit_sha:
        return
    url = f"https://api.github.com/repos/{owner}/{repo_name}/statuses/{commit_sha}"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "state": state,
        "description": description[:140],
        "context": f"regression/{gate}",
    }
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        response.raise_for_status()
    except Exception as exc:
        logging.warning(f"Failed to post GitHub status for {commit_sha}: {exc}")


def _checkout_build_run_gate(
    remote_url: str,
    directory_name: str,
    branch: str,
    gate: str,
    commit_sha: str | None,
    owner: str | None = None,
    repo_name: str | None = None,
) -> None:
    _set_github_commit_status(owner, repo_name, commit_sha, gate, "pending", f"Waiting for runner slot for {gate}")
    with SessionLocal() as session:
        run = create_run(
            session,
            repository=directory_name,
            gate=gate,
            trigger="github-webhook",
            commit_sha=commit_sha,
            branch=branch,
            status="waiting",
        )
        capacity = RunnerCapacityManager(
            session_factory=SessionLocal,
            runner_slots=settings.runner_slots,
            poll_seconds=settings.queue_poll_seconds,
            timeout_seconds=settings.queue_timeout_seconds,
        )
        if not capacity.wait_for_slot(run.id):
            update_run_status(session, run.id, "timed_out")
            _set_github_commit_status(owner, repo_name, commit_sha, gate, "error", "Timed out waiting for runner slot")
            return
        try:
            _set_github_commit_status(owner, repo_name, commit_sha, gate, "pending", f"Running {gate} regression")
            checkout = GitRepositoryManager().checkout(
                CheckoutRequest(
                    remote_url=remote_url,
                    branch=branch,
                    workspace_root=Path(settings.webhook_workspace_root),
                    directory_name=directory_name,
                    clean=settings.webhook_clean_workspace,
                )
            )
            repo_root = checkout.repo_root
            repo_config = load_repository_config(repo_root)
            upsert_repository(session, repo_config.repository, remote_url, repo_config.owner)
            run_record = session.get(ExecutionRun, run.id)
            if run_record is not None:
                run_record.repository = repo_config.repository
                run_record.commit_sha = checkout.commit_sha
                session.commit()
            gate_decision = resolve_gate_decision(repo_root, gate, branch)
            if not gate_decision.enabled:
                update_run_status(session, run.id, "skipped")
                _set_github_commit_status(owner, repo_name, commit_sha, gate, "success", f"Skipped: {gate_decision.reason or 'disabled'}")
                return
            policy = resolve_branch_policy(repo_root, branch)
            orchestrator = BuildOrchestrator()
            orchestrator.run(repo_root, repo_config, policy)
            orchestrator.run_pre_test(repo_root, repo_config, policy)
            try:
                tests = TestDiscovery().discover(repo_root=repo_root, gate=gate, branch=branch)
                results = ExecutionEngine().run(tests)
                results_dir = (
                    Path(settings.webhook_results_root)
                    / repo_config.repository
                    / branch
                    / checkout.commit_sha
                    / gate
                )
                ReportWriter().write(results, results_dir)
                if settings.webhook_publish:
                    finalize_run(session, run.id, results)
                else:
                    update_run_status(session, run.id, "failed" if should_fail_gate(results) else "passed")
                if should_fail_gate(results):
                    _set_github_commit_status(owner, repo_name, commit_sha, gate, "failure", f"{gate} regression failed")
                else:
                    _set_github_commit_status(owner, repo_name, commit_sha, gate, "success", f"{gate} regression passed")
            finally:
                orchestrator.run_post_test(repo_root, repo_config, policy)
        except Exception as exc:  # noqa: BLE001
            update_run_status(session, run.id, "failed")
            _set_github_commit_status(owner, repo_name, commit_sha, gate, "error", f"Internal error running {gate}: {exc}")
            raise


def _apply_git_token(remote_url: str) -> str:
    token = settings.github_token
    if not token:
        return remote_url
    parsed = urlparse(remote_url)
    if parsed.scheme not in {"http", "https"}:
        return remote_url
    if "@" in parsed.netloc:
        return remote_url
    return urlunparse(parsed._replace(netloc=f"x-access-token:{token}@{parsed.netloc}"))


_DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Enterprise Regression Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #f7f8fb; color: #172033; }
    h1 { margin-bottom: 4px; }
    .panel { background: white; border: 1px solid #dde3ee; border-radius: 10px; padding: 16px; margin: 16px 0; box-shadow: 0 1px 2px #0001; }
    label { display: block; font-weight: 600; margin-top: 10px; }
    input { width: 100%; max-width: 820px; padding: 8px; border: 1px solid #b8c2d6; border-radius: 6px; }
    button { margin: 12px 8px 0 0; padding: 9px 14px; border: 0; border-radius: 6px; background: #155eef; color: white; font-weight: 700; cursor: pointer; }
    button.secondary { background: #52637a; }
    table { border-collapse: collapse; width: 100%; margin-top: 12px; background: white; }
    th, td { border: 1px solid #dde3ee; padding: 8px; text-align: left; vertical-align: top; }
    th { background: #edf2fb; }
    .passed { color: #047857; font-weight: 700; }
    .failed, .error { color: #b42318; font-weight: 700; }
    .muted { color: #5d6b82; }
    pre { white-space: pre-wrap; background: #111827; color: #e5e7eb; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>Enterprise Regression Dashboard</h1>
  <div class="muted">Run Level 1 through Level 5 regression layers and inspect latest pass/fail summaries with field-level diffs.</div>

  <section class="panel">
    <label>Repository root on this runner/server</label>
    <input id="repoRoot" placeholder="C:\\Users\\pravi\\spring-services\\sample-inventory" />
    <label>Branch policy</label>
    <input id="branch" value="main" />
    <label>API key, only if REGAUTO_API_KEY is configured</label>
    <input id="apiKey" type="password" placeholder="optional" />
    <button onclick="runGate('level1')">Run Level 1</button>
    <button onclick="runGate('level2')">Run Level 2</button>
    <button onclick="runGate('level3')">Run Level 3</button>
    <button onclick="runGate('level4')">Run Level 4</button>
    <button onclick="runGate('level5')">Run Level 5</button>
    <button class="secondary" onclick="loadLatest()">View Latest Results</button>
  </section>

  <section class="panel">
    <h2>Run Summary</h2>
    <div id="summary">No run loaded yet.</div>
  </section>

  <section class="panel">
    <h2>Test Results</h2>
    <div id="results"></div>
  </section>

  <section class="panel">
    <h2>Field-Level Differences</h2>
    <div id="diffs"></div>
  </section>

  <section class="panel">
    <h2>Raw Response</h2>
    <pre id="raw"></pre>
  </section>

  <script>
    function headers() {
      const apiKey = document.getElementById("apiKey").value;
      const value = {"Content-Type": "application/json"};
      if (apiKey) value["x-api-key"] = apiKey;
      return value;
    }

    async function runGate(gate) {
      const payload = {
        repo_root: document.getElementById("repoRoot").value,
        branch: document.getElementById("branch").value || "main",
        trigger: "ui"
      };
      setRaw(`Running ${gate}...`);
      const response = await fetch(`/run/${gate}`, {method: "POST", headers: headers(), body: JSON.stringify(payload)});
      const data = await response.json();
      setRaw(JSON.stringify(data, null, 2));
      if (!response.ok) return;
      if (data.run_id) await loadRun(data.run_id);
      else renderSummary(data);
    }

    async function loadLatest() {
      const response = await fetch("/executions/latest?limit=1", {headers: headers()});
      const data = await response.json();
      setRaw(JSON.stringify(data, null, 2));
      if (Array.isArray(data) && data.length) await loadRun(data[0].id);
      if (Array.isArray(data) && data.length === 0) document.getElementById("summary").innerText = "No runs found.";
    }

    async function loadRun(id) {
      const response = await fetch(`/executions/${id}/results`, {headers: headers()});
      const data = await response.json();
      setRaw(JSON.stringify(data, null, 2));
      renderRun(data);
    }

    function renderRun(data) {
      renderSummary(data.run);
      const rows = data.results.map(r => `<tr><td class="${r.status}">${r.status.toUpperCase()}</td><td>${r.gate}</td><td>${r.service}</td><td>${r.service_type || ""}</td><td>${r.test_id}</td><td>${r.duration_ms}</td><td>${r.error || ""}</td></tr>`).join("");
      document.getElementById("results").innerHTML = `<table><tr><th>Status</th><th>Gate</th><th>Service</th><th>Type</th><th>Test</th><th>Duration ms</th><th>Error</th></tr>${rows}</table>`;
      const diffRows = [];
      data.results.forEach(r => (r.differences || []).forEach(d => diffRows.push(`<tr><td>${r.test_id}</td><td>${d.path}</td><td><code>${escapeHtml(JSON.stringify(d.expected))}</code></td><td><code>${escapeHtml(JSON.stringify(d.actual))}</code></td><td>${d.message}</td></tr>`)));
      document.getElementById("diffs").innerHTML = diffRows.length ? `<table><tr><th>Test</th><th>JSON Path</th><th>Expected</th><th>Actual</th><th>Message</th></tr>${diffRows.join("")}</table>` : "No field-level differences.";
    }

    function renderSummary(summary) {
      document.getElementById("summary").innerHTML = `<table><tr><th>Status</th><th>Repository</th><th>Gate</th><th>Branch</th><th>Total</th><th>Pass Rate</th></tr><tr><td class="${summary.status || ""}">${summary.status || ""}</td><td>${summary.repository || ""}</td><td>${summary.gate || ""}</td><td>${summary.branch || ""}</td><td>${summary.total ?? ""}</td><td>${summary.pass_rate ?? ""}</td></tr></table>`;
    }

    function setRaw(value) { document.getElementById("raw").innerText = value; }
    function escapeHtml(value) { return String(value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch])); }
  </script>
</body>
</html>
"""
