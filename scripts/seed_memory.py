"""Load data/seed_incidents.json, validate each record, and retain it into Hindsight.

Run: python -m scripts.seed_memory
"""

import json
from pathlib import Path

from agent.models import HistoricalIncident

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "seed_incidents.json"


def load_seed_incidents(path: Path = SEED_FILE) -> list[HistoricalIncident]:
    """Parse and validate the seed file. Raises pydantic.ValidationError on bad records."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [HistoricalIncident.model_validate(item) for item in raw]


def main() -> None:
    incidents = load_seed_incidents()
    print(f"Validated {len(incidents)} seed incidents.")
    # TODO(memory owner): memory = IncidentMemory(load_settings()); memory.ensure_bank();
    # then memory.retain_historical(incident) for each incident.


if __name__ == "__main__":
    main()
