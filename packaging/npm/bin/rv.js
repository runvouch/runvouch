#!/usr/bin/env node
// rv — RunVouch CLI (Node 18+, zero dependencies). Fails open: monitoring can never break your job.
//   rv agent  NAME [--cadence 24h] [--cap-run-cost 2] [--cap-day-cost 10] [--evidence]
//   rv run    NAME [--evidence-file PATH] [--evidence-url URL] [--source cron] [--log FILE] -- CMD ARGS...
//   rv status | rv alerts [--ack ID]
// Env: RUNVOUCH_KEY (free key at https://runvouch.com/app), RUNVOUCH_URL (default https://api.runvouch.com)
const fs = require('fs'), path = require('path'), { spawnSync } = require('child_process');
const URL_ = (process.env.RUNVOUCH_URL || 'https://api.runvouch.com').replace(/\/$/, '');
const KEY = process.env.RUNVOUCH_KEY || '';
const USAGE = fs.readFileSync(__filename, 'utf8').split('\n').slice(1, 6).map(l => l.replace(/^\/\/ ?/, '')).join('\n');

async function api(method, p, body, soft) {
  if (!KEY) { if (soft) { console.error('runvouch: RUNVOUCH_KEY not set, running unmonitored'); return null; } die('RUNVOUCH_KEY not set'); }
  try {
    const r = await fetch(URL_ + p, { method, headers: { 'X-API-Key': KEY, 'Content-Type': 'application/json', 'User-Agent': 'runvouch-node-cli/0.3' }, body: body ? JSON.stringify(body) : undefined });
    if (!r.ok) throw new Error(`RunVouch ${r.status}: ${(await r.text()).slice(0, 200)}`);
    return await r.json();
  } catch (e) { if (soft) { console.error('runvouch:', e.message, '(running unmonitored)'); return null; } die(e.message); }
}
function die(m) { console.error(m); process.exit(1); }
function dur(s) { const u = { s: 1, m: 60, h: 3600, d: 86400 }; const k = s.slice(-1); return u[k] ? Math.round(parseFloat(s) * u[k]) : parseInt(s, 10); }
function parse(argv) { // tiny flag parser: --a b, --flag, --multi x --multi y
  const o = { _: [], flags: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) { const k = a.slice(2); const v = argv[i + 1]; if (v !== undefined && !v.startsWith('--')) { (o.flags[k] = o.flags[k] || []).push(v); i++; } else o.flags[k] = [true]; }
    else o._.push(a);
  }
  return o;
}
const one = (f, k, d) => (f[k] ? f[k][0] : d);

(async () => {
  let argv = process.argv.slice(2), tail = [];
  const cmd = argv.shift();
  if (cmd === 'run' && argv.includes('--')) { const i = argv.indexOf('--'); tail = argv.slice(i + 1); argv = argv.slice(0, i); }
  const { _, flags } = parse(argv);
  if (cmd === 'agent') {
    const name = _[0] || die(USAGE);
    console.log(JSON.stringify(await api('POST', '/v1/agents', {
      name, cadence_s: flags.cadence ? dur(one(flags, 'cadence')) : null, grace_s: dur(one(flags, 'grace', '15m')), max_runtime_s: dur(one(flags, 'max-runtime', '1h')),
      cap_run_cost: flags['cap-run-cost'] ? parseFloat(one(flags, 'cap-run-cost')) : null, cap_day_cost: flags['cap-day-cost'] ? parseFloat(one(flags, 'cap-day-cost')) : null,
      cap_run_tokens: flags['cap-run-tokens'] ? parseInt(one(flags, 'cap-run-tokens'), 10) : null, evidence_required: !!flags.evidence,
    })));
  } else if (cmd === 'run') {
    const name = _[0]; if (!name || !tail.length) die('rv run NAME -- CMD ...');
    const evFiles = (flags['evidence-file'] || []).map(f => path.resolve(f));
    const r0 = await api('POST', '/v1/runs/start', { agent: name, source: one(flags, 'source', 'cron'), meta: { cmd: tail.join(' ') } }, true);
    const rid = r0 && r0.run_id, t0 = Date.now() / 1000;
    const proc = spawnSync(tail[0], tail.slice(1), { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
    const out = (proc.stdout || '') + (proc.stderr || '');
    const log = one(flags, 'log');
    if (log) fs.appendFileSync(log, out); else { process.stdout.write(proc.stdout || ''); process.stderr.write(proc.stderr || ''); }
    const evidence = {};
    for (const f of evFiles) { let ok = false; try { const st = fs.statSync(f); ok = st.size > 0 && st.mtimeMs / 1000 >= t0 - 1; } catch (_) {} evidence['file:' + path.basename(f)] = ok; }
    for (const u of flags['evidence-url'] || []) evidence['url:' + u] = { type: 'url', url: u, expect: 200 };
    const code = proc.status === null ? 1 : proc.status;
    if (rid) await api('POST', '/v1/runs/end', { run_id: rid, status: code === 0 ? 'ok' : 'fail', output_bytes: Buffer.byteLength(out), evidence, meta: { exit: code, error: code ? (proc.stderr || '').slice(-500) : '' } }, true);
    process.exit(code);
  } else if (cmd === 'status') {
    for (const ag of await api('GET', '/v1/agents')) { const l = ag.last_run; console.log(`${ag.name.padEnd(28)} ${String(ag.state).padEnd(8)} ${l ? new Date(l.started * 1000).toISOString().slice(0, 16) + ' ' + l.status : '-'}  alerts:${ag.open_alerts}`); }
  } else if (cmd === 'alerts') {
    if (flags.ack) { await api('POST', `/v1/alerts/${one(flags, 'ack')}/ack`); console.log('acked'); }
    else for (const a of await api('GET', '/v1/alerts')) console.log(`#${a.id} ${a.kind.padEnd(12)} ${a.agent.padEnd(24)} ${a.message}`);
  } else { console.log(USAGE); process.exit(cmd ? 1 : 0); }
})();
