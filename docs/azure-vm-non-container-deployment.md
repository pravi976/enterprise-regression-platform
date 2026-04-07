# Azure Non-Container Deployment Guide

This project is a Python service, so the production equivalent of a Java `jar` deployment is a
Python package installed into a virtual environment and hosted as a long-running service.

Use this model when your organization does not allow Docker, Kubernetes, Helm, or container
runtimes.

## Recommended Azure Target

Use an Azure Linux VM for the dashboard/control-plane API and PostgreSQL for metadata.

Why this option:

- No containers required.
- Works like traditional enterprise application hosting.
- Easy to secure with NSG rules, private networking, Nginx, and systemd.
- Compatible with GitHub-hosted runners, self-hosted runners, cron, and enterprise schedulers.

## Runtime Components

- Azure VM running Ubuntu or RHEL-compatible Linux
- Python 3.11+
- Git
- Python virtual environment under `/opt/regauto/venv`
- Application checkout under `/opt/regauto/enterprise-regression-platform`
- `systemd` service for the FastAPI dashboard
- Optional Nginx reverse proxy for HTTPS
- PostgreSQL database, preferably Azure Database for PostgreSQL

## Optional Azure VM Creation

If you do not already have a VM, create one with Azure CLI from your workstation:

```bash
az login
az group create --name rg-regauto --location eastus
az vm create \
  --resource-group rg-regauto \
  --name vm-regauto-dashboard \
  --image Ubuntu2204 \
  --admin-username azureuser \
  --generate-ssh-keys
az vm open-port --resource-group rg-regauto --name vm-regauto-dashboard --port 8080
az vm show --resource-group rg-regauto --name vm-regauto-dashboard --show-details --query publicIps --output tsv
```

For production, prefer private networking and expose the UI through your enterprise reverse proxy,
VPN, or Application Gateway rather than opening port `8080` directly to the internet.

## Linux VM Installation

Connect to the VM and run:

```bash
sudo useradd --system --create-home --home-dir /opt/regauto --shell /usr/sbin/nologin regauto || true
sudo mkdir -p /opt/regauto
sudo chown -R regauto:regauto /opt/regauto
sudo apt-get update
sudo apt-get install -y git python3.11 python3.11-venv python3-pip
```

Clone and install:

```bash
sudo -u regauto git clone https://github.com/pravi976/enterprise-regression-platform.git /opt/regauto/enterprise-regression-platform
sudo -u regauto python3.11 -m venv /opt/regauto/venv
sudo -u regauto /opt/regauto/venv/bin/python -m pip install --upgrade pip
sudo -u regauto /opt/regauto/venv/bin/python -m pip install /opt/regauto/enterprise-regression-platform
```

Configure secrets in an environment file:

```bash
sudo install -o regauto -g regauto -m 640 /opt/regauto/enterprise-regression-platform/examples/deployment/regauto-dashboard.env.example /etc/regauto-dashboard.env
sudo nano /etc/regauto-dashboard.env
```

Install and start the service:

```bash
sudo cp /opt/regauto/enterprise-regression-platform/examples/deployment/regauto-dashboard.service /etc/systemd/system/regauto-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable regauto-dashboard
sudo systemctl start regauto-dashboard
sudo systemctl status regauto-dashboard
```

Access the UI from the VM:

```text
http://<vm-private-or-public-ip>:8080/ui
```

For production, place Nginx or an enterprise reverse proxy in front of the service and expose HTTPS.

## Example Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name regression.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Windows VM Option

Use a Windows VM when your enterprise runners/services are Windows-first.

```powershell
mkdir C:\regauto
cd C:\regauto
git clone https://github.com/pravi976/enterprise-regression-platform.git
py -3.11 -m venv C:\regauto\venv
C:\regauto\venv\Scripts\python.exe -m pip install --upgrade pip
C:\regauto\venv\Scripts\python.exe -m pip install C:\regauto\enterprise-regression-platform
```

Run interactively for validation:

```powershell
$env:REGAUTO_DATABASE_URL = "postgresql+psycopg://regression:<password>@<postgres-host>:5432/regression"
$env:REGAUTO_API_KEY = "<strong-api-key>"
C:\regauto\venv\Scripts\python.exe -m uvicorn regauto.dashboard.api:app --host 0.0.0.0 --port 8080
```

For production, host with NSSM, Windows Service Wrapper, IIS reverse proxy, or a scheduled startup
task that calls `examples/deployment/windows-dashboard-run.ps1`.

## Running Gates From The UI

The dashboard UI runs on the server where the API is hosted. The repository path entered in the UI
must exist on that same server.

Example repo path on Linux:

```text
/opt/regauto/workspaces/sample-inventory
```

Example repo path on Windows:

```text
C:\regauto\workspaces\sample-inventory
```

If your preferred model is to keep execution in GitHub Actions, use the UI only for latest results
and keep Gate 1/Gate 2 runs in CI.

## Scheduled Runs Without Containers

Use one of these:

- GitHub Actions `schedule`
- Linux cron or systemd timer
- Windows Task Scheduler
- Enterprise scheduler such as Control-M

The scheduled job should run `regauto checkout-build-run` or `regauto build-run` and pass `--publish`
so the dashboard can show the latest results.
