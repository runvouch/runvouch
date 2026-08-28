#!/usr/bin/env bash
# verified-run: wrap a scheduled task in a RunVouch run (start, task, end with evidence file).
# Usage: verified-run.sh NAME [--every 24h] [--grace 15m] [--evidence-file PATH] [--cost USD] [--source openclaw] -- COMMAND ARGS...
# Exit code is the command's exit code. RunVouch being unreachable never fails the task.
set -u
API="${RUNVOUCH_URL:-https://api.runvouch.com}"
KEY="${RUNVOUCH_KEY:-}"
NAME=""; EVERY="24h"; GRACE="15m"; EVIDENCE=""; COST="0"; SOURCE="openclaw"

usage() { sed -n '2,4p' "$0" | sed 's/^# //'; exit 2; }
secs() { # 15m, 2h, 24h, 90s, 1d -> seconds
  local v="$1" n="${1%[smhd]}"
  case "$v" in *s) echo "$n";; *m) echo $((n*60));; *h) echo $((n*3600));; *d) echo $((n*86400));; *) echo "$v";; esac
}

[ $# -ge 1 ] || usage
NAME="$1"; shift
while [ $# -gt 0 ]; do
  case "$1" in
    --every) EVERY="$2"; shift 2;;
    --grace) GRACE="$2"; shift 2;;
    --evidence-file) EVIDENCE="$2"; shift 2;;
    --cost) COST="$2"; shift 2;;
    --source) SOURCE="$2"; shift 2;;
    --) shift; break;;
    -h|--help) usage;;
    *) echo "verified-run: unknown option $1" >&2; usage;;
  esac
done
[ $# -ge 1 ] || { echo "verified-run: no command given after --" >&2; usage; }
[ -n "$KEY" ] || echo "verified-run: RUNVOUCH_KEY not set, running unmonitored" >&2

post() { # post PATH JSON -> body on stdout, empty when unreachable
  [ -n "$KEY" ] || return 0
  curl -sS -m 15 -X POST "$API$1" -H "X-API-Key: $KEY" -H "Content-Type: application/json" -H "User-Agent: openclaw-verified-run/0.1" -d "$2" 2>/dev/null
}
run_id_of() { sed -n 's/.*"run_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p'; }

START_BODY="{\"agent\":\"$NAME\",\"source\":\"$SOURCE\"}"
RUN_ID=$(post /v1/runs/start "$START_BODY" | run_id_of)
if [ -z "$RUN_ID" ] && [ -n "$KEY" ]; then
  # agent not registered yet: register with the cadence given, then start again
  post /v1/agents "{\"name\":\"$NAME\",\"cadence_s\":$(secs "$EVERY"),\"grace_s\":$(secs "$GRACE"),\"evidence_required\":$([ -n "$EVIDENCE" ] && echo true || echo false)}" >/dev/null
  RUN_ID=$(post /v1/runs/start "$START_BODY" | run_id_of)
  [ -n "$RUN_ID" ] || echo "verified-run: RunVouch unreachable, running unmonitored" >&2
fi

# remove a stale evidence file so yesterday's output cannot pass as today's
[ -n "$EVIDENCE" ] && [ -f "$EVIDENCE" ] && rm -f -- "$EVIDENCE"

"$@"; RC=$?

STATUS="ok"; [ $RC -eq 0 ] || STATUS="fail"
EV="{}"; BYTES=0
if [ -n "$EVIDENCE" ]; then
  if [ -s "$EVIDENCE" ]; then
    BYTES=$(wc -c < "$EVIDENCE" | tr -d ' '); EV="{\"evidence_file\":true}"
  else
    EV="{\"evidence_file\":false}"; STATUS="fail"
    echo "verified-run: evidence file missing or empty: $EVIDENCE" >&2
  fi
fi
if [ -n "$RUN_ID" ]; then
  post /v1/runs/end "{\"run_id\":\"$RUN_ID\",\"status\":\"$STATUS\",\"cost\":$COST,\"output_bytes\":$BYTES,\"evidence\":$EV,\"meta\":{\"exit_code\":$RC,\"command\":\"$(printf '%s ' "$@" | sed 's/["\\]/ /g' | cut -c1-200)\"}}" >/dev/null
  echo "verified-run: $NAME $STATUS run_id=$RUN_ID evidence=${EVIDENCE:-none} bytes=$BYTES" >&2
fi
exit $RC
