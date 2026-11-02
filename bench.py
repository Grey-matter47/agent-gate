"""Benchmark: does the gate catch each seeded defect, and does it leave the fixed agent alone?

Run:  python3 bench.py [spec.json]      (default: refund_desk/spec.json)
Writes reports/<agent>/bench.json and fixed.json and prints a markdown summary.
"""
import importlib
import json
import os
import sys

from agent_gate.providers import MockProvider
from agent_gate.runner import BAD, run_suite
from agent_gate.spec import load, load_spec


def main(path="refund_desk/spec.json"):
    spec = load_spec(path)
    factory = load(spec["adapter"]["agent"])
    expected = spec["seeded_defects"]
    descr = importlib.import_module(spec["adapter"]["agent"].split(":")[0]).DEFECTS

    def run(defects, **kw):
        return run_suite(spec, MockProvider(), factory, {"defects": defects}, k=5, **kw)

    fixed, rows = run(""), []
    for d, req in expected.items():
        rep = run(d)
        flagged = sorted({r["req"] for r in rep["results"] if r["status"] in BAD})
        rows.append({"defect": d, "what": descr[d], "expected_req": req, "caught": req in flagged,
                     "flagged_reqs": flagged, "verdict": rep["verdict"]["verdict"],
                     "classes": sorted({r["status"] for r in rep["results"] if r["status"] in BAD})})
    everything = run(",".join(expected))
    out = {"agent": spec["agent"],
           "fixed": {"verdict": fixed["verdict"]["verdict"], "metrics": fixed["metrics"],
                     "dropped_checks": len(fixed["generation"]["dropped_checks"]),
                     "dropped_cases": len(fixed["generation"]["dropped_cases"]), "coverage": fixed["coverage"]},
           "defects": rows, "caught": sum(r["caught"] for r in rows),
           "all_defects_verdict": everything["verdict"]["verdict"]}
    d = os.path.join("reports", spec["agent"])
    os.makedirs(d, exist_ok=True)
    json.dump(out, open(os.path.join(d, "bench.json"), "w"), indent=2)
    json.dump(fixed, open(os.path.join(d, "fixed.json"), "w"), indent=2)
    json.dump(everything, open(os.path.join(d, "buggy.json"), "w"), indent=2)

    m = fixed["metrics"]
    print(f"[{spec['agent']}] Fixed agent: {out['fixed']['verdict']}, failing cases {m['agent_bug'] + m['flaky']} of "
          f"{m['cases']}, coverage {fixed['coverage']:.0%}")
    print(f"Sanity gate on the fixed run: {out['fixed']['dropped_checks']} checks dropped, "
          f"{out['fixed']['dropped_cases']} cases dropped")
    print(f"Seeded defects caught: {out['caught']} of {len(rows)}; all together: {out['all_defects_verdict']}\n")
    print("| Defect | What it does | Expected requirement | Caught | Flagged requirements | Verdict | Classes |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['defect']} | {r['what']} | {r['expected_req']} | {'yes' if r['caught'] else 'NO'} | "
              f"{', '.join(r['flagged_reqs'])} | {r['verdict']} | {', '.join(r['classes'])} |")


if __name__ == "__main__":
    main(*sys.argv[1:2])
