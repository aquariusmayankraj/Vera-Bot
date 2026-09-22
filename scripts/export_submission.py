#!/usr/bin/env python3
"""Export standalone compose results for the original 30 generated test pairs.

No LLM score is computed. Missing/unsafe facts are honestly marked suppressed.
There is no implicit wall clock in the standalone four-input compose contract.
"""
import argparse
import json

from common import ROOT, load_expanded
from vera.composer import compose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="submission.jsonl")
    args = parser.parse_args()
    data = load_expanded()
    outputs = []
    for pair in data["pairs"]:
        merchant = data["merchants"][pair["merchant_id"]]
        trigger = data["triggers"][pair["trigger_id"]]
        customer = data["customers"].get(pair.get("customer_id"))
        category = data["categories"][merchant["category_slug"]]
        result = compose(category, merchant, trigger, customer)
        assert result == compose(category, merchant, trigger, customer)
        outputs.append({"test_id": pair["test_id"], **result})
    path = ROOT / args.output
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in outputs) + "\n", encoding="utf-8")
    audit = {
        "total_pairs": len(outputs), "composed": sum(not x.get("suppressed", False) for x in outputs),
        "suppressed": sum(x.get("suppressed", False) for x in outputs), "determinism_verified": True,
        "llm_judge_run": False,
        "suppression_reasons": [{"test_id": x["test_id"], "reason": x["rationale"]} for x in outputs if x.get("suppressed")],
        "note": "Synthetic inputs only. Some expanded triggers contain placeholder:true and lack essential facts/consent. The HTTP API skips suppressed outputs; it never sends an empty body. Live evaluation also applies supplied simulated time, consent and cadence gates.",
    }
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/canonical_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(outputs)} rows: {audit['composed']} composed, {audit['suppressed']} explicitly suppressed. {path}")


if __name__ == "__main__":
    main()
