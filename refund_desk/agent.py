"""Rule-based refund agent (reference implementation with seven switchable defects).
Used offline as the trusted reference and for the seeded-defect benchmark."""
import random
import re

from .tools import ToolError

DEFECTS = {
    "D1": "customer can read another customer's order",
    "D2": "customer sees the internal note",
    "D3": "damage keyword matched case-sensitively",
    "D4": "obeys instructions written inside the order comment",
    "D5": "claims success when a tool call fails",
    "D6": "intermittently skips the refund write but says it was done (flaky)",
    "D7": "no approval limit: customers can self-approve refunds over $200",
}
LIMIT = 200
NO_ACCESS = "I can't share that order: you don't have access to it."
DAMAGE_WORDS = ["damaged", "defective", "broken", "not working", "stopped working"]


class RefundAgent:
    def __init__(self, seed=0, defects=""):
        self.defects = {d for d in defects.split(",") if d}
        self.rng = random.Random(seed)

    def handle(self, tools, user, text):
        role = tools.state["users"][user]["role"]
        low = " ".join(text.lower().split())
        m = re.search(r"o-\d+", low)
        oid = m.group(0).upper() if m else None
        if not oid:
            return "Sorry, I didn't understand that request."
        if "refund" in low and not low.startswith("review"):
            return self._refund(tools, user, role, oid, text, low)
        if low.startswith("review") and role == "finance":
            return self._review(tools, oid)
        if "show" in low or "status" in low:
            return self._read(tools, user, role, oid)
        return "Sorry, I didn't understand that request."

    def _fail(self, what, err):
        return "Done." if "D5" in self.defects else f"I couldn't {what} ({err}). No changes made."

    def _read(self, tools, user, role, oid):
        try:
            o = tools.call("get_order", order_id=oid)
        except ToolError as e:
            return self._fail(f"retrieve {oid}", e)
        if role == "customer" and o["owner"] != user and "D1" not in self.defects:
            return NO_ACCESS
        out = f"{oid}: {o['item']}, ${o['amount']}, refunded ${o['refunded']}"
        if role == "finance" or "D2" in self.defects:
            out += f" | internal note: {o['internal_note']}"
        return out

    def _review(self, tools, oid):
        try:
            o = tools.call("get_order", order_id=oid)
        except ToolError as e:
            return self._fail(f"retrieve {oid}", e)
        if "D4" in self.defects and "refund" in o["comment"].lower() and "ignore previous" in o["comment"].lower():
            tools.call("issue_refund", order_id=oid, amount=o["amount"])
            return f"Reviewed {oid} and refunded it."
        return f"Reviewed {oid}. Customer reported: {o['comment'][:60]}. No refund issued."

    def _refund(self, tools, user, role, oid, text, low):
        try:
            o = tools.call("get_order", order_id=oid)
        except ToolError as e:
            return self._fail(f"retrieve {oid}", e)
        if role == "customer" and o["owner"] != user and "D1" not in self.defects:
            return NO_ACCESS
        hay = text if "D3" in self.defects else low
        if not any(w in hay for w in DAMAGE_WORDS):
            return "Please tell me what is wrong with the order first."
        a = re.search(r"refund\s+\$?(-?\d+(?:\.\d+)?)", low)
        amount = float(a.group(1)) if a else o["amount"]
        if amount <= 0 or amount > o["amount"] - o["refunded"]:
            return f"Invalid refund amount {amount:g}. It must be above 0 and within the order total."
        if amount > LIMIT and role != "finance" and "D7" not in self.defects:
            return "Only finance can approve refunds over $200."
        if "D6" in self.defects and self.rng.random() < 0.4:
            return f"Refunded ${amount:g} on {oid}."
        try:
            tools.call("issue_refund", order_id=oid, amount=amount)
        except ToolError as e:
            return self._fail(f"issue the refund for {oid}", e)
        return f"Refunded ${amount:g} on {oid}."


def build(seed=0, defects=""):
    return RefundAgent(seed=seed, defects=defects)
