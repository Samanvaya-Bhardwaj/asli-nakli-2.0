import json
from pathlib import Path
from typing import Any

VECTORS_PATH = Path(__file__).resolve().parents[3] / "docs" / "plan" / "test-vectors" / "codes.json"


def load() -> dict[str, Any]:
    with VECTORS_PATH.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


V = load()
