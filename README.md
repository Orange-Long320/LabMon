# LabMon

[简体中文](README.zh-CN.md)

LabMon is a lightweight, read-only web dashboard for shared GPU servers in research labs. It helps a team answer the everyday questions before starting a run: which GPU is free, who is using the busy cards, what command is running, and whether recent training logs are still moving.

![LabMon dashboard](img/dashboard.png)

## Highlights

- Physical GPU order: cards are shown as GPU `0`, `1`, `2`, `3`, matching `nvidia-smi`.
- Per-GPU status: utilization, memory, temperature, power, owner, command line, process count, and start time.
- Host status: CPU, memory, disk, load average, free GPU count, and collector warnings.
- Server-side trends: records recent GPU, CPU, and memory history even when no browser page is open.
- Training progress: scans configured log directories and extracts common fields such as `step`, `epoch`, `loss`, `reward`, `lr`, and `eta`.
- Built-in authentication: local users, PBKDF2 password hashes, signed HttpOnly sessions, and protected API/static routes.
- Read-only by design: no process killing, no scheduling, and no writes to users' experiment directories.

## Login

LabMon can run without authentication for local demos. For shared lab deployment, enable `LABMON_AUTH=1` so only group members with local LabMon accounts can access the dashboard.

![LabMon login](img/login.png)

## Quick Start

Install dependencies with `uv`:

```bash
uv sync --dev
```

Run a local demo with four mock RTX 3090 cards:

```bash
LABMON_DEMO=1 uv run uvicorn labmon.app:app --reload --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765>.

To preview the login flow locally:

```bash
uv run python scripts/manage_users.py add demo
LABMON_DEMO=1 \
LABMON_AUTH=1 \
LABMON_AUTH_SECRET="$(openssl rand -hex 32)" \
uv run uvicorn labmon.app:app --reload --host 127.0.0.1 --port 8765
```

## One-Command Server Install

Prerequisites: Linux, NVIDIA drivers, `git`, `uv`, and a user with `sudo` access.

For a first install, clone LabMon into `/opt/labmon`:

```bash
sudo git clone https://github.com/Orange-Long320/LabMon.git /opt/labmon && cd /opt/labmon && sudo env LABMON_ADMIN_USER=alice bash deploy/install.sh
```

Expanded form:

```bash
sudo git clone https://github.com/Orange-Long320/LabMon.git /opt/labmon
cd /opt/labmon
sudo env LABMON_ADMIN_USER=alice bash deploy/install.sh
```

Replace `alice` with the first LabMon account you want to create. The script will prompt for that user's password.

The installer will:

- run `uv sync --no-dev`
- create `/etc/labmon/labmon.env` with a random `LABMON_AUTH_SECRET`
- install and start `/etc/systemd/system/labmon.service`
- enable boot startup and automatic restart through `systemd`

If users already exist, run the installer without `LABMON_ADMIN_USER`:

```bash
cd /opt/labmon
sudo bash deploy/install.sh
```

Status and logs:

```bash
sudo systemctl status labmon
sudo journalctl -u labmon -f
```

`systemd` detaches LabMon from your SSH session, starts it after reboot, and restarts it if the process exits unexpectedly. It cannot prevent an administrator from stopping the service, a power loss, or a root-level forced kill, but it does solve SSH disconnects killing the server process.

## Campus Intranet Access

The default installer makes LabMon listen on `0.0.0.0:8765`. That means the server accepts connections on all network interfaces, but it does not guarantee that the whole campus network can route to the machine-room subnet.

First check the listener on the server:

```bash
sudo ss -lntp | grep 8765
```

If you see `0.0.0.0:8765`, LabMon is listening on the server network interfaces. Then test from a computer on the campus intranet:

```bash
curl http://<server-ip>:8765/api/me
```

If it returns JSON, open `http://<server-ip>:8765` in a browser. In this case, restrict the firewall rule to the campus CIDR instead of exposing the port broadly:

```bash
sudo ufw allow from <campus-cidr> to any port 8765 proto tcp
```

Or with firewalld:

```bash
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="<campus-cidr>" port port="8765" protocol="tcp" accept'
sudo firewall-cmd --reload
```

If the machine-room LAN can access LabMon but the wider campus intranet cannot, the machine-room subnet is probably blocked by routing or firewall policy. Ask the network administrator to allow:

```text
source: campus intranet CIDR
destination: GPU server IP
port: TCP 8765
purpose: read-only LabMon GPU monitoring dashboard for the research group
```

