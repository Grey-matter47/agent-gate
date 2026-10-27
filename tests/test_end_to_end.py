import unittest

from agent_gate.generate import generate
from agent_gate.providers import MockProvider
from agent_gate.runner import BAD, run_suite
from agent_gate.spec import discover, load, load_spec

SPEC = load_spec("sample_agent/spec.json")
FACTORY = load(SPEC["adapter"]["agent"])
EXPECTED = {"D1": "R1", "D2": "R2", "D3": "R3", "D4": "R4", "D5": "R5", "D6": "R3"}


def run(defects="", **kw):
    return run_suite(SPEC, MockProvider(), FACTORY, {"defects": defects}, k=5, **kw)


def flagged(rep):
    return {r["req"] for r in rep["results"] if r["status"] in BAD}


class GateTests(unittest.TestCase):
    def test_discover_covers_every_tool(self):
        self.assertEqual(discover(SPEC)["uncovered_tools"], [])

    def test_sanity_gate_drops_weak_checks_and_keeps_signal(self):
        cases, gen = generate(SPEC, MockProvider())
        self.assertTrue(gen["dropped_checks"], "weak checks should have been dropped")
        self.assertTrue(all(c["checks"] for c in cases))
        self.assertEqual({c["req"] for c in cases}, {r["id"] for r in SPEC["requirements"]})

    def test_fixed_agent_ships_with_no_false_blocks(self):
        rep = run()
        self.assertEqual(rep["verdict"]["verdict"], "SHIP")
        self.assertEqual(flagged(rep), set())
        self.assertEqual(rep["coverage"], 1.0)

    def test_each_seeded_defect_is_caught_in_isolation(self):
        for d, req in EXPECTED.items():
            rep = run(d)
            self.assertIn(req, flagged(rep), f"{d} not caught")
            self.assertNotEqual(rep["verdict"]["verdict"], "SHIP", d)

    def test_flaky_defect_is_classified_flaky(self):
        rep = run("D6")
        self.assertTrue(any(r["status"] == "flaky" for r in rep["results"]))

    def test_p1_only_defect_is_conditional(self):
        self.assertEqual(run("D3")["verdict"]["verdict"], "CONDITIONAL")

    def test_all_defects_block(self):
        self.assertEqual(run(",".join(EXPECTED))["verdict"]["verdict"], "BLOCK")

    def test_regression_against_baseline_blocks(self):
        rep = run("D3", baseline=run())
        self.assertEqual(rep["verdict"]["verdict"], "BLOCK")
        self.assertTrue(rep["verdict"]["regressions"])

    def test_cases_failing_on_reference_are_test_bugs(self):
        rep = run("D1", ref=(FACTORY, {"defects": "D1"}))
        r1 = [r for r in rep["results"] if r["req"] == "R1" and r["kind"] == "permission"]
        self.assertTrue(any(r["status"] == "test_bug" for r in r1))

    def test_changed_tool_selects_affected_cases_only(self):
        rep = run(changed_tools=["set_priority"])
        reqs = {r["req"] for r in rep["results"]}
        self.assertNotIn("R1", reqs)
        self.assertNotIn("R2", reqs)
        self.assertIn("R7", reqs)


if __name__ == "__main__":
    unittest.main()
