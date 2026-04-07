# Enterprise Regression Platform

Centralized Python regression automation framework for multi-repository GitHub quality gates.

## Quick start

```powershell
cd C:\Users\pravi\spring-services\enterprise-regression-platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
regauto discover-tests --repo-root .\samples\sample-application-repo
regauto run-gate1 --repo-root .\samples\sample-application-repo --results-dir .\results
regauto run-gate2 --repo-root .\samples\sample-application-repo --results-dir .\results
uvicorn regauto.dashboard.api:app --reload
```

The sample tests use the built-in `echo` executor and a file-backed JMS provider. For real REST
services, set `service_type: rest` and provide endpoint details. For JMS, set `service_type: jms`
and register an enterprise broker provider.

Gates can be enabled or disabled per repository in `regression/config/regression.yaml` using
`gate_policies`, and per branch in `regression/config/branches.yaml` using `disabled_gates` or
`gate_overrides`. A disabled gate writes a skipped `summary.json` and exits with code `0`.

## Standard VM deployment

Deploy it on standard Linux/Windows servers or CI agents using a Python virtual environment:

```powershell
python -m venv C:\regauto\venv
C:\regauto\venv\Scripts\python.exe -m pip install .
```

Linux API hosting can use `systemd`; see `examples/deployment/regauto-dashboard.service`.
Windows scheduled execution can use Task Scheduler calling
`examples/deployment/windows-scheduled-run.ps1`.

For a complete local validation against `sample-producer` and `sample-consumer`, see
`docs/testing-sample-producer-consumer.md`.
