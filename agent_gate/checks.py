"""Deterministic checks (oracles). Each check is a dict: {"kind": ..., "args": {...}}.

A trace is what the harness records for one run of the agent under test:
{"reply": str, "state": dict, "tool_calls": [dict], "crashed": bool}
"""


def evaluate(check, tr, case):
    """Return True if the trace satisfies the check. Malformed traces count as a failure."""
    kind, a = check["kind"], check.get("args", {})
    try:
        reply = tr["reply"].lower()
        if kind == "reply_not_contains":
            return a["text"].lower() not in reply
        if kind == "reply_contains_any":
            return any(t.lower() in reply for t in a["texts"])
        if kind == "state_equals":
            return tr["state"]["tickets"][a["ticket"]][a["field"]] == a["value"]
        if kind == "state_unchanged":
            return tr["state"] == case["fixtures"]
        if kind == "no_crash":
            return not tr["crashed"]
        if kind == "tool_not_called":
            return all(c["name"] != a["name"] for c in tr["tool_calls"])
    except (KeyError, TypeError):
        return False
    raise ValueError(f"unknown check kind: {kind}")
