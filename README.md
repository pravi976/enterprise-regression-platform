# Enterprise Regression Platform Setup

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

## End-to-End Setup Guide (Do Not Skip)

This section documents:

- Where regression assets live and how test discovery works.
- Which configuration files are required and how they interact.
- How to run locally.
- How to run fully inside GitHub Actions (recommended when you want everything “in GitHub only”).
- How to run in a centralized webhook-driven mode (optional) and publish pass/fail back to GitHub.
- Where to find results and field-level JSON comparisons.

### Key Concepts

- **Gates / Layers**
  - `level1`..`level5` are the supported regression layers.
  - `gate1` is an alias for `level1`, and `gate2` is an alias for `level2`.
- **Repository-owned regression assets**
  - Every application repository owns its own regression tests and executors under `repo-root/regression/`.
- **Branch policy**
  - Which gates run, which tags are included/excluded, and optional build/startup hooks are defined per branch policy in `regression/config/branches.yaml`.
- **Test discovery**
  - Tests are discovered from `regression/services/<service>/<gate>/<testcase>/`.
  - A folder is considered a test case only when it contains:
    - `input.json`
    - `expected_output.json`
    - optional `metadata.yaml`
- **Comparisons**
  - Each test execution returns an “actual” payload that is compared against `expected_output.json`.
  - Field-by-field JSON differences are captured and reported.

### Repository Layout (Required)

```text
repo-root/
  regression/
    config/
      regression.yaml
      branches.yaml
    executors/
      some_service.py
    services/
      some-service/
        level1/
          TC001_example/
            input.json
            expected_output.json
            metadata.yaml
```

### Centralized Suite Layout (Optional, Platform-Owned Tests)

If you do not want to keep `regression/` inside every application repository, you can centralize
all regression assets inside `enterprise-regression-platform` and point runs to them using
`--assets-root`.

Recommended structure in `enterprise-regression-platform`:

```text
enterprise-regression-platform/
  suites/
    regression-test-producer/
      regression/
        config/
          regression.yaml
          branches.yaml
        executors/
          upstream_customer_service.py
        services/
          upstream-customer-service/
            level1/
              TC001_customer_lookup/
                input.json
                expected_output.json
                metadata.yaml
            level2/
              TC010_city_search/
                input.json
                expected_output.json
                metadata.yaml
    regression-test-consumer/
      regression/
        config/
          regression.yaml
          branches.yaml
        executors/
          downstream_customer_journey.py
        services/
          downstream-customer-journey/
            level3/...
            level4/...
            level5/...
```

How it works:

- The application repository can be “code-only” (no `regression/` folder required).
- The platform still checks out/builds the application repo, but it discovers tests/config from `--assets-root`.
- Discovery, branch policy, tags, and `metadata.yaml` filtering still apply the same way.

CLI usage example:

```bash
regauto checkout-build-run \
  --remote-url "https://github.com/<owner>/regression-test-producer.git" \
  --branch "main" \
  --gate "level1" \
  --workspace-root "/tmp/regression-workspaces" \
  --directory-name "regression-test-producer" \
  --assets-root "/path/to/enterprise-regression-platform/suites/regression-test-producer" \
  --results-dir "/tmp/regression-results/level1" \
  --trigger github-actions
```

### Configuration Files (Required)

#### 1) regression/config/regression.yaml

This is repository-level configuration. Minimal example:

```yaml
repository: your-repo-name
owner: your-team-or-org
default_branch: main
services_root: regression/services
build_tool: none
gate_policies:
  level1: { enabled: true }
  level2: { enabled: true }
  level3: { enabled: true }
  level4: { enabled: true }
  level5: { enabled: true }
impact_map:
  src/**:
    - some-service
```

If you want the framework to build your app and optionally run pre/post hooks, provide `commands`:

```yaml
build_tool: gradle
health_check:
  urls:
    - http://localhost:8080/actuator/health
  timeout_seconds: 2.0
  retries: 30
  delay_seconds: 1.0
commands:
  pre_build:
    - 'chmod +x ./gradlew'
  build:
    - './gradlew --gradle-user-home .gradle-home clean test bootJar'
  pre_test:
    - |
      set -e
      java -jar build/libs/your-app.jar >/dev/null 2>&1 &
      echo $! > .app.pid
      for i in $(seq 1 60); do
        curl -fsS "http://localhost:8080/actuator/health" >/dev/null 2>&1 && exit 0
        sleep 1
      done
      exit 1
  post_test:
    - |
      set +e
      [ -f .app.pid ] && kill "$(cat .app.pid)" && rm -f .app.pid
      exit 0
```

