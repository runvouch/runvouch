#!/usr/bin/env bash
# RunVouch hook for Claude Code. Reads hook JSON on stdin, posts to RunVouch.
# Only active when RUNVOUCH_KEY is set AND RUNVOUCH_AGENT names this session's agent
# (set both in the environment of your Routine / cron / headless run). Interactive sessions: no-op.
# Never blocks the agent: all failures are swallowed, exit 0 always.
set -u
[ -z "${RUNVOUCH_KEY:-}" ] && exit 0
[ -z "${RUNVOUCH_AGENT:-}" ] && exit 0
URL="${RUNVOUCH_URL:-http://localhost:8787}"
STATE="${TMPDIR:-/tmp}/runvouch-${RUNVOUCH_AGENT}-$$-${CLAUDE_SESSION_ID:-nosession}.run"
STATE_GLOB="${TMPDIR:-/tmp}/runvouch-${RUNVOUCH_AGENT}-*-${CLAUDE_SESSION_ID:-nosession}.run"
IN="$(cat 2>/dev/null || true)"; export AW_IN="$IN"

post() { # path json
  curl -s -m 5 -X POST "$URL$1" -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" -d "$2" 2>/dev/null
}
jsonstr() { python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1" 2>/dev/null || printf '"%s"' "$1"; }

case "${1:-}" in
  start)
    RID=$(post /v1/runs/start "{\"agent\":$(jsonstr "$RUNVOUCH_AGENT"),\"source\":\"claude-code\",\"meta\":{\"session\":$(jsonstr "${CLAUDE_SESSION_ID:-}")}}" \
          | python3 -c 'import json,sys;print(json.load(sys.stdin)["run_id"])' 2>/dev/null)
    [ -n "$RID" ] && printf '%s' "$RID" > "$STATE"
    ;;
  tool)
    RID=$(cat $STATE_GLOB 2>/dev/null | head -1); [ -z "$RID" ] && exit 0
    python3 - "$RID" <<'PY' 2>/dev/null | { read -r BODY; [ -n "$BODY" ] && post /v1/runs/tool "$BODY" >/dev/null; }
import json, sys, os
d = json.loads(os.environ.get("AW_IN") or sys.stdin.read() or "{}")
tool = d.get("tool_name") or "unknown"
inp = d.get("tool_input") or {}
resp = d.get("tool_response")
ok = True
if isinstance(resp, dict):
    ok = not (resp.get("is_error") or resp.get("error"))
elif isinstance(resp, str) and resp[:200].lower().startswith(("error", "traceback")):
    ok = False
print(json.dumps({"run_id": sys.argv[1], "tool": tool, "input": inp, "ok": ok}))
PY
    ;;
  end)
    RID=$(cat $STATE_GLOB 2>/dev/null | head -1); [ -z "$RID" ] && exit 0
    # RUNVOUCH_EVIDENCE: JSON object, or a file path (must exist, be non-empty and modified since session start),
    # or an https:// URL (RunVouch checks for 200), or cmd:<shell command that must exit 0>
    EV="{}"
    if [ -n "${RUNVOUCH_EVIDENCE:-}" ]; then
      case "$RUNVOUCH_EVIDENCE" in
        \{*) EV="$RUNVOUCH_EVIDENCE" ;;
        http*) EV="{\"url\":{\"type\":\"url\",\"url\":$(jsonstr "$RUNVOUCH_EVIDENCE"),\"expect\":200}}" ;;
        cmd:*) if bash -c "${RUNVOUCH_EVIDENCE#cmd:}" >/dev/null 2>&1; then EV='{"assertion":true}'; else EV='{"assertion":false}'; fi ;;
        *) T0=$(stat -c %Y "$STATE" 2>/dev/null || echo 0); F="$RUNVOUCH_EVIDENCE"
           if [ -s "$F" ] && [ "$(stat -c %Y "$F" 2>/dev/null || echo 0)" -ge "$T0" ]; then EV="{\"file\":true}"; else EV="{\"file\":false}"; fi ;;
      esac
    fi
    # tokens + cost: summed from the Claude Code transcript (transcript_path in hook JSON); env overrides win
    read -r TOK COST <<<"$(python3 - <<'PY' 2>/dev/null
import json, os
d = json.loads(os.environ.get("AW_IN") or "{}")
path = d.get("transcript_path")
# USD per 1M tokens: (input, output, cache_write, cache_read); unknown model -> sonnet-class fallback
PRICES = {"opus": (15, 75, 18.75, 1.5), "fable": (15, 75, 18.75, 1.5), "mythos": (15, 75, 18.75, 1.5),
          "sonnet": (3, 15, 3.75, 0.3), "haiku": (0.8, 4, 1, 0.08)}
tok = 0; cost = 0.0
if path and os.path.exists(path):
    seen = set()
    for line in open(path, errors="ignore"):
        try: m = json.loads(line)
        except Exception: continue
        msg = m.get("message") or {}
        u = msg.get("usage") if isinstance(msg, dict) else None
        if m.get("type") != "assistant" or not u: continue
        key = msg.get("id") or m.get("uuid")
        if key in seen: continue          # streamed duplicates share message id
        seen.add(key)
        model = (msg.get("model") or "").lower()
        pi, po, pw, pr = next((v for k, v in PRICES.items() if k in model), PRICES["sonnet"])
        i, o = u.get("input_tokens", 0), u.get("output_tokens", 0)
        w, r = u.get("cache_creation_input_tokens", 0), u.get("cache_read_input_tokens", 0)
        tok += i + o + w + r
        cost += (i*pi + o*po + w*pw + r*pr) / 1e6
print(tok, round(cost, 4))
PY
)"
    TOK=${RUNVOUCH_TOKENS:-${TOK:-0}}; COST=${RUNVOUCH_COST:-${COST:-0}}
    post /v1/runs/end "{\"run_id\":\"$RID\",\"status\":\"ok\",\"cost\":$COST,\"tokens\":$TOK,\"evidence\":$EV,\"meta\":{\"cost_source\":\"transcript\"}}" >/dev/null
    rm -f $STATE_GLOB
    ;;
esac
exit 0
