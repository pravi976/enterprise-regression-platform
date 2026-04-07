# GitHub Actions Results-Only Operating Model

Use this model when the organization does not want Azure hosting, VMs, Kubernetes, containers, or a
separate dashboard service.

## What Runs Where

- GitHub Actions checks out the latest branch or pull request.
- GitHub Actions builds and starts the application when needed.
- `regauto` discovers and executes Gate 1 or Gate 2 tests from the repo's `regression/` folder.
- `regauto` compares actual results against `expected_output.json`.
- GitHub Actions shows pass/fail summaries and field-level diffs in the job summary.
- GitHub Actions uploads `summary.json`, `results.json`, and `junit.xml` as artifacts.
- The workflow exits non-zero when a regression is found, so the PR/commit gate fails.

## Developer Experience

Developers do not need a hosted dashboard. They open the GitHub Actions run and review:

- The workflow job status.
- The GitHub job summary.
- Clickable annotations pointing to each test's `metadata.yaml`.
- Field-by-field differences for failed comparisons.
- Uploaded artifacts:
  - `summary.json`
  - `results.json`
  - `junit.xml`

## Gate 1 Workflow

Use Gate 1 for fast PR/commit validation:

```yaml
name: Gate 1 Regression

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  gate1:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install regression framework
        run: pip install git+https://github.com/pravi976/enterprise-regression-platform.git
      - name: Run Gate 1
        run: |
          regauto run-gate1 \
            --repo-root . \
            --results-dir regression-results/gate1 \
            --trigger pr \
            --commit-sha ${{ github.sha }} \
            --branch ${{ github.head_ref || github.ref_name }}
      - name: Upload Gate 1 artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: gate1-regression-results
          path: regression-results/gate1
```

## Gate 2 Workflow

Use Gate 2 for scheduled or manual deeper validation:

```yaml
name: Gate 2 Scheduled Regression

on:
  workflow_dispatch:
  schedule:
    - cron: "30 18 * * 1-5"

jobs:
  gate2:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        branch: [develop, test, release]
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ matrix.branch }}
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install regression framework
        run: pip install git+https://github.com/pravi976/enterprise-regression-platform.git
      - name: Run Gate 2
        run: |
          regauto run-gate2 \
            --repo-root . \
            --results-dir regression-results/gate2-${{ matrix.branch }} \
            --branch ${{ matrix.branch }} \
            --trigger schedule
      - name: Upload Gate 2 artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: gate2-${{ matrix.branch }}-regression-results
          path: regression-results/gate2-${{ matrix.branch }}
```

## Where To See Results

Open:

```text
Repository -> Actions -> Workflow run -> Summary
```

The summary includes:

- Total tests.
- Passed, failed, and errored counts.
- Pass rate.
- Test table by service/type/test id.
- Field-level diff table for failures.

Then open:

```text
Repository -> Actions -> Workflow run -> Artifacts
```

Download the artifact and inspect:

- `summary.json` for dashboard-friendly run totals.
- `results.json` for test-level details and diffs.
- `junit.xml` for CI/test-report tooling.

## Failure Behavior

The workflow fails automatically when any test status is:

- `failed`
- `error`

The framework exits with code `1` for validation or execution failures. It exits with code `2` when
an enabled gate discovers no tests or a test folder is invalid, such as missing `expected_output.json`.

## Recommended Enterprise Pattern

- Keep `regression/` assets in each application repo.
- Use GitHub Actions job summary as the management-friendly report for now.
- Use artifacts for audit/history.
- Use branch protection rules to require Gate 1 before merge.
- Use scheduled Gate 2 workflows for `develop`, `test`, and `release` branches.
