"""Fake tool backend for the refund-desk agent. It does not know who is asking, so the agent
itself must enforce permissions and limits."""
import copy


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
        except TypeError as e:  # wrong arguments from the agent
            rec["error"] = f"bad arguments: {e}"
            raise ToolError(rec["error"])

    def _get_order(self, order_id):
        o = self.state["orders"].get(order_id)
        if o is None:
            raise ToolError("order not found")
        return copy.deepcopy(o)

    def _issue_refund(self, order_id, amount):
        o = self.state["orders"].get(order_id)
        if o is None:
            raise ToolError("order not found")
        amount = float(amount)
        if amount <= 0 or amount > o["amount"] - o["refunded"]:
            raise ToolError("refund amount out of range")
        o["refunded"] = round(o["refunded"] + amount, 2)
        return o["refunded"]


def make_toolbox(state, fail_tool=None):
    return Toolbox(state, fail_tool)
