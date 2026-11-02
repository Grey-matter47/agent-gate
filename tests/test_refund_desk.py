import unittest

from agent_gate.providers import MockProvider
from agent_gate.runner import BAD, run_suite
from agent_gate.spec import discover, load, load_spec

SPEC = load_spec("refund_desk/spec.json")
FACTORY = load(SPEC["adapter"]["agent"])
EXPECTED = SPEC["seeded_defects"]


def run(defects="", **kw):
    return run_suite(SPEC, MockProvider(), FACTORY, {"defects": defects}, k=5, **kw)


def flagged(rep):
    return {r["req"] for r in rep["results"] if r["status"] in BAD}


class RefundDeskTests(unittest.TestCase):
    def test_every_tool_is_covered(self):
        self.assertEqual(discover(SPEC)["uncovered_tools"], [])

    def test_fixed_agent_ships(self):
        rep = run()
        self.assertEqual(rep["verdict"]["verdict"], "SHIP")
        self.assertEqual(flagged(rep), set())
        self.assertEqual(rep["coverage"], 1.0)

    def test_each_seeded_defect_is_caught_in_isolation(self):
        for d, req in EXPECTED.items():
            rep = run(d)
            self.assertIn(req, flagged(rep), f"{d} not caught")
            self.assertNotEqual(rep["verdict"]["verdict"], "SHIP", d)

    def test_flaky_refund_skip_is_classified_flaky(self):
        self.assertTrue(any(r["status"] == "flaky" for r in run("D6")["results"]))

    def test_regression_against_baseline_blocks(self):
        rep = run("D7", baseline=run())
        self.assertEqual(rep["verdict"]["verdict"], "BLOCK")
        self.assertTrue(rep["verdict"]["regressions"])

    def test_changed_tool_selects_only_affected_cases(self):
        reqs = {r["req"] for r in run(changed_tools=["issue_refund"])["results"]}
        self.assertNotIn("R1", reqs)
        self.assertIn("R7", reqs)

    def test_html_report_renders(self):
        from agent_gate.report import render
        page = render(run("D1"))
        self.assertIn("BLOCK", page)
        self.assertIn("R1-", page)


if __name__ == "__main__":
    unittest.main()
