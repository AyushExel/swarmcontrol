# Tutorial: self-host the governor for your team (about 30 minutes)

This sets the governor up the way a company would run it: one server inside your network that holds the laws and the dashboard, with every developer's Claude Code sessions reporting to it. Agent code and traces never leave your network.

```
 developer laptops                         your network
 ┌──────────────────────┐   HTTPS + token   ┌───────────────────────────────┐
 │ Claude Code + hook   │ ────────────────► │ SwarmControl (one process)  │
 │ (.claude/hooks/…)    │ ◄──── allow/deny  │  API + dashboard on :8787     │
 └──────────────────────┘                   │  laws + event log (SQLite)    │
 ┌──────────────────────┐                   └───────────────────────────────┘
 │ browser: dashboard   │ ──────────────────────────────────▲
 └──────────────────────┘
```

**What was tested** (November 12, 2026, on macOS, with the Python governor):
- **The install below** (with pipx then; `uv tool install` was checked the same way on November 13): a clean install from the built wheel, start with a token on a network address, the token checks (missing, wrong, correct), the dashboard and the connector download.
- **Docker Compose (section 3a):** built and run with Colima on macOS: it refuses to start without `SWARMCONTROL_TOKEN`, the token checks pass, the gates are compiled natively in the image, and a governed run blocked every violation (same results as the same seed on macOS). The image is about 950 MB, mostly clang and Bend.

The October 30, 2026 run of this tutorial (with the earlier TypeScript server) also governed a real Claude Code session through a committed hook; the hook protocol is unchanged.

## 1. Pick a host

Any Linux VM or server your developers can reach over a private network or VPN. 1 vCPU, 1 GB RAM and a few GB of disk are plenty for a small team; the event log grows with use.

The governor makes **no outbound connections** for its own work. Model API keys are only needed if you run the built-in benchmark scenarios on the server; your developers' Claude Code sessions use their own logins.

## 2. Create an access token

Everyone with this token can view the dashboard, edit laws and approve escalations, so treat it like a password.

```bash
openssl rand -hex 32
```

The server refuses to listen on a network address without one.

## 3a. Run with Docker Compose

```bash
git clone <this repository> swarmcontrol && cd swarmcontrol
export SWARMCONTROL_TOKEN=<the token>
docker compose -f deploy/docker-compose.yml up -d --build
```

The image builds the dashboard, installs the governor and Bend, and runs `swctl serve --host 0.0.0.0`. The laws and the event log live in the `governor-data` volume.

## 3b. Run with uv and systemd

On the host, as a service user (`governor`):

```bash
# Python 3.11+ and clang 14+ (from your distro, e.g. apt install clang), then:
curl -LsSf https://astral.sh/uv/install.sh | sh     # uv: installs to ~/.local/bin
uv tool install swarmcontrol
curl -fsSL https://bend-lang.com/install.sh | sh     # Bend, required: installs to ~/.bend and checks the archive's sha256
```

Create `/etc/swarmcontrol.env`, readable only by the service user:

```bash
HOST=0.0.0.0
PORT=8787
SWARMCONTROL_TOKEN=<the token>
SWARMCONTROL_DB=/var/lib/swarmcontrol/swarmcontrol.db
BEND_NO_TELEMETRY=1
```

And a systemd unit, `/etc/systemd/system/swarmcontrol.service`:

```ini
[Unit]
Description=SwarmControl
After=network.target

[Service]
User=governor
EnvironmentFile=/etc/swarmcontrol.env
Environment=PATH=/home/governor/.bend/bin:/home/governor/.local/bin:/usr/bin:/bin
ExecStart=/home/governor/.local/bin/swctl serve
Restart=always

[Install]
WantedBy=multi-user.target
```

Then start it:

```bash
sudo mkdir -p /var/lib/swarmcontrol && sudo chown governor /var/lib/swarmcontrol
sudo systemctl enable --now swarmcontrol
journalctl -u swarmcontrol -f      # expect: "core proofs: proof_checked · gates: loaded" and "API on http://0.0.0.0:8787"
```

## 4. Put TLS in front

