---
id: github-pulse
name: GitHub Pulse
version: 0.1.0
description: GitHub issues, pull requests, and repository metadata flow into reports and brain enrichment queues through ClawVisor.
category: sense
requires: [credential-gateway]
secrets:
  - name: CLAWVISOR_URL
    description: ClawVisor gateway URL (recommended credential route)
    where: https://clawvisor.com — create/connect an agent with GitHub enabled
  - name: CLAWVISOR_AGENT_TOKEN
    description: ClawVisor agent token
    where: https://clawvisor.com — agent settings, copy the agent token
health_checks:
  - type: any_of
    label: "ClawVisor availability"
    checks:
      - type: http
        url: "$CLAWVISOR_URL/health"
        label: "ClawVisor"
  - type: env_exists
    name: GITHUB_WORKSPACE_REPO
    label: "Target GitHub repository"
setup_time: 15 min
cost_estimate: "$0"
---

# GitHub Pulse: Repository Signals Into the Brain

GitHub Pulse is a deterministic collector for repository signals. It uses
ClawVisor as the credential boundary, then writes daily reports and heartbeat
data that agents can enrich into the brain.

## Architecture

```
GitHub connection in ClawVisor
  ↓ read-only standing/ephemeral task
GitHub Pulse collector
  ↓ Outputs:
  ├── reports/github-pulse/{YYYY-MM-DD}.md
  ├── cron/state/github-pulse/raw/*.json
  ├── ~/.gbrain/integrations/github-pulse/heartbeat.jsonl
  └── cron/state/brain-steward/enrichment-queue.jsonl
```

The collector is deliberately code-first:
- ClawVisor performs the credentialed GitHub reads.
- The collector stores raw responses for auditability.
- Markdown reports summarize open issues, pull requests, repo metadata, and
  deltas from the previous pulse.
- Agents later decide which people, companies, or product decisions deserve
  brain-page enrichment.

## Configuration

Required environment:

```bash
CLAWVISOR_URL=https://app.clawvisor.com
CLAWVISOR_AGENT_TOKEN=...
GITHUB_WORKSPACE_REPO=owner/repo
```

Optional environment:

```bash
GITHUB_SERVICE=github:owner          # defaults from GITHUB_WORKSPACE_REPO owner
GITHUB_PULSE_REPOS=owner/repo,owner/another-repo
GITHUB_CLAWVISOR_TASK_ID=...         # optional standing task; otherwise a short-lived read-only task is created per run
GITHUB_PULSE_MAX_RESULTS=100
GITHUB_PULSE_MAX_PAGES=3
```

## Collector Command

```bash
/data/.openclaw/cron/bin/github-pulse-collector.sh
```

The wrapper sources the OpenClaw environment, runs the Node collector, appends a
GBrain integration heartbeat, and queues the report for brain-steward enrichment.

## Safety

The default ClawVisor task only authorizes:
- `list_repos`
- `list_issues`
- `list_prs`

It does not authorize issue creation, comments, branch mutation, or repository
administration.
