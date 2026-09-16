#!/usr/bin/env python3
"""
RunVouch site builder, generates site/public/ from templates in this file.
Run: python3 site/build.py   (server serves site/public on runvouch.com)
Design system: warm paper background, ink text, RunVouch teal accent, amber for alerts.
Fonts: Instrument Sans (display) + Figtree (body) + Geist Mono (code), Google Fonts.
"""
from __future__ import annotations
import json, os, re, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "public"

# Versie uit het pakket, niet met de hand: de changelog stond op 0.2 terwijl PyPI,
# npm en /health al 0.3.3 gaven (gemeten 7 sep 2026). Eén bron voorkomt dat opnieuw.
def _pkg_version():
    m = re.search(r'^version = "([^"]+)"', (ROOT.parent / "packaging" / "pypi" / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "unknown"

VERSION = _pkg_version()
if VERSION == "unknown":
    # De changelog belooft dat dit hetzelfde getal is als /health, PyPI en npm geven. Kan de
    # bouw het pakket niet lezen, dan is die belofte niet te houden en publiceren we niets.
    raise SystemExit("build gestopt: versie niet uit packaging/pypi/pyproject.toml te lezen")
BASE = "https://runvouch.com"
API = "https://api.runvouch.com"
TODAY = datetime.date.today().isoformat()
# Bezoekteller (GoatCounter, zonder cookies). Code staat in site/analytics.json; leeg = geen tag.
try:
    _GC = (json.loads((ROOT / "analytics.json").read_text()).get("goatcounter_code") or "").strip()
except Exception:
    _GC = ""
ANALYTICS = (f'<script data-goatcounter="https://{_GC}.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'
             if _GC else "")
_ENV = {l.split("=",1)[0]: l.split("=",1)[1].strip() for l in open(ROOT.parent / ".env") if "=" in l and not l.startswith("#")} if (ROOT.parent / ".env").exists() else {}
LS_LIVE = _ENV.get("LS_LIVE") == "1"
STRIPE_LIVE = _ENV.get("STRIPE_LIVE") == "1" and _ENV.get("STRIPE_SOLO_URL") and _ENV.get("STRIPE_TEAM_URL")
POLAR_LIVE = _ENV.get("POLAR_LIVE") == "1" and _ENV.get("POLAR_SOLO_URL") and _ENV.get("POLAR_TEAM_URL")
# billing provider: Polar (merchant of record, no KvK needed) > Stripe > Lemon Squeezy (rejected 26 Aug 2026)
if POLAR_LIVE:
    PROCESSOR, SOLO_URL, TEAM_URL, EMAIL_PARAM = "Polar", _ENV["POLAR_SOLO_URL"], _ENV["POLAR_TEAM_URL"], "customer_email"
elif STRIPE_LIVE:
    PROCESSOR, SOLO_URL, TEAM_URL, EMAIL_PARAM = "Stripe", _ENV["STRIPE_SOLO_URL"], _ENV["STRIPE_TEAM_URL"], "prefilled_email"
else:
    PROCESSOR, SOLO_URL, TEAM_URL, EMAIL_PARAM = ("Lemon Squeezy" if LS_LIVE else "Polar"), "https://runvouch.lemonsqueezy.com/checkout/buy/41587f68-6ccd-490c-b3ca-8cb781045b22", "https://runvouch.lemonsqueezy.com/checkout/buy/f0589446-3a09-469b-9381-c1e1f9af45e9", "checkout[email]"

# Data en inhoud uit de git-historie van dit archief, niet uit het hoofd. De provider staat
# er als vaste tekst en niet als PROCESSOR-variabele: die geeft de HUIDIGE provider, en dan
# leest de regel van 25 augustus alsof Polar er toen al stond (gemeld 7 sep 2026).
RELEASES = [
    ("0.3.3", "2026-08-26", ["<code>pip install runvouch</code> and <code>npm install runvouch</code>: client plus the <code>rv</code> CLI, hosted API by default.",
                             "Listed in the MCP registry with a verifiable proof link.",
                             "Subscriptions moved from Lemon Squeezy to Polar, with billing mail on its webhook."]),
    ("0.3.2", "2026-08-26", ["Claude Code plugin: skill, agent and the <code>/vouch</code> command.",
                             "Claude Desktop bundle (<code>.mcpb</code>)."]),
    ("0.3",   "2026-08-25", ["Public launch on runvouch.com and api.runvouch.com.",
                             "Dead man's switch, cost cap and outcome check.",
                             "Eight detectors: MISSED, FAILED, NO_EVIDENCE, RETRY_STORM, BUDGET_RUN, BUDGET_DAY, DRIFT, STALLED.",
                             "MCP server and the zero-dependency <code>rv</code> CLI with fail-open."]),
    ("0.2",   "2026-08-25", ["Hashed API keys, rate limits, CORS, self-serve signup and key rotation.",
                             "Deploy documentation for Cloudflare Tunnel and nginx."]),
]
# Losse pakketten met hun eigen nummering; anders lijkt 0.1.3 een stap terug.
SIDE_RELEASES = [("n8n-nodes-runvouch 0.1.3", "2026-08-28", "n8n community node, published with provenance.")]
BILLING_LIVE = POLAR_LIVE or STRIPE_LIVE or LS_LIVE
SOLO_BTN = f'<a class="btn" href="{SOLO_URL}" data-ls="{EMAIL_PARAM}">Upgrade to Solo, $19/mo</a>' if BILLING_LIVE else '<a class="btn" href="/contact?topic=billing">Start free; paid plans open Sept 2026</a>'
TEAM_BTN = f'<a class="btn ghost" href="{TEAM_URL}" data-ls="{EMAIL_PARAM}">Upgrade to Team, $99/mo</a>' if BILLING_LIVE else '<a class="btn ghost" href="/contact?topic=billing">Request Team plan</a>'
import hashlib
CSS_HASH = ""  # set after CSS is defined

LOGO_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-label="RunVouch">
<circle cx="32" cy="32" r="27" fill="#141B33" stroke="#4C8DFF" stroke-width="4"/>
<path d="M19 34 l9 9 l17 -19" fill="none" stroke="#EEF2FF" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''

CSS = r'''
:root{--bg:#0B1020;--bg2:#0F1529;--bg3:#141B33;--line:rgba(169,180,214,.14);--line2:rgba(169,180,214,.26);--fg:#EEF2FF;--fg2:#A9B4D6;--fg3:#6F7A9E;--acc:#4C8DFF;--acc2:#8FB6FF;--acc-soft:rgba(76,141,255,.14);--good:#3ECF8E;--good-soft:rgba(62,207,142,.14);--bad:#FF6363;--bad-soft:rgba(255,99,99,.14);--warn:#F5B84B;--warn-soft:rgba(245,184,75,.16);--ease:cubic-bezier(.2,.7,.2,1);--max:1140px}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 Figtree,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:var(--acc2);text-decoration:none}a:hover{text-decoration:underline}
h1,h2,h3,h4{font-family:"Instrument Sans",Figtree,system-ui,sans-serif;letter-spacing:-.02em;line-height:1.08;margin:0 0 .5em;font-weight:700;text-wrap:balance}
h1{font-size:clamp(2.2rem,4.6vw,3.5rem);letter-spacing:-.03em}h2{font-size:clamp(1.6rem,3vw,2.25rem)}h3{font-size:1.12rem;font-weight:600;letter-spacing:-.01em}
.grad{color:var(--acc2)}
p{margin:0 0 1em}.muted{color:var(--fg2)}.small{font-size:.9rem}
code,pre,kbd{font-family:"Geist Mono",ui-monospace,SFMono-Regular,Menlo,monospace}
code{background:rgba(169,180,214,.08);border:1px solid var(--line);border-radius:6px;padding:.1em .4em;font-size:.88em;color:#DCE4FF}
pre{background:#070B17;border:1px solid var(--line);border-radius:12px;padding:1.1rem 1.25rem;overflow-x:auto;font-size:.87rem;line-height:1.65;margin:0 0 1.2rem;color:#DCE4FF}
pre code{background:none;border:0;padding:0;color:inherit;font-size:inherit}.c,.k{color:var(--acc2)}.d{color:var(--fg3)}
.wrap{max-width:var(--max);margin:0 auto;padding:0 1.25rem}
.ambient{position:absolute;left:0;right:0;top:0;height:var(--bandh,420px);z-index:0;pointer-events:none;overflow:hidden;mask-image:linear-gradient(180deg,#000 70%,transparent 100%)}body{position:relative}main,footer,.ticker{position:relative;z-index:1}
.blob{position:absolute;border-radius:50%;filter:blur(100px);opacity:.35}.b1{width:600px;height:600px;left:-220px;top:-220px;background:radial-gradient(circle,rgba(76,141,255,.55),transparent 60%)}.b2{width:520px;height:520px;right:-200px;top:20%;background:radial-gradient(circle,rgba(76,141,255,.3),transparent 60%)}.b3{display:none}
.grid-overlay{position:absolute;inset:0;background-image:linear-gradient(rgba(169,180,214,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(169,180,214,.06) 1px,transparent 1px);background-size:56px 56px;mask-image:radial-gradient(ellipse 70% 55% at 50% 30%,#000 20%,transparent 100%)}
canvas.sig{position:absolute;inset:0;width:100%;height:100%;opacity:.95}
header.top{position:sticky;top:0;z-index:20;background:rgba(11,16,32,.78);backdrop-filter:blur(14px) saturate(1.2);border-bottom:1px solid var(--line)}
.nav{display:flex;align-items:center;gap:1.5rem;height:66px}.nav .brand{display:flex;align-items:center;gap:.6rem;font-family:"Instrument Sans";font-weight:700;font-size:1.2rem;color:var(--fg);letter-spacing:-.02em}
.nav .brand svg{width:30px;height:30px}.nav nav{display:flex;gap:1.5rem;margin-left:auto}.nav nav a{color:var(--fg2);font-weight:500;font-size:.95rem}.nav nav a:hover{color:var(--fg);text-decoration:none}
.btn{display:inline-flex;align-items:center;gap:.5rem;background:var(--acc);color:#fff!important;padding:.78rem 1.25rem;border-radius:10px;font-weight:600;border:0;cursor:pointer;font-size:1rem;font-family:Figtree;box-shadow:0 8px 24px -10px rgba(76,141,255,.7);transition:transform .2s var(--ease),background .2s}
.btn:hover{background:#3C7CF0;transform:translateY(-1px);text-decoration:none}.btn.ghost{background:rgba(169,180,214,.06);color:var(--fg)!important;border:1px solid var(--line2);box-shadow:none}.btn.ghost:hover{background:rgba(169,180,214,.12)}
.btn:focus-visible,a:focus-visible,input:focus-visible,button:focus-visible{outline:2px solid var(--acc2);outline-offset:2px}
.hero{position:relative;padding:7.4rem 0 3.5rem;display:flex;align-items:center;overflow:hidden}
.hero-inner{position:relative;z-index:1;display:grid;grid-template-columns:1fr 1fr;gap:3rem;align-items:center;width:100%}
.eyebrow{display:inline-flex;align-items:center;gap:.6rem;border:1px solid var(--line2);background:rgba(169,180,214,.05);color:var(--fg2);border-radius:999px;padding:.35rem .9rem .35rem .6rem;font-weight:500;font-size:.82rem;margin-bottom:1.4rem}
.eyebrow i{width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 10px var(--good);animation:blink 1.6s infinite}@keyframes blink{50%{opacity:.25}}
.hero .lead{font-size:1.2rem;color:var(--fg2);max-width:34rem}.hero .cta{display:flex;gap:.8rem;flex-wrap:wrap;margin:1.6rem 0 1rem}
.ph-badge img{display:block;border-radius:8px}
.trust{display:flex;gap:1.2rem;flex-wrap:wrap;color:var(--fg3);font-size:.85rem;margin-top:.4rem}.trust span::before{content:"✓ ";color:var(--good)}
.reveal{opacity:0;transform:translateY(16px);transition:opacity .7s var(--ease),transform .7s var(--ease)}.reveal.in{opacity:1;transform:none}.card.reveal:nth-child(2){transition-delay:.08s}.card.reveal:nth-child(3){transition-delay:.16s}.card.reveal:nth-child(4){transition-delay:.24s}
.panel{background:rgba(15,21,41,.88);border:1px solid var(--line2);border-radius:16px;box-shadow:0 40px 90px -40px rgba(0,0,0,.9);overflow:hidden;backdrop-filter:blur(8px)}
.panel .bar{display:flex;align-items:center;gap:.5rem;padding:.7rem 1rem;border-bottom:1px solid var(--line);font-size:.78rem;color:var(--fg3);font-family:"Geist Mono"}.panel .bar i{width:10px;height:10px;border-radius:50%;background:rgba(169,180,214,.18);display:inline-block}
.runs{list-style:none;margin:0;padding:.4rem 0}.runs li{display:grid;grid-template-columns:120px 1fr auto;gap:.75rem;align-items:center;padding:.7rem 1rem;border-bottom:1px solid var(--line);font-size:.9rem}
.runs li:last-child{border:0}.runs .t{font-family:"Geist Mono";color:var(--fg3);font-size:.78rem}
.pill{font-family:"Geist Mono";font-size:.7rem;font-weight:600;padding:.25rem .6rem;border-radius:6px;letter-spacing:.08em;text-transform:uppercase}
.ok{background:var(--good-soft);color:var(--good);border:1px solid rgba(62,207,142,.35)}.warn{background:var(--warn-soft);color:var(--warn);border:1px solid rgba(245,184,75,.35)}.bad{background:var(--bad-soft);color:#FF8A8A;border:1px solid rgba(255,99,99,.4)}
.runs .m{color:var(--fg2)}.runs .m b{color:var(--fg);font-weight:600}
.alertbox{margin:.75rem 1rem 1rem;background:var(--bad-soft);border:1px solid rgba(255,99,99,.35);border-radius:10px;padding:.75rem .95rem;font-size:.86rem;display:flex;gap:.6rem;color:var(--fg)}
.ticker{display:block;border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:rgba(169,180,214,.03);overflow:hidden;white-space:nowrap;color:var(--fg2);font-family:"Geist Mono";font-size:.8rem;padding:.6rem 0}
.tk-track{display:inline-block;animation:tk 60s linear infinite}.tk-track span{margin-right:3rem}.tk-track b{color:var(--acc2);font-weight:600}.tk-track em{color:#FF8A8A;font-style:normal}@keyframes tk{to{transform:translateX(-50%)}}
section{padding:4.5rem 0;position:relative}section.alt{background:var(--bg2);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.kicker{font-family:"Geist Mono";font-size:.76rem;letter-spacing:.14em;text-transform:uppercase;color:var(--acc2);margin-bottom:.8rem;display:block}
.grid{display:grid;gap:1.1rem}.g3{grid-template-columns:repeat(3,1fr)}.g2{grid-template-columns:repeat(2,1fr)}.g4{grid-template-columns:repeat(4,1fr)}
.card{background:var(--bg3);border:1px solid var(--line);border-radius:14px;padding:1.4rem;color:var(--fg);position:relative;transition:transform .3s var(--ease),border-color .3s}
.card:hover{transform:none;border-color:rgba(76,141,255,.55);box-shadow:0 0 0 1px rgba(76,141,255,.25),0 12px 34px rgba(76,141,255,.12)}a.card:hover{text-decoration:none}
.card h3{display:flex;align-items:center;gap:.5rem;margin-bottom:.45rem}.card .tag{font-family:"Geist Mono";font-size:.7rem;font-weight:600;color:#FF8A8A;background:var(--bad-soft);padding:.2rem .55rem;border-radius:6px;letter-spacing:.08em}
.card p{margin:0;color:var(--fg2);font-size:.95rem}.card pre{margin-top:.9rem;margin-bottom:0}
.big{font-family:"Instrument Sans";font-size:2.1rem;font-weight:700;letter-spacing:-.03em;line-height:1;margin-bottom:.4rem;color:var(--acc2)}
.steps{counter-reset:s}.steps .card{padding-top:1.5rem}.steps .card::before{counter-increment:s;content:"0" counter(s);position:absolute;right:1.1rem;top:.9rem;font-family:"Geist Mono";font-weight:600;font-size:.9rem;color:var(--fg3)}
table{width:100%;border-collapse:collapse;background:var(--bg3);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:.93rem;font-variant-numeric:tabular-nums}
th,td{padding:.8rem .95rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:rgba(169,180,214,.04);font-weight:600;font-size:.78rem;color:var(--fg2);font-family:"Geist Mono";letter-spacing:.06em;text-transform:uppercase}tr:last-child td{border:0}
td.y{color:var(--good);font-weight:600}td.n{color:var(--fg3)}
.price{display:grid;grid-template-columns:repeat(3,1fr);gap:1.1rem}.price .card{display:flex;flex-direction:column}.price .n{font-family:"Instrument Sans";font-size:2.6rem;font-weight:700;letter-spacing:-.03em}.price .n small{font-size:1rem;color:var(--fg3);font-weight:500;font-family:Figtree}
.price ul{padding-left:1.1rem;margin:.6rem 0 1.2rem;color:var(--fg2);font-size:.93rem;flex:1}.price .card.hi{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc),0 30px 70px -40px rgba(76,141,255,.6)}
.faq details{background:var(--bg3);border:1px solid var(--line);border-radius:12px;padding:1rem 1.2rem;margin-bottom:.6rem;transition:border-color .3s,box-shadow .3s}.faq details:hover,.faq details[open]{border-color:rgba(76,141,255,.55);box-shadow:0 0 0 1px rgba(76,141,255,.2)}.faq details[open] summary{color:var(--acc2)}.faq summary{cursor:pointer;font-weight:600;list-style:none}.faq summary::-webkit-details-marker{display:none}.faq summary::before{content:"→ ";color:var(--acc2)}.faq p{margin:.6rem 0 0;color:var(--fg2)}
.signup{display:flex;gap:.6rem;flex-wrap:wrap;margin:1rem 0}.signup input{flex:1;min-width:16rem;padding:.85rem 1rem;border:1px solid var(--line2);border-radius:10px;font:inherit;background:#070B17;color:var(--fg)}
.keybox{display:none;margin-top:.75rem}.keybox.show{display:block}
.quote{border-left:3px solid var(--acc);padding:.4rem 1.1rem;color:var(--fg2);font-size:1.05rem}.quote a{color:var(--fg2);text-decoration:underline}
footer{border-top:1px solid var(--line);padding:3rem 0;color:var(--fg2);font-size:.9rem;background:var(--bg2)}footer .cols{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:2rem}footer h4{margin:0 0 .6rem;font-size:.74rem;color:var(--fg3);font-family:"Geist Mono";letter-spacing:.12em;text-transform:uppercase}footer a{color:var(--fg2);display:block;margin:.3rem 0}footer p a{display:inline;margin:0;color:var(--fg)}footer .avail{display:flex;flex-wrap:wrap;gap:.4rem;margin:.9rem 0 .6rem;padding:0;list-style:none}footer .avail li a{display:inline-block;margin:0;padding:.25rem .6rem;border:1px solid var(--line2);border-radius:999px;font-size:.78rem;color:var(--fg2);text-decoration:none}footer .avail li a:hover{color:var(--fg);border-color:var(--accent)}
.doc{max-width:780px;padding-top:5.6rem;padding-bottom:3rem}.doc h2{margin-top:2.4rem}.doc .toc{background:var(--bg3);border:1px solid var(--line);border-radius:12px;padding:1rem 1.25rem;margin:1.5rem 0}.doc .toc a{color:var(--fg2)}
.logos{display:flex;gap:.7rem;flex-wrap:wrap;align-items:center;color:var(--fg2);font-weight:500;font-size:.88rem}.logos span{border:1px solid var(--line2);background:rgba(169,180,214,.04);padding:.5rem .9rem;border-radius:999px}
html,body{overflow-x:hidden;max-width:100%}.card,.g2>*,.g3>*,.g4>*,.price>*,.cols>*{min-width:0}.card pre{max-width:100%;white-space:pre-wrap;overflow-wrap:anywhere}.doc a,.doc code{overflow-wrap:anywhere}.doc table{display:block;overflow-x:auto;max-width:100%}footer .cols>div{min-width:0}.ticker{display:flex;align-items:center;max-width:100vw}.tk-label{flex:none;margin:0 1rem 0 var(--pad,1.25rem);padding:.15rem .55rem;border:1px solid var(--line2);border-radius:999px;font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:var(--fg3)}.tk-wrap{flex:1;overflow:hidden;white-space:nowrap}
@media(max-width:900px){table{display:block;overflow-x:auto;max-width:100%}.hero-inner{grid-template-columns:1fr;gap:2rem}.hero{padding-top:5rem}.g3,.g4,.g2,.price{grid-template-columns:1fr}footer .cols{grid-template-columns:1fr 1fr;gap:1.5rem}footer .cols>div:first-child{grid-column:1/-1}.nav nav{display:none}.nav .btn{margin-left:auto}.tk-label{display:none}}
.roster-pad main>section:first-child{padding-top:5.6rem}
@media(prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none}.tk-track,.eyebrow i{animation:none}}
'''

SIGNUP_JS = '''
const API="__API__";
async function signup(e){e.preventDefault();const k=document.getElementById('keybox');k.classList.add('show');k.innerHTML='<pre>…</pre>';
try{const r=await fetch(API+'/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('em').value,source:location.pathname,ref:document.referrer})});
const j=await r.json();if(!r.ok){k.innerHTML='<div class="alertbox">'+(j.detail||('Error '+r.status))+'</div>';return}
if(j.sent){k.innerHTML='<div class="alertbox">This address already has an account. We just e-mailed a fresh key to it (the old one stopped working). Check your inbox, then <a href="/app">open the dashboard</a>.</div>';return}
k.innerHTML='<pre><span class="d"># Your key, shown once. Store it now.</span>\\nexport RUNVOUCH_KEY=<span class="k">'+j.api_key+'</span>\\nexport RUNVOUCH_URL='+API+'\\n\\n<span class="d"># Install the client, register an agent, wrap your job</span>\\npip install runvouch   <span class="d"># or: curl -fsSL https://runvouch.com/rv -o ~/bin/rv</span>\\nrv agent nightly-report --cadence 24h --cap-run-cost 2 --evidence\\nrv run nightly-report --evidence-file out/report.html -- claude -p "build tonight\\'s report"</pre><p class="small muted">Free plan: 3 agents, no card. <a href="/app">Open the dashboard</a> and paste the key.</p>'}
catch(err){k.innerHTML='<div class="alertbox">Network error: '+err+'</div>'}return false}

(function(){const hero=document.querySelector('.hero');if(hero){const setH=()=>document.documentElement.style.setProperty('--bandh',(hero.offsetTop+hero.offsetHeight)+'px');setH();addEventListener('resize',setH)}else{document.documentElement.style.setProperty('--bandh','360px')}
document.querySelectorAll('main section > .wrap > h2, main section .card, main .doc h2, main .doc table, main .doc pre, main .doc .card, main .price .card').forEach(el=>el.classList.add('reveal'));const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.12});setTimeout(()=>document.querySelectorAll('.reveal').forEach(el=>el.classList.add('in')),1800);document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
const c=document.getElementById('sig');if(!c||matchMedia('(prefers-reduced-motion: reduce)').matches)return;const x=c.getContext('2d');let W,H,D=devicePixelRatio,lanes=[],P=[],t=0;
if(c.dataset.mode==='roster'){/* day roster (names are real agents from our own fleet, see /stats): rows are agents, columns are the 24 hours of one day; fills like a clock over about 16 s, rests 10 s, then a new day (slower on purpose: it is background, not a show). green vouched, amber missed or unproven, red failed */
let S=[],cols=24,rows=3,pw=0,ph=0,gx=0,gy=0,x0=0,y0=0,tick=0,maxAt=0;
const COL={ok:'#3DDC84',warn:'#F5B547',fail:'#FF6B6B'},POOL=['performance-build','streams-refresh','blog-queue','trackrecord','indexnow-ping','digest-weekly','alerts-pro','smoke-chain','refresh-formd','db-backup','quality-round','subscribers-sync'];let NAMES=POOL.slice(0,3);
function RR(){W=c.width=c.offsetWidth*D;H=c.height=c.offsetHeight*D;const narrow=c.offsetWidth<700;rows=narrow?2:3;x0=(narrow?12:110)*D;const avail=W-x0-16*D;gx=Math.max(3*D,avail*0.012);pw=(avail-gx*(cols-1))/cols;ph=7*D;gy=20*D;y0=(narrow?84:92)*D;S=[];maxAt=0;
NAMES=POOL.slice().sort(()=>Math.random()-0.5).slice(0,3);for(let r=0;r<rows;r++)for(let i=0;i<cols;i++){const u=Math.random();const at=i*40+r*6;maxAt=Math.max(maxAt,at);S.push({r,i,kind:u<0.86?'ok':u<0.95?'warn':'fail',at})}tick=0}
RR();addEventListener('resize',RR);
function drawR(){tick++;x.clearRect(0,0,W,H);x.font=`${10*D}px Geist Mono, monospace`;x.textAlign='left';
if(c.offsetWidth>=700){x.fillStyle='rgba(169,180,214,.5)';NAMES.slice(0,rows).forEach((l,r)=>x.fillText(l,x0-100*D,y0+r*gy+ph))}
x.fillStyle='rgba(169,180,214,.38)';[0,6,12,18,24].forEach(h=>{const px=x0+Math.min(h,cols-1)*(pw+gx)+(h===24?pw:0);x.textAlign=h===24?'right':'left';x.fillText((h<10?'0'+h:h)+':00',px,y0-9*D)});
for(const s of S){const px=x0+s.i*(pw+gx),py=y0+s.r*gy;x.fillStyle='rgba(169,180,214,.09)';x.fillRect(px,py,pw,ph);
if(tick>s.at){const k=Math.min(1,(tick-s.at)/24);x.globalAlpha=0.62*k;x.shadowColor=COL[s.kind];x.shadowBlur=(s.kind==='ok'?0:10)*D;x.fillStyle=COL[s.kind];x.fillRect(px,py,pw*k,ph);x.shadowBlur=0;x.globalAlpha=1}}
const sweep=Math.min(tick,maxAt)/40;const sx=x0+Math.min(sweep,cols)*(pw+gx);if(tick<=maxAt+24){x.fillStyle='rgba(238,242,255,.35)';x.fillRect(sx,y0-4*D,1*D,rows*gy)}
x.textAlign='right';x.fillStyle='rgba(169,180,214,.42)';x.fillText(c.offsetWidth<700?'our own jobs, every hour checked':'one day, three of our own jobs, every hour checked',W-16*D,y0+rows*gy+4*D);
if(tick>maxAt+24+600){RR()}requestAnimationFrame(drawR)}
drawR();return}
function R(){W=c.width=c.offsetWidth*D;H=c.height=c.offsetHeight*D;const n=Math.max(4,Math.floor(H/(110*D)));lanes=Array.from({length:n},(_,i)=>(i+.6)*H/n);P=[];for(let i=0;i<n*2;i++)add(true)}
function add(rand){const y=lanes[Math.floor(Math.random()*lanes.length)];P.push({x:rand?Math.random()*W:-30*D,y,y0:y,v:(0.35+Math.random()*0.5)*D,life:0,fail:Math.random()<0.14,failAt:600+Math.random()*900,vy:0,trail:[]})}
R();addEventListener('resize',R);
function draw(){x.clearRect(0,0,W,H);x.lineWidth=1*D;x.strokeStyle='rgba(169,180,214,.11)';for(const y of lanes){x.beginPath();x.moveTo(0,y);x.lineTo(W,y);x.stroke()}
if(t%95===0)add(false);
for(const p of P){p.life++;const dropping=p.fail&&p.life>p.failAt;
if(dropping){p.vy+=0.045*D;p.y+=p.vy;p.x+=p.v*0.6}else{p.x+=p.v;p.y=p.y0+Math.sin(t*0.02+p.x*0.002)*1.2*D}
p.trail.push([p.x,p.y]);if(p.trail.length>46)p.trail.shift();
const col=dropping?'255,99,99':'62,207,142';
for(let i=1;i<p.trail.length;i++){const a=(i/p.trail.length)*(dropping?.7:.5);x.strokeStyle=`rgba(${col},${a})`;x.lineWidth=(dropping?2.6:2.2)*D;x.beginPath();x.moveTo(...p.trail[i-1]);x.lineTo(...p.trail[i]);x.stroke()}
const g=x.createRadialGradient(p.x,p.y,0,p.x,p.y,18*D);g.addColorStop(0,`rgba(${col},.95)`);g.addColorStop(.3,`rgba(${col},.4)`);g.addColorStop(1,`rgba(${col},0)`);x.fillStyle=g;x.beginPath();x.arc(p.x,p.y,18*D,0,7);x.fill();
x.fillStyle=dropping?'#FFC8C8':'#EAFFF4';x.beginPath();x.arc(p.x,p.y,3*D,0,7);x.fill();
if(dropping&&p.vy>0.3*D&&p.vy<0.36*D){x.strokeStyle='rgba(255,99,99,.5)';x.lineWidth=1.2*D;x.beginPath();x.arc(p.x,p.y,14*D,0,7);x.stroke()}}
P=P.filter(p=>p.x<W+40*D&&p.y<H+40*D);t++;requestAnimationFrame(draw)}draw()})();
document.querySelectorAll('a[data-ls]').forEach(a=>a.addEventListener('click',()=>{const e=(document.getElementById('em')||{}).value;if(e)a.href=a.href.split('?')[0]+'?'+a.dataset.ls+'='+encodeURIComponent(e)}));
'''.replace("__API__", API)


def head(title, desc, path, jsonld=None, article=False):
    ld = json.dumps(jsonld, ensure_ascii=False) if jsonld else ""
    icon_v = hashlib.sha1(LOGO_SVG.encode()).hexdigest()[:8]  # verandert mee met het logo, zodat een oud favicon niet een jaar in de browsercache blijft
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0B1020">
<title>{title}</title><meta name="description" content="{desc}"><link rel="canonical" href="{BASE}{path}">
<meta property="og:type" content="{'article' if article else 'website'}"><meta property="og:site_name" content="RunVouch"><meta property="og:title" content="{title}"><meta property="og:description" content="{desc}"><meta property="og:url" content="{BASE}{path}"><meta property="og:image" content="{BASE}/og.png"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/logo.svg?v={icon_v}" type="image/svg+xml"><link rel="icon" href="/favicon.png?v={icon_v}" type="image/png" sizes="64x64"><link rel="apple-touch-icon" href="/favicon.png?v={icon_v}"><link rel="alternate" type="application/rss+xml" title="RunVouch changelog" href="/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@500;600;700&family=Figtree:wght@400;500;600&family=Geist+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.{CSS_HASH}.css"><noscript><style>.reveal{{opacity:1;transform:none}}</style></noscript>{('<script type="application/ld+json">'+ld+'</script>') if ld else ''}{ANALYTICS}</head><body{(' class="roster-pad"' if path != '/' else '')}>
<div class="ambient" aria-hidden="true"><span class="blob b1"></span><canvas id="sig" class="sig" data-mode="roster"></canvas></div>
<header class="top"><div class="wrap nav"><a class="brand" href="/">{LOGO_SVG}RunVouch</a><nav><a href="/#how">How it works</a><a href="/docs/">Docs</a><a href="/integrations/">Integrations</a><a href="/vs/">Compare</a><a href="/pricing">Pricing</a><a href="/blog/">Blog</a><a href="https://github.com/runvouch">GitHub</a></nav><a class="btn" href="/#start">Get a free key</a></div></header>'''


SAASHUB_BADGE = ('<p style="margin:.8rem 0"><a href="https://www.saashub.com/runvouch?utm_source=badge&amp;utm_campaign=badge&amp;utm_content=runvouch&amp;badge_variant=color&amp;badge_kind=approved"'
                 ' target="_blank" rel="noopener"><img alt="RunVouch is approved on SaaSHub" width="150" height="50" loading="lazy" src="/assets/saashub-approved.png"></a></p>')
PH_BADGE = '<p style="margin:.8rem 0"><a class="ph-badge" href="https://www.producthunt.com/products/runvouch?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-runvouch" target="_blank" rel="noopener noreferrer"><img alt="RunVouch - Dead man\'s switch + cost cap for unattended AI agents | Product Hunt" width="250" height="54" loading="lazy" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1232338&amp;theme=dark&amp;t=1787690858298"></a></p>' if datetime.date.today() >= datetime.date(2026, 9, 1) else ''
FOOTER = f'''<footer><div class="wrap"><div class="cols"><div><div class="brand" style="display:flex;align-items:center;gap:.5rem;font-family:"Instrument Sans";font-weight:700;color:var(--fg)">{LOGO_SVG.replace('width="64" height="64"','width="24" height="24"')}RunVouch</div>
<p class="small" style="margin-top:.6rem">The watchdog for unattended AI agents: proof they did the job, and an alert the moment they don't, or start spending. (For the ops crowd: a dead man's switch, cost cap and outcome check.)</p>
{PH_BADGE}{SAASHUB_BADGE}
<ul class="avail" aria-label="Available on"><li><a href="https://pypi.org/project/runvouch/">PyPI</a></li><li><a href="https://www.npmjs.com/package/runvouch">npm</a></li><li><a href="https://github.com/runvouch/vouch-action">GitHub Action</a></li><li><a href="https://github.com/runvouch/claude-plugin">Claude Code plugin</a></li><li><a href="https://registry.modelcontextprotocol.io/?search=runvouch">MCP Registry</a></li><li><a href="https://smithery.ai/servers/runvouch/runvouch">Smithery</a></li><li><a href="https://glama.ai/mcp/servers/runvouch/runvouch">Glama</a></li></ul>
<p class="small muted">© {datetime.date.today().year} RunVouch · Netherlands · <a href="/contact">contact</a><br>Built by the team behind <a href="https://datasignalslab.com" rel="noopener">DataSignals Lab</a>, whose nightly pipelines it watches.</p></div>
<div><h4>Product</h4><a href="/#how">How it works</a><a href="/verifiable-agent-runs">Verifiable agent runs</a><a href="/for-agencies">For agencies</a><a href="/pricing">Pricing</a><a href="/blog/">Blog</a><a href="/app">Dashboard</a><a href="/changelog">Changelog</a><a href="/status">Status</a></div>
<div><h4>Docs</h4><a href="/integrations/">All integrations</a><a href="/docs/claude-code">Claude Code</a><a href="/docs/cron">Cron &amp; scripts</a><a href="/docs/python-node">Python &amp; Node</a><a href="/docs/github-actions">GitHub Actions</a><a href="/docs/openclaw">OpenClaw</a><a href="/docs/n8n">n8n</a><a href="/docs/templates">Agent templates</a><a href="/docs/proof">Verifiable runs</a><a href="/docs/alerts">Alert channels</a><a href="/docs/mcp">MCP server</a><a href="/docs/api">API</a></div>
<div><h4>Compare</h4><a href="/vs/">All comparisons</a><a href="/observability-or-watchdog">Which tool do I need</a><a href="/self-hosted">Self-hosted</a><a href="/verify">Verify a run</a><a href="/fleet/datasignals">A live fleet</a><a href="/eu-ai-act">EU AI Act</a><a href="/vs/healthchecks">vs Healthchecks.io</a><a href="/vs/cronitor">vs Cronitor</a><a href="/vs/langfuse">vs Langfuse</a><a href="/how-often-jobs-fail">How often jobs fail</a><a href="/stats">In numbers</a><a href="/security">Security</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a></div></div></div></footer>
<script>{SIGNUP_JS}</script></body></html>'''


ORG_LD = {"@context": "https://schema.org", "@type": "Organization", "name": "RunVouch", "url": BASE, "logo": BASE + "/logo.svg", "contactPoint": {"@type": "ContactPoint", "url": "https://runvouch.com/contact", "contactType": "customer support"}}
APP_LD = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "RunVouch", "url": BASE, "applicationCategory": "DeveloperApplication", "operatingSystem": "Any",
          "description": "RunVouch is the watchdog for unattended AI agents: a dead man's switch, cost cap and outcome check (Claude Code Routines, headless claude -p, OpenClaw, n8n, cron). It alerts within minutes when a scheduled agent is missing, failed, looping, over budget, drifting, or reported success without evidence. Every finished run gets a tamper-evident proof: a hashed record, a public daily Merkle chain and a Bitcoin anchor via OpenTimestamps.",
          "offers": [{"@type": "Offer", "price": "0", "priceCurrency": "USD", "name": "Free"}, {"@type": "Offer", "price": "19", "priceCurrency": "USD", "name": "Solo"}, {"@type": "Offer", "price": "99", "priceCurrency": "USD", "name": "Team"}]}

CSS_HASH = hashlib.sha1(CSS.encode()).hexdigest()[:8]
PAGES: dict[str, tuple[str, str, str]] = {}  # path -> (title, desc, body)


def _colour_tables(body):
    """Comparison tables: only the RunVouch column (last cell of a row) gets colour, green for yes, muted for no.
    Competitor cells stay neutral: honest, but the eye lands on our column."""
    def row(m):
        cells = re.findall(r'<td[^>]*>.*?</td>', m.group(0), re.S)
        if len(cells) < 3 or ' id="' in m.group(0):
            return m.group(0)  # live tables (status page) keep their ids; only comparison tables get coloured
        out = []
        for i, c in enumerate(cells):
            txt = re.sub(r'<[^>]+>', '', c).strip().lower()
            c = re.sub(r'<td[^>]*>', '<td>', c, count=1)
            if i == len(cells) - 1:
                if txt.startswith("yes"): c = c.replace('<td>', '<td class="y">', 1)
                elif txt.startswith("no"): c = c.replace('<td>', '<td class="n">', 1)
            out.append(c)
        return "<tr>" + "".join(out) + "</tr>"
    return re.sub(r'<tr>(?:(?!</tr>).)*?<td(?:(?!</tr>).)*</tr>', row, body, flags=re.S)


def page(path, title, desc, body, ld=None, article=False):
    body = _colour_tables(body)
    html = head(title, desc, path, ld, article) + body + FOOTER
    if path == "/":
        p = OUT / "index.html"
    else:
        p = OUT / path.strip("/")
        p = p / "index.html" if path.endswith("/") else p.with_suffix(".html")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    PAGES[path] = (title, desc, body)


# ───────────────────────── HOME ─────────────────────────
HOME = f'''
<main>
<section class="hero">
<div class="wrap hero-inner"><div>
<span class="eyebrow reveal"><i></i>watching agents that run while you sleep</span>
<h1 class="reveal">Know your agents did the job<br><span class="grad">before the bill tells you</span> they didn't.</h1>
<p class="lead reveal">A green run means the scheduler worked, not that the task got done. RunVouch watches agents that run while you sleep and tells you when a run is missed, fails quietly, loops, or blows its budget. Works with Claude Code Routines, headless <code>claude&nbsp;-p</code>, OpenClaw, n8n and cron. When it went right, you get a record you can verify without us.</p>
<div class="cta reveal"><a class="btn" href="#start">Get a free key</a><a class="btn ghost" href="/docs/claude-code">Read the docs →</a></div>
<div class="trust reveal"><span>no card</span><span>2-minute setup</span><span>email, Telegram, Slack, Discord, Teams or webhook</span><span>self-host (MIT)</span></div>
</div>
<div class="panel reveal" aria-label="Example RunVouch dashboard"><div class="bar"><i></i><i></i><i></i>&nbsp;example night · tonight an alert, next year a record</div>
<ul class="runs">
<li><span class="t">02:00 nightly-report</span><span class="m"><b>Missed.</b> Expected 02:00, nothing by 02:15</span><span class="pill bad">missed</span></li>
<li><span class="t">03:00 inbox-triage</span><span class="m">Exit 0, but <b>no evidence</b>: <code>digest.html</code> unchanged</span><span class="pill warn">unproven</span></li>
<li><span class="t">03:30 repo-janitor</span><span class="m"><b>Retry storm</b>: <code>cat CHANGELOG.md</code> ×41 in 4 min</span><span class="pill bad">loop</span></li>
<li><span class="t">04:00 price-scraper</span><span class="m">$0.41 · 12 tool calls · output 118 KB</span><span class="pill ok">vouched</span></li>
<li><span class="t">05:00 lead-enricher</span><span class="m">$7.90 this run · <b>daily cap $5 hit</b></span><span class="pill bad">budget</span></li>
</ul>
<div class="alertbox"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex:none;margin-top:.15rem"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg> <span><b>Telegram, 03:34 (example)</b>: repo-janitor: same tool + same input 41×. Each call looks fine; together it's a loop. <a href="/docs/api">Pause agent</a></span></div></div>
</div></section>
<a class="ticker" href="#how" aria-label="Example alerts"><span class="tk-label">examples</span><div class="tk-wrap"><div class="tk-track"><span><b>MISSED</b> nightly-report, no run started for 16 min</span><span><b>NO_EVIDENCE</b> inbox-triage, digest.html unchanged, <em>green ≠ done</em></span><span><b>RETRY_STORM</b> repo-janitor, 41× identical tool call</span><span><b>BUDGET_DAY</b> lead-enricher, <em>$7.90 &gt; cap $5.00</em></span><span><b>VOUCHED</b> price-scraper, $0.41, evidence ok</span><span><b>MISSED</b> nightly-report, no run started for 16 min</span><span><b>NO_EVIDENCE</b> inbox-triage, digest.html unchanged, <em>green ≠ done</em></span><span><b>RETRY_STORM</b> repo-janitor, 41× identical tool call</span><span><b>BUDGET_DAY</b> lead-enricher, <em>$7.90 &gt; cap $5.00</em></span><span><b>VOUCHED</b> price-scraper, $0.41, evidence ok</span></div></div></a>

<section class="alt"><div class="wrap">
<span class="kicker">the problem</span><h2>"It ran" is the <span class="grad">wrong question</span></h2>
<div class="grid g3">
<div class="card"><div class="big grad">$1,800</div><h3>in two nights</h3><p>A Max subscriber scheduled overnight Claude Code runs. Nobody noticed until the bill. A per-run cost cap stops this at $2.</p></div>
<div class="card"><div class="big grad">$437</div><h3>for 14,000 identical calls</h3><p>An agent got stuck on a missing file. Every single call looked normal in the logs; the pattern only exists across calls. That's a retry storm, RunVouch counts them and alerts at 8.</p></div>
<div class="card"><div class="big grad">0 bytes</div><h3>green run, empty report</h3><p>The routine "succeeded". The report it was supposed to publish never changed. Ping monitors can't see that. Evidence checks can.</p></div>
</div>
<p class="small muted" style="margin-top:1rem">Sources: <a href="https://github.com/anthropics/claude-code/issues/37686" rel="noopener">Claude Code issue #37686</a> ($1,800+ in two days) · <a href="https://dev.to/magicrails/i-let-my-ai-agent-run-overnight-it-cost-437-dd7" rel="noopener">"I let my AI agent run overnight, it cost $437"</a>. <a href="/blog/">Read the write-ups →</a></p>
</div></section>

<section id="how"><div class="wrap">
<span class="kicker">how it works</span><h2>Two lines around any job.<br><span class="grad">Eight detectors</span> behind it.</h2>
<div class="grid g3 steps">
<div class="card"><h3>Register the agent</h3><p>Name it, set how often it should run, what it may cost, and what proof counts as "done".</p><pre>rv agent nightly-report \\
  --cadence 24h --cap-run-cost 2 --evidence</pre></div>
<div class="card"><h3>Wrap the run</h3><p>Cron, systemd, GitHub Actions, a Routine, anything. Exit code, duration, output and evidence are captured automatically.</p><pre>rv run nightly-report \\
  --evidence-file out/report.html \\
  -- claude -p "build tonight's report"</pre></div>
<div class="card"><h3>Get told, not surprised</h3><p>Missed, failed, unproven, looping, over budget, drifting or stalled → Telegram, Slack, Discord, Teams or any webhook within minutes. Ask your MCP client "are my agents healthy?"</p><pre>rv status
nightly-report   ok   $0.41   0 alerts</pre></div>
</div>
</div></section>

<section class="alt" id="proof"><div class="wrap">
<span class="kicker">verifiable runs</span><h2>Prove what your agent did, <span class="grad">to anyone</span></h2>
<p class="muted">An alert tells you tonight. A proof tells an auditor, a customer or your future self next year. Every finished run gets one, on every plan, Free included.</p>
<div class="grid g3">
<div class="card"><h3>A record per run</h3><p>When a run ends, its facts (agent, start, end, status, cost, tokens, tool calls, evidence verdicts) become one JSON object and a sha256 leaf. Written once, never updated.</p></div>
<div class="card"><h3>A public daily chain</h3><p>Every UTC day the leaves of all runs form a Merkle root, chained to the previous day. The day file is public at <a href="https://api.runvouch.com/proof/">api.runvouch.com/proof/</a>, no login.</p></div>
<div class="card"><h3>A Bitcoin anchor</h3><p>Each day file is stamped with OpenTimestamps, so its existence is committed in a Bitcoin block. Check it with <code>ots verify</code>; no RunVouch code involved.</p></div>
</div>
<pre>rv proof RUN_ID --verify   <span class="d"># recomputes the leaf and the Merkle path against the public day file, exit 0 or 1</span></pre>
<p class="small muted"><a href="/verify"><b>Verify a real run in your browser</b></a>, no account: recompute the hashes and edit a field to watch it break. Who needs this: <a href="/verifiable-agent-runs">verifiable agent runs</a> · the mechanism, byte for byte: <a href="/docs/proof">docs/proof</a></p>
</div></section>


<section><div class="wrap">
<span class="kicker">platform reality</span><h2>Why a Routine alone <span class="grad">isn't enough</span></h2>
<p class="quote">"A green status means the routine ran — it does not mean the task in your prompt succeeded." (<a href="https://code.claude.com/docs/en/scheduled-tasks">Claude Code documentation, scheduled tasks</a>)</p>
<p class="muted">Platforms schedule your agent. None of them tell you it silently produced nothing, looped on a missing file, or crossed a daily budget. That is the whole job of RunVouch, and it works the same for Claude Code, OpenClaw, n8n and plain cron:</p>
<div class="grid g3">
<div class="card"><h3>Claude Code</h3><pre>RUNVOUCH_AGENT=nightly \\
claude -p "build the report"</pre><p>Plugin hooks report start, tools, cost, stop.</p></div>
<div class="card"><h3>OpenClaw / n8n</h3><pre>rv run inbox-agent --cap-day-cost 10 \\
  -- openclaw task run inbox</pre><p>Or two HTTP calls from any workflow.</p></div>
<div class="card"><h3>cron / scripts</h3><pre>0 2 * * * rv run etl \\
  --evidence-file out.parquet -- python3 etl.py</pre><p>Zero dependencies. Fails open.</p></div>
</div></div></section>
<section class="alt"><div class="wrap">
<span class="kicker">detectors</span><h2>What RunVouch <span class="grad">catches</span></h2>
<div class="grid g4">
<div class="card"><h3><span class="tag">MISSED</span></h3><p>Expected run never started. Dead scheduler, expired token, crash before the first line.</p></div>
<div class="card"><h3><span class="tag">FAILED</span></h3><p>Non-zero exit or explicit failure, with the last stderr lines in the alert.</p></div>
<div class="card"><h3><span class="tag">NO_EVIDENCE</span></h3><p>Run says ok, but the file didn't change, the URL 404s, the assertion is false. Green ≠ done.</p></div>
<div class="card"><h3><span class="tag">RETRY_STORM</span></h3><p>Same tool, identical input, N times in one run. The invisible loop that burns money.</p></div>
<div class="card"><h3><span class="tag">BUDGET</span></h3><p>Per-run and per-day cost or token caps. Alert, then pause the agent.</p></div>
<div class="card"><h3><span class="tag">DRIFT</span></h3><p>Duration or output size off its recent baseline, and outside the range this job has actually produced. The agent is quietly doing something else.</p></div>
<div class="card"><h3><span class="tag">STALLED</span></h3><p>Started, no end, no heartbeat past the max runtime. Hung on a prompt nobody will answer.</p></div>
<div class="card"><h3><span class="tag">COST</span></h3><p>Tokens and dollars per run, read straight from Claude Code transcripts. Weekly cost report per agent.</p></div>
<div class="card"><h3><span class="tag" style="color:var(--good);background:var(--good-soft)">PROOF</span></h3><p>Not a detector but a receipt: one hashed record per run, written once, that an auditor can check with a standalone script. <a href="/verifiable-agent-runs">Verify it yourself</a>.</p></div>
</div>
<h3 style="margin-top:2rem">What the alert looks like</h3>
<div class="grid g2">
<div class="panel"><div class="bar">Telegram · 02:16</div><div style="padding:1rem;font-size:.92rem">⚠️ <b>RunVouch [MISSED] nightly-report</b><br>no run started for 16 min (cadence 24h + grace). Scheduler dead, auth expired, or agent crashed before first ping.</div></div>
<div class="panel"><div class="bar">Slack · #agents · 05:02</div><div style="padding:1rem;font-size:.92rem">⚠️ <b>RunVouch [BUDGET_DAY] lead-enricher</b><br>24h cost 7.90 &gt; daily cap 5.00, <a href="#">pause agent</a> · <a href="#">view runs</a></div></div>
</div></div></section>

<section><div class="wrap">
<span class="kicker">integrations</span><h2>Works with what you <span class="grad">already run</span></h2>
<div class="logos"><span>Claude Code Routines</span><span>claude -p (headless)</span><span>Claude Code hooks</span><span>MCP</span><span>OpenClaw</span><span>n8n</span><span>cron / systemd</span><span>GitHub Actions</span><span>LangGraph</span><span>Python / Node / bash</span></div>
<p class="muted" style="margin-top:1rem">Native <a href="/docs/claude-code">Claude Code plugin</a> (hooks report start, every tool call and stop), an <a href="/docs/mcp">MCP server</a> so agents can check on each other, and a zero-dependency CLI for everything else.</p>
<p class="muted" style="margin-top:.6rem">Nothing to watch yet? Start from a <a href="/docs/templates">ready-made agent on official data</a>: a nightly 13F digest, Form D raises in your sector, or a weekly competitor hiring watch, each with evidence built in.</p>
</div></section>

<section class="alt"><div class="wrap">
<span class="kicker">compare</span><h2>Why not Healthchecks, Cronitor or <span class="grad">Langfuse</span>?</h2>
<table><tr><th></th><th>Ping monitors<br><span class="small">Healthchecks · Cronitor</span></th><th>Trace platforms<br><span class="small">Langfuse · LangSmith · Arize</span></th><th>RunVouch</th></tr>
<tr><td>Knows the job ran on time</td><td class="y">yes</td><td class="n">no</td><td class="y">yes</td></tr>
<tr><td>Knows the job actually <em>did</em> something (evidence)</td><td class="n">no</td><td class="n">no</td><td class="y">yes</td></tr>
<tr><td>Detects retry storms across tool calls</td><td class="n">no</td><td class="n">manual, in traces</td><td class="y">automatic</td></tr>
<tr><td>Hard cost cap per run / per day</td><td class="n">no</td><td class="n">threshold alerts, no cap</td><td class="y">yes + pause</td></tr>
<tr><td>Setup</td><td>1 URL</td><td>SDK in your code</td><td>2 lines or a plugin</td></tr>
<tr><td>Built for</td><td>ops teams, cron</td><td>ML teams debugging prompts</td><td>people running agents unattended</td></tr>
<tr><td>Price</td><td>$0–85/mo</td><td>per seat / per million spans</td><td>$0 · $19 · $99</td></tr></table>
<p class="small muted" style="margin-top:.8rem">Detailed comparisons: <a href="/vs/healthchecks">Healthchecks.io</a> · <a href="/vs/cronitor">Cronitor</a> · <a href="/vs/langfuse">Langfuse</a></p>
</div></section>

<section id="start"><div class="wrap">
<span class="kicker">pricing</span><h2>The alert is free. <span class="grad">The brake is $19.</span></h2>
<div class="price">
<div class="card"><h3>Free</h3><div class="n">$0</div><ul><li>3 agents</li><li>All 8 detectors</li><li>Email, Telegram, Slack, Discord, Teams &amp; webhook alerts</li><li>A cost cap alerts you, the agent keeps running</li><li>7-day history</li><li>Verifiable proof per run</li></ul><a class="btn ghost" href="#signup">Start free</a></div>
<div class="card hi"><h3>Solo</h3><div class="n">$19<small>/month</small></div><ul><li><b>A cost cap that refuses the next run</b></li><li>50 agents</li><li>90-day history</li><li>Weekly cost report</li><li>MISSED and FAILED alerts sent every time, no 10-minute cooldown</li><li>Verifiable proof per run</li></ul>{SOLO_BTN}</div>
<div class="card"><h3>Team</h3><div class="n">$99<small>/month</small></div><ul><li>1000 agents</li><li>90-day history</li><li>API export (CSV / JSON) for audits</li><li>Read-only dashboard for teammates (viewer keys)</li><li>PagerDuty incidents</li><li>Verifiable proof per run</li></ul>{TEAM_BTN}</div>
</div>
<p class="small muted" style="margin-top:1rem">Running these jobs for clients instead of yourself? <a href="/for-agencies">What an agency shows the client</a>.</p>
<div id="signup" style="margin-top:2rem"><h3>Get your key</h3><p class="muted">Only used to identify your account and match a future subscription. No newsletter, no card. Prices in USD, VAT handled at checkout by {PROCESSOR}; upgrade with the same email you sign up with.</p>
<form class="signup" onsubmit="return signup(event)"><input id="em" type="email" required placeholder="you@company.com" autocomplete="email"><button class="btn" type="submit">Get a free key</button></form>
<div id="keybox" class="keybox"></div></div>
</div></section>

<section class="alt faq"><div class="wrap"><span class="kicker">faq</span><h2>Questions</h2>
<details><summary>Why do you need my email for a free key?</summary><p>Because the key is the account. If you upgrade later, the payment is matched to the same email; if you lose the key, we can rotate it. We don't send marketing mail.</p></details>
<details><summary>What does $19 buy that Free does not have?</summary><p>The brake. On every plan a cost cap alerts you the moment a run crosses it. On Solo and Team the next run is refused as well, so a loop that bills by the token stops instead of running until morning. Free is three agents, all eight detectors and every alert channel, so you can see what RunVouch does before you pay for it.</p></details>
<details><summary>Does RunVouch see my prompts or data?</summary><p>No. It receives what your job reports: start/end, exit status, tool names and a hash of their input (for loop detection), cost/tokens, output size, and true/false evidence results. Evidence checks on files run on your machine; only the verdict is sent.</p></details>
<details><summary>What if RunVouch is down?</summary><p><code>rv run</code> fails open: your job still runs unmonitored and prints a warning. Monitoring must never break the thing it monitors.</p></details>
<details><summary>Can I self-host?</summary><p>Yes. The server is a single MIT-licensed Python file with SQLite. The hosted version is the same code plus alerts, backups and the dashboard.</p></details>
<details><summary>Where does it run?</summary><p>EU (Netherlands) infrastructure behind Cloudflare. Data stays in the EU.</p></details>
</div></section>
</main>'''

page("/", "RunVouch: the watchdog for unattended AI agents", "Proof your scheduled AI agents did the job, and an alert the moment they don't, or start spending. Claude Code Routines, headless claude -p, OpenClaw, n8n, cron.", HOME, [APP_LD, ORG_LD])
VERIFY_FAQ = [
    ("Does RunVouch make my agent compliant with the EU AI Act?", "No, and nobody can promise that with a tool. The Act introduces logging and record-keeping duties for providers and deployers of high-risk AI systems. RunVouch gives you one piece of that: a record per run that cannot be altered afterwards without it showing, and that an auditor can verify with a script rather than with your word. Whether your system is high-risk, and what else you must keep, is a question for your legal counsel."),
    ("What exactly is in the record?", "run_id, agent, account_id, started, ended, status, cost, tokens, tool_calls, output_bytes, evidence (name to true/false), evidence_ok, source, exit (when reported) and tool_events_hash, a hash over the ordered tool events (tool name, input hash, ok flag, timestamp). Nothing else. Prompts, model output, tool inputs and file contents never reach RunVouch, so they are not in it."),
    ("Can RunVouch change a record after the fact?", "Not without it showing. The leaf hash of the run is written in the same database transaction that ends the run, the leaves of the day are published in a public day file with a Merkle root, the root is chained to the previous day, and the day file is stamped in Bitcoin with OpenTimestamps. Changing one leaf changes the root that every other customer can see and that the Bitcoin attestation no longer matches."),
    ("Do I need to trust RunVouch to verify a proof?", "No. templates/verify_proof.py is a standalone Python 3 script, standard library only, that recomputes the leaf, the Merkle path, the day root and the chain hash. The Bitcoin anchor is checked with the open-source OpenTimestamps client: ots verify DATE.json.ots -f DATE.json. Neither step calls RunVouch code."),
    ("Which plans include proofs?", "All of them, including Free. Proofs are part of how runs are stored, not a feature we switch on. On Free the full run record is purged after 7 days, on Solo and Team after 90 days; the leaf hash stays in the public day file, so a proof you saved keeps verifying."),
    ("When is a proof final?", "A day is sealed a few minutes after UTC midnight and anchored in Bitcoin some hours later. For a run that ended today, the proof endpoint returns sealed: false and a live root; until the seal it is our word, not a proof. ots_status tells you whether the Bitcoin block is in yet."),
    ("What does the proof not prove?", "It does not show what the agent wrote. It shows that a run with these numbers and these evidence booleans ended at this time and was not edited afterwards. If your client reports wrong numbers, the proof preserves them faithfully. A run that never called run end (killed, stalled) has no leaf. OpenTimestamps proves existence before a block, not after."),
]
VERIFY_LD = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in VERIFY_FAQ]}
page("/verifiable-agent-runs", "Verifiable AI agent runs: a tamper-evident audit trail | RunVouch",
     "Prove what an AI agent did: a hashed record per run, a public daily Merkle chain, a Bitcoin anchor. Verify offline with a stdlib script. On every plan, Free included.",
     '''<main><div class="wrap doc"><p class="small muted"><a href="/">RunVouch</a> / Verifiable agent runs</p>
<h1>Prove what your AI agent did. <span class="grad">To anyone, without trusting us.</span></h1>
<p class="lead muted">A tamper-evident record for every run of an unattended agent: what ran, when, with which evidence, at what cost. Hashed the moment the run ends, chained in a public daily file, anchored in Bitcoin. An auditor verifies it with a 60-line script and the open-source OpenTimestamps client. Included on every plan, Free too.</p>
<p class="cta"><a class="btn" href="/#signup">Get a free key</a><a class="btn ghost" href="/verify">Verify a real run</a><a class="btn ghost" href="/docs/proof">Read the mechanism</a></p>

<h2 id="who">Who needs this, and why now</h2>
<p>An agent that runs while nobody watches produces two things: a result, and a claim that it produced the result. Until now the claim lived in a log file that the same team could edit. Three groups are starting to ask for more than that.</p>
<ul>
<li><b>Regulated teams.</b> The EU AI Act introduces logging and record-keeping duties: high-risk AI systems must be able to record events automatically over their lifetime (Article 12), and deployers must keep the logs the system generates for at least six months (Article 26). Most of those obligations apply from 2 August 2026 (source: <a href="https://artificialintelligenceact.eu/article/12/" rel="noopener">artificialintelligenceact.eu, Article 12</a> and <a href="https://artificialintelligenceact.eu/article/26/" rel="noopener">Article 26</a>). Whether your agent is high-risk is your counsel's call. If it is, a log you can alter is a weak log.</li>
<li><b>Customers who buy the output of an agent.</b> A nightly research digest, an enrichment pipeline, a report for a client: the buyer wants to know it ran on time, produced the file and cost what you said. A proof they can check beats an invoice line.</li>
<li><b>Anyone after an incident.</b> When a run went wrong, the first question is "what actually happened and when", and the second is "is this record the original". A record fixed at run end, chained with every other run of the day, answers the second question for good.</li>
</ul>
<p>Finance and compliance teams, internal audit, and engineers who have to hand something to those teams: this page is for you. RunVouch does not make anyone compliant. It gives you a record an auditor can verify themselves.</p>

<h2 id="how">How it works, in five lines</h2>
<ol>
<li>When a run ends, RunVouch builds one JSON object with the facts of the run and stores its sha256, the <em>leaf</em>. Written once, in the same transaction that ends the run.</li>
<li>Every UTC day, the leaves of all runs of all accounts form a Merkle tree. The top is the day <em>root</em>.</li>
<li><code>chain_hash = sha256(prev + ":" + date + ":" + root)</code> links the day to the previous day. First day: 64 zeros.</li>
<li>The day file (date, root, prev, chain hash, list of run_id and leaf) is public at <a href="https://api.runvouch.com/proof/">api.runvouch.com/proof/</a>. No login. Run ids are random; the file does not reveal who ran what.</li>
<li>The day file is stamped with OpenTimestamps, which commits its hash in a Bitcoin block. The <code>.ots</code> file sits next to the day file.</li>
</ol>
<pre>rv proof RUN_ID            <span class="d"># the proof JSON: record, leaf, Merkle path, root, chain hash, ots status</span>
rv proof RUN_ID --verify   <span class="d"># recomputes everything against the public day file; exit 0 or 1</span></pre>

<h2 id="record">What is in the record, and what is not</h2>
<p>The record has these keys and nothing else: <code>run_id, agent, account_id, started, ended, status, cost, tokens, tool_calls, output_bytes, evidence, evidence_ok, source, exit, tool_events_hash</code>. Evidence is a map of check names to true or false: the file changed, the URL returned 200, the assertion held. <code>tool_events_hash</code> covers the ordered tool events of the run: tool name, the input hash the client sent, ok flag, timestamp.</p>
<p><b>Not in it:</b> prompts, model output, tool inputs, file contents, log lines. RunVouch never receives those, so it cannot hash them. That is a limit and a feature at once: the proof shows that a run with these numbers and these evidence verdicts ended at this time and was not edited afterwards. It does not show what the agent wrote. If you need the content itself under seal, hash the output file on your side and pass that hash as an evidence check; it then becomes part of the record.</p>
<p>The record is built from what your client reported. If the client lies about cost, the proof preserves the lie faithfully. What the chain rules out is editing afterwards, by you or by us. The full list of limits is on <a href="/docs/proof#honest-limits">docs/proof</a>.</p>

<h2 id="verify">Verify without trusting RunVouch</h2>
<p>Two open tools, neither of them ours to run:</p>
<pre>curl -H "X-API-Key: rv_..." https://api.runvouch.com/v1/runs/RUN_ID/proof > proof.json
curl https://api.runvouch.com/proof/days/2026-08-25.json > day.json
python3 verify_proof.py proof.json day.json
PASS leaf hash matches the record
PASS merkle path leads to the root
PASS day file lists this run with this leaf
PASS day file root recomputed from its leaves
PASS chain hash of the day
VERIFIED</pre>
<p><a href="https://github.com/runvouch/runvouch/blob/main/templates/verify_proof.py">verify_proof.py</a> is Python 3, standard library only, about 60 lines you can read in full before you run it. Change one byte of the record and the first line reads FAIL with exit code 1. For the Bitcoin anchor:</p>
<pre>pip install opentimestamps-client
curl -O https://api.runvouch.com/proof/days/2026-08-25.ots
ots verify 2026-08-25.ots -f day.json</pre>
<p>With a local Bitcoin node this checks the block header itself; without one it tells you which block to look up in any explorer. A day whose <code>ots_status</code> still reads <code>pending</code> is sealed but not yet in a block; usually a matter of hours.</p>

<h2 id="pricing">Pricing</h2>
<p>Proofs are on every plan, including Free. They are part of how runs are stored, not an add-on. The plans differ in the number of agents, history and alert channels: <a href="/pricing">pricing</a>. On Free the full run record is purged after 7 days, on Solo and Team after 90; the leaf hash stays in the public day file, so a proof you saved keeps verifying after that.</p>

<span class="kicker" style="display:block;margin-top:2.6rem">faq</span><h2 id="faq" style="margin-top:.4rem">Questions an auditor will ask</h2>
<div class="faq">''' + "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in VERIFY_FAQ) + '''</div>

<hr style="border:0;border-top:1px solid var(--line);margin:2.5rem 0">
<h2>Start with one agent</h2>
<p class="muted">Wrap the job, let it run once, fetch the proof, hand it to whoever asked. Free for 3 agents, no card.</p>
<pre>pip install runvouch
rv agent nightly-report --cadence 24h --evidence
rv run nightly-report --evidence-file out/report.html -- claude -p "build tonight's report"
rv proof RUN_ID --verify</pre>
<p class="cta"><a class="btn" href="/#signup">Get a free key</a><a class="btn ghost" href="/docs/proof">The mechanism, byte for byte</a><a class="btn ghost" href="/blog/prove-what-your-ai-agent-did-audit-trail-for-unattended-agents">Field note with a real proof</a></p>
</div></main>''', [ORG_LD, VERIFY_LD])

PRICING_LD = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "RunVouch", "applicationCategory": "DeveloperApplication", "operatingSystem": "Any", "url": BASE + "/pricing",
              "description": "RunVouch watches unattended AI agents (Claude Code, OpenClaw, n8n, cron): alerts on missed, failed, looping, over-budget or unproven runs, and a verifiable, tamper-evident proof per run on every plan.",
              "offers": [{"@type": "Offer", "name": "Free", "price": "0", "priceCurrency": "USD", "description": "3 agents, all 8 detectors, e-mail, Telegram, Slack, Discord, Teams and webhook alerts, cost cap alerts, 7-day history, verifiable proof per run"},
                         {"@type": "Offer", "name": "Solo", "price": "19", "priceCurrency": "USD", "description": "50 agents, a cost cap that refuses the next run, 90-day history, weekly cost report, priority alerts, verifiable proof per run", "priceSpecification": {"@type": "UnitPriceSpecification", "price": "19", "priceCurrency": "USD", "billingDuration": "P1M"}},
                         {"@type": "Offer", "name": "Team", "price": "99", "priceCurrency": "USD", "description": "1000 agents, 90-day history, PagerDuty incidents, shared dashboard, API export, verifiable proof per run", "priceSpecification": {"@type": "UnitPriceSpecification", "price": "99", "priceCurrency": "USD", "billingDuration": "P1M"}}]}
# ───────────────────────── PRICING ─────────────────────────
PRICING_FAQ = '''<section class="alt faq"><div class="wrap"><span class="kicker">faq</span><h2>What the plans mean, exactly</h2>
<details><summary>What does "history" mean?</summary><p>How long RunVouch keeps your runs, tool events and acknowledged alerts: 7 days on Free, 90 days on Solo and Team. A purge runs once a day and deletes what is older than your window. Open alerts stay until you acknowledge them. Runs that are part of a sealed proof day keep their leaf hash, so <a href="/docs/proof">proofs still verify</a> after the full record is gone.</p></details>
<details><summary>What are priority alerts?</summary><p>Alerts of the same kind for the same agent are normally sent at most once per 10 minutes; repeats are stored and shown in the dashboard but not re-sent. On Solo and Team, MISSED and FAILED skip that cooldown and are delivered immediately, every time. The other kinds keep the cooldown on every plan.</p></details>
<details><summary>Which alert channels are in which plan?</summary><p>E-mail, Telegram, a Slack incoming webhook and a generic JSON webhook work on every plan, including Free. PagerDuty (Events API v2) is Team only: MISSED, FAILED, STALLED, BUDGET_RUN and BUDGET_DAY open an incident, and acknowledging the alert in RunVouch resolves it. Settings calls per channel: <a href="/docs/alerts">docs/alerts</a>.</p></details>
<details><summary>What is the shared dashboard?</summary><p>On Team you can create viewer keys (prefix rvv_). A viewer key opens the dashboard and can read agents, runs, alerts and the export, and acknowledge alerts. It cannot change settings, register agents or report runs. Revoke it any time; it stops working the moment the plan is no longer Team.</p></details>
<details><summary>What does the API export return?</summary><p><code>GET /v1/export?from=YYYY-MM-DD&amp;to=YYYY-MM-DD&amp;format=csv|json</code> streams every run of your account that started in that range: agent, run_id, started, ended, status, cost, tokens, tool_calls, evidence_ok and leaf_hash. Team only; Free and Solo get a 402 with a plain message.</p></details>
<details><summary>Why do you need my email for a free key?</summary><p>Because the key is the account. If you upgrade later, the payment is matched to the same email; if you lose the key, we can rotate it. We do not send marketing mail.</p></details>
<details><summary>Can I self-host?</summary><p>Yes. The server is a single MIT-licensed Python file with SQLite. The hosted version is the same code plus alerts, backups and the dashboard.</p></details>
</div></section>'''
AGENCY_FAQ = [
    ("Does this replace the n8n error workflow?", "No, and if one instance is all you run, the error workflow is free and enough. RunVouch watches from outside: it notices the run that never started, which is the failure an Error Trigger cannot see, and it does that across every client instance from one place."),
    ("Do I need access to the client's server?", "No. Anything that can call a URL can report: an HTTP Request node at the end of the workflow, a curl line in their cron, or the rv wrapper if you do control the box. The client keeps their instance, you keep the watch."),
    ("What do I show a client who asks whether it ran?", "A status page with the last 90 days per job, on your own link, and a proof file per run: a hashed record, chained into a public daily file and anchored in Bitcoin. They can verify it without trusting you or us."),
    ("What does it cost per client?", "Free covers three agents, which is one small client or your own first test. Solo is $19 a month for 50 agents and adds the cost cap that refuses the next run. Team is $99 for 1000 agents, a status page per client, PagerDuty, API export and read-only dashboards for people who should not hold your key."),
]
AGENCY_LD = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in AGENCY_FAQ]}
page("/for-agencies", "Monitoring for automation agencies: prove the client's jobs ran | RunVouch",
     "Watch every client's scheduled workflows from outside their n8n, cron or Claude Code setup: missed runs, silent failures, cost caps with a brake, and a verifiable proof file you can hand the client.",
     '''<main><div class="wrap doc"><p class="small muted"><a href="/">RunVouch</a> / For agencies</p>
<h1>The client's workflow went quiet in August. <span class="grad">You heard about it in September.</span></h1>
<p class="lead muted">You built the automation, handed it over, and you are still the one who gets called when it goes silent. The workflows live in instances you do not control, on schedules set months ago, for people who assume that no news is good news. RunVouch watches them from the outside and gives you something to show when the question comes.</p>
<p class="cta"><a class="btn" href="/#signup">Get a free key</a><a class="btn ghost" href="/fleet/datasignals">See a live client page</a><a class="btn ghost" href="/contact?topic=agency">Talk to us</a></p>

<h2 id="blind">The failure your error handling cannot see</h2>
<p>A failed run is the easy case: the error workflow fires, Slack lights up, you fix it. The expensive case is the run that never happened. A workflow someone deactivated during a test, a schedule that did not survive an upgrade, a token that expired, a container that never came back after a reboot. None of those produce a failed execution, because none of them produce an execution at all. The execution list stays clean, the error workflow stays quiet, and the report the client pays for is simply not there. Weeks later they ask, and you are explaining instead of invoicing.</p>
<p>The same hole exists outside n8n. Cron does not care whether your job ran; it only cares that it fired the command. A headless agent that exits 0 after writing nothing looks exactly like a good night.</p>

<h2 id="watch">What RunVouch watches, per client</h2>
<ul>
<li><b>MISSED.</b> You declare the cadence and a grace window. Nothing checked in by then is an alert, whatever the reason.</li>
<li><b>FAILED.</b> Non-zero exit with the last lines of stderr, so you know what to open before you log in.</li>
<li><b>NO_EVIDENCE.</b> The run went green, but the file, row or URL it exists for did not change. This is the one that protects the client relationship: green is not done.</li>
<li><b>BUDGET.</b> A cap per run and per day. On a paid plan the next run is refused instead of billed, which matters when the workflow calls a model in a loop.</li>
<li><b>RETRY_STORM, DRIFT, STALLED.</b> The same tool call forty times, a job that suddenly finishes in a tenth of the usual time, a run that started and never ended.</li>
</ul>

<h2 id="hand">What you hand the client</h2>
<p>Two things they can check without taking your word for it. A status page per client on a link you share, with the last run and the 90-day record per job. And a proof per run: a hashed record fixed when the run ends, chained into a public daily file and anchored in Bitcoin through OpenTimestamps. Our own fleet runs on it in public: <a href="/fleet/datasignals">a real fleet page</a>, and the mechanism is written out on <a href="/verifiable-agent-runs">verifiable agent runs</a>. A client who has been burned before does not want a screenshot of a dashboard. They want a record that nobody could edit afterwards.</p>
<p>One page per client, two calls, nothing else to configure. Each job sits on exactly one page, so Acme never sees Globex:</p>
<pre>curl -X POST https://api.runvouch.com/v1/fleets -H "X-API-Key: $RUNVOUCH_KEY" \\
  -d '{"slug":"acme","title":"Acme nightly jobs"}'
curl -X POST https://api.runvouch.com/v1/fleets/acme/agents -H "X-API-Key: $RUNVOUCH_KEY" \\
  -d '{"agent":"acme-nightly-report","label":"Nightly report"}'</pre>
<p class="small muted">The page is public JSON at <code>/public/fleet/acme.json</code>: run facts only, no cost, no evidence, no keys. Drop it in your own client portal or link it as is. Client pages are part of Team.</p>

<h2 id="setup">Setting it up on an instance you do not own</h2>
<p>Every agent gets a ping URL. At the end of the client workflow, one HTTP Request node to the success URL; on the error path, one to the /fail URL. That is the whole integration, and it works on their cloud instance, their VPS or their laptop. Where you do control the machine, wrap the command instead and you get cost, duration and evidence for free:</p>
<pre>rv agent acme-nightly-report --cadence 24h --cap-run-cost 2 --evidence
rv run acme-nightly-report --evidence-file /srv/acme/report.html -- python build_report.py</pre>
<p>Guides per platform: <a href="/docs/n8n">n8n</a>, <a href="/docs/cron">cron and systemd</a>, <a href="/docs/claude-code">Claude Code</a>, <a href="/integrations/">everything else</a>.</p>

<h2 id="honest">Where this is not the right tool</h2>
<p>If you run one instance and you only need to hear about failed executions, n8n's own error workflow does that and costs nothing. If you need traces of every prompt and token to debug an agent's reasoning, you want an observability tool and we link to <a href="/vs/langfuse">the comparison</a>. RunVouch is the outside watch: it tells you that something did not happen, and it gives you the record that it did when it did.</p>

<h2 id="price">What it costs</h2>
<p>Free is three agents with all eight detectors and every alert channel, no card, enough to put your own worst job under it tonight. Solo is $19 a month for 50 agents and adds the cap that refuses the next run. Team is $99 for 1000 agents, a public status page per client, PagerDuty, CSV and JSON export for audits, and read-only dashboards for people who should not hold your key. Full detail on <a href="/pricing">pricing</a>.</p>
<h2 id="faq">Questions agencies ask</h2>
<div class="faq">''' + "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in AGENCY_FAQ) + '''</div>
<p class="cta"><a class="btn" href="/#signup">Start free</a><a class="btn ghost" href="/contact?topic=agency">Ask a question</a></p>
</div></main>''', [AGENCY_LD, ORG_LD])

page("/pricing", "RunVouch pricing: free for 3 agents, $19 Solo, $99 Team", "Simple pricing for agent monitoring: free for 3 agents with all detectors and all alert channels; Solo $19/month adds the cost cap that refuses the next run and 50 agents; Team $99/month for 1000 agents, PagerDuty, shared dashboard and API export.",
     HOME[HOME.index('<section id="start">'):HOME.index('<section class="alt faq">')].replace('<section id="start">', '<main><section id="start">').replace('<h2>', '<h1>', 1).replace('</h2>', '</h1>', 1) + PRICING_FAQ + '</main>', [ORG_LD, PRICING_LD])


# ───────────────────────── DOCS ─────────────────────────
def doc(path, title, desc, h1, intro, sections, howto_steps=None):
    toc = "".join(f'<li><a href="#{re.sub(r"[^a-z0-9]+","-",h.lower())}">{h}</a></li>' for h, _ in sections)
    body = f'<main><div class="wrap doc"><p class="small muted"><a href="/docs/">Docs</a> › {h1}</p><h1>{h1}</h1><p class="lead muted">{intro}</p><div class="toc"><b>On this page</b><ol>{toc}</ol></div>'
    for h, html in sections:
        body += f'<h2 id="{re.sub(r"[^a-z0-9]+","-",h.lower())}">{h}</h2>{html}'
    body += '<hr style="border:0;border-top:1px solid var(--line);margin:2.5rem 0"><p class="muted">Need a key? <a href="/#signup">Get a free key</a> · Stuck? <a href="/contact">contact</a></p></div></main>'
    ld = [ORG_LD]
    if howto_steps:
        ld.append({"@context": "https://schema.org", "@type": "HowTo", "name": h1, "step": [{"@type": "HowToStep", "name": s, "text": t} for s, t in howto_steps]})
    page(path, title, desc, body, ld, article=True)


doc("/docs/claude-code", "Monitor Claude Code Routines & headless claude -p runs | RunVouch docs",
    "Install the RunVouch plugin so every scheduled Claude Code run reports start, tool calls, cost and outcome. Catch silent failures, retry storms and runaway cost.",
    "Claude Code: Routines, headless runs and hooks",
    "RunVouch watches Claude Code agents that run without you: Routines, <code>claude -p</code> in cron, desktop scheduled tasks. The plugin uses Claude Code hooks to report the start, every tool call, and the stop, including tokens and cost read from the transcript.",
    [("Install the plugin", '''<pre>/plugin marketplace add runvouch/claude-plugin
/plugin install runvouch</pre><p>Or from a checkout: <code>claude --plugin-dir ./integrations/claude-code-plugin</code>. The plugin is a no-op in interactive sessions; it only reports when <code>RUNVOUCH_AGENT</code> is set.</p>'''),
     ("Wire a Routine or cron job", '''<pre><span class="d"># once: register the agent</span>
rv agent nightly-report --cadence 24h --cap-run-cost 2 --evidence

<span class="d"># in the Routine / cron environment</span>
export RUNVOUCH_KEY=rv_…
export RUNVOUCH_AGENT=nightly-report
export RUNVOUCH_EVIDENCE='{"report":{"type":"url","url":"https://example.com/reports/latest.html"}}'
claude -p "Generate tonight's report and publish it" --dangerously-skip-permissions</pre>
<p>What gets reported: <b>SessionStart</b> → run start · <b>PostToolUse</b> → tool name + input hash + error flag (retry-storm and budget checks run on every call) · <b>Stop</b> → run end with tokens and cost summed from the transcript, plus your evidence · <b>StopFailure</b> → run failed, with the API error type (rate_limit, authentication_failed, billing_error, server_error and the rest) · <b>SessionEnd</b> → run failed, when the session was killed or exited before the turn finished.</p><p>Read Stop as "Claude stopped responding", not as "the job is done": the hook cannot see what you wanted. An expired session or a rate limit at 03:00 now arrives as FAILED with the reason, and everything beyond that is what <code>RUNVOUCH_EVIDENCE</code> is for. Without evidence a finished session is the only thing RunVouch can vouch for.</p>'''),
     ("No client, just a URL", '''<p>Every agent has its own ping URL. Nothing to install, no header, no JSON: anything that can call a URL can report to RunVouch, from a crontab line to an n8n node, a GitHub Actions step or a Docker <code>HEALTHCHECK</code>.</p>
<pre><span class="d"># one line in your crontab: report the exit code of the job</span>
0 3 * * * /usr/local/bin/nightly.sh; curl -fsS -m 10 https://api.runvouch.com/ping/&lt;token&gt;/$?

<span class="d"># or bracket the job so RunVouch also sees how long it took</span>
0 3 * * * curl -fsS https://api.runvouch.com/ping/&lt;token&gt;/start; /usr/local/bin/nightly.sh &amp;&amp; curl -fsS https://api.runvouch.com/ping/&lt;token&gt;</pre>
<p>The suffixes: nothing for success, <code>/start</code> to open a run, <code>/fail</code> for a failure, or the exit code itself (<code>0</code> is success, anything else is a failure). GET, POST and HEAD all work. A POST body up to 100 kB is kept as the error excerpt on a failure. Ten pings per agent per minute.</p>
<p>The token is a write-only secret for that one agent: it can report runs and nothing else, so unlike your API key it can sit in a crontab or a shared workflow. <code>rv agent NAME</code> prints it, and it stays the same when you re-register the agent. A bare ping with no <code>/start</code> before it is a heartbeat: one run that begins and ends on the spot, which is all a dead man's switch needs.</p>'''),
     ("Evidence: prove the task happened", '''<p>Evidence turns "exit 0" into "done". Three forms:</p><ul><li><b>URL</b>: <code>{"type":"url","url":"…","expect":200}</code>, checked by RunVouch after the run.</li><li><b>File</b>: with <code>rv run --evidence-file PATH</code>: the file must exist, be non-empty and have changed during the run. Checked on your machine; only true/false is sent.</li><li><b>Boolean</b>: your own assertion: <code>{"rows_inserted": true}</code>.</li></ul><p>If <code>--evidence</code> is set on the agent and a run ends "ok" without passing evidence, you get a <code>NO_EVIDENCE</code> alert.</p>'''),
     ("Cost caps and retry storms", '''<p><code>--cap-run-cost 2</code> and <code>--cap-day-cost 10</code> alert the moment a run or a day crosses the line, and the agent is paused right there: the next <code>rv run</code> is refused and the command is not started. The run that crossed the line has already finished, so the cap stops the schedule, not the job in flight. Get it going again with <code>rv agent NAME --resume</code>. Only that explicit answer stops a command; if RunVouch is unreachable your job runs unmonitored, as everywhere else. Retry storms fire when the same tool is called with an identical input hash 8+ times in one run (configurable). Cost is computed from transcript usage with current Anthropic list prices; override with <code>RUNVOUCH_COST</code> / <code>RUNVOUCH_TOKENS</code> if you meter elsewhere. A job wrapped in <code>rv run</code> can also report what it spent by printing one line of its own, <code>RUNVOUCH_COST=1.25</code> (and <code>RUNVOUCH_TOKENS=</code>), which works from any language without a client. <code>rv run</code> also puts <code>RUNVOUCH_RUN_ID</code> in the job's environment, so the job can add tool calls or evidence to the run it is already in.</p>'''),
     ("Ask your agents about each other (MCP)", '''<pre>claude mcp add runvouch -e RUNVOUCH_KEY=rv_… -- python3 runvouch_mcp.py</pre><p>Tools: <code>runvouch_status</code>, <code>runvouch_alerts</code>, <code>runvouch_ack</code>, <code>runvouch_runs</code>, <code>runvouch_run_start</code>, <code>runvouch_run_end</code>. A morning agent can refuse to build on last night's output if last night is <code>UNPROVEN</code>. See <a href="/docs/mcp">MCP docs</a>.</p>''')],
    [("Install the plugin", "Add the RunVouch marketplace and install the plugin."), ("Register an agent", "rv agent NAME --cadence 24h --cap-run-cost 2 --evidence"), ("Set environment in the Routine", "RUNVOUCH_KEY, RUNVOUCH_AGENT, optional RUNVOUCH_EVIDENCE"), ("Run", "claude -p …, hooks report start, tool calls, cost and outcome.")])

