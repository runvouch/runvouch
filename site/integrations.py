"""Integration pages: one per scheduler, platform or agent framework.

Every entry is written by hand from the platform's own documented behaviour; nothing here is generated
from a template of guesses. The parts that are the same everywhere (install, cadence, what RunVouch
detects) live in build.py so the page-specific part stays small and true.

Fields: slug, name, group, title, desc, h1, intro, where (how the job runs there), key (how to store
RUNVOUCH_KEY as a secret), snippet (HTML <pre>), silent (what fails silently on this platform, in the
platform's own terms), mode: "wrap" (rv run around a command) or "http" (the two HTTP calls, for
platforms where you cannot run a binary).
"""

API = "https://api.runvouch.com"

def _pre(s):
    return "<pre>" + s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\\n", "\n") + "</pre>"

HTTP_SNIPPET = _pre(f'''# 1. at the start of the job
curl -s -X POST {API}/v1/runs/start -H "X-API-Key: $RUNVOUCH_KEY" \\
  -H "content-type: application/json" -d '{{"agent":"AGENT","source":"PLATFORM"}}'
# -> {{"run_id":"..."}}

# 2. at the end, with what you know: status, cost, evidence
curl -s -X POST {API}/v1/runs/end -H "X-API-Key: $RUNVOUCH_KEY" \\
  -H "content-type: application/json" \\
  -d '{{"run_id":"...","status":"ok","cost":0.12,"evidence":{{"rows_written":true}}}}\'''')

def http_snippet(agent, platform):
    return HTTP_SNIPPET.replace("AGENT", agent).replace("PLATFORM", platform)

def wrap_snippet(agent, cmd, before="", evidence="--evidence-file out/report.json"):
    return _pre(f"{before}rv run {agent} {evidence} -- {cmd}".strip())

