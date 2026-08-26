#!/usr/bin/env bash
# Build the PyPI package from the canonical sources (client + CLI).
# Publishing is a separate, explicit step:  twine upload dist/*  (see PUBLISH.md)
set -euo pipefail
cd "$(dirname "$0")"
ROOT=../..
rm -rf runvouch dist build ./*.egg-info
mkdir runvouch
cp $ROOT/integrations/python/runvouch.py runvouch/__init__.py
# the published CLI talks to the hosted API by default (self-hosters set RUNVOUCH_URL)
sed 's#os.getenv("RUNVOUCH_URL", "http://localhost:8787")#os.getenv("RUNVOUCH_URL", "https://api.runvouch.com")#' $ROOT/runvouch/cli.py > runvouch/cli.py
grep -q 'api.runvouch.com' runvouch/cli.py
cp $ROOT/LICENSE .
$ROOT/.venv/bin/python -m build -q
ls -la dist