Important notes:

- If `health_check.urls` is configured, the framework checks each URL before running any regression tests.
  - If a health check fails, the run stops immediately with status `error` and a clear “application is down” message.
- Commands run via the host shell (`/bin/sh` on Linux GitHub runners, `cmd.exe` on Windows by default).
- If you run on `ubuntu-latest`, use Linux commands (`./gradlew`, `chmod`, `curl`).
- If you run on Windows runners, use Windows equivalents (`.\gradlew.bat`, PowerShell).
- If you use centralized suites, keep `regression/config/*.yaml` under the suite’s `--assets-root`.

#### 2) regression/config/branches.yaml

This controls which gates/tags apply per branch and can disable gates per branch.

```yaml
default_branch: main
policies:
  main:
    environment: DEV
    gates: [level1, level2]
    include_tags: [develop]
    disabled_gates: [level3, level4, level5]

  release:
    environment: PREPROD
    gates: [level1, level2, level3, level4, level5]
    include_tags: [release]
```

Notes:

- `gates` indicates the gates that are considered “in scope” for this branch policy.
- `disabled_gates` explicitly disables gates.
- `include_tags` and `exclude_tags` filter tests by tags (see `metadata.yaml`).
- The branch used at runtime must match a policy name (or it falls back to defaults).

### Per-Test Metadata (metadata.yaml)

`metadata.yaml` is optional, but recommended. It controls:

- `branches`: which branches the test applies to.
  - If you omit `branches`, the test is considered valid for all branches.
  - If you include `branches`, the current branch must be in the list or discovery will skip it.
- `tags`: used for filtering by branch policy and for reporting.
- `service_type` / `executor` and executor-specific configs.

Example (Python executor):

```yaml
id: TC001_EXAMPLE
name: Example regression
team: platform-team
microservice: some-service
service_type: python
tags: [level1, critical, develop, release]
branches: [main, develop, release]
python:
  script: regression/executors/some_service.py
  function: execute
```

### Executors

Executors determine how the “actual” output is produced.

- **python**: loads and calls a Python function.
- **rest/http**: calls an HTTP endpoint and compares the response.
- **jms**: runs through a JMS provider abstraction (file-backed provider is included for deterministic tests).

### Running Locally (Developer Machine)

From the platform repo:

```powershell
cd C:\Users\pravi\spring-services\enterprise-regression-platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run a gate against a checked-out application repository:

```powershell
regauto run-level1 --repo-root C:\path\to\your-repo --branch main --results-dir .\results\level1
regauto run-level3 --repo-root C:\path\to\your-repo --branch main --results-dir .\results\level3
```

If you want the platform to run the build hooks first:

```powershell
regauto build-run --repo-root C:\path\to\your-repo --branch main --gate level1 --results-dir .\results\build-run-level1
```

### Running in GitHub Actions (Recommended “GitHub Only” Model)

If you want everything to run inside GitHub, you must keep a workflow file in each repo
that should be tested.

Workflow responsibilities:

- Install Python and Java (if you build Spring Boot).
- Install this framework via `pip install git+https://github.com/<owner>/enterprise-regression-platform.git`.
- Run `regauto checkout-build-run`.
- Upload artifacts (`summary.json`, `results.json`, `junit.xml`) so you can inspect comparisons.

Minimum requirements for GitHub Actions:

- Runner: `ubuntu-latest` is recommended for consistent shell behavior.
- `regression/config/regression.yaml` must use Linux commands when running on Ubuntu (example: `./gradlew`, not `.\gradlew.bat`).
- Tests must be discoverable for the branch. If your `metadata.yaml` uses `branches: [...]`, the current branch must be listed.

Centralized suite usage in GitHub Actions:

- Checkout your service repository (default behavior of Actions).
- Checkout `enterprise-regression-platform` into the workspace.
- Install the framework from that local checkout.
- Run `regauto checkout-build-run`.
  - If you keep suites under `enterprise-regression-platform/suites/<directory-name>/`, the CLI auto-detects the suite
    based on:
    - `--directory-name <directory-name>` (already required by `checkout-build-run`)
    - `$GITHUB_WORKSPACE/enterprise-regression-platform/suites/<directory-name>`
  - You can still force a suite root by setting `REGAUTO_ASSETS_ROOT` or passing `--assets-root`.

