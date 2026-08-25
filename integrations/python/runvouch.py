"""runvouch.py — zero-dependency Python client. Fails open: report calls never raise.
    import runvouch
    with runvouch.vouch("nightly-report", evidence=lambda: {"report": os.path.exists("out.html")}) as run:
        run.tool("openai.chat", {"model": "gpt-5", "h": "…"}, cost=0.01)
        ...
"""
import json, os, sys, urllib.request, contextlib
URL = os.getenv("RUNVOUCH_URL", "https://api.runvouch.com").rstrip("/"); KEY = os.getenv("RUNVOUCH_KEY", "")

def _api(path, body=None, method="POST"):
    try:
        req = urllib.request.Request(URL + path, json.dumps(body).encode() if body is not None else None,
                                     {"X-API-Key": KEY, "Content-Type": "application/json", "User-Agent": "runvouch-python/0.3"}, method=method)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read() or b"{}")
    except Exception as e:
        sys.stderr.write(f"runvouch: {e} (running unmonitored)\n"); return None

def agent(name, **opts): return _api("/v1/agents", {"name": name, **opts})

class Run:
    def __init__(self, agent, source="python", meta=None):
        r = _api("/v1/runs/start", {"agent": agent, "source": source, "meta": meta or {}}); self.run_id = r and r.get("run_id")
    def tool(self, tool, input=None, ok=True, cost=0, tokens=0):
        return self.run_id and _api("/v1/runs/tool", {"run_id": self.run_id, "tool": tool, "input": input, "ok": ok, "cost": cost, "tokens": tokens})
    def heartbeat(self): return self.run_id and _api(f"/v1/runs/heartbeat?run_id={self.run_id}")
    def end(self, status="ok", cost=0, tokens=0, evidence=None, output_bytes=None, meta=None):
        return self.run_id and _api("/v1/runs/end", {"run_id": self.run_id, "status": status, "cost": cost, "tokens": tokens, "evidence": evidence or {}, "output_bytes": output_bytes, "meta": meta or {}})

@contextlib.contextmanager
def vouch(agent, source="python", evidence=None, cost=None):
    run = Run(agent, source)
    try:
        yield run
    except Exception as e:
        run.end(status="fail", meta={"error": str(e)[-500:]}); raise
    run.end(status="ok", evidence=(evidence() if callable(evidence) else evidence) or {}, cost=(cost() if callable(cost) else cost) or 0)
