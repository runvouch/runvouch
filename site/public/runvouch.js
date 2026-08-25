// runvouch.js — zero-dependency Node client (Node 18+). Fails open: never throws from report calls.
// Usage: const rv = require('./runvouch'); const run = await rv.start('nightly-report'); ... await run.end({ status:'ok', cost:0.12, evidence:{ rows:true } });
const URL_ = process.env.RUNVOUCH_URL || 'https://api.runvouch.com';
const KEY = process.env.RUNVOUCH_KEY || '';
async function api(path, body, method = 'POST') {
  try {
    const r = await fetch(URL_ + path, { method, headers: { 'X-API-Key': KEY, 'Content-Type': 'application/json', 'User-Agent': 'runvouch-node/0.3' }, body: body ? JSON.stringify(body) : undefined });
    return r.ok ? await r.json() : (console.error('runvouch:', r.status, await r.text()), null);
  } catch (e) { console.error('runvouch: unreachable, running unmonitored'); return null; }
}
module.exports = {
  agent: (name, opts = {}) => api('/v1/agents', { name, ...opts }),
  async start(agent, source = 'node', meta = {}) {
    const r = await api('/v1/runs/start', { agent, source, meta }); const run_id = r && r.run_id;
    return {
      run_id,
      tool: (tool, input, extra = {}) => run_id ? api('/v1/runs/tool', { run_id, tool, input, ...extra }) : null,
      heartbeat: () => run_id ? api('/v1/runs/heartbeat?run_id=' + run_id) : null,
      end: (o = {}) => run_id ? api('/v1/runs/end', { run_id, status: 'ok', ...o }) : null,
    };
  },
  // wrap an async job: reports start/end, status from thrown errors, evidence from your callback
  async vouch(agent, fn, { source = 'node', evidence } = {}) {
    const run = await this.start(agent, source); let out, err;
    try { out = await fn(run); } catch (e) { err = e; }
    await run.end({ status: err ? 'fail' : 'ok', evidence: evidence ? await evidence(out) : {}, meta: err ? { error: String(err).slice(-500) } : {} });
    if (err) throw err; return out;
  },
  status: () => api('/v1/agents', null, 'GET'),
  alerts: () => api('/v1/alerts', null, 'GET'),
};
