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
BILLING_LIVE = POLAR_LIVE or STRIPE_LIVE or LS_LIVE
SOLO_BTN = f'<a class="btn" href="{SOLO_URL}" data-ls="{EMAIL_PARAM}">Upgrade to Solo, $9/mo</a>' if BILLING_LIVE else '<a class="btn" href="/contact?topic=billing">Start free; paid plans open Sept 2026</a>'
TEAM_BTN = f'<a class="btn ghost" href="{TEAM_URL}" data-ls="{EMAIL_PARAM}">Upgrade to Team, $29/mo</a>' if BILLING_LIVE else '<a class="btn ghost" href="/contact?topic=billing">Request Team plan</a>'
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
html,body{overflow-x:hidden;max-width:100%}.card,.g2>*,.g3>*,.g4>*,.price>*,.cols>*{min-width:0}.card pre{max-width:100%;white-space:pre-wrap;overflow-wrap:anywhere}.doc table{display:block;overflow-x:auto;max-width:100%}footer .cols>div{min-width:0}.ticker{display:flex;align-items:center;max-width:100vw}.tk-label{flex:none;margin:0 1rem 0 var(--pad,1.25rem);padding:.15rem .55rem;border:1px solid var(--line2);border-radius:999px;font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:var(--fg3)}.tk-wrap{flex:1;overflow:hidden;white-space:nowrap}
@media(max-width:900px){table{display:block;overflow-x:auto;max-width:100%}.hero-inner{grid-template-columns:1fr;gap:2rem}.hero{padding-top:5rem}.g3,.g4,.g2,.price{grid-template-columns:1fr}footer .cols{grid-template-columns:1fr 1fr;gap:1.5rem}footer .cols>div:first-child{grid-column:1/-1}.nav nav{display:none}.nav .btn{margin-left:auto}.tk-label{display:none}}
.roster-pad main>section:first-child{padding-top:5.6rem}
@media(prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none}.tk-track,.eyebrow i{animation:none}}
'''

SIGNUP_JS = '''
const API="__API__";
async function signup(e){e.preventDefault();const k=document.getElementById('keybox');k.classList.add('show');k.innerHTML='<pre>…</pre>';
try{const r=await fetch(API+'/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('em').value})});
const j=await r.json();if(!r.ok){k.innerHTML='<div class="alertbox">'+(j.detail||('Error '+r.status))+'</div>';return}
if(j.sent){k.innerHTML='<div class="alertbox">This address already has an account. We just e-mailed a fresh key to it (the old one stopped working). Check your inbox, then <a href="/app">open the dashboard</a>.</div>';return}
k.innerHTML='<pre><span class="d"># Your key, shown once. Store it now.</span>\\nexport RUNVOUCH_KEY=<span class="k">'+j.api_key+'</span>\\nexport RUNVOUCH_URL='+API+'\\n\\n<span class="d"># Install the client, register an agent, wrap your job</span>\\npip install runvouch   <span class="d"># or: curl -fsSL https://runvouch.com/rv -o ~/bin/rv</span>\\nrv agent nightly-report --cadence 24h --cap-run-cost 2 --evidence\\nrv run nightly-report --evidence-file out/report.html -- claude -p "build tonight\\'s report"</pre><p class="small muted">Free plan: 3 agents, no card. <a href="/app">Open the dashboard</a> and paste the key.</p>'}
catch(err){k.innerHTML='<div class="alertbox">Network error: '+err+'</div>'}return false}

(function(){const hero=document.querySelector('.hero');if(hero){const setH=()=>document.documentElement.style.setProperty('--bandh',(hero.offsetTop+hero.offsetHeight)+'px');setH();addEventListener('resize',setH)}else{document.documentElement.style.setProperty('--bandh','360px')}
document.querySelectorAll('main section > .wrap > h2, main section .card, main .doc h2, main .doc table, main .doc pre, main .doc .card, main .price .card').forEach(el=>el.classList.add('reveal'));const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.12});setTimeout(()=>document.querySelectorAll('.reveal').forEach(el=>el.classList.add('in')),1800);document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
const c=document.getElementById('sig');if(!c||matchMedia('(prefers-reduced-motion: reduce)').matches)return;const x=c.getContext('2d');let W,H,D=devicePixelRatio,lanes=[],P=[],t=0;
if(c.dataset.mode==='roster'){/* day roster: rows are agents, columns are the 24 hours of one day; fills like a clock, holds, then a new day. green vouched, amber missed or unproven, red failed */
let S=[],cols=24,rows=3,pw=0,ph=0,gx=0,gy=0,x0=0,y0=0,tick=0,maxAt=0;
const COL={ok:'#3DDC84',warn:'#F5B547',fail:'#FF6B6B'},POOL=['nightly-report','inbox-triage','price-scraper','lead-enricher','repo-janitor','13f-digest','hiring-watch','invoice-sync','changelog-bot','backup-check','ticket-triage','form-d-raises'];let NAMES=POOL.slice(0,3);
function RR(){W=c.width=c.offsetWidth*D;H=c.height=c.offsetHeight*D;const narrow=c.offsetWidth<700;rows=narrow?2:3;x0=(narrow?12:110)*D;const avail=W-x0-16*D;gx=Math.max(3*D,avail*0.012);pw=(avail-gx*(cols-1))/cols;ph=7*D;gy=20*D;y0=(narrow?84:92)*D;S=[];maxAt=0;
NAMES=POOL.slice().sort(()=>Math.random()-0.5).slice(0,3);for(let r=0;r<rows;r++)for(let i=0;i<cols;i++){const u=Math.random();const at=i*9+r*2;maxAt=Math.max(maxAt,at);S.push({r,i,kind:u<0.86?'ok':u<0.95?'warn':'fail',at})}tick=0}
RR();addEventListener('resize',RR);
function drawR(){tick++;x.clearRect(0,0,W,H);x.font=`${10*D}px Geist Mono, monospace`;x.textAlign='left';
if(c.offsetWidth>=700){x.fillStyle='rgba(169,180,214,.5)';NAMES.slice(0,rows).forEach((l,r)=>x.fillText(l,x0-100*D,y0+r*gy+ph))}
x.fillStyle='rgba(169,180,214,.38)';[0,6,12,18,24].forEach(h=>{const px=x0+Math.min(h,cols-1)*(pw+gx)+(h===24?pw:0);x.textAlign=h===24?'right':'left';x.fillText((h<10?'0'+h:h)+':00',px,y0-9*D)});
for(const s of S){const px=x0+s.i*(pw+gx),py=y0+s.r*gy;x.fillStyle='rgba(169,180,214,.09)';x.fillRect(px,py,pw,ph);
if(tick>s.at){const k=Math.min(1,(tick-s.at)/10);x.globalAlpha=0.62*k;x.shadowColor=COL[s.kind];x.shadowBlur=(s.kind==='ok'?0:10)*D;x.fillStyle=COL[s.kind];x.fillRect(px,py,pw*k,ph);x.shadowBlur=0;x.globalAlpha=1}}
const sweep=Math.min(tick,maxAt)/9;const sx=x0+Math.min(sweep,cols)*(pw+gx);if(tick<=maxAt+10){x.fillStyle='rgba(238,242,255,.35)';x.fillRect(sx,y0-4*D,1*D,rows*gy)}
x.textAlign='right';x.fillStyle='rgba(169,180,214,.42)';x.fillText(c.offsetWidth<700?'every hour, every agent, checked':'one day, three agents, every hour checked',W-16*D,y0+rows*gy+4*D);
if(tick>maxAt+10+300){RR()}requestAnimationFrame(drawR)}
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
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0B1020">
<title>{title}</title><meta name="description" content="{desc}"><link rel="canonical" href="{BASE}{path}">
<meta property="og:type" content="{'article' if article else 'website'}"><meta property="og:site_name" content="RunVouch"><meta property="og:title" content="{title}"><meta property="og:description" content="{desc}"><meta property="og:url" content="{BASE}{path}"><meta property="og:image" content="{BASE}/og.png"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/logo.svg?v={CSS_HASH}" type="image/svg+xml"><link rel="icon" href="/favicon.png?v={CSS_HASH}" type="image/png" sizes="64x64"><link rel="apple-touch-icon" href="/favicon.png?v={CSS_HASH}"><link rel="alternate" type="application/rss+xml" title="RunVouch changelog" href="/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@500;600;700&family=Figtree:wght@400;500;600&family=Geist+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.{CSS_HASH}.css"><noscript><style>.reveal{{opacity:1;transform:none}}</style></noscript>{('<script type="application/ld+json">'+ld+'</script>') if ld else ''}{ANALYTICS}</head><body{(' class="roster-pad"' if path != '/' else '')}>
<div class="ambient" aria-hidden="true"><span class="blob b1"></span><canvas id="sig" class="sig" data-mode="roster"></canvas></div>
<header class="top"><div class="wrap nav"><a class="brand" href="/">{LOGO_SVG}RunVouch</a><nav><a href="/#how">How it works</a><a href="/docs/">Docs</a><a href="/vs/">Compare</a><a href="/pricing">Pricing</a><a href="/blog/">Blog</a><a href="https://github.com/runvouch">GitHub</a></nav><a class="btn" href="/#start">Get a free key</a></div></header>'''


PH_BADGE = '<p style="margin:.8rem 0"><a class="ph-badge" href="https://www.producthunt.com/products/runvouch?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-runvouch" target="_blank" rel="noopener noreferrer"><img alt="RunVouch - Dead man\'s switch + cost cap for unattended AI agents | Product Hunt" width="250" height="54" loading="lazy" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1232338&amp;theme=dark&amp;t=1787690858298"></a></p>' if datetime.date.today() >= datetime.date(2026, 9, 1) else ''
FOOTER = f'''<footer><div class="wrap"><div class="cols"><div><div class="brand" style="display:flex;align-items:center;gap:.5rem;font-family:"Instrument Sans";font-weight:700;color:var(--fg)">{LOGO_SVG.replace('width="64" height="64"','width="24" height="24"')}RunVouch</div>
<p class="small" style="margin-top:.6rem">The watchdog for unattended AI agents: proof they did the job, and an alert the moment they don't, or start spending. (For the ops crowd: a dead man's switch, cost cap and outcome check.)</p>
{PH_BADGE}
<ul class="avail" aria-label="Available on"><li><a href="https://pypi.org/project/runvouch/">PyPI</a></li><li><a href="https://www.npmjs.com/package/runvouch">npm</a></li><li><a href="https://github.com/runvouch/vouch-action">GitHub Action</a></li><li><a href="https://github.com/runvouch/claude-plugin">Claude Code plugin</a></li><li><a href="https://registry.modelcontextprotocol.io/?search=runvouch">MCP Registry</a></li><li><a href="https://smithery.ai/servers/runvouch/runvouch">Smithery</a></li><li><a href="https://glama.ai/mcp/servers/runvouch/runvouch">Glama</a></li></ul>
<p class="small muted">© {datetime.date.today().year} RunVouch · Netherlands · <a href="/contact">contact</a><br>Built by the team behind <a href="https://datasignalslab.com" rel="noopener">DataSignals Lab</a>, whose nightly pipelines it watches.</p></div>
<div><h4>Product</h4><a href="/#how">How it works</a><a href="/verifiable-agent-runs">Verifiable agent runs</a><a href="/pricing">Pricing</a><a href="/blog/">Blog</a><a href="/app">Dashboard</a><a href="/changelog">Changelog</a><a href="/status">Status</a></div>
<div><h4>Docs</h4><a href="/docs/claude-code">Claude Code</a><a href="/docs/cron">Cron &amp; scripts</a><a href="/docs/python-node">Python &amp; Node</a><a href="/docs/github-actions">GitHub Actions</a><a href="/docs/openclaw">OpenClaw</a><a href="/docs/n8n">n8n</a><a href="/docs/templates">Agent templates</a><a href="/docs/proof">Verifiable runs</a><a href="/docs/alerts">Alert channels</a><a href="/docs/mcp">MCP server</a><a href="/docs/api">API</a></div>
<div><h4>Compare</h4><a href="/vs/healthchecks">vs Healthchecks.io</a><a href="/vs/cronitor">vs Cronitor</a><a href="/vs/langfuse">vs Langfuse</a><a href="/security">Security</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a></div></div></div></footer>
<script>{SIGNUP_JS}</script></body></html>'''


ORG_LD = {"@context": "https://schema.org", "@type": "Organization", "name": "RunVouch", "url": BASE, "logo": BASE + "/logo.svg", "contactPoint": {"@type": "ContactPoint", "url": "https://runvouch.com/contact", "contactType": "customer support"}}
APP_LD = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "RunVouch", "url": BASE, "applicationCategory": "DeveloperApplication", "operatingSystem": "Any",
          "description": "RunVouch is the watchdog for unattended AI agents: a dead man's switch, cost cap and outcome check (Claude Code Routines, headless claude -p, OpenClaw, n8n, cron). It alerts within minutes when a scheduled agent is missing, failed, looping, over budget, drifting, or reported success without evidence. Every finished run gets a tamper-evident proof: a hashed record, a public daily Merkle chain and a Bitcoin anchor via OpenTimestamps.",
          "offers": [{"@type": "Offer", "price": "0", "priceCurrency": "USD", "name": "Free"}, {"@type": "Offer", "price": "9", "priceCurrency": "USD", "name": "Solo"}, {"@type": "Offer", "price": "29", "priceCurrency": "USD", "name": "Team"}]}

CSS_HASH = hashlib.sha1(CSS.encode()).hexdigest()[:8]
PAGES: dict[str, tuple[str, str, str]] = {}  # path -> (title, desc, body)


def _colour_tables(body):
    """Comparison tables: only the RunVouch column (last cell of a row) gets colour, green for yes, muted for no.
    Competitor cells stay neutral: honest, but the eye lands on our column."""
    def row(m):
        cells = re.findall(r'<td[^>]*>.*?</td>', m.group(0), re.S)
        if len(cells) < 3:
            return m.group(0)
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
<div class="trust reveal"><span>no card</span><span>2-minute setup</span><span>email, Telegram, Slack or webhook</span><span>self-host (MIT)</span></div>
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
<div class="card"><h3>Get told, not surprised</h3><p>Missed, failed, unproven, looping, over budget, drifting or stalled → Telegram, Slack or any webhook within minutes. Ask your MCP client "are my agents healthy?"</p><pre>rv status
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
<p class="small muted">Who needs this and how to verify without trusting us: <a href="/verifiable-agent-runs">verifiable agent runs</a> · the mechanism, byte for byte: <a href="/docs/proof">docs/proof</a></p>
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
<div class="card"><h3><span class="tag">DRIFT</span></h3><p>Duration or output size off its 7-run baseline. The agent is quietly doing something else.</p></div>
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
<tr><td>Hard cost cap per run / per day</td><td class="n">no</td><td class="n">dashboards, no cap</td><td class="y">yes + pause</td></tr>
<tr><td>Setup</td><td>1 URL</td><td>SDK in your code</td><td>2 lines or a plugin</td></tr>
<tr><td>Built for</td><td>ops teams, cron</td><td>ML teams debugging prompts</td><td>people running agents unattended</td></tr>
<tr><td>Price</td><td>$0–85/mo</td><td>per seat / per million spans</td><td>$0 · $9 · $29</td></tr></table>
<p class="small muted" style="margin-top:.8rem">Detailed comparisons: <a href="/vs/healthchecks">Healthchecks.io</a> · <a href="/vs/cronitor">Cronitor</a> · <a href="/vs/langfuse">Langfuse</a></p>
</div></section>

<section id="start"><div class="wrap">
<span class="kicker">pricing</span><h2>Free until you outgrow it. <span class="grad">Then $9.</span></h2>
<div class="price">
<div class="card"><h3>Free</h3><div class="n">$0</div><ul><li>3 agents</li><li>All 8 detectors</li><li>Email, Telegram, Slack &amp; webhook alerts</li><li>7-day history</li><li>Verifiable proof per run</li></ul><a class="btn ghost" href="#signup">Start free</a></div>
<div class="card hi"><h3>Solo</h3><div class="n">$9<small>/month</small></div><ul><li>15 agents</li><li>90-day history</li><li>Weekly cost report</li><li>MISSED and FAILED alerts sent every time, no 10-minute cooldown</li><li>Verifiable proof per run</li></ul>{SOLO_BTN}</div>
<div class="card"><h3>Team</h3><div class="n">$29<small>/month</small></div><ul><li>100 agents</li><li>90-day history</li><li>API export (CSV / JSON) for audits</li><li>Read-only dashboard for teammates (viewer keys)</li><li>PagerDuty incidents</li><li>Verifiable proof per run</li></ul>{TEAM_BTN}</div>
</div>
<div id="signup" style="margin-top:2rem"><h3>Get your key</h3><p class="muted">Only used to identify your account and match a future subscription. No newsletter, no card. Prices in USD, VAT handled at checkout by {PROCESSOR}; upgrade with the same email you sign up with.</p>
<form class="signup" onsubmit="return signup(event)"><input id="em" type="email" required placeholder="you@company.com" autocomplete="email"><button class="btn" type="submit">Get a free key</button></form>
<div id="keybox" class="keybox"></div></div>
</div></section>

<section class="alt faq"><div class="wrap"><span class="kicker">faq</span><h2>Questions</h2>
<details><summary>Why do you need my email for a free key?</summary><p>Because the key is the account. If you upgrade later, the payment is matched to the same email; if you lose the key, we can rotate it. We don't send marketing mail.</p></details>
<details><summary>Why 3 agents on the free plan?</summary><p>Most solo builders run one to three scheduled agents. Free covers that completely, forever. Paid plans are for people who run more, that's the only difference besides history and reports.</p></details>
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
<p class="cta"><a class="btn" href="/#signup">Get a free key</a><a class="btn ghost" href="/docs/proof">Read the mechanism</a></p>

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
              "offers": [{"@type": "Offer", "name": "Free", "price": "0", "priceCurrency": "USD", "description": "3 agents, all 8 detectors, e-mail, Telegram, Slack and webhook alerts, 7-day history, verifiable proof per run"},
                         {"@type": "Offer", "name": "Solo", "price": "9", "priceCurrency": "USD", "description": "15 agents, 90-day history, weekly cost report, priority alerts, verifiable proof per run", "priceSpecification": {"@type": "UnitPriceSpecification", "price": "9", "priceCurrency": "USD", "billingDuration": "P1M"}},
                         {"@type": "Offer", "name": "Team", "price": "29", "priceCurrency": "USD", "description": "100 agents, 90-day history, PagerDuty incidents, shared dashboard, API export, verifiable proof per run", "priceSpecification": {"@type": "UnitPriceSpecification", "price": "29", "priceCurrency": "USD", "billingDuration": "P1M"}}]}
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
page("/pricing", "RunVouch pricing: free for 3 agents, $9 Solo, $29 Team", "Simple pricing for agent monitoring: free for 3 agents with all detectors; Solo $9/month for 15 agents; Team $29/month for 100 agents, PagerDuty, shared dashboard and API export.",
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
<p>What gets reported: <b>SessionStart</b> → run start · <b>PostToolUse</b> → tool name + input hash + error flag (retry-storm and budget checks run on every call) · <b>Stop</b> → run end with tokens and cost summed from the transcript, plus your evidence.</p>'''),
     ("Evidence: prove the task happened", '''<p>Evidence turns "exit 0" into "done". Three forms:</p><ul><li><b>URL</b>: <code>{"type":"url","url":"…","expect":200}</code>, checked by RunVouch after the run.</li><li><b>File</b>: with <code>rv run --evidence-file PATH</code>: the file must exist, be non-empty and have changed during the run. Checked on your machine; only true/false is sent.</li><li><b>Boolean</b>: your own assertion: <code>{"rows_inserted": true}</code>.</li></ul><p>If <code>--evidence</code> is set on the agent and a run ends "ok" without passing evidence, you get a <code>NO_EVIDENCE</code> alert.</p>'''),
     ("Cost caps and retry storms", '''<p><code>--cap-run-cost 2</code> and <code>--cap-day-cost 10</code> alert the moment a run or a day crosses the line; combine with <code>rv agent … --pause</code> in your alert webhook to stop the schedule. Retry storms fire when the same tool is called with an identical input hash 8+ times in one run (configurable). Cost is computed from transcript usage with current Anthropic list prices; override with <code>RUNVOUCH_COST</code> / <code>RUNVOUCH_TOKENS</code> if you meter elsewhere.</p>'''),
     ("Ask your agents about each other (MCP)", '''<pre>claude mcp add runvouch -e RUNVOUCH_KEY=rv_… -- python3 runvouch_mcp.py</pre><p>Tools: <code>runvouch_status</code>, <code>runvouch_alerts</code>, <code>runvouch_ack</code>, <code>runvouch_runs</code>, <code>runvouch_run_start</code>, <code>runvouch_run_end</code>. A morning agent can refuse to build on last night's output if last night is <code>UNPROVEN</code>. See <a href="/docs/mcp">MCP docs</a>.</p>''')],
    [("Install the plugin", "Add the RunVouch marketplace and install the plugin."), ("Register an agent", "rv agent NAME --cadence 24h --cap-run-cost 2 --evidence"), ("Set environment in the Routine", "RUNVOUCH_KEY, RUNVOUCH_AGENT, optional RUNVOUCH_EVIDENCE"), ("Run", "claude -p …, hooks report start, tool calls, cost and outcome.")])

