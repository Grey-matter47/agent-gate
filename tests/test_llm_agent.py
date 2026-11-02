import json
import unittest

from refund_desk.domain import base_state
from refund_desk.llm_agent import LLMRefundAgent
from refund_desk.tools import make_toolbox


def call(name, **args):
    return {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def scripted(*replies):
    seen = []

    def post(payload):
        seen.append(payload)
        return {"choices": [{"message": replies[min(len(seen), len(replies)) - 1]}]}
    post.seen = seen
    return post


class LLMAgentTests(unittest.TestCase):
    def test_tool_loop_executes_calls_and_returns_final_text(self):
        post = scripted({"content": "", "tool_calls": [call("issue_refund", order_id="O-1", amount=120)]},
                        {"content": "Refunded $120 on O-1."})
        tools = make_toolbox(base_state())
        reply = LLMRefundAgent(post=post).handle(tools, "alice", "O-1 arrived damaged, refund it")
        self.assertEqual(reply, "Refunded $120 on O-1.")
        self.assertEqual(tools.state["orders"]["O-1"]["refunded"], 120.0)
        self.assertIn("Verified user: alice (role: customer)", post.seen[0]["messages"][0]["content"])
        self.assertEqual(post.seen[1]["messages"][-1]["role"], "tool")

    def test_tool_error_is_returned_to_the_model_not_raised(self):
        post = scripted({"content": "", "tool_calls": [call("get_order", order_id="O-1")]},
                        {"content": "I couldn't retrieve O-1."})
        tools = make_toolbox(base_state(), fail_tool="get_order")
        LLMRefundAgent(post=post).handle(tools, "alice", "Show order O-1")
        self.assertIn("unavailable", post.seen[1]["messages"][-1]["content"])
        self.assertEqual(tools.calls[0]["error"], "get_order unavailable")

    def test_bad_arguments_and_runaway_loops_are_contained(self):
        looping = scripted({"content": "", "tool_calls": [{"id": "x", "function": {"name": "get_order", "arguments": "{bad"}}]})
        reply = LLMRefundAgent(post=looping, max_steps=3).handle(make_toolbox(base_state()), "alice", "hi")
        self.assertIn("couldn't finish", reply)
        self.assertEqual(len(looping.seen), 3)


if __name__ == "__main__":
    unittest.main()
