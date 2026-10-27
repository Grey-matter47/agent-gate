"""Benchmark: does the gate catch each seeded defect, and does it leave the fixed agent alone?

Run:  python bench.py
Writes reports/bench.json and prints a markdown summary.
"""
import json
import os

from agent_gate.providers import MockProvider
from agent_gate.runner import BAD, run_suite
from agent_gate.spec import load, load_spec
from sample_agent.agent import DEFECTS

SPEC = load_spec("sample_agent/spec.json")
FACTORY = load(SPEC["adapter"]["agent"])
EXPECTED_REQ = {"D1": "R1", "D2": "R2", "D3": "R3", "D4": "R4", "D5": "R5", "D6": "R3"}


def run(defects, **kw):
    return run_suite(SPEC, MockProvider(), FACTORY, {"defects": defects}, k=5, **kw)


def main():
    fixed = run("")
    rows = []
    for d, req in EXPECTED_REQ.items():
        rep = run(d)
        flagged = sorted({r["req"] for r in rep["results"] if r["status"] in BAD})
        rows.append({"defect": d, "what": DEFECTS[d], "expected_req": req, "caught": req in flagged,
                     "flagged_reqs": flagged, "verdict": rep["verdict"]["verdict"],
                     "classes": sorted({r["status"] for r in rep["results"] if r["status"] in BAD})})
    everything = run(",".join(EXPECTED_REQ))
    out = {
        "fixed": {"verdict": fixed["verdict"]["verdict"], "metrics": fixed["metrics"],
                  "dropped_checks": len(fixed["generation"]["dropped_checks"]),
                  "dropped_cases": len(fixed["generation"]["dropped_cases"]), "coverage": fixed["coverage"]},
        "defects": rows,
        "caught": sum(r["caught"] for r in rows),
        "all_defects_verdict": everything["verdict"]["verdict"],
    }
    os.makedirs("reports", exist_ok=True)
    json.dump(out, open("reports/bench.json", "w"), indent=2)
    json.dump(fixed, open("reports/fixed.json", "w"), indent=2)

    print(f"Fixed agent: {out['fixed']['verdict']}, failing cases "
          f"{fixed['metrics']['agent_bug'] + fixed['metrics']['flaky']} of {fixed['metrics']['cases']}, "
          f"coverage {fixed['coverage']:.0%}")
    print(f"Sanity gate on the fixed run: {out['fixed']['dropped_checks']} checks dropped, "
          f"{out['fixed']['dropped_cases']} cases dropped")
    print(f"Seeded defects caught: {out['caught']} of {len(rows)}; all six together: {out['all_defects_verdict']}\n")
    print("| Defect | What it does | Expected requirement | Caught | Flagged requirements | Verdict | Classes |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['defect']} | {r['what']} | {r['expected_req']} | {'yes' if r['caught'] else 'NO'} | "
              f"{', '.join(r['flagged_reqs'])} | {r['verdict']} | {', '.join(r['classes'])} |")


if __name__ == "__main__":
    main()