doc("/docs/cron", "Monitor cron jobs, scripts and LLM batch jobs | RunVouch docs",
    "Wrap any cron job or script with rv run to get missed-run, failure, evidence, drift and cost alerts. Zero dependencies, fails open.",
    "Cron, systemd, GitHub Actions and plain scripts",
    "The <code>rv</code> client is a single Python file with no dependencies. It wraps a command, captures exit code, duration and output size, checks evidence files, and reports, and if RunVouch is unreachable your job still runs.",
    [("Install", '<pre>pip install runvouch   <span class="d"># or: curl -fsSL https://runvouch.com/rv -o ~/bin/rv</span>\nexport RUNVOUCH_KEY=rv_…   <span class="d"># put in ~/.profile or the cron env</span></pre>'),
     ("Wrap a job", '''<pre><span class="d"># crontab -e</span>
0 2 * * * rv run nightly-etl --log /var/log/etl.log --evidence-file /data/out/today.parquet -- python3 etl.py</pre><p><code>--log</code> appends the job's stdout/stderr to a file (and counts as evidence if it grew). <code>--evidence-file</code> requires the file to exist, be non-empty and be modified during the run.</p>'''),
     ("No client at all: the ping URL", '''<p>If you would rather not install anything, every agent has its own ping URL. Anything that can call a URL can report: a crontab line, an n8n node, a GitHub Actions step, a Docker <code>HEALTHCHECK</code>, a Zapier or Make action.</p>
<pre><span class="d"># report the exit code of the job, nothing installed</span>
0 3 * * * /usr/local/bin/nightly.sh; curl -fsS -m 10 https://api.runvouch.com/ping/&lt;token&gt;/$?

<span class="d"># bracket it so RunVouch also sees the duration and catches a job that never ends</span>
0 3 * * * curl -fsS https://api.runvouch.com/ping/&lt;token&gt;/start; /usr/local/bin/nightly.sh &amp;&amp; curl -fsS https://api.runvouch.com/ping/&lt;token&gt;</pre>
<p>Nothing after the token means success, <code>/start</code> opens a run, <code>/fail</code> reports a failure, and a number is the exit code (<code>0</code> is success). GET, POST and HEAD all work; a POST body up to 100 kB is kept as the error excerpt when the run failed. Ten pings per agent per minute.</p>
<p><code>rv agent NAME</code> prints the URL, and so does the dashboard. The token is a write-only secret for that one agent: it reports runs and can do nothing else, so it may sit in a crontab or a shared workflow where your API key never should. It survives re-registering the agent, because by then the URL lives in someone else's crontab.</p>
<p>What you give up without the client: no evidence file check, no automatic cost from a transcript, no output-size drift unless you POST the output. Cadence, MISSED, STALLED, FAILED and the daily cost cap all work the same.</p>'''),
     ("Hourly, weekly, monthly", '<pre>rv agent hourly-sync --cadence 1h --grace 10m\nrv agent weekly-digest --cadence 7d --grace 2h --max-runtime 30m</pre><p>MISSED fires when cadence + grace passes without a start; STALLED when a run exceeds max runtime without ending.</p>'),
     ("Report cost from any LLM job", '<pre>RID=$(rv start price-scraper)\nrv tool $RID openai.chat --input \'{"model":"gpt-5","prompt_hash":"…"}\' --cost 0.012 --tokens 4100\nrv end $RID --status ok --cost 0.35 --evidence \'{"rows": true}\'</pre><p>Per-call reporting enables retry-storm and per-run budget detection; per-run reporting is enough for daily caps and drift.</p>'),
     ("GitHub Actions", '<pre>- run: rv run nightly-build --evidence-file dist/report.html -- npm run build:report\n  env:\n    RUNVOUCH_KEY: ${{ secrets.RUNVOUCH_KEY }}</pre>')])

