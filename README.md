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

Teams can also add service-owned Python executors without changing the core framework. Set
`service_type: python` in `metadata.yaml`, then add a service-named file such as
`regression/executors/customer_service.py` or
`regression/services/customer-service/customer_service.py`. The file must expose
`execute(input_payload, context)` and return the actual JSON-compatible result. The framework still
loads `input.json`, runs the Python executor, compares the returned actual result against
`expected_output.json`, and fails the gate with field-level differences when values are missing or
different.

```yaml
service_type: python
python:
  script: regression/executors/customer_service.py
  function: execute
```

To generate this skeleton automatically:

```powershell
regauto scaffold-python-test `
  --repo-root C:\path\to\application-repo `
  --service customer-service `
  --test-id TC001_customer_lookup `
  --team customer-team `
  --gate gate1 `
  --branch main `
  --branch develop `
  --tag critical
```

```python
def execute(input_payload, context):
    return {
        "body": {
            "customerId": input_payload["customerId"],
            "status": "ACTIVE",
        }
    }
```

Gates can be enabled or disabled per repository in `regression/config/regression.yaml` using
`gate_policies`, and per branch in `regression/config/branches.yaml` using `disabled_gates` or
`gate_overrides`. A disabled gate writes a skipped `summary.json` and exits with code `0`.

## Add a new application repository

To onboard another repository, add a `regression/` folder to that application repo. The central
framework does not need code changes.

```text
repo-root/
  regression/
    config/
      regression.yaml
      branches.yaml
    executors/
      customer_service.py
    services/
      customer-service/
        gate1/
          TC001_customer_lookup/
            input.json
            expected_output.json
            metadata.yaml
```

Minimum `regression/config/regression.yaml`:

```yaml
repository: your-application-repo
owner: your-team
default_branch: main
services_root: regression/services
build_tool: none
gate_policies:
  gate1:
    enabled: true
  gate2:
    enabled: true
impact_map:
  src/customer/**:
    - customer-service
```

Minimum `regression/config/branches.yaml`:

```yaml
default_branch: main
policies:
  main:
    environment: DEV
    gates: [gate1]
    include_tags: [main]
  release:
    environment: RELEASE
    gates: [gate1, gate2]
    include_tags: [release]
```

Fastest way to generate a service-owned Python test skeleton:

```powershell
regauto scaffold-python-test `
  --repo-root C:\path\to\your-application-repo `
  --service customer-service `
  --test-id TC001_customer_lookup `
  --team customer-team `
  --gate gate1 `
  --branch main `
  --branch release `
  --tag critical
```

Then copy one of the GitHub Actions examples from `examples/github-actions/` into the new repo under
`.github/workflows/`, update the framework URL to
`https://github.com/pravi976/enterprise-regression-platform.git`, and run the workflow.

## Standard VM deployment

Deploy it on standard Linux/Windows servers or CI agents using a Python virtual environment:

```powershell
python -m venv C:\regauto\venv
C:\regauto\venv\Scripts\python.exe -m pip install .
```

Linux API hosting can use `systemd`; see `examples/deployment/regauto-dashboard.service`.
Windows scheduled execution can use Task Scheduler calling
`examples/deployment/windows-scheduled-run.ps1`.

If you do not want any hosted dashboard service, use the GitHub Actions results-only model in
`docs/github-actions-results-only.md`.

For a complete local validation against `sample-producer` and `sample-consumer`, see
`docs/testing-sample-producer-consumer.md`.
