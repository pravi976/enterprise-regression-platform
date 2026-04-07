$ErrorActionPreference = "Stop"
$Project = "C:\regauto\enterprise-regression-platform"
$Python = "C:\regauto\venv\Scripts\python.exe"

Set-Location $Project
& $Python -m uvicorn regauto.dashboard.api:app --host 0.0.0.0 --port 8080