Where to find results in GitHub Actions:

- Go to the workflow run → “Artifacts”
- Download the artifact for the gate you ran
- Open:
  - `summary.json` for the high-level summary
  - `results.json` for per-test details and JSON diffs
  - `junit.xml` for CI-friendly reporting

## Step-by-Step Tutorial: Banking Producer + Banking Consumer (GitHub + Centralized Suites)

This tutorial shows how to:

- Create 2 Spring Boot services (banking producer + banking consumer).
- Push each service to GitHub.
- Add GitHub Actions in each repo to run regression with this framework.
- Store all regression assets centrally in `enterprise-regression-platform` under `suites/`.
- See pass/fail + comparisons via uploaded artifacts.

The tutorial is structured so you can follow it without needing any local servers other than GitHub Actions runners.

### Overview

- **Repo 1 (Producer):** `banking-producer` (provides account data API).
- **Repo 2 (Consumer):** `banking-consumer` (calls producer API and exposes a “summary/journey” API).
- **Repo 3 (Framework):** `enterprise-regression-platform` (this repo; stores suites + runs tests).

Recommended branch names used below:

- `main` for both application repos.

### 1) Create the banking-producer Spring Boot app

Create a new GitHub repository named `banking-producer` and generate a Spring Boot Gradle project:

- Project: Gradle
- Language: Java
- Spring Boot: 3.3.x
- Java: 17
- Dependencies:
  - Spring Web

Implement the following endpoints:

- `GET /api/banking/accounts/{accountId}`
- `GET /api/banking/ops/status`

Example implementation:

`src/main/resources/application.properties`

```properties
spring.application.name=banking-producer
server.port=8091
```

`src/main/java/.../BankingOpsController.java`

```java
package com.enterprise.banking.producer.ops;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/banking/ops")
public class BankingOpsController {
    @GetMapping("/status")
    public Map<String, Object> status() {
        return Map.of("service", "banking-producer", "status", "UP");
    }
}
```

`src/main/java/.../AccountController.java`

```java
package com.enterprise.banking.producer.accounts;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.util.Map;

@RestController
@RequestMapping("/api/banking/accounts")
public class AccountController {
    private final Map<String, Map<String, Object>> accounts = Map.of(
            "ACC-1001", Map.of("accountId", "ACC-1001", "holderName", "Asha Verma", "balance", new BigDecimal("18450.25"), "currency", "INR", "status", "ACTIVE"),
            "ACC-1002", Map.of("accountId", "ACC-1002", "holderName", "Rahul Mehta", "balance", new BigDecimal("6200.00"), "currency", "INR", "status", "ACTIVE")
    );

    @GetMapping("/{accountId}")
    public ResponseEntity<Map<String, Object>> get(@PathVariable String accountId) {
        Map<String, Object> account = accounts.get(accountId);
        if (account == null) return ResponseEntity.notFound().build();
        return ResponseEntity.ok(account);
    }
}
```

Push to GitHub:

- `git init`
- `git add .`
- `git commit -m "banking producer"`
- `git branch -M main`
- `git remote add origin https://github.com/<owner>/banking-producer.git`
- `git push -u origin main`

### 2) Create the banking-consumer Spring Boot app

Create a new GitHub repository named `banking-consumer` and generate a Spring Boot Gradle project:

- Project: Gradle
- Language: Java
- Spring Boot: 3.3.x
- Java: 17
- Dependencies:
  - Spring Web
  - OpenFeign (Spring Cloud OpenFeign)

`src/main/resources/application.properties`

```properties
spring.application.name=banking-consumer
server.port=8092
upstream.base-url=http://localhost:8091
```

Feign client + summary endpoint:

```java
package com.enterprise.banking.consumer.client;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;

import java.util.Map;

@FeignClient(name = "bankingUpstreamClient", url = "${upstream.base-url}")
public interface BankingUpstreamClient {
    @GetMapping("/api/banking/accounts/{accountId}")
    Map<String, Object> account(@PathVariable("accountId") String accountId);

    @GetMapping("/api/banking/ops/status")
    Map<String, Object> status();
}
```

