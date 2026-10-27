# Agent Gate

A QA agent for enterprise AI agents. Give it an agent's spec and it generates test cases, proves its own checks can fail, runs the cases, triages failures, and returns a release verdict: **SHIP**, **BLOCK** or **CONDITIONAL**.

Built for the Meta Global AI Developer Hackathon (Oct 26 to Nov 4, 2026), Indie track. Status: working harness on a deterministic sample agent. The Meta Model API provider is written but not yet run against the live API.

## Why

Enterprises will not ship agents they cannot test. In a June 2026 VentureBeat Pulse survey (157 enterprises, self-selected, so directional), about half had an agent pass internal checks and still cause a customer-facing problem, and only 5% fully trusted the automated evals behind release decisions. Agent Gate generates the tests and refuses to trust a check until it has shown that the check can tell a good answer from a bad one.

## The six loops (what exists today)

| # | Loop | Code | What it does today |
|---|---|---|---|
| 1 | Discover | `agent_gate/spec.py` | Reads the spec, lists requirements and tools, reports tools that no requirement covers |
| 2 | Generate and validate | `agent_gate/generate.py` | Builds cases per requirement kind (permission, leak, rule, injection, tool failure, boundary, role gate). Each case proposes several checks. A check is kept only if it passes a known-good trace and fails a known-bad trace |
| 3 | Execute | `agent_gate/runner.py` | Fresh data for every run, tool-failure injection, k repeats per case (default 5), per-run seeds so results are reproducible |
| 4 | Triage | `agent_gate/runner.py` | Re-runs anything that did not pass cleanly, then labels it `agent_bug` (fails every run), `flaky` (fails some), `test_bug` (a trusted reference agent also fails it) or `env_error` |
| 5 | Expand | `agent_gate/generate.py` | Creates new variants of failing cases through the same builders, so every new check is validated again |
| 6 | Gate | `agent_gate/runner.py` | P0 failure or any regression against a baseline report gives BLOCK. Only P1 or P2 failures give CONDITIONAL. Otherwise SHIP. `--changed-tool` re-runs only the cases for requirements touching that tool |

## Quick start

```bash
python3 -m unittest discover -s tests -t .      # 10 tests
python3 bench.py                                # seeded-defect benchmark
python3 -m agent_gate --agent-arg defects=D1,D3 # gate a buggy agent
python3 -m agent_gate --baseline reports/fixed.json --agent-arg defects=D3
python3 -m agent_gate --changed-tool set_priority
```

Standard library only. Tested on Python 3.13; other versions not checked.

## Results on the sample agent

The sample agent (`sample_agent/`) is a deterministic, rule-based support-ticket triage agent with two tools and six switchable defects. The same author wrote the agent, the defects and the generators, so these numbers show the harness works end to end. They do not show it generalises to a real LLM-driven agent.

Fixed agent: **SHIP**, 0 of 38 cases failing, 100% requirement coverage, 190 runs.

| Defect | What it does | Requirement | Caught alone | Verdict | Class |
|---|---|---|---|---|---|
| D1 | customer can read another customer's ticket | R1 | yes | BLOCK | agent_bug |
| D2 | customer sees the internal note | R2 | yes | BLOCK | agent_bug |
| D3 | outage keyword matched case-sensitively | R3 | yes | CONDITIONAL | agent_bug |
| D4 | obeys instructions written inside ticket text | R4 | yes | BLOCK | agent_bug |
| D5 | claims success when a tool call fails | R5 | yes | BLOCK | agent_bug |
| D6 | intermittently skips a write but says it was done | R3 (also flagged R5) | yes | BLOCK | flaky |

All six together: BLOCK. Full output is in `reports/`.

The sanity gate dropped 52 weak candidate checks per run: 34 `no_crash`, 12 `reply_contains_any`, 4 `reply_not_contains` and 2 `state_unchanged`. Most of those are trivial, because the synthetic bad traces never crash. A few are real catches, for example a reply check that would have passed an agent that claims success without writing anything.

## Known limits

- Case generation offline is templates plus string mutations (`MockProvider`). No LLM is used for it yet, so "dynamic" currently means spec-driven, not model-driven.
- The sample agent is rule-based. No LLM-driven agent has been tested, and the keyword matching in it would break on free-form paraphrases from a real model.
- Expansion currently multiplies variants of known failures. It confirms and sizes a defect but has not yet found a new defect class.
- Known-good and known-bad traces are authored by the case builders. They prove a check discriminates; they do not prove the check is right for a real agent. The `--reference` option (a trusted agent) is the partial answer.
- Triage reports the failing check and the trace, not the first wrong step.
- `MetaProvider` is untested against the live Meta Model API. The base URL, bearer auth and `muse-spark-1.3` come from Meta's models page. The chat-completions request shape is assumed.

## Planned

- Run `MetaProvider` live for case generation and as the model driving an LLM-based agent under test.
- A second, independent judge from a different model family for rubric checks on fuzzy output, calibrated against a few human labels.
- A regression store that replays past failures.
- First-wrong-step localisation in triage.
- Adapters so a real agent can be plugged in without writing a toolbox.

## Using the Meta Model API

Set `MODEL_API_KEY` in your shell and run with `--provider meta`. Never paste the key into a file or chat. Use the standard model id (`muse-spark-1.3`), not the `-contributor` variant, which lets Meta use your content for training.
