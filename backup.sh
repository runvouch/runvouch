#!/usr/bin/env bash
# Daily RunVouch DB backup. Writes to a temp file and moves it into place, so a re-run on the
# same day refreshes the backup instead of failing on "output file already exists".
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
DAY=$(date +%Y%m%d)
OUT="data/backups/runvouch-$DAY.db"
TMP="$OUT.tmp"
rm -f "$TMP"
.venv/bin/python -c "import sqlite3,sys;c=sqlite3.connect('data/runvouch.db');c.execute('VACUUM INTO ?',(sys.argv[1],))" "$TMP"
mv -f "$TMP" "$OUT"
ls -t data/backups/runvouch-*.db | tail -n +31 | xargs -r rm -f
cp "$OUT" "$HOME/apify/landing-live/maintenance/runvouch-latest.db.bak" 2>/dev/null || true
echo "backup ok $OUT $(stat -c %s "$OUT") bytes $(date)"