```java
package com.enterprise.banking.consumer.summary;

import com.enterprise.banking.consumer.client.BankingUpstreamClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/banking/customers")
public class BankingSummaryController {
    private final BankingUpstreamClient upstream;

    public BankingSummaryController(BankingUpstreamClient upstream) {
        this.upstream = upstream;
    }

    @GetMapping("/{accountId}/summary")
    public Map<String, Object> summary(@PathVariable String accountId) {
        Map<String, Object> account = upstream.account(accountId);
        return Map.of(
                "accountId", account.get("accountId"),
                "holderName", account.get("holderName"),
                "balance", account.get("balance"),
                "currency", account.get("currency"),
                "status", account.get("status"),
                "summaryStatus", "READY"
        );
    }
}
```

Push to GitHub (same steps as producer).

### 3) Create centralized suites inside enterprise-regression-platform

In the `enterprise-regression-platform` repository, add two suite folders:

```text
enterprise-regression-platform/
  suites/
    banking-producer/
      regression/...
    banking-consumer/
      regression/...
```

Important naming rule:

- The suite directory name must match the `--directory-name` used in CI for that repo.
- When using GitHub Actions, the CLI auto-detects suites at:
  - `$GITHUB_WORKSPACE/enterprise-regression-platform/suites/<directory-name>`

#### 3.1 banking-producer suite files

`suites/banking-producer/regression/config/regression.yaml` (Ubuntu runner example):

```yaml
repository: banking-producer
default_branch: main
services_root: regression/services
build_tool: gradle
commands:
  pre_build:
    - 'chmod +x ./gradlew'
  build:
    - './gradlew --gradle-user-home .gradle-home clean test bootJar'
  pre_test:
    - |
      set -e
      JAR_PATH="$(ls -1 build/libs/*.jar 2>/dev/null | head -n 1)"
      java -jar "$JAR_PATH" >/dev/null 2>&1 &
      echo $! > .app.pid
      for i in $(seq 1 60); do
        curl -fsS "http://localhost:8091/api/banking/ops/status" >/dev/null 2>&1 && exit 0
        sleep 1
      done
      exit 1
  post_test:
    - |
      set +e
      [ -f .app.pid ] && kill "$(cat .app.pid)" >/dev/null 2>&1
      rm -f .app.pid
      exit 0
```

Add a python executor for calling the running service:

`suites/banking-producer/regression/executors/banking_producer.py`

```python
from __future__ import annotations

import json
from urllib.request import urlopen

BASE_URL = "http://localhost:8091"

def _get(path: str) -> dict[str, object]:
    with urlopen(f"{BASE_URL}{path}") as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))

def execute(input_payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    account_id = input_payload["accountId"]
    response = _get(f"/api/banking/accounts/{account_id}")
    return {
        "accountId": response["accountId"],
        "holderName": response["holderName"],
        "balance": response["balance"],
        "currency": response["currency"],
        "status": response["status"],
    }
```

Create a test case:

```text
suites/banking-producer/regression/services/banking-account-service/level1/TC001_account_lookup/
  input.json
  expected_output.json
  metadata.yaml
```

`input.json`

```json
{ "accountId": "ACC-1001" }
```

`expected_output.json`

```json
{
  "accountId": "ACC-1001",
  "holderName": "Asha Verma",
  "balance": 18450.25,
  "currency": "INR",
  "status": "ACTIVE"
}
```

`metadata.yaml`

```yaml
id: BANK_PRODUCER_TC001_ACCOUNT_LOOKUP
team: banking-team
service_type: python
branches: [main]
python:
  script: regression/executors/banking_producer.py
  function: execute
```

#### 3.2 banking-consumer suite files (decoupled from producer)

To avoid coupling, the consumer suite can start an upstream stub on `localhost:8091`
that returns deterministic account responses. This makes consumer regression stable even
when producer is not built or not deployed.

`suites/banking-consumer/regression/config/regression.yaml` (Ubuntu runner example):

