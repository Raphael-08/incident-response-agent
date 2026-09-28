# Our incident agent learned a fix from an engineer, and then used it without being asked

*Draft. Adjust to the hackathon content guide before publishing.*

Every on-call engineer knows this feeling. Checkout is down, the error log looks familiar, and somewhere in a postmortem from six months ago is the exact fix. Nobody can find it in time.

For the Hindsight hackathon our team built an incident response agent for ShopFast, a mock e-commerce platform. The agent detects failures, recalls how similar incidents were fixed, proposes one safe runbook action, runs it only after a human approves, and checks that the shop is healthy again. Then it writes the outcome back to memory.

## Memory has to be more than search
The first version recalled past incidents with Hindsight `recall` and asked an LLM (Groq, `gpt-oss-120b`) for a root cause and fix. That already worked for incidents in memory. It failed quietly on one thing: when the agent had no memory of a failure and no confident idea, it proposed nothing. It recorded nothing either, so it never learned. `REDIS_TIMEOUT` stayed unsolved in every run.

My contribution started there.

**1. Learning from people.** Engineers can now run a different allow-listed action from the UI. It is verified and recorded exactly like the agent's own action, marked as the engineer's choice. The next time the same failure happens, the agent recalls that outcome and proposes the fix itself. It learned from a human, not from a prompt change.

**2. Postmortems with `reflect`.** After an incident, Hindsight `reflect` writes a blameless postmortem with a JSON schema: timeline, impact, what went wrong, action items, related past incidents. Because `reflect` reasons over the whole memory bank, it can say "this happened before in INC-1042". The postmortem is appended to the incident's own document, so every later recall brings the lessons back.

**3. A living runbook.** A Hindsight mental model with `refresh_after_consolidation` keeps a table of what worked and what failed for each failure type. Nobody maintains it. Hindsight rewrites it as outcomes arrive.

**4. Proof that it learns.** A learning-curve script replays every fault for several rounds on a fresh bank, once with memory and once with memory switched off. With memory, the share of incidents fixed by the agent's first action went from 50% in round 1 to 100% in rounds 2 and 3, and wrong actions on production fell from 4 to 0. With memory off it stayed at 50-75%, with 2-3 wrong actions every round.

**5. Memory for other agents.** An MCP server gives Claude Code or Cursor the same tools: detect, analyze, run action, postmortem, runbook, search memory. Writing tools are marked destructive, so the client asks the human first. A REST API does the same for any service.

## What I learned
- Memory without a write path from humans is half a memory. The most useful memories came from fixes the agent did not think of.
- Measure learning against a memory-off baseline. Otherwise "it got better" is a feeling, not a result.
- Keep the guardrails in code: an allow-list of actions, a human approval, and verification after every action. The LLM chooses; it never gets raw access.

Repo: <link>. Built with Hindsight by Vectorize and Groq.