doc("/docs/cron", "Monitor cron jobs, scripts and LLM batch jobs | RunVouch docs",
    "Wrap any cron job or script with rv run to get missed-run, failure, evidence, drift and cost alerts. Zero dependencies, fails open.",
    "Cron, systemd, GitHub Actions and plain scripts",
    "The <code>rv</code> client is a single Python file with no dependencies. It wraps a command, captures exit code, duration and output size, checks evidence files, and reports, and if RunVouch is unreachable your job still runs.",
    [("Install", '<pre>pip install runvouch   <span class="d"># or: curl -fsSL https://runvouch.com/rv -o ~/bin/rv</span>\nexport RUNVOUCH_KEY=rv_…   <span class="d"># put in ~/.profile or the cron env</span></pre>'),
     ("Wrap a job", '''<pre><span class="d"># crontab -e</span>
0 2 * * * rv run nightly-etl --log /var/log/etl.log --evidence-file /data/out/today.parquet -- python3 etl.py</pre><p><code>--log</code> appends the job's stdout/stderr to a file (and counts as evidence if it grew). <code>--evidence-file</code> requires the file to exist, be non-empty and be modified during the run.</p>'''),
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
     ("Per-task runs via the HTTP API", '<pre>curl -X POST https://api.runvouch.com/v1/runs/start -H "X-API-Key: $RUNVOUCH_KEY" -d \'{"agent":"openclaw-inbox","source":"openclaw"}\'\n<span class="d"># … tool events … then</span>\ncurl -X POST https://api.runvouch.com/v1/runs/end -H "X-API-Key: $RUNVOUCH_KEY" -d \'{"run_id":"…","status":"ok","cost":0.21,"evidence":{"replied":true}}\'</pre><p>Or install the <b>RunVouch skill</b>: copy <a href="/openclaw/runvouch/SKILL.md">SKILL.md</a> into your OpenClaw skills directory (<code>~/.openclaw/skills/runvouch/</code>). It teaches the agent to check in at start, per tool call and at the end, with evidence.</p>')])

