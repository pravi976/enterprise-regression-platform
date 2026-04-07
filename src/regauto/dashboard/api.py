"""FastAPI dashboard/control-plane API."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from regauto.config import Settings
from regauto.db import create_schema, get_session
from regauto.models import ExecutionRun, Repository, TestResult

settings = Settings()
app = FastAPI(title="Enterprise Regression Dashboard API", version="0.1.0")


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


@app.get("/metrics/summary", dependencies=[Depends(require_api_key)])
def management_summary(session: Session = Depends(get_session)) -> dict[str, object]:
    repo_count = session.query(func.count(Repository.id)).scalar() or 0
    run_count = session.query(func.count(ExecutionRun.id)).scalar() or 0
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