The token travels in every request, so use HTTPS for anything beyond a private network. With [Caddy](https://caddyserver.com/), the whole config is:

```
governor.your-company.internal {
    reverse_proxy 127.0.0.1:8787
}
```

With nginx, also set `proxy_buffering off;`, because the dashboard streams live events. Once a proxy is in front, set `HOST=127.0.0.1` so the governor is only reachable through it.

## 5. Check it

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://governor.your-company.internal/api/status                                   # 401
curl -s -H "Authorization: Bearer $SWARMCONTROL_TOKEN" https://governor.your-company.internal/api/status | head -c 120; echo   # JSON
```

Open the dashboard in a browser. It asks for the token once and remembers it in that browser.

## 6. Connect developers (one command each)

The server serves its own connector, so developers don't need the governor repo. The exact command is on the dashboard's **Overview** page, under "Connect your Claude Code":

```bash
curl -fsSL https://governor.your-company.internal/connect.py | python3 - connect --server https://governor.your-company.internal --token <the token>
```

It needs only Python 3.8+ (no packages). Developers who installed the package can run `swctl connect …` instead.

Run it in a project folder to connect that project, or add `--global` to connect every Claude Code session on that machine. The command checks the server and token, then saves them in `~/.config/swarmcontrol/config.json` (readable only by that user). The token never goes into a repository.

**To cover a whole repository** instead of one laptop, a maintainer runs it once with `--team` and commits the result:

```bash
curl -fsSL https://governor.your-company.internal/connect.py | python3 - connect --team --server https://governor.your-company.internal --token <the token>
git add .claude/settings.json .claude/hooks/swarmcontrol-hook.py && git commit -m "Govern Claude Code sessions"
```

Teammates then run the plain `connect` command once to save the server and token. It sees the committed hooks and doesn't install them twice.

Per-session defaults can be saved at connect time (`--role`, `--agent`, `--done-check "npm test"`, `--observe`), or set per session with `SC_*` environment variables (see `claude-code.md`). `status` shows what's connected, and `disconnect` removes it.

> **Roll out in observe mode first.** For the first week, have everyone connect with `--observe` (or run with `SC_MODE=observe`). The dashboard then shows what would have been blocked, without blocking anything. Tune the laws, then switch to enforcing.

## 7. Write the team's laws

On the dashboard, under **Laws**:
- **Global laws** apply to every session. A fresh install already protects `test/`, `.ci/` and `package.json`, bounds retries at 3, and requires completion checks.
- **Role laws** apply by `SC_ROLE`, for example "implementers may not touch `/repo/infra/`".
- **Agent laws** apply to one `SC_AGENT`, for example "billing-bot may not touch `/repo/src/payments/`".

Changes take effect on each session's next action. No restart, and no developer has to update anything.

## 8. Operate it

- **Backups.** Everything is one SQLite file (`SWARMCONTROL_DB`). Take a consistent copy while it runs:

  ```bash
  sqlite3 /var/lib/swarmcontrol/swarmcontrol.db ".backup '/backups/governor-$(date +%F).db'"
  ```

- **Upgrades.** `uv tool upgrade swarmcontrol && sudo systemctl restart swarmcontrol`. The event log is append-only and carries over.
- **Health.** A `GET /` returning 200 means the process is up; `GET /api/status` with the token also reports proof and gate status.
- **If the governor goes down:** hooks fail closed, so governed sessions can't run tools until it's back. Developers can set `SC_FAIL_OPEN=1` to keep working unguarded during an outage. Decide which behavior your team wants before rollout.
- **Exports for training.** `GET /api/export?format=sft|preferences|trajectories` (with the token) writes the governed runs as JSONL. That's the data the training add-on uses.

## Limits today

- **One shared token, no per-user accounts, no roles:** anyone with the token can change laws. SSO, accounts and roles are on the roadmap. Until then, keep the token to the people who should manage agents, and keep the server on a private network.
- **One process with SQLite,** sized for a team, not a whole company. Postgres and multiple instances are on the roadmap.
- **Shell commands are parsed for the files they write; a write hidden inside a script isn't seen.** Pair the governor with a sandbox for hard guarantees.
- **Claude Code is the only native integration so far.** Other harnesses can call `POST /api/attach/check` (send the token as `Authorization: Bearer …`).
