#!/usr/bin/env python3
"""Real HTTP, API-key-free integration test using unique synthetic demo IDs.

Does not wipe server state. Do not run on a bot during official evaluation.
"""
from __future__ import annotations

import argparse
import json
import time
import uuid

from common import ROOT, http
from dotenv import load_dotenv

NOW = "2026-04-26T10:00:00Z"


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--report", default="reports/http_smoke_test.json")
    args = parser.parse_args()
    checks = []
    start = time.perf_counter()

    def check(name: str, condition: bool):
        if not condition:
            raise AssertionError(name)
        checks.append({"check": name, "passed": True})
        print("PASS", name)

    status, health = http(args.base_url, "/v1/healthz")
    check("GET /v1/healthz", status == 200 and health.get("status") == "ok")
    status, meta = http(args.base_url, "/v1/metadata")
    check("GET /v1/metadata", status == 200 and "model" in meta)
    prefix = "smoke_" + uuid.uuid4().hex[:10]
    category = {"slug": prefix + "_restaurants", "peer_stats": {"avg_ctr": 0.03}, "voice": {"tone": "warm_busy_practical"}}
    merchant = {"merchant_id": prefix + "_merchant", "category_slug": category["slug"],
                "identity": {"name": "Demo Cafe", "owner_first_name": "Asha", "languages": ["en"], "verified": True},
                "performance": {"calls": 20, "views": 800, "window_days": 30, "ctr": 0.025},
                "offers": [{"id": "offer_1", "title": "Lunch Thali @ ₹149", "status": "active"}]}
    trigger = {"id": prefix + "_trigger", "merchant_id": merchant["merchant_id"], "scope": "merchant",
               "kind": "perf_dip", "urgency": 3, "suppression_key": prefix + "_dip",
               "payload": {"metric": "calls", "delta_pct": -0.4, "window": "7d"}, "expires_at": "2026-05-30T00:00:00Z"}
    for scope, key, payload in (("category", "slug", category), ("merchant", "merchant_id", merchant), ("trigger", "id", trigger)):
        envelope = {"scope": scope, "context_id": payload[key], "version": 2, "payload": payload, "delivered_at": NOW}
        status, ack = http(args.base_url, "/v1/context", envelope)
        check(f"context push {scope}", status == 200 and ack.get("accepted"))
        status, repeated = http(args.base_url, "/v1/context", envelope)
        check(f"idempotency {scope}", status == 200 and repeated == ack)
        envelope["version"] = 1
        status, stale = http(args.base_url, "/v1/context", envelope)
        check(f"stale version {scope}", status == 409 and stale.get("reason") == "stale_version")
    tick = {"now": NOW, "available_triggers": [trigger["id"]]}
    status, data = http(args.base_url, "/v1/tick", tick)
    check("tick returns a grounded action", status == 200 and len(data.get("actions", [])) == 1)
    action = data["actions"][0]
    check("action anchored in input", "40%" in action["body"] and "20 calls" in action["body"])
    check("first message uses a template", bool(action["template_name"]) and bool(action["template_params"]))
    status, data = http(args.base_url, "/v1/tick", tick)
    check("duplicate tick suppressed", status == 200 and data == {"actions": []})
    inbound = {"conversation_id": action["conversation_id"], "merchant_id": merchant["merchant_id"], "customer_id": None,
               "from_role": "merchant", "message": "Yes, send the draft", "turn_number": 2, "received_at": "2026-04-26T10:01:00Z"}
    status, response = http(args.base_url, "/v1/reply", inbound)
    check("acceptance produces draft", status == 200 and response.get("action") == "send" and "draft" in response.get("body", "").lower())
    status, repeated = http(args.base_url, "/v1/reply", inbound)
    check("reply replay returns cached response", status == 200 and response == repeated)
    inbound.update(message="STOP", turn_number=3, received_at="2026-04-26T10:02:00Z")
    status, stopped = http(args.base_url, "/v1/reply", inbound)
    check("STOP ends conversation", status == 200 and stopped.get("action") == "end")
    report = {"checks_passed": len(checks), "checks": checks, "elapsed_seconds": round(time.perf_counter() - start, 4),
              "sample_action": action, "sample_reply": response,
              "note": "Real local HTTP functional test. Not an LLM judge score, load benchmark or public deployment certification."}
    report_path = ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(checks)} checks passed. Report: {report_path}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"FAILED: {exc}") from exc
