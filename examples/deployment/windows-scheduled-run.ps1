$ErrorActionPreference = "Stop"
$Project = "C:\regauto\enterprise-regression-platform"
$Python = "C:\regauto\venv\Scripts\python.exe"
Set-Location $Project
& $Python -m regauto.cli checkout-build-run `
  --remote-url "https://github.com/YOUR_ORG/YOUR_APP_REPO.git" `
  --branch "develop" `
  --gate "gate1" `
  --workspace-root "C:\regauto\workspaces" `
  --directory-name "YOUR_APP_REPO" `
  --results-dir "C:\regauto\results\develop-gate1" `
  --trigger "schedule" `
  --publish
exit $LASTEXITCODE
