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

## Standard VM deployment

Deploy it on standard Linux/Windows servers or CI agents using a Python virtual environment:

```powershell
python -m venv C:\regauto\venv
C:\regauto\venv\Scripts\python.exe -m pip install .
```

Linux API hosting can use `systemd`; see `examples/deployment/regauto-dashboard.service`.
Windows scheduled execution can use Task Scheduler calling
`examples/deployment/windows-scheduled-run.ps1`.

For Azure without containers, deploy it as a Python service on an Azure VM using
`docs/azure-vm-non-container-deployment.md`.

For a complete local validation against `sample-producer` and `sample-consumer`, see
`docs/testing-sample-producer-consumer.md`.
