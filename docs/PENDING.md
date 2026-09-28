# Incident Response Agent: pending work

The code is ready for the demo. What remains is mostly the required submission material: the demo video, content deliverables for each member, and a rehearsed live demo. Owners are open: put your name next to an item when you take it.

## 1. Required for submission

| # | Item | Why it is required | Owner | Notes |
| --- | --- | --- | --- | --- |
| 1 | Demo video | Submission requirement | | Follow `docs/DEMO.md` (about 3 min). Record on a fresh demo bank. |
| 2 | Article, social post and video for each member | "All team members must complete" them, per the content guide | Each member | Check the official content guide for format. Mohan has drafts. |
| 3 | Live demo to judges | Submission requirement | | Rehearse `docs/DEMO.md` end to end at least twice. Have the backup lines ready. |
| 4 | Explanation of how Hindsight memory is used | Submission requirement | | Done in the README and the project overview; check it matches the final demo. |
| 5 | Clean, documented GitHub repo | Submission requirement | Sanjana | Merge PR #1 and PR #2; check the README top to bottom after merging. |

## 2. Parked: Claude Code recording (needs video)
A short screen recording (30-60 s) of Claude Code fixing ShopFast through the MCP server. It shows that any agent can use this memory, which is a strong innovation point.

1. Start ShopFast, then enable a fault: `curl -X POST http://127.0.0.1:8001/admin/faults/DB_POOL_EXHAUST`.
2. Open Claude Code in the repo folder. `.mcp.json` offers the `incident-memory` server; approve it.
3. Ask: "Detect the latest ShopFast incident and fix it, then write the postmortem."
4. Show it call `detect_incident`, ask before `run_action`, verify, then call `write_postmortem`.
5. Optional: ask "What are our team rules?" (`list_team_rules`) and "What fixed Redis timeouts before?" (`search_memory`).

## 3. Review and merge

| Item | Owner | Notes |
| --- | --- | --- |
| Review and merge [PR #1](https://github.com/Sanjanasree02/incident-response-agent/pull/1) | Sanjana | Learning from engineers, reflect postmortems, living runbook, learning curve, REST API, MCP server |
| Review and merge PR #2 | Sanjana | 4 more faults, repeated learning curve, SQLite persistence, team rules (directives) |
| Setup after merging | Everyone | `uv pip install -r requirements.txt`; `uv run python -m scripts.seed_memory` on your bank (adds team rules and the living runbook); `AGENT_API_KEY` in `.env` only for the REST API |

## 4. Checks before the demo

- [ ] Full UI walkthrough of `docs/DEMO.md` on a fresh demo bank (`--bank-id shopfast-incidents-demo1`)
- [ ] Add a team rule in the UI and check that the next suggestion names it and follows it
- [ ] Write a postmortem from the UI and download it
- [ ] Refresh the browser mid-incident and check that the incident and its action log come back
- [ ] Load the living runbook after a few incidents (Hindsight refreshes it after consolidation, which can take a minute)
- [ ] REST API smoke test with `curl` (detect, actions, postmortem)
- [ ] Confirm each member's Groq key has room on the free tier (8,000 tokens per minute) before the live demo

## 5. Nice to have, if time remains

| Idea | Value | Effort |
| --- | --- | --- |
| Deploy ShopFast and the UI (for example Render or Fly.io) so judges can click through | Live demo without a laptop | Medium |
| Alert webhook intake (Slack or PagerDuty style) instead of probing | Closer to a real on-call flow | Medium |
| "Ask memory" chat box backed by `reflect` | Shows free-form questions over incident history | Small |
| Per-service tags on memories, filtered in recall | Sharper recall as the bank grows | Small |
| Per-client banks and hashed API keys | Needed only if the API leaves localhost | Medium |
| Delete old test banks (`shopfast-curve-*`, `shopfast-probe-*`) in Hindsight Cloud | Tidy account, credits | Small |

## Known limits
- Groq free tier: 8,000 tokens per minute, about 2 analyses per minute. The agent waits when Groq asks and falls back to showing memory.
- Runbook actions are simulated in ShopFast; the evaluation harness approves every proposal (the UI never does).
- LLM results vary run to run; the learning curve therefore averages several runs.
