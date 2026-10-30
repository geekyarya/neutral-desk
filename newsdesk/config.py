import datetime as dt
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None):
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def episode_dir(date=None):
    date = date or dt.date.today().isoformat()
    d = ROOT / "output" / date
    d.mkdir(parents=True, exist_ok=True)
    return d