doc("/docs/python-node", "Python & Node clients, LangGraph, OpenAI Agents | RunVouch docs",
    "Report runs, tool calls, cost and evidence from Python or Node code: LangGraph, OpenAI Agents SDK, CrewAI, any script. Zero dependencies, fails open.",
    "Python & Node: LangGraph, OpenAI Agents SDK and any script",
    "Two single-file clients with no dependencies. Both fail open: if RunVouch is unreachable your code runs unmonitored and prints one warning.",
    [("Python", '''<pre><span class="d"># pip install runvouch   (or: curl -fsSL https://runvouch.com/runvouch.py -o runvouch.py)</span>
import os, runvouch
runvouch.agent("nightly-etl", cadence_s=86400, cap_run_cost=2, evidence_required=True)

with runvouch.vouch("nightly-etl", evidence=lambda: {"parquet": os.path.getsize("out.parquet") > 0}) as run:
    for f in files:
        run.tool("summarize", {"file": f}, cost=0.004)   <span class="d"># identical inputs 8x → RETRY_STORM</span>
        summarize(f)</pre><p>An exception inside the block ends the run as <code>fail</code> with the error text in the alert; a clean exit ends it as <code>ok</code> and evaluates your evidence.</p>'''),
     ("LangGraph", '''<pre>from langchain_core.callbacks import BaseCallbackHandler
import runvouch

class Vouch(BaseCallbackHandler):
    def __init__(self, run): self.run = run
    def on_tool_start(self, serialized, input_str, **kw):
        self.run.tool(serialized.get("name", "tool"), input_str)
    def on_llm_end(self, response, **kw):
        u = (response.llm_output or {}).get("token_usage", {})
        self.run.tool("llm", None, tokens=u.get("total_tokens", 0), cost=u.get("total_cost", 0))

with runvouch.vouch("research-graph", evidence=lambda: {"report": open("report.md").read() != ""}) as run:
    graph.invoke(state, config={"callbacks": [Vouch(run)]})</pre>'''),
     ("OpenAI Agents SDK", '''<pre>from agents import Runner
import runvouch

with runvouch.vouch("inbox-agent", evidence=lambda: {"replied": replied_count > 0}) as run:
    result = Runner.run_sync(agent, "Triage today's inbox")
    run.tool("openai.run", None, tokens=result.context_wrapper.usage.total_tokens)</pre><p>Per-tool reporting is optional; per-run cost and evidence are enough for daily caps, drift and "green ≠ done".</p>'''),
     ("Node", '''<pre><span class="d">// npm install runvouch   (Node 18+; or: curl -fsSL https://runvouch.com/runvouch.js -o runvouch.js)</span>
const rv = require('runvouch');
await rv.agent('nightly-report', { cadence_s: 86400, cap_run_cost: 2, evidence_required: true });

await rv.vouch('nightly-report', async (run) => {
  for (const page of pages) { await run.tool('fetch', { url: page }); await scrape(page); }
}, { evidence: async () => ({ report: fs.existsSync('out/report.html') }) });</pre>'''),
     ("CrewAI, AutoGen, anything else", '''<p>Wrap the entry point with <code>rv run</code> (no code changes) or use the two HTTP calls: <code>POST /v1/runs/start</code> and <code>POST /v1/runs/end</code>: see the <a href="/docs/api">API</a>. Cost from OpenRouter/OpenAI/Anthropic responses goes into <code>cost</code> on the end call.</p>''')],
    [("Install the client", "pip install runvouch (Python) or npm install runvouch (Node)"), ("Register the agent", "runvouch.agent(name, cadence_s=…, cap_run_cost=…, evidence_required=True)"), ("Wrap the job", "with runvouch.vouch(name, evidence=…) as run: …")])

