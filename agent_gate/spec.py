"""Loop 1: Discover. Load the agent spec and build a coverage map."""
import importlib
import json


def load_spec(path):
    with open(path) as f:
        return json.load(f)


def load(dotted):
    """Resolve 'package.module:name' to the object."""
    mod, name = dotted.split(":")
    return getattr(importlib.import_module(mod), name)


def discover(spec):
    reqs = spec["requirements"]
    covered = {t for r in reqs for t in r.get("tools", [])}
    return {
        "requirements": [r["id"] for r in reqs],
        "tools": list(spec["tools"]),
        "uncovered_tools": [t for t in spec["tools"] if t not in covered],
    }
