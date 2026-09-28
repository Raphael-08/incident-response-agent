# Social post and video drafts

*Drafts. Adjust to the hackathon content guide.*

## LinkedIn / X post
Checkout is down at 2 a.m. The fix is in a postmortem from six months ago. Nobody can find it.

For the #Hindsight hackathon we built an incident response agent that remembers every incident, and gets better at fixing them:

- Recalls how similar incidents were fixed, and which fixes failed
- Proposes one allow-listed action, runs it only after a human approves, verifies the shop
- Learns from engineers too: when a person picks a different fix, the agent uses it next time on its own
- Writes blameless postmortems with Hindsight reflect, and keeps a living runbook that updates itself
- Works from Claude Code through an MCP server

With memory, fixes on the first action went from 50% to 100% by round 2, and wrong actions on production from 4 to 0. With memory off: 2-3 wrong actions every round.

Repo: <link> @Vectorize #AIAgents #SRE #MCP

## Video script (60-90 s)
1. (0-10 s) Storefront, checkout fails. Voice: "Checkout is down. Has this happened before?"
2. (10-25 s) Detect incident. Agent cites INC-1042, proposes a rollback, warns that restarting pods failed before. Approve. Healthy.
3. (25-45 s) New failure: Redis timeout. Agent has no memory of it. Engineer picks the fix. Trigger it again: the agent proposes that fix itself, citing the incident from a minute ago.
4. (45-60 s) Postmortem written by Hindsight reflect; living runbook table.
5. (60-75 s) Learning curve chart: with memory vs memory off.
6. (75-90 s) Claude Code: "Detect the latest ShopFast incident and fix it." Close: "Memory turns an on-call agent from a search box into a teammate."
