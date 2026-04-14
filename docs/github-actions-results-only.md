# GitHub Actions Results-Only Operating Model

Use this model when the organization wants the entire regression strategy to run inside GitHub Actions
without a separately hosted dashboard.

## What Runs Where

- GitHub Actions checks out the branch or pull request.
- The workflow builds and starts the application when needed.
- `regauto` discovers and executes the requested regression layer from the repo's `regression/` folder.
- `regauto` compares actual results against `expected_output.json`.
- GitHub Actions publishes summaries, diffs, JUnit XML, and artifacts.
- The job exits non-zero when a regression is detected.

## Recommended Enterprise Mapping

- `level1`: PR-fast unit regression.
- `level2`: PR or post-merge service component or API regression.
- `level3`: Nightly integration regression.
- `level4`: Release-candidate end-to-end business journey regression.
- `level5`: Operational certification before promotion or on a scheduled release branch cadence.

## Example Level 1 Workflow

```yaml
name: Level 1 Regression

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  level1:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install regression framework
        run: pip install git+https://github.com/pravi976/enterprise-regression-platform.git
      - name: Run Level 1
        run: |
          regauto run-level1 \
            --repo-root . \
            --results-dir regression-results/level1 \
            --trigger pr \
            --commit-sha ${{ github.sha }} \
            --branch ${{ github.head_ref || github.ref_name }}
      - name: Upload Level 1 artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: level1-regression-results
          path: regression-results/level1
```

## Example Level 3 Workflow

```yaml
name: Level 3 Nightly Integration Regression

on:
  workflow_dispatch:
  schedule:
    - cron: "30 18 * * 1-5"

jobs:
  level3:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        branch: [test]
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ matrix.branch }}
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install regression framework
        run: pip install git+https://github.com/pravi976/enterprise-regression-platform.git
      - name: Run Level 3
        run: |
          regauto run-level3 \
            --repo-root . \
            --results-dir regression-results/level3-${{ matrix.branch }} \
            --branch ${{ matrix.branch }} \
            --trigger schedule
      - name: Upload Level 3 artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: level3-${{ matrix.branch }}-regression-results
          path: regression-results/level3-${{ matrix.branch }}
```

## Example Release Certification Workflow

```yaml
name: Release Certification Regression

on:
  workflow_dispatch:

jobs:
  release-certification:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        layer: [level4, level5]
    steps:
      - uses: actions/checkout@v4
        with:
          ref: release
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install regression framework
        run: pip install git+https://github.com/pravi976/enterprise-regression-platform.git
      - name: Run release certification layer
        run: |
          regauto run-layer \
            --repo-root . \
            --gate ${{ matrix.layer }} \
            --results-dir regression-results/${{ matrix.layer }} \
            --branch release \
            --trigger manual
      - name: Upload certification artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.layer }}-regression-results
          path: regression-results/${{ matrix.layer }}
```

## Result Locations

Open:

```text
Repository -> Actions -> Workflow run -> Summary
```

Artifacts typically include:

- `summary.json`
- `results.json`
- `junit.xml`

## Failure Behavior

- Exit code `1`: at least one test failed or errored.
- Exit code `2`: the requested enabled layer found no tests or the test assets are invalid.

## Recommended Operating Pattern

- Protect `main` with `level1`.
- Add `level2` to post-merge validation or critical PR paths.
- Schedule `level3` on `test`.
- Run `level4` and `level5` before release promotion.
- Keep regression assets service-owned under each repo's `regression/` folder.
