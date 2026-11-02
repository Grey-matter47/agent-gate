"""Loop 2: generate cases from the spec and validate every check before trusting it.

Each requirement kind has a builder. A builder returns the fixtures, the user turn, candidate
checks, and two synthetic traces: a known-good answer and a known-bad one. The sanity gate keeps a
check only if it passes the good trace and fails the bad trace. A check that cannot tell them apart
carries no signal and is dropped. A case with no surviving check is dropped.
"""
import importlib

from .checks import evaluate


def chk(kind, **args):
    return {"kind": kind, "args": args}


def trace(reply, state, calls=(), crashed=False):
    return {"reply": reply, "state": state, "tool_calls": list(calls), "crashed": crashed}


def _case(user, message, st, cands, good, bad, tool_fail=None):
    return dict(user=user, message=message, fixtures=st, tool_fail=tool_fail,
                candidates=cands, good=good, bad=bad)




def domain_of(spec):
    return importlib.import_module(spec["domain"])


def validate(case):
    kept, dropped = [], []
    for c in case["candidates"]:
        ok_good, ok_bad = evaluate(c, case["good"], case), evaluate(c, case["bad"], case)
        if ok_good and not ok_bad:
            kept.append(c)
        else:
            dropped.append({"check": c["kind"], "why": "fails on known-good" if not ok_good else "passes on known-bad"})
    return kept, dropped


def make_case(dom, req, params, cid):
    case = {"id": cid, "req": req["id"], "kind": req["kind"], "priority": dom.PRIORITY[req["kind"]],
            "params": params, "tools": req.get("tools", []), **dom.BUILDERS[req["kind"]](params)}
    case["checks"], dropped = validate(case)
    return case, dropped


def generate(spec, provider, variants=3):
    dom = domain_of(spec)
    cases, dropped_checks, dropped_cases = [], [], []
    for req in spec["requirements"]:
        n = 0
        for base in dom.PLANS[req["kind"]]:
            key = dom.VARY.get(req["kind"])
            plist = [base] + ([{**base, key: t} for t in provider.paraphrase(base[key], variants, offset=0)] if key else [])
            for p in plist:
                n += 1
                case, dropped = make_case(dom, req, p, f"{req['id']}-{n:02d}")
                dropped_checks += [{"case": case["id"], **d} for d in dropped]
                (cases if case["checks"] else dropped_cases).append(case if case["checks"] else case["id"])
    return cases, {"generated": len(cases) + len(dropped_cases), "kept": len(cases),
                   "dropped_checks": dropped_checks, "dropped_cases": dropped_cases}


def expand(spec, case, provider, offset, seen):
    """Loop 5: new variants of a failing case (same builder, so every check is re-validated)."""
    dom = domain_of(spec)
    key = dom.VARY.get(case["kind"])
    if not key:
        return []
    req = next(r for r in spec["requirements"] if r["id"] == case["req"])
    out = []
    for i, t in enumerate(provider.paraphrase(case["params"][key], 2, offset=offset), 1):
        if (case["req"], t) in seen:
            continue
        seen.add((case["req"], t))
        new, _ = make_case(dom, req, {**case["params"], key: t}, f"{case['id']}.x{offset}{i}")
        if new["checks"]:
            out.append(new)
    return out