doc("/docs/github-actions", "Monitor scheduled GitHub Actions | RunVouch docs", "A watchdog for scheduled GitHub Actions workflows: alerts when the schedule silently stops firing, the job fails, or it finishes green without doing the work.",
    "GitHub Actions", "GitHub disables scheduled workflows after 60 days without commits and never tells you; a cron job can also exit 0 without producing anything. RunVouch watches both: a MISSED alert when no run starts within the cadence, and NO_EVIDENCE when the output file was not written.",
    [("Add the action", '<pre>- uses: runvouch/vouch-action@v1\n  with:\n    agent: nightly-report\n    key: ${{ secrets.RUNVOUCH_KEY }}\n    cadence: 24h                 <span class="d"># MISSED if no run starts in 24h + grace</span>\n    evidence-file: out/report.html\n    run: python report.py --out out/report.html</pre><p>Store your key as a repository secret named <code>RUNVOUCH_KEY</code>. Fails open: if RunVouch is unreachable the step logs a warning and the job runs unmonitored.</p>'),
     ("Without the action", '<pre>- run: pip install runvouch\n- run: rv run nightly-report --evidence-file out/report.html -- python report.py\n  env: {{ RUNVOUCH_KEY: ${{ secrets.RUNVOUCH_KEY }} }}</pre>'),
     ("What you get", '<p>MISSED (schedule stopped), FAILED (non-zero exit), NO_EVIDENCE (green run, no output), plus cost caps if your script reports spend via the <a href="/docs/python-node">Python or Node client</a>. Source: <a href="https://github.com/runvouch/vouch-action">github.com/runvouch/vouch-action</a>.</p>')],
    [("Get a key", "Get a free key at runvouch.com and add it as the RUNVOUCH_KEY repository secret."), ("Add the step", "Add the runvouch/vouch-action@v1 step with agent, cadence, evidence-file and run."), ("Push", "The first run registers the agent. Alerts arrive via Telegram, Slack, e-mail or webhook.")])

doc("/docs/openclaw", "Monitor OpenClaw agents | RunVouch docs", "A watchdog for OpenClaw: detect crashed or looping OpenClaw agents, cap their spend, and get Telegram alerts.",
    "OpenClaw", "OpenClaw agents run continuously and call tools in loops. RunVouch treats each scheduled task or heartbeat window as a run, so polling loops and runaway spend show up within minutes.",
    [("Heartbeat pattern", '<pre>rv agent openclaw-main --cadence 15m --grace 5m --cap-day-cost 10\n<span class="d"># from a cron on the OpenClaw host, every 15 min:</span>\nrv run openclaw-main -- curl -fsS http://127.0.0.1:18789/health</pre><p>If the gateway stops answering, MISSED/FAILED fires. Add a daily cap to catch the "$150 polling loop".</p>'),
     ("Per-task runs via the HTTP API", '<pre>curl -X POST https://api.runvouch.com/v1/runs/start -H "X-API-Key: $RUNVOUCH_KEY" -d \'{"agent":"openclaw-inbox","source":"openclaw"}\'\n<span class="d"># … tool events … then</span>\ncurl -X POST https://api.runvouch.com/v1/runs/end -H "X-API-Key: $RUNVOUCH_KEY" -d \'{"run_id":"…","status":"ok","cost":0.21,"evidence":{"replied":true}}\'</pre><p>Or install the <b>RunVouch skill</b>: copy <a href="/openclaw/runvouch/SKILL.md">SKILL.md</a> into your OpenClaw skills directory (<code>~/.openclaw/skills/runvouch/</code>). It teaches the agent to check in at start, per tool call and at the end, with evidence.</p>'),
     ("The verified-run skill for scheduled tasks", '<p>For a task on a schedule, install <b>verified-run</b>: it wraps the task in start-run, task, end-run with the output file as evidence, and reports <code>fail</code> when the file is missing. Copy <code>integrations/openclaw/verified-run</code> into <code>~/.openclaw/skills/</code> (skill file: <a href="/openclaw/verified-run/SKILL.md">SKILL.md</a>, wrapper: <a href="/openclaw/verified-run/scripts/verified-run.sh">verified-run.sh</a>), set <code>RUNVOUCH_KEY</code>, then:</p><pre>0 7 * * * ~/.openclaw/skills/verified-run/scripts/verified-run.sh inbox-digest --every 24h --grace 30m --evidence-file ~/out/digest.md -- openclaw task run inbox-digest</pre><p>Install steps, plugin manifest and the companion skill: <a href="https://github.com/runvouch/runvouch/tree/main/integrations/openclaw">github.com/runvouch/runvouch/tree/main/integrations/openclaw</a>, and the <a href="/integrations/openclaw">integration page</a>.</p>')])

doc("/docs/n8n", "Monitor n8n AI workflows | RunVouch docs", "Catch n8n workflow failures your Error Workflow never sees, and track LLM cost per workflow run, with RunVouch.",
    "n8n", "Error Workflows only fire when a node errors. A workflow that runs, does nothing, and exits green is invisible. RunVouch adds expected-cadence, evidence and cost per run.",
    [("The community node", '<p>Install <b>n8n-nodes-runvouch</b> from <b>Settings, Community Nodes, Install</b>, add a RunVouch API credential with your key, and use two nodes: <b>Start Run</b> after the Schedule Trigger and <b>End Run</b> at the end with status and evidence, or a single <b>Heartbeat</b> node. The first run registers the agent with the cadence you set in the node. Source, README and an importable example workflow: <a href="https://github.com/runvouch/runvouch/tree/main/integrations/n8n-nodes-runvouch">integrations/n8n-nodes-runvouch</a>; details on the <a href="/integrations/n8n">integration page</a>.</p>'),
     ("Two HTTP Request nodes", '<p>At the start: <code>POST {API}/v1/runs/start</code> with header <code>X-API-Key</code> and body <code>{{"agent":"lead-enricher","source":"n8n"}}</code>; save <code>run_id</code>. At the end: <code>POST {API}/v1/runs/end</code> with status, cost (from your OpenAI/Anthropic node usage) and evidence such as <code>{{"rows_written": true}}</code>.</p>'.replace("{API}", API)),
     ("Cadence", '<pre>rv agent lead-enricher --cadence 1h --grace 15m --cap-day-cost 5</pre><p>Now a workflow that stops being triggered, or quietly returns nothing, alerts you.</p>')])

doc("/docs/templates", "Agent templates: nightly digests on official data, with evidence - RunVouch docs",
    "Three copy-paste agent templates: a nightly 13F consensus digest, Form D raises in your sector, and a weekly competitor hiring watch. Official SEC and career-site data via DataSignals Lab, wrapped in rv run with evidence and cost caps.",
    "Agent templates: nightly digests on official data, with evidence",
    'Three ready-to-run agents on official public data (SEC 13F, Form D, company career sites) from <a href="https://datasignalslab.com/datasignals-mcp.html">DataSignals Lab</a>. Each one writes a file, and RunVouch checks that the file actually changed, that the run started on time, and what it cost. Plain Python, standard library only, with a <code>claude -p</code> or n8n variant in every folder. Copy a folder, set two keys, done in two minutes.',
    [("What you need", '''<p>A RunVouch key (free for 3 agents) and, depending on the template, an <a href="https://console.apify.com/settings/integrations">Apify token</a> (free account; the DataSignals MCP server is free for the first 50 calls a month, then $0.20 per result on your own account) or a DataSignals Events API key (a permanent free plan exists: one stream, 250 events a month, 24 hours behind; <a href="https://datasignalslab.com/events-api.html#free-key">request it here</a>, the key arrives by e-mail). Nothing here needs a card. All templates: <a href="https://github.com/runvouch/runvouch/tree/main/templates">github.com/runvouch/runvouch/tree/main/templates</a>.</p>'''),
     ("1. Nightly 13F consensus digest", '''<p>Which stocks are the funds you follow buying? One MCP call a night (<code>hedge_fund_13f</code>, cross-fund consensus from SEC EDGAR 13F), a top 10 in <code>out/13f-digest.md</code>, and a diff against yesterday. Two flavours: <code>digest.py</code> (no Claude) or <code>prompt.md</code> for headless <code>claude -p</code>.</p><pre>rv agent nightly-13f-digest --cadence 24h --grace 2h --cap-run-cost 1 --evidence
rv run nightly-13f-digest --evidence-file out/13f-digest.md -- python3 digest.py --spend-cap 5
<span class="d"># or, with Claude Code and the MCP server registered via claude mcp add:</span>
rv run nightly-13f-digest --evidence-file out/13f-digest.md -- claude -p "$(cat prompt.md)" --dangerously-skip-permissions
<span class="d"># crontab</span>
15 2 * * * cd ~/templates/nightly-13f-consensus-digest &amp;&amp; rv run nightly-13f-digest --evidence-file out/13f-digest.md --log out/run.log -- python3 digest.py --spend-cap 5</pre><p>13F is quarterly with a 45 day lag, so most nights the digest says "No change"; the night a filing lands you see it, and every other night RunVouch confirms the agent ran and wrote the file. Folder: <a href="https://github.com/runvouch/runvouch/tree/main/templates/nightly-13f-consensus-digest">nightly-13f-consensus-digest</a>.</p>'''),
     ("2. Form D raises in my sector", '''<p>Who just raised private money in your industry? Reads the <code>private_raise</code> stream of the Events API since the last cursor, filters on your keywords (SEC industry group and issuer name), appends matches to <code>out/raises.jsonl</code> and sends a Telegram message when something matched. The evidence file is the cursor, which every successful run advances, so a quiet night still counts as proven. Needs a free Events API key.</p><pre>rv agent form-d-raises --cadence 24h --grace 2h --evidence
rv run form-d-raises --evidence-file out/cursor.txt -- python3 raises.py
<span class="d"># crontab</span>
30 6 * * * cd ~/templates/form-d-raises-in-my-sector &amp;&amp; rv run form-d-raises --evidence-file out/cursor.txt --log out/run.log -- python3 raises.py</pre><p>The folder also has <code>n8n-workflow.json</code>: Schedule, HTTP Request to <code>/v1/runs/start</code>, HTTP Request to the Events API (retry on 503 while the API wakes), Code node filter, If, Telegram, HTTP Request to <code>/v1/runs/end</code> with evidence. Folder: <a href="https://github.com/runvouch/runvouch/tree/main/templates/form-d-raises-in-my-sector">form-d-raises-in-my-sector</a>.</p>'''),
     ("3. Competitor hiring watch", '''<p>How many open roles do your competitors have this week, and who is suddenly hiring? One MCP call per company (<code>job_openings</code>, live from Greenhouse, Lever, Ashby and five more career-site platforms), a table in <code>out/hiring-YYYY-WW.md</code> with counts, top departments and the change versus last week, and an alert when a count is up more than 25 percent.</p><pre>rv agent competitor-hiring --cadence 7d --grace 6h --max-runtime 30m --cap-run-cost 5 --evidence
rv run competitor-hiring --evidence-file "out/hiring-$(date +%G-%V).md" -- python3 hiring.py --spend-cap 10
<span class="d"># crontab, Mondays 07:00</span>
0 7 * * 1 cd ~/templates/competitor-hiring-watch &amp;&amp; rv run competitor-hiring --evidence-file "out/hiring-$(date +\\%G-\\%V).md" --log out/run.log -- python3 hiring.py --spend-cap 10</pre><p>Folder: <a href="https://github.com/runvouch/runvouch/tree/main/templates/competitor-hiring-watch">competitor-hiring-watch</a>.</p>'''),
     ("What gets checked", '''<p><code>--evidence-file</code> passes only if the file exists, is non-empty and was modified during the run; only true/false is sent to RunVouch, never the content. <code>--cadence</code> plus <code>--grace</code> raises MISSED when no run starts in time. <code>--cap-run-cost</code> needs a reported cost: <code>rv run</code> does not know what Claude spent, so for the Claude Code flavour use the <a href="/docs/claude-code">plugin</a> (set <code>RUNVOUCH_AGENT</code> and <code>RUNVOUCH_EVIDENCE</code>) instead of <code>rv run</code>, not both. The DataSignals side has its own cap: <code>--spend-cap</code> makes the MCP server refuse calls once your ledger reaches that amount.</p>''')],
    [("Copy a folder", "cp -r templates/<slug> ~/templates/ and set RUNVOUCH_KEY plus the data key the README names."), ("Register the agent", "rv agent NAME --cadence 24h --evidence (7d for the weekly one)."), ("Run once by hand", "rv run NAME --evidence-file out/<file> -- python3 <script>.py, then read the output file."), ("Install the cron line", "Copy the line from crontab.txt; from now on MISSED, FAILED and NO_EVIDENCE alerts reach you on Telegram, Slack or webhook.")])

doc("/docs/proof", "Verifiable runs: prove what your agent did - RunVouch docs",
    "Every finished run gets a sha256 record, every UTC day a Merkle root chained to the previous day and stamped in Bitcoin with OpenTimestamps. Verify offline with a 60-line script; no trust in RunVouch needed.",
    "Verifiable runs: prove what your agent did",
    'When an agent ran unattended, "it worked" is a claim. A proof is better: a record of what ran, when, with which evidence and at what cost, fixed the moment the run ended, chained to every other run of that day, and anchored in the Bitcoin blockchain. Later you, an auditor or a customer can check that the record was not edited afterwards, without asking us. This page explains exactly what is hashed, what is not, and where the guarantee stops.',
    [("What is in the record", '''<p>At <code>POST /v1/runs/end</code> RunVouch builds one JSON object for the run and stores its sha256 (the <em>leaf</em>). The object has these keys and nothing else:</p>
<pre>run_id, agent, account_id, started, ended, status, cost, tokens, tool_calls, output_bytes,
evidence (name -> true/false), evidence_ok, source, exit (only when reported), tool_events_hash</pre>
<p><code>tool_events_hash</code> is the sha256 over the ordered list of tool events of the run: tool name, the input hash the client sent, ok flag and timestamp. The leaf is <code>sha256(canonical JSON)</code>, canonical meaning sorted keys, separators <code>,</code> and <code>:</code>, UTF-8. It is written once and never updated.</p>
<p><b>What is not in it:</b> prompts, model outputs, tool inputs, file contents, log lines. RunVouch never receives those, so they cannot be hashed. The proof shows that a run with these numbers and these evidence booleans ended at this time; it does not show what the agent wrote.</p>'''),
     ("The daily chain", '''<p>Every UTC day, a few minutes after midnight, the server seals the day that just ended:</p>
<ol><li>Take the leaves of all runs that ended that day (all accounts, sorted by run_id).</li><li>Build a Merkle tree: pairwise <code>sha256(left + right)</code> over the hex strings, an odd node is paired with itself, an empty day gives <code>sha256("")</code>. The top is the day <em>root</em>.</li><li><code>chain_hash = sha256(prev + ":" + date + ":" + root)</code>, where <code>prev</code> is the chain hash of the previous sealed day (64 zeros for the first one).</li><li>Write <code>/proof/days/DATE.json</code> with date, root, prev, chain_hash and the list of (run_id, leaf), publicly, without authentication.</li></ol>
<p>The chain is global on purpose: one public object per day for everyone, so changing one leaf of one account would change the root that every other customer can also see. The index of all sealed days is at <a href="https://api.runvouch.com/proof/">api.runvouch.com/proof/</a>. Run ids are random hex; the day file does not reveal who ran what.</p>'''),
     ("The Bitcoin anchor", '''<p>Right after writing the day file the server runs <code>ots stamp DATE.json</code> from the OpenTimestamps client. That submits the file hash to the public OpenTimestamps calendar servers, which aggregate hashes and commit them in a Bitcoin transaction. The resulting <code>DATE.json.ots</code> is served next to the day file. The status you see in <code>ots_status</code> means:</p>
<table><tr><th>ots_status</th><th>meaning</th></tr><tr><td><code>pending</code></td><td>stamped; the calendar has the hash, the Bitcoin block is not in yet. Usually a few hours.</td></tr><tr><td><code>bitcoin:NNNNNN</code></td><td>the .ots file was upgraded and contains an attestation from Bitcoin block NNNNNN.</td></tr><tr><td><code>ots missing</code> / <code>stamp failed: ...</code></td><td>the chain still works, but that day has no Bitcoin anchor. We do not hide this.</td></tr></table>
<p>Once a day the server runs <code>ots upgrade</code> on pending files of the last two weeks. To check an anchor yourself: <code>pip install opentimestamps-client</code>, download both files, run <code>ots verify DATE.json.ots -f DATE.json</code>. With a local Bitcoin node it verifies against the block header; without one it tells you which block to look up.</p>'''),
     ("Get the proof of a run", '''<pre>rv proof RUN_ID            <span class="d"># prints the proof JSON</span>
rv proof RUN_ID --verify   <span class="d"># recomputes leaf and Merkle path, fetches the public day file, exit 0 or 1</span>
curl -H "X-API-Key: rv_..." https://api.runvouch.com/v1/runs/RUN_ID/proof</pre>
<p>The response contains <code>record</code>, <code>leaf_hash</code>, <code>stored_leaf_hash</code> (the one written at run end; a difference would mean the row changed since), <code>merkle_path</code> as a list of (sibling hash, side), <code>root</code>, <code>chain_hash</code>, <code>prev</code>, <code>sealed</code>, <code>ots_status</code> and <code>verify_url</code>. The dashboard has a <em>proof</em> link per run, and the MCP server has <code>runvouch_run_proof</code>, so an agent can fetch its own proof and hand it to whoever asked for the work.</p>'''),
     ("Verify offline, without our code", '''<p><a href="https://github.com/runvouch/runvouch/blob/main/templates/verify_proof.py">templates/verify_proof.py</a> is a standalone Python 3 script, standard library only. Save the proof JSON and the day file, then:</p>
<pre>python3 verify_proof.py proof.json 2026-08-26.json
PASS leaf hash matches the record
PASS merkle path leads to the root
PASS day file lists this run with this leaf
PASS day file root recomputed from its leaves
PASS chain hash of the day
VERIFIED</pre>
<p>Change one byte of the record and the first line reads FAIL and the exit code is 1. The script fetches the day file itself when you leave the second argument out. It checks everything except the Bitcoin attestation; that is the <code>ots verify</code> step above.</p>'''),
     ("Honest limits", '''<ul><li>A day is sealed after it ends (UTC) and anchored some hours later. For a run that ended today, the proof endpoint returns a live root and <code>sealed: false</code>; until midnight it is our word, not a proof.</li>
<li>The leaf is computed from what your client reported. If the client lies about cost or evidence, the proof faithfully preserves the lie. What it rules out is editing afterwards, by you or by us.</li>
<li>A run that never called <code>/v1/runs/end</code> (stalled, killed) has no leaf and is not in any day.</li>
<li>The record contains no content. It cannot prove that the report your agent wrote said X; it proves that a run with evidence <code>report_written: true</code> ended at that time and cost that much.</li>
<li>OpenTimestamps gives a proof that the day file existed before a certain Bitcoin block. It does not give a proof of "not after". The chain hash gives the ordering between days.</li>
<li>If the ots client is missing or a calendar is down, the day is sealed without an anchor and says so. We do not backfill anchors silently.</li>
<li>Runs that ended before 26 August 2026 (the day this shipped) got their leaf computed afterwards from the stored fields, not at the moment they ended. From that day on the leaf is written in the same transaction that ends the run. The first sealed day is 2026-08-25.</li></ul>''')],
    [("Fetch the proof", "rv proof RUN_ID, or GET /v1/runs/RUN_ID/proof with your key, once the run has ended."), ("Wait for the seal", "After UTC midnight the day is sealed: sealed becomes true and the public day file exists."), ("Verify", "python3 verify_proof.py proof.json DATE.json; exit 0 means intact."), ("Check the anchor", "ots verify DATE.json.ots -f DATE.json once ots_status reads bitcoin:BLOCK.")])

doc("/docs/alerts", "Alert channels: e-mail, Telegram, Slack, Discord, Teams, webhook, PagerDuty - RunVouch docs",
    "Where RunVouch alerts go and how to set each channel with one PUT /v1/settings call: e-mail, Telegram, Slack, Discord, Microsoft Teams, JSON webhook, PagerDuty Events API v2.",
    "Alert channels",
    'Every alert (MISSED, FAILED, NO_EVIDENCE, BUDGET_RUN, BUDGET_DAY, RETRY_STORM, DRIFT, STALLED) goes to every channel you configure. Settings are one call; fields you leave out keep their value. Check the result with <code>POST /v1/settings/test-alert</code>, which sends a TEST alert to every configured channel. All of this is also on the <a href="/app">dashboard</a>.',
    [("E-mail (every plan)", f'''<pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"alert_email": "ops@company.com"}}'</pre><p>Subject <code>[RunVouch] KIND: agent</code>, the message in the body, a link to the dashboard. Signing up sets this to your signup address.</p>'''),
     ("Telegram (every plan)", f'''<p>Create a bot with @BotFather, start a chat with it (or add it to a group), and read the chat id from <code>https://api.telegram.org/bot&lt;token&gt;/getUpdates</code>.</p><pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"telegram_token": "123456:ABC...", "telegram_chat": "-100123456"}}'</pre>'''),
     ("Slack (every plan)", f'''<p><a href="/integrations/slack">Add to Slack</a> installs it in one click when the Slack app is enabled on this server; that page says whether it is. The webhook route below always works. By hand, in Slack: Apps, Incoming Webhooks, add to a channel, copy the URL. It starts with <code>https://hooks.slack.com/services/</code>; other URLs are rejected with 422.</p><pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"slack_webhook_url": "https://hooks.slack.com/services/T000/B000/XXXX"}}'</pre><p>The message has a plain-text fallback plus blocks: a header with kind and agent, two fields (kind, agent), the message, and a link to the dashboard. The weekly cost report goes to the same channel.</p>'''),
     ("Discord (every plan)", f'''<p>In Discord: Server Settings, Integrations, Webhooks, New Webhook, pick the channel, Copy Webhook URL.</p><pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"discord_webhook_url": "https://discord.com/api/webhooks/123456/XXXX"}}'</pre><p>One embed per alert: kind and agent as the title, the message as the body, red for a failure and green for a test, with a link to the dashboard. Other hosts are rejected with 422.</p>'''),
     ("Microsoft Teams (every plan)", f'''<p>In Teams the modern route is a workflow: in the channel, click the three dots, Workflows, "Post to a channel when a webhook request is received", and copy the URL it gives you (it ends up on <code>logic.azure.com</code>). An old Office 365 connector URL still works too.</p><pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"teams_webhook_url": "https://prod-1.westeurope.logic.azure.com/workflows/…/triggers/manual/paths/invoke?…"}}'</pre><p>The alert arrives as an adaptive card: kind and agent in the heading, the message underneath, a button to the dashboard.</p>'''),
     ("Generic webhook (every plan)", f'''<pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"webhook_url": "https://example.com/hooks/runvouch"}}'</pre><p>One JSON POST per alert:</p><pre>{{"kind":"RETRY_STORM","agent":"repo-janitor","run_id":"9808c5af...","message":"tool 'Bash' called 41x with identical input in one run.","ts":1787673506.3}}</pre><p>The weekly report arrives as <code>{{"kind":"WEEKLY_REPORT", ...}}</code>. Discord, Mattermost and n8n take this as is.</p>'''),
     ("PagerDuty (Team)", f'''<p>In PagerDuty: Services, your service, Integrations, add "Events API v2", copy the 32-character integration key.</p><pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"pagerduty_routing_key": "R0123456789ABCDEF0123456789ABCDEF"}}'</pre><p>On Free and Solo this call returns 402 with a plain message. Behaviour:</p><ul><li>MISSED, FAILED, STALLED, BUDGET_RUN and BUDGET_DAY trigger an incident (severity error) with <code>dedup_key = runvouch:AGENT:KIND</code>, so a repeat of the same problem lands on the same incident.</li><li>NO_EVIDENCE, RETRY_STORM and DRIFT do not page; they still reach your other channels.</li><li>Acknowledging the alert in RunVouch (<code>POST /v1/alerts/{{id}}/ack</code>, the dashboard, or the MCP tool) sends a resolve for that dedup key.</li><li>The test alert opens an incident with severity info; ack it in RunVouch to resolve it.</li></ul>'''),
     ("Priority alerts (Solo and Team)", '''<p>Alerts of the same kind for the same agent are sent at most once per 10 minutes; repeats within that window are stored and shown in the dashboard with <code>delivered = -1</code>, but not re-sent. On Solo and Team, MISSED and FAILED skip that cooldown and are delivered immediately, every time. All other kinds keep the cooldown on every plan.</p>'''),
     ("Test and status", f'''<pre>curl -X POST {API}/v1/settings/test-alert -H "X-API-Key: $RUNVOUCH_KEY"
curl {API}/v1/me -H "X-API-Key: $RUNVOUCH_KEY"   <span class="d"># "channels": which ones are set</span></pre>''')],
    [("Pick a channel", "E-mail, Telegram, Slack, Discord, Teams or a webhook on every plan; PagerDuty on Team."), ("Set it", "PUT /v1/settings with the field for that channel, or fill it in on the dashboard."), ("Test it", "POST /v1/settings/test-alert and watch the channel.")])

