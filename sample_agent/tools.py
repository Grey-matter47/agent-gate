"""Fake tool backend for the sample ticket-triage agent. It does not know who is asking, so the
agent itself must enforce permissions."""
import copy

PRIORITIES = ["low", "medium", "high", "urgent"]


class ToolError(Exception):
    pass


class Toolbox:
    def __init__(self, state, fail_tool=None):
        self.state, self.fail_tool, self.calls = state, fail_tool, []

    def call(self, name, **args):
        rec = {"name": name, "args": args, "result": None, "error": None}
        self.calls.append(rec)
        try:
            if name == self.fail_tool:
                raise ToolError(f"{name} unavailable")
            rec["result"] = getattr(self, "_" + name)(**args)
            return rec["result"]
        except ToolError as e:
            rec["error"] = str(e)
            raise

    def _get_ticket(self, ticket_id):
        t = self.state["tickets"].get(ticket_id)
        if t is None:
            raise ToolError("not found")
        return copy.deepcopy(t)

    def _set_priority(self, ticket_id, priority):
        if priority not in PRIORITIES or ticket_id not in self.state["tickets"]:
            raise ToolError("invalid priority or ticket")
        self.state["tickets"][ticket_id]["priority"] = priority
        return priority


def make_toolbox(state, fail_tool=None):
    return Toolbox(state, fail_tool)