INTEGRATIONS = [
  # ───────────── schedulers and runtimes ─────────────
  dict(slug="kubernetes-cronjob", name="Kubernetes CronJob", group="Schedulers",
    title="Monitor Kubernetes CronJobs: missed schedules, silent success, cost | RunVouch docs",
    desc="Alert when a Kubernetes CronJob stops firing, exits 0 without doing the work, loops, or an LLM job inside it overspends. One line in the container command.",
    h1="Kubernetes CronJob", mode="wrap",
    intro="A CronJob that reports Succeeded tells you the pod exited 0. It does not tell you the schedule was missed (startingDeadlineSeconds), the job produced nothing, or an agent inside it called the same tool 400 times.",
    where="The job runs in a pod from the CronJob's <code>jobTemplate</code>. Put <code>rv</code> in the image (<code>pip install runvouch</code> in the Dockerfile, or copy the single file) and wrap the container command.",
    key="Store the key in a Secret and mount it as an environment variable: <code>env: - name: RUNVOUCH_KEY valueFrom: secretKeyRef: {name: runvouch, key: api-key}</code>.",
    snippet=_pre('''apiVersion: batch/v1
kind: CronJob
metadata: {name: nightly-report}
spec:
  schedule: "0 2 * * *"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: job
            image: ghcr.io/you/report:latest
            command: ["rv", "run", "nightly-report", "--evidence-file", "/out/report.html", "--", "python", "report.py"]
            env:
            - name: RUNVOUCH_KEY
              valueFrom: {secretKeyRef: {name: runvouch, key: api-key}}'''),
    silent="<ul><li>The controller skips a run when it misses <code>startingDeadlineSeconds</code>; nothing pages you. RunVouch fires MISSED when cadence plus grace passes without a start.</li><li><code>successfulJobsHistoryLimit</code> keeps a few pods; a job that exits 0 with an empty output looks identical to a good one. <code>--evidence-file</code> makes the empty one FAILED with NO_EVIDENCE.</li><li>With <code>concurrencyPolicy: Allow</code> a slow run overlaps the next; STALLED (max runtime) catches the slow one.</li></ul>"),
  dict(slug="systemd-timers", name="systemd timers", group="Schedulers",
    title="Monitor systemd timers and services: missed timers, failed units | RunVouch docs",
    desc="Get alerted when a systemd timer stops firing or its service fails silently, including user timers. Wrap ExecStart with rv run.",
    h1="systemd timers", mode="wrap",
    intro="A timer that fires a failing service shows up in <code>systemctl --failed</code> and nowhere else. A timer that never fires (unit disabled, machine asleep, Persistent missing) shows up nowhere at all.",
    where="The timer starts a <code>.service</code>; wrap that service's <code>ExecStart</code>. Works for system units and <code>systemctl --user</code> units.",
    key="Put <code>RUNVOUCH_KEY=rv_...</code> in a file with mode 600 and reference it with <code>EnvironmentFile=</code>; do not put the key in the unit file itself, which is world-readable.",
    snippet=_pre('''# ~/.config/systemd/user/nightly-report.service
[Service]
Type=oneshot
EnvironmentFile=%h/.config/runvouch.env
ExecStart=%h/.local/bin/rv run nightly-report --evidence-file %h/out/report.html -- %h/bin/report.sh

# ~/.config/systemd/user/nightly-report.timer
[Timer]
OnCalendar=*-*-* 02:00
Persistent=true
[Install]
WantedBy=timers.target'''),
    silent="<ul><li>Without <code>Persistent=true</code> a timer that was due while the machine was off is simply skipped.</li><li><code>OnFailure=</code> can start a notifier unit, but only on non-zero exit; a script that exits 0 with no output is never a failure to systemd.</li><li>User timers stop when the user session ends unless <code>loginctl enable-linger</code> is set; MISSED tells you the same evening, not when you next log in.</li></ul>"),
  dict(slug="gitlab-ci-schedules", name="GitLab CI scheduled pipelines", group="Schedulers",
    title="Monitor GitLab CI scheduled pipelines: skipped schedules, green no-ops | RunVouch docs",
    desc="Catch GitLab pipeline schedules that stop running (owner token expired, schedule deactivated) or pass without producing the artifact. One job line.",
    h1="GitLab CI scheduled pipelines", mode="wrap",
    intro="Pipeline schedules run as the user who created them. When that user leaves or the schedule is deactivated the pipeline silently stops, and a job that passes is not a job that did the work.",
    where="Inside the job's <code>script:</code>. The runner image needs Python 3 (<code>pip install runvouch</code>) or the single <code>rv</code> file fetched with curl.",
    key="Add <code>RUNVOUCH_KEY</code> as a masked, protected CI/CD variable (Settings, CI/CD, Variables).",
    snippet=_pre('''nightly-report:
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  script:
    - pip install -q runvouch
    - rv run nightly-report --evidence-file public/report.html -- python report.py
  artifacts:
    paths: [public/report.html]'''),
    silent="<ul><li>A deactivated schedule, or one whose owner lost access to the project, stops without a notification. MISSED covers it.</li><li>Pipeline notifications fire on failure, not on \"passed but wrote nothing\"; <code>--evidence-file</code> does.</li><li>Retried jobs (<code>retry:</code>) can run an LLM step several times; the retry-storm and per-run cost cap see the repeats.</li></ul>"),
  dict(slug="jenkins", name="Jenkins", group="Schedulers",
    title="Monitor Jenkins scheduled builds: cron triggers that stop, green no-ops | RunVouch docs",
    desc="Alert when a Jenkins job with a cron trigger stops running or passes without its artifact, without touching Jenkins notifications.",
    h1="Jenkins scheduled builds", mode="wrap",
    intro="Jenkins tells you about red builds. It does not tell you a job has not been triggered for a week because the trigger was edited away, or that a green build's script exited 0 with an empty report.",
    where="In a Pipeline <code>sh</code> step or a freestyle shell build step, on the agent that runs the job.",
    key="Store the key as a Secret text credential and bind it with <code>withCredentials([string(credentialsId: 'runvouch', variable: 'RUNVOUCH_KEY')])</code>.",
    snippet=_pre('''pipeline {
  agent any
  triggers { cron('H 2 * * *') }
  stages {
    stage('report') {
      steps {
        withCredentials([string(credentialsId: 'runvouch', variable: 'RUNVOUCH_KEY')]) {
          sh 'rv run nightly-report --evidence-file out/report.html -- python3 report.py'
        }
      }
    }
  }
}'''),
    silent="<ul><li>A disabled job or a removed trigger produces no notification; MISSED does.</li><li>Post-build e-mail fires on failure or unstable, never on \"passed, produced nothing\".</li><li>Queued builds that wait for an executor for hours are not late to Jenkins; STALLED and MISSED are measured against your cadence, not the queue.</li></ul>"),
  dict(slug="heroku-scheduler", name="Heroku Scheduler", group="Schedulers",
    title="Monitor Heroku Scheduler jobs: best-effort runs that never happened | RunVouch docs",
    desc="Heroku Scheduler is documented as best effort and can skip runs. RunVouch alerts when a scheduled dyno did not start or its task did nothing.",
    h1="Heroku Scheduler", mode="wrap",
    intro="Heroku's own documentation calls Scheduler a best-effort service: a run can be skipped without a trace. For a nightly agent that is exactly the failure you cannot see from the logs.",
    where="Scheduler starts a one-off dyno with the command you enter. Add <code>runvouch</code> to <code>requirements.txt</code> and prefix the command.",
    key="Set the key as a config var: <code>heroku config:set RUNVOUCH_KEY=rv_...</code>; one-off dynos inherit it.",
    snippet=_pre('''# Scheduler command field
rv run nightly-report --log /tmp/report.log -- python report.py
# cadence registered once, from anywhere with the key
rv agent nightly-report --cadence 24h --grace 30m --evidence'''),
    silent="<ul><li>Skipped runs are documented behaviour, not an error; MISSED is the only alert you will get.</li><li>One-off dynos have no persistent disk, so use <code>--log</code> (the log growing during the run counts as evidence) or report a URL that must return 200.</li></ul>"),
  dict(slug="aws-lambda-eventbridge", name="AWS Lambda + EventBridge Scheduler", group="Cloud functions",
    title="Monitor scheduled AWS Lambda functions (EventBridge): disabled rules, silent success | RunVouch docs",
    desc="Alert when an EventBridge schedule stops invoking your Lambda, the function returns early without doing the work, or an LLM call inside it overspends.",
    h1="AWS Lambda with EventBridge Scheduler", mode="http",
    intro="CloudWatch can alarm on errors and on invocation count, if you build those alarms. It cannot tell a function that returned in 200 ms because a feature flag was off from one that did the work.",
    where="Inside the handler, with the two HTTP calls (no binary needed). Python: <code>pip install runvouch</code> into the deployment package and use <code>runvouch.vouch()</code> as a context manager; any language: plain HTTPS.",
    key="Put the key in Secrets Manager or SSM Parameter Store and read it at cold start, or as an encrypted environment variable on the function.",
    snippet=_pre('''import os, runvouch
runvouch.agent("nightly-report", cadence_s=86400, grace_s=1800, evidence_required=True)

def handler(event, context):
    with runvouch.vouch("nightly-report", evidence=lambda: {"s3_object": wrote_object}) as run:
        wrote_object = build_report()   # your work
        run.tool("bedrock.invoke", {"model": "anthropic.claude-3"}, cost=0.02)'''),
    silent="<ul><li>A disabled or deleted schedule stops invocations; without a custom alarm on <code>Invocations == 0</code> nobody notices. MISSED notices.</li><li>Timeouts show as errors, but a function that catches everything and returns <code>{\"ok\": true}</code> is a success to Lambda. Evidence is what separates the two.</li><li>Retries (asynchronous invocation retries twice by default) can triple an LLM bill; the per-run cost cap and retry-storm detector see them as one agent.</li></ul>"),
  dict(slug="google-cloud-scheduler", name="Google Cloud Scheduler", group="Cloud functions",
    title="Monitor Google Cloud Scheduler jobs (Cloud Run jobs, Cloud Functions) | RunVouch docs",
    desc="Alert when a Cloud Scheduler job stops firing, the Cloud Run job or function returns 2xx without doing the work, or an LLM step overspends.",
    h1="Google Cloud Scheduler with Cloud Run jobs and Cloud Functions", mode="wrap",
    intro="Cloud Scheduler counts an HTTP 2xx as success and retries on anything else. Everything that goes wrong inside a 2xx is yours to find.",
    where="For a Cloud Run <em>job</em>, wrap the container command with <code>rv run</code> (the image needs Python 3). For an HTTP-triggered function, use the two HTTP calls or the Python client inside the handler.",
    key="Reference the key from Secret Manager as an environment variable on the Cloud Run job or function (<code>--set-secrets RUNVOUCH_KEY=runvouch-key:latest</code>).",
    snippet=_pre('''# Cloud Run job, container command
gcloud run jobs create nightly-report --image gcr.io/PROJECT/report \\
  --set-secrets RUNVOUCH_KEY=runvouch-key:latest \\
  --command rv --args run,nightly-report,--evidence-file,/tmp/report.html,--,python,report.py
# schedule it
gcloud scheduler jobs create http nightly-report --schedule "0 2 * * *" \\
  --uri "https://run.googleapis.com/v2/projects/PROJECT/locations/REGION/jobs/nightly-report:run" \\
  --oauth-service-account-email SA@PROJECT.iam.gserviceaccount.com'''),
    silent="<ul><li>A paused scheduler job, or one whose service account lost <code>run.jobs.run</code>, fails on the scheduler side; the alerting policy for that is not created by default. MISSED needs no policy.</li><li>A function that returns 200 after catching an exception is a success to Scheduler and to Cloud Monitoring.</li><li>Scheduler retries plus function retries can run an agent several times an hour; the daily cost cap holds regardless.</li></ul>"),
  dict(slug="azure-functions-timer", name="Azure Functions timer trigger", group="Cloud functions",
    title="Monitor Azure Functions timer triggers: stopped apps, silent success | RunVouch docs",
    desc="Alert when an Azure Functions timer trigger stops running (app stopped, scale-to-zero on Consumption) or completes without doing the work.",
    h1="Azure Functions timer trigger", mode="http",
    intro="A timer-triggered function that runs, catches its own exception and returns is a success in Application Insights. A function app that is stopped does not run at all, and no default alert says so.",
    where="Inside the function, with the Python client or the two HTTP calls. NCRONTAB schedule stays as it is.",
    key="Store the key in Key Vault and reference it from an app setting (<code>@Microsoft.KeyVault(SecretUri=...)</code>), or as a plain app setting for a first test.",
    snippet=_pre('''import azure.functions as func, runvouch
app = func.FunctionApp()

@app.timer_trigger(schedule="0 0 2 * * *", arg_name="timer")
def nightly_report(timer: func.TimerRequest):
    with runvouch.vouch("nightly-report", evidence=lambda: {"blob_written": ok}) as run:
        ok = build_report()'''),
    silent="<ul><li>On the Consumption plan the timer trigger runs on a scale controller; when the app is stopped or the storage account is unreachable, nothing fires and nothing alerts. MISSED does.</li><li><code>timer.past_due</code> tells your code a run was late; it does not tell you.</li><li>Application Insights availability tests cover HTTP endpoints, not whether a nightly job produced its output.</li></ul>"),
  dict(slug="cloudflare-workers-cron", name="Cloudflare Workers Cron Triggers", group="Cloud functions",
    title="Monitor Cloudflare Workers Cron Triggers: scheduled handlers that stop or no-op | RunVouch docs",
    desc="Two fetch() calls in your scheduled() handler give a Cloudflare Worker cron a dead man's switch, evidence and a cost cap.",
    h1="Cloudflare Workers Cron Triggers", mode="http",
    intro="A Worker's <code>scheduled()</code> handler has no output you can look at later, no exit code and, on the free plan, a CPU time limit that ends a run mid-way without an error you will see.",
    where="Inside <code>scheduled(event, env, ctx)</code>, with two <code>fetch()</code> calls to the API. Workers cannot run a binary.",
    key="<code>wrangler secret put RUNVOUCH_KEY</code>; read it as <code>env.RUNVOUCH_KEY</code>.",
    snippet=_pre('''export default {
  async scheduled(event, env, ctx) {
    const h = {"X-API-Key": env.RUNVOUCH_KEY, "content-type": "application/json"};
    const {run_id} = await (await fetch("''' + API + '''/v1/runs/start", {method: "POST", headers: h,
      body: JSON.stringify({agent: "nightly-report", source: "cloudflare"})})).json();
    let status = "ok", evidence = {};
    try { evidence = {rows: await doTheWork(env)}; } catch (e) { status = "fail"; }
    ctx.waitUntil(fetch("''' + API + '''/v1/runs/end", {method: "POST", headers: h,
      body: JSON.stringify({run_id, status, evidence})}));
  }
}
// wrangler.toml:  [triggers]  crons = ["0 2 * * *"]'''),
    silent="<ul><li>A cron trigger removed from <code>wrangler.toml</code> on the next deploy stops silently; MISSED is the only signal.</li><li>Exceeding CPU time kills the invocation; the start call already happened, so RunVouch marks the run STALLED when it never ends.</li><li>An <code>await</code> that is not wrapped in <code>ctx.waitUntil</code> can be cut off; put the end call in <code>waitUntil</code> as above.</li></ul>"),
  dict(slug="vercel-cron", name="Vercel Cron Jobs", group="Cloud functions",
    title="Monitor Vercel Cron Jobs: routes that return 200 and do nothing | RunVouch docs",
    desc="Vercel cron calls a route and records the status code. RunVouch adds the missing part: did the route do the work, on time, within budget.",
    h1="Vercel Cron Jobs", mode="http",
    intro="A cron entry in <code>vercel.json</code> hits a route on a schedule and logs the status. A route that returns 200 after an early return is a success; a function that hits its duration limit is a log line.",
    where="Inside the route handler (Next.js route handler or serverless function), with two <code>fetch()</code> calls. Cron jobs run against the production deployment only.",
    key="Project Settings, Environment Variables: <code>RUNVOUCH_KEY</code>, production scope. Keep <code>CRON_SECRET</code> as Vercel documents it so only Vercel can call the route.",
    snippet=_pre('''// app/api/cron/report/route.ts
export async function GET(req: Request) {
  if (req.headers.get("authorization") !== `Bearer ${process.env.CRON_SECRET}`) return new Response("no", {status: 401});
  const h = {"X-API-Key": process.env.RUNVOUCH_KEY!, "content-type": "application/json"};
  const {run_id} = await (await fetch("''' + API + '''/v1/runs/start", {method: "POST", headers: h,
    body: JSON.stringify({agent: "nightly-report", source: "vercel"})})).json();
  const rows = await buildReport();
  await fetch("''' + API + '''/v1/runs/end", {method: "POST", headers: h,
    body: JSON.stringify({run_id, status: "ok", evidence: {rows: rows > 0}})});
  return Response.json({rows});
}
// vercel.json: {"crons": [{"path": "/api/cron/report", "schedule": "0 2 * * *"}]}'''),
    silent="<ul><li>Cron jobs only run on production; a preview deployment that looks fine never runs them. MISSED on the production agent is what tells you the schedule is not live.</li><li>The Hobby plan runs crons once a day at most and may run them within the hour, not at the minute; set grace accordingly.</li><li>Function duration limits end a run without a 5xx you will act on; STALLED covers a start without an end.</li></ul>"),
  dict(slug="supabase-pg-cron", name="Supabase (pg_cron + Edge Functions)", group="Cloud functions",
    title="Monitor Supabase pg_cron jobs and scheduled Edge Functions | RunVouch docs",
    desc="pg_cron fires an HTTP call through pg_net and forgets it. RunVouch tells you whether the Edge Function ran, finished and produced its result.",
    h1="Supabase: pg_cron and Edge Functions", mode="http",
    intro="The documented pattern is <code>cron.schedule()</code> calling <code>net.http_post()</code> to an Edge Function. pg_net is fire-and-forget: a function that never ran, or ran and failed, leaves only a row in <code>net._http_response</code> that nobody reads.",
    where="Inside the Edge Function (Deno), with two <code>fetch()</code> calls around the work.",
    key="<code>supabase secrets set RUNVOUCH_KEY=rv_...</code>; read it with <code>Deno.env.get(\"RUNVOUCH_KEY\")</code>.",
    snippet=_pre('''// supabase/functions/nightly-report/index.ts
Deno.serve(async () => {
  const h = {"X-API-Key": Deno.env.get("RUNVOUCH_KEY")!, "content-type": "application/json"};
  const {run_id} = await (await fetch("''' + API + '''/v1/runs/start", {method: "POST", headers: h,
    body: JSON.stringify({agent: "nightly-report", source: "supabase"})})).json();
  const inserted = await buildReport();
  await fetch("''' + API + '''/v1/runs/end", {method: "POST", headers: h,
    body: JSON.stringify({run_id, status: "ok", evidence: {inserted: inserted > 0}})});
  return new Response("ok");
});
-- SQL, once:
select cron.schedule('nightly-report', '0 2 * * *',
  $$ select net.http_post(url := 'https://PROJECT.supabase.co/functions/v1/nightly-report',
       headers := '{"Authorization": "Bearer SERVICE_ROLE_KEY"}'::jsonb) $$);'''),
    silent="<ul><li>pg_cron runs inside the database; a paused project or a dropped job produces no alert. MISSED does.</li><li>pg_net records the HTTP response in a table and nothing else happens on a 500.</li><li>Edge Functions have a wall-clock limit; a function that is cut off started a run and never ended it, which is STALLED.</li></ul>"),
  dict(slug="render-cron", name="Render Cron Jobs", group="Platforms",
    title="Monitor Render Cron Jobs: missed runs and green no-ops | RunVouch docs",
    desc="Wrap a Render cron job command with rv run to get MISSED, FAILED, NO_EVIDENCE and cost alerts, without adding a service.",
    h1="Render Cron Jobs", mode="wrap",
    intro="Render shows each cron run's log and exit status in the dashboard. It does not page you when runs stop, and exit 0 with an empty output is a success.",
    where="The Cron Job service's command field. The build installs <code>runvouch</code> from <code>requirements.txt</code>.",
    key="Environment tab of the cron job service: <code>RUNVOUCH_KEY</code>. Environment groups work too.",
    snippet=wrap_snippet("nightly-report", "python report.py", before="# Render cron job command\n", evidence="--log /tmp/report.log"),
    silent="<ul><li>A suspended service, or a cron job whose schedule was edited, stops without notification.</li><li>Cron jobs on Render have no persistent disk by default; use <code>--log</code> or URL evidence rather than a file that must survive the run.</li></ul>"),
  dict(slug="railway-cron", name="Railway cron schedules", group="Platforms",
    title="Monitor Railway cron schedules: services that stop running or do nothing | RunVouch docs",
    desc="Railway runs a service on a cron schedule and shows the logs. RunVouch adds the dead man's switch, evidence check and cost cap.",
    h1="Railway cron schedules", mode="wrap",
    intro="A Railway service with a cron schedule starts, runs its start command and exits. The dashboard shows it happened; nothing tells you when it stops happening.",
    where="The service's start command. Railway expects the process to exit when done; <code>rv run</code> exits with the wrapped command's code.",
    key="Service Variables: <code>RUNVOUCH_KEY</code>. Shared variables work across services.",
    snippet=wrap_snippet("nightly-report", "python report.py", before="# Railway start command\n", evidence="--log /tmp/report.log"),
    silent="<ul><li>Railway documents that a cron run is skipped if the previous execution is still running; that is a MISSED in RunVouch terms and a STALLED for the one still going.</li><li>Deploy failures stop the schedule with the service; MISSED covers both.</li></ul>"),
  dict(slug="fly-io", name="Fly.io scheduled Machines", group="Platforms",
    title="Monitor Fly.io scheduled Machines and cron in containers | RunVouch docs",
    desc="Fly.io has no cron service; scheduled Machines and in-container cron both need an outside watchdog. rv run gives them one.",
    h1="Fly.io scheduled Machines", mode="wrap",
    intro="On Fly you either run a Machine with a schedule (<code>fly machine run --schedule daily</code>) or run cron (often supercronic) inside a long-lived Machine. Both stop silently when the Machine is destroyed, stuck or out of memory.",
    where="The Machine's command, or the crontab line inside the container. The image needs Python 3 for <code>rv</code>.",
    key="<code>fly secrets set RUNVOUCH_KEY=rv_...</code>; secrets are exposed as environment variables in every Machine of the app.",
    snippet=_pre('''# scheduled Machine (runs once per schedule, then stops)
fly machine run ghcr.io/you/report:latest --schedule daily \\
  --command "rv run nightly-report --log /tmp/report.log -- python report.py"

# or, inside a long-lived Machine with supercronic
0 2 * * * rv run nightly-report --evidence-file /data/report.html -- python /app/report.py'''),
    silent="<ul><li>Scheduled Machines run \"approximately\" at the interval; use a grace of an hour or more.</li><li>An OOM-killed Machine restarts (or does not); the run that was in flight never ends and becomes STALLED.</li><li>A Machine that was stopped by <code>fly scale count 0</code> or a failed deploy takes the cron with it; MISSED is the signal.</li></ul>"),
  dict(slug="docker-cron", name="Cron inside Docker (supercronic, crond)", group="Platforms",
    title="Monitor cron inside Docker containers: supercronic, crond, ofelia | RunVouch docs",
    desc="Cron in a container dies with the container and logs to nowhere. Wrap each line with rv run so you learn about it before the next morning.",
    h1="Cron inside Docker", mode="wrap",
    intro="Whether you use supercronic, BusyBox crond or ofelia, a scheduled command inside a container has the same two silent failures: the container is not running, or the command ran and produced nothing.",
    where="The crontab line (or the ofelia label). Install <code>runvouch</code> in the image; <code>rv</code> has no dependencies beyond Python 3.",
    key="Pass the key as an environment variable (<code>-e RUNVOUCH_KEY</code>, <code>env_file:</code> in Compose, or a Docker secret read at start).",
    snippet=_pre('''# crontab used by supercronic
0 2 * * * rv run nightly-report --evidence-file /out/report.html -- python /app/report.py

# docker-compose.yml
services:
  cron:
    image: ghcr.io/you/report:latest
    command: supercronic /app/crontab
    env_file: .env          # contains RUNVOUCH_KEY=rv_...
    volumes: ["./out:/out"]'''),
    silent="<ul><li>BusyBox crond inside a container does not load the container's environment for the job by default; if the job cannot see <code>RUNVOUCH_KEY</code>, <code>rv</code> fails open and runs the job unmonitored. Test with <code>docker exec ... rv status</code>.</li><li>A container restart loop means no cron ticks; MISSED after cadence plus grace.</li><li>Logs go to the cron daemon's stdout at best; <code>--log</code> keeps the job's output as evidence.</li></ul>"),
  # ───────────── orchestrators ─────────────
  dict(slug="airflow", name="Apache Airflow", group="Orchestrators",
    title="Monitor Airflow DAGs for silent success and empty outputs | RunVouch docs",
    desc="Airflow alerts on task failure and SLA misses. RunVouch adds what a green DAG run cannot prove: the output exists, the run was on time, the LLM tasks stayed under budget.",
    h1="Apache Airflow", mode="wrap",
    intro="Airflow is very good at telling you a task failed. A task that succeeds with an empty DataFrame, a DAG that is paused, or a scheduler that stopped scheduling all look like silence.",
    where="Wrap the command of a <code>BashOperator</code>, or use the Python client inside a <code>PythonOperator</code> / <code>@task</code>. One RunVouch agent per DAG (or per critical task) is the usual shape.",
    key="An Airflow Variable or Connection backed by your secrets backend; pass it into the task environment (<code>env={\"RUNVOUCH_KEY\": ...}</code>) rather than hardcoding.",
    snippet=_pre('''from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
from airflow.models import Variable
import pendulum, runvouch

@dag(schedule="0 2 * * *", start_date=pendulum.datetime(2026, 1, 1, tz="UTC"), catchup=False)
def nightly_report():
    build = BashOperator(task_id="build",
        env={"RUNVOUCH_KEY": Variable.get("runvouch_key")},
        bash_command="rv run nightly-report --evidence-file /out/report.html -- python /opt/report.py")

    @task
    def summarise():
        with runvouch.vouch("nightly-summary", evidence=lambda: {"rows": n > 0}) as run:
            n = summarise_rows(run)   # run.tool(...) per LLM call for cost and loop detection

    build >> summarise()

nightly_report()'''),
    silent="<ul><li>A paused DAG (or one that failed to import after a bad deploy) schedules nothing; the DAG import error banner is not an alert. MISSED is.</li><li><code>sla_miss_callback</code> only fires when the scheduler is healthy enough to notice.</li><li>A task with <code>retries=3</code> around an LLM call is a retry storm with a budget; the per-run cost cap ends it.</li></ul>"),
  dict(slug="prefect", name="Prefect", group="Orchestrators",
    title="Monitor Prefect deployments: Late runs, missing workers, empty results | RunVouch docs",
    desc="Prefect marks runs Late when no worker picks them up. RunVouch pages you about it, checks the flow produced its result, and caps LLM spend per run.",
    h1="Prefect", mode="wrap",
    intro="A Prefect deployment with a schedule creates flow runs; a worker on the right work pool executes them. When the worker is gone, runs pile up as Late and Scheduled, and the flow's own failure hooks never fire because nothing failed.",
    where="Around the flow: wrap the process that runs the flow (<code>rv run ... -- python flow.py</code> or <code>prefect deployment run</code>), or use the Python client inside the flow function. Prefect's own retries and logging stay untouched.",
    key="A Prefect Secret block (<code>Secret.load(\"runvouch-key\")</code>) or an environment variable on the work pool's job template.",
    snippet=_pre('''from prefect import flow, task
from prefect.blocks.system import Secret
import os, runvouch

@flow(name="nightly-report")
def nightly_report():
    os.environ["RUNVOUCH_KEY"] = Secret.load("runvouch-key").get()
    with runvouch.vouch("nightly-report", evidence=lambda: {"report": os.path.exists("out/report.html")}) as run:
        rows = extract()
        run.tool("llm.summarise", {"rows": len(rows)}, cost=0.03)
        write_report(rows)

# prefect deploy ... --cron "0 2 * * *"'''),
    silent="<ul><li>Late runs are visible in the UI and in automations you have to create; RunVouch's MISSED needs neither.</li><li>A flow that completes with an empty result is Completed; evidence separates it from a good run.</li><li>Prefect task retries multiply LLM calls; the retry-storm detector sees identical tool inputs across retries.</li></ul>"),
  dict(slug="dagster", name="Dagster", group="Orchestrators",
    title="Monitor Dagster schedules and sensors: daemon down, green no-ops | RunVouch docs",
    desc="Dagster schedules stop when the daemon stops. RunVouch alerts on the missing run, checks the asset was actually produced, and caps LLM cost per run.",
    h1="Dagster", mode="wrap",
    intro="Schedules and sensors in Dagster are executed by the dagster-daemon. When it is down, unhealthy or pointed at a stale code location, nothing runs and the UI shows a status you have to go and look at.",
    where="Inside an op or asset with the Python client, or wrap the run launcher command for a whole job. One agent per job or per critical asset.",
    key="An environment variable on the code location (Dagster+ env vars, or the container env for OSS); read it with <code>EnvVar(\"RUNVOUCH_KEY\")</code> in a resource.",
    snippet=_pre('''from dagster import asset, ScheduleDefinition, define_asset_job, Definitions
import os, runvouch

@asset
def nightly_report():
    with runvouch.vouch("nightly-report", evidence=lambda: {"report": os.path.exists("out/report.html")}) as run:
        rows = extract()
        run.tool("llm.summarise", {"rows": len(rows)}, cost=0.03)
        write_report(rows)

job = define_asset_job("nightly_report_job", selection=[nightly_report])
defs = Definitions(assets=[nightly_report], jobs=[job],
    schedules=[ScheduleDefinition(job=job, cron_schedule="0 2 * * *")])'''),
    silent="<ul><li>A stopped daemon or a schedule left in the Stopped state after a redeploy produces no runs; MISSED after cadence plus grace.</li><li>An asset materialised with zero rows is a successful materialisation; evidence is the check.</li><li>Run retries (<code>max_retries</code>) re-execute LLM ops; the per-run cost cap holds across the retry.</li></ul>"),
  dict(slug="celery-beat", name="Celery beat", group="Orchestrators",
    title="Monitor Celery beat periodic tasks: beat down, workers gone, tasks that no-op | RunVouch docs",
    desc="Celery beat schedules; workers execute. When either is gone, periodic tasks silently stop. RunVouch alerts on the missing run and on tasks that finish without their result.",
    h1="Celery beat periodic tasks", mode="wrap",
    intro="Celery beat is a single process that publishes tasks on a schedule. If it dies, or a worker for that queue is not running, tasks are late or never run, and Flower will not page you.",
    where="Inside the task function with the Python client (recommended), or wrap the worker-side command if the task shells out.",
    key="An environment variable on the worker processes; beat itself does not need the key.",
    snippet=_pre('''from celery import Celery
from celery.schedules import crontab
import runvouch

app = Celery("jobs", broker="redis://redis:6379/0")
app.conf.beat_schedule = {"nightly-report": {"task": "jobs.nightly_report", "schedule": crontab(hour=2, minute=0)}}

@app.task(bind=True, max_retries=2)
def nightly_report(self):
    with runvouch.vouch("nightly-report", evidence=lambda: {"rows": n > 0}) as run:
        n = build_report(run)'''),
    silent="<ul><li>Beat down means no task is even published; MISSED is the only external signal.</li><li>A task that is published but never consumed (wrong queue, no worker) is neither failed nor succeeded; it is a MISSED start.</li><li><code>max_retries</code> around an LLM call repeats the spend; the per-run cost cap and retry-storm detector cover it.</li></ul>"),
  dict(slug="apscheduler", name="APScheduler (in-process)", group="Orchestrators",
    title="Monitor APScheduler and node-cron jobs: schedulers that die with the process | RunVouch docs",
    desc="In-process schedulers (APScheduler, node-cron, node-schedule) stop when the process stops. RunVouch notices from outside.",
    h1="APScheduler and other in-process schedulers", mode="wrap",
    intro="APScheduler, node-cron and node-schedule run inside your application process. When that process is restarted at the wrong moment, crashes or is scaled to zero, the schedule goes with it and nothing outside knows.",
    where="Inside the scheduled function with the Python or Node client. The agent's cadence is what makes the missing process visible.",
    key="An environment variable on the process.",
    snippet=_pre('''from apscheduler.schedulers.blocking import BlockingScheduler
import runvouch

def nightly_report():
    with runvouch.vouch("nightly-report", evidence=lambda: {"rows": n > 0}) as run:
        n = build_report(run)

sched = BlockingScheduler()
sched.add_job(nightly_report, "cron", hour=2, minute=0, misfire_grace_time=3600)
sched.start()'''),
    silent="<ul><li>A job missed while the process was down is dropped after <code>misfire_grace_time</code>; with the default (1 second in APScheduler 3) it is dropped almost always.</li><li>Two replicas of the process run the job twice; RunVouch shows both runs under one agent, and the daily cost cap counts both.</li><li>A process stuck on a lock still looks alive to the orchestrator; STALLED catches the run that never ends.</li></ul>"),
  dict(slug="temporal", name="Temporal Schedules", group="Orchestrators",
    title="Monitor Temporal Schedules and workflows: no workers polling, silent completion | RunVouch docs",
    desc="Temporal guarantees the workflow will eventually run. RunVouch tells you it did not run on time, and that it produced what it was supposed to.",
    h1="Temporal Schedules", mode="wrap",
    intro="A Temporal Schedule starts workflows on time; a worker polling the task queue executes them. With no worker, workflow tasks wait in the queue indefinitely with no error, because from Temporal's point of view nothing is wrong yet.",
    where="Inside the workflow's first and last activity, or around the worker process if one workflow per process. Use the two HTTP calls from an activity (activities may do I/O; workflows must not).",
    key="An environment variable on the worker.",
    snippet=_pre('''# activities.py (activities may do I/O; workflows must not)
import os, requests
from temporalio import activity
H = {"X-API-Key": os.environ["RUNVOUCH_KEY"], "content-type": "application/json"}

@activity.defn
async def start_run(agent: str) -> str:
    return requests.post("https://api.runvouch.com/v1/runs/start", headers=H, timeout=10,
                         json={"agent": agent, "source": "temporal"}).json()["run_id"]

@activity.defn
async def end_run(run_id: str, ok: bool, rows: int) -> None:
    requests.post("https://api.runvouch.com/v1/runs/end", headers=H, timeout=10,
                  json={"run_id": run_id, "status": "ok" if ok else "fail", "evidence": {"rows": rows > 0}})

# the schedule, once:  temporal schedule create --schedule-id nightly-report --cron "0 2 * * *" \\
#   --workflow-type NightlyReport --task-queue reports'''),
    silent="<ul><li>No worker on the task queue means the schedule fires and the work waits; the schedule's own counters say \"running\". MISSED and STALLED both apply.</li><li>Activity retries are unlimited by default; an LLM activity that keeps failing keeps spending. The per-run cap ends it.</li><li>Overlap policy Skip drops a start; that is a MISSED you would otherwise not see.</li></ul>"),
  dict(slug="windmill", name="Windmill", group="Orchestrators",
    title="Monitor Windmill scheduled scripts and flows | RunVouch docs",
    desc="Windmill schedules scripts and flows and shows their runs. RunVouch adds an outside dead man's switch, evidence and an LLM cost cap.",
    h1="Windmill", mode="wrap",
    intro="Windmill has error handlers and a runs page. It does not have an outside party that notices the whole instance, or one worker group, has stopped taking jobs.",
    where="Inside the script (Python or Bash) with the client or <code>rv run</code>; Windmill scripts can shell out.",
    key="A Windmill variable marked secret, read with <code>wmill.get_variable(\"u/you/runvouch_key\")</code>, or a worker environment variable.",
    snippet=_pre('''# Python script scheduled in Windmill
import os, wmill, runvouch
os.environ["RUNVOUCH_KEY"] = wmill.get_variable("u/you/runvouch_key")

def main():
    with runvouch.vouch("nightly-report", evidence=lambda: {"rows": n > 0}) as run:
        n = build_report(run)
    return {"rows": n}'''),
    silent="<ul><li>A disabled schedule, or a worker group with zero workers, queues jobs without an error.</li><li>Flow error handlers fire on failure; a flow that completes with an empty result does not fail.</li></ul>"),
  # ───────────── no-code automation ─────────────
  dict(slug="make", name="Make (Integromat)", group="No-code automation",
    title="Monitor Make scenarios: deactivated after errors, runs that do nothing | RunVouch docs",
    desc="Make turns a scenario off after repeated errors and e-mails you once. RunVouch keeps watching: missed runs, empty runs, LLM cost per run.",
    h1="Make scenarios", mode="http",
    intro="A Make scenario on a schedule runs until Make deactivates it after consecutive errors, or until someone toggles it off. The deactivation e-mail is easy to miss, and a scenario that runs with zero bundles is a normal run.",
    where="Two HTTP modules in the scenario: one at the start, one at the end, with the API's JSON.",
    key="Store the key in a Make connection or as a scenario variable; put it in the <code>X-API-Key</code> header of both HTTP modules.",
    snippet=http_snippet("lead-enricher", "make"),
    silent="<ul><li>Auto-deactivation after errors is documented Make behaviour; the scenario does not run again until you re-enable it. MISSED tells you the same hour.</li><li>Zero bundles processed is a successful run in the history; report <code>evidence: {\"bundles\": count &gt; 0}</code> from the end module.</li><li>Operations consumed by an OpenAI module are visible per run in Make; passing the cost into the end call makes the daily cap work.</li></ul>"),
  dict(slug="zapier", name="Zapier", group="No-code automation",
    title="Monitor Zapier Zaps: turned off after errors, Schedule by Zapier that stops | RunVouch docs",
    desc="Zapier pauses a Zap after too many errors and can hold tasks. RunVouch alerts when a scheduled Zap stops running or completes without doing the work.",
    h1="Zapier Zaps", mode="http",
    intro="A Zap with a Schedule by Zapier trigger runs until Zapier turns it off (repeated errors, a disconnected app, a plan limit). Zap History shows what happened; it does not call you.",
    where="Two Webhooks by Zapier steps (POST, JSON), one right after the trigger and one at the end.",
    key="Paste the key in the header field of both webhook steps, or keep it in a Storage by Zapier value.",
    snippet=http_snippet("weekly-digest", "zapier"),
    silent="<ul><li>Zapier turning a Zap off, and held tasks when a plan limit is reached, are both silent until you open Zap History.</li><li>Filter steps that stop a run early are successful runs; only the end call with evidence distinguishes them.</li></ul>"),
  dict(slug="home-assistant", name="Home Assistant automations", group="No-code automation",
    title="Monitor Home Assistant scheduled automations and shell commands | RunVouch docs",
    desc="Time-triggered Home Assistant automations that call scripts or LLM services can stop or no-op after an update. RunVouch notices from outside the house.",
    h1="Home Assistant automations", mode="http",
    intro="An automation with a time trigger that runs a <code>shell_command</code> or a conversation agent keeps working until an update breaks the integration or the automation is left disabled. The logbook records it; nobody reads the logbook.",
    where="A <code>rest_command</code> at the start and end of the automation, or wrap the shell command with <code>rv run</code> if the script runs on the same host.",
    key="Put the key in <code>secrets.yaml</code> and reference it with <code>!secret runvouch_key</code>.",
    snippet=_pre('''# configuration.yaml
rest_command:
  runvouch_start:
    url: ''' + API + '''/v1/runs/start
    method: POST
    headers: {X-API-Key: !secret runvouch_key, content-type: application/json}
    payload: '{"agent":"nightly-backup","source":"home-assistant"}'
  runvouch_end:
    url: ''' + API + '''/v1/runs/end
    method: POST
    headers: {X-API-Key: !secret runvouch_key, content-type: application/json}
    payload: '{"run_id":"{{ run_id }}","status":"ok","evidence":{"backup": true}}'

# automation: call runvouch_start, store response_variable, do the work, call runvouch_end with run_id'''),
    silent="<ul><li>Disabled automations and broken integrations after a core update do not notify; MISSED does.</li><li>A shell command that exits non-zero is a warning in the log, not an alert.</li></ul>"),
  # ───────────── agent frameworks ─────────────
  dict(slug="langgraph", name="LangGraph", group="Agent frameworks",
    title="Monitor scheduled LangGraph agents: loops, cost per run, missing output | RunVouch docs",
    desc="A LangGraph graph on a schedule can loop on a tool, overspend, or finish without its artifact. Wrap the run and report each tool call for retry-storm and cost detection.",
    h1="LangGraph", mode="wrap",
    intro="LangGraph gives you cycles by design. A cycle that never converges, on a nightly schedule, is a bill. LangSmith shows you the trace afterwards; RunVouch stops the run when it crosses the cap.",
    where="Around the graph invocation with the Python client; report each tool node call with <code>run.tool()</code> so identical inputs are detected as a retry storm.",
    key="An environment variable wherever the graph runs (cron, container, Lambda).",
    snippet=_pre('''import runvouch
from graph import app   # your compiled StateGraph

runvouch.agent("research-digest", cadence_s=86400, cap_run_cost=2, evidence_required=True)

with runvouch.vouch("research-digest", evidence=lambda: {"digest": len(result["digest"]) > 200}) as run:
    result = None
    for event in app.stream({"topic": "..."}, stream_mode="updates"):
        for node, update in event.items():
            run.tool(node, update.get("tool_input", {}), cost=update.get("cost", 0))
    result = app.get_state(config).values'''),
    silent="<ul><li>Cycles with a high recursion limit look like progress; 40 identical tool inputs in one run is RETRY_STORM.</li><li>A graph that ends with an empty final state is a completed run; evidence says whether the digest exists.</li><li>Nothing in LangGraph knows the schedule; MISSED comes from the agent's cadence.</li></ul>"),
  dict(slug="crewai", name="CrewAI", group="Agent frameworks",
    title="Monitor scheduled CrewAI crews: runaway iterations, cost caps, evidence | RunVouch docs",
    desc="Wrap crew.kickoff() with RunVouch to cap cost per run, detect a crew looping on a tool and confirm the deliverable exists.",
    h1="CrewAI", mode="wrap",
    intro="A crew has <code>max_iter</code> per agent and <code>max_rpm</code>; neither is a budget. A nightly crew that keeps re-planning burns tokens until the iteration limit, then returns whatever it has.",
    where="Around <code>crew.kickoff()</code> with the Python client, plus <code>run.tool()</code> from a step callback for loop detection.",
    key="An environment variable on the host or container that runs the crew.",
    snippet=_pre('''import runvouch
from crewai import Crew

def on_step(step):
    run.tool(step.tool or "llm", {"input": step.tool_input or ""}, cost=getattr(step, "cost", 0))

crew = Crew(agents=[...], tasks=[...], step_callback=on_step)
with runvouch.vouch("weekly-competitor-brief", evidence=lambda: {"brief": len(out.raw) > 500}) as run:
    out = crew.kickoff()'''),
    silent="<ul><li>Reaching <code>max_iter</code> is not an error; the crew returns a partial answer. Evidence (length, file, URL) is what fails it.</li><li>Per-agent token usage is available in <code>crew.usage_metrics</code>; pass it as cost so the daily cap works.</li></ul>"),
  dict(slug="autogen", name="AutoGen", group="Agent frameworks",
    title="Monitor scheduled AutoGen agents: conversations that never terminate, cost per run | RunVouch docs",
    desc="Multi-agent chats in AutoGen can run to max_turns without producing the result. RunVouch caps the run, detects loops and checks the output.",
    h1="AutoGen", mode="wrap",
    intro="Two AutoGen agents that keep agreeing to continue, or a tool that keeps failing and being retried by the assistant, look exactly like work until the bill arrives.",
    where="Around the chat or team run with the Python client, reporting tool executions through <code>run.tool()</code>.",
    key="An environment variable wherever the script runs.",
    snippet=_pre('''import asyncio, runvouch
from autogen_agentchat.teams import RoundRobinGroupChat

async def main():
    with runvouch.vouch("nightly-triage", evidence=lambda: {"labels": labels_applied > 0}) as run:
        team = RoundRobinGroupChat([triager, verifier], max_turns=12)
        result = await team.run(task="Triage new issues and apply labels")
        for m in result.messages:
            if getattr(m, "type", "") == "ToolCallExecutionEvent":
                run.tool("tool", {"content": str(m.content)[:200]})

asyncio.run(main())'''),
    silent="<ul><li><code>max_turns</code> is a ceiling, not an alarm; hitting it every night is invisible without evidence.</li><li>Repeated identical tool executions are RETRY_STORM once reported.</li></ul>"),
  dict(slug="openai-agents-sdk", name="OpenAI Agents SDK", group="Agent frameworks",
    title="Monitor scheduled OpenAI Agents SDK runs: max_turns, cost, evidence | RunVouch docs",
    desc="Wrap Runner.run() with RunVouch for a per-run cost cap, retry-storm detection on tool calls and a check that the agent produced its output.",
    h1="OpenAI Agents SDK", mode="wrap",
    intro="The Agents SDK stops a run at <code>max_turns</code> and raises. Everything below that limit, including a run that spent $30 calling the same function, is a normal completion.",
    where="Around <code>Runner.run()</code> with the Python client; report each tool call from the run result's new items.",
    key="An environment variable on the host that runs the script.",
    snippet=_pre('''import asyncio, runvouch
from agents import Agent, Runner

async def main():
    res = None
    with runvouch.vouch("morning-briefing",
                        evidence=lambda: {"briefing": len(res.final_output) > 300},
                        cost=lambda: res.context_wrapper.usage.total_tokens * 0.000004) as run:   # your price per token
        res = await Runner.run(agent, "Write today's briefing", max_turns=20)
        for item in res.new_items:
            if item.type == "tool_call_item":
                run.tool(item.raw_item.name, {"args": item.raw_item.arguments})

asyncio.run(main())'''),
    silent="<ul><li>Tracing in the OpenAI dashboard is after the fact; the cost cap acts during the run.</li><li>A final output that is an apology is a completed run; evidence is a length or a file, not a status.</li></ul>"),
  dict(slug="pydantic-ai", name="Pydantic AI and smolagents", group="Agent frameworks",
    title="Monitor scheduled Pydantic AI and smolagents runs | RunVouch docs",
    desc="Lightweight agent libraries have no scheduler and no budget. Wrapping the script with rv run gives a nightly Pydantic AI or smolagents job both.",
    h1="Pydantic AI and smolagents", mode="wrap",
    intro="These libraries are a few hundred lines you call from a script. The script is what runs on cron, so the script is what gets wrapped; no callbacks are required for the basic detectors.",
    where="Wrap the script with <code>rv run</code> for MISSED, FAILED, STALLED, DRIFT and evidence. Add <code>run.tool()</code> calls from a tool wrapper if you want retry-storm and per-call cost.",
    key="An environment variable in the cron environment.",
    snippet=_pre('''# crontab
0 6 * * * rv run morning-digest --evidence-file /out/digest.md -- python digest.py

# digest.py (Pydantic AI); smolagents is the same shape
from pydantic_ai import Agent
agent = Agent("anthropic:claude-sonnet-5", system_prompt="...")
result = agent.run_sync("Summarise overnight changes")
open("/out/digest.md", "w").write(result.output)'''),
    silent="<ul><li>A script that raises exits non-zero and is FAILED with the stderr excerpt in the alert.</li><li>A script that writes an empty digest is NO_EVIDENCE.</li><li>Output size drifting from 6 KB to 300 bytes over a week is DRIFT, which is how a broken data source usually shows up first.</li></ul>"),
  dict(slug="dify-flowise", name="Dify and Flowise", group="Agent frameworks",
    title="Monitor scheduled Dify and Flowise workflows called from cron | RunVouch docs",
    desc="Dify and Flowise run workflows when something calls their API. Wrap the caller with rv run and report the run so a stopped scheduler or an empty answer gets an alert.",
    h1="Dify and Flowise", mode="wrap",
    intro="Both tools expose a workflow or chatflow over HTTP; the schedule lives outside them, in cron, n8n or a cloud scheduler. That outside caller is the thing that stops quietly.",
    where="Wrap the caller script with <code>rv run</code>; the script calls the Dify (<code>/v1/workflows/run</code>) or Flowise (<code>/api/v1/prediction/{id}</code>) endpoint and writes the answer to a file that serves as evidence.",
    key="An environment variable in the caller's environment; the Dify or Flowise API key stays where it is.",
    snippet=_pre('''# crontab
0 7 * * * rv run daily-brief --evidence-file /out/brief.json -- python call_dify.py

# call_dify.py
import json, os, requests
r = requests.post("https://api.dify.ai/v1/workflows/run", timeout=600,
    headers={"Authorization": f"Bearer {os.environ['DIFY_KEY']}"},
    json={"inputs": {"topic": "overnight"}, "response_mode": "blocking", "user": "cron"})
r.raise_for_status()
json.dump(r.json(), open("/out/brief.json", "w"))'''),
    silent="<ul><li>A workflow that returns 200 with an empty <code>outputs</code> is a success to the caller; the evidence file being empty is not.</li><li>Token usage is in the Dify response (<code>metadata.usage</code>); pass it as cost with <code>rv end</code> for the daily cap.</li></ul>"),
  dict(slug="ollama-local-llm", name="Ollama and local LLM batch jobs", group="Agent frameworks",
    title="Monitor nightly Ollama and local LLM batch jobs: stalls, drift, empty output | RunVouch docs",
    desc="Local models cost no API money, which is why nobody notices when the nightly job stalls on a swapped-out model or writes an empty file. rv run does.",
    h1="Ollama and local LLM batch jobs", mode="wrap",
    intro="With a local model the failure modes change: the process hangs while the model loads, the GPU is taken by another job, or a model update changes output length by half. None of them cost money, all of them cost the result.",
    where="Wrap the batch script with <code>rv run</code> and set <code>--max-runtime</code> on the agent so a hang becomes STALLED.",
    key="An environment variable in the cron environment.",
    snippet=_pre('''rv agent nightly-classify --cadence 24h --max-runtime 2h --evidence
0 1 * * * rv run nightly-classify --evidence-file /data/labels.jsonl -- python classify.py --model llama3.1'''),
    silent="<ul><li>A hang has no exit code; STALLED fires when max runtime passes without an end.</li><li>Output size drift (DRIFT) is the first sign a model update or a prompt change broke the pipeline.</li><li>Zero cost is fine; leave the cost caps unset and keep evidence and drift.</li></ul>"),
]

GROUPS = ["Schedulers", "Cloud functions", "Platforms", "Orchestrators", "No-code automation", "Agent frameworks"]
