import argparse
import json
import os

from .providers import MetaProvider, MockProvider
from .runner import BAD, run_suite
from .spec import load, load_spec


def _kv(items):
    return dict(i.split("=", 1) for i in (items or []))


def summary(rep):
    v, m = rep["verdict"], rep["metrics"]
    lines = [f"VERDICT: {v['verdict']}  ({'; '.join(v['reasons']) or 'all checks passed'})",
             f"cases {m['cases']} | runs {m['runs']} | coverage {rep['coverage']:.0%} | "
             f"agent_bug {m['agent_bug']} | flaky {m['flaky']} | test_bug {m['test_bug']} | env_error {m['env_error']} | "
             f"llm_calls {m['llm_calls']} | {m['seconds']}s",
             f"checks dropped by the sanity gate: {len(rep['generation']['dropped_checks'])}; "
             f"cases dropped: {len(rep['generation']['dropped_cases'])}",
             "", "req   | cases | failing | classes"]
    for req in rep["discover"]["requirements"]:
        rs = [r for r in rep["results"] if r["req"] == req]
        if rs:
            bad = [r for r in rs if r["status"] in BAD]
            cls = sorted({r["status"] for r in bad})
            lines.append(f"{req:<5} | {len(rs):>5} | {len(bad):>7} | {', '.join(cls) or '-'}")
    for e in rep["expansion"]:
        lines.append(f"expansion round {e['round']}: {e['new_cases']} new cases, {e['new_failures']} new failures")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent_gate", description="Generate, run and gate evals for an agent.")
    ap.add_argument("--spec", default="refund_desk/spec.json")
    ap.add_argument("--agent", help="module:factory (default: spec adapter)")
    ap.add_argument("--agent-arg", action="append", help="key=value passed to the agent factory")
    ap.add_argument("--reference", help="module:factory of a trusted agent; cases it fails are test bugs")
    ap.add_argument("--reference-arg", action="append")
    ap.add_argument("--provider", choices=["mock", "meta"], default="mock")
    ap.add_argument("--k", type=int, default=5, help="repeats per case")
    ap.add_argument("--rounds", type=int, default=2, help="expansion rounds (0 = expansion off)")
    ap.add_argument("--req", action="append", help="only run this requirement id (repeatable), e.g. --req R6")
    ap.add_argument("--changed-tool", action="append", help="only run cases for requirements touching this tool")
    ap.add_argument("--baseline", help="report.json of the last approved version")
    ap.add_argument("--out", help="write the full report as JSON")
    ap.add_argument("--html", help="also write a standalone HTML report")
    ap.add_argument("--model", default="muse-spark-1.3", help="model id for --provider meta")
    ap.add_argument("--base-url", default="https://api.meta.ai/v1", help="OpenAI-style endpoint for --provider meta")
    a = ap.parse_args(argv)

    spec = load_spec(a.spec)
    factory = load(a.agent or spec["adapter"]["agent"])
    ref = (load(a.reference), _kv(a.reference_arg)) if a.reference else None
    base = json.load(open(a.baseline)) if a.baseline else None
    provider = MetaProvider(base_url=a.base_url, model=a.model) if a.provider == "meta" else MockProvider()
    rep = run_suite(spec, provider, factory, _kv(a.agent_arg), k=a.k, ref=ref, baseline=base,
                    changed_tools=a.changed_tool, rounds=a.rounds, only_reqs=a.req)
    print(summary(rep))
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump(rep, open(a.out, "w"), indent=2)
    if a.html:
        from .report import render
        open(a.html, "w").write(render(rep))
    return 0 if rep["verdict"]["verdict"] == "SHIP" else 1
