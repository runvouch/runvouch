#!/usr/bin/env bash
# Build the npm package from the canonical Node client. Publishing is explicit: npm publish (see PUBLISH.md)
set -euo pipefail
cd "$(dirname "$0")"
cp ../../integrations/node/runvouch.js index.js
cp ../../LICENSE .
chmod +x bin/rv.js
rm -f ./*.tgz
npm pack --silent
ls -la ./*.tgz
