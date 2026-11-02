"""Model-swap gate: run the identical cases on a baseline agent and a candidate agent and say whether
the candidate is safe to swap in. Example: Muse Spark (baseline) vs Muse Spark Open (candidate).

    python3 -m agent_gate.compare --agent-a refund_desk.llm_agent:build --a-arg model=muse-spark-1.3 \
        --agent-b refund_desk.llm_agent:build --b-arg model=<id> --b-arg base_url=<endpoint> --b-arg key_env=<ENV> \
        --provider meta --html reports/swap.html --out reports/swap.json

Cases are generated once and reused for both agents, so any difference comes from the agent, not the tests.
No expansion rounds: they would create different cases for each side.
"""
import argparse
import html
import json
import os

from .generate import generate
from .providers import MetaProvider, MockProvider
from .runner import BAD, run_suite
from .spec import load, load_spec

SWAP = {"SAFE TO SWAP": "#1a7f37", "SWAP WITH CONDITIONS": "#b26a00", "DO NOT SWAP": "#c62828"}


def compare(spec, provider, fa, ka, fb, kb, k=5):
    pre = generate(spec, provider)
    a = run_suite(spec, provider, fa, ka, k=k, rounds=0, prebuilt=pre)
    b = run_suite(spec, provider, fb, kb, k=k, rounds=0, prebuilt=pre, baseline=a)
    sa = {r["id"]: r for r in a["results"]}
    rows, reg, fixed = [], [], []
    for r in b["results"]:
        was, now = sa[r["id"]], r
        a_bad, b_bad = was["status"] in BAD, now["status"] in BAD
        delta = "regression" if (b_bad and not a_bad) else "fixed" if (a_bad and not b_bad) else \
                "both fail" if (a_bad and b_bad) else "same"
        if delta == "regression":
            reg.append(r)
        if delta == "fixed":
            fixed.append(r)
        rows.append({"id": r["id"], "req": r["req"], "kind": r["kind"], "priority": r["priority"],
                     "a": was["status"], "b": now["status"], "delta": delta,
                     "b_evidence": (now["evidence"] or {}).get("reply", "") if now["evidence"] else ""})
    p0 = [r["id"] for r in reg if r["priority"] == "P0"]
    if p0:
        swap, why = "DO NOT SWAP", f"{len(p0)} P0 regression(s)"
    elif reg:
        swap, why = "SWAP WITH CONDITIONS", f"{len(reg)} lower-priority regression(s)"
    else:
        swap, why = "SAFE TO SWAP", "no case that passed on the baseline fails on the candidate"
    return {"swap": swap, "why": why, "regressions": [r["id"] for r in reg], "fixed": [r["id"] for r in fixed],
            "cases": len(rows), "a": {"verdict": a["verdict"], "metrics": a["metrics"]},
            "b": {"verdict": b["verdict"], "metrics": b["metrics"]}, "rows": rows}


def render(c, name_a="Baseline", name_b="Candidate"):
    e = html.escape
    tone = {"regression": "#c62828", "fixed": "#1a7f37", "both fail": "#b26a00", "same": "#666"}
    rows = "".join(
        f"<tr><td>{e(r['id'])}</td><td>{e(r['req'])}</td><td>{e(r['kind'])}</td><td>{e(r['priority'])}</td>"
        f"<td>{e(r['a'])}</td><td>{e(r['b'])}</td><td style='color:{tone[r['delta']]};font-weight:600'>{e(r['delta'])}</td>"
        f"<td>{e(r['b_evidence'][:90])}</td></tr>"
        for r in sorted(c["rows"], key=lambda r: (r["delta"] == "same", r["id"])))
    ma, mb = c["a"]["metrics"], c["b"]["metrics"]
    return f"""<!doctype html><meta charset=utf-8><title>Model-swap gate</title>
<style>body{{font:15px system-ui;margin:2rem auto;max-width:1050px;padding:0 1rem;color:#1b1f23}}
.v{{display:inline-block;padding:.4rem 1rem;border-radius:6px;color:#fff;font-size:1.6rem;font-weight:700;background:{SWAP[c['swap']]}}}
.cols{{display:flex;gap:1rem;margin:1rem 0}}.card{{flex:1;border:1px solid #ddd;border-radius:8px;padding:.8rem 1rem}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:.3rem .5rem;text-align:left;font-size:13px}}</style>
<h1>Model-swap gate</h1><p><span class=v>{c['swap']}</span> {e(c['why'])}</p>
<div class=cols><div class=card><b>{e(name_a)}</b> (baseline)<br>{c['a']['verdict']['verdict']}: {ma['agent_bug']} failing, {ma['flaky']} flaky of {ma['cases']} cases</div>
<div class=card><b>{e(name_b)}</b> (candidate)<br>{c['b']['verdict']['verdict']}: {mb['agent_bug']} failing, {mb['flaky']} flaky of {mb['cases']} cases</div></div>
<p>Same {c['cases']} cases for both. Regressions: {len(c['regressions'])}. Fixed by the candidate: {len(c['fixed'])}.</p>
<table><tr><th>Case<th>Req<th>Kind<th>Pri<th>{e(name_a)}<th>{e(name_b)}<th>Change<th>Candidate's first failing reply</tr>{rows}</table>"""


def _kv(items):
    return dict(i.split("=", 1) for i in (items or []))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent_gate.compare", description="Model-swap gate")
    ap.add_argument("--spec", default="refund_desk/spec.json")
    ap.add_argument("--agent-a"); ap.add_argument("--a-arg", action="append"); ap.add_argument("--name-a", default="Baseline")
    ap.add_argument("--agent-b"); ap.add_argument("--b-arg", action="append"); ap.add_argument("--name-b", default="Candidate")
    ap.add_argument("--provider", choices=["mock", "meta"], default="mock")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--out"); ap.add_argument("--html")
    a = ap.parse_args(argv)
    spec = load_spec(a.spec)
    fa = load(a.agent_a or spec["adapter"]["agent"])
    fb = load(a.agent_b or spec["adapter"]["agent"])
    provider = MetaProvider() if a.provider == "meta" else MockProvider()
    c = compare(spec, provider, fa, _kv(a.a_arg), fb, _kv(a.b_arg), k=a.k)
    print(f"{c['swap']}: {c['why']}\nbaseline {c['a']['verdict']['verdict']} | candidate {c['b']['verdict']['verdict']} | "
          f"regressions {len(c['regressions'])} | fixed {len(c['fixed'])} | cases {c['cases']}")
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump(c, open(a.out, "w"), indent=2)
    if a.html:
        open(a.html, "w").write(render(c, a.name_a, a.name_b))
    return 0 if c["swap"] == "SAFE TO SWAP" else 1


if __name__ == "__main__":
    raise SystemExit(main())
