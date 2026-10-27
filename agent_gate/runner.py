"""Loops 3 to 6: execute, triage, expand, gate."""
import copy
import time
import zlib

from .checks import evaluate
from .generate import VARY, expand, generate
from .spec import discover, load

BAD = ("agent_bug", "flaky")


def run_once(spec, case, factory, kwargs, seed):
    state = copy.deepcopy(case["fixtures"])  # fresh data for every run
    try:
        tools = load(spec["adapter"]["toolbox"])(state, case["tool_fail"])
        agent = factory(seed=seed, **kwargs)
    except Exception as e:  # harness or fixture problem, not an agent verdict
        return {"env_error": repr(e)}
    crashed, reply = False, ""
    try:
        reply = agent.handle(tools, case["user"], case["message"])
    except Exception as e:
        crashed, reply = True, f"CRASH: {e!r}"
    return {"reply": reply, "state": tools.state, "tool_calls": tools.calls, "crashed": crashed}


def run_case(spec, case, factory, kwargs, k, seed_base=0):
    runs = []
    for i in range(k):
        seed = zlib.crc32(f"{case['id']}:{seed_base + i}".encode())
        tr = run_once(spec, case, factory, kwargs, seed)
        if "env_error" in tr:
            runs.append({"ok": None, "env_error": tr["env_error"]})
            continue
        failed = [c["kind"] for c in case["checks"] if not evaluate(c, tr, case)]
        runs.append({"ok": not failed, "failed": failed, "reply": tr["reply"][:160],
                     "calls": [c["name"] for c in tr["tool_calls"]]})
    return runs


def triage(spec, case, factory, kwargs, k, rerun=5):
    """Loop 4: re-run anything that did not pass cleanly, then classify."""
    runs = run_case(spec, case, factory, kwargs, k)
    if any(r["ok"] is not True for r in runs):
        runs += run_case(spec, case, factory, kwargs, rerun, seed_base=k)
    fails = [r for r in runs if r["ok"] is False]
    envs = [r for r in runs if r["ok"] is None]
    if envs:
        status = "env_error"
    elif not fails:
        status = "pass"
    else:
        status = "agent_bug" if len(fails) == len(runs) else "flaky"
    return {"id": case["id"], "req": case["req"], "kind": case["kind"], "priority": case["priority"],
            "status": status, "runs": len(runs), "fails": len(fails),
            "evidence": fails[0] if fails else (envs[0] if envs else None)}


def gate(results, coverage, baseline=None):
    """Loop 6: SHIP, BLOCK or CONDITIONAL."""
    bad = [r for r in results if r["status"] in BAD]
    envs = [r for r in results if r["status"] == "env_error"]
    p0 = [r["id"] for r in bad if r["priority"] == "P0"]
    regress = []
    if baseline:
        was = {r["id"]: r["status"] for r in baseline["results"]}
        regress = [r["id"] for r in bad if was.get(r["id"]) == "pass"]
    reasons = []
    if p0:
        reasons.append(f"{len(p0)} P0 case(s) failing")
    if regress:
        reasons.append(f"{len(regress)} regression(s) against the baseline")
    if p0 or regress:
        verdict = "BLOCK"
    elif bad or envs or coverage < 1.0:
        verdict = "CONDITIONAL"
        reasons.append(f"{len(bad)} lower-priority failure(s), {len(envs)} environment error(s), coverage {coverage:.0%}")
    else:
        verdict = "SHIP"
    return {"verdict": verdict, "reasons": reasons, "regressions": regress}


def run_suite(spec, provider, factory, agent_kwargs=None, k=5, ref=None, baseline=None,
              changed_tools=None, rounds=2):
    t0, kw = time.time(), agent_kwargs or {}
    cdisc = discover(spec)
    cases, gen = generate(spec, provider)
    reqs = spec["requirements"]
    if changed_tools:
        cases = [c for c in cases if set(c["tools"]) & set(changed_tools)]
        reqs = [r for r in reqs if set(r.get("tools", [])) & set(changed_tools)]
    ref_bad = set()
    if ref:  # a case the trusted reference agent also fails is a bad test, not a bad agent
        rf, rkw = ref
        ref_bad = {c["id"] for c in cases if any(r["ok"] is False for r in run_case(spec, c, rf, rkw, 1))}
    by_id = {c["id"]: c for c in cases}
    results = [triage(spec, c, factory, kw, k) for c in cases]
    for r in results:
        if r["id"] in ref_bad:
            r["status"] = "test_bug"
    seen = {(c["req"], c["params"][VARY[c["kind"]]]) for c in cases if VARY.get(c["kind"])}
    frontier, expansion = [r for r in results if r["status"] in BAD], []
    for rnd in range(1, rounds + 1):
        new = []
        for r in frontier:
            new += expand(spec, by_id[r["id"]], provider, 3 + 2 * (rnd - 1), seen)
        if not new:
            break
        new_res = [triage(spec, c, factory, kw, k) for c in new]
        for c, r in zip(new, new_res):
            by_id[c["id"]] = c
            r["origin"] = f"expanded round {rnd}"
        results += new_res
        frontier = [r for r in new_res if r["status"] in BAD]
        expansion.append({"round": rnd, "new_cases": len(new), "new_failures": len(frontier)})
    coverage = len({c["req"] for c in cases}) / max(1, len(reqs))
    v = gate(results, coverage, baseline)
    n = len(results)
    return {
        "verdict": v, "coverage": coverage, "discover": cdisc, "generation": gen, "expansion": expansion,
        "metrics": {
            "cases": n, "runs": sum(r["runs"] for r in results),
            "agent_bug": sum(r["status"] == "agent_bug" for r in results),
            "flaky": sum(r["status"] == "flaky" for r in results),
            "test_bug": sum(r["status"] == "test_bug" for r in results),
            "env_error": sum(r["status"] == "env_error" for r in results),
            "flake_rate": round(sum(r["status"] == "flaky" for r in results) / max(1, n), 3),
            "llm_calls": getattr(provider, "llm_calls", 0), "seconds": round(time.time() - t0, 2),
        },
        "results": results,
    }
