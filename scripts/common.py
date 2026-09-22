from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def http(base: str, path: str, data: dict | None = None, method: str | None = None, token: str | None = None, timeout: float = 20) -> tuple[int, dict]:
    if not base.startswith(("http://", "https://")):
        raise ValueError("Base URL must start with http:// or https://")
    headers = {"Content-Type": "application/json"}
    token = os.getenv("API_TOKEN", "") if token is None else token
    if token:
        headers["Authorization"] = "Bearer " + token
    req = request.Request(base.rstrip("/") + path, data=json.dumps(data).encode() if data is not None else None,
                          headers=headers, method=method or ("POST" if data is not None else "GET"))
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.load(resp)
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())
    except error.URLError as exc:
        raise RuntimeError(f"Cannot reach {base}: {exc.reason}. Start the server and check your URL/port.") from exc


def load_expanded(root: Path | None = None) -> dict:
    root = root or ROOT / "expanded"
    result = {}
    for plural, key in (("categories", "slug"), ("merchants", "merchant_id"), ("customers", "customer_id"), ("triggers", "id")):
        result[plural] = {}
        for path in sorted((root / plural).glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            result[plural][value[key]] = value
        if not result[plural]:
            raise FileNotFoundError(f"No {plural} in {root}. Run the supplied dataset generator first.")
    result["pairs"] = json.loads((root / "test_pairs.json").read_text())["pairs"]
    return result
