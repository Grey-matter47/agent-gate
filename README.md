# Agent Gate

A QA agent for enterprise AI agents. Give it an agent's spec and it generates test cases, proves its own checks can fail, runs the cases, triages failures, and returns a release verdict: **SHIP**, **BLOCK** or **CONDITIONAL**.

Built for the Meta Global AI Developer Hackathon (Oct 26 to Nov 4, 2026), Indie track.

**Status:** working harness with two sample domains (support-ticket triage, refund desk), a rule-based reference agent with seeded defects for each, and an LLM-driven refund agent that runs on Muse Spark or any OpenAI-style endpoint. The Meta Model API path (`MetaProvider`, `LLMRefundAgent`) is written and tested against a scripted client but **has not been run against the live API yet**; `live_check.py` is the first-call check.

## Why

Enterprises will not ship agents they cannot test. In a June 2026 VentureBeat Pulse survey (157 enterprises, self-selected, so directional), about half had an agent pass internal checks and still cause a customer-facing problem, and only 5% fully trusted the automated evals behind release decisions. Agent Gate generates the tests and refuses to trust a check until it has shown that the check can tell a good answer from a bad one.

## The six loops

| # | Loop | Code | What it does today |
|---|---|---|---|
| 1 | Discover | `agent_gate/spec.py` | Reads the spec, lists requirements and tools, reports tools that no requirement covers |
| 2 | Generate and validate | `agent_gate/generate.py` + a domain module | Builds cases per requirement kind (permission, leak, rule, injection, tool failure, boundary, role gate). Each case proposes several checks. A check is kept only if it passes a known-good trace and fails a known-bad trace |
| 3 | Execute | `agent_gate/runner.py` | Fresh data for every run, tool-failure injection, k repeats per case (default 5), per-run seeds |
| 4 | Triage | `agent_gate/runner.py` | Re-runs anything that did not pass cleanly, then labels it `agent_bug` (fails every run), `flaky` (fails some), `test_bug` (a trusted reference agent also fails it) or `env_error` |
| 5 | Expand | `agent_gate/generate.py` | Creates new variants of failing cases through the same builders, so every new check is validated again |
| 6 | Gate | `agent_gate/runner.py` | P0 failure or any regression against a baseline gives BLOCK. Only lower-priority failures give CONDITIONAL. Otherwise SHIP. `--changed-tool` re-runs only the cases for requirements touching that tool |

A new domain is one module (`fixtures`, `BUILDERS`, `PLANS`, `VARY`, `PRIORITY`) plus a `spec.json`; see `refund_desk/`.

## Quick start (offline, standard library only)

```bash
python3 -m unittest discover -s tests -t .                       # 24 tests
python3 bench.py                                                 # refund-desk seeded-defect benchmark
python3 bench.py sample_agent/spec.json                          # ticket-triage benchmark
python3 -m agent_gate --agent-arg defects=D1,D7 --html out.html  # gate a buggy agent, write an HTML report
python3 -m agent_gate --baseline reports/refund-desk/fixed.json --agent-arg defects=D7
python3 -m agent_gate --changed-tool issue_refund
```

Tested on Python 3.13; other versions not checked.

## Model-swap gate

Can a cheaper or open-weight model replace the one in production? `agent_gate.compare` generates the cases once, runs them on a baseline agent and a candidate agent, and reports **SAFE TO SWAP**, **SWAP WITH CONDITIONS** (only lower-priority regressions) or **DO NOT SWAP** (any P0 regression), with a side-by-side HTML page.

```bash
python3 -m agent_gate.compare --a-arg defects= --b-arg defects=D7 --html swap.html      # offline demo
python3 -m agent_gate.compare --agent-a refund_desk.llm_agent:build --a-arg model=muse-spark-1.3 \
  --agent-b refund_desk.llm_agent:build --b-arg model=<open-weight id> --b-arg base_url=<endpoint> --b-arg key_env=<ENV> \
  --provider meta --k 3 --html swap.html --out swap.json                                # live
```

Offline, with rule-based agents standing in for models, an identical candidate is SAFE TO SWAP and a candidate with the missing approval limit (D7) is DO NOT SWAP with 4 P0 regressions on 42 shared cases. No live model has been compared yet.

## Live run on Muse Spark

```bash
export MODEL_API_KEY=...        # your own shell only. Never paste the key into a file or a chat.
python3 live_check.py           # 3 calls: plain chat, paraphrase, tool-calling agent
python3 -m agent_gate --provider meta --agent refund_desk.llm_agent:build --k 3 --out reports/live-spark.json --html reports/live-spark.html
```

`--provider meta` uses Muse Spark to write the message variants and injection payloads. `--agent refund_desk.llm_agent:build` makes the agent under test an LLM that decides its own tool calls. Use the standard model id `muse-spark-1.3`, not the `-contributor` variant, which lets Meta use your content for training.

For the open-weight run, point both at a partner endpoint, for example `--base-url <endpoint> --model <id> --agent-arg base_url=<endpoint> --agent-arg model=<id> --agent-arg key_env=<ENV_NAME>`.

## Results (offline, rule-based agents)

The same author wrote each agent, its defects and the generators, so these numbers show the harness works end to end. They do not show it generalises to an LLM-driven agent; that is what the live run is for.

| Domain | Fixed agent | Cases | Runs | Seeded defects caught alone | All defects together |
|---|---|---|---|---|---|
| refund-desk | SHIP, 0 failing | 42 | 210 | 7 of 7 | BLOCK |
| ticket-triage | SHIP, 0 failing | 38 | 190 | 6 of 6 | BLOCK |

Both fixed agents have 100% requirement coverage. The sanity gate drops 52 weak candidate checks per run, mostly trivial (`no_crash` cannot fail on synthetic traces). A flaky defect (intermittent skipped write) is labelled `flaky`, not `agent_bug`. Against a SHIP baseline, a new defect is reported as a regression and blocks. Full output is in `reports/`.

One defect shows a side effect: the refund-desk case-sensitivity bug (D3) is flagged on R3, R6 and R7 because the shouted variants of those cases also fall through to "tell me what is wrong". That is the defect's real blast radius, not a false alarm.

## Known limits

- Offline generation is templates plus string mutation (`MockProvider`). The LLM-written variants exist only behind `--provider meta`, which is untested live.
- The reference agents are rule-based. No LLM-driven agent has been gated yet.
- Expansion multiplies variants of known failures. It has not yet found a new defect class.
- Known-good and known-bad traces are authored by the case builders. They prove a check discriminates; they do not prove the check is right for a real agent. `--reference` (a trusted agent) is the partial answer.
- Checks are deterministic only (reply text, state, tool calls). There is no judge model for fuzzy output yet.
- Triage reports the failing check and the trace, not the first wrong step.
- `MetaProvider` and `LLMRefundAgent` assume an OpenAI-style chat-completions and tool-calling shape. Base URL, bearer auth and model ids come from Meta's models page; the request shape is unverified.

## Planned

- A second, independent judge from a different model family for rubric checks, calibrated against a few human labels.
- A regression store that replays past failures.
- First-wrong-step localisation in triage.
- Adapters so a real agent can be plugged in without writing a toolbox.