```yaml
repository: banking-consumer
default_branch: main
services_root: regression/services
build_tool: gradle
commands:
  pre_build:
    - 'chmod +x ./gradlew'
  build:
    - './gradlew --gradle-user-home .gradle-home clean test bootJar'
  pre_test:
    - |
      set -e
      python - <<'PY' >/dev/null 2>&1 &
      import json
      import re
      from http.server import BaseHTTPRequestHandler, HTTPServer
      from urllib.parse import urlparse

      ACCOUNTS = {
          "ACC-1001": {"accountId": "ACC-1001", "holderName": "Asha Verma", "balance": 18450.25, "currency": "INR", "status": "ACTIVE"},
          "ACC-1002": {"accountId": "ACC-1002", "holderName": "Rahul Mehta", "balance": 6200.00, "currency": "INR", "status": "ACTIVE"},
      }

      class Handler(BaseHTTPRequestHandler):
          def log_message(self, format, *args):
              return
          def _send(self, code, payload):
              body = json.dumps(payload).encode("utf-8")
              self.send_response(code)
              self.send_header("Content-Type", "application/json")
              self.send_header("Content-Length", str(len(body)))
              self.end_headers()
              self.wfile.write(body)
          def do_GET(self):
              path = urlparse(self.path).path
              if path == "/api/banking/ops/status":
                  return self._send(200, {"service": "banking-producer-stub", "status": "UP"})
              match = re.fullmatch(r"/api/banking/accounts/([^/]+)", path)
              if match:
                  account_id = match.group(1)
                  account = ACCOUNTS.get(account_id)
                  return self._send(200, account) if account else self._send(404, {"error": "not_found"})
              return self._send(404, {"error": "not_found"})

      HTTPServer(("0.0.0.0", 8091), Handler).serve_forever()
      PY
      echo $! > .upstream.pid

      JAR_PATH="$(ls -1 build/libs/*.jar 2>/dev/null | head -n 1)"
      java -jar "$JAR_PATH" >/dev/null 2>&1 &
      echo $! > .app.pid
      for i in $(seq 1 60); do
        curl -fsS "http://localhost:8092/actuator/health" >/dev/null 2>&1 && exit 0 || true
        curl -fsS "http://localhost:8092/api/banking/customers/ACC-1001/summary" >/dev/null 2>&1 && exit 0 || true
        sleep 1
      done
      exit 1
  post_test:
    - |
      set +e
      [ -f .app.pid ] && kill "$(cat .app.pid)" >/dev/null 2>&1
      [ -f .upstream.pid ] && kill "$(cat .upstream.pid)" >/dev/null 2>&1
      rm -f .app.pid .upstream.pid
      exit 0
```

Add a consumer executor:

`suites/banking-consumer/regression/executors/banking_consumer.py`

```python
from __future__ import annotations

import json
from urllib.request import urlopen

BASE_URL = "http://localhost:8092"

def _get(path: str) -> dict[str, object]:
    with urlopen(f"{BASE_URL}{path}") as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))

def execute(input_payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    account_id = input_payload["accountId"]
    response = _get(f"/api/banking/customers/{account_id}/summary")
    return {
        "accountId": response["accountId"],
        "holderName": response["holderName"],
        "balance": response["balance"],
        "currency": response["currency"],
        "status": response["status"],
        "summaryStatus": response["summaryStatus"],
    }
```

Create a test case:

`input.json`

```json
{ "accountId": "ACC-1001" }
```

`expected_output.json`

```json
{
  "accountId": "ACC-1001",
  "holderName": "Asha Verma",
  "balance": 18450.25,
  "currency": "INR",
  "status": "ACTIVE",
  "summaryStatus": "READY"
}
```

`metadata.yaml`

```yaml
id: BANK_CONSUMER_TC001_ACCOUNT_SUMMARY
team: banking-team
service_type: python
branches: [main]
python:
  script: regression/executors/banking_consumer.py
  function: execute
```

Commit and push the suites to the `enterprise-regression-platform` GitHub repository.

### 4) Add GitHub Actions to banking-producer

In `banking-producer`, create `.github/workflows/regression.yml`:

```yaml
name: Banking Producer Regression

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  regression:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        gate: [level1]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Checkout enterprise regression platform
        uses: actions/checkout@v4
        with:
          repository: ${{ github.repository_owner }}/enterprise-regression-platform
          path: enterprise-regression-platform
      - name: Install enterprise regression framework
        run: |
          python -m pip install --upgrade pip
          python -m pip install "./enterprise-regression-platform"
      - name: Run regression
        run: |
          regauto checkout-build-run \
            --remote-url "${{ github.server_url }}/${{ github.repository }}.git" \
            --branch "${{ github.head_ref || github.ref_name }}" \
            --gate "${{ matrix.gate }}" \
            --workspace-root "$RUNNER_TEMP/regression-workspaces" \
            --directory-name banking-producer \
            --results-dir "$RUNNER_TEMP/regression-results/${{ matrix.gate }}" \
            --trigger github-actions
      - name: Upload artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: banking-producer-${{ matrix.gate }}-results
          path: ${{ runner.temp }}/regression-results/${{ matrix.gate }}
```

### 5) Add GitHub Actions to banking-consumer

In `banking-consumer`, create `.github/workflows/regression.yml` (consumer-only, upstream stubbed):

