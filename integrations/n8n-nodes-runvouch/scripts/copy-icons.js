// Copies node icons (svg/png) next to the compiled node files so n8n can find them.
const fs = require('fs');
const path = require('path');
const src = path.join(__dirname, '..', 'nodes');
const dst = path.join(__dirname, '..', 'dist', 'nodes');
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (/\.(svg|png)$/i.test(entry.name)) {
      const out = path.join(dst, path.relative(src, p));
      fs.mkdirSync(path.dirname(out), { recursive: true });
      fs.copyFileSync(p, out);
    }
  }
}
walk(src);
