"""Model providers used for case generation.

MockProvider is deterministic and offline (used for tests and the benchmark).
MetaProvider calls the Meta Model API. It has NOT been exercised against the live API yet:
the base URL, bearer auth and the model id come from Meta's models page, but the exact
chat-completions request/response shape is assumed to be OpenAI-style and must be checked
on the first live call.
"""
import json
import os
import urllib.request


def post_chat(base_url, key, payload, timeout=90):
    """POST an OpenAI-style chat-completions request. Shared by the case generator and LLM agents."""
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions", data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class MockProvider:
    name = "mock"
    llm_calls = 0

    _T = [
        lambda t: t[:1].upper() + t[1:],
        lambda t: t.upper(),
        lambda t: t + ".",
        lambda t: t.lower(),
        lambda t: "  " + t,
        lambda t: t + " !!",
        lambda t: t.replace(" ", "  "),
        lambda t: "Hi, " + t[:1].lower() + t[1:],
    ]

    def paraphrase(self, text, n, offset=0):
        out = []
        for f in self._T[offset:]:
            v = f(text)
            if v != text and v not in out:
                out.append(v)
            if len(out) == n:
                break
        return out


class MetaProvider:
    name = "meta"

    def __init__(self, base_url="https://api.meta.ai/v1", model="muse-spark-1.3", key_env="MODEL_API_KEY"):
        # Standard mode on purpose: the "-contributor" model ids let Meta use your content for training.
        if key_env not in os.environ:
            raise SystemExit(f"Set {key_env} in your environment first (never paste the key into a chat or a file).")
        self.base_url, self.model, self.key = base_url.rstrip("/"), model, os.environ[key_env]
        self.llm_calls = 0

    def _chat(self, prompt):
        data = post_chat(self.base_url, self.key,
                         {"model": self.model, "messages": [{"role": "user", "content": prompt}]})
        self.llm_calls += 1
        return data["choices"][0]["message"]["content"]

    def paraphrase(self, text, n, offset=0):
        prompt = (
            f"Rewrite this message sent to an enterprise AI agent in {n} different ways. Keep any ids (like O-1 or T-2) "
            f"and the meaning unchanged. Return ONLY a JSON array of {n} strings.\n\nMessage: {text}"
        )
        try:
            out = json.loads(self._chat(prompt))
            return [s for s in out if isinstance(s, str) and s != text][:n]
        except (ValueError, KeyError, OSError):
            return []
