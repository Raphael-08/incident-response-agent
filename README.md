# Incident Response Agent

An AI agent that remembers every past production incident at ShopFast (a fictional e-commerce platform) and uses that memory to suggest root causes and fixes for new incidents. Built on [Hindsight](https://hindsight.vectorize.io/) memory and Groq.

When production breaks, the agent:
1. Recalls similar past incidents from Hindsight memory and cites them.
2. Suggests a probable root cause, ordered fix steps, and fixes that failed before.
3. Learns from each outcome the engineer records, so the next similar incident gets a better answer.

See [docs/DESIGN.md](docs/DESIGN.md) for architecture, data model, and task split.

## How Hindsight memory is used
- **Seed:** 25 synthetic past incidents (`data/seed_incidents.json`) are stored with `retain` in the shared bank `shopfast-incidents`.
- **Recall:** each new incident is matched against memory with `recall`. Results include source chunks, so the agent cites incident IDs.
- **Learn:** recorded outcomes, including failed fix attempts, are stored with `retain`. A new failure type gets a generic answer the first time and a specific, cited answer after its outcome is recorded.

## Project structure
```
agent/      config, models, Hindsight memory wrapper, Groq advisor, service
shopfast/   mock e-commerce API with fault switches
ui/         Streamlit UI
data/       synthetic seed incidents
scripts/    seed script
tests/      unit tests
docs/       design document
```

## Setup
Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # then fill in real values
```

Get credentials:
- Hindsight Cloud: sign up at https://ui.hindsight.vectorize.io, apply promo code in billing, copy the API URL and key.
- Groq: create a key at https://console.groq.com.

Never commit `.env`.

## Run
```bash
python -m scripts.seed_memory                              # load seed incidents into Hindsight
uvicorn shopfast.app:app --host 127.0.0.1 --port 8001      # mock shop
streamlit run ui/app.py                                    # agent UI
pytest                                                     # tests
```

## Status
In progress. Config, models, log normalizer, fault switches, seed data, Hindsight memory wrapper and seed script are done and tested (91 tests passing). LLM advisor, service, ShopFast shop endpoints and UI still have TODOs for each owner; see the task split in `docs/DESIGN.md`.