doc("/docs/n8n", "Monitor n8n AI workflows | RunVouch docs", "Catch n8n workflow failures your Error Workflow never sees, and track LLM cost per workflow run, with RunVouch.",
    "n8n", "Error Workflows only fire when a node errors. A workflow that runs, does nothing, and exits green is invisible. RunVouch adds expected-cadence, evidence and cost per run.",
    [("Two HTTP Request nodes", '<p>At the start: <code>POST {API}/v1/runs/start</code> with header <code>X-API-Key</code> and body <code>{{"agent":"lead-enricher","source":"n8n"}}</code>; save <code>run_id</code>. At the end: <code>POST {API}/v1/runs/end</code> with status, cost (from your OpenAI/Anthropic node usage) and evidence such as <code>{{"rows_written": true}}</code>.</p>'.replace("{API}", API)),
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

doc("/docs/alerts", "Alert channels: e-mail, Telegram, Slack, webhook, PagerDuty - RunVouch docs",
    "Where RunVouch alerts go and how to set each channel with one PUT /v1/settings call: e-mail, Telegram, Slack incoming webhook, JSON webhook, PagerDuty Events API v2.",
    "Alert channels",
    'Every alert (MISSED, FAILED, NO_EVIDENCE, BUDGET_RUN, BUDGET_DAY, RETRY_STORM, DRIFT, STALLED) goes to every channel you configure. Settings are one call; fields you leave out keep their value. Check the result with <code>POST /v1/settings/test-alert</code>, which sends a TEST alert to every configured channel. All of this is also on the <a href="/app">dashboard</a>.',
    [("E-mail (every plan)", f'''<pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"alert_email": "ops@company.com"}}'</pre><p>Subject <code>[RunVouch] KIND: agent</code>, the message in the body, a link to the dashboard. Signing up sets this to your signup address.</p>'''),
     ("Telegram (every plan)", f'''<p>Create a bot with @BotFather, start a chat with it (or add it to a group), and read the chat id from <code>https://api.telegram.org/bot&lt;token&gt;/getUpdates</code>.</p><pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"telegram_token": "123456:ABC...", "telegram_chat": "-100123456"}}'</pre>'''),
     ("Slack (every plan)", f'''<p>In Slack: Apps, Incoming Webhooks, add to a channel, copy the URL. It starts with <code>https://hooks.slack.com/services/</code>; other URLs are rejected with 422.</p><pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"slack_webhook_url": "https://hooks.slack.com/services/T000/B000/XXXX"}}'</pre><p>The message has a plain-text fallback plus blocks: a header with kind and agent, two fields (kind, agent), the message, and a link to the dashboard. The weekly cost report goes to the same channel.</p>'''),
     ("Generic webhook (every plan)", f'''<pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"webhook_url": "https://example.com/hooks/runvouch"}}'</pre><p>One JSON POST per alert:</p><pre>{{"kind":"RETRY_STORM","agent":"repo-janitor","run_id":"9808c5af...","message":"tool 'Bash' called 41x with identical input in one run.","ts":1787673506.3}}</pre><p>The weekly report arrives as <code>{{"kind":"WEEKLY_REPORT", ...}}</code>. Discord, Mattermost and n8n take this as is.</p>'''),
     ("PagerDuty (Team)", f'''<p>In PagerDuty: Services, your service, Integrations, add "Events API v2", copy the 32-character integration key.</p><pre>curl -X PUT {API}/v1/settings -H "X-API-Key: $RUNVOUCH_KEY" -H "Content-Type: application/json" \\
  -d '{{"pagerduty_routing_key": "R0123456789ABCDEF0123456789ABCDEF"}}'</pre><p>On Free and Solo this call returns 402 with a plain message. Behaviour:</p><ul><li>MISSED, FAILED, STALLED, BUDGET_RUN and BUDGET_DAY trigger an incident (severity error) with <code>dedup_key = runvouch:AGENT:KIND</code>, so a repeat of the same problem lands on the same incident.</li><li>NO_EVIDENCE, RETRY_STORM and DRIFT do not page; they still reach your other channels.</li><li>Acknowledging the alert in RunVouch (<code>POST /v1/alerts/{{id}}/ack</code>, the dashboard, or the MCP tool) sends a resolve for that dedup key.</li><li>The test alert opens an incident with severity info; ack it in RunVouch to resolve it.</li></ul>'''),
     ("Priority alerts (Solo and Team)", '''<p>Alerts of the same kind for the same agent are sent at most once per 10 minutes; repeats within that window are stored and shown in the dashboard with <code>delivered = -1</code>, but not re-sent. On Solo and Team, MISSED and FAILED skip that cooldown and are delivered immediately, every time. All other kinds keep the cooldown on every plan.</p>'''),
     ("Test and status", f'''<pre>curl -X POST {API}/v1/settings/test-alert -H "X-API-Key: $RUNVOUCH_KEY"
curl {API}/v1/me -H "X-API-Key: $RUNVOUCH_KEY"   <span class="d"># "channels": which ones are set</span></pre>''')],
    [("Pick a channel", "E-mail, Telegram, Slack or a webhook on every plan; PagerDuty on Team."), ("Set it", "PUT /v1/settings with the field for that channel, or fill it in on the dashboard."), ("Test it", "POST /v1/settings/test-alert and watch the channel.")])

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
<div class="grid g2"><a class="card" href="/docs/claude-code"><h3>Claude Code</h3><p>Routines, headless claude -p, hooks plugin, transcript cost.</p></a><a class="card" href="/docs/cron"><h3>Cron &amp; scripts</h3><p>rv run for anything: Python, Node, bash, GitHub Actions.</p></a><a class="card" href="/docs/github-actions"><h3>GitHub Actions</h3><p>One step: MISSED when the schedule stops, NO_EVIDENCE when it fakes it.</p></a><a class="card" href="/docs/openclaw"><h3>OpenClaw</h3><p>Heartbeats, per-task runs, daily caps.</p></a><a class="card" href="/docs/n8n"><h3>n8n</h3><p>Two HTTP nodes; catch the failures Error Workflows miss.</p></a><a class="card" href="/docs/python-node"><h3>Python &amp; Node</h3><p>LangGraph, OpenAI Agents SDK, CrewAI, any script.</p></a><a class="card" href="/docs/templates"><h3>Agent templates</h3><p>Nightly 13F digest, Form D raises, hiring watch: copy, set keys, monitored.</p></a><a class="card" href="/docs/proof"><h3>Verifiable runs</h3><p>Hash per run, Merkle root per day, anchored in Bitcoin. Verify offline. Need to show an auditor? Start at <span style="color:var(--acc2)">/verifiable-agent-runs</span>.</p></a><a class="card" href="/docs/alerts"><h3>Alert channels</h3><p>E-mail, Telegram, Slack, webhook, PagerDuty: one settings call each.</p></a><a class="card" href="/docs/mcp"><h3>MCP server</h3><p>Agents that check on agents.</p></a><a class="card" href="/docs/api"><h3>HTTP API</h3><p>Everything the CLI does, over REST.</p></a></div></div></main>''', [ORG_LD])


# ───────────────────────── VS PAGES ─────────────────────────
def vs(slug, name, tagline, rows, verdict):
    body = f'''<main><div class="wrap doc"><p class="small muted"><a href="/vs/">Compare</a> › {name}</p><h1>RunVouch vs {name}</h1><p class="lead muted">{tagline}</p>
<table><tr><th></th><th>{name}</th><th>RunVouch</th></tr>{"".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a,b,c in rows)}</table>
<h2>When to use which</h2>{verdict}<p><a class="btn" href="/#signup">Get a free key</a></p></div></main>'''
    page(f"/vs/{slug}", f"RunVouch vs {name}: for AI agents, cron and scheduled jobs", f"Honest comparison of RunVouch and {name} for monitoring scheduled AI agents: missed runs, evidence, retry storms, cost caps, pricing.", body, [ORG_LD], article=True)


vs("healthchecks", "Healthchecks.io", "Healthchecks.io is the reference dead man's switch for cron jobs. RunVouch starts where a ping ends: did the job do the work, and what did it cost?",
   [("Missed / late run alerts", "yes", "yes"), ("Failure with stderr excerpt", "via /fail ping", "yes, automatic with rv run"), ("Evidence the task was actually done", "no", "yes, file / URL / assertion"), ("Retry-storm (loop) detection", "no", "yes"), ("Cost and token caps", "no", "yes, per run and per day"), ("Output/duration drift", "no", "yes"), ("Claude Code plugin / MCP server", "no", "yes"), ("Self-host", "yes (BSD)", "yes (MIT)"), ("Price", "free 20 checks; $17–85/mo", "free 3 agents; $9 / $29")],
   "<p>Use Healthchecks.io for classic cron jobs where \"it ran\" is enough. Use RunVouch when the job is an agent or an LLM script: a green ping tells you nothing about whether the report was written or whether the agent spent $60 looping on a missing file. Many teams run both.</p>")
vs("cronitor", "Cronitor", "Cronitor is a mature cron, heartbeat and uptime monitor for ops teams. RunVouch is narrower and deeper: outcome, cost and loop detection for unattended AI agents.",
   [("Cron expression parsing", "yes", "cadence + grace"), ("Uptime / status pages", "yes", "no (we link to yours)"), ("Evidence the task was done", "no", "yes"), ("Retry-storm detection", "no", "yes"), ("Cost caps", "no", "yes"), ("Claude Code / MCP / OpenClaw integrations", "no", "yes"), ("Price", "free tier; paid from ~$5 per monitor tier", "free 3 agents; $9 / $29")],
   "<p>Pick Cronitor if you need status pages and hundreds of classic monitors. Pick RunVouch if what you run is agents and you care about \"done\" and \"how much\", not just \"on time\".</p>")
vs("langfuse", "Langfuse", "Langfuse is excellent open-source LLM observability: traces, evals, prompt management. RunVouch is not a tracing tool; it's the watchdog that tells you a scheduled agent is broken or expensive, without instrumenting your code.",
   [("Traces, spans, prompt versions, evals", "yes", "no"), ("Requires SDK in your code", "yes", "no, wrap the command or install the plugin"), ("Missed-run / dead man's switch", "no", "yes"), ("Evidence the task was done", "no", "yes"), ("Retry-storm alert", "you can find it in traces", "automatic"), ("Hard cost cap + pause", "dashboards", "yes"), ("Pricing", "free self-host; cloud per unit", "free 3 agents; $9 / $29")],
   "<p>They're complementary. Langfuse answers \"why did this prompt produce that\"; RunVouch answers \"did last night's agent run, finish, prove it, and stay under budget\". If you only want the second, you don't need the first.</p>")
page("/vs/", "RunVouch compared", "How RunVouch compares to Healthchecks.io, Cronitor and Langfuse for monitoring scheduled AI agents.", '<main><div class="wrap doc"><h1>Compare</h1><div class="grid g3"><a class="card" href="/vs/healthchecks"><h3>vs Healthchecks.io</h3><p>Ping monitor vs outcome watchdog.</p></a><a class="card" href="/vs/cronitor"><h3>vs Cronitor</h3><p>Ops monitoring vs agent monitoring.</p></a><a class="card" href="/vs/langfuse"><h3>vs Langfuse</h3><p>Tracing vs watchdog, complementary.</p></a></div></div></main>', [ORG_LD])

# ───────────────────────── misc pages ─────────────────────────
page("/contact", "Contact | RunVouch", "Questions, bugs, security reports or partnership ideas, reach the RunVouch team.", '''<main><div class="wrap doc"><h1>Contact</h1><p class="lead muted">Support, billing, security or just an idea. Replies within one working day.</p>
<form id="cf" onsubmit="return sendContact(event)"><p><select id="ct" style="padding:.8rem;border-radius:10px;background:#040308;color:var(--fg);border:1px solid var(--line2);font:inherit"><option value="support">Support</option><option value="billing">Billing</option><option value="security">Security report</option><option value="partnership">Partnership / integration</option></select></p>
<p><input id="ce" type="email" required placeholder="you@company.com" style="width:100%;padding:.85rem 1rem;border:1px solid var(--line2);border-radius:12px;font:inherit;background:#040308;color:var(--fg)"></p>
<p><textarea id="cm" required minlength="5" rows="6" placeholder="What happened, what you expected, agent name if relevant…" style="width:100%;padding:.85rem 1rem;border:1px solid var(--line2);border-radius:12px;font:inherit;background:#040308;color:var(--fg)"></textarea></p>
<p><button class="btn" type="submit">Send</button> <span id="cs" class="muted small"></span></p></form>
<script>const tp=new URLSearchParams(location.search).get('topic');if(tp)document.getElementById('ct').value=tp;
async function sendContact(e){e.preventDefault();const s=document.getElementById('cs');s.textContent='Sending…';
try{const r=await fetch(API+'/contact',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('ce').value,message:document.getElementById('cm').value,topic:document.getElementById('ct').value})});
s.textContent=r.ok?'Sent. We reply by email within one working day.':'Could not send ('+r.status+'). Try again later.';if(r.ok)document.getElementById('cf').reset()}catch(err){s.textContent='Network error.'}return false}</script></div></main>''', [ORG_LD])
page("/status", "Status | RunVouch", "Live status of the RunVouch API, dashboard and alert delivery, checked from your browser against the production API.", '''<main><div class="wrap doc"><h1>Status</h1><p class="lead muted">Checked live from your browser against the API.</p><table><tr><th>Component</th><th>Status</th></tr><tr><td>API (api.runvouch.com)</td><td id="s-api">checking…</td></tr><tr><td>Dashboard</td><td id="s-app">checking…</td></tr><tr><td>Alert delivery (Telegram / e-mail / webhook)</td><td id="s-alerts">checking…</td></tr></table><p class="small muted" style="margin-top:1rem">Incidents are posted here and in the <a href="/changelog">changelog</a>.</p>
<script>fetch(API+'/health').then(async r=>{document.getElementById('s-api').innerHTML=r.ok?'<span class="pill ok">operational</span>':'<span class="pill bad">degraded</span>';try{const j=await r.json();const a=(j.checks||{}).alert_delivery;document.getElementById('s-alerts').innerHTML=a==='ok'?'<span class="pill ok">operational</span>':a==='idle'?'<span class="pill ok">idle (no alerts due)</span>':'<span class="pill bad">'+(a||'unknown')+'</span>'}catch(e){document.getElementById('s-alerts').textContent='unknown'}}).catch(()=>{document.getElementById('s-api').innerHTML='<span class="pill bad">unreachable</span>'});fetch('/app').then(r=>{document.getElementById('s-app').innerHTML=r.ok?'<span class="pill ok">operational</span>':'<span class="pill bad">degraded</span>'})</script></div></main>''', [ORG_LD])
page("/security", "Security | RunVouch", "What RunVouch stores, how keys are handled, and how to report a vulnerability.", '''<main><div class="wrap doc"><h1>Security</h1>
<ul><li>API keys are stored as SHA-256 hashes; the plaintext key is shown once.</li><li>Tool inputs are hashed on the client or server for loop detection; prompts and outputs are never stored.</li><li>Evidence file checks run on your machine; only a boolean is transmitted.</li><li>Every finished run gets a hash that is chained per day and anchored in Bitcoin via OpenTimestamps, so a record cannot be altered afterwards without it showing; see <a href="/docs/proof">verifiable runs</a>. An auditor can verify a run with a standalone script and <code>ots verify</code>, without trusting us: <a href="/verifiable-agent-runs">how</a>.</li><li>All traffic is TLS via Cloudflare; infrastructure in the EU (Netherlands).</li><li>Per-key rate limits; alert credentials (Telegram token, webhook URL) are stored per account and used only to deliver your alerts.</li><li>Report vulnerabilities via the <a href="/contact?topic=security">contact form</a> (topic: security), see <a href="/.well-known/security.txt">security.txt</a>.</li></ul></div></main>''', [ORG_LD])
page("/privacy", "Privacy | RunVouch", "RunVouch privacy policy: the run metadata and account data we process, what we never store (prompts, outputs), retention, and how to delete your data.", f'''<main><div class="wrap doc"><h1>Privacy</h1><p>RunVouch (Netherlands) processes: your email (account identity, billing match), agent names and run metadata you send (timestamps, status, cost, token counts, tool names, input hashes, output sizes, evidence verdicts), alert delivery settings, and standard server logs (IP, user agent) kept 30 days. Runs, tool events and acknowledged alerts are purged after the history window of your plan (7 days on Free, 90 days on Solo and Team); the per-run leaf hash stays in the public proof chain. We do not sell data, do not send marketing email, and do not use third-party analytics that track you across sites. Payments are processed by {PROCESSOR}; card details never touch our servers. Delete your account and data any time via <a href="/contact">contact</a>. GDPR requests: same form.</p></div></main>''', [ORG_LD])
page("/terms", "Terms | RunVouch", "RunVouch terms of service: early-access status, monthly plans that cancel any time, acceptable use, and liability limits in plain language.", '''<main><div class="wrap doc"><h1>Terms of service</h1><p>RunVouch is provided as-is during early access. Free plans may be rate-limited. Paid plans renew monthly and can be cancelled any time; the current period is not refunded. Don't use RunVouch to monitor anything illegal, and don't attack the service. We may change these terms with notice on this page. Governing law: the Netherlands.</p></div></main>''', [ORG_LD])
page("/changelog", "Changelog | RunVouch", "What's new in RunVouch: releases of the API, CLI, Claude Code plugin, MCP server and detectors, with dates.", f'''<main><div class="wrap doc"><h1>Changelog</h1><h3>{TODAY}: 0.2 (early access)</h3><ul><li>Public launch on runvouch.com and api.runvouch.com.</li><li>Eight detectors: MISSED, FAILED, NO_EVIDENCE, RETRY_STORM, BUDGET_RUN, BUDGET_DAY, DRIFT, STALLED.</li><li>Claude Code plugin with transcript-based cost; MCP server; zero-dependency <code>rv</code> CLI with fail-open.</li><li>Hashed keys, rate limits, self-serve signup, subscriptions via {PROCESSOR}.</li></ul></div></main>''', [ORG_LD])
# ───────────────────────── BLOG ─────────────────────────
ARTICLES = json.loads((ROOT / "articles.json").read_text(encoding="utf-8"))["articles"] if (ROOT / "articles.json").exists() else []
BLOG_DATE = "2026-08-25"
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
    body = f'''<main><div class="wrap doc"><p class="small muted"><a href="/blog/">Field notes</a> · {BLOG_DATE} · RunVouch</p><h1>{art["title"]}</h1><p class="lead muted">{art["description"]}</p>{art["html"]}
{_sources_html(art)}{_related_html(art)}<hr style="border:0;border-top:1px solid var(--line);margin:2.5rem 0"><p class="muted">Try it: <a href="/#signup">free for 3 agents</a> · Docs: <a href="/docs/claude-code">Claude Code</a> · <a href="/docs/cron">cron</a></p></div></main>'''
    ld = [ORG_LD, {"@context": "https://schema.org", "@type": "Article", "headline": art["title"], "description": art["description"], "datePublished": BLOG_DATE, "dateModified": BLOG_DATE,
                   "author": {"@type": "Organization", "name": "RunVouch", "url": BASE}, "publisher": {"@type": "Organization", "name": "RunVouch", "logo": {"@type": "ImageObject", "url": BASE + "/logo.svg"}},
                   "mainEntityOfPage": f"{BASE}/blog/{art['slug']}", "image": BASE + "/og.png"}]
    t = art["title"] if len(art["title"]) <= 62 else art["title"][:59].rsplit(" ", 1)[0] + "…"
    page(f"/blog/{art['slug']}", t, art["description"], body, ld, article=True)
idx = "".join(f'<a class="card" href="/blog/{a["slug"]}"><h3>{a["title"]}</h3><p>{a["description"]}</p><p class="small muted" style="margin-top:.5rem">{BLOG_DATE}</p></a>' for a in ARTICLES)
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
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    grad = Image.new("RGBA", (64, 64)); gd = ImageDraw.Draw(grad)
    for i in range(64):
        gd.line((i, 0, i, 64), fill=(int(255 - 131 * i / 64), int(61 + 16 * i / 64), int(129 + 126 * i / 64), 255))
    mask = Image.new("L", (64, 64), 0); md = ImageDraw.Draw(mask); md.ellipse((4, 6, 56, 58), fill=255); md.ellipse((24, 7, 58, 41), fill=0)
    im.paste(grad, (0, 0), mask); d = ImageDraw.Draw(im)
    d.line([(17, 36), (25, 44), (41, 26)], fill="white", width=6, joint="curve"); d.ellipse((47, 9, 53, 15), fill="white")
    im.save(OUT / "favicon.png")
except Exception as e:
    print("favicon png skipped", e)
(OUT / "google0eb34a6a1ec37a46.html").write_text("google-site-verification: google0eb34a6a1ec37a46.html\n")
(OUT / "BingSiteAuth.xml").write_text('<?xml version="1.0"?>\n<users>\n\t<user>230B54FA2CDEA9154CB1DF8F8609A6BB</user>\n</users>\n')
# logo-400.png is generated separately (site/public/logo-400.png, kept in git)
(OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nUser-agent: OAI-SearchBot\nAllow: /\nUser-agent: ChatGPT-User\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: Claude-SearchBot\nAllow: /\nUser-agent: Google-Extended\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
(OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{BASE}{p}</loc><lastmod>{TODAY}</lastmod></url>" for p in PAGES) + "</urlset>")
(OUT / "llms.txt").write_text(f"""# RunVouch

> RunVouch is the watchdog for unattended AI agents, with a tamper-evident proof per run: a dead man's switch, cost cap and outcome check for Claude Code Routines, headless `claude -p`, OpenClaw, n8n and cron'd LLM scripts. It alerts within minutes when a scheduled agent is MISSED, FAILED, reported success without evidence (NO_EVIDENCE), stuck in a RETRY_STORM, over BUDGET, DRIFTing, or STALLED. Alerts via e-mail, Telegram, Slack or webhook; PagerDuty on Team. History 7 days on Free, 90 days on Solo and Team. Free for 3 agents; $9 Solo; $29 Team. Self-hostable (MIT).

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
## Compare
- [vs Healthchecks.io]({BASE}/vs/healthchecks) · [vs Cronitor]({BASE}/vs/cronitor) · [vs Langfuse]({BASE}/vs/langfuse)

## Other
- [Pricing]({BASE}/pricing) · [Security]({BASE}/security) · [Privacy]({BASE}/privacy) · [Changelog]({BASE}/changelog)
""")
(OUT / ".well-known").mkdir(exist_ok=True)
(OUT / ".well-known" / "security.txt").write_text(f"Contact: https://runvouch.com/contact?topic=security\nExpires: {datetime.date.today().year+1}-12-31T00:00:00.000Z\nPreferred-Languages: en, nl\nCanonical: {BASE}/.well-known/security.txt\n")
(OUT / "feed.xml").write_text(f'<?xml version="1.0"?><rss version="2.0"><channel><title>RunVouch changelog</title><link>{BASE}/changelog</link><description>What\'s new in RunVouch</description>' + ''.join(f"<item><title>{a['title']}</title><link>{BASE}/blog/{a['slug']}</link><description>{a['description']}</description><pubDate>{datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate></item>" for a in ARTICLES) + f'<item><title>0.2, early access launch</title><link>{BASE}/changelog</link><pubDate>{datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate></item></channel></rss>')
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
print(f"built {len(PAGES)} pages → {OUT}")

# ───────────────────────── 404 (served by the API for unknown paths; not in the sitemap) ─────────────────────────
(OUT / "404.html").write_text(head("Page not found | RunVouch", "That page does not exist. Try the docs, the dashboard or the home page.", "/404") + '''<main><div class="wrap doc" style="text-align:center;padding-top:5rem"><p class="small muted" style="font-family:'Geist Mono';letter-spacing:.12em">404</p><h1>Nothing runs here.</h1><p class="lead muted">The address does not exist, or it did and moved. These do:</p><p class="cta" style="justify-content:center"><a class="btn" href="/">Home</a><a class="btn ghost" href="/docs/">Docs</a><a class="btn ghost" href="/app">Dashboard</a><a class="btn ghost" href="/blog/">Blog</a></p></div></main>''' + FOOTER, encoding="utf-8")