doc("/integrations/slack", "RunVouch for Slack: alerts for scheduled jobs and AI agents in a channel",
    "Add RunVouch to Slack in one click. Missed, failed, evidence-less, stalled, looping or overspending runs are posted to the channel you pick, with a weekly digest.",
    "Slack",
    'RunVouch posts to the Slack channel you choose when a scheduled job or AI agent is MISSED, FAILED, NO_EVIDENCE, STALLED, RETRY_STORM, BUDGET_RUN, BUDGET_DAY or DRIFT, plus a weekly digest. Works on every plan, including Free. Two ways in: the Add to Slack button below, or paste an incoming webhook URL yourself.',
    [("Add to Slack", f'''<p>Enter your RunVouch API key (it stays in your browser; the link only carries it to RunVouch, never to Slack), click the button, pick a channel in Slack, done. RunVouch stores the channel's webhook and posts a first message so you can see it works.</p>
<p><input id="rvkey" type="password" placeholder="rv_..." autocomplete="off" style="width:22rem;max-width:100%;padding:.55rem .7rem;border:1px solid var(--line);border-radius:8px;background:transparent;color:inherit"> <a id="addslack" class="btn" href="{API}/integrations/slack/install" onclick="this.href='{API}/integrations/slack/install?token='+encodeURIComponent(document.getElementById('rvkey').value.trim())">Add to Slack</a></p>
<p id="slackstate" class="small muted">Checking whether the Slack app is enabled...</p>
<script>fetch('{API}/integrations/slack/status').then(r=>r.json()).then(j=>{{const e=document.getElementById('slackstate');if(j.configured){{e.textContent='The Slack app is enabled. You need a RunVouch key first: get a free one on the home page.'}}else{{e.textContent='The one-click install is not enabled yet on this server. Use the webhook route below; it gives exactly the same messages.';document.getElementById('addslack').style.opacity='.5';document.getElementById('addslack').onclick=function(ev){{ev.preventDefault();e.textContent='Not enabled yet: use the webhook route below.'}}}}}}).catch(()=>{{document.getElementById('slackstate').textContent='Could not reach the API to check; use the webhook route below.'}})</script>
<p>Behind the button: <code>GET {API}/integrations/slack/install?token=YOUR_KEY</code> redirects to Slack's consent screen with the single scope <code>incoming-webhook</code>. Slack sends the browser back to <code>{API}/integrations/slack/callback</code>; RunVouch exchanges the code, saves the webhook URL on your account and posts a connected message. RunVouch never reads messages from your workspace.</p>'''),
     ("Or paste a webhook yourself (every plan)", f'''<p>In Slack: Apps, Incoming Webhooks, add to a channel, copy the URL. It starts with <code>https://hooks.slack.com/services/</code>; other URLs are rejected with 422.</p><pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"slack_webhook_url": "https://hooks.slack.com/services/T000/B000/XXXX"}}'</pre><p>Or paste it in the Slack field on the <a href="{API}/app">dashboard</a>. Both routes end with the same field on your account; the last one written wins.</p>'''),
     ("What lands in the channel", '''<p>Each alert is one message with a plain-text fallback plus blocks: a header with kind and agent, two fields (kind, agent), the message (for FAILED the stderr excerpt, for BUDGET the cost and the cap), and a link to the dashboard. The weekly digest per account goes to the same channel.</p><pre>RunVouch MISSED: nightly-report
Kind    MISSED          Agent   nightly-report
cadence 24h + grace 30m passed without a start
Open the dashboard</pre><p>Alerts of the same kind for the same agent are sent at most once per 10 minutes; on Solo and Team, MISSED and FAILED skip that cooldown. Details on <a href="/docs/alerts">alert channels</a>.</p>'''),
     ("Test and remove", f'''<pre>curl -X POST {API}/v1/settings/test-alert -H "X-API-Key: $RUNVOUCH_KEY"</pre><p>A TEST alert must land in the channel within a few seconds. To disconnect: remove the RunVouch app from the channel in Slack (Slack revokes the webhook), or overwrite <code>slack_webhook_url</code> with a new one.</p>
<p>Scope and data: the app asks for <code>incoming-webhook</code> only. RunVouch stores one webhook URL per account and sends alerts to it; it holds no Slack tokens, member names or message history. See the <a href="/privacy">privacy policy</a> and <a href="/security">security page</a>.</p>''')],
    [("Get a key", "Get a free RunVouch key on the home page."), ("Add to Slack", "Enter the key on this page, click Add to Slack and pick a channel."), ("Test it", "POST /v1/settings/test-alert and watch the channel.")])

page("/integrations/slack/installed", "RunVouch is connected to Slack",
     "Confirmation page after installing the RunVouch Slack app.",
     f'''<main><div class="wrap doc"><p class="small muted"><a href="/integrations/">Integrations</a> &rsaquo; <a href="/integrations/slack">Slack</a> &rsaquo; Connected</p>
<h1 id="slack-h1">RunVouch is connected to Slack</h1>
<p class="lead muted" id="slack-lead">A first message has been posted to the channel you picked. From now on every alert and the weekly digest land there.</p>
<div id="slack-err" style="display:none" class="card"><h3>The install did not finish</h3><p id="slack-err-text"></p><p>Nothing was changed on your account. <a href="/integrations/slack">Try again</a>, or paste a webhook URL by hand (same page). If it keeps failing, <a href="/contact">contact support</a> with the code above.</p></div>
<div id="slack-next"><h2>Next</h2><ol><li>Send a test: <code>curl -X POST {API}/v1/settings/test-alert -H "X-API-Key: $RUNVOUCH_KEY"</code></li><li>Register an agent if you have none yet: <code>rv agent nightly-report --cadence 24h --grace 30m --evidence</code></li><li>Open the <a href="{API}/app">dashboard</a> to see the Slack channel marked as set.</li></ol></div>
<script>(function(){{var q=new URLSearchParams(location.search);var ch=q.get('channel');var er=q.get('error');
if(er){{document.getElementById('slack-h1').textContent='Slack install not completed';document.getElementById('slack-lead').style.display='none';document.getElementById('slack-next').style.display='none';var b=document.getElementById('slack-err');b.style.display='block';document.getElementById('slack-err-text').textContent=(er==='access_denied'?'You cancelled on the Slack consent screen.':'Slack answered: '+er.replace(/[^a-zA-Z0-9_:. -]/g,''))}}
else if(ch){{document.getElementById('slack-lead').textContent='A first message has been posted to '+ch.replace(/[^#@a-zA-Z0-9_.-]/g,'')+'. From now on every alert and the weekly digest land there.'}}}})()</script>
<hr style="border:0;border-top:1px solid var(--line);margin:2.5rem 0"><p class="muted">Back to <a href="/integrations/slack">the Slack page</a> or <a href="/docs/alerts">all alert channels</a>.</p></div></main>''', [ORG_LD])

doc("/docs/mcp", "RunVouch MCP server: let agents check on agents", "Add the RunVouch MCP server so Claude and other MCP clients can ask which agents are healthy, read alerts, and report their own runs.",
    "MCP server", "Seven tools, stdio transport, no SDK dependency. Lets an agent refuse to build on another agent's unproven output.",
    [("Install (remote, no download)", '<p>RunVouch is listed in the official MCP Registry as <code>com.runvouch/runvouch</code>. Any client that supports remote servers can add it directly:</p><pre>claude mcp add --transport http runvouch https://api.runvouch.com/mcp --header "X-API-Key: rv_…"</pre><p>Cursor / VS Code / Windsurf: add a server with URL <code>https://api.runvouch.com/mcp</code> and header <code>X-API-Key</code>.</p>'),
     ("Claude Desktop (one-click bundle)", '<p>Download <a href="/runvouch.mcpb">runvouch.mcpb</a> and open it with Claude Desktop (Settings → Extensions → Install from file). It asks for your API key once. Requires Python 3.9+ on your machine.</p>'),
     ("Install (local stdio)", '<pre>claude mcp add runvouch -e RUNVOUCH_KEY=rv_… -e RUNVOUCH_URL=https://api.runvouch.com -- python3 /path/runvouch_mcp.py</pre>'),
     ("Tools", '<table><tr><th>Tool</th><th>Does</th></tr><tr><td><code>runvouch_status</code></td><td>state of every agent (ok / alert / failed / unproven / running / waiting), last run, 24h cost</td></tr><tr><td><code>runvouch_alerts</code></td><td>open alerts</td></tr><tr><td><code>runvouch_ack</code></td><td>acknowledge one</td></tr><tr><td><code>runvouch_runs</code></td><td>recent runs of an agent</td></tr><tr><td><code>runvouch_run_start</code> / <code>runvouch_run_end</code></td><td>report from inside an agent</td></tr><tr><td><code>runvouch_run_proof</code></td><td>the tamper-evident proof of a finished run (see <a href="/docs/proof">verifiable runs</a>)</td></tr></table>'),
     ("Example prompt", '<p class="quote">"Before you summarize yesterday&#39;s data, call runvouch_status. If <code>nightly-etl</code> is not <code>ok</code>, stop and tell me why."</p>')])

doc("/docs/api", "RunVouch HTTP API", "REST API reference for RunVouch: agents, runs, tool events, evidence, alerts, settings.",
    "HTTP API", f"Base URL <code>{API}</code>. Auth: <code>X-API-Key</code>. JSON in, JSON out. Rate limit 600 requests/min per key.",
    [("Endpoints", '''<table><tr><th>Method · path</th><th>Purpose</th></tr>
<tr><td><code>POST /signup</code></td><td>{"email"} → free account + key (shown once)</td></tr>
<tr><td><code>GET /v1/me</code> · <code>POST /v1/me/rotate-key</code></td><td>account, plan, key rotation</td></tr>
<tr><td><code>PUT /v1/settings</code></td><td>alert_email, telegram_token, telegram_chat, webhook_url, slack_webhook_url, pagerduty_routing_key (Team) · <code>POST /v1/settings/test-alert</code> sends a TEST alert to every configured channel · details per channel on <a href="/docs/alerts">alerts</a></td></tr>
<tr><td><code>POST /v1/agents</code> · <code>GET /v1/agents</code></td><td>upsert (name, cadence_s, grace_s, max_runtime_s, cap_run_cost, cap_day_cost, cap_run_tokens, evidence_required) · list with state</td></tr>
<tr><td><code>POST /v1/agents/{name}/pause</code> · <code>GET /v1/agents/{name}/runs</code></td><td>pause/resume · run history</td></tr>
<tr><td><code>GET /v1/runs/{run_id}/proof</code> · <code>GET /proof/</code> (public)</td><td>proof of one finished run · the daily chain, see <a href="/docs/proof">verifiable runs</a></td></tr>
<tr><td><code>POST /v1/runs/start</code> · <code>/tool</code> · <code>/heartbeat</code> · <code>/end</code></td><td>run lifecycle; tool events carry tool, input (hashed server-side) or input_hash, ok, cost, tokens</td></tr>
<tr><td><code>GET /v1/alerts</code> · <code>POST /v1/alerts/{id}/ack</code></td><td>alerts (ack also resolves the PagerDuty incident on Team)</td></tr>
<tr><td><code>GET /v1/export?from=YYYY-MM-DD&amp;to=YYYY-MM-DD&amp;format=csv|json</code></td><td>Team: streams every run that started in the range (UTC days, inclusive): agent, run_id, started, ended, status, cost, tokens, tool_calls, evidence_ok, leaf_hash. Free and Solo get 402.</td></tr>
<tr><td><code>POST /v1/me/viewer-keys</code> · <code>GET /v1/me/viewer-keys</code> · <code>DELETE /v1/me/viewer-keys/{id}</code></td><td>Team: read-only keys (rvv_) for a shared dashboard. Body {"name"}; the key is shown once. A viewer key may GET anything under /v1 and POST /v1/alerts/{id}/ack; every other write returns 403.</td></tr></table>'''),
     ("History retention", '<p>Runs, tool events and acknowledged alerts are kept for 7 days on Free and 90 days on Solo and Team (<code>history_days</code> in <code>GET /v1/me</code>). A purge runs once a day. Open alerts are never purged. A run that is part of a sealed proof day keeps its id, end time and leaf hash in a small table, so <code>GET /v1/runs/{id}/proof</code> still returns the leaf, its Merkle path and the sealed root after the full record is gone (with <code>"purged": true</code> and <code>"record": null</code>).</p>'),
     ("Alert webhook payload", '<pre>{"kind":"RETRY_STORM","agent":"repo-janitor","run_id":"9808c5af…","message":"tool \'Bash\' called 41x with identical input in one run.","ts":1787673506.3}</pre>')])

page("/docs/", "RunVouch documentation", "Guides for monitoring Claude Code, cron jobs, OpenClaw, n8n and the MCP server with RunVouch.", '''<main><div class="wrap doc"><h1>Documentation</h1><p class="lead muted">Pick your runtime. Every guide is copy-paste and takes under five minutes.</p>
<div class="grid g2"><a class="card" href="/docs/claude-code"><h3>Claude Code</h3><p>Routines, headless claude -p, hooks plugin, transcript cost.</p></a><a class="card" href="/docs/cron"><h3>Cron &amp; scripts</h3><p>rv run for anything: Python, Node, bash, GitHub Actions.</p></a><a class="card" href="/docs/cron#no-client-at-all-the-ping-url"><h3>Ping URL</h3><p>One URL per agent. No client, no header: curl, n8n, Zapier, a Docker HEALTHCHECK.</p></a><a class="card" href="/docs/github-actions"><h3>GitHub Actions</h3><p>One step: MISSED when the schedule stops, NO_EVIDENCE when it fakes it.</p></a><a class="card" href="/docs/openclaw"><h3>OpenClaw</h3><p>verified-run skill, heartbeats, daily caps.</p></a><a class="card" href="/docs/n8n"><h3>n8n</h3><p>Community node or two HTTP nodes; catch the failures Error Workflows miss.</p></a><a class="card" href="/integrations/"><h3>All integrations</h3><p>Kubernetes, systemd, Airflow, Prefect, Lambda, Vercel, LangGraph, CrewAI and 25 more.</p></a><a class="card" href="/docs/python-node"><h3>Python &amp; Node</h3><p>LangGraph, OpenAI Agents SDK, CrewAI, any script.</p></a><a class="card" href="/docs/templates"><h3>Agent templates</h3><p>Nightly 13F digest, Form D raises, hiring watch: copy, set keys, monitored.</p></a><a class="card" href="/docs/proof"><h3>Verifiable runs</h3><p>Hash per run, Merkle root per day, anchored in Bitcoin. Verify offline. Need to show an auditor? Start at <span style="color:var(--acc2)">/verifiable-agent-runs</span>.</p></a><a class="card" href="/docs/alerts"><h3>Alert channels</h3><p>E-mail, Telegram, Slack, Discord, Teams, webhook, PagerDuty: one settings call each.</p></a><a class="card" href="/docs/mcp"><h3>MCP server</h3><p>Agents that check on agents.</p></a><a class="card" href="/docs/api"><h3>HTTP API</h3><p>Everything the CLI does, over REST.</p></a></div></div></main>''', [ORG_LD])



# ───────────────────────── INTEGRATIONS (one page per scheduler / platform / framework) ─────────────────────────
import sys as _sys
_sys.path.insert(0, str(ROOT))
from integrations import INTEGRATIONS, GROUPS

DETECTS = ('<table><tr><th>Alert</th><th>What it means here</th></tr>'
           '<tr><td><b>MISSED</b></td><td>cadence plus grace passed and no run started</td></tr>'
           '<tr><td><b>FAILED</b></td><td>non-zero exit or a reported failure, with the stderr excerpt</td></tr>'
           '<tr><td><b>NO_EVIDENCE</b></td><td>the run said ok but the file, URL or assertion you required is missing</td></tr>'
           '<tr><td><b>STALLED</b></td><td>a run started and never ended within max runtime</td></tr>'
           '<tr><td><b>RETRY_STORM</b></td><td>the same tool called with identical input many times in one run</td></tr>'
           '<tr><td><b>BUDGET_RUN / BUDGET_DAY</b></td><td>cost cap crossed; the agent is paused until you resume it</td></tr>'
           '<tr><td><b>DRIFT</b></td><td>duration or output size far off its 7-run baseline</td></tr></table>')

SETUP = ('<ol><li><a href="/#signup">Get a free key</a> (3 agents, no card) and store it where this page says.</li>'
         '<li>HOW: copy the snippet above into the scheduled job.</li>'
         '<li>Register the cadence once: <code>rv agent nightly-report --cadence 24h --grace 30m --evidence</code>, or let the first run create the agent and set the cadence on the <a href="/app">dashboard</a>.</li>'
         '<li>Send one test alert: <code>curl -X POST ' + API + '/v1/settings/test-alert -H "X-API-Key: $RUNVOUCH_KEY"</code>. The next missed, failed or empty run reaches the same channels.</li></ol>')

def integration_page(i):
    agent = "nightly-report"
    cadence = (f'<pre>rv agent {agent} --cadence 24h --grace 30m --max-runtime 1h --evidence --cap-run-cost 2</pre>'
               f'<p>Register the agent once, from anywhere with the key. Cadence is what turns a schedule that stopped into an alert; '
               f'<code>--evidence</code> makes a run without evidence a failure; the caps pause the agent when it overspends.</p>')
    how = "Wrap the job" if i["mode"] == "wrap" else "Report the run (two HTTP calls)"
    sections = [("How it runs on " + i["name"], f'<p>{i["where"]}</p>'),
                ("Store the key", f'<p>{i["key"]}</p>'),
                (how, i["snippet"] + ('<p><code>rv</code> fails open: if RunVouch is unreachable the job still runs and you get one warning line.</p>' if i["mode"] == "wrap" else f'<p>The start call returns <code>run_id</code>; the end call takes <code>status</code> (ok or fail), optional <code>cost</code> and <code>tokens</code>, and <code>evidence</code> as a JSON object of booleans. Full reference on the <a href="/docs/api">API page</a>.</p>')),
                ("Register the cadence and caps", cadence),
                ("What goes silent on " + i["name"], i["silent"]),
                ("What " + i["name"] + " does not tell you", i["missing"]),
                ("What RunVouch detects", DETECTS),
                ("Set up in two minutes", SETUP.replace("HOW", how.lower()))]
    steps = [("Store RUNVOUCH_KEY as a secret", re.sub("<[^>]+>", "", i["key"])),
             (how, "Add the snippet from this page to the scheduled job."),
             ("Register the agent", f"rv agent {agent} --cadence 24h --grace 30m --evidence")]
    doc(f"/integrations/{i['slug']}", i["title"], i["desc"], i["h1"] + " with RunVouch", i["intro"], sections, steps)

for _i in INTEGRATIONS:
    integration_page(_i)

_cards = ""
for _g in GROUPS:
    _items = [i for i in INTEGRATIONS if i["group"] == _g]
    _cards += f'<h2>{_g}</h2><div class="grid g3">' + "".join(
        f'<a class="card" href="/integrations/{i["slug"]}"><h3>{i["name"]}</h3><p>{i["intro"].split(". ")[0].rstrip(".")[:120]}.</p></a>' for i in _items) + '</div>'
_existing = ('<h2>Guides with their own page</h2><div class="grid g3">'
             '<a class="card" href="/docs/claude-code"><h3>Claude Code</h3><p>Routines, headless claude -p, hooks plugin.</p></a>'
             '<a class="card" href="/docs/cron"><h3>Cron and scripts</h3><p>rv run for anything on a schedule.</p></a>'
             '<a class="card" href="/docs/github-actions"><h3>GitHub Actions</h3><p>Scheduled workflows that stop firing.</p></a>'
             '<a class="card" href="/docs/openclaw"><h3>OpenClaw</h3><p>verified-run skill, heartbeats, daily caps.</p></a>'
             '<a class="card" href="/docs/n8n"><h3>n8n</h3><p>Community node n8n-nodes-runvouch; Error Workflows miss the rest.</p></a>'
             '<a class="card" href="/docs/python-node"><h3>Python and Node</h3><p>Single-file clients, any script.</p></a>'
             '<a class="card" href="/integrations/slack"><h3>Slack</h3><p>Add to Slack: alerts and the weekly digest in a channel.</p></a></div>')
page("/integrations/", "RunVouch integrations: every scheduler, platform and agent framework",
     f"How to give a scheduled job a dead man's switch, evidence check and cost cap on {len(INTEGRATIONS) + 6} runtimes: Kubernetes, systemd, Airflow, Prefect, Lambda, Vercel, LangGraph, CrewAI and more.",
     f'<main><div class="wrap doc"><h1>Integrations</h1><p class="lead muted">RunVouch wraps a command or takes two HTTP calls, so it works wherever a job runs. Pick the runtime; each page lists where the job runs there, how to store the key, the snippet, and what fails silently on that platform in its own terms.</p>{_existing}{_cards}</div></main>', [ORG_LD])

VS_LIST = [('healthchecks', 'Healthchecks.io', 'Ping monitor vs outcome watchdog.'), ('cronitor', 'Cronitor', 'Ops monitoring vs agent monitoring.'), ('langfuse', 'Langfuse', 'Tracing vs watchdog, complementary.'), ('dead-mans-snitch', "Dead Man's Snitch", 'Heartbeat vs heartbeat plus outcome.'), ('sentry-crons', 'Sentry Crons', 'Exceptions vs silent failures.'), ('better-stack', 'Better Stack', 'One vendor for uptime vs one job done well.'), ('uptime-kuma', 'Uptime Kuma', 'Self-hosted push monitor vs agent watchdog.'), ('cronhub', 'Cronhub', 'Cron monitor vs LLM job monitor.'), ('helicone', 'Helicone', 'LLM proxy vs outside watchdog.'), ('agentops', 'AgentOps', 'Session replay vs pager.'), ('langsmith', 'LangSmith', 'Tracing vs the alert that there is something to trace.'), ('traceseal', 'Traceseal', 'Signed receipt per invocation vs watchdog plus proof.'), ('traccia', 'Traccia', 'Control plane inside the stack vs watchdog outside it.')]
# ───────────────────────── VS PAGES ─────────────────────────
def vs(slug, name, tagline, rows, verdict):
    body = f'''<main><div class="wrap doc"><p class="small muted"><a href="/vs/">Compare</a> › {name}</p><h1>RunVouch vs {name}</h1><p class="lead muted">{tagline}</p>
<table><tr><th></th><th>{name}</th><th>RunVouch</th></tr>{"".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a,b,c in rows)}</table>
<h2>When to use which</h2>{verdict}<p><a class="btn" href="/#signup">Get a free key</a></p></div></main>'''
    page(f"/vs/{slug}", f"RunVouch vs {name}: for AI agents, cron and scheduled jobs", f"Honest comparison of RunVouch and {name} for monitoring scheduled AI agents: missed runs, evidence, retry storms, cost caps, pricing.", body, [ORG_LD], article=True)


vs("healthchecks", "Healthchecks.io", "Healthchecks.io is the reference dead man's switch for cron jobs. RunVouch starts where a ping ends: did the job do the work, and what did it cost?",
   [("Missed / late run alerts", "yes", "yes"), ("Failure with stderr excerpt", "via /fail ping", "yes, with rv run or the same /fail ping"), ("Evidence the task was actually done", "no", "yes, file / URL / assertion"), ("Retry-storm (loop) detection", "no", "yes"), ("Cost and token caps", "no", "yes, per run and per day"), ("Output/duration drift", "no", "yes"), ("Claude Code plugin / MCP server", "no", "yes"), ("Self-host", "yes (BSD)", "yes (MIT)"), ("Price", "free 20 checks; $20/mo for 100, $80 for 1000", "free 3 agents; $19 / $99")],
   "<p>Use Healthchecks.io for classic cron jobs where \"it ran\" is enough. Use RunVouch when the job is an agent or an LLM script: a green ping tells you nothing about whether the report was written or whether the agent spent $60 looping on a missing file. Many teams run both.</p>")
vs("cronitor", "Cronitor", "Cronitor is a mature cron, heartbeat and uptime monitor for ops teams. RunVouch is narrower and deeper: outcome, cost and loop detection for unattended AI agents.",
   [("Cron expression parsing", "yes", "cadence + grace"), ("Uptime / status pages", "yes", "no (we link to yours)"), ("Evidence the task was done", "no", "yes"), ("Retry-storm detection", "no", "yes"), ("Cost caps", "no", "yes"), ("Claude Code / MCP / OpenClaw integrations", "no", "yes"), ("Price", "free tier; paid from ~$5 per monitor tier", "free 3 agents; $19 / $99")],
   "<p>Pick Cronitor if you need status pages and hundreds of classic monitors. Pick RunVouch if what you run is agents and you care about \"done\" and \"how much\", not just \"on time\".</p>")
vs("langfuse", "Langfuse", "Langfuse is excellent open-source LLM observability: traces, evals, prompt management. RunVouch is not a tracing tool; it's the watchdog that tells you a scheduled agent is broken or expensive, without instrumenting your code.",
   [("Traces, spans, prompt versions, evals", "yes", "no"), ("Requires SDK in your code", "yes", "no, wrap the command or install the plugin"), ("Missed-run / dead man's switch", "no", "yes"), ("Evidence the task was done", "no", "yes"), ("Retry-storm alert", "you can find it in traces", "automatic"), ("Hard cost cap + pause", "cost threshold alerts since v4, no cap or pause", "yes"), ("Pricing", "free self-host; cloud per unit", "free 3 agents; $19 / $99")],
   "<p>They're complementary. Langfuse answers \"why did this prompt produce that\"; RunVouch answers \"did last night's agent run, finish, prove it, and stay under budget\". If you only want the second, you don't need the first.</p>")

vs("traceseal", "Traceseal", "Traceseal (Show HN, August 2026) signs a receipt for every agent invocation: what code ran, who published it, input and output hashes, sandbox profile, all verifiable offline with one command. RunVouch proves a scheduled run happened and was done, and pages you when it was not. Both are proof; they answer different questions.",
   [("What is proven", "which signed skill ran, on which inputs, in which sandbox (per invocation)", "that the scheduled run started, ended, passed its evidence check and what it cost (per run, chained per day)"),
    ("Anchor", "ed25519 signatures plus a transparency log", "SHA-256 chain per day, anchored in Bitcoin via OpenTimestamps"),
    ("Verify without trusting the operator", "yes, pip install traceseal-verify", "yes, the chain and every day file are public, verify with the free ots client"),
    ("Missed-run / dead man's switch", "no", "yes"),
    ("Alert when the run is late, fails, loops or overspends", "no", "yes: Telegram, Slack, Discord, Teams, email, PagerDuty, webhook"),
    ("Hard cost cap + pause", "no", "yes"),
    ("Requires a sandbox around the agent", "yes, bwrap kernel namespaces", "no, wrap the command or two HTTP calls"),
    ("Regulatory angle", "EU AI Act Article 50 receipts", "audit trail of unattended runs; no compliance claims"),
    ("Pricing", "not published on the site (September 2026); open source verifier", "free 3 agents; $19 / $99")],
   "<p>If you have to prove to a third party <i>which code</i> an agent executed and on <i>which inputs</i>, Traceseal is built for exactly that and RunVouch is not. If you have to know at 07:00 that last night's agent ran, did the work and stayed under budget, and want a proof of that record you can hand to anyone, that is RunVouch. Running both is coherent: Traceseal seals the invocation, RunVouch watches the schedule.</p>")

vs("traccia", "Traccia", "Traccia is an AI agent control plane: traces, cost attribution, PII detection, policy enforcement and evals, from one SDK init call. RunVouch sits outside the stack: it does not see inside the run, it checks that the run happened, finished, produced evidence and stayed under budget.",
   [("Where it lives", "inside your code (traccia.init(), SDK per framework)", "outside: wraps the command, or two HTTP calls"),
    ("Traces, spans, prompt registry, evals", "yes", "no"),
    ("Cost attribution per agent and model", "yes, from spans", "per run, as reported by the wrapper or your call"),
    ("Policy enforcement, PII masking, model restrictions", "yes, hard blocks mid-execution on higher tiers", "no"),
    ("Spend limit with hard cap", "Enterprise tier, per the pricing table", "every plan, including free: cap per run and per day, agent paused"),
    ("Missed-run / dead man's switch", "no", "yes"),
    ("Evidence the task was done", "no", "yes: file, URL or assertion required, else NO_EVIDENCE"),
    ("Third-party verifiable proof of the run record", "compliance evidence export", "public hash chain, Bitcoin-anchored"),
    ("Pricing", "free 50K events, 7-day retention; $99 / $299 / $799 per month; enterprise custom", "free 3 agents; $19 / $99")],
   "<p>Traccia is for a team running many agents in production that needs governance inside the stack: who called what, at what cost, with which policy. RunVouch is for anyone with agents on a schedule who needs to know they ran and were done, without instrumenting anything. If your worry is \"the routine stopped and nobody noticed\" or \"it ran up $1,800 overnight\", the watchdog outside the process is the cheaper answer; Traccia's hard spend cap starts at Enterprise, RunVouch's is on the free plan.</p>")

