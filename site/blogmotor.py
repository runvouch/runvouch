#!/usr/bin/env python3
"""
blogmotor.py — writes ONE new RunVouch field-notes article per run from site/topics.json,
verifies every source link, publishes (build + restart + IndexNow) and notifies via Telegram.
Runs weekly under RunVouch itself:  rv run blogmotor --cap-run-cost 3 --evidence-file site/articles.json -- python3 site/blogmotor.py
Safety: never publishes without >=2 working source links; never repeats a slug; one article per run.
"""
import json, os, re, subprocess, sys, time, urllib.request, urllib.parse
ROOT = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(ROOT)
CLAUDE = os.path.expanduser("~/.npm-global/bin/claude")
TOPICS = os.path.join(ROOT, "topics.json"); ARTICLES = os.path.join(ROOT, "articles.json")
env = {l.split("=",1)[0]: l.split("=",1)[1].strip() for l in open(os.path.join(REPO, ".env")) if "=" in l and not l.startswith("#")}

def tg(text):
    tok, chat = env.get("TG_TOKEN"), env.get("TG_CHAT")
    if not tok:
        # reuse the owner's Telegram settings stored in the RunVouch DB
        import sqlite3
        r = sqlite3.connect(env["RUNVOUCH_DB"]).execute("SELECT telegram_token, telegram_chat FROM accounts WHERE telegram_token IS NOT NULL ORDER BY id LIMIT 1").fetchone()
        if not r: return
        tok, chat = r
    try: urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", urllib.parse.urlencode({"chat_id": chat, "text": text}).encode(), timeout=10)
    except Exception: pass

def link_ok(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20); return r.status < 400
    except urllib.error.HTTPError as e: return e.code in (401, 403, 405, 429)  # exists but blocks bots
    except Exception: return False

topics = json.load(open(TOPICS)); arts = json.load(open(ARTICLES))
done = {a["slug"] for a in arts["articles"]}
todo = [t for t in topics if t["slug"] not in done and not t.get("skip")]
if not todo:
    print("no topics left"); tg("📝 blogmotor: topic queue empty — add topics to site/topics.json"); sys.exit(0)
t = todo[0]
prompt = f"""Write one blog article for RunVouch (runvouch.com), a dead man's switch, cost cap and outcome check for unattended AI agents (Claude Code Routines, headless claude -p, OpenClaw, n8n, cron).
Product facts: CLI `rv` (`rv agent NAME --cadence 24h --cap-run-cost 2 --evidence`, `rv run NAME --evidence-file out.html -- cmd`, fails open), Claude Code plugin via hooks (tokens+cost from transcript), MCP server (official registry com.runvouch/runvouch), Python/Node clients, detectors MISSED/FAILED/NO_EVIDENCE/RETRY_STORM(same tool+identical input >=8x)/BUDGET_RUN/BUDGET_DAY/DRIFT(7-run MAD)/STALLED; alerts Telegram/Slack/webhook; RunVouch alerts and can pause an agent via webhook — it never kills a running process; free 3 agents, $9 Solo, $29 Team; MIT self-host; EU hosting.
Voice: first person, a builder who ran agents and a crypto trading bot unattended for two years. Byline "RunVouch", never a personal name. Honest, specific, no hype, no emoji. ~900-1200 words. H2s phrased close to the target query. One-sentence definition of RunVouch early. Short FAQ (3 Q&As) at the end. Every factual claim about incidents, docs or competitors must link to a real source you verified with WebFetch/WebSearch — never invent sources or numbers.
Title: {t['title']}
Target query: {t['query']}
Angle: {t['angle']}
Do not repeat these existing articles: {[a['title'] for a in arts['articles']]}
Return ONLY a JSON object: {{"slug":"{t['slug']}","title":"...","description":"<=155 chars","html":"<article body: h2/p/pre/ul/li/a/strong/code only, no h1>"}}"""
t0 = time.time()
r = subprocess.run([CLAUDE, "-p", prompt, "--output-format", "json", "--max-turns", "30", "--allowedTools", "WebSearch,WebFetch"], capture_output=True, text=True, timeout=1500, cwd=REPO)
if r.returncode != 0:
    print("claude failed:", r.stderr[-500:]); tg(f"📝 blogmotor FAILED for '{t['title']}': {r.stderr[-200:]}"); sys.exit(1)
out = json.loads(r.stdout); text = out.get("result", ""); cost = out.get("total_cost_usd", 0)
m = re.search(r"\{.*\}", text, re.S)
art = json.loads(m.group(0))
links = re.findall(r'href="(https?://[^"]+)"', art["html"]); ext = [u for u in links if "runvouch.com" not in u]
bad = [u for u in ext if not link_ok(u)]
if len(ext) - len(bad) < 2 or bad:
    tg(f"📝 blogmotor HELD '{art['title']}': {len(ext)} sources, broken: {bad[:3]} — not published"); print("held", bad); sys.exit(2)
art["html"] = art["html"].replace("<pre><code>", "<pre>").replace("</code></pre>", "</pre>")
arts["articles"].append({k: art[k] for k in ("slug", "title", "description", "html")}); json.dump(arts, open(ARTICLES, "w"), indent=1)
subprocess.run([os.path.join(REPO, ".venv/bin/python"), os.path.join(ROOT, "build.py")], check=True)
subprocess.run(["systemctl", "--user", "restart", "runvouch"], check=False)
url = f"https://runvouch.com/blog/{art['slug']}"
try:
    key = env["INDEXNOW_KEY"]; body = json.dumps({"host": "runvouch.com", "key": key, "keyLocation": f"https://runvouch.com/{key}.txt", "urlList": [url, "https://runvouch.com/blog/"]}).encode()
    urllib.request.urlopen(urllib.request.Request("https://api.indexnow.org/indexnow", body, {"Content-Type": "application/json"}), timeout=15)
except Exception: pass
subprocess.run(["git", "-c", "user.name=RunVouch", "-c", "user.email=launch@runvouch.com", "commit", "-qam", f"blog: {art['title']}"], cwd=REPO)
tg(f"📝 New article live ({len(ext)} sources, ${cost:.2f}, {int(time.time()-t0)}s):\n{art['title']}\n{url}")
print("published", url, "cost", cost)
