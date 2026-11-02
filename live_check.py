"""First live call: verify the Meta Model API request shape before running the full suite.

    export MODEL_API_KEY=...            # in your own shell; never paste it into a chat or a file
    python3 live_check.py [model] [base_url]

Prints what came back (never the key). Stops at the first problem so you can see which assumption broke.
"""
import sys

from agent_gate.providers import MetaProvider
from refund_desk.domain import base_state
from refund_desk.llm_agent import LLMRefundAgent
from refund_desk.tools import make_toolbox


def main(model="muse-spark-1.3", base_url="https://api.meta.ai/v1"):
    p = MetaProvider(base_url=base_url, model=model)
    print("1/3 plain chat ...", repr(p._chat("Reply with the single word OK.")[:60]))
    print("2/3 paraphrase ...", p.paraphrase("O-1 arrived damaged, please refund it.", 2))
    tools = make_toolbox(base_state())
    reply = LLMRefundAgent(model=model, base_url=base_url).handle(tools, "alice", "Show order O-1")
    print("3/3 tool-calling agent ...", repr(reply[:120]), "| tool calls:", [c["name"] for c in tools.calls])
    if not tools.calls:
        print("WARNING: the model did not call get_order. Tool calling may use a different request shape.")


if __name__ == "__main__":
    main(*sys.argv[1:3])