If direct access to the GPU server cannot be allowed, bind LabMon to `127.0.0.1` and put an Nginx reverse proxy on a campus-reachable gateway or jump host. Users will open the gateway address, and the gateway will forward traffic to the GPU server.

To change the port, log roots, history window, or HTTPS cookie setting, edit:

```bash
sudo nano /etc/labmon/labmon.env
sudo systemctl restart labmon
```

If the port may be reachable outside the campus intranet, bind LabMon to `127.0.0.1` and access it through an SSH tunnel, a VPN, or a reverse proxy with HTTPS. When serving over HTTPS, set `LABMON_AUTH_COOKIE_SECURE=1`.

## Temporary Debug Run

For quick debugging only:

```bash
uv sync --no-dev
uv run python scripts/manage_users.py add alice
LABMON_LOG_ROOTS="/home/*/runs,/home/*/logs,/data/runs,/data/logs" \
LABMON_AUTH=1 \
LABMON_AUTH_SECRET="$(openssl rand -hex 32)" \
uv run uvicorn labmon.app:app --host 0.0.0.0 --port 8765
```

This runs in your SSH foreground session and may exit when SSH disconnects.

## User Management

After server deployment, use the installed Python and deployed users file:

```bash
sudo env LABMON_USERS_FILE=/opt/labmon/labmon-users.json /opt/labmon/.venv/bin/python /opt/labmon/scripts/manage_users.py add bob
sudo env LABMON_USERS_FILE=/opt/labmon/labmon-users.json /opt/labmon/.venv/bin/python /opt/labmon/scripts/manage_users.py list
sudo env LABMON_USERS_FILE=/opt/labmon/labmon-users.json /opt/labmon/.venv/bin/python /opt/labmon/scripts/manage_users.py remove bob
```

For local development:

```bash
uv run python scripts/manage_users.py add alice
uv run python scripts/manage_users.py list
uv run python scripts/manage_users.py remove alice
```

Each user gets an independent account. Passwords are stored as PBKDF2 hashes in `LABMON_USERS_FILE`; the default file is `./labmon-users.json`, which is intentionally ignored by git.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `LABMON_DEMO` | unset | Set to `1` to use mock four-card RTX 3090 data. |
| `LABMON_LOG_ROOTS` | demo sample logs | Comma-separated directories or glob patterns to scan for logs. |
| `LABMON_HOST_LABEL` | system hostname | Overrides the host label shown in the header. |
| `LABMON_REFRESH_SECONDS` | `1` | Dashboard polling interval in seconds. |
| `LABMON_HISTORY_SECONDS` | `3600` | Server-side metric history retention in seconds. |
| `LABMON_HISTORY_INTERVAL_SECONDS` | `1` | Server-side metric sampling interval in seconds. |
| `LABMON_AUTH` | unset | Set to `1` to require login. |
| `LABMON_AUTH_SECRET` | unset | Required in auth mode; use `openssl rand -hex 32`. |
| `LABMON_USERS_FILE` | `./labmon-users.json` | Local user database path. |
| `LABMON_AUTH_SESSION_HOURS` | `168` | Session lifetime in hours. |
| `LABMON_AUTH_COOKIE_SECURE` | unset | Set to `1` when serving over HTTPS. |

## API

- `GET /api/snapshot`: complete dashboard snapshot with host, GPU, process, log, and warning data.
- `GET /api/history?seconds=600`: server-side metric history for GPU utilization, GPU memory, CPU, and RAM.
- `GET /api/logs/{log_id}?lines=200`: tail a discovered log file by whitelist ID.
- `GET /api/me`: current authenticated user when auth is enabled.
- `POST /api/login`: create a session.
- `POST /api/logout`: clear the session.

`/api/logs/{log_id}` only reads files discovered by the log scanner, so callers cannot pass arbitrary filesystem paths.

## Data Sources

In demo mode, LabMon reads real local CPU, memory, and disk data, then generates four dynamic mock RTX 3090 cards and sample training logs.

In server mode, LabMon uses `psutil` for host resources, `nvidia-smi` for GPU and compute-process data, and PID lookups to attach Linux user, command line, memory usage, and start time.

## Tests

```bash
uv run pytest
```

The test suite covers GPU CSV parsing, PID enrichment, missing/permission-denied collectors, log parsing, API behavior, and authenticated route protection.
