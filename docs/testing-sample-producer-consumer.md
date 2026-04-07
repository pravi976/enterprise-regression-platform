# Testing sample-producer and sample-consumer

This guide validates the enterprise regression platform against the local Gradle applications:

- `C:\Users\pravi\spring-services\sample-producer`
- `C:\Users\pravi\spring-services\sample-consumer`

The regression assets live inside each application repository under `regression/`.

## 1. Install the platform

```powershell
cd C:\Users\pravi\spring-services\enterprise-regression-platform
python -m pip install -e ".[dev]"
```

## 2. Discover producer tests

```powershell
python -m regauto.cli discover-tests --repo-root ..\sample-producer --gate gate1 --tag develop
```

Expected result: two Gate 1 tests are discovered:

- `PRODUCER_REST_TC001_SEARCH_PRODUCTS`
- `PRODUCER_JMS_TC001_PRODUCT_CHANGED`

## 3. Discover consumer tests

```powershell
python -m regauto.cli discover-tests --repo-root ..\sample-consumer --gate gate1 --tag develop
```

Expected result: two Gate 1 tests are discovered:

- `CONSUMER_REST_TC001_CATALOG_HEALTH`
- `CONSUMER_JMS_TC001_PRODUCT_EVENT_CONSUMED`

## 4. Run producer Gate 1 regression only

```powershell
python -m regauto.cli run-gate1 --repo-root ..\sample-producer --results-dir results\sample-producer\gate1-develop --branch develop
```

Expected result: two tests pass and reports are created under:

```text
results\sample-producer\gate1-develop
```

## 5. Run consumer Gate 1 regression only

```powershell
python -m regauto.cli run-gate1 --repo-root ..\sample-consumer --results-dir results\sample-consumer\gate1-develop --branch develop
```

Expected result: two tests pass and reports are created under:

```text
results\sample-consumer\gate1-develop
```

## 6. Run producer build plus Gate 1

```powershell
python -m regauto.cli build-run --repo-root ..\sample-producer --branch develop --gate gate1 --results-dir results\sample-producer\build-run-gate1-develop --trigger manual
```

This command runs the Gradle command configured in:

```text
sample-producer\regression\config\branches.yaml
```

Then it runs Gate 1 regression. Expected result: Gradle build passes, then two regression tests pass.

## 7. Run consumer build plus Gate 1

```powershell
python -m regauto.cli build-run --repo-root ..\sample-consumer --branch develop --gate gate1 --results-dir results\sample-consumer\build-run-gate1-develop --trigger manual
```

Expected result: Gradle build passes, then two regression tests pass.

## 8. Verify disabled Gate 2 behavior on develop

Both sample repos disable Gate 2 on `develop` in `branches.yaml`.

```powershell
python -m regauto.cli run-gate2 --repo-root ..\sample-producer --results-dir results\sample-producer\gate2-develop --branch develop
```

Expected result: the command exits with code `0` and writes a skipped `summary.json`.

## 9. Test Gate 2 on release policy

```powershell
python -m regauto.cli run-gate2 --repo-root ..\sample-producer --results-dir results\sample-producer\gate2-release --branch release
python -m regauto.cli run-gate2 --repo-root ..\sample-consumer --results-dir results\sample-consumer\gate2-release --branch release
```

Expected result: Gate 2 tests run because `release` enables Gate 2.

## 10. Test impact mapping

```powershell
python -m regauto.cli impacted-tests --repo-root ..\sample-producer --changed-file src/main/java/com/enterprise/sample/producer/product/ProductController.java
python -m regauto.cli impacted-tests --repo-root ..\sample-consumer --changed-file src/main/java/com/enterprise/sample/consumer/messaging/ProductEventListener.java
```

Expected result:

- Producer product code maps to `product-service`
- Consumer messaging code maps to `catalog-events`

## Notes

The REST sample tests use `response_fixture` so the platform validates REST-shaped responses without requiring a live Spring Boot service. In real environments, remove `response_fixture` and configure `base_url`, `endpoint`, headers, auth, and expected status.

The JMS sample tests use the file-backed provider to validate the JMS execution contract without an external broker. Enterprise broker support should be added by implementing the `JmsProvider` interface in the platform.