vs("dead-mans-snitch", "Dead Man's Snitch", "Dead Man's Snitch is a heartbeat monitor: your job checks in, and you hear about it when it does not. RunVouch keeps the heartbeat and adds what the job did and what it cost.",
   [("Missed check-in alerts", "yes", "yes"), ("Failure with stderr excerpt", "via the snitch CLI wrapper", "yes, automatic with rv run"), ("Evidence the task was done", "no", "yes, file / URL / assertion"), ("Retry-storm (loop) detection", "no", "yes"), ("Cost and token caps", "no", "yes, per run and per day"), ("Output/duration drift", "no", "yes"), ("Claude Code plugin / MCP server", "no", "yes"), ("Self-host", "no", "yes (MIT)"), ("Price", "free for one snitch; paid plans", "free 3 agents; $19 / $99")],
   "<p>If all you need is \"did the cron check in\", Dead Man's Snitch has done that reliably for years. If the job is an agent, the check-in is the least interesting fact about it.</p>")
vs("sentry-crons", "Sentry Crons", "Sentry Crons adds scheduled-job monitoring to Sentry error tracking. RunVouch is for jobs whose failure is not an exception: empty output, loops, overspend.",
   [("Missed / late run alerts", "yes", "yes"), ("Exceptions with stack traces", "yes, with the Sentry SDK", "stderr excerpt only"), ("Evidence the task was done", "no", "yes"), ("Retry-storm (loop) detection", "no", "yes"), ("Cost and token caps", "no", "yes"), ("Output/duration drift", "no (duration thresholds only)", "yes"), ("Requires SDK in your code", "yes (or curl check-ins)", "no, wrap the command"), ("Self-host", "yes (Sentry self-hosted)", "yes (MIT)"), ("Price", "included in Sentry plans; per-monitor quota", "free 3 agents; $19 / $99")],
   "<p>Already on Sentry and your jobs fail by throwing? Use Sentry Crons. Agents mostly fail without throwing; that is the case RunVouch is built for. They coexist fine.</p>")
vs("better-stack", "Better Stack", "Better Stack combines uptime, heartbeat monitoring, logs and incident management. RunVouch is one narrow thing: is the scheduled agent alive, done, and under budget.",
   [("Heartbeat (missed run) alerts", "yes", "yes"), ("Uptime / status pages / on-call", "yes", "no (we link to yours)"), ("Failure with stderr excerpt", "no (heartbeat only)", "yes"), ("Evidence the task was done", "no", "yes"), ("Retry-storm detection", "no", "yes"), ("Cost caps", "no", "yes"), ("PagerDuty", "own on-call product", "yes (Team)"), ("Price", "free tier; paid plans", "free 3 agents; $19 / $99")],
   "<p>Pick Better Stack when you want one vendor for uptime, logs and paging. Pick RunVouch when the thing you are worried about is a nightly agent, not a website.</p>")
vs("uptime-kuma", "Uptime Kuma", "Uptime Kuma is the self-hosted uptime monitor everyone runs at home, and it has push monitors that work as a dead man's switch. RunVouch is the agent-specific layer on top of that idea.",
   [("Push (heartbeat) monitors", "yes", "yes"), ("HTTP / TCP / DNS uptime checks", "yes", "no"), ("Failure with stderr excerpt", "no", "yes"), ("Evidence the task was done", "no", "yes"), ("Retry-storm detection", "no", "yes"), ("Cost caps", "no", "yes"), ("Tamper-evident proof of each run", "no", "yes"), ("Self-host", "yes (MIT)", "yes (MIT)"), ("Price", "free", "free 3 agents; $19 / $99")],
   "<p>Keep Uptime Kuma for everything with a URL. For scheduled agents, a push monitor tells you the script ran; RunVouch tells you whether it did the job and what it spent, and the self-hosted version is also MIT.</p>")
vs("cronhub", "Cronhub", "Cronhub is a straightforward cron monitor with a clean UI. RunVouch shares the missed-run alert and adds outcome, loops and cost.",
   [("Missed / late run alerts", "yes", "yes"), ("Failure with stderr excerpt", "via /fail ping", "yes"), ("Evidence the task was done", "no", "yes"), ("Retry-storm detection", "no", "yes"), ("Cost caps", "no", "yes"), ("Output/duration drift", "no", "yes"), ("Self-host", "no", "yes (MIT)"), ("Price", "free tier; paid plans", "free 3 agents; $19 / $99")],
   "<p>For plain cron, either works. For an LLM job on cron, the questions change from \"did it run\" to \"did it finish the work and how much did it cost\", which is where the comparison ends.</p>")
vs("helicone", "Helicone", "Helicone is an LLM gateway and observability layer: one proxy URL, then dashboards of requests and cost. RunVouch does not sit in the request path; it watches the scheduled job from outside.",
   [("Per-request logs and cost dashboards", "yes", "no (cost per run and per day)"), ("Requires routing LLM calls through a proxy", "yes", "no"), ("Missed-run / dead man's switch", "no", "yes"), ("Evidence the task was done", "no", "yes"), ("Retry-storm alert", "visible in logs", "automatic"), ("Hard cost cap that pauses the agent", "rate limits per key", "yes, per run and per day"), ("Self-host", "yes", "yes (MIT)")],
   "<p>Helicone answers \"what did all my LLM calls look like\". RunVouch answers \"did last night's agent run, finish, prove it and stay under budget\". If you only need the second, you do not need a proxy in the path.</p>")
vs("agentops", "AgentOps", "AgentOps is session replay and analytics for agent frameworks: every step, every LLM call, in a timeline. RunVouch is the pager: is the scheduled agent alive, done and under budget right now.",
   [("Step-by-step session replay", "yes", "no"), ("Requires SDK in your code", "yes", "no, wrap the command or two HTTP calls"), ("Missed-run / dead man's switch", "no", "yes"), ("Evidence the task was done", "no", "yes"), ("Retry-storm alert", "visible in the replay", "automatic, during the run"), ("Hard cost cap + pause", "no", "yes"), ("Tamper-evident proof per run", "no", "yes"), ("Self-host", "no", "yes (MIT)")],
   "<p>Use AgentOps to understand why an agent did what it did. Use RunVouch to find out, within minutes, that it did not do it at all. Debugging tool and watchdog, not the same job.</p>")
vs("langsmith", "LangSmith", "LangSmith is LangChain's tracing, evaluation and prompt platform. RunVouch is the outside watchdog for the scheduled run: missed, failed, empty, looping or over budget.",
   [("Traces, evals, prompt hub, datasets", "yes", "no"), ("Requires SDK / callbacks", "yes", "no"), ("Missed-run / dead man's switch", "no", "yes"), ("Evidence the task was done", "no", "yes"), ("Retry-storm alert", "you can find it in the trace", "automatic"), ("Hard cost cap + pause", "no", "yes"), ("Works without LangChain", "partially", "yes, any command"), ("Self-host", "enterprise", "yes (MIT)")],
   "<p>They are complementary and many LangGraph users will want both: LangSmith for the trace, RunVouch for the alert that there is something to trace.</p>")
page("/vs/", "RunVouch compared", "How RunVouch compares to Healthchecks.io, Cronitor, Dead Man's Snitch, Sentry Crons, Better Stack, Uptime Kuma, Cronhub, Langfuse, Helicone, AgentOps and LangSmith for monitoring scheduled AI agents.", """<main><div class="wrap doc"><h1>Compare</h1><p class="lead muted">Feature tables, kept honest: where the other tool is better, it says so.</p><p>Not sure which category you need at all? Start at <a href="/observability-or-watchdog">observability, a heartbeat, or a watchdog</a>.</p><div class="grid g3"><a class="card" href="/vs/healthchecks"><h3>vs Healthchecks.io</h3><p>Ping monitor vs outcome watchdog.</p></a><a class="card" href="/vs/cronitor"><h3>vs Cronitor</h3><p>Ops monitoring vs agent monitoring.</p></a><a class="card" href="/vs/langfuse"><h3>vs Langfuse</h3><p>Tracing vs watchdog, complementary.</p></a><a class="card" href="/vs/dead-mans-snitch"><h3>vs Dead Man's Snitch</h3><p>Heartbeat vs heartbeat plus outcome.</p></a><a class="card" href="/vs/sentry-crons"><h3>vs Sentry Crons</h3><p>Exceptions vs silent failures.</p></a><a class="card" href="/vs/better-stack"><h3>vs Better Stack</h3><p>One vendor for uptime vs one job done well.</p></a><a class="card" href="/vs/uptime-kuma"><h3>vs Uptime Kuma</h3><p>Self-hosted push monitor vs agent watchdog.</p></a><a class="card" href="/vs/cronhub"><h3>vs Cronhub</h3><p>Cron monitor vs LLM job monitor.</p></a><a class="card" href="/vs/helicone"><h3>vs Helicone</h3><p>LLM proxy vs outside watchdog.</p></a><a class="card" href="/vs/agentops"><h3>vs AgentOps</h3><p>Session replay vs pager.</p></a><a class="card" href="/vs/langsmith"><h3>vs LangSmith</h3><p>Tracing vs the alert that there is something to trace.</p></a><a class="card" href="/vs/traceseal"><h3>vs Traceseal</h3><p>Signed receipt per invocation vs watchdog plus proof.</p></a><a class="card" href="/vs/traccia"><h3>vs Traccia</h3><p>Control plane inside the stack vs watchdog outside it.</p></a></div></div></main>""", [ORG_LD])


# ───────────────────────── STATS (real numbers from our own fleet, rebuilt weekly) ─────────────────────────
def _stats():
    import sqlite3, statistics
    db = ROOT.parent / "data" / "runvouch.db"
    if not db.exists():
        return None
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    d7, d30 = now - 7 * 86400, now - 30 * 86400
    def one(q, *a): return c.execute(q, a).fetchone()[0]
    runs30 = one("select count(*) from runs where ended is not null and ended > ?", d30)
    if runs30 < 20:
        return None
    fails30 = one("select count(*) from runs where status='fail' and ended > ?", d30)
    runs7 = one("select count(*) from runs where ended is not null and ended > ?", d7)
    agents30 = one("select count(distinct agent_id) from runs where ended > ?", d30)
    kinds = c.execute("select kind, count(*) from alerts where ts > ? and kind != 'TEST' group by kind order by 2 desc", (d30,)).fetchall()
    noev = one("select count(*) from alerts where kind='NO_EVIDENCE' and ts > ?", d30)
    ok30 = one("select count(*) from runs where status='ok' and ended > ?", d30)
    # detection time: alert timestamp minus the end of the run it belongs to (FAILED and NO_EVIDENCE only)
    lags = [r[0] for r in c.execute("select a.ts - r.ended from alerts a join runs r on r.id = a.run_id where a.kind in ('FAILED','NO_EVIDENCE') and a.ts > ? and r.ended is not null", (d30,)) if r[0] is not None and r[0] >= 0]
    lag = statistics.median(lags) if lags else None
    days = c.execute("select date, n_runs, ots_status from proof_days order by date").fetchall()
    anchored = sum(1 for d in days if (d[2] or "").startswith("bitcoin:"))
    return dict(runs30=runs30, fails30=fails30, runs7=runs7, agents30=agents30, kinds=kinds, noev=noev, ok30=ok30,
                lag=lag, days=len(days), anchored=anchored, day_runs=sum(d[1] for d in days), first_day=days[0][0] if days else None)

_KIND_UITLEG = {
    "FAILED": "exited non-zero, or the client reported failure",
    "DRIFT": "cost or duration moved away from this job's own baseline, while nothing failed",
    "MISSED": "the run never started: dead scheduler, expired auth, crash before the first line",
    "NO_EVIDENCE": "reported success, but the file, URL or assertion it promised was missing",
    "STALLED": "started and then stopped reporting before it ended",
    "RETRY_STORM": "the same tool with the same input, over and over, inside one run",
    "BUDGET_RUN": "one run went over its cost cap",
    "BUDGET_DAY": "one agent went over its daily cost cap",
}

def _aantal_tests():
    """Hoeveel tests de suite telt, geteld in plaats van ingetypt: dat laatste loopt altijd achter.

    Vragen aan pytest en niet zelf 'def test_' tellen, want een geparametriseerde test is er een per geval: het
    verschil was 95 tegen 99. Mislukt het verzamelen, dan valt hij terug op tellen, want een pagina die niet bouwt
    is erger dan een getal dat vier te laag staat."""
    import re as _re
    import subprocess as _sp
    try:
        r = _sp.run([str(ROOT.parent / ".venv" / "bin" / "python"), "-m", "pytest", "--collect-only", "-q", "tests"],
                    cwd=ROOT.parent, capture_output=True, text=True, timeout=120)
        m = _re.search(r"(\d+) tests? collected", r.stdout)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    n = 0
    for f in (ROOT.parent / "tests").glob("test_*.py"):
        n += len(_re.findall(r"^def test_", f.read_text(encoding="utf-8"), _re.M))
    return n


_TESTS = _aantal_tests()

