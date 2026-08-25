#!/usr/bin/env python3
"""
RunVouch MCP server (stdio, JSON-RPC 2.0, no SDK dependency).
Lets Claude / any MCP client ask: "which of my agents are unhealthy?", read alerts, ack them,
and report run start/end from inside an agent.

Register (Claude Code):
  claude mcp add runvouch -e RUNVOUCH_KEY=rv_... -e RUNVOUCH_URL=https://api.runvouch.com -- python3 /path/runvouch_mcp.py
"""
import json, os, sys, urllib.request

URL = os.getenv("RUNVOUCH_URL", "http://localhost:8787").rstrip("/")
KEY = os.getenv("RUNVOUCH_KEY", "")


def api(method, path, body=None):
    req = urllib.request.Request(URL + path, json.dumps(body).encode() if body is not None else None,
                                 {"X-API-Key": KEY, "Content-Type": "application/json", "User-Agent": "runvouch-mcp/0.2"}, method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read() or b"{}")


TOOLS = [
    {"name": "runvouch_status", "description": "Health of all watched agents: state (ok/alert/failed/unproven/running/waiting), last run, 24h cost, open alerts.",
     "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
    {"name": "runvouch_alerts", "description": "Open (un-acknowledged) alerts: MISSED, FAILED, NO_EVIDENCE, BUDGET_RUN, BUDGET_DAY, RETRY_STORM, DRIFT, STALLED.",
     "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
    {"name": "runvouch_ack", "description": "Acknowledge an alert by id.",
     "inputSchema": {"type": "object", "properties": {"alert_id": {"type": "integer"}}, "required": ["alert_id"]}},
    {"name": "runvouch_runs", "description": "Recent runs of one agent.",
     "inputSchema": {"type": "object", "properties": {"agent": {"type": "string"}, "limit": {"type": "integer", "default": 20}}, "required": ["agent"]},
     "annotations": {"readOnlyHint": True}},
    {"name": "runvouch_run_start", "description": "Report that a run of `agent` started. Returns run_id.",
     "inputSchema": {"type": "object", "properties": {"agent": {"type": "string"}, "source": {"type": "string"}}, "required": ["agent"]}},
    {"name": "runvouch_run_end", "description": "Report that a run ended, with status and evidence dict (name -> bool or {type:'url',url}). Green run without evidence alerts.",
     "inputSchema": {"type": "object", "properties": {"run_id": {"type": "string"}, "status": {"type": "string", "enum": ["ok", "fail"]},
                                                      "cost": {"type": "number"}, "tokens": {"type": "integer"}, "evidence": {"type": "object"}},
                     "required": ["run_id"]}},
]


def call(name, a):
    if name == "runvouch_status":
        return api("GET", "/v1/agents")
    if name == "runvouch_alerts":
        return api("GET", "/v1/alerts")
    if name == "runvouch_ack":
        return api("POST", f"/v1/alerts/{int(a['alert_id'])}/ack")
    if name == "runvouch_runs":
        return api("GET", f"/v1/agents/{a['agent']}/runs?limit={int(a.get('limit', 20))}")
    if name == "runvouch_run_start":
        return api("POST", "/v1/runs/start", {"agent": a["agent"], "source": a.get("source", "mcp")})
    if name == "runvouch_run_end":
        return api("POST", "/v1/runs/end", {"run_id": a["run_id"], "status": a.get("status", "ok"), "cost": a.get("cost", 0),
                                            "tokens": a.get("tokens", 0), "evidence": a.get("evidence", {})})
    raise ValueError(f"unknown tool {name}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid, m, p = msg.get("id"), msg.get("method"), msg.get("params") or {}
        resp = None
        if m == "initialize":
            resp = {"protocolVersion": p.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                    "serverInfo": {"name": "runvouch", "version": "0.1.0"}}
        elif m == "tools/list":
            resp = {"tools": TOOLS}
        elif m == "tools/call":
            try:
                out = call(p["name"], p.get("arguments") or {})
                resp = {"content": [{"type": "text", "text": json.dumps(out, indent=1)}]}
            except Exception as e:
                resp = {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}
        elif m == "ping":
            resp = {}
        if mid is not None and resp is not None:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": resp}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