```yaml
name: Banking Consumer Regression

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  regression:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        gate: [level3, level4, level5]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Checkout enterprise regression platform
        uses: actions/checkout@v4
        with:
          repository: ${{ github.repository_owner }}/enterprise-regression-platform
          path: enterprise-regression-platform
      - name: Install enterprise regression framework
        run: |
          python -m pip install --upgrade pip
          python -m pip install "./enterprise-regression-platform"
      - name: Run regression
        run: |
          regauto checkout-build-run \
            --remote-url "${{ github.server_url }}/${{ github.repository }}.git" \
            --branch "${{ github.head_ref || github.ref_name }}" \
            --gate "${{ matrix.gate }}" \
            --workspace-root "$RUNNER_TEMP/regression-workspaces" \
            --directory-name banking-consumer \
            --results-dir "$RUNNER_TEMP/regression-results/${{ matrix.gate }}" \
            --trigger github-actions
      - name: Upload artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: banking-consumer-${{ matrix.gate }}-results
          path: ${{ runner.temp }}/regression-results/${{ matrix.gate }}
```

### 6) Verify regressions

After pushing code to either repo:

- Go to GitHub → Actions tab → open the latest run.
- Download artifacts:
  - `summary.json`: high-level counts + pass rate
  - `results.json`: per-test details and JSON differences (expected vs actual)
  - `junit.xml`: CI format

If `results.json` contains differences for a test, the workflow fails and blocks the PR merge (if branch protection requires it).

### Optional: Centralized Webhook-Driven Mode (Dashboard + Server Runner)

Use this when you want pushes to trigger a central server to pull/build/test and optionally
publish pass/fail statuses back into GitHub.

1) Start the dashboard API:

```bash
uvicorn regauto.dashboard.api:app --host 0.0.0.0 --port 8000
```

2) Configure environment variables on that host:

- `REGAUTO_GITHUB_WEBHOOK_SECRET`: GitHub webhook secret used to validate signatures.
- `REGAUTO_GITHUB_TOKEN`: token used for cloning private repos and posting commit statuses.
- `REGAUTO_WEBHOOK_WORKSPACE_ROOT`: where repos will be cloned on the server.
- `REGAUTO_WEBHOOK_RESULTS_ROOT`: where results will be written on the server.
- `REGAUTO_WEBHOOK_CLEAN_WORKSPACE`: `true|false` to clean untracked files between runs.
- `REGAUTO_WEBHOOK_PUBLISH`: `true|false` to publish results to the dashboard DB.
- `REGAUTO_DATABASE_URL`: optional; defaults to SQLite.
- `REGAUTO_API_KEY`: optional; required to access protected dashboard endpoints if set.

3) Add a webhook in each application repository:

- Repository → Settings → Webhooks → Add webhook
- Payload URL: `https://<your-host>/webhooks/github`
- Content type: `application/json`
- Secret: same value as `REGAUTO_GITHUB_WEBHOOK_SECRET`
- Events: Push events

4) Where to see results:

- Dashboard UI: `GET /ui`
- Latest runs: `GET /executions/latest`
- Full run details and diffs: `GET /executions/{run_id}/results`
- Raw artifacts on disk:
  - `REGAUTO_WEBHOOK_RESULTS_ROOT/<repo>/<branch>/<commit>/<gate>/`

### Results and Comparison Outputs (What Files Mean)

Every run writes:

- `summary.json`
  - Total/passed/failed/errored and pass rate.
- `results.json`
  - One entry per test with:
    - status
    - runtime metadata
    - any error
    - field-by-field JSON differences (when comparison fails)
- `junit.xml`
  - Suitable for CI dashboards and test reporting.

If you run inside GitHub Actions, the CLI also emits:

- GitHub step summary output (job summary)
- GitHub annotations for failed tests (clickable)

### Troubleshooting (Common Failures)

- **`.\\gradlew.bat: not found` on `ubuntu-latest`**
  - Your repo build command is Windows-only. Use `./gradlew` for Ubuntu runners.
- **`No regression tests were discovered for the enabled gate and branch`**
  - Either the folder layout is wrong, or the branch policy/tag filters excluded everything.
  - If `metadata.yaml` contains `branches: [...]`, ensure the current branch (ex: `main`) is included.
  - Confirm `services_root` points to the right directory (default `regression/services`).
- **Gate is skipped**
  - Gate disabled by repository `gate_policies` or branch `disabled_gates` in `branches.yaml`.
