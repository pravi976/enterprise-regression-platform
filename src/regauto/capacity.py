"""Runner-capacity coordination for dashboard-triggered enterprise runs."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from regauto.models import ExecutionRun


class RunnerCapacityManager:
    """Coordinates waiting and running states for finite runner capacity."""

    def __init__(
        self,
        session_factory: sessionmaker,
        runner_slots: int,
        poll_seconds: float,
        timeout_seconds: int,
    ) -> None:
        self.session_factory = session_factory
        self.runner_slots = max(1, runner_slots)
        self.poll_seconds = max(0.1, poll_seconds)
        self.timeout_seconds = max(1, timeout_seconds)

    def wait_for_slot(self, run_id: int) -> bool:
        """Block until this run can claim a runner slot or the wait times out."""
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            with self.session_factory() as session:
                run = session.get(ExecutionRun, run_id)
                if run is None:
                    return False
                running_count = self._running_count(session)
                older_waiting = self._older_waiting_runs(session, run_id)
                if running_count < self.runner_slots and older_waiting == 0:
                    run.status = "running"
                    run.started_at = datetime.now(UTC)
                    session.commit()
                    return True
            time.sleep(self.poll_seconds)
        with self.session_factory() as session:
            run = session.get(ExecutionRun, run_id)
            if run is not None and run.status == "waiting":
                run.status = "timed_out"
                run.finished_at = datetime.now(UTC)
                session.commit()
        return False

    def _running_count(self, session: Session) -> int:
        return (
            session.query(func.count(ExecutionRun.id))
            .filter(ExecutionRun.status == "running")
            .scalar()
            or 0
        )

    def _older_waiting_runs(self, session: Session, run_id: int) -> int:
        return (
            session.query(func.count(ExecutionRun.id))
            .filter(ExecutionRun.status == "waiting", ExecutionRun.id < run_id)
            .scalar()
            or 0
        )
