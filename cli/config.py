from __future__ import annotations
import json, os
from typing import Dict, Any

def load_cfg(path: str | None) -> Dict[str, Any]:
    if not path:
        return {}
    if not os.path.exists(path):
        raise FileNotFoundError(f"Konfigurasjonsfil ikke funnet: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)