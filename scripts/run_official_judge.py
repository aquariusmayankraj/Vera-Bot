#!/usr/bin/env python3
"""Run the supplied, unchanged official scorer with an explicit simulation clock.

Optional LLM scoring needs your own provider/key/model. --reset is destructive.
Only wrapper adaptations: env configuration, explicit clock, complete seed
merchant/customer warmup, optional Bearer transport, and optional teardown. Original scoring code is intact.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from common import ROOT, http
from dotenv import load_dotenv


def load_official():
    path = ROOT / "challenge_reference/judge_simulator.py"
    spec = importlib.util.spec_from_file_location("official_vera_judge", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the supplied judge simulator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--now", default="2026-04-26T10:00:00Z")
    parser.add_argument("--scenario", default="full_evaluation", choices=["warmup", "phase2_short", "auto_reply_hell", "intent_transition", "hostile", "all", "full_evaluation"])
    parser.add_argument("--reset", action="store_true", help="Explicitly wipe this test bot's stored state before running; never use during official evaluation")
    args = parser.parse_args()
    provider = os.getenv("JUDGE_LLM_PROVIDER", "openai")
    key = os.getenv("JUDGE_LLM_API_KEY", "")
    model = os.getenv("JUDGE_LLM_MODEL", "")
    if provider != "ollama" and not key:
        parser.error("Set JUDGE_LLM_API_KEY in .env. The bot itself needs no key; this is the optional scorer.")
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
    if now.tzinfo is None:
        parser.error("--now needs an explicit UTC offset or Z")
    if args.reset:
        status, _ = http(args.base_url, "/v1/teardown", method="POST", token=os.getenv("TEARDOWN_TOKEN") or os.getenv("API_TOKEN", ""))
        if status != 200:
            raise RuntimeError(f"Teardown failed: HTTP {status}")
    original = load_official()
    original.BOT_URL, original.LLM_PROVIDER, original.LLM_API_KEY, original.LLM_MODEL = args.base_url, provider, key, model
    original.OLLAMA_URL = os.getenv("JUDGE_OLLAMA_URL", "http://localhost:11434")

    class SimulationClient(original.BotClient):
        def __init__(self, base_url):
            super().__init__(base_url)
            self.simulated_now = now

        def _request(self, method, path, timeout=30, body_dict=None):
            started = time.perf_counter()
            try:
                status, payload = http(self.base_url, path, body_dict, method=method, timeout=timeout)
                elapsed = (time.perf_counter() - started) * 1000
                if status >= 400:
                    return None, f"HTTP {status}: {payload.get('reason', 'request_failed')}", elapsed
                return payload, None, elapsed
            except (RuntimeError, ValueError) as exc:
                return None, str(exc), (time.perf_counter() - started) * 1000

        def push_context(self, scope, cid, version, payload):
            return self._request("POST", "/v1/context", 10, {"scope": scope, "context_id": cid, "version": version,
                "payload": payload, "delivered_at": self.simulated_now.isoformat()})

        def tick(self, triggers):
            result = self._request("POST", "/v1/tick", 15, {"now": self.simulated_now.isoformat(), "available_triggers": triggers})
            self.simulated_now += timedelta(minutes=5)
            return result

        def reply(self, conv_id, merchant_id, message, turn):
            self.simulated_now += timedelta(seconds=1)
            return self._request("POST", "/v1/reply", 15, {"conversation_id": conv_id, "merchant_id": merchant_id,
                "customer_id": None, "from_role": "merchant", "message": message, "turn_number": turn,
                "received_at": self.simulated_now.isoformat()})

    original.BotClient = SimulationClient

    class CompatibleSimulator(original.JudgeSimulator):
        def _warmup(self):
            if not super()._warmup():
                return False
            for merchant in self.dataset.merchants.values():
                self.client.push_context("merchant", merchant["merchant_id"], 1, merchant)
            for customer in self.dataset.customers.values():
                self.client.push_context("customer", customer["customer_id"], 1, customer)
            return True

    llm = original.create_provider()
    print("Original scoring logic; explicit simulated time; all supplied seed customers loaded.")
    print("Some triggers correctly produce no action due to expiry, future due dates, missing facts, consent or cadence.")
    print("The original simulator scores seed-trigger batches, not the generated 30-pair submission file.")
    success = CompatibleSimulator(llm).run(args.scenario)
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
