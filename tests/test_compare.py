import unittest

from agent_gate.compare import compare, render
from agent_gate.providers import MockProvider
from agent_gate.spec import load, load_spec

SPEC = load_spec("refund_desk/spec.json")
F = load(SPEC["adapter"]["agent"])


def cmp(b_defects):
    return compare(SPEC, MockProvider(), F, {"defects": ""}, F, {"defects": b_defects}, k=3)


class CompareTests(unittest.TestCase):
    def test_identical_agents_are_safe_to_swap(self):
        c = cmp("")
        self.assertEqual(c["swap"], "SAFE TO SWAP")
        self.assertEqual(c["regressions"], [])

    def test_candidate_with_p0_defect_is_blocked(self):
        c = cmp("D7")
        self.assertEqual(c["swap"], "DO NOT SWAP")
        self.assertTrue(c["regressions"])
        self.assertIn("DO NOT SWAP", render(c))

    def test_candidate_that_fixes_baseline_defects_is_not_a_regression(self):
        c = compare(SPEC, MockProvider(), F, {"defects": "D7"}, F, {"defects": ""}, k=3)
        self.assertEqual(c["swap"], "SAFE TO SWAP")
        self.assertTrue(c["fixed"])

    def test_both_sides_run_the_same_cases(self):
        c = cmp("D1")
        self.assertEqual(c["a"]["metrics"]["cases"], c["b"]["metrics"]["cases"])


if __name__ == "__main__":
    unittest.main()
