"""Render a report.json as one self-contained HTML page (no network, no dependencies)."""
import html
import json
import sys

COLORS = {"SHIP": "#1a7f37", "CONDITIONAL": "#b26a00", "BLOCK": "#c62828"}


def render(rep, title="Agent Gate report"):
    v, m = rep["verdict"], rep["metrics"]
    e = html.escape
    rows = "".join(
        f"<tr class='{r['status']}'><td>{e(r['id'])}</td><td>{e(r['req'])}</td><td>{e(r['kind'])}</td>"
        f"<td>{e(r['priority'])}</td><td>{e(r['status'])}</td><td>{r['fails']}/{r['runs']}</td>"
        f"<td>{e((r['evidence'] or {}).get('reply', '') if r['evidence'] else '')}</td></tr>"
        for r in sorted(rep["results"], key=lambda r: (r["status"] == "pass", r["id"])))
    dropped = rep["generation"]["dropped_checks"]
    return f"""<!doctype html><meta charset=utf-8><title>{e(title)}</title>
<style>body{{font:15px system-ui;margin:2rem auto;max-width:1000px;padding:0 1rem;color:#1b1f23}}
.v{{display:inline-block;padding:.4rem 1rem;border-radius:6px;color:#fff;font-size:1.6rem;font-weight:700;background:{COLORS[v['verdict']]}}}
table{{border-collapse:collapse;width:100%;margin-top:1rem}}td,th{{border-bottom:1px solid #ddd;padding:.3rem .5rem;text-align:left;font-size:13px}}
tr.agent_bug td:nth-child(5),tr.flaky td:nth-child(5){{color:#c62828;font-weight:600}}tr.pass{{color:#666}}</style>
<h1>{e(title)}</h1><p><span class=v>{v['verdict']}</span> {e('; '.join(v['reasons']) or 'all checks passed')}</p>
<p>{m['cases']} cases, {m['runs']} runs, coverage {rep['coverage']:.0%}, agent_bug {m['agent_bug']}, flaky {m['flaky']},
test_bug {m['test_bug']}, env_error {m['env_error']}, LLM calls {m['llm_calls']}, {m['seconds']}s.</p>
<p>The sanity gate dropped {len(dropped)} weak checks before running anything (a check is kept only if it passes a
known-good trace and fails a known-bad one).</p>
<table><tr><th>Case<th>Req<th>Kind<th>Pri<th>Status<th>Fails<th>First failing reply</tr>{rows}</table>"""


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    open(dst, "w").write(render(json.load(open(src))))
