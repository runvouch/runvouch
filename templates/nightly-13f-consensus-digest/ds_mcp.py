#!/usr/bin/env python3
"""Minimal client for the DataSignals Lab MCP server. Standard library only.

    from ds_mcp import call
    r = call("resolve_company", {"query": "Berkshire"})

Needs APIFY_TOKEN in the environment (a free Apify account is enough).
The server is streamable HTTP MCP and stateless, so one POST per tool call is all it takes.
Free tools: confluence_signals, resolve_company, usage. Every other tool is free for the
first 50 MCP calls a month, then $0.20 per non-empty result on your Apify account.
Pass spend_cap_usd to have the server refuse calls once your ledger reaches that amount.
"""
import json, os, sys, urllib.request

URL = os.getenv("DATASIGNALS_MCP_URL", "https://datasignalslab--datasignals-mcp.apify.actor/mcp")


def call(tool, args=None, spend_cap_usd=None, timeout=330):
    token = os.getenv("APIFY_TOKEN", "")
    if not token:
        sys.exit("APIFY_TOKEN not set (free at https://console.apify.com/settings/integrations)")
    params = {"name": tool, "arguments": args or {}}
    if spend_cap_usd is not None:
        params["_meta"] = {"spend_cap_usd": spend_cap_usd, "caller_id": os.getenv("DATASIGNALS_CALLER", "runvouch-template")}
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}).encode()
    req = urllib.request.Request(URL, body, {"Authorization": "Bearer " + token, "Content-Type": "application/json",
                                             "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode()
    # The server answers as SSE ("event: message" / "data: {...}") or as plain JSON.
    msg = None
    for line in raw.splitlines():
        if line.startswith("data:"):
            msg = json.loads(line[5:].strip())
    if msg is None:
        msg = json.loads(raw)
    if "error" in msg:
        raise RuntimeError(msg["error"])
    res = msg["result"]
    if res.get("structuredContent"):
        return res["structuredContent"]
    text = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
    try:
        return json.loads(text)
    except ValueError:
        return {"ok": not res.get("isError"), "text": text}


if __name__ == "__main__":
    tool = sys.argv[1] if len(sys.argv) > 1 else "usage"
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(call(tool, args), indent=1)[:4000])