_st = _stats()
if _st:
    _rows = "".join(f"<tr><td><b>{k}</b></td><td>{n}</td></tr>" for k, n in _st["kinds"]) or "<tr><td colspan=2>none</td></tr>"
    _lag = ("under 1 second" if _st["lag"] is not None and _st["lag"] < 1 else f"{_st['lag']:.0f} seconds" if _st["lag"] is not None and _st["lag"] < 120 else f"{_st['lag']/60:.0f} minutes" if _st["lag"] is not None else "n/a")
    _pct = 100 * _st["fails30"] / _st["runs30"]
    _noev_pct = 100 * _st["noev"] / max(_st["ok30"], 1)
    _cards = (f'<div class="card"><div class="big grad">{_st["runs30"]:,}</div><h3>runs in 30 days</h3><p>{_st["runs7"]:,} in the last 7 days, across {_st["agents30"]} agents.</p></div>'
              f'<div class="card"><div class="big grad">{_pct:.1f}%</div><h3>ended in failure</h3><p>{_st["fails30"]} runs exited non-zero or reported fail. Each one produced an alert with the stderr excerpt.</p></div>'
              f'<div class="card"><div class="big grad">{_st["noev"]}</div><h3>green runs without evidence</h3><p>{_noev_pct:.1f}% of successful runs said ok while the required file, URL or assertion was missing. A ping monitor calls these successes.</p></div>'
              f'<div class="card"><div class="big grad">{_lag}</div><h3>median time to alert</h3><p>From the end of a failed or evidence-less run to the alert being written: it happens in the same database transaction that ends the run. Delivery to Telegram, Slack or e-mail follows within seconds. Missed runs alert at cadence plus grace, by definition.</p></div>'
              f'<div class="card"><div class="big grad">{_st["days"]}</div><h3>proof days sealed</h3><p>{_st["day_runs"]:,} run leaves in the public Merkle chain since {_st["first_day"]}; {_st["anchored"]} day roots anchored in Bitcoin via OpenTimestamps. <a href="{API}/proof/">See the chain.</a></p></div>')
    _body = (f'<main><div class="wrap doc"><h1>RunVouch in numbers</h1>'
             f'<p class="lead muted">These are not benchmarks. They are the last 30 days of the {_st["agents30"]} scheduled agents and cron jobs that run the RunVouch and DataSignals Lab businesses, monitored by RunVouch itself. Rebuilt every week; this build is from {TODAY}.</p>'
             f'<div class="grid g3">{_cards}</div>'
             f'<h2>Alerts by kind, last 30 days</h2><table><tr><th>Kind</th><th>Count</th></tr>{_rows}</table>'
             f'<p class="muted">What the kinds mean is on the <a href="/docs/alerts">alerts page</a>. TEST alerts are excluded. Numbers come straight from the production database at build time; nothing is edited by hand.</p>'
             f'<h2>How to read this</h2>'
             f'<p>The failure rate is what you would expect from a fleet of scrapers and LLM jobs hitting external sources: most failures are an upstream 5xx or a rate limit, and the interesting number is not the rate but the time it took to know. The evidence figure is the one a heartbeat monitor cannot produce at all: those runs would have been green.</p>'
             f'<p>The same fleet, live and per agent instead of totalled: <a href="/fleet/datasignals">a live fleet</a>. If you publish your own numbers from RunVouch and want them linked here, <a href="/contact">say so</a>.</p></div></main>')
    # ── Hoe vaak faalt een onbewaakte taak eigenlijk ───────────────────────────
    # Niemand publiceert dit. De concurrentie verkoopt monitoring en laat de koper zelf raden hoe vaak er iets
    # misgaat, en de koper raadt te laag: hij denkt aan crashes en die zijn juist zeldzaam. Wij hebben 4.000 echte
    # runs liggen met de soorten erbij. Dezelfde cijfers als /stats, want ze komen uit dezelfde meting, maar hier
    # als antwoord op een vraag die iemand intypt in plaats van als dashboard.
    _soorten = dict(_st["kinds"])
    _tot_alerts = sum(_soorten.values())
    _fp = 100 * _st["fails30"] / _st["runs30"]
    _rij = "".join(
        f'<tr><td><b>{k}</b></td><td>{n}</td><td>{_KIND_UITLEG.get(k, "")}</td></tr>'
        for k, n in _st["kinds"])
    _maand_nu = TODAY[:7]
    _archief = sorted({f.name[len("failure-rates-"):-len(".json")] for f in (OUT / "api").glob("failure-rates-2*.json")} | {_maand_nu})
    _faal = f"""<main><div class="wrap doc"><h1>How often does an unattended job actually fail?</h1>
<p class="lead muted">Nobody publishes this, so here are our own numbers: {_st["runs30"]:,} runs by {_st["agents30"]} scheduled agents over 30 days, with every alert broken out by kind. Measured, not estimated, and rebuilt from the production database every week.</p>

<h2>The rate is boring. The kinds are not.</h2>
<p>{_fp:.1f} percent of runs ended in failure: {_st["fails30"]} out of {_st["runs30"]:,}. If you were expecting worse, that matches most fleets, and it is also why people underestimate the problem. A crash is loud, rare and easy to catch. It is not what costs you a night.</p>
<p>Those {_st["runs30"]:,} runs produced {_tot_alerts} alerts in total. Here is what they were:</p>
<table><tr><th>Kind</th><th>Count</th><th>What it means</th></tr>{_rij}</table>

<h2>Read that table from the bottom up</h2>
<p><b>The rarest one is the one nothing else catches.</b> {_soorten.get("NO_EVIDENCE", 0)} runs reported success while the file, URL or assertion they promised was not there. Every heartbeat monitor in this category would have counted those as green, because the job did check in. It just did not do anything. That is the failure mode people only discover downstream, when someone asks where the data went.</p>
<p><b>The second most common one has no category.</b> {_soorten.get("DRIFT", 0)} alerts were drift: cost or duration moving away from the job's own baseline while nothing failed at all. No exception, no missed run, no red status. A job that quietly starts taking four times as long is the earliest warning you get, and almost nothing watches for it.</p>
<p><b>Only {_soorten.get("MISSED", 0)} were the one everybody monitors.</b> A run that never started is what a dead man's switch is for, and it is the minority of what actually goes wrong.</p>

<h2>What these numbers are not</h2>
<p>This is one fleet: {_st["agents30"]} scheduled jobs that run a data business, mostly small scrapers, refreshes, health checks and report builders, plus a handful of LLM jobs. The median run takes about a second. A fleet of long agent sessions would fail more often and differently, and anyone who tells you there is one industry failure rate is selling something.</p>
<p>Two more honest limits. The record is built from what each client reported, so a client that lies about its own cost produces a faithful record of the lie. And a job nobody registered produces no alerts at all, which is the one failure mode monitoring can never see.</p>

<h2>Why we can publish this at all</h2>
<p>Because the runs behind it cannot be edited afterwards. Each finished run is hashed, each day of hashes is sealed into a Merkle root, and each root is chained to the day before and anchored in Bitcoin. So this page is not a marketing claim about our own reliability, it is a number you can recompute: <a href="/verify">verify a real run yourself</a>, no account needed.</p>
<p>The dashboard version of the same measurement, with the median time to alert and the proof chain, is on <a href="/stats">in numbers</a>. The fleet itself is live on <a href="/fleet/datasignals">a real fleet</a>.</p>

<h2>If you want your own numbers</h2>
<p>Wrap one job and you have a baseline within a week. Free for 3 agents, all detectors on, no card: <a href="/#signup">get a free key</a>.</p>
<h2 id="cite">Use these numbers</h2>
<p>They are free to quote, with attribution, under <a href="https://creativecommons.org/licenses/by/4.0/" rel="noopener">CC BY 4.0</a>. The same figures are machine readable at <a href="/api/failure-rates.json">/api/failure-rates.json</a>, rebuilt every week from the production database, with the method and the limits in the file itself.</p>
<pre><code>RunVouch (2026). How often does an unattended job actually fail?
{_st["runs30"]:,} runs by {_st["agents30"]} scheduled agents over 30 days, measured {TODAY}.
https://runvouch.com/how-often-jobs-fail</code></pre>
<p>Quoting it in something that has to stay true? Use the frozen copy of the month, which stops changing when the month does: <a href="/api/failure-rates-{_maand_nu}.json">/api/failure-rates-{_maand_nu}.json</a>. Months published so far: {", ".join(f'<a href="/api/failure-rates-{m}.json">{m}</a>' for m in _archief)}.</p>
<p><b>Check it before you quote it.</b> Every run behind these counts is hashed into a public daily Merkle root, chained to the day before and anchored in Bitcoin: the day files are at <a href="{API}/proof/">{API}/proof/</a> and you can recompute one in your browser at <a href="/verify">/verify</a>. The fleet that produced them is public run by run at <a href="/fleet/datasignals">/fleet/datasignals</a>. If a number here moves, the chain says whether the history moved with it.</p>
<p>Writing about agent reliability and want something specific broken out, per kind, per job type or over a longer window? Ask on <a href="/contact?topic=data">contact</a> and we will run the query and publish the answer here.</p>
<p class="small muted">Figures from the production database on {TODAY}, over the preceding 30 days. TEST alerts excluded. Nothing on this page is typed in by hand.</p>
</div></main>"""
    _dataset_ld = {"@context": "https://schema.org", "@type": "Dataset",
                   "name": "Failure rates of unattended scheduled jobs and AI agents",
                   "description": f"Counts of runs, failures and alerts by kind over 30 days from a production fleet of {_st['agents30']} scheduled jobs, with a tamper-evident hash chain behind every run.",
                   "url": BASE + "/how-often-jobs-fail", "license": "https://creativecommons.org/licenses/by/4.0/",
                   "creator": {"@type": "Organization", "name": "RunVouch", "url": BASE},
                   "isAccessibleForFree": True, "dateModified": TODAY,
                   "measurementTechnique": "Every run reports start and end to the RunVouch API; alerts are raised by eight detectors in the same transaction that ends the run; each finished run is hashed into a daily Merkle root anchored with OpenTimestamps.",
                   "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json",
                                     "contentUrl": BASE + "/api/failure-rates.json"}],
                   "variableMeasured": [{"@type": "PropertyValue", "name": k, "value": v} for k, v in _soorten.items()]}
    (OUT / "api").mkdir(parents=True, exist_ok=True)
    (OUT / "api" / "failure-rates.json").write_text(json.dumps({
        "source": "RunVouch, https://runvouch.com/how-often-jobs-fail",
        "license": "CC BY 4.0",
        "generated": TODAY,
        "window_days": 30,
        "fleet": {"agents": _st["agents30"], "description": "one production fleet running a data business: scrapers, refreshes, health checks, report builders and a handful of LLM jobs"},
        "runs": {"finished": _st["runs30"], "failed": _st["fails30"], "ok": _st["ok30"],
                 "failure_rate_percent": round(100 * _st["fails30"] / _st["runs30"], 2)},
        "alerts_by_kind": _soorten,
        "kind_meaning": _KIND_UITLEG,
        "median_seconds_to_alert": round(_st["lag"], 1) if _st["lag"] is not None else None,
        "proof": {"days_sealed": _st["days"], "days_anchored_in_bitcoin": _st["anchored"],
                  "runs_in_chain": _st["day_runs"], "first_day": _st["first_day"],
                  "day_files": API + "/proof/", "verify_in_browser": BASE + "/verify"},
        "limits": ["One fleet, not an industry average.",
                   "Mostly small scheduled jobs; the median run takes about a second.",
                   "The record is what each client reported: a client that misreports its own cost produces a faithful record of the misreport.",
                   "A job nobody registered produces no alerts, so unmonitored work is invisible here by definition.",
                   "TEST alerts are excluded."],
    }, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    # Een citaat heeft een doel nodig dat niet meer verandert. Het weekbestand hierboven beweegt elke week mee,
    # dus er staat per maand ook een kopie naast: die groeit binnen de maand mee en ligt daarna stil. Wie ons
    # aanhaalt wijst naar de maand, niet naar een getal dat morgen anders is.
    _maand = OUT / "api" / f"failure-rates-{TODAY[:7]}.json"
    _maand.write_text((OUT / "api" / "failure-rates.json").read_text(encoding="utf-8"), encoding="utf-8")
    # ── Observability of waakhond ──────────────────────────────────────────────
    # Dertien vs-pagina's vergelijken ons met een genoemd product. Geen enkele beantwoordt de vraag die daarvoor
    # komt: welk soort gereedschap heb ik hier eigenlijk nodig. Die vraag stelt iedereen die drie tabbladen open
    # heeft met Langfuse, Healthchecks en ons, en niemand beantwoordt hem neutraal omdat iedereen een van de drie
    # verkoopt. Deze pagina wijst mensen ook naar de anderen, en dat is niet grootmoedig maar rekenwerk: wie hier
    # met de verkeerde behoefte binnenkomt, zegt binnen een maand op.
    _keuze = f"""<main><div class="wrap doc"><h1>Observability, a heartbeat, or a watchdog?</h1>
<p class="lead muted">Three categories get sold as if they compete. They solve different problems, and the one you need depends on a question nobody asks you first: who is watching when this runs?</p>

<h2>The three, in one line each</h2>
<p><b>Tracing and observability</b> (Langfuse, LangSmith, Helicone, Arize) record what happened inside a run: prompts, tokens, latency, tool calls, the chain of thought. They are built for the run you are already looking at, while you are building it.</p>
<p><b>A heartbeat monitor</b> (Healthchecks.io, Dead Man's Snitch, Cronitor) records that a run checked in. They are built for the schedule, not for the work: the job pings, the page stays green.</p>
<p><b>A watchdog</b> (this) records whether the work got done, for runs nobody is looking at. Start, end, cost, evidence, and an alert when any of it is missing or wrong.</p>

<h2>Three questions that put you in one box</h2>
<p><b>Are you debugging, or are you asleep?</b> If you are iterating on a prompt and want to see why the model did something, you want tracing. Buy Langfuse or LangSmith, not us. We store no prompts and no outputs on purpose, so we cannot help you with that and never will.</p>
<p><b>Is checking in enough?</b> If the only thing that can go wrong is that the job does not run, a heartbeat is the right tool and Healthchecks.io is free, open source and excellent. Use it. You do not need us.</p>
<p><b>Can the job finish and still have failed?</b> This is the one that decides. A scraper that returns an empty list, a report builder whose upstream went quiet, an agent that hit a rate limit and gave up gracefully. All three exit zero, ping their monitor and show green. If that is your situation, neither of the first two categories will tell you.</p>

<h2>What that looks like in numbers</h2>
<p>Over 30 days our own fleet of {_st["agents30"]} scheduled jobs produced {sum(dict(_st["kinds"]).values())} alerts across {_st["runs30"]:,} runs. {dict(_st["kinds"]).get("MISSED", 0)} of them were "the run never started", which is the part a heartbeat catches. The rest were not: failures with an exit code, cost or duration drifting away from a job's own baseline, and runs that reported success while the file they promised was missing.</p>
<p>Full breakdown with what each kind means: <a href="/how-often-jobs-fail">how often does an unattended job actually fail</a>.</p>

<h2>They stack, and that is normal</h2>
<p>Tracing and a watchdog are not alternatives. Tracing answers "why did this run do that", a watchdog answers "should someone look at this run at all". Plenty of setups have both, with the watchdog as the thing that pages you and the tracer as the thing you open once it has.</p>
<p>The one pairing that is genuinely redundant is two heartbeat monitors. Pick one.</p>

<h2>The part only one of the three has</h2>
<p>A record you can prove was not edited afterwards. Every finished run here is hashed, every day of hashes sealed into a Merkle root, every root chained to the day before and anchored in Bitcoin. No tracer and no heartbeat does this, because their record is a row in their own database and you are asked to trust it.</p>
<p>That matters in exactly one situation: when someone other than you has to believe the record. <a href="/verify">Recompute a real run yourself</a>, no account, and see <a href="/eu-ai-act">what it does and does not cover</a> for the EU AI Act.</p>

<h2>Compare us against a specific tool</h2>
<p>Each of these says where the other one is better, because a comparison that never does is an advert: <a href="/vs/">all comparisons</a>.</p>
<p class="small muted">If you read this and conclude you need one of the others, that is a good outcome. Somebody who arrives with the wrong need cancels within a month, and we would rather not have the month.</p>
</div></main>"""
    # ── Zelf hosten ────────────────────────────────────────────────────────────
    # De grootste groep in dit hokje host zelf: Uptime Kuma staat op 91.257 sterren in vier jaar en Healthchecks
    # op 10.320 in elf. Die mensen zoeken letterlijk op self-hosted, ze proberen het dezelfde avond, en ze vertellen
    # het door. Wij stonden er met een zin op de prijspagina. Deze pagina geeft ze de commando's, en zegt eerlijk
    # wanneer Healthchecks de betere keuze is: wie met de verkeerde verwachting begint, is binnen een week weg.
    _zelf = f"""<main><div class="wrap doc"><h1>Run it yourself</h1>
<p class="lead muted">MIT licensed, one server file, one client file and a SQLite database. No external service is required to run it, and the hosted version and the self-hosted one are the same code.</p>

<h2>Five commands</h2>
<pre><code>git clone https://github.com/runvouch/runvouch &amp;&amp; cd runvouch
python3 -m venv .venv &amp;&amp; .venv/bin/pip install -r requirements.txt
cp .env.example .env          # nothing in it is required to boot
.venv/bin/uvicorn runvouch.server:app --host 127.0.0.1 --port 8787
curl localhost:8787/health</code></pre>
<p>That is a working install. The database creates itself on first start under <code>data/</code>, every setting has a default, and the detectors begin sweeping straight away. Put it behind nginx or a tunnel when you want it reachable, and set <code>RUNVOUCH_PUBLIC_URL</code> so the proof files point at the right host.</p>

<h2>What runs where</h2>
<p><b>The server</b> is <code>runvouch/server.py</code>: the API, the detectors, the alert delivery, the proof chain and the dashboard, in one file on FastAPI and SQLite. Two dependencies, pinned.</p>
<p><b>The client</b> is <code>runvouch/cli.py</code>: standard library only, no dependencies, ever. Copy that one file onto a machine and <code>rv run</code> works. It also fails open, so a monitoring outage can never take down the job it watches.</p>
<p><b>The proof rules</b> are <code>runvouch/proof.py</code>, and <code>templates/verify_proof.py</code> repeats them on purpose so a reader can check a run without importing anything of ours.</p>
<p>Nothing calls home. Alerts go where you point them: e-mail through your own Resend key, Telegram, Slack, a webhook, or nowhere at all.</p>

<h2>What you give up, honestly</h2>
<p><b>The Bitcoin anchor needs one more package.</b> The hash chain works out of the box; anchoring the daily root with OpenTimestamps needs the <code>ots</code> client installed. Without it the chain still seals and still verifies, it just has no third party attesting to the date.</p>
<p><b>Alerting needs a channel.</b> Self-hosted with no Resend key and no Telegram token means the detectors fire and nobody hears it. Set one before you rely on it.</p>
<p><b>You are the uptime.</b> A watchdog on the same machine as the jobs it watches shares their fate. That is fine for a homelab and wrong for anything that matters: run it somewhere else, or let us run it.</p>

<h2>When Healthchecks.io is the better answer</h2>
<p>If what you need is "tell me when cron did not fire", Healthchecks.io has done exactly that since 2015, it is open source, it is excellent, and it has eleven years of people finding its edge cases. Use it. We would rather say that here than have you find out in a month.</p>
<p>Where this one differs is what it does after the job checks in: evidence that the work actually happened, cost and duration drift against the job's own baseline, retry storms, and a per-run record that cannot be edited afterwards. The full comparison, including where they win: <a href="/vs/healthchecks">vs Healthchecks.io</a>.</p>

<h2>Tests are part of the deal</h2>
<p>The suite is {_TESTS} tests and runs in under half a minute with no network. If you fork this, that suite is how you know your change did not break a detector.</p>
<pre><code>.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q tests</code></pre>

<h2>The hosted version</h2>
<p>Same code, and free for 3 agents with every detector on. The reason to use it is that somebody else is awake when your machine is not: <a href="/#signup">get a free key</a>. Moving between the two is a change of one environment variable, because the client only knows a URL and a key.</p>
<p class="small muted">MIT. Source on <a href="https://github.com/runvouch/runvouch">GitHub</a>. Issues and pull requests are read by a person.</p>
</div></main>"""
    page("/self-hosted", "Self-hosted cron and AI agent monitoring: run RunVouch yourself",
         "MIT licensed, one server file and a SQLite database, five commands to a working install. What you give up "
         "when you self-host, and when Healthchecks.io is the better answer.",
         _zelf, [ORG_LD], article=True)

    page("/observability-or-watchdog", "Observability, a heartbeat, or a watchdog? Which one you actually need",
         "Tracing tells you what happened inside a run. A heartbeat tells you it checked in. A watchdog tells you "
         "whether the work got done while nobody was looking. Three questions that decide which one you need, and "
         "when the answer is one of the others.",
         _keuze, [ORG_LD], article=True)

    page("/how-often-jobs-fail", f"How often does an unattended job actually fail? Real numbers from {_st['runs30']:,} runs",
         f"Measured over {_st['runs30']:,} runs by {_st['agents30']} scheduled agents in 30 days: {_fp:.1f} percent failed, "
         f"{_tot_alerts} alerts in total, broken out by kind. The rarest failure is the one no heartbeat monitor can see.",
         _faal, [ORG_LD, _dataset_ld], article=True)

    page("/stats", "RunVouch in numbers: our own agents, last 30 days",
         f"Real figures from the fleet that runs RunVouch itself: {_st['runs30']} runs by {_st['agents30']} agents in 30 days, {_pct:.1f}% failed, {_st['noev']} green runs without evidence, median time to alert {_lag}. Updated weekly.",
         _body, [ORG_LD])

# ───────────────────────── misc pages ─────────────────────────
# ───────────────────── VERIFY IT YOURSELF ─────────────────────
# Every tool in the cron and agent monitoring comparisons can show a green tick. None of them can show a proof that
# the tick was not edited afterwards. That difference sat under /proof/days/, where only a reader who already
# believed us would look, so this page hands a stranger one real run from our own fleet and lets him break it in
# his own browser. The sample is checked against the leaf hash the server stored on the day itself: if those two
# disagree the page is not built, because a verification demo that cannot itself be verified is worse than none.
def _proof_sample():
    import sqlite3
    import sys as _sys
    db = ROOT.parent / "data" / "runvouch.db"
    if not db.exists():
        return None
    _sys.path.insert(0, str(ROOT.parent))
    try:
        from runvouch import proof as pf
    except Exception:
        return None
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    leaf_sql = ("SELECT id, leaf_hash FROM (SELECT id, leaf_hash, ended FROM runs WHERE leaf_hash IS NOT NULL "
                "UNION SELECT id, leaf_hash, ended FROM run_leaves) WHERE ended>=? AND ended<? ORDER BY id, leaf_hash")
    for day in c.execute("SELECT * FROM proof_days WHERE n_runs BETWEEN 2 AND 600 ORDER BY date DESC LIMIT 14"):
        t0 = datetime.datetime.strptime(day["date"], "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp()
        rows = c.execute(leaf_sql, (t0, t0 + 86400)).fetchall()
        leaves = [r["leaf_hash"] for r in rows]
        if pf.merkle_root(leaves) != day["root"]:
            continue                       # the day file and the database disagree: never publish that as a demo
        # a failed run teaches more than a green one: the record says fail and the hash says nobody changed it later
        order = sorted(range(len(rows)), key=lambda i: 0 if _is_fail(c, rows[i]["id"]) else 1)
        for i in order:
            run = c.execute("SELECT * FROM runs WHERE id=?", (rows[i]["id"],)).fetchone()
            if not run or run["ended"] is None:
                continue                   # purged by retention: the leaf lives on, the record to show does not
            agent = c.execute("SELECT * FROM agents WHERE id=?", (run["agent_id"],)).fetchone()
            if not agent:
                continue
            meta = json.loads(run["meta_json"] or "{}")
            ev = c.execute("SELECT tool, input_hash, ok, ts FROM tool_events WHERE account_id=? AND run_id=? ORDER BY id",
                           (agent["account_id"], run["id"])).fetchall()
            rec = {"run_id": run["id"], "agent": agent["name"], "account_id": agent["account_id"], "started": run["started"],
                   "ended": run["ended"], "status": run["status"], "cost": run["cost"], "tokens": run["tokens"],
                   "tool_calls": run["tool_calls"], "output_bytes": run["output_bytes"],
                   "evidence": json.loads(run["evidence_json"] or "{}"), "evidence_ok": run["evidence_ok"],
                   "source": run["source"],
                   "tool_events_hash": pf.tool_events_hash([(x["tool"], x["input_hash"], x["ok"], x["ts"]) for x in ev])}
            if "exit" in meta:
                rec["exit"] = meta["exit"]
            if pf.leaf_hash(rec) != rows[i]["leaf_hash"]:
                continue                   # the record no longer reproduces its own leaf: not a sample, a bug report
            return {"run_id": run["id"], "date": day["date"], "record": rec, "leaf_hash": rows[i]["leaf_hash"],
                    # the text, not only the object: json.dumps writes 0.0 where a browser would write 0, and that
                    # one character changes the hash. The page shows this string and hashes what it parses back.
                    "record_text": json.dumps(rec, indent=1, sort_keys=True),
                    "merkle_path": [[h, s] for h, s in pf.merkle_path(leaves, i)], "root": day["root"],
                    "prev": day["prev"], "chain_hash": day["chain_hash"], "n_runs": len(leaves),
                    "ots_status": day["ots_status"] or "", "index": i,
                    "leaves": [{"run_id": r["id"], "leaf": r["leaf_hash"]} for r in rows],
                    "day_url": f"{API}/proof/days/{day['date']}.json", "ots_url": f"{API}/proof/days/{day['date']}.ots"}
    return None


def _is_fail(c, run_id):
    r = c.execute("SELECT status, evidence_ok FROM runs WHERE id=?", (run_id,)).fetchone()
    return bool(r) and (r["status"] == "fail" or r["evidence_ok"] == 0)


# the curl line on /verify points here, so the verifier has to be next to the sample, not only on GitHub
(OUT / "dl").mkdir(parents=True, exist_ok=True)
(OUT / "dl" / "verify_proof.py").write_text((ROOT.parent / "templates" / "verify_proof.py").read_text(encoding="utf-8"), encoding="utf-8")

_ps = _proof_sample()
if _ps:
    (OUT / "verify-sample.json").write_text(json.dumps(_ps, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    _anchored = _ps["ots_status"].startswith("bitcoin:")
    _anchor_line = ("That root is anchored in the Bitcoin blockchain by OpenTimestamps, so the date cannot be moved either."
                    if _anchored else "That root is queued for an OpenTimestamps anchor in the Bitcoin blockchain; the .ots file next to the day file carries the stamp.")
    _VERIFY_JS = r"""
<script>
const P_URL='/verify-sample.json';let P=null;
const enc=new TextEncoder();
async function sha(s){const b=await crypto.subtle.digest('SHA-256',enc.encode(s));return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('')}
// A JSON reader that keeps every number exactly as it was written. The server writes 0.0 and JSON.stringify would
// write 0; that one character is the difference between a hash that matches and one that does not.
function Num(l){this.lit=l}
function parse(t){let i=0;
 const ws=()=>{while(i<t.length&&' \t\n\r'.indexOf(t[i])>=0)i++};
 function str(){const j=i;i++;while(t[i]!=='"'){if(t[i]==='\\')i++;i++}i++;return JSON.parse(t.slice(j,i))}
 function val(){ws();const c=t[i];
  if(c==='{'){i++;const o={};ws();if(t[i]==='}'){i++;return o}for(;;){ws();const k=str();ws();i++;o[k]=val();ws();if(t[i]===','){i++;continue}i++;return o}}
  if(c==='['){i++;const a=[];ws();if(t[i]===']'){i++;return a}for(;;){a.push(val());ws();if(t[i]===','){i++;continue}i++;return a}}
  if(c==='"')return str();
  if(t.startsWith('true',i)){i+=4;return true}
  if(t.startsWith('false',i)){i+=5;return false}
  if(t.startsWith('null',i)){i+=4;return null}
  const j=i;while(i<t.length&&'-+.eE0123456789'.indexOf(t[i])>=0)i++;
  if(j===i)throw new Error('not JSON at '+i);return new Num(t.slice(j,i))}
 const v=val();ws();if(i<t.length)throw new Error('trailing text');return v}
function canon(v){
 if(v===null)return 'null';if(v===true)return 'true';if(v===false)return 'false';
 if(v instanceof Num)return v.lit;
 if(typeof v==='string')return JSON.stringify(v);
 if(typeof v==='number')return Number.isInteger(v)?String(v):JSON.stringify(v);
 if(Array.isArray(v))return '['+v.map(canon).join(',')+']';
 return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canon(v[k])).join(',')+'}'}
async function merkle(hs){if(!hs.length)return await sha('');let l=hs.slice();
 while(l.length>1){if(l.length%2)l.push(l[l.length-1]);const n=[];for(let i=0;i<l.length;i+=2)n.push(await sha(l[i]+l[i+1]));l=n}return l[0]}
function row(ok,label,detail){return '<tr><td class="vok">'+(ok?'PASS':'FAIL')+'</td><td>'+label+'<div class="small muted mono">'+detail+'</div></td></tr>'}
function out(h){document.getElementById('vout').innerHTML=h}
async function verify(){
 const box=document.getElementById('rec');
 let rec;try{rec=parse(box.value)}catch(e){return out('<p class="bad">That is not valid JSON: '+e.message+'</p>')}
 out('<p class="muted">Hashing in your browser...</p>');
 const leaf=await sha(canon(rec));
 const step1=leaf===P.leaf_hash;
 let h=leaf;for(const [sib,side] of P.merkle_path){h=await sha(side==='left'?sib+h:h+sib)}
 const step2=h===P.root;
 const rebuilt=await merkle(P.leaves.map(x=>x.leaf));
 const step3=rebuilt===P.root;
 const listed=P.leaves.some(x=>x.run_id===P.run_id&&x.leaf===leaf);
 const chain=await sha(P.prev+':'+P.date+':'+P.root);
 const step4=chain===P.chain_hash;
 const all=step1&&step2&&step3&&step4&&listed;
 out('<p class="'+(all?'good':'bad')+'"><b>'+(all?'All four checks passed. This record is the one that was sealed on '+P.date+'.':'At least one check failed. The record below is not the record that was sealed.')+'</b></p>'
  +'<table class="vtab">'
  +row(step1,'The record hashes to its leaf','sha256(canonical json) = '+leaf.slice(0,32)+'...')
  +row(listed&&step2,'That leaf sits under the day root','walked '+P.merkle_path.length+' steps to '+h.slice(0,32)+'...')
  +row(step3,'The day root follows from all '+P.n_runs+' published leaves','recomputed '+rebuilt.slice(0,32)+'...')
  +row(step4,'The day sits in the chain','sha256(prev:'+P.date+':root) = '+chain.slice(0,32)+'...')
  +'</table>')}
async function tamper(){
 // a text edit on purpose: JSON.parse plus stringify would quietly rewrite the numbers and break the hash for the
 // wrong reason. This changes exactly the one thing a run report would be worth lying about.
 const box=document.getElementById('rec');const t=box.value;
 box.value=/"status": ?"ok"/.test(t)?t.replace(/"status": ?"ok"/,'"status": "fail"')
  :/"status": ?"fail"/.test(t)?t.replace(/"status": ?"fail"/,'"status": "ok"')
  :t.replace(/"output_bytes": ?(\d+)/,(m,n)=>'"output_bytes": '+(Number(n)+1));
 await verify()}
async function reset(){document.getElementById('rec').value=P.record_text;await verify()}
(async()=>{P=await (await fetch(P_URL)).json();await reset()})();
</script>"""
    _VERIFY_BODY = """<main><div class="wrap doc"><h1>Verify a run yourself</h1>
<p class="lead muted">Below is one real run from the fleet that runs this company, sealed on __DATE__ and never touched since. Nothing here trusts us: your browser recomputes every hash, and you can edit any field and watch it break.</p>
<div class="card" style="margin:1.4rem 0"><p class="small muted" style="margin:0 0 .5rem">The sealed record of run <span class="mono">__RUNID__</span>. Change a character and press Verify.</p>
<textarea id="rec" spellcheck="false" style="width:100%;min-height:19rem;font:13px/1.55 var(--mono,monospace);padding:.8rem;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:inherit"></textarea>
<p style="margin:.8rem 0 0"><button class="btn" onclick="verify()">Verify</button> <button class="btn ghost" onclick="tamper()">Change one value</button> <button class="btn ghost" onclick="reset()">Reset</button></p></div>
<div id="vout"></div>
<h2>What those four checks mean</h2>
<p>The first says the record still hashes to its leaf, so not one byte of it moved. The second walks that leaf up the Merkle tree of the day and lands on the day root. The third rebuilds that same root from all __N__ leaves published for that day, so the path we handed you cannot have been invented. The fourth links the day to the day before it, which is why a single edited run would have to be followed by every day since. __ANCHOR__</p>
<p class="muted">Your browser never sends anything back. The page holds the day's leaf list, and the authoritative copy is the file the server publishes: <a class="mono" href="__DAYURL__">__DAYURL__</a>, with the timestamp proof next to it at <a class="mono" href="__OTSURL__">.ots</a>.</p>
<h2>Without a browser</h2>
<p>The same four checks in 90 lines of standard-library Python, written so it imports nothing of ours:</p>
<pre><code>curl -sO https://runvouch.com/dl/verify_proof.py
curl -s __DAYURL__ &gt; day.json
curl -s https://runvouch.com/verify-sample.json &gt; proof.json
python3 verify_proof.py proof.json day.json</code></pre>
<h2>Your own runs</h2>
<p>Every finished run you send gets the same receipt, on the free plan too. Fetch it with <span class="mono">rv proof RUN_ID</span> and drop the JSON into the box above, or run the script against it. What is never in the record: your prompts, your outputs and the contents of your files. Only their sizes and hashes.</p>
<p class="muted">Why this exists is on <a href="/verifiable-agent-runs">verifiable agent runs</a>; the hashing rules are in <a href="/docs/proof">the proof docs</a>, and the numbers behind this fleet are on <a href="/stats">in numbers</a>.</p>
</div></main>"""
    _VERIFY_BODY = (_VERIFY_BODY.replace("__DATE__", _ps["date"]).replace("__RUNID__", _ps["run_id"])
                    .replace("__N__", str(_ps["n_runs"])).replace("__ANCHOR__", _anchor_line)
                    .replace("__DAYURL__", _ps["day_url"]).replace("__OTSURL__", _ps["ots_url"])) + _VERIFY_JS
    page("/verify", "Verify a RunVouch run yourself, in your browser",
         "One real sealed run from our own fleet: recompute its hash, walk the Merkle path, rebuild the day root from every published leaf and check the chain. Edit a field and watch it break. No account, nothing leaves your browser.",
         _VERIFY_BODY, [ORG_LD])

# ───────────────────── PUBLIC FLEET (a real fleet, live, no account) ─────────────────────
# The fleet endpoint has been public JSON since the start and nothing rendered it, so the only place a stranger could
# see RunVouch actually running was a screenshot. A screenshot of a dashboard with no data is worse than none: the one
# in the directory listings showed 48 agents all waiting, zero cost, zero alerts. This page is the live thing instead,
# and it doubles as the status page a Team customer can point their own users at.
def _fleets():
    import sqlite3
    db = ROOT.parent / "data" / "runvouch.db"
    if not db.exists():
        return []
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [(r[0], r[1]) for r in c.execute("SELECT slug, title FROM public_fleets ORDER BY slug")]
    except sqlite3.OperationalError:
        return []


_FLEET_JS = r"""
<script>
const A='__API__', SLUG='__SLUG__';
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function ago(ts){if(!ts)return 'never';const s=Math.max(0,Date.now()/1000-ts);
 if(s<90)return Math.round(s)+' s ago';if(s<5400)return Math.round(s/60)+' min ago';
 if(s<172800)return Math.round(s/3600)+' h ago';return Math.round(s/86400)+' days ago'}
function every(s){if(!s)return 'on demand';if(s%86400===0)return s/86400+' d';if(s%3600===0)return s/3600+' h';return Math.round(s/60)+' min'}
function pct(r){return !r||!r.runs?'-':Math.round(100*r.ok/r.runs)+'% of '+r.runs}
function state(a){
 if(a.paused)return ['paused','muted'];
 if(a.open_alert)return [String(a.open_alert.kind||'alert').toLowerCase(),'bad'];
 if(a.late)return ['late','warn'];
 if(a.last_run&&a.last_run.status==='fail')return ['failed','bad'];
 if(a.last_run&&a.last_run.ended)return ['vouched','ok'];
 return ['waiting','muted']}
fetch(A+'/public/fleet/'+SLUG+'.json').then(r=>r.json()).then(j=>{
 const ags=j.agents||[];
 const open=ags.filter(a=>a.open_alert).length, late=ags.filter(a=>a.late&&!a.open_alert).length;
 const runs30=ags.reduce((n,a)=>n+((a.rates&&a.rates['30d']&&a.rates['30d'].runs)||0),0);
 const ok30=ags.reduce((n,a)=>n+((a.rates&&a.rates['30d']&&a.rates['30d'].ok)||0),0);
 document.getElementById('f-cards').innerHTML=
   '<div class="card"><div class="big grad">'+ags.length+'</div><h3>agents watched</h3></div>'+
   '<div class="card"><div class="big grad">'+runs30.toLocaleString('en')+'</div><h3>runs in 30 days</h3><p>'+(runs30?Math.round(100*ok30/runs30):0)+'% ended ok.</p></div>'+
   '<div class="card"><div class="big grad">'+open+'</div><h3>open alerts</h3><p>'+late+' late right now.</p></div>';
 document.getElementById('f-rows').innerHTML=ags.map(a=>{
   const [lab,cls]=state(a);
   return '<tr><td><b>'+esc(a.name)+'</b><div class="small muted">'+esc(a.label||'')+'</div></td>'+
   '<td><span class="pill '+cls+'">'+esc(lab)+'</span></td>'+
   '<td class="small">'+every(a.cadence_s)+'</td>'+
   '<td class="small">'+(a.last_run?ago(a.last_run.ended||a.last_run.started):'never')+'</td>'+
   '<td class="small">'+pct(a.rates&&a.rates['7d'])+'</td>'+
   '<td class="small">'+pct(a.rates&&a.rates['30d'])+'</td></tr>'}).join('');
 document.getElementById('f-time').textContent='Read from the public endpoint at '+(j.time||'').replace('T',' ').replace('Z',' UTC')+'.';
}).catch(()=>{document.getElementById('f-time').textContent='The public endpoint could not be reached from your browser right now. The raw data is one click away below.'});
</script>"""

_FLEET_BODY = """<main><div class="wrap doc"><h1>__TITLE__</h1>
<p class="lead muted">A real fleet, watched by RunVouch, live on this page. No account, no login, nothing cached: your browser reads the same public endpoint anyone can read.</p>
<div class="grid g3" id="f-cards"></div>
<h2>Every agent</h2>
<table><tr><th>Agent</th><th>State</th><th>Every</th><th>Last run</th><th>7 days</th><th>30 days</th></tr><tbody id="f-rows"></tbody></table>
<p class="small muted" id="f-time">Loading...</p>
<h2>What you are looking at</h2>
<p>These are scheduled jobs that run whether anyone is watching or not: scrapers, report builders, refreshes, monitors. <b>Vouched</b> means the run finished and left the evidence it promised. <b>Late</b> means the next run is past its cadence plus grace and nobody has seen it yet. A failure or a run without evidence raises an alert within minutes, and the owner hears about it on Telegram, Slack, e-mail or a webhook.</p>
<p>Every finished run in this list also has a tamper-evident proof. Pick one apart yourself on <a href="/verify">verify a run</a>, or read the raw feed behind this page: <a class="mono" href="__API__/public/fleet/__SLUG__.json">__API__/public/fleet/__SLUG__.json</a></p>
<p class="muted">Any account can publish a fleet like this. It is the same data the owner sees, minus everything private: no costs, no run contents, no agent the owner did not mark public. Our own 30-day numbers are on <a href="/stats">in numbers</a>.</p>
</div></main>"""

_fl = _fleets()
for _slug, _title in _fl:
    page(f"/fleet/{_slug}", f"{_title}: a real fleet watched by RunVouch, live",
         f"Live public status of {_title}: every scheduled agent with its state, cadence, last run and success rate over 7 and 30 days, read straight from the public endpoint. No account needed.",
         _FLEET_BODY.replace("__TITLE__", _title).replace("__SLUG__", _slug).replace("__API__", API)
         + _FLEET_JS.replace("__API__", API).replace("__SLUG__", _slug), [ORG_LD])

# ───────────────────── EU AI ACT (the obligation is live, the standard is not) ─────────────────────
# Annex III obligations apply since 2 August 2026 and Article 26 makes a deployer keep its own logs for at least six
# months, while the technical standards for Article 12 (prEN 18229-1, ISO/IEC DIS 24970) are still drafts. A page that
# says plainly what a run record does and does not cover is worth more to that reader than a page that claims
# compliance, which no tool can deliver. Everything here is what the product does today; nothing is promised.
_ACT = """<main><div class="wrap doc"><h1>RunVouch and the EU AI Act</h1>
<p class="lead muted">Article 12 wants automatic records of what an AI system did. Article 26 makes the organisation using it keep those records for at least six months. This page says exactly which part of that a RunVouch run record covers, and which part it does not.</p>
<p>The obligations for the systems in Annex III apply since 2 August 2026. The technical standards that will say how to satisfy Article 12 are still drafts (prEN 18229-1, ISO/IEC DIS 24970), so what exists in the meantime is the text of the regulation and whatever your records can actually show.</p>

<h2>What a run record contains</h2>
<table><tr><th>The regulation asks for</th><th>What RunVouch records, automatically</th></tr>
<tr><td>Automatic logging over the lifetime of the system, not documentation written by hand (Art. 12(1))</td><td>Every run reports itself: the client wraps the command, or the job calls a ping URL. Nothing is typed by a person.</td></tr>
<tr><td>The period of each use: start and end date and time (Art. 12(2), for the systems where that list applies)</td><td><code>started</code> and <code>ended</code> per run, to the second, plus the exit status and the duration.</td></tr>
<tr><td>Data for operational monitoring by the deployer (Art. 12(2)(c))</td><td>Cost, token count, tool calls, output size, and the evidence verdict: whether the file, URL or assertion the run promised was actually there.</td></tr>
<tr><td>Records a deployer keeps under its own control (Art. 26(6))</td><td>Export of every run as CSV or JSON on the Team plan, so the record lives in your systems and not only in ours.</td></tr>
<tr><td>Records that can be relied on afterwards</td><td>The part no log file has: each finished run is hashed into a daily Merkle root, chained to the day before and anchored in Bitcoin. A record cannot be edited after the fact, by you or by us, and anyone can recompute it. <a href="/verify">Try it on a real run.</a></td></tr></table>

<h2>What it does not cover</h2>
<p>Being straight about this is the whole point of a page like this.</p>
<ul>
<li><b>Not the content of the work.</b> RunVouch never stores prompts, model outputs, or the contents of the files a run reads or writes. It stores that they happened, their sizes and their hashes. Where Article 12 asks for input data or a reference database for a specific class of system, a run record does not give you that.</li>
<li><b>Not a conformity assessment.</b> No tool makes a system compliant. This is a record of execution, one input to whatever your assessment needs.</li>
<li><b>Not six months by default.</b> Full run records are kept 7 days on Free and 90 days on Solo and Team. If you need to hold six months or more, export them: Team gives CSV and JSON of every run, and the per-run hash stays in the public proof chain permanently, so an exported record can still be proved unaltered years later, after we no longer hold the detail ourselves.</li>
<li><b>Not legal advice.</b> Whether your system falls under Annex III, and what your records must contain, is a question for your own counsel.</li>
</ul>

<h2>Why the hash matters here</h2>
<p>A log file proves what a system wrote down. It does not prove that nobody changed it afterwards, and a record that can be edited is worth what the auditor thinks of the person holding it. RunVouch seals each day of runs into a Merkle root, chains that root to the previous day, and stamps it with OpenTimestamps into the Bitcoin blockchain. To alter one run after the fact you would have to alter every day since, and the anchor makes even that visible.</p>
<p>Nothing in that chain requires trusting us: the day files are public, the rules are 90 lines of standard-library Python, and <a href="/verify">the verification runs in your browser</a> with no account.</p>

<h2>Where to start</h2>
<p>Take a free key, wrap one scheduled job, and look at what the record contains before you decide it is useful: <a href="/#signup">get a free key</a>. The mechanism is on <a href="/docs/proof">docs/proof</a>, a live fleet is on <a href="/fleet/datasignals">a real fleet</a>, and our own 30-day numbers are on <a href="/stats">in numbers</a>.</p>
<p class="small muted">Sources: <a href="https://artificialintelligenceact.eu/article/12/">Article 12, record-keeping</a> and <a href="https://artificialintelligenceact.eu/article/26/">Article 26, obligations of deployers</a>. Read them yourself; this page is a description of a product, not of the law.</p>
</div></main>"""
page("/eu-ai-act", "RunVouch and the EU AI Act: what a run record proves",
     "Article 12 wants automatic records of what an AI system did and Article 26 makes the deployer keep them for six months. What a RunVouch run record covers, what it does not, and why a tamper-evident hash matters for a log.",
     _ACT, [ORG_LD], article=True)

page("/contact", "Contact | RunVouch", "Questions, bugs, security reports or partnership ideas, reach the RunVouch team.", '''<main><div class="wrap doc"><h1>Contact</h1><p class="lead muted">Support, billing, security or just an idea. Replies within one working day.</p>
<form id="cf" onsubmit="return sendContact(event)"><p><select id="ct" style="padding:.8rem;border-radius:10px;background:#040308;color:var(--fg);border:1px solid var(--line2);font:inherit"><option value="support">Support</option><option value="billing">Billing</option><option value="security">Security report</option><option value="partnership">Partnership / integration</option></select></p>
<p><input id="ce" type="email" required placeholder="you@company.com" style="width:100%;padding:.85rem 1rem;border:1px solid var(--line2);border-radius:12px;font:inherit;background:#040308;color:var(--fg)"></p>
<p><textarea id="cm" required minlength="5" rows="6" placeholder="What happened, what you expected, agent name if relevant…" style="width:100%;padding:.85rem 1rem;border:1px solid var(--line2);border-radius:12px;font:inherit;background:#040308;color:var(--fg)"></textarea></p>
<p><button class="btn" type="submit">Send</button> <span id="cs" class="muted small"></span></p></form>
<script>const tp=new URLSearchParams(location.search).get('topic');if(tp)document.getElementById('ct').value=tp;
async function sendContact(e){e.preventDefault();const s=document.getElementById('cs');s.textContent='Sending…';
try{const r=await fetch(API+'/contact',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('ce').value,message:document.getElementById('cm').value,topic:document.getElementById('ct').value})});
s.textContent=r.ok?'Sent. We reply by email within one working day.':'Could not send ('+r.status+'). Try again later.';if(r.ok)document.getElementById('cf').reset()}catch(err){s.textContent='Network error.'}return false}</script></div></main>''', [ORG_LD])
page("/status", "Status | RunVouch", "Is RunVouch itself up? Live checks from your browser, uptime per component over 24 hours to 90 days, and every outage since measurement began.", """<main><div class="wrap doc"><h1>Status</h1>
<p class="lead muted">Is RunVouch itself up right now, and has it been? This page is for anyone who depends on our alerts: if an alert did not arrive, start here.</p>
<p class="small muted">The "now" column is checked live from your browser against the production API. The uptime columns come from the API's own heartbeat: one row per minute the detector loop ran, published at <a href="__API__/status.json">status.json</a>. A gap longer than 3 minutes counts as an outage; our own watcher checks every minute from the public side. Nothing on this page is account-specific.</p>
<table><tr><th>Component</th><th>Now</th><th>24 h</th><th>7 d</th><th>30 d</th><th>90 d</th></tr>
<tr><td>API (api.runvouch.com)<br><span class="small muted">accepts runs and serves the dashboard</span></td><td id="s-api">checking</td><td id="u-api-24h">-</td><td id="u-api-7d">-</td><td id="u-api-30d">-</td><td id="u-api-90d">-</td></tr>
<tr><td>Detectors<br><span class="small muted">missed, stalled, failed, no evidence, budget</span></td><td id="s-det">checking</td><td id="u-det-24h">-</td><td id="u-det-7d">-</td><td id="u-det-30d">-</td><td id="u-det-90d">-</td></tr>
<tr><td>Alert delivery<br><span class="small muted">Telegram, e-mail, webhook, PagerDuty</span></td><td id="s-alerts">checking</td><td id="u-al-24h">-</td><td id="u-al-7d">-</td><td id="u-al-30d">-</td><td id="u-al-90d">-</td></tr>
<tr><td>Website and dashboard<br><span class="small muted">runvouch.com, /app</span></td><td id="s-app">checking</td><td colspan="4" class="small muted">same host as the API, through Cloudflare; up whenever the API row is up</td></tr></table>
<p class="small muted" id="s-meta">Loading the heartbeat record.</p>
<h2>Outages</h2>
<div id="s-incidents" class="small muted">Loading.</div>
<h2>Proof the service ran</h2>
<p class="small muted" id="s-proof">Every UTC day the API seals a Merkle root over all runs and anchors it in Bitcoin via OpenTimestamps. A sealed day is independent evidence the service was up that day; see <a href="__API__/proof/">proof/</a> and <a href="/verifiable-agent-runs">how verification works</a>.</p>
<p class="small muted">Check it yourself, without this page: <a href="__API__/health">__API__/health</a> answers with <code>"status":"ok"</code> when the API and its database are fine. Incidents are also written up in the <a href="/changelog">changelog</a>.</p>
</div></main>
<script>
const SAPI="__API__";
const pill=(cls,txt)=>'<span class="pill '+cls+'">'+txt+'</span>';
const pct=v=>v==null?'-':(v>=99.95?'100%':v.toFixed(2)+'%');
fetch(SAPI+'/health').then(async r=>{
  document.getElementById('s-api').innerHTML=r.ok?pill('ok','operational'):pill('bad','degraded');
  try{const j=await r.json();const c=j.checks||{};
    document.getElementById('s-det').innerHTML=c.detectors==='running'?pill('ok','running'):pill('bad',c.detectors||'unknown');
    const a=c.alert_delivery;document.getElementById('s-alerts').innerHTML=a==='ok'?pill('ok','operational'):a==='idle'?pill('ok','idle, nothing due'):pill('bad',a||'unknown');
  }catch(e){document.getElementById('s-alerts').textContent='unknown'}
}).catch(()=>{['s-api','s-det','s-alerts'].forEach(i=>document.getElementById(i).innerHTML=pill('bad','unreachable'))});
fetch('/app').then(r=>{document.getElementById('s-app').innerHTML=r.ok?pill('ok','operational'):pill('bad','degraded')}).catch(()=>{document.getElementById('s-app').innerHTML=pill('bad','unreachable')});
fetch(SAPI+'/status.json').then(r=>r.json()).then(j=>{
  const w=j.windows||{};
  for(const k of ['24h','7d','30d','90d']){const x=w[k]||{};
    document.getElementById('u-api-'+k).textContent=pct(x.detectors);document.getElementById('u-det-'+k).textContent=pct(x.detectors);document.getElementById('u-al-'+k).textContent=pct(x.alerts);}
  const t=(j.time||'').replace('T',' ').replace('Z',' UTC');
  document.getElementById('s-meta').textContent=j.measured_since?('Last heartbeat '+(j.last_heartbeat_age_s==null?'unknown':j.last_heartbeat_age_s+' s ago')+', checked '+t+'. Measured since '+j.measured_since+'; windows that start before that date are measured from it.'):'No heartbeat record yet.';
  const inc=j.incidents||[];
  document.getElementById('s-incidents').innerHTML=inc.length?'<table><tr><th>Started (UTC)</th><th>Component</th><th>Duration</th></tr>'+inc.slice().reverse().map(i=>'<tr><td>'+i.start.replace('T',' ').replace('Z','')+'</td><td>'+i.component+'</td><td>'+i.minutes+' min'+(i.ongoing?' (ongoing)':'')+'</td></tr>').join('')+'</table>'+((j.incidents_total||inc.length)>inc.length?'<p class="small muted">Showing the '+inc.length+' most recent of '+j.incidents_total+' recorded outages. Every minute we could not deliver is counted in the percentages above.</p>':''):'No outages since measurement began on '+(j.measured_since||'-')+'.';
  const p=j.sealed_days||{};if(p.count){document.getElementById('s-proof').insertAdjacentHTML('afterbegin',p.count+' sealed days so far, the latest '+p.last+'. ')}
}).catch(()=>{document.getElementById('s-meta').textContent='The heartbeat record could not be loaded.';document.getElementById('s-incidents').textContent='Unknown: the heartbeat record could not be loaded.'});
</script>
""".replace("__API__", API))
page("/security", "Security | RunVouch", "What RunVouch stores, how keys are handled, and how to report a vulnerability.", '''<main><div class="wrap doc"><h1>Security</h1>
<ul><li>API keys are stored as SHA-256 hashes; the plaintext key is shown once.</li><li>Tool inputs are hashed on the client or server for loop detection; prompts and outputs are never stored.</li><li>Evidence file checks run on your machine; only a boolean is transmitted.</li><li>Every finished run gets a hash that is chained per day and anchored in Bitcoin via OpenTimestamps, so a record cannot be altered afterwards without it showing; see <a href="/docs/proof">verifiable runs</a>. An auditor can verify a run with a standalone script and <code>ots verify</code>, without trusting us: <a href="/verifiable-agent-runs">how</a>.</li><li>All traffic is TLS via Cloudflare; infrastructure in the EU (Netherlands).</li><li>Per-key rate limits; alert credentials (Telegram token, webhook URL) are stored per account and used only to deliver your alerts.</li><li>Report vulnerabilities via the <a href="/contact?topic=security">contact form</a> (topic: security), see <a href="/.well-known/security.txt">security.txt</a>.</li></ul></div></main>''', [ORG_LD])
page("/privacy", "Privacy | RunVouch", "RunVouch privacy policy: the run metadata and account data we process, what we never store (prompts, outputs), retention, and how to delete your data.", f'''<main><div class="wrap doc"><h1>Privacy</h1><p>RunVouch (Netherlands) processes: your email (account identity, billing match), agent names and run metadata you send (timestamps, status, cost, token counts, tool names, input hashes, output sizes, evidence verdicts), alert delivery settings, and standard server logs (IP, user agent) kept 30 days. Runs, tool events and acknowledged alerts are purged after the history window of your plan (7 days on Free, 90 days on Solo and Team); the per-run leaf hash stays in the public proof chain. We do not sell data, do not send marketing email, and do not use third-party analytics that track you across sites. Payments are processed by {PROCESSOR}; card details never touch our servers. Delete your account and data any time via <a href="/contact">contact</a>. GDPR requests: same form.</p></div></main>''', [ORG_LD])
page("/terms", "Terms | RunVouch", "RunVouch terms of service: early-access status, monthly plans that cancel any time, acceptable use, and liability limits in plain language.", '''<main><div class="wrap doc"><h1>Terms of service</h1><p>RunVouch is provided as-is during early access. Free plans may be rate-limited. Paid plans renew monthly and can be cancelled any time; the current period is not refunded. Don't use RunVouch to monitor anything illegal, and don't attack the service. We may change these terms with notice on this page. Governing law: the Netherlands.</p></div></main>''', [ORG_LD])
_cl = "".join(f'<h3>{v} <span class="small muted">{d}</span></h3><ul>' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
               for v, d, items in RELEASES)
_cl += '<h3 class="small muted">Separately versioned packages</h3><ul>' + "".join(
    f"<li>{n} <span class=\"small muted\">{d}</span>: {t}</li>" for n, d, t in SIDE_RELEASES) + "</ul>"
page("/changelog", "Changelog | RunVouch", "What's new in RunVouch: releases of the API, CLI, Claude Code plugin, MCP server and detectors, with dates.", f'''<main><div class="wrap doc"><h1>Changelog</h1><p class="small muted">Current release: <b>{VERSION}</b>, the same version <a href="{API}/health">{API}/health</a>, PyPI and npm report. Incidents are on the <a href="/status">status page</a>.</p>{_cl}</div></main>''', [ORG_LD])
# ───────────────────────── BLOG ─────────────────────────
ARTICLES = json.loads((ROOT / "articles.json").read_text(encoding="utf-8"))["articles"] if (ROOT / "articles.json").exists() else []
BLOG_DATE = "2026-08-25"   # terugval voor de eerste lichting artikelen; nieuwe dragen hun eigen "date"

# verified sources per article (only URLs that resolve); anything we cannot link, we do not claim
SOURCES = {
    "claude-code-cron-unexpected-api-bill-runaway-cost-overnight": [("Claude Code issue #37686: $1,800+ in two days", "https://github.com/anthropics/claude-code/issues/37686"), ("dev.to: \"I let my AI agent run overnight, it cost $437\"", "https://dev.to/magicrails/i-let-my-ai-agent-run-overnight-it-cost-437-dd7")],
    "claude-code-routine-failed-silently-scheduled-task-didnt-run": [("Claude Code docs: scheduled tasks, limitations", "https://code.claude.com/docs/en/scheduled-tasks#limitations"), ("Claude Code docs: routines", "https://code.claude.com/docs/en/routines")],
    "dead-mans-switch-for-ai-agents": [("Healthchecks.io docs", "https://healthchecks.io/docs/"), ("Claude Code issue #37686", "https://github.com/anthropics/claude-code/issues/37686")],
    "openclaw-stuck-in-polling-loop-150-no-alert": [("OpenClaw issue #16808", "https://github.com/openclaw/openclaw/issues/16808")],
    "prove-what-your-ai-agent-did-audit-trail-for-unattended-agents": [("RunVouch docs: verifiable runs (what is hashed, limits)", "https://runvouch.com/docs/proof"), ("Public proof index, api.runvouch.com/proof/", "https://api.runvouch.com/proof/"), ("Day file 2026-08-25", "https://api.runvouch.com/proof/days/2026-08-25.json"), ("verify_proof.py, standalone verifier", "https://github.com/runvouch/runvouch/blob/main/templates/verify_proof.py"), ("OpenTimestamps", "https://opentimestamps.org/"), ("OpenTimestamps client", "https://github.com/opentimestamps/opentimestamps-client"), ("EU AI Act, Article 12 (record-keeping)", "https://artificialintelligenceact.eu/article/12/"), ("EU AI Act, Article 26 (obligations of deployers)", "https://artificialintelligenceact.eu/article/26/")],
    "7-ways-unattended-ai-agents-fail-silently": [("Claude Code issue #37686", "https://github.com/anthropics/claude-code/issues/37686"), ("OpenClaw issue #16808", "https://github.com/openclaw/openclaw/issues/16808"), ("dev.to: $437 overnight", "https://dev.to/magicrails/i-let-my-ai-agent-run-overnight-it-cost-437-dd7")],
}
def _sources_html(art):
    src = SOURCES.get(art["slug"]) or []
    return ('<h2>Sources</h2><ul class="muted">' + "".join(f'<li><a href="{u}" rel="noopener">{t}</a></li>' for t, u in src) + '</ul>') if src else ""
def _related_html(art):
    others = [a for a in ARTICLES if a["slug"] != art["slug"]][:3]
    return '<h2>Related field notes</h2><ul>' + "".join(f'<li><a href="/blog/{a["slug"]}">{a["title"]}</a></li>' for a in others) + '</ul>'
for art in ARTICLES:
    body = f'''<main><div class="wrap doc"><p class="small muted"><a href="/blog/">Field notes</a> · {art.get("date") or BLOG_DATE} · RunVouch</p><h1>{art["title"]}</h1><p class="lead muted">{art["description"]}</p>{art["html"]}
{_sources_html(art)}{_related_html(art)}<hr style="border:0;border-top:1px solid var(--line);margin:2.5rem 0"><p class="muted">Try it: <a href="/#signup">free for 3 agents</a> · Docs: <a href="/docs/claude-code">Claude Code</a> · <a href="/docs/cron">cron</a></p></div></main>'''
    ld = [ORG_LD, {"@context": "https://schema.org", "@type": "Article", "headline": art["title"], "description": art["description"], "datePublished": art.get("date") or BLOG_DATE, "dateModified": art.get("date") or BLOG_DATE,
                   "author": {"@type": "Organization", "name": "RunVouch", "url": BASE}, "publisher": {"@type": "Organization", "name": "RunVouch", "logo": {"@type": "ImageObject", "url": BASE + "/logo.svg"}},
                   "mainEntityOfPage": f"{BASE}/blog/{art['slug']}", "image": BASE + "/og.png"}]
    t = art["title"] if len(art["title"]) <= 62 else art["title"][:59].rsplit(" ", 1)[0] + "…"
    page(f"/blog/{art['slug']}", t, art["description"], body, ld, article=True)
idx = "".join(f'<a class="card" href="/blog/{a["slug"]}"><h3>{a["title"]}</h3><p>{a["description"]}</p><p class="small muted" style="margin-top:.5rem">{a.get("date") or BLOG_DATE}</p></a>' for a in sorted(ARTICLES, key=lambda x: x.get("date") or BLOG_DATE, reverse=True))
page("/blog/", "RunVouch field notes: unattended agents in practice", "Incident write-ups and guides on scheduled AI agents that fail silently or run up bills, and the checks that catch them.", f'''<main><div class="wrap doc"><h1>Field notes</h1><p class="lead muted">How unattended agents fail in practice, with sources, and the check that catches each one.</p><div class="grid g2">{idx}</div>
<h2 style="margin-top:2.5rem">Coming up</h2><ul class="muted"><li>Monitoring a headless claude -p job: hooks, exit codes, cost, alerts</li></ul></div></main>''', [ORG_LD])

# ───────────────────────── static assets & SEO files ─────────────────────────
(OUT / "assets").mkdir(parents=True, exist_ok=True)
import glob as _g
for old in _g.glob(str(OUT / "assets" / "style.*.css")): os.remove(old)
(OUT / "assets" / f"style.{CSS_HASH}.css").write_text(CSS.strip(), encoding="utf-8")
(OUT / "logo.svg").write_text(LOGO_SVG, encoding="utf-8")
try:
    from PIL import Image, ImageDraw
    # Zelfde beeld als LOGO_SVG (blauwe ring, donkere schijf, witte vink), 8x oversampled en dan verkleind voor gladde randen.
    S = 8
    im = Image.new("RGBA", (64 * S, 64 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((5 * S, 5 * S, 59 * S, 59 * S), fill="#4C8DFF")
    d.ellipse((9 * S, 9 * S, 55 * S, 55 * S), fill="#141B33")
    d.line([(19 * S, 34 * S), (28 * S, 43 * S), (45 * S, 24 * S)], fill="#EEF2FF", width=int(6.5 * S), joint="curve")
    for x, y in ((19, 34), (28, 43), (45, 24)):
        r = 6.5 * S / 2; d.ellipse((x * S - r, y * S - r, x * S + r, y * S + r), fill="#EEF2FF")
    im = im.resize((64, 64), Image.LANCZOS)
    im.save(OUT / "favicon.png")
except Exception as e:
    print("favicon png skipped", e)
(OUT / "google0eb34a6a1ec37a46.html").write_text("google-site-verification: google0eb34a6a1ec37a46.html\n")
(OUT / "BingSiteAuth.xml").write_text('<?xml version="1.0"?>\n<users>\n\t<user>230B54FA2CDEA9154CB1DF8F8609A6BB</user>\n</users>\n')
# logo-400.png is generated separately (site/public/logo-400.png, kept in git)
(OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nUser-agent: OAI-SearchBot\nAllow: /\nUser-agent: ChatGPT-User\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: Claude-SearchBot\nAllow: /\nUser-agent: Google-Extended\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
(OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{BASE}{p}</loc><lastmod>{TODAY}</lastmod></url>" for p in PAGES) + "</urlset>")
(OUT / "llms.txt").write_text(f"""# RunVouch

> RunVouch is the watchdog for unattended AI agents, with a tamper-evident proof per run: a dead man's switch, cost cap and outcome check for Claude Code Routines, headless `claude -p`, OpenClaw, n8n and cron'd LLM scripts. It alerts within minutes when a scheduled agent is MISSED, FAILED, reported success without evidence (NO_EVIDENCE), stuck in a RETRY_STORM, over BUDGET, DRIFTing, or STALLED. Alerts via e-mail, Telegram, Slack, Discord, Teams or webhook; PagerDuty on Team. History 7 days on Free, 90 days on Solo and Team. Free for 3 agents; $19 Solo, which adds a cost cap that refuses the next run; $99 Team. Self-hostable (MIT).

Install: `pip install runvouch` (or `curl -fsSL {BASE}/rv -o ~/bin/rv && chmod +x ~/bin/rv`) then `rv agent NAME --cadence 24h --evidence` and `rv run NAME --evidence-file OUT -- your-command`.
Claude Code plugin: `/plugin marketplace add runvouch/claude-plugin` → `/plugin install runvouch`.
Claude Desktop bundle: https://runvouch.com/runvouch.mcpb
Remote MCP (official registry, com.runvouch/runvouch): `claude mcp add --transport http runvouch https://api.runvouch.com/mcp --header "X-API-Key: rv_…"`.
API base: {API} (header X-API-Key).

## Docs
- [Claude Code]({BASE}/docs/claude-code): Routines, headless runs, hooks plugin, transcript cost
- [Cron & scripts]({BASE}/docs/cron): rv run for any job; GitHub Actions
- [Python & Node]({BASE}/docs/python-node): LangGraph, OpenAI Agents SDK, CrewAI callbacks
- [Agent templates]({BASE}/docs/templates): three copy-paste agents on official SEC and career-site data (DataSignals Lab), wrapped in rv run with evidence and cost caps
- [Verifiable agent runs]({BASE}/verifiable-agent-runs): who needs a tamper-evident record of what an AI agent did (finance, compliance, EU AI Act logging and record-keeping duties, audits), what is and is not in the record, and how to verify it without trusting RunVouch
- [Verifiable runs]({BASE}/docs/proof): every finished run gets a sha256 leaf, every UTC day a Merkle root chained to the previous day and stamped with OpenTimestamps (Bitcoin); public day files at {API}/proof/, offline verifier script
- [Alert channels]({BASE}/docs/alerts): e-mail, Telegram, Slack incoming webhook and JSON webhook on every plan; PagerDuty Events API v2 on Team (incident per agent and kind, resolved on ack); Solo and Team deliver MISSED and FAILED without the 10-minute cooldown
- [GitHub Actions]({BASE}/docs/github-actions) · [OpenClaw]({BASE}/docs/openclaw) · [n8n]({BASE}/docs/n8n) · [MCP server]({BASE}/docs/mcp) · [HTTP API]({BASE}/docs/api)

## Field notes (blog)
""" + "".join(f"- [{a['title']}]({BASE}/blog/{a['slug']}): {a['description']}\n" for a in ARTICLES) + f"""
## Integrations (one page per runtime: where the job runs, key as secret, snippet, what fails silently there)
""" + "".join(f"- [{i['name']}]({BASE}/integrations/{i['slug']}): {i['desc']}\n" for i in INTEGRATIONS) + f"""
## Compare
""" + "".join(f"- [vs {b}]({BASE}/vs/{a}): {c}\n" for a, b, c in VS_LIST) + f"""

## Other
- [RunVouch and the EU AI Act]({BASE}/eu-ai-act): which part of Article 12 and Article 26 a run record covers, and which part it does not
- [A live fleet]({BASE}/fleet/datasignals): 31 real scheduled agents with their state and success rate, read live from the public endpoint
- [Verify a run yourself]({BASE}/verify): one real sealed run, hashes recomputed in your browser, no account
- [Run it yourself]({BASE}/self-hosted): MIT, one server file and SQLite, five commands, and when Healthchecks.io is the better answer
- [Observability, a heartbeat, or a watchdog?]({BASE}/observability-or-watchdog): which of the three categories a given situation needs, including when the answer is one of the others
- [How often does an unattended job actually fail?]({BASE}/how-often-jobs-fail): measured over thousands of real runs, every alert broken out by kind, rebuilt weekly from the production database. Machine-readable and free to quote under CC BY 4.0: {BASE}/api/failure-rates.json
- [RunVouch in numbers]({BASE}/stats): real 30-day figures from our own fleet, rebuilt weekly
- [Pricing]({BASE}/pricing) · [Security]({BASE}/security) · [Privacy]({BASE}/privacy) · [Changelog]({BASE}/changelog)
""")
(OUT / ".well-known").mkdir(exist_ok=True)
(OUT / ".well-known" / "security.txt").write_text(f"Contact: https://runvouch.com/contact?topic=security\nExpires: {datetime.date.today().year+1}-12-31T00:00:00.000Z\nPreferred-Languages: en, nl\nCanonical: {BASE}/.well-known/security.txt\n")
_RFC_DAY = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_RFC_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _rfc822(d):
    """Datum als RFC 822, zoals RSS eist. Stond hier utcnow(), waardoor alle tien items
    de bouwtijd droegen en elke lezer dacht dat alles vandaag geplaatst was (gemeten 7 sep 2026).
    Namen uit een vaste tabel en niet uit strftime: %a en %b volgen LC_TIME van de bouwomgeving,
    en een RSS-lezer verwerpt een Nederlandse dagnaam."""
    dt = datetime.date.fromisoformat(d)
    return f"{_RFC_DAY[dt.weekday()]}, {dt.day:02d} {_RFC_MON[dt.month - 1]} {dt.year} 00:00:00 GMT"

_feed_rows = [(a.get("date") or BLOG_DATE,
               f"<item><title>{a['title']}</title><link>{BASE}/blog/{a['slug']}</link>"
               f"<guid isPermaLink=\"true\">{BASE}/blog/{a['slug']}</guid>"
               f"<description>{a['description']}</description>"
               f"<pubDate>{_rfc822(a.get('date') or BLOG_DATE)}</pubDate></item>")
              for a in ARTICLES]
_feed_rows.append((RELEASES[0][1],
                   f"<item><title>{RELEASES[0][0]}, latest release</title><link>{BASE}/changelog</link>"
                   f"<guid isPermaLink=\"false\">runvouch-release-{RELEASES[0][0]}</guid>"
                   f"<pubDate>{_rfc822(RELEASES[0][1])}</pubDate></item>"))
# Nieuwste eerst, met de releaseregel op zijn eigen datum in de rij; hij stond achteraan
# na oudere artikelen, waardoor de feed niet meer op datum aflopend was.
_items = "".join(row for _, row in sorted(_feed_rows, key=lambda x: x[0], reverse=True))
(OUT / "feed.xml").write_text(f'<?xml version="1.0"?><rss version="2.0"><channel><title>RunVouch changelog</title><link>{BASE}/changelog</link><description>What\'s new in RunVouch</description>' + _items + '</channel></rss>')
# rv client download
import shutil
shutil.copy(ROOT.parent / "runvouch" / "cli.py", OUT / "rv")
import zipfile as _z
with _z.ZipFile(OUT / "runvouch.mcpb", "w", _z.ZIP_DEFLATED) as zf:
    zf.write(ROOT.parent / "integrations" / "mcp" / "mcpb-manifest.json", "manifest.json"); zf.write(OUT / "favicon.png", "icon.png"); zf.write(ROOT.parent / "integrations" / "mcp" / "runvouch_mcp.py", "server/runvouch_mcp.py")
shutil.copy(ROOT.parent / "integrations" / "python" / "runvouch.py", OUT / "runvouch.py")
shutil.copy(ROOT.parent / "integrations" / "node" / "runvouch.js", OUT / "runvouch.js")
(OUT / "openclaw" / "runvouch").mkdir(parents=True, exist_ok=True)
shutil.copy(ROOT.parent / "integrations" / "openclaw" / "runvouch" / "SKILL.md", OUT / "openclaw" / "runvouch" / "SKILL.md")
(OUT / "openclaw" / "verified-run" / "scripts").mkdir(parents=True, exist_ok=True)
shutil.copy(ROOT.parent / "integrations" / "openclaw" / "verified-run" / "SKILL.md", OUT / "openclaw" / "verified-run" / "SKILL.md")
shutil.copy(ROOT.parent / "integrations" / "openclaw" / "verified-run" / "scripts" / "verified-run.sh", OUT / "openclaw" / "verified-run" / "scripts" / "verified-run.sh")
print(f"built {len(PAGES)} pages → {OUT}")

# ───────────────────────── 404 (served by the API for unknown paths; not in the sitemap) ─────────────────────────
(OUT / "404.html").write_text(head("Page not found | RunVouch", "That page does not exist. Try the docs, the dashboard or the home page.", "/404") + '''<main><div class="wrap doc" style="text-align:center;padding-top:5rem"><p class="small muted" style="font-family:'Geist Mono';letter-spacing:.12em">404</p><h1>Nothing runs here.</h1><p class="lead muted">The address does not exist, or it did and moved. These do:</p><p class="cta" style="justify-content:center"><a class="btn" href="/">Home</a><a class="btn ghost" href="/docs/">Docs</a><a class="btn ghost" href="/app">Dashboard</a><a class="btn ghost" href="/blog/">Blog</a></p></div></main>''' + FOOTER, encoding="utf-8")

# Schrijfregel: geen gedachtestreepjes in wat de klant ziet (leest als AI-tekst). Het enige
# toegestane streepje is het letterlijke citaat uit de Claude Code-documentatie.
_TOEGESTAAN = 'the routine ran — it does not mean'
for _f in OUT.rglob("*.html"):
    _t = _f.read_text(encoding="utf-8")
    if _t.replace(_TOEGESTAAN, "").count("—"):
        raise SystemExit(f"gedachtestreepje in {_f.relative_to(OUT)}; herschrijf de zin (komma, dubbele punt of punt)")
