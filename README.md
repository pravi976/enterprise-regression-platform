# Enterprise Regression Platform

Centralized Python regression automation framework for multi-repository GitHub quality gates.

## Enterprise Layer Model

The framework supports a practical enterprise regression stack:

- `level1`: Unit regression for fast local logic validation.
- `level2`: Component or API regression for each service independently.
- `level3`: Integration regression for service-to-service, database, and messaging flows.
- `level4`: End-to-end regression for full business journeys.
- `level5`: Operational regression for jobs, configs, monitoring, security, and resilience checks.

Legacy aliases are still supported:

- `gate1` maps to `level1`
- `gate2` maps to `level2`

## Quick Start

```powershell
cd C:\Users\pravi\spring-services\enterprise-regression-platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
regauto discover-tests --repo-root .\samples\sample-application-repo
regauto run-level1 --repo-root .\samples\sample-application-repo --results-dir .\results\level1
regauto run-level3 --repo-root .\samples\sample-application-repo --results-dir .\results\level3 --branch test
regauto run-level5 --repo-root .\samples\sample-application-repo --results-dir .\results\level5 --branch release
uvicorn regauto.dashboard.api:app --reload
```

## CLI Commands

Use the explicit layer commands for most automation:

```powershell
regauto run-level1 --repo-root C:\path\to\repo --branch develop
regauto run-level2 --repo-root C:\path\to\repo --branch develop
regauto run-level3 --repo-root C:\path\to\repo --branch test
regauto run-level4 --repo-root C:\path\to\repo --branch release
regauto run-level5 --repo-root C:\path\to\repo --branch release
regauto run-layer --repo-root C:\path\to\repo --gate level3 --branch test
regauto run-full --repo-root C:\path\to\repo
```

`run-gate1` and `run-gate2` remain available for backward compatibility.

## Repository Layout

Each application repository keeps its own regression assets:

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
        level1/
          TC001_customer_lookup/
            input.json
            expected_output.json
            metadata.yaml
        level3/
          TC030_customer_profile_sync/
            input.json
            expected_output.json
            metadata.yaml
      payment-service/
        level4/
          TC040_payment_refund_journey/
            input.json
            expected_output.json
            metadata.yaml
      notification-service/
        level5/
          TC050_notification_job_health/
            input.json
            expected_output.json
            metadata.yaml
```

## Minimal Configuration

`regression/config/regression.yaml`:

```yaml
repository: your-application-repo
owner: your-team
default_branch: main
services_root: regression/services
build_tool: none
gate_policies:
  level1:
    enabled: true
  level2:
    enabled: true
  level3:
    enabled: true
  level4:
    enabled: true
  level5:
    enabled: true
impact_map:
  src/customer/**:
    - customer-service
```

`regression/config/branches.yaml`:

```yaml
default_branch: main
policies:
  develop:
    environment: DEV
    gates: [level1, level2]
    include_tags: [develop]
    disabled_gates: [level3, level4, level5]
  test:
    environment: QA
    gates: [level1, level2, level3]
    include_tags: [test]
    disabled_gates: [level4, level5]
  release:
    environment: PREPROD
    gates: [level1, level2, level3, level4, level5]
    include_tags: [release]
```

## Service-Owned Python Executors

Teams can add Python executors without changing the core framework. Set `service_type: python` in
`metadata.yaml`, then add a service-owned script under `regression/executors/` or the service folder.

```yaml
service_type: python
python:
  script: regression/executors/customer_service.py
  function: execute
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

To scaffold a test quickly:

```powershell
regauto scaffold-python-test `
  --repo-root C:\path\to\application-repo `
  --service customer-service `
  --test-id TC001_customer_lookup `
  --team customer-team `
  --gate level1 `
  --branch main `
  --branch develop `
  --tag critical
```

## GitHub Actions

The framework is designed to plug into GitHub Actions directly:

- Run `level1` and `level2` on pull requests for fast feedback.
- Run `level3` nightly in test-like environments.
- Run `level4` and `level5` on release branches or before production promotion.
- Publish `summary.json`, `results.json`, and `junit.xml` as artifacts.

Ready-to-copy examples live under `examples/github-actions/`.

## Deployment Options

You can use the framework in different operating models:

- Results-only GitHub Actions workflows with no hosted dashboard.
- Standard Linux or Windows runners with Python virtual environments.
- Optional FastAPI dashboard for centralized visibility.

See:

- `docs/github-actions-results-only.md`
- `docs/testing-sample-producer-consumer.md`
- `docs/azure-vm-non-container-deployment.md`
