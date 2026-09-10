#!/usr/bin/env bash
# Daily RunVouch backup. Writes to a temp file and moves it into place, so a re-run on the
# same day refreshes the backup instead of failing on "output file already exists".
#
# Two artefacts, on purpose. The database can be rebuilt from a copy; the proof files cannot.
# seal_day writes a day file once and OpenTimestamps stamps it once, so a lost .ots is a lost
# Bitcoin attestation and every claim about that day becomes unverifiable. They travel together.
#
# Off this machine: set RUNVOUCH_BACKUP_CMD in .env to a command that takes one file path and
# ships it somewhere else (rclone, rsync over a key, aws s3 cp). It runs once per artefact and
# a failure is reported, not swallowed: a backup nobody checks is not a backup.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
[ -f .env ] && set -a && . ./.env && set +a
DAY=$(date +%Y%m%d)
OUT="data/backups/runvouch-$DAY.db"
PROOF="data/backups/runvouch-proof-$DAY.tar.gz"
TMP="$OUT.tmp"

rm -f "$TMP"
.venv/bin/python -c "import sqlite3,sys;c=sqlite3.connect('data/runvouch.db');c.execute('VACUUM INTO ?',(sys.argv[1],))" "$TMP"
mv -f "$TMP" "$OUT"

# .bak files are OpenTimestamps' own leftovers from an upgrade, not attestations of their own
tar czf "$PROOF.tmp" --exclude='*.bak' -C data proof
mv -f "$PROOF.tmp" "$PROOF"

ls -t data/backups/runvouch-*.db | tail -n +31 | xargs -r rm -f
ls -t data/backups/runvouch-proof-*.tar.gz | tail -n +31 | xargs -r rm -f
cp "$OUT" "$HOME/apify/landing-live/maintenance/runvouch-latest.db.bak" 2>/dev/null || true
cp "$PROOF" "$HOME/apify/landing-live/maintenance/runvouch-latest-proof.tar.gz" 2>/dev/null || true

WEG="not configured"
if [ -n "${RUNVOUCH_BACKUP_CMD:-}" ]; then
  if $RUNVOUCH_BACKUP_CMD "$OUT" && $RUNVOUCH_BACKUP_CMD "$PROOF"; then
    WEG="ok"
  else
    echo "off-machine copy FAILED with RUNVOUCH_BACKUP_CMD" >&2
    exit 1
  fi
fi
echo "backup ok $OUT $(stat -c %s "$OUT") bytes, $PROOF $(stat -c %s "$PROOF") bytes, off-machine $WEG $(date)"
