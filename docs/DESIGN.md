# Design: Incident Response Agent

## Goal
Help on-call engineers at ShopFast (a fictional e-commerce platform) resolve production incidents faster by recalling how similar incidents were resolved before. The agent advises; the engineer applies the fix.

## Flow
1. Engineer submits an incident (service, severity, title, symptoms, error log).
2. Agent recalls the most similar past incidents from Hindsight memory, with source incident IDs.
3. Agent suggests a probable root cause, ordered fix steps, and steps to avoid (fixes that failed before).
4. Engineer applies the fix in their own systems, then records the outcome.
5. Agent retains the outcome in Hindsight. The next similar incident gets a better, cited answer.

## Acceptance criteria
- AC1: Submitting an incident returns the top similar past incidents from Hindsight with source references.
- AC2: The agent suggests a root cause and ordered fix steps based on recalled memory.
- AC3: The user records the outcome (resolved or not, actual root cause, steps, notes). The agent retains it in Hindsight.
- AC4: The demo shows improvement: a new incident type gets a generic answer first, and a specific, cited answer after its outcome is recorded.
- AC5: Secrets come only from environment variables. All inputs are validated. LLM errors are handled gracefully.

## Architecture
```
ShopFast mock app (FastAPI :8001)        Streamlit UI (:8501)
fault switches -> real error logs  --->  submit / suggestions / record outcome
                                                |
                                       agent/service.py
                                        |              |
                               agent/memory.py     agent/llm.py
                               Hindsight Cloud     Groq (openai/gpt-oss-120b)
                               bank: shopfast-incidents
```

| Module | Responsibility |
|---|---|
| `agent/config.py` | Load settings from env; fail fast when missing |
| `agent/models.py` | Pydantic models; all input validation; incident ID generation |
| `agent/log_normalizer.py` | Strip noise from logs before recall |
| `agent/memory.py` | Hindsight `create_bank`, `retain`, `recall` |
| `agent/llm.py` | Groq call, JSON output, retries, `LLMError` |
| `agent/service.py` | `analyze_incident`, `record_outcome` |
| `shopfast/` | Mock shop with fault switches |
| `ui/app.py` | Streamlit UI |
| `scripts/seed_memory.py` | Validate and load seed data into Hindsight |

## Hindsight memory usage
- One shared bank: `shopfast-incidents` (overridable per demo run, see below).
- Seeding: one `retain` per past incident, `document_id = incident_id`, metadata `service`, `severity`, `resolved`. Content text includes the incident ID so recalled facts can be cited.
- Analyze, similar incidents: `recall(query, types=["world"], include_chunks=True)`. Chunks provide source text for citations.
- Analyze, learned patterns: `recall(query, types=["observation"])`. Observations are patterns Hindsight consolidates across many incidents (for example "restarting pods never fixes pool exhaustion"). Shown in the UI as "What the agent has learned", so learning is visible, not only search.
- Recall query: `service + title + symptoms + normalize_log(error_log)`. `agent/log_normalizer.py` replaces timestamps, IPs, UUIDs, pod hashes, hex values and long numbers with placeholders, so the same error from different runs produces the same query.
- Learn: `record_outcome` calls `retain` with the new incident and its outcome, including failed attempts.

## Incident IDs
Generated automatically when not supplied: `INC-` + UTC timestamp `yymmddHHMMSS` + 2 random digits (for example `INC-26092814301207`). Seed incidents keep short IDs (`INC-1042`). Pattern: `^INC-\d{4,16}$`.

## Demo reset
The Hindsight SDK does not document a bank delete call, and deleting memory is irreversible. Instead, each demo run uses a fresh bank:
```
python -m scripts.seed_memory --bank-id shopfast-incidents-demo3
```
Then set `HINDSIGHT_BANK_ID=shopfast-incidents-demo3` in `.env`. Old banks stay untouched. Bank IDs must match `^[a-z0-9][a-z0-9-]{2,63}$`.

## Seed data
25 synthetic incidents in `data/seed_incidents.json`:

| Pattern | Incidents | Demo role |
|---|---|---|
| DB connection pool exhaustion | INC-1042, INC-1067, INC-1113 | strong recall |
| Redis timeout | INC-1051, INC-1088, INC-1129 | strong recall |
| Auth token expiry | INC-1075, INC-1098, INC-1141 | strong recall |
| Payment gateway timeout | none | learning moment |
| Other realistic incidents | 16 | noise; shows ranking |

## Trade-offs
- `recall` + Groq instead of Hindsight `reflect`: gives structured JSON output and explicit citations. `reflect` is a possible stretch goal.
- Sync SDK: Streamlit is synchronous; simpler code at demo scale.
- Fault switches held in memory: simple; state resets on restart.

## Security
- Secrets only in `.env` (git-ignored). `.env.example` has placeholders.
- Pydantic validation with length limits and patterns on all inputs.
- No `unsafe_allow_html` in Streamlit.
- ShopFast binds to `127.0.0.1`; `/admin/faults` is local-only.
- No SQL database in this build.

## Demo script (about 90 s)
1. ShopFast checkout works.
2. Enable `DB_POOL_EXHAUST`; checkout fails with 503 and a real log line.
3. Paste the log into the agent; it cites INC-1042 and others, suggests rollback plus pool size, warns that restarting pods failed before.
4. Disable the fault ("apply fix"); checkout works. Record the outcome.
5. Enable `PAYMENT_GATEWAY_TIMEOUT`; agent reports no similar incident and gives a generic answer. Record the real fix.
6. Trigger it again; agent now gives a specific answer citing the incident just recorded.

## Task split (4 people)
| Owner | Tasks |
|---|---|
| Memory owner | `agent/memory.py` (incl. `recall_learned_patterns`), `scripts/seed_memory.py`, Hindsight Cloud bank setup |
| Agent owner | `agent/llm.py`, `agent/service.py`, prompt, Groq error handling |
| ShopFast owner | `shopfast/app.py` endpoints and fault behavior |
| UI + demo owner | `ui/app.py` (incl. "What the agent has learned" panel), demo script, video, content deliverables |

## Future work
- Agent learns whether its own suggestions worked (retain suggestion plus result).
- ShopFast sends alerts to the agent automatically instead of copy-paste.
- Persist open incidents (SQLite) so a page refresh does not lose them.
- Fake memory and advisor classes for offline service tests.
- Eval script: recall hit rate before and after the feedback loop.
- Treat error logs as untrusted input in the LLM prompt (delimiters, data-only instruction).
