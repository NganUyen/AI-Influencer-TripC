# OpenClaw OAuth Setup & Usage Guide

**Last verified:** 2026-03-26 (UTC)

This document records the complete process of setting up **OpenAI Codex OAuth** (ChatGPT Plus/Pro subscription) for OpenClaw inside the `ai-influencer` Docker project. It also contains the final working usage instructions for the team.

## Problem Summary

- OpenClaw is running as container `ai-influencer-openclaw` (image: `ai-influencer-openclaw:latest`).
- Direct headless OAuth (`models auth login`) repeatedly hangs after pasting the redirect URL due to a known CLI bug in version 2026.3.14.
- Permission issues (`EACCES`) and deactivated workspace errors appeared during setup.
- Final solution: Authenticate on Windows 11 then copy the token into the container.

## Final Working Architecture (OpenClaw in this project)

```text
Windows 11 (Local Machine)
  → openclaw CLI (native)
  → OAuth login (browser opens automatically)
  → auth-profiles.json (contains openai-codex OAuth token)

VPS (Docker)
  → ai-influencer-openclaw container
  → /home/node/.openclaw/agents/main/agent/auth-profiles.json (copied token)
  → OpenClaw gateway (ws://127.0.0.1:18789)
  → TUI / Agent / Dashboard
```

## Step-by-Step Setup (Recommended for any new account)

### 1. Authenticate on Windows 11
```powershell
openclaw models auth login --provider openai-codex
```

Log in with the new personal ChatGPT Plus/Pro account (do not select Team workspace).

### 2. Copy token to VPS
```powershell
# Find the file
Get-ChildItem -Path "$env:USERPROFILE\.openclaw" -Recurse -Filter "auth-profiles.json"

# Copy to VPS
scp "$env:USERPROFILE\.openclaw\agents\main\agent\auth-profiles.json" root@ai-influencer:/tmp/auth-profiles.json
```

### 3. Apply token on VPS
```bash
cd /opt/ai-influencer/repo

# Remove old token (if any)
docker compose -f docker-compose.production.yml exec --user root openclaw rm -f /home/node/.openclaw/agents/main/agent/auth-profiles.json

# Copy new token
docker compose -f docker-compose.production.yml cp /tmp/auth-profiles.json openclaw:/home/node/.openclaw/agents/main/agent/auth-profiles.json

# Fix permissions
docker compose -f docker-compose.production.yml exec --user root openclaw sh -c '
  chown -R node:node /home/node/.openclaw
  chmod -R 755 /home/node/.openclaw
  chmod 644 /home/node/.openclaw/agents/main/agent/auth-profiles.json
'

# Restart
docker compose -f docker-compose.production.yml restart openclaw
```

### 4. Verify & Set Default Model
```bash
docker compose -f docker-compose.production.yml exec openclaw sh -c '
  cd /app && node openclaw.mjs models list
'

docker compose -f docker-compose.production.yml exec openclaw sh -c '
  cd /app && node openclaw.mjs models set openai-codex/gpt-5.4
'
```

## Final Usage Commands (Copy & Use)

### Chat continuously (Recommended - TUI)
```bash
docker compose -f docker-compose.production.yml exec openclaw sh -c '
  cd /app && node openclaw.mjs tui
'
```

Inside TUI:
- Type normally and press Enter
- Change model: `/model openai-codex/gpt-5.4`
- Exit: `/exit` or `Ctrl+C`

### Quick single message
```bash
docker compose -f docker-compose.production.yml exec openclaw sh -c '
  cd /app && node openclaw.mjs agent --message "Your message here" --agent main
'
```

### Open Web Dashboard (easiest for team)
```bash
docker compose -f docker-compose.production.yml exec openclaw sh -c '
  cd /app && node openclaw.mjs dashboard
'
```
Then open the printed URL + paste the gateway token in your browser.

## Troubleshooting (Common Issues)

| Issue | Fix |
|-------|-----|
| deactivated_workspace | Use personal account, not Team workspace |
| EACCES: permission denied | Run chown/chmod with `--user root` |
| OAuth command hangs | Auth on Windows → copy token |
| Still using Claude | Run `models set openai-codex/gpt-5.4` |

## Key Files & Locations
- Token file inside container: `/home/node/.openclaw/agents/main/agent/auth-profiles.json`
- Docker compose: `/opt/ai-influencer/repo/docker-compose.production.yml`
- OpenClaw container name: `ai-influencer-openclaw`
