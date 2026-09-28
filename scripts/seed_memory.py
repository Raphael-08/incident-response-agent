"""Load data/seed_incidents.json, validate each record, and retain it into Hindsight.

Run:
  python -m scripts.seed_memory                                   # bank from HINDSIGHT_BANK_ID
  python -m scripts.seed_memory --bank-id shopfast-incidents-demo3  # fresh bank for a demo rerun

Demo reset: seed a new bank ID and set HINDSIGHT_BANK_ID to it. Old banks are left untouched,
so nothing is deleted and earlier runs stay available for comparison.
"""

import argparse
import json
from pathlib import Path

from agent.models import HistoricalIncident

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "seed_incidents.json"


def load_seed_incidents(path: Path = SEED_FILE) -> list[HistoricalIncident]:
    """Parse and validate the seed file. Raises pydantic.ValidationError on bad records."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [HistoricalIncident.model_validate(item) for item in raw]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Hindsight with ShopFast incident history.")
    parser.add_argument("--bank-id", help="Target bank ID (default: HINDSIGHT_BANK_ID from .env)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    incidents = load_seed_incidents()
    print(f"Validated {len(incidents)} seed incidents.")
    # TODO(memory owner): memory = IncidentMemory(load_settings(args.bank_id)); memory.ensure_bank();
    # then memory.retain_historical(incident) for each incident.


if __name__ == "__main__":
    main()
