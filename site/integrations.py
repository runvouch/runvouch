"""Integration pages: one per scheduler, platform or agent framework.

Every entry is written by hand from the platform's own documented behaviour; nothing here is generated
from a template of guesses. The parts that are the same everywhere (install, cadence, what RunVouch
detects) live in build.py so the page-specific part stays small and true.

Fields: slug, name, group, title, desc, h1, intro, where (how the job runs there), key (how to store
RUNVOUCH_KEY as a secret), snippet (HTML <pre>), silent (what fails silently on this platform, in the
platform's own terms), missing (what the platform itself does not tell you: 2 to 4 verifiable sentences), mode: "wrap" (rv run around a command) or "http" (the two HTTP calls, for
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
    h1="Kubernetes CronJob monitoring", mode="wrap",
    intro="Kubernetes CronJob monitoring, the way kubectl cannot do it: a CronJob that reports Succeeded tells you the pod exited 0. It does not tell you the schedule was missed (startingDeadlineSeconds), the job produced nothing, or an agent inside it called the same tool 400 times.",
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
    silent="<ul><li>The controller skips a run when it misses <code>startingDeadlineSeconds</code>; nothing pages you. RunVouch fires MISSED when cadence plus grace passes without a start.</li><li><code>successfulJobsHistoryLimit</code> keeps a few pods; a job that exits 0 with an empty output looks identical to a good one. <code>--evidence-file</code> makes the empty one FAILED with NO_EVIDENCE.</li><li>With <code>concurrencyPolicy: Allow</code> a slow run overlaps the next; STALLED (max runtime) catches the slow one.</li></ul>",
    missing="<p>The CronJob controller records <code>lastScheduleTime</code> and <code>lastSuccessfulTime</code> on the object and keeps a handful of finished pods, bounded by <code>successfulJobsHistoryLimit</code> and <code>failedJobsHistoryLimit</code> (defaults 3 and 1). There is no built-in notification: a schedule that stops firing, a job that exits 0 with nothing written, or a job killed by <code>activeDeadlineSeconds</code> only shows up if someone runs <code>kubectl get cronjob</code> and reads the timestamps. Alerting needs a separate stack (kube-state-metrics, Prometheus rules on <code>kube_cronjob_next_schedule_time</code>) that most clusters do not have wired for every job.</p>"),
  dict(slug="systemd-timers", name="systemd timers", group="Schedulers",
    title="Monitor systemd timers and services: missed timers, failed units | RunVouch docs",
    desc="Get alerted when a systemd timer stops firing or its service fails silently, including user timers. Wrap ExecStart with rv run.",
    h1="systemd timer monitoring", mode="wrap",
    intro="systemd timer monitoring from outside the machine: a timer that fires a failing service shows up in <code>systemctl --failed</code> and nowhere else. A timer that never fires (unit disabled, machine asleep, Persistent missing) shows up nowhere at all.",
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
    silent="<ul><li>Without <code>Persistent=true</code> a timer that was due while the machine was off is simply skipped.</li><li><code>OnFailure=</code> can start a notifier unit, but only on non-zero exit; a script that exits 0 with no output is never a failure to systemd.</li><li>User timers stop when the user session ends unless <code>loginctl enable-linger</code> is set; MISSED tells you the same evening, not when you next log in.</li></ul>",
    missing="<p><code>systemctl list-timers</code> shows the next and last trigger, and <code>journalctl -u</code> holds the output, but systemd sends nothing anywhere. <code>OnFailure=</code> can start a second unit, and only when the service exits non-zero. A oneshot that exits 0 after writing an empty file, a timer whose unit was masked during an upgrade, or a user timer that stopped when the session ended (no <code>loginctl enable-linger</code>) produces no signal you will see without logging in.</p>"),
  dict(slug="gitlab-ci-schedules", name="GitLab CI scheduled pipelines", group="Schedulers",
    title="Monitor GitLab CI scheduled pipelines: skipped schedules, green no-ops | RunVouch docs",
    desc="Catch GitLab pipeline schedules that stop running (owner token expired, schedule deactivated) or pass without producing the artifact. One job line.",
    h1="GitLab CI scheduled pipeline monitoring", mode="wrap",
    intro="GitLab CI scheduled pipeline monitoring for the failure GitLab does not report: pipeline schedules run as the user who created them. When that user leaves or the schedule is deactivated the pipeline silently stops, and a job that passes is not a job that did the work.",
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
    silent="<ul><li>A deactivated schedule, or one whose owner lost access to the project, stops without a notification. MISSED covers it.</li><li>Pipeline notifications fire on failure, not on \"passed but wrote nothing\"; <code>--evidence-file</code> does.</li><li>Retried jobs (<code>retry:</code>) can run an LLM step several times; the retry-storm and per-run cost cap see the repeats.</li></ul>",
    missing="<p>GitLab e-mails and integrations fire on pipeline status: failed, fixed, or success if you opt in. They never fire for a pipeline that did not run. A schedule owned by a user who was removed from the project, or a schedule that was deactivated by hand, stays in the list with its next-run time and simply never creates a pipeline. A job that passes with an empty artifact is a passed job.</p>"),
  dict(slug="jenkins", name="Jenkins", group="Schedulers",
    title="Monitor Jenkins scheduled builds: cron triggers that stop, green no-ops | RunVouch docs",
    desc="Alert when a Jenkins job with a cron trigger stops running or passes without its artifact, without touching Jenkins notifications.",
    h1="Jenkins scheduled build monitoring", mode="wrap",
    intro="Jenkins scheduled build monitoring for what a red ball cannot show: Jenkins tells you about red builds. It does not tell you a job has not been triggered for a week because the trigger was edited away, or that a green build's script exited 0 with an empty report.",
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
    silent="<ul><li>A disabled job or a removed trigger produces no notification; MISSED does.</li><li>Post-build e-mail fires on failure or unstable, never on \"passed, produced nothing\".</li><li>Queued builds that wait for an executor for hours are not late to Jenkins; STALLED and MISSED are measured against your cadence, not the queue.</li></ul>",
    missing="<p>Jenkins notifies on build result: failure, unstable, back to normal. A job that is disabled, whose <code>triggers { cron() }</code> block was removed in a Jenkinsfile change, or whose agent label no longer matches any node, sits in the queue or never enters it, and no build result is produced to notify about. Console output is kept per build; a build that printed nothing and exited 0 is a blue ball.</p>"),
  dict(slug="heroku-scheduler", name="Heroku Scheduler", group="Schedulers",
    title="Monitor Heroku Scheduler jobs: best-effort runs that never happened | RunVouch docs",
    desc="Heroku Scheduler is documented as best effort and can skip runs. RunVouch alerts when a scheduled dyno did not start or its task did nothing.",
    h1="Heroku Scheduler monitoring", mode="wrap",
    intro="Heroku Scheduler monitoring for the run Heroku skipped: Heroku's own documentation calls Scheduler a best-effort service, a run can be skipped without a trace. For a nightly agent that is exactly the failure you cannot see from the logs.",
    where="Scheduler starts a one-off dyno with the command you enter. Add <code>runvouch</code> to <code>requirements.txt</code> and prefix the command.",
    key="Set the key as a config var: <code>heroku config:set RUNVOUCH_KEY=rv_...</code>; one-off dynos inherit it.",
    snippet=_pre('''# Scheduler command field
rv run nightly-report --log /tmp/report.log -- python report.py
# cadence registered once, from anywhere with the key
rv agent nightly-report --cadence 24h --grace 30m --evidence'''),
    silent="<ul><li>Skipped runs are documented behaviour, not an error; MISSED is the only alert you will get.</li><li>One-off dynos have no persistent disk, so use <code>--log</code> (the log growing during the run counts as evidence) or report a URL that must return 200.</li></ul>",
    missing="<p>The Heroku Dev Center states that Scheduler is a best-effort service and that a scheduled job may occasionally not run; it recommends a custom clock process for anything that must run. A skipped run leaves no dyno, no log line and no notification. A one-off dyno that exits 0 with no output is indistinguishable in <code>heroku logs --ps scheduler</code> from one that did the work.</p>"),
  dict(slug="aws-lambda-eventbridge", name="AWS Lambda + EventBridge Scheduler", group="Cloud functions",
    title="Monitor scheduled AWS Lambda functions (EventBridge): disabled rules, silent success | RunVouch docs",
    desc="Alert when an EventBridge schedule stops invoking your Lambda, the function returns early without doing the work, or an LLM call inside it overspends.",
    h1="AWS Lambda scheduled function monitoring", mode="http",
    intro="AWS Lambda scheduled function monitoring without writing CloudWatch alarms: CloudWatch can alarm on errors and on invocation count, if you build those alarms. It cannot tell a function that returned in 200 ms because a feature flag was off from one that did the work.",
    where="Inside the handler, with the two HTTP calls (no binary needed). Python: <code>pip install runvouch</code> into the deployment package and use <code>runvouch.vouch()</code> as a context manager; any language: plain HTTPS.",
    key="Put the key in Secrets Manager or SSM Parameter Store and read it at cold start, or as an encrypted environment variable on the function.",
    snippet=_pre('''import os, runvouch
runvouch.agent("nightly-report", cadence_s=86400, grace_s=1800, evidence_required=True)

def handler(event, context):
    with runvouch.vouch("nightly-report", evidence=lambda: {"s3_object": wrote_object}) as run:
        wrote_object = build_report()   # your work
        run.tool("bedrock.invoke", {"model": "anthropic.claude-3"}, cost=0.02)'''),
    silent="<ul><li>A disabled or deleted schedule stops invocations; without a custom alarm on <code>Invocations == 0</code> nobody notices. MISSED notices.</li><li>Timeouts show as errors, but a function that catches everything and returns <code>{\"ok\": true}</code> is a success to Lambda. Evidence is what separates the two.</li><li>Retries (asynchronous invocation retries twice by default) can triple an LLM bill; the per-run cost cap and retry-storm detector see them as one agent.</li></ul>",
    missing="<p>EventBridge Scheduler counts invocations and failed invocations as metrics; nothing alerts unless you create a CloudWatch alarm per schedule, and an alarm on <code>Invocations == 0</code> needs the <code>TreatMissingData</code> setting right or it stays green on silence. A disabled schedule, a schedule whose IAM role lost <code>lambda:InvokeFunction</code>, or a function that catches every exception and returns 200, all look like success or like nothing at all.</p>"),
  dict(slug="google-cloud-scheduler", name="Google Cloud Scheduler", group="Cloud functions",
    title="Monitor Google Cloud Scheduler jobs (Cloud Run jobs, Cloud Functions) | RunVouch docs",
    desc="Alert when a Cloud Scheduler job stops firing, the Cloud Run job or function returns 2xx without doing the work, or an LLM step overspends.",
    h1="Google Cloud Scheduler monitoring", mode="wrap",
    intro="Google Cloud Scheduler monitoring beyond the status code: Cloud Scheduler counts an HTTP 2xx as success and retries on anything else. Everything that goes wrong inside a 2xx is yours to find.",
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
    silent="<ul><li>A paused scheduler job, or one whose service account lost <code>run.jobs.run</code>, fails on the scheduler side; the alerting policy for that is not created by default. MISSED needs no policy.</li><li>A function that returns 200 after catching an exception is a success to Scheduler and to Cloud Monitoring.</li><li>Scheduler retries plus function retries can run an agent several times an hour; the daily cost cap holds regardless.</li></ul>",
    missing="<p>Cloud Scheduler writes a log entry per attempt and a status per job in the console; it does not notify. A paused job, a job whose service account lost the invoke permission, or a job deleted with the project's Terraform state, disappears from the log without a line saying so. Cloud Monitoring alerting policies on <code>scheduler.googleapis.com/job/attempt_count</code> are possible but are not created by default.</p>"),
  dict(slug="azure-functions-timer", name="Azure Functions timer trigger", group="Cloud functions",
    title="Monitor Azure Functions timer triggers: stopped apps, silent success | RunVouch docs",
    desc="Alert when an Azure Functions timer trigger stops running (app stopped, scale-to-zero on Consumption) or completes without doing the work.",
    h1="Azure Functions timer trigger monitoring", mode="http",
    intro="Azure Functions timer trigger monitoring from outside Application Insights: a timer-triggered function that runs, catches its own exception and returns is a success in Application Insights. A function app that is stopped does not run at all, and no default alert says so.",
    where="Inside the function, with the Python client or the two HTTP calls. NCRONTAB schedule stays as it is.",
    key="Store the key in Key Vault and reference it from an app setting (<code>@Microsoft.KeyVault(SecretUri=...)</code>), or as a plain app setting for a first test.",
    snippet=_pre('''import azure.functions as func, runvouch
app = func.FunctionApp()

@app.timer_trigger(schedule="0 0 2 * * *", arg_name="timer")
def nightly_report(timer: func.TimerRequest):
    with runvouch.vouch("nightly-report", evidence=lambda: {"blob_written": ok}) as run:
        ok = build_report()'''),
    silent="<ul><li>On the Consumption plan the timer trigger runs on a scale controller; when the app is stopped or the storage account is unreachable, nothing fires and nothing alerts. MISSED does.</li><li><code>timer.past_due</code> tells your code a run was late; it does not tell you.</li><li>Application Insights availability tests cover HTTP endpoints, not whether a nightly job produced its output.</li></ul>",
    missing="<p>Application Insights records each execution and its result. It records nothing for an execution that did not happen: a stopped function app, a Consumption plan app whose storage account is unreachable (the timer trigger stores its schedule status in that storage), or a function that was removed in a deployment. The <code>IsPastDue</code> flag on the timer object is passed to your code and to nobody else.</p>"),
  dict(slug="cloudflare-workers-cron", name="Cloudflare Workers Cron Triggers", group="Cloud functions",
    title="Monitor Cloudflare Workers Cron Triggers: scheduled handlers that stop or no-op | RunVouch docs",
    desc="Two fetch() calls in your scheduled() handler give a Cloudflare Worker cron a dead man's switch, evidence and a cost cap.",
    h1="Cloudflare Workers Cron Trigger monitoring", mode="http",
    intro="Cloudflare Workers Cron Trigger monitoring where there is no exit code: a Worker's <code>scheduled()</code> handler has no output you can look at later and, on the free plan, a CPU time limit that ends a run mid-way without an error you will see.",
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
    silent="<ul><li>A cron trigger removed from <code>wrangler.toml</code> on the next deploy stops silently; MISSED is the only signal.</li><li>Exceeding CPU time kills the invocation; the start call already happened, so RunVouch marks the run STALLED when it never ends.</li><li>An <code>await</code> that is not wrapped in <code>ctx.waitUntil</code> can be cut off; put the end call in <code>waitUntil</code> as above.</li></ul>",
    missing="<p>The Cloudflare dashboard lists past cron invocations per Worker with a status and duration; there is no notification when an invocation fails, is cut off by the CPU limit, or stops being scheduled because the <code>[triggers]</code> block was dropped from <code>wrangler.toml</code> in a deploy. Console output is only kept if you enable Workers Logs or tail the Worker live.</p>"),
  dict(slug="vercel-cron", name="Vercel Cron Jobs", group="Cloud functions",
    title="Monitor Vercel Cron Jobs: routes that return 200 and do nothing | RunVouch docs",
    desc="Vercel cron calls a route and records the status code. RunVouch adds the missing part: did the route do the work, on time, within budget.",
    h1="Vercel cron monitoring", mode="http",
    intro="Vercel cron monitoring for the part Vercel leaves to you: a cron entry in <code>vercel.json</code> hits a route on a schedule and logs the status code. A route that returns 200 after an early return is a success; a function that hits its duration limit is a log line; a run that never started is nothing at all.",
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
    silent="<ul><li>Cron jobs only run on production; a preview deployment that looks fine never runs them. MISSED on the production agent is what tells you the schedule is not live.</li><li>The Hobby plan runs crons once a day at most and may run them within the hour, not at the minute; set grace accordingly.</li><li>Function duration limits end a run without a 5xx you will act on; STALLED covers a start without an end.</li></ul>",
    missing="<p>Vercel's documentation is explicit: Vercel will not retry an invocation if a cron job fails, and cron delivery is best effort, so a scheduled run can be skipped by a transient error, in which case no runtime log is created for it. There is no failure notification; errors are found through the View Logs button on the Cron Jobs settings page. On Hobby, a cron may run at any point within the scheduled hour. An Instant Rollback does not update the crons, so the schedule can keep calling the old routes.</p>"),
  dict(slug="supabase-pg-cron", name="Supabase (pg_cron + Edge Functions)", group="Cloud functions",
    title="Monitor Supabase pg_cron jobs and scheduled Edge Functions | RunVouch docs",
    desc="pg_cron fires an HTTP call through pg_net and forgets it. RunVouch tells you whether the Edge Function ran, finished and produced its result.",
    h1="Supabase pg_cron monitoring", mode="http",
    intro="Supabase pg_cron monitoring where the database cannot see the result: the documented pattern is <code>cron.schedule()</code> calling <code>net.http_post()</code> to an Edge Function. pg_net is fire-and-forget: a function that never ran, or ran and failed, leaves only a row in <code>net._http_response</code> that nobody reads.",
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
    silent="<ul><li>pg_cron runs inside the database; a paused project or a dropped job produces no alert. MISSED does.</li><li>pg_net records the HTTP response in a table and nothing else happens on a 500.</li><li>Edge Functions have a wall-clock limit; a function that is cut off started a run and never ended it, which is STALLED.</li></ul>",
    missing="<p>pg_cron records each attempt in <code>cron.job_run_details</code>, including the status of the SQL statement; for a <code>net.http_post()</code> call that status is succeeded as soon as the request was queued, before the Edge Function did anything. The HTTP result lands in <code>net._http_response</code> and is deleted after a short retention. Supabase does not alert on either table, and a paused project stops pg_cron together with everything else.</p>"),
  dict(slug="render-cron", name="Render Cron Jobs", group="Platforms",
    title="Monitor Render Cron Jobs: missed runs and green no-ops | RunVouch docs",
    desc="Wrap a Render cron job command with rv run to get MISSED, FAILED, NO_EVIDENCE and cost alerts, without adding a service.",
    h1="Render cron job monitoring", mode="wrap",
    intro="Render cron job monitoring beyond the dashboard: Render shows each cron run's log and exit status. It does not page you when runs stop, and exit 0 with an empty output is a success.",
    where="The Cron Job service's command field. The build installs <code>runvouch</code> from <code>requirements.txt</code>.",
    key="Environment tab of the cron job service: <code>RUNVOUCH_KEY</code>. Environment groups work too.",
    snippet=wrap_snippet("nightly-report", "python report.py", before="# Render cron job command\n", evidence="--log /tmp/report.log"),
    silent="<ul><li>A suspended service, or a cron job whose schedule was edited, stops without notification.</li><li>Cron jobs on Render have no persistent disk by default; use <code>--log</code> or URL evidence rather than a file that must survive the run.</li></ul>",
    missing="<p>Render shows each cron job's runs with start time, duration and exit code in the dashboard, and sends failure notifications for deploys, not for cron runs. A suspended service, a cron job whose schedule was changed, or a build that failed and left the previous command in place, shows as an absence in the run list that nobody is watching.</p>"),
  dict(slug="railway-cron", name="Railway cron schedules", group="Platforms",
    title="Monitor Railway cron schedules: services that stop running or do nothing | RunVouch docs",
    desc="Railway runs a service on a cron schedule and shows the logs. RunVouch adds the dead man's switch, evidence check and cost cap.",
    h1="Railway cron schedule monitoring", mode="wrap",
    intro="Railway cron schedule monitoring for the run that did not happen: a Railway service with a cron schedule starts, runs its start command and exits. The dashboard shows it happened; nothing tells you when it stops happening.",
    where="The service's start command. Railway expects the process to exit when done; <code>rv run</code> exits with the wrapped command's code.",
    key="Service Variables: <code>RUNVOUCH_KEY</code>. Shared variables work across services.",
    snippet=wrap_snippet("nightly-report", "python report.py", before="# Railway start command\n", evidence="--log /tmp/report.log"),
    silent="<ul><li>Railway documents that a cron run is skipped if the previous execution is still running; that is a MISSED in RunVouch terms and a STALLED for the one still going.</li><li>Deploy failures stop the schedule with the service; MISSED covers both.</li></ul>",
    missing="<p>Railway's cron documentation states that a scheduled execution is skipped when the previous one is still running, and that the process must exit on its own. Both cases are visible only in the deployment logs. There is no notification for a skipped execution, a crashed start command, or a schedule removed from the service settings.</p>"),
  dict(slug="fly-io", name="Fly.io scheduled Machines", group="Platforms",
    title="Monitor Fly.io scheduled Machines and cron in containers | RunVouch docs",
    desc="Fly.io has no cron service; scheduled Machines and in-container cron both need an outside watchdog. rv run gives them one.",
    h1="Fly.io scheduled Machine monitoring", mode="wrap",
    intro="Fly.io scheduled Machine monitoring from outside the Machine: on Fly you either run a Machine with a schedule (<code>fly machine run --schedule daily</code>) or run cron (often supercronic) inside a long-lived Machine. Both stop when the Machine is destroyed, stuck or out of memory, and neither tells you.",
    where="The Machine's command, or the crontab line inside the container. The image needs Python 3 for <code>rv</code>.",
    key="<code>fly secrets set RUNVOUCH_KEY=rv_...</code>; secrets are exposed as environment variables in every Machine of the app.",
    snippet=_pre('''# scheduled Machine (runs once per schedule, then stops)
fly machine run ghcr.io/you/report:latest --schedule daily \\
  --command "rv run nightly-report --log /tmp/report.log -- python report.py"

# or, inside a long-lived Machine with supercronic
0 2 * * * rv run nightly-report --evidence-file /data/report.html -- python /app/report.py'''),
    silent="<ul><li>Scheduled Machines run \"approximately\" at the interval; use a grace of an hour or more.</li><li>An OOM-killed Machine restarts (or does not); the run that was in flight never ends and becomes STALLED.</li><li>A Machine that was stopped by <code>fly scale count 0</code> or a failed deploy takes the cron with it; MISSED is the signal.</li></ul>",
    missing="<p>Fly documents that scheduled Machines are started approximately on the schedule and that Fly does not run a cron service; the schedule is a Machine property that stops existing with the Machine. There is no notification for a Machine that failed to start, was OOM-killed mid-run, or was scaled to zero. <code>fly logs</code> is the only record and only for as long as the log retention.</p>"),
  dict(slug="docker-cron", name="Cron inside Docker (supercronic, crond)", group="Platforms",
    title="Monitor cron inside Docker containers: supercronic, crond, ofelia | RunVouch docs",
    desc="Cron in a container dies with the container and logs to nowhere. Wrap each line with rv run so you learn about it before the next morning.",
    h1="Cron in Docker monitoring", mode="wrap",
    intro="Cron in Docker monitoring for the two failures every container cron shares: whether you use supercronic, BusyBox crond or ofelia, a scheduled command inside a container either does not run because the container is not running, or runs and produces nothing.",
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
    silent="<ul><li>BusyBox crond inside a container does not load the container's environment for the job by default; if the job cannot see <code>RUNVOUCH_KEY</code>, <code>rv</code> fails open and runs the job unmonitored. Test with <code>docker exec ... rv status</code>.</li><li>A container restart loop means no cron ticks; MISSED after cadence plus grace.</li><li>Logs go to the cron daemon's stdout at best; <code>--log</code> keeps the job's output as evidence.</li></ul>",
    missing="<p>A cron daemon inside a container writes to its own stdout at best (supercronic) or to nowhere (BusyBox crond without <code>-f -l</code>). Docker reports container health only if a <code>HEALTHCHECK</code> is defined, and a healthy cron container is one where the daemon process exists, not one where the jobs ran. A restart loop, a wrong timezone in the image, or a job that cannot see its environment variables produces no signal outside <code>docker logs</code>.</p>"),
  # ───────────── orchestrators ─────────────
  dict(slug="airflow", name="Apache Airflow", group="Orchestrators",
    title="Monitor Airflow DAGs for silent success and empty outputs | RunVouch docs",
    desc="Airflow alerts on task failure and SLA misses. RunVouch adds what a green DAG run cannot prove: the output exists, the run was on time, the LLM tasks stayed under budget.",
    h1="Airflow DAG monitoring", mode="wrap",
    intro="Airflow DAG monitoring for what a green DAG run cannot prove: Airflow is very good at telling you a task failed. A task that succeeds with an empty DataFrame, a DAG that is paused, or a scheduler that stopped scheduling all look like silence.",
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
    silent="<ul><li>A paused DAG (or one that failed to import after a bad deploy) schedules nothing; the DAG import error banner is not an alert. MISSED is.</li><li><code>sla_miss_callback</code> only fires when the scheduler is healthy enough to notice.</li><li>A task with <code>retries=3</code> around an LLM call is a retry storm with a budget; the per-run cost cap ends it.</li></ul>",
    missing="<p>Airflow's <code>on_failure_callback</code>, e-mail on failure and SLA misses all need a task instance that ran or was scheduled. A DAG that failed to import after a deploy shows a red banner in the UI and creates no task instances; a paused DAG creates none either; a scheduler that is down creates none for any DAG. The scheduler's own health check is an HTTP endpoint you have to poll yourself.</p>"),
  dict(slug="prefect", name="Prefect", group="Orchestrators",
    title="Monitor Prefect deployments: Late runs, missing workers, empty results | RunVouch docs",
    desc="Prefect marks runs Late when no worker picks them up. RunVouch pages you about it, checks the flow produced its result, and caps LLM spend per run.",
    h1="Prefect deployment monitoring", mode="wrap",
    intro="Prefect deployment monitoring for the run that stays Late: a Prefect deployment with a schedule creates flow runs; a worker on the right work pool executes them. When the worker is gone, runs pile up as Late and Scheduled, and the flow's own failure hooks never fire because nothing failed.",
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
    silent="<ul><li>Late runs are visible in the UI and in automations you have to create; RunVouch's MISSED needs neither.</li><li>A flow that completes with an empty result is Completed; evidence separates it from a good run.</li><li>Prefect task retries multiply LLM calls; the retry-storm detector sees identical tool inputs across retries.</li></ul>",
    missing="<p>Prefect shows Late runs in the UI and can notify through an Automation, if you create one with the right trigger and a notification block. Without that, a work pool with no worker, a worker whose process died, or a deployment whose schedule was set inactive, produces a growing list of Scheduled runs and no message. A flow that completes with an empty result is Completed.</p>"),
  dict(slug="dagster", name="Dagster", group="Orchestrators",
    title="Monitor Dagster schedules and sensors: daemon down, green no-ops | RunVouch docs",
    desc="Dagster schedules stop when the daemon stops. RunVouch alerts on the missing run, checks the asset was actually produced, and caps LLM cost per run.",
    h1="Dagster schedule monitoring", mode="wrap",
    intro="Dagster schedule monitoring for the daemon nobody watches: schedules and sensors in Dagster are executed by the dagster-daemon. When it is down, unhealthy or pointed at a stale code location, nothing runs and the UI shows a status you have to go and look at.",
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
    silent="<ul><li>A stopped daemon or a schedule left in the Stopped state after a redeploy produces no runs; MISSED after cadence plus grace.</li><li>An asset materialised with zero rows is a successful materialisation; evidence is the check.</li><li>Run retries (<code>max_retries</code>) re-execute LLM ops; the per-run cost cap holds across the retry.</li></ul>",
    missing="<p>The Dagster UI shows daemon health on the Deployment page and marks a schedule as running or stopped; run failure hooks and alert policies (Dagster+) fire on runs that exist. A daemon that is not running, a schedule that came back Stopped after a redeploy, or a code location that failed to load, all result in no run and therefore no failure to alert on.</p>"),
  dict(slug="celery-beat", name="Celery beat", group="Orchestrators",
    title="Monitor Celery beat periodic tasks: beat down, workers gone, tasks that no-op | RunVouch docs",
    desc="Celery beat schedules; workers execute. When either is gone, periodic tasks silently stop. RunVouch alerts on the missing run and on tasks that finish without their result.",
    h1="Celery beat monitoring", mode="wrap",
    intro="Celery beat monitoring for a process with no watchdog: Celery beat is a single process that publishes tasks on a schedule. If it dies, or a worker for that queue is not running, tasks are late or never run, and Flower will not page you.",
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
    silent="<ul><li>Beat down means no task is even published; MISSED is the only external signal.</li><li>A task that is published but never consumed (wrong queue, no worker) is neither failed nor succeeded; it is a MISSED start.</li><li><code>max_retries</code> around an LLM call repeats the spend; the per-run cost cap and retry-storm detector cover it.</li></ul>",
    missing="<p>Celery has no notification of its own. Flower shows workers and tasks it has seen; a task that beat never published because beat is down does not appear anywhere, and a task published to a queue no worker consumes sits in the broker as a message. Task-level failure handling (<code>on_failure</code>, <code>task_failure</code> signal) requires the task to have started.</p>"),
  dict(slug="apscheduler", name="APScheduler (in-process)", group="Orchestrators",
    title="Monitor APScheduler and node-cron jobs: schedulers that die with the process | RunVouch docs",
    desc="In-process schedulers (APScheduler, node-cron, node-schedule) stop when the process stops. RunVouch notices from outside.",
    h1="APScheduler monitoring", mode="wrap",
    intro="APScheduler monitoring from outside the process it lives in: APScheduler runs inside your application process. When that process is restarted at the wrong moment, crashes or is scaled to zero, the schedule goes with it and nothing outside knows.",
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
    silent="<ul><li>A job missed while the process was down is dropped after <code>misfire_grace_time</code>; with the default (1 second in APScheduler 3) it is dropped almost always.</li><li>Two replicas of the process run the job twice; RunVouch shows both runs under one agent, and the daily cost cap counts both.</li><li>A process stuck on a lock still looks alive to the orchestrator; STALLED catches the run that never ends.</li></ul>",
    missing="<p>APScheduler emits events (<code>EVENT_JOB_ERROR</code>, <code>EVENT_JOB_MISSED</code>) that your code can listen to, inside the same process that may be the thing that died. A job that was due while the process was down is dropped when <code>misfire_grace_time</code> passes, and in APScheduler 3 that default is one second. Nothing is persisted unless you configure a job store, and nothing is sent anywhere unless you write the listener.</p>"),
  dict(slug="temporal", name="Temporal Schedules", group="Orchestrators",
    title="Monitor Temporal Schedules and workflows: no workers polling, silent completion | RunVouch docs",
    desc="Temporal guarantees the workflow will eventually run. RunVouch tells you it did not run on time, and that it produced what it was supposed to.",
    h1="Temporal Schedule monitoring", mode="wrap",
    intro="Temporal Schedule monitoring for eventually: a Temporal Schedule starts workflows on time; a worker polling the task queue executes them. With no worker, workflow tasks wait in the queue indefinitely with no error, because from Temporal's point of view nothing is wrong yet.",
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
    silent="<ul><li>No worker on the task queue means the schedule fires and the work waits; the schedule's own counters say \"running\". MISSED and STALLED both apply.</li><li>Activity retries are unlimited by default; an LLM activity that keeps failing keeps spending. The per-run cap ends it.</li><li>Overlap policy Skip drops a start; that is a MISSED you would otherwise not see.</li></ul>",
    missing="<p>Temporal's Schedule keeps counters of actions taken and skipped and the Web UI shows workflow status; there is no built-in notification for a workflow that has been Running for hours because no worker is polling, or for a Schedule whose overlap policy skipped a start. Workflow timeouts (<code>execution_timeout</code>) turn a stuck workflow into a failure only if you set them.</p>"),
  dict(slug="windmill", name="Windmill", group="Orchestrators",
    title="Monitor Windmill scheduled scripts and flows | RunVouch docs",
    desc="Windmill schedules scripts and flows and shows their runs. RunVouch adds an outside dead man's switch, evidence and an LLM cost cap.",
    h1="Windmill schedule monitoring", mode="wrap",
    intro="Windmill schedule monitoring from outside the instance: Windmill has error handlers and a runs page. It does not have an outside party that notices the whole instance, or one worker group, has stopped taking jobs.",
    where="Inside the script (Python or Bash) with the client or <code>rv run</code>; Windmill scripts can shell out.",
    key="A Windmill variable marked secret, read with <code>wmill.get_variable(\"u/you/runvouch_key\")</code>, or a worker environment variable.",
    snippet=_pre('''# Python script scheduled in Windmill
import os, wmill, runvouch
os.environ["RUNVOUCH_KEY"] = wmill.get_variable("u/you/runvouch_key")

def main():
    with runvouch.vouch("nightly-report", evidence=lambda: {"rows": n > 0}) as run:
        n = build_report(run)
    return {"rows": n}'''),
    silent="<ul><li>A disabled schedule, or a worker group with zero workers, queues jobs without an error.</li><li>Flow error handlers fire on failure; a flow that completes with an empty result does not fail.</li></ul>",
    missing="<p>Windmill's error handler (per schedule, per flow, or workspace-wide) runs when a job errors. A schedule that was disabled, a worker group scaled to zero so jobs stay queued, or an instance that is down, produces no errored job for the handler to react to. The queue depth is visible on the runs page and in the instance metrics, if you look.</p>"),
  # ───────────── no-code automation ─────────────
  dict(slug="make", name="Make (Integromat)", group="No-code automation",
    title="Monitor Make scenarios: deactivated after errors, runs that do nothing | RunVouch docs",
    desc="Make turns a scenario off after repeated errors and e-mails you once. RunVouch keeps watching: missed runs, empty runs, LLM cost per run.",
    h1="Make scenario monitoring", mode="http",
    intro="Make scenario monitoring after the deactivation e-mail: a Make scenario on a schedule runs until Make deactivates it after consecutive errors, or until someone toggles it off. The deactivation e-mail is easy to miss, and a scenario that runs with zero bundles is a normal run.",
    where="Two HTTP modules in the scenario: one at the start, one at the end, with the API's JSON.",
    key="Store the key in a Make connection or as a scenario variable; put it in the <code>X-API-Key</code> header of both HTTP modules.",
    snippet=http_snippet("lead-enricher", "make"),
    silent="<ul><li>Auto-deactivation after errors is documented Make behaviour; the scenario does not run again until you re-enable it. MISSED tells you the same hour.</li><li>Zero bundles processed is a successful run in the history; report <code>evidence: {\"bundles\": count &gt; 0}</code> from the end module.</li><li>Operations consumed by an OpenAI module are visible per run in Make; passing the cost into the end call makes the daily cap work.</li></ul>",
    missing="<p>Make sends one e-mail when it deactivates a scenario after consecutive errors and shows warnings in the scenario list; it does not repeat the warning, and it sends nothing for a scenario someone switched off. Scenario history keeps each execution with its operations count; an execution that processed zero bundles is a successful execution with a small number.</p>"),
  dict(slug="zapier", name="Zapier", group="No-code automation",
    title="Monitor Zapier Zaps: turned off after errors, Schedule by Zapier that stops | RunVouch docs",
    desc="Zapier pauses a Zap after too many errors and can hold tasks. RunVouch alerts when a scheduled Zap stops running or completes without doing the work.",
    h1="Zapier Zap monitoring", mode="http",
    intro="Zapier Zap monitoring beyond Zap History: a Zap with a Schedule by Zapier trigger runs until Zapier turns it off (repeated errors, a disconnected app, a plan limit). Zap History shows what happened; it does not call you.",
    where="Two Webhooks by Zapier steps (POST, JSON), one right after the trigger and one at the end.",
    key="Paste the key in the header field of both webhook steps, or keep it in a Storage by Zapier value.",
    snippet=http_snippet("weekly-digest", "zapier"),
    silent="<ul><li>Zapier turning a Zap off, and held tasks when a plan limit is reached, are both silent until you open Zap History.</li><li>Filter steps that stop a run early are successful runs; only the end call with evidence distinguishes them.</li></ul>",
    missing="<p>Zapier e-mails you when it turns a Zap off after a high error ratio and when a connected account needs re-authorizing; both are single e-mails to the account owner. Held tasks (plan limit reached) and a Zap paused by a teammate are only visible in Zap History and the Zap list. A run stopped by a Filter step counts as a successful run with the label Filtered.</p>"),
  dict(slug="home-assistant", name="Home Assistant automations", group="No-code automation",
    title="Monitor Home Assistant scheduled automations and shell commands | RunVouch docs",
    desc="Time-triggered Home Assistant automations that call scripts or LLM services can stop or no-op after an update. RunVouch notices from outside the house.",
    h1="Home Assistant automation monitoring", mode="http",
    intro="Home Assistant automation monitoring from outside the house: an automation with a time trigger that runs a <code>shell_command</code> or a conversation agent keeps working until an update breaks the integration or the automation is left disabled. The logbook records it; nobody reads the logbook.",
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
    silent="<ul><li>Disabled automations and broken integrations after a core update do not notify; MISSED does.</li><li>A shell command that exits non-zero is a warning in the log, not an alert.</li></ul>",
    missing="<p>Home Assistant writes automation triggers to the logbook and shows the last triggered time on each automation; a persistent notification appears for some integration failures after a core update, and for nothing else. A disabled automation, a <code>shell_command</code> that exits non-zero (logged as a warning), or a time trigger that did not fire because the instance was restarting, produces no alert unless you build one. The reverse direction also works: the <a href=\"https://github.com/runvouch/runvouch/tree/main/integrations/home-assistant\">RunVouch REST sensor package</a> shows each agent's state as an entity so you can automate on it.</p>"),
  # ───────────── agent frameworks ─────────────
  dict(slug="langgraph", name="LangGraph", group="Agent frameworks",
    title="Monitor scheduled LangGraph agents: loops, cost per run, missing output | RunVouch docs",
    desc="A LangGraph graph on a schedule can loop on a tool, overspend, or finish without its artifact. Wrap the run and report each tool call for retry-storm and cost detection.",
    h1="LangGraph scheduled agent monitoring", mode="wrap",
    intro="LangGraph scheduled agent monitoring for the cycle that never converges: LangGraph gives you cycles by design. A cycle that never converges, on a nightly schedule, is a bill. LangSmith shows you the trace afterwards; RunVouch stops the run when it crosses the cap.",
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
    silent="<ul><li>Cycles with a high recursion limit look like progress; 40 identical tool inputs in one run is RETRY_STORM.</li><li>A graph that ends with an empty final state is a completed run; evidence says whether the digest exists.</li><li>Nothing in LangGraph knows the schedule; MISSED comes from the agent's cadence.</li></ul>",
    missing="<p>LangGraph raises <code>GraphRecursionError</code> when the recursion limit (default 25 steps) is reached; anything below that limit is a normal run, and the limit is often raised in exactly the graphs that loop. LangSmith tracing records every step for inspection after the fact and can alert on error rate and latency; it does not know the graph was supposed to run tonight, and it does not stop a run mid-way.</p>"),
  dict(slug="crewai", name="CrewAI", group="Agent frameworks",
    title="Monitor scheduled CrewAI crews: runaway iterations, cost caps, evidence | RunVouch docs",
    desc="Wrap crew.kickoff() with RunVouch to cap cost per run, detect a crew looping on a tool and confirm the deliverable exists.",
    h1="CrewAI scheduled crew monitoring", mode="wrap",
    intro="CrewAI scheduled crew monitoring for the partial answer: a crew has <code>max_iter</code> per agent and <code>max_rpm</code>; neither is a budget. A nightly crew that keeps re-planning burns tokens until the iteration limit, then returns whatever it has.",
    where="Around <code>crew.kickoff()</code> with the Python client, plus <code>run.tool()</code> from a step callback for loop detection.",
    key="An environment variable on the host or container that runs the crew.",
    snippet=_pre('''import runvouch
from crewai import Crew

def on_step(step):
    run.tool(step.tool or "llm", {"input": step.tool_input or ""}, cost=getattr(step, "cost", 0))

crew = Crew(agents=[...], tasks=[...], step_callback=on_step)
with runvouch.vouch("weekly-competitor-brief", evidence=lambda: {"brief": len(out.raw) > 500}) as run:
    out = crew.kickoff()'''),
    silent="<ul><li>Reaching <code>max_iter</code> is not an error; the crew returns a partial answer. Evidence (length, file, URL) is what fails it.</li><li>Per-agent token usage is available in <code>crew.usage_metrics</code>; pass it as cost so the daily cap works.</li></ul>",
    missing="<p>CrewAI reports token usage per crew run in <code>usage_metrics</code> and stops an agent at <code>max_iter</code> by returning its best answer so far, without raising. There is no built-in budget, no notion of a schedule, and no notification; the crew's verbose log is printed to the console of whatever started it.</p>"),
  dict(slug="autogen", name="AutoGen", group="Agent frameworks",
    title="Monitor scheduled AutoGen agents: conversations that never terminate, cost per run | RunVouch docs",
    desc="Multi-agent chats in AutoGen can run to max_turns without producing the result. RunVouch caps the run, detects loops and checks the output.",
    h1="AutoGen scheduled agent monitoring", mode="wrap",
    intro="AutoGen scheduled agent monitoring for the chat that keeps agreeing to continue: two AutoGen agents that keep agreeing to continue, or a tool that keeps failing and being retried by the assistant, look exactly like work until the bill arrives.",
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
    silent="<ul><li><code>max_turns</code> is a ceiling, not an alarm; hitting it every night is invisible without evidence.</li><li>Repeated identical tool executions are RETRY_STORM once reported.</li></ul>",
    missing="<p>AutoGen ends a team run on a termination condition or at <code>max_turns</code>, and returns the message history either way; reaching the turn limit is a normal stop reason, not an error. Usage is available per message in the result. Nothing in AutoGen knows when the run was supposed to happen or whether the result was used.</p>"),
  dict(slug="openai-agents-sdk", name="OpenAI Agents SDK", group="Agent frameworks",
    title="Monitor scheduled OpenAI Agents SDK runs: max_turns, cost, evidence | RunVouch docs",
    desc="Wrap Runner.run() with RunVouch for a per-run cost cap, retry-storm detection on tool calls and a check that the agent produced its output.",
    h1="OpenAI Agents SDK scheduled run monitoring", mode="wrap",
    intro="OpenAI Agents SDK scheduled run monitoring below the turn limit: the Agents SDK stops a run at <code>max_turns</code> and raises. Everything below that limit, including a run that spent $30 calling the same function, is a normal completion.",
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
    silent="<ul><li>Tracing in the OpenAI dashboard is after the fact; the cost cap acts during the run.</li><li>A final output that is an apology is a completed run; evidence is a length or a file, not a status.</li></ul>",
    missing="<p>The Agents SDK raises <code>MaxTurnsExceeded</code> at the turn limit and sends traces to the OpenAI dashboard, where you can read them afterwards. Token usage is on the run result. There is no budget, no schedule awareness and no alerting in the SDK; a final output that is an apology is a completed run.</p>"),
  dict(slug="pydantic-ai", name="Pydantic AI and smolagents", group="Agent frameworks",
    title="Monitor scheduled Pydantic AI and smolagents runs | RunVouch docs",
    desc="Lightweight agent libraries have no scheduler and no budget. Wrapping the script with rv run gives a nightly Pydantic AI or smolagents job both.",
    h1="Pydantic AI and smolagents scheduled run monitoring", mode="wrap",
    intro="Pydantic AI and smolagents scheduled run monitoring at the script level: these libraries are a few hundred lines you call from a script. The script is what runs on cron, so the script is what gets wrapped; no callbacks are required for the basic detectors.",
    where="Wrap the script with <code>rv run</code> for MISSED, FAILED, STALLED, DRIFT and evidence. Add <code>run.tool()</code> calls from a tool wrapper if you want retry-storm and per-call cost.",
    key="An environment variable in the cron environment.",
    snippet=_pre('''# crontab
0 6 * * * rv run morning-digest --evidence-file /out/digest.md -- python digest.py

# digest.py (Pydantic AI); smolagents is the same shape
from pydantic_ai import Agent
agent = Agent("anthropic:claude-sonnet-5", system_prompt="...")
result = agent.run_sync("Summarise overnight changes")
open("/out/digest.md", "w").write(result.output)'''),
    silent="<ul><li>A script that raises exits non-zero and is FAILED with the stderr excerpt in the alert.</li><li>A script that writes an empty digest is NO_EVIDENCE.</li><li>Output size drifting from 6 KB to 300 bytes over a week is DRIFT, which is how a broken data source usually shows up first.</li></ul>",
    missing="<p>Both libraries return a result object with usage counts and raise on hard errors; Pydantic AI can send spans to Logfire if you configure it. Neither has a schedule, a budget, or a notion of whether the output was written anywhere. What runs them is cron, and cron's only failure channel is local mail that nobody reads.</p>"),
  dict(slug="dify-flowise", name="Dify and Flowise", group="Agent frameworks",
    title="Monitor scheduled Dify and Flowise workflows called from cron | RunVouch docs",
    desc="Dify and Flowise run workflows when something calls their API. Wrap the caller with rv run and report the run so a stopped scheduler or an empty answer gets an alert.",
    h1="Dify and Flowise scheduled workflow monitoring", mode="wrap",
    intro="Dify and Flowise scheduled workflow monitoring where the schedule lives outside the tool: both expose a workflow or chatflow over HTTP; the schedule lives in cron, n8n or a cloud scheduler. That outside caller is the thing that stops quietly.",
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
    silent="<ul><li>A workflow that returns 200 with an empty <code>outputs</code> is a success to the caller; the evidence file being empty is not.</li><li>Token usage is in the Dify response (<code>metadata.usage</code>); pass it as cost with <code>rv end</code> for the daily cap.</li></ul>",
    missing="<p>Dify and Flowise keep a log of API calls and workflow runs in their own UI, with status and usage per run. They cannot record a call that never came. A caller that stopped, a 200 with empty <code>outputs</code>, or a chatflow that answered with a refusal, are all successful runs in that log.</p>"),
  dict(slug="ollama-local-llm", name="Ollama and local LLM batch jobs", group="Agent frameworks",
    title="Monitor nightly Ollama and local LLM batch jobs: stalls, drift, empty output | RunVouch docs",
    desc="Local models cost no API money, which is why nobody notices when the nightly job stalls on a swapped-out model or writes an empty file. rv run does.",
    h1="Ollama nightly batch job monitoring", mode="wrap",
    intro="Ollama nightly batch job monitoring where nothing costs money: with a local model the failure modes change. The process hangs while the model loads, the GPU is taken by another job, or a model update changes output length by half. None of them cost money, all of them cost the result.",
    where="Wrap the batch script with <code>rv run</code> and set <code>--max-runtime</code> on the agent so a hang becomes STALLED.",
    key="An environment variable in the cron environment.",
    snippet=_pre('''rv agent nightly-classify --cadence 24h --max-runtime 2h --evidence
0 1 * * * rv run nightly-classify --evidence-file /data/labels.jsonl -- python classify.py --model llama3.1'''),
    silent="<ul><li>A hang has no exit code; STALLED fires when max runtime passes without an end.</li><li>Output size drift (DRIFT) is the first sign a model update or a prompt change broke the pipeline.</li><li>Zero cost is fine; leave the cost caps unset and keep evidence and drift.</li></ul>",
    missing="<p>Ollama logs requests to its server log and returns per-request timings in the API response; there is no job history, no notion of a schedule and no alerting. A request that blocks while a model is loaded onto a busy GPU has no timeout unless the client sets one, and a model pulled to a new version answers with a different length without saying so.</p>"),
  dict(slug="n8n", name="n8n (community node)", group="No-code automation",
    title="Monitor n8n scheduled workflows with the RunVouch community node: missed schedules, green runs without output | RunVouch docs",
    desc="Install n8n-nodes-runvouch from Settings, Community Nodes. Start Run and End Run with evidence, or one Heartbeat node; alerts when the Schedule Trigger stops or the workflow runs and does nothing.",
    h1="n8n workflows", mode="http",
    intro="An n8n Error Workflow fires when a node errors. It stays quiet when the Schedule Trigger stops firing, when the instance is down, and when the workflow runs, finds nothing and exits green. The community forum thread on cron job monitoring asks for exactly that alert.",
    where="Install the community node <code>n8n-nodes-runvouch</code> (Settings, Community Nodes, Install) and drop two RunVouch nodes in the workflow: <b>Start Run</b> right after the Schedule Trigger, <b>End Run</b> at the end with status and evidence. <b>Heartbeat</b> does both in one node when you only need the dead man's switch. Source and example workflow: <a href=\"https://github.com/runvouch/runvouch/tree/main/integrations/n8n-nodes-runvouch\">integrations/n8n-nodes-runvouch</a>. Without the node, two HTTP Request nodes do the same:",
    key="A RunVouch API credential in n8n (Credentials, Add, RunVouch API); the node sets the <code>X-API-Key</code> header. With plain HTTP Request nodes, a header credential.",
    snippet=_pre('''# node "RunVouch Start": operation Start Run, agent lead-enricher, expected every 60 min, grace 15 min
# node "RunVouch End":   operation End Run, run ID {{ $("RunVouch Start").item.json.run_id }},
#                        status ok, evidence {{ { "leads_fetched": $json.count > 0 } }}

# the same with HTTP Request nodes
POST https://api.runvouch.com/v1/runs/start   {"agent":"lead-enricher","source":"n8n"}
POST https://api.runvouch.com/v1/runs/end     {"run_id":"...","status":"ok","evidence":{"leads_fetched":true}}'''),
    silent="<ul><li>A deactivated workflow, an n8n restart without the workflow active, or a changed trigger: nothing runs, nothing errors. MISSED after cadence plus grace.</li><li>The API returns an empty list, every node is green: the evidence expression is false and NO_EVIDENCE fires within a minute.</li><li>An LLM node in a loop: pass the model usage as cost in End Run and set <code>rv agent lead-enricher --cap-day-cost 5</code>.</li></ul>"),
  dict(slug="openclaw", name="OpenClaw (verified-run skill)", group="Agent frameworks",
    title="Monitor scheduled OpenClaw tasks with the verified-run skill: start, task, end with evidence file | RunVouch docs",
    desc="Install the verified-run skill from integrations/openclaw. It wraps a scheduled OpenClaw task in a RunVouch run and reports the output file as evidence; missed, failed or empty runs alert you.",
    h1="OpenClaw scheduled tasks", mode="wrap",
    intro="OpenClaw tasks on a schedule are agents talking to themselves at 7 in the morning: nobody is watching when the task does not start, or starts and writes nothing. The verified-run skill turns each task into a run with a start, an end and a file that proves the work.",
    where="Copy <code>integrations/openclaw/verified-run</code> (and optionally <code>runvouch</code>, the check-in skill for long sessions) into <code>~/.openclaw/skills/</code>, or load the folder as a plugin via its <code>openclaw.plugin.json</code>. The skill ships <code>scripts/verified-run.sh</code> for cron and instructions the agent follows when it does the task itself. Source and README: <a href=\"https://github.com/runvouch/runvouch/tree/main/integrations/openclaw\">integrations/openclaw</a>.",
    key="<code>RUNVOUCH_KEY</code> in the OpenClaw environment, or <code>skills.entries.verified-run.apiKey</code> in <code>openclaw.json</code>; the skill stays hidden until the key is there.",
    snippet=_pre('''# crontab on the OpenClaw host
0 7 * * * ~/.openclaw/skills/verified-run/scripts/verified-run.sh inbox-digest --every 24h --grace 30m --evidence-file ~/out/digest.md -- openclaw task run inbox-digest

# the same wrapper with the rv CLI, if installed
0 7 * * * rv run inbox-digest --evidence-file ~/out/digest.md -- openclaw task run inbox-digest'''),
    silent="<ul><li>The gateway is down at 7:00: no start call, MISSED at 7:30.</li><li>The task exits 0 without writing the digest: the wrapper reports <code>fail</code> with <code>evidence_file: false</code>; yesterday's file is removed first so it cannot pass as today's.</li><li>The agent loops on the same tool call: the companion <code>runvouch</code> skill reports tool calls, RETRY_STORM stops it.</li></ul>"),
  # ───────────── added 28 Aug 2026: the scheduler axis (Claude Code, OpenClaw, GitHub Actions, n8n, language schedulers) ─────────────
  dict(slug="claude-code-scheduled-tasks", name="Claude Code scheduled tasks", group="Schedulers",
    title="Claude Code scheduled task monitoring: Routines, Desktop tasks and claude -p in cron | RunVouch",
    desc="Heartbeat monitoring for Claude Code on a schedule: a green Routine run means the session exited without an infrastructure error, not that the task succeeded. RunVouch fires MISSED when a run did not start, NO_EVIDENCE when it finished without its output, BUDGET_RUN when it overspent.",
    h1="Claude Code scheduled task monitoring", mode="wrap",
    intro="Claude Code scheduled task monitoring for the three ways Claude runs without you: cloud Routines (<code>/schedule</code>), Desktop scheduled tasks, and <code>claude -p</code> from cron. The docs say it themselves: a green status in the run list does not mean the task in your prompt succeeded. RunVouch checks the outcome from outside.",
    where="For <code>claude -p</code> on a server, wrap the command with <code>rv run</code> and require the file the prompt is supposed to write. For Routines and Desktop tasks, install the <a href=\"/docs/claude-code\">RunVouch plugin</a>; its hooks report the start, each tool call and the stop with cost from the transcript, so the run exists in RunVouch even when it never wrote anything.",
    key="On a server: <code>RUNVOUCH_KEY</code> in the cron environment. In a Routine: an environment variable on the routine's cloud environment (note that environment variables there are visible to anyone who uses that environment). On Desktop: the user's shell environment or <code>~/.claude/settings.json</code> <code>env</code> block.",
    snippet=_pre('''# once: the agent, its cadence, and what counts as done
rv agent nightly-changelog --cadence 24h --grace 2h --cap-run-cost 3 --evidence

# crontab on the machine that runs headless Claude Code (jitter-proof: not :00)
7 2 * * * cd /srv/repo && rv run nightly-changelog --evidence-file out/CHANGELOG-draft.md --log out/claude.log \\
  -- claude -p "$(cat prompts/changelog.md)" --dangerously-skip-permissions --max-turns 30

# Routine or Desktop task instead: same agent, reported by the plugin's hooks
export RUNVOUCH_AGENT=nightly-changelog
export RUNVOUCH_EVIDENCE='{"draft":{"type":"file","path":"out/CHANGELOG-draft.md"}}\''''),
    silent="<ul><li>Routines: runs may start a few minutes after the scheduled time (stagger), and the minimum interval is one hour. Set grace to two hours and cadence to the real cadence; MISSED then means the routine did not run, not that it ran late.</li><li>Desktop tasks: if the computer sleeps through the time, the run is skipped; on wake, exactly one catch-up run happens for the most recent missed time and older ones are discarded. A daily task that missed six days runs once.</li><li>A run that hit <code>--max-turns</code>, was denied a tool, or could not reach a domain outside the environment's allowlist (403, <code>x-deny-reason: host_not_allowed</code>) still exits; only the missing evidence file says it did not do the job.</li><li>Cost: the plugin reads tokens from the transcript; a run that loops on the same tool call is RETRY_STORM before it is a bill.</li></ul>",
    missing="<p>The Claude Code documentation states that a green status in a Routine's run list means the session started and exited without an infrastructure error, and that it does not mean the task in your prompt succeeded; blocked network requests, missing connector tools and task-level failures surface in the transcript, not in the status. Desktop scheduled tasks show a notification when a task fires or a catch-up run starts, and list skipped runs in the task's history; nothing is sent when a run that should have happened did not. Headless <code>claude -p</code> in cron has exactly what cron has: an exit code and local mail.</p>"),
  dict(slug="openclaw-cron", name="OpenClaw automations and heartbeat", group="Schedulers",
    title="OpenClaw cron job monitoring: automations that auto-disable, heartbeats that stop | RunVouch",
    desc="Heartbeat monitoring for OpenClaw scheduled jobs (openclaw automations, formerly openclaw cron): OpenClaw disables a recurring job after 10 consecutive failures. RunVouch fires MISSED when a job stops running, STALLED when the gateway hangs, BUDGET_DAY when an agent polls itself into a bill.",
    h1="OpenClaw cron job monitoring", mode="wrap",
    intro="OpenClaw cron job monitoring from outside the gateway: <code>openclaw automations create \"0 7 * * *\"</code> (the <code>openclaw cron</code> alias still works) runs an agent turn on a schedule, in the main session or an isolated one. When the gateway is down at fire time, or the job has been auto-disabled after ten failures, the schedule is a line in a list that nobody reads.",
    where="Two layers. A host cron line wraps a health probe of the gateway so the whole instance has a heartbeat. Per job, the <a href=\"/openclaw/runvouch/SKILL.md\">RunVouch skill</a> makes the agent report start, tool calls and end with evidence; or, for a job that runs a script (<code>--script</code> / <code>--command</code>), wrap that script with <code>rv run</code>.",
    key="<code>RUNVOUCH_KEY</code> in the OpenClaw gateway environment (the skill reads it there) and in the host crontab environment for the heartbeat line.",
    snippet=_pre('''# 1. the instance: a heartbeat every 15 minutes from host cron (MISSED if the gateway stops answering)
rv agent openclaw-gateway --cadence 15m --grace 5m --cap-day-cost 10
*/15 * * * * rv run openclaw-gateway -- curl -fsS http://127.0.0.1:18789/health

# 2. a scheduled job, isolated session, announced to the chat
openclaw automations create "0 7 * * *" --name "Morning inbox triage" --session isolated --announce \\
  --message "Triage overnight mail per SKILL.md runvouch: report start, each tool call and the end with evidence."
rv agent openclaw-inbox --cadence 24h --grace 1h --evidence --cap-run-cost 1

# the skill makes the agent do this itself
curl -s -X POST ''' + API + '''/v1/runs/start -H "X-API-Key: $RUNVOUCH_KEY" -H "content-type: application/json" \\
  -d '{"agent":"openclaw-inbox","source":"openclaw"}'
curl -s -X POST ''' + API + '''/v1/runs/end -H "X-API-Key: $RUNVOUCH_KEY" -H "content-type: application/json" \\
  -d '{"run_id":"...","status":"ok","cost":0.21,"evidence":{"replied":true}}'

# 3. check what OpenClaw itself recorded
openclaw automations runs --id <jobId> --limit 20'''),
    silent="<ul><li>A time-based recurring job is auto-disabled after 10 consecutive execution failures; the disable notification goes to the configured channel once. MISSED keeps firing until the job runs again.</li><li>A job that fires while the gateway is restarting has no run record; <code>openclaw automations runs</code> shows nothing for that slot.</li><li>An agent that polls a tool in a loop inside one turn is RETRY_STORM once the skill reports tool calls, and BUDGET_DAY when the daily cap is crossed; OpenClaw has per-script tool budgets (<code>--script-tool-budget</code>) but no money cap.</li><li>The reply it announced to the chat is not evidence; the reply that was actually sent (<code>{\"replied\": true}</code> from the tool result) is.</li></ul>",
    missing="<p>OpenClaw keeps a run history per job (<code>openclaw automations runs --id</code>) and disables a recurring job after ten consecutive failures with one notification. It does not notify when a job fired into a gateway that was down, when a disabled job stays disabled, or when the agent finished its turn without doing what the prompt asked. <code>openclaw system heartbeat last</code> shows the last heartbeat time to whoever runs it; nothing calls you when that time stops moving.</p>"),
  dict(slug="github-actions-schedule", name="GitHub Actions schedule", group="Schedulers",
    title="GitHub Actions scheduled workflow monitoring: schedules disabled after 60 days, green jobs that did nothing | RunVouch",
    desc="Heartbeat monitoring for GitHub Actions schedule: cron workflows. GitHub disables them after 60 days without repository activity and can delay them under load; nothing tells you. The runvouch/vouch-action step gives them MISSED, FAILED and NO_EVIDENCE.",
    h1="GitHub Actions scheduled workflow monitoring", mode="wrap",
    intro="GitHub Actions scheduled workflow monitoring for the workflow that quietly stopped: <code>on: schedule</code> runs on the default branch, only while the repository is active, and only when GitHub's queue has room. A green check on a run that wrote nothing is still a green check.",
    where="One step in the job, before or around your command: <code>runvouch/vouch-action@v1</code> (a composite action that installs <code>rv</code> and wraps the command), or <code>pip install runvouch</code> and <code>rv run</code> by hand. Source: <a href=\"https://github.com/runvouch/vouch-action\">github.com/runvouch/vouch-action</a>.",
    key="Repository secret <code>RUNVOUCH_KEY</code> (Settings, Secrets and variables, Actions). Pass it as <code>key: ${{ secrets.RUNVOUCH_KEY }}</code>; for a reusable workflow, add <code>secrets: inherit</code>.",
    snippet=_pre('''# .github/workflows/nightly-report.yml
name: nightly-report
on:
  schedule: [{ cron: "17 3 * * *" }]   # UTC; avoid :00, GitHub queues are busiest there
  workflow_dispatch:
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: runvouch/vouch-action@v1
        with:
          agent: nightly-report
          key: ${{ secrets.RUNVOUCH_KEY }}
          cadence: 24h                       # registers the agent: MISSED after 24h + grace
          evidence-file: out/report.html     # must exist, be non-empty and be modified by the run
          cap-run-cost: 2
          run: python report.py --out out/report.html

# without the action
      - run: pip install runvouch && rv run nightly-report --evidence-file out/report.html -- python report.py
        env: { RUNVOUCH_KEY: ${{ secrets.RUNVOUCH_KEY }} }'''),
    silent="<ul><li>In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days. The workflow page shows a banner; no e-mail is sent. MISSED fires the first night.</li><li>The schedule event can be delayed during periods of high load, and the docs say a run may not start at the scheduled minute or at all. Set grace to an hour.</li><li>Schedules run on the default branch only; a workflow edited on a feature branch does not change what runs tonight.</li><li>A job that passes with an empty <code>out/report.html</code> is a green run to GitHub and NO_EVIDENCE to RunVouch.</li></ul>",
    missing="<p>GitHub notifies on failed workflow runs, by e-mail or in the notifications inbox, and only for runs that happened. A schedule that was disabled after 60 days of inactivity, a schedule that GitHub dropped under load, or a workflow file that lost its <code>schedule:</code> block in a merge, produces no run and no notification. The last run's timestamp on the Actions tab is the only record that the job used to exist.</p>"),
  dict(slug="n8n-schedule-trigger", name="n8n Schedule Trigger", group="No-code automation",
    title="n8n Schedule Trigger monitoring: inactive workflows, Error Workflows that never fire, green runs that did nothing | RunVouch",
    desc="Heartbeat monitoring for n8n workflows on a Schedule Trigger: an Error Workflow only fires when a node errors. RunVouch fires MISSED when the workflow stops running (deactivated, instance down), NO_EVIDENCE when it ran and produced nothing, and caps LLM cost per execution.",
    h1="n8n Schedule Trigger monitoring", mode="http",
    intro="n8n Schedule Trigger monitoring for the execution that did not happen: a Schedule Trigger fires only while the workflow is active and the instance is up. When someone deactivates the workflow to edit it and forgets, or the container restarts into a broken credential, the Error Workflow has nothing to react to.",
    where="Two HTTP Request nodes: one right after the Schedule Trigger (POST <code>/v1/runs/start</code>, keep <code>run_id</code>), one at the end (POST <code>/v1/runs/end</code> with status, cost from your OpenAI or Anthropic node's usage, and evidence). Put the end node on the error output too, with <code>status: fail</code>. Full node settings on the <a href=\"/docs/n8n\">n8n guide</a>.",
    key="An n8n credential of type Header Auth (name <code>X-API-Key</code>, value the key), selected in both HTTP Request nodes. Keep the key out of the node's JSON body.",
    snippet=http_snippet("lead-enricher", "n8n"),
    silent="<ul><li>A workflow that is inactive does not run and does not error; the Error Workflow is never called. MISSED after cadence plus grace is the only signal.</li><li>A workflow that runs and finds zero items is a successful execution; with Save successful executions off, it is not even in the list. Report <code>evidence: {\"rows_written\": count &gt; 0}</code>.</li><li>Schedule Trigger uses the workflow's timezone setting, which defaults to the instance timezone; a schedule that moved by an hour after a timezone change is a DRIFT in run start, not an error.</li><li>An AI node that retries (Retry On Fail) multiplies token spend; pass the usage into the end call so the daily cap holds.</li></ul>",
    missing="<p>n8n's Error Workflow runs when an execution fails with an error. It is not triggered for a workflow that was never executed because it is inactive, for an instance that is down, or for an execution that finished with no output. The Executions list shows each run with its status and is the only record; whether successful executions are saved at all depends on the workflow's settings.</p>"),
  dict(slug="node-cron", name="node-cron", group="Orchestrators",
    title="node-cron monitoring: in-process schedules that die with the Node process | RunVouch",
    desc="Heartbeat monitoring for node-cron and node-schedule: the schedule lives inside your Node process and stops when it stops. RunVouch fires MISSED from outside, FAILED when the callback throws, NO_EVIDENCE when it ran and wrote nothing. Node client, no dependencies.",
    h1="node-cron monitoring", mode="wrap",
    intro="node-cron monitoring from outside the process: <code>cron.schedule(\"0 2 * * *\", fn)</code> is a timer in your Node process. A crash at 01:59, a deploy that restarted the pod at 02:00, or a scale-to-zero platform, and the job simply does not run; no exception, no log line.",
    where="Inside the scheduled callback with the <a href=\"/runvouch.js\">Node client</a> (<code>rv.vouch</code> reports start, end, status from a thrown error, and evidence from your callback). The agent's cadence is what makes the missing process visible.",
    key="<code>RUNVOUCH_KEY</code> in the process environment (<code>.env</code> via dotenv, or the platform's variables).",
    snippet=_pre('''// npm install node-cron ; curl -O https://runvouch.com/runvouch.js
const cron = require("node-cron");
const rv = require("./runvouch");
const { buildReport } = require("./report");

// once, at boot: cadence and caps (idempotent)
rv.agent("nightly-report", { cadence_s: 86400, grace_s: 1800, evidence_required: true, cap_run_cost: 2 });

cron.schedule("0 2 * * *", () =>
  rv.vouch("nightly-report", async (run) => {
    const rows = await buildReport();          // your work
    await run.tool("openai.chat", { rows }, { cost: 0.04 });
    return rows;
  }, { source: "node-cron", evidence: (rows) => ({ rows_written: rows > 0 }) })
  .catch((e) => console.error("nightly-report failed:", e)),   // rv already reported status: fail
  { timezone: "UTC" });'''),
    silent="<ul><li>A rejected promise inside the callback is an unhandled rejection: on Node 15 and later it crashes the process unless caught, which takes every other schedule down with it. The <code>.catch</code> above keeps the process alive; the FAILED alert has the message.</li><li>node-cron has no persistence and no catch-up: a tick that falls while the process is down is gone.</li><li>Two replicas of the service run the job twice; both runs show under one agent and the daily cap counts both.</li><li>A callback that runs past the next tick overlaps itself; STALLED (max runtime) catches the slow one.</li></ul>",
    missing="<p>node-cron validates the expression and calls your function; it keeps no run history, has no error channel of its own, and does not know a tick was skipped because the process was not running. Whatever you <code>console.log</code> goes to the process stdout, which on most platforms is kept for days and read by nobody until something else breaks.</p>"),
  dict(slug="pm2-cron", name="PM2 cron restart", group="Orchestrators",
    title="PM2 cron job monitoring: cron_restart scripts that stop when the daemon does | RunVouch",
    desc="Heartbeat monitoring for PM2 scheduled scripts (cron_restart with autorestart off): when the PM2 daemon is not resurrected after a reboot, nothing runs and nothing says so. Wrap the script with rv run for MISSED, FAILED and NO_EVIDENCE.",
    h1="PM2 cron job monitoring", mode="wrap",
    intro="PM2 cron job monitoring for the daemon that was not there: PM2 can start a script on a cron expression (<code>cron_restart</code>) and let it exit (<code>autorestart: false</code>). The schedule is a property of the PM2 daemon; a reboot without <code>pm2 startup</code> and <code>pm2 save</code>, or a <code>pm2 kill</code> in a deploy script, and the job is gone.",
    where="Make <code>rv</code> the process PM2 starts (<code>interpreter: none</code>) with your script as the wrapped command, so every scheduled start becomes a run and the exit code becomes the status.",
    key="<code>env: { RUNVOUCH_KEY: ... }</code> in the ecosystem file is stored in plain text; better: <code>pm2 start ecosystem.config.js --update-env</code> from a shell where the key is exported, or read it from a file with mode 600 in the script.",
    snippet=_pre('''// ecosystem.config.js
module.exports = { apps: [{
  name: "nightly-report",
  script: "rv",                 // the runvouch CLI; pip install runvouch
  interpreter: "none",
  args: "run nightly-report --evidence-file out/report.html --source pm2 -- node report.js",
  cron_restart: "0 2 * * *",
  autorestart: false,           // exit when done; PM2 starts it again at the next cron tick
  cwd: "/srv/report",
}]};

// pm2 start ecosystem.config.js && pm2 save && pm2 startup
// rv agent nightly-report --cadence 24h --grace 30m --evidence'''),
    silent="<ul><li>Without <code>pm2 save</code> and a working <code>pm2 startup</code> hook, a reboot brings back nothing; MISSED fires that night.</li><li>With <code>autorestart: true</code> (the default) a script that exits is restarted immediately in a loop, at up to 15 restarts before PM2 gives up (<code>max_restarts</code>); every restart is a new run in RunVouch, so the pattern is obvious on the dashboard.</li><li><code>cron_restart</code> restarts a process that is still running at the tick; a slow run is cut short with no exit code of its own, which RunVouch reports as STALLED.</li><li>PM2 logs (<code>~/.pm2/logs</code>) grow until pm2-logrotate is installed; <code>--log</code> on <code>rv run</code> keeps the part that matters as evidence.</li></ul>",
    missing="<p>PM2 records restarts, uptime and the last exit code per process in <code>pm2 list</code> and keeps stdout and stderr in <code>~/.pm2/logs</code>. It has no notification of its own; PM2 Plus adds e-mail and Slack alerts for exceptions and restarts on a paid plan, and neither knows that a cron-restarted script was supposed to write a file tonight. A daemon that is not running reports nothing at all.</p>"),
  dict(slug="bullmq-repeatable", name="BullMQ job schedulers", group="Orchestrators",
    title="BullMQ repeatable job monitoring: schedulers with no Worker, jobs that complete with nothing | RunVouch",
    desc="Heartbeat monitoring for BullMQ job schedulers and repeatable jobs: a scheduler adds jobs on a cron pattern, a Worker must process them. No Worker, evicted Redis, or a processor that resolves early, and nothing tells you. RunVouch fires MISSED, STALLED and NO_EVIDENCE.",
    h1="BullMQ repeatable job monitoring", mode="wrap",
    intro="BullMQ repeatable job monitoring for the queue that fills up quietly: <code>queue.upsertJobScheduler(\"nightly\", { pattern: \"0 2 * * *\" })</code> puts a delayed job in Redis; a <code>Worker</code> picks it up. With the Worker down, jobs move from delayed to waiting and stay there, and every scheduled tick adds one more.",
    where="Inside the Worker's processor function with the <a href=\"/runvouch.js\">Node client</a>, so the run starts when the job is actually picked up, not when it was scheduled. For long jobs call <code>run.heartbeat()</code> next to <code>job.updateProgress()</code>.",
    key="<code>RUNVOUCH_KEY</code> in the Worker process environment; the producer that upserts the scheduler does not need it.",
    snippet=_pre('''// producer (once, idempotent): BullMQ 5.16+ job schedulers; older: queue.add(name, data, { repeat: { pattern } })
const { Queue, Worker } = require("bullmq");
const rv = require("./runvouch");
const connection = { host: "redis", port: 6379 };
const queue = new Queue("reports", { connection });
await queue.upsertJobScheduler("nightly-report", { pattern: "0 2 * * *", tz: "UTC" }, { name: "nightly-report" });

// worker
new Worker("reports", async (job) =>
  rv.vouch("nightly-report", async (run) => {
    const rows = await buildReport(job.data);
    await run.heartbeat();                  // long jobs: keeps STALLED honest
    return rows;
  }, { source: "bullmq", evidence: (rows) => ({ rows_written: rows > 0 }) }),
  { connection, concurrency: 1, lockDuration: 600000 });

// rv agent nightly-report --cadence 24h --grace 30m --max-runtime 1h --evidence'''),
    silent="<ul><li>No Worker means the scheduled job sits in the waiting list with no error; MISSED after cadence plus grace is the signal. <code>queue.getJobCounts()</code> would show it, if something polled it.</li><li>A job whose lock expires (<code>lockDuration</code>, default 30 s) while the processor is still running is marked stalled by BullMQ and retried up to <code>maxStalledCount</code>; each retry is another run under the same agent.</li><li>Redis with an eviction policy other than <code>noeviction</code> can drop the scheduler key itself; the docs require <code>noeviction</code>, and MISSED is what tells you it was ignored.</li><li>A processor that returns without throwing is completed; an empty result is completed too.</li></ul>",
    missing="<p>BullMQ moves a failed job to the failed set and emits <code>failed</code> and <code>stalled</code> events on a <code>QueueEvents</code> instance, if a process is listening. It has no notification, no notion of a job that should have been added but was not (a lost scheduler, a producer that never ran), and no record of a completed job's usefulness. Taskforce.sh and Bull Board show the counts; someone has to look.</p>"),
  dict(slug="sidekiq-cron", name="Sidekiq cron (sidekiq-cron, sidekiq-scheduler)", group="Orchestrators",
    title="Sidekiq cron job monitoring: schedules that stop with the process, jobs that die in the retry set | RunVouch",
    desc="Heartbeat monitoring for sidekiq-cron and sidekiq-scheduler jobs: the poller lives inside the Sidekiq process, so when it is down or the schedule failed to load, nothing is enqueued and nothing errors. RunVouch fires MISSED, FAILED and NO_EVIDENCE from two HTTP calls in perform.",
    h1="Sidekiq cron job monitoring", mode="http",
    intro="Sidekiq cron job monitoring for the schedule Sidekiq Web says is fine: sidekiq-cron loads <code>config/schedule.yml</code> into Redis and a poller in the Sidekiq process enqueues jobs on time. A job that raises goes to the retry set, retries for 25 attempts over about 21 days, then goes to the Dead set. A job that was never enqueued goes nowhere.",
    where="Inside <code>perform</code>, with two <code>Net::HTTP</code> calls around the work (no gem required), or shell out to <code>rv run</code> if the job runs a script. Report the run from the job, not from the schedule, so a job that was enqueued but never picked up is a MISSED start.",
    key="<code>ENV[\"RUNVOUCH_KEY\"]</code> on the Sidekiq process, from Rails credentials (<code>Rails.application.credentials.runvouch_key</code>) or the process environment.",
    snippet=_pre('''# config/schedule.yml (sidekiq-cron)
nightly_report:
  cron: "0 2 * * *"
  class: NightlyReportJob
  queue: reports

# app/jobs/nightly_report_job.rb
require "net/http"; require "json"
class NightlyReportJob
  include Sidekiq::Job
  sidekiq_options retry: 2
  API = "''' + API + '''"
  def post(path, body)
    uri = URI(API + path)
    req = Net::HTTP::Post.new(uri, "X-API-Key" => ENV.fetch("RUNVOUCH_KEY"), "content-type" => "application/json")
    req.body = body.to_json
    JSON.parse(Net::HTTP.start(uri.host, uri.port, use_ssl: true, read_timeout: 10) { |h| h.request(req) }.body)
  rescue StandardError => e
    Rails.logger.warn("runvouch unreachable: #{e.message}"); {}   # fail open
  end
  def perform
    run_id = post("/v1/runs/start", agent: "nightly-report", source: "sidekiq")["run_id"]
    rows = Report.build!                                         # your work
    post("/v1/runs/end", run_id: run_id, status: "ok", evidence: { rows_written: rows > 0 })
  rescue StandardError => e
    post("/v1/runs/end", run_id: run_id, status: "fail", meta: { error: e.message[0, 500] }) if run_id
    raise
  end
end'''),
    silent="<ul><li>The cron poller runs inside the Sidekiq process. Sidekiq down, or a <code>schedule.yml</code> that failed to parse at boot, means nothing is enqueued; MISSED is the only external signal.</li><li>A job enqueued to a queue no process listens to (a queue renamed in the deploy) is enqueued forever; RunVouch sees no start.</li><li>Default retries: 25 attempts over about 21 days before the Dead set. With an LLM call inside, that is 25 bills. <code>retry: 2</code> above plus the per-run cost cap bound it.</li><li>A job that rescues everything and returns is a success in Sidekiq Web; evidence is what separates it from a good run.</li></ul>",
    missing="<p>Sidekiq Web shows queues, the retry set, the Dead set and a Cron tab with each schedule's last enqueue time. Sidekiq itself sends no notifications; error trackers (Sentry, Honeybadger) receive exceptions from jobs that ran. There is no exception for a poller that is not running, a schedule that did not load, or a job that completed with nothing to show.</p>"),
  dict(slug="rq-scheduler", name="RQ Scheduler", group="Orchestrators",
    title="RQ Scheduler monitoring: the rqscheduler process that must be running, jobs that fail in the registry | RunVouch",
    desc="Heartbeat monitoring for rq-scheduler cron jobs: a separate rqscheduler process enqueues them and an rq worker runs them. If either is missing, nothing errors. RunVouch fires MISSED on the missing run, FAILED with the exception, NO_EVIDENCE on an empty result.",
    h1="RQ Scheduler monitoring", mode="wrap",
    intro="RQ Scheduler monitoring for the two processes it needs: <code>scheduler.cron(\"0 2 * * *\", func=nightly_report)</code> stores the schedule in Redis; the <code>rqscheduler</code> process moves it into a queue on time; an <code>rq worker</code> executes it. A supervisor that restarts the worker but forgot the scheduler is the usual way it stops.",
    where="Inside the job function with the <a href=\"/runvouch.py\">Python client</a>, so the run starts when a worker actually picks the job up. Register the agent's cadence once.",
    key="<code>RUNVOUCH_KEY</code> in the rq worker's environment; the scheduler process does not need it.",
    snippet=_pre('''# schedule.py (run once; use_local_timezone=False means UTC)
from redis import Redis
from rq_scheduler import Scheduler
from jobs import nightly_report
scheduler = Scheduler(queue_name="reports", connection=Redis("redis"))
scheduler.cron("0 2 * * *", func=nightly_report, queue_name="reports", id="nightly-report", use_local_timezone=False)

# jobs.py
import runvouch
def nightly_report():
    with runvouch.vouch("nightly-report", source="rq", evidence=lambda: {"rows_written": n > 0}) as run:
        n = build_report()
        run.tool("llm.summarise", {"rows": n}, cost=0.03)

# processes (both must be running):  rqscheduler --url redis://redis:6379  |  rq worker reports
# rv agent nightly-report --cadence 24h --grace 30m --evidence'''),
    silent="<ul><li>No <code>rqscheduler</code> process: the cron entry stays in Redis and is never enqueued. No <code>rq worker</code> on the queue: it is enqueued and never runs. Both are MISSED.</li><li>rq-scheduler does not catch up on ticks it missed while it was down.</li><li>A failed job lands in the FailedJobRegistry with its traceback; RQ does not retry unless <code>Retry()</code> was passed, and it sends nothing anywhere.</li><li>Jobs that exceed the RQ job timeout (default 180 s) are killed with a <code>JobTimeoutException</code>; set the agent's max runtime to the same value so STALLED and the timeout agree.</li></ul>",
    missing="<p>RQ keeps started, finished and failed job registries in Redis and shows them in rq-dashboard or <code>rq info</code>. It has no notifications. A scheduled job that was never enqueued does not appear in any registry, and the rqscheduler process has no health endpoint; its absence is visible only in your process supervisor.</p>"),
  dict(slug="laravel-scheduler", name="Laravel task scheduler", group="Orchestrators",
    title="Laravel scheduler monitoring: schedule:run cron that stops, tasks that pass and do nothing | RunVouch",
    desc="Heartbeat monitoring for the Laravel task scheduler: everything depends on one system cron line calling schedule:run every minute. When that line is missing after a server rebuild, no task runs and no task fails. RunVouch fires MISSED, FAILED and NO_EVIDENCE per task.",
    h1="Laravel scheduler monitoring", mode="wrap",
    intro="Laravel scheduler monitoring for the cron line that is not there: <code>Schedule::command(\"report:build\")-&gt;dailyAt(\"02:00\")</code> only runs if <code>php artisan schedule:run</code> is called every minute by cron. The docs' crontab line ends in <code>&gt;&gt; /dev/null 2&gt;&amp;1</code>, so the scheduler's own output is discarded too.",
    where="Two options. Per task: <code>Schedule::exec()</code> with <code>rv run</code> wrapping the artisan command, so each run has an exit code and evidence. For the scheduler as a whole: wrap <code>schedule:run</code> itself with a 1-minute cadence agent when what you need to know is that cron is alive.",
    key="<code>RUNVOUCH_KEY</code> in <code>.env</code> (read by the cron environment through Laravel), or in the crontab line's environment. Do not put it in <code>config/</code> under version control.",
    snippet=_pre('''# system crontab (the one line everything depends on)
* * * * * cd /srv/app && php artisan schedule:run >> /dev/null 2>&1

# routes/console.php (Laravel 11+; app/Console/Kernel.php on 10)
use Illuminate\\Support\\Facades\\Schedule;

Schedule::exec('rv run nightly-report --evidence-file storage/app/report.html -- php artisan report:build')
    ->dailyAt('02:00')
    ->withoutOverlapping()
    ->onOneServer()
    ->environments(['production']);

# or, if you would rather not shell out: the two HTTP calls inside the command's handle()
# Http::withHeaders(['X-API-Key' => env('RUNVOUCH_KEY')])->post('''' + API + '''/v1/runs/start', ['agent' => 'nightly-report', 'source' => 'laravel']);

# rv agent nightly-report --cadence 24h --grace 30m --evidence'''),
    silent="<ul><li>No <code>schedule:run</code> cron line (new server, container without cron, a Forge server whose scheduler was removed): no task runs, no task fails. MISSED is the first and only signal.</li><li><code>emailOutputOnFailure()</code> and <code>pingOnFailure()</code> exist per task and fire on a non-zero exit; a command that returns 0 with an empty report is a success to both.</li><li><code>withoutOverlapping()</code> holds a lock for 24 hours by default; a task that crashed hard leaves the lock and the next runs are skipped. That is a MISSED with a cause you can read on the dashboard.</li><li><code>onOneServer()</code> needs a shared cache; with a file cache each server runs the task, and the daily cap counts every run.</li></ul>",
    missing="<p>Laravel's scheduler can e-mail a task's output, ping a URL before, after and on failure, and send events to a monitoring service, all per task and all only when the task ran. The scheduler has no record of a minute in which <code>schedule:run</code> was not called, and the documented crontab line sends its output to <code>/dev/null</code>. Laravel Pulse and Horizon show queues and requests, not whether a scheduled task was skipped.</p>"),
  dict(slug="spring-scheduled", name="Spring @Scheduled", group="Orchestrators",
    title="Spring @Scheduled monitoring: exceptions that are only logged, tasks that block the single scheduler thread | RunVouch",
    desc="Heartbeat monitoring for Spring Boot @Scheduled methods: an exception is logged and swallowed, a hung task blocks the default single scheduler thread, and a stopped app runs nothing. RunVouch fires FAILED, STALLED and MISSED from two HTTP calls in the method.",
    h1="Spring @Scheduled monitoring", mode="http",
    intro="Spring @Scheduled monitoring for the log line nobody grepped: <code>@Scheduled(cron = \"0 0 2 * * *\")</code> runs inside the application. An exception is caught by the scheduler's error handler, logged at ERROR, and the next fire proceeds as planned. A method that hangs on a socket blocks the default one-thread scheduler and every other task with it.",
    where="At the top and bottom of the scheduled method with Java's built-in <code>HttpClient</code> (Java 11+), or in a small <code>@Aspect</code> around every <code>@Scheduled</code> method if you have many. Register the agent's cadence once.",
    key="<code>RUNVOUCH_KEY</code> as an environment variable read through <code>@Value(\"${RUNVOUCH_KEY}\")</code> or <code>application.yml</code> with a placeholder; Spring Cloud Config or Vault if you have them.",
    snippet=_pre('''@Component
public class NightlyReport {
  private static final String API = "''' + API + '''";
  private final HttpClient http = HttpClient.newHttpClient();
  private final ObjectMapper json = new ObjectMapper();
  @Value("${RUNVOUCH_KEY}") String key;

  private Map<String, Object> post(String path, Map<String, Object> body) {
    try {
      var req = HttpRequest.newBuilder(URI.create(API + path)).timeout(Duration.ofSeconds(10))
          .header("X-API-Key", key).header("content-type", "application/json")
          .POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body))).build();
      return json.readValue(http.send(req, HttpResponse.BodyHandlers.ofString()).body(), Map.class);
    } catch (Exception e) { return Map.of(); }   // fail open: the job still runs
  }

  @Scheduled(cron = "0 0 2 * * *", zone = "UTC")
  public void run() {
    String runId = (String) post("/v1/runs/start", Map.of("agent", "nightly-report", "source", "spring")).get("run_id");
    try {
      int rows = reportService.build();                     // your work
      post("/v1/runs/end", Map.of("run_id", runId, "status", "ok", "evidence", Map.of("rows_written", rows > 0)));
    } catch (Exception e) {
      post("/v1/runs/end", Map.of("run_id", runId, "status", "fail", "meta", Map.of("error", e.toString())));
      throw e;
    }
  }
}
// @EnableScheduling on a configuration class; rv agent nightly-report --cadence 24h --grace 30m --max-runtime 1h --evidence'''),
    silent="<ul><li>The default <code>TaskScheduler</code> has one thread. A task blocked on a slow HTTP call without a timeout blocks every other <code>@Scheduled</code> method; the blocked one is STALLED, the others are MISSED, and the app's health endpoint says UP.</li><li>Exceptions are handled by the scheduler's <code>ErrorHandler</code> (logged) and the schedule continues; nothing is thrown to anything that would page you.</li><li>No catch-up: a fire time that passes while the app is restarting is skipped.</li><li>Two instances of the app run the task twice unless you add ShedLock or similar; both runs are visible under one agent.</li></ul>",
    missing="<p>Spring logs a scheduled task's exception at ERROR level through the default error handler and moves on; Actuator's <code>/actuator/scheduledtasks</code> lists the schedules, not their outcomes, and Micrometer only measures what you instrument. Nothing in the framework knows that 02:00 came and went with the app down, or that the method returned after writing an empty file.</p>"),
  dict(slug="quartz", name="Quartz Scheduler", group="Orchestrators",
    title="Quartz Scheduler monitoring: misfires, RAMJobStore restarts, jobs that complete with nothing | RunVouch",
    desc="Heartbeat monitoring for Quartz jobs (Java, .NET): a misfire is handled by a policy, not reported; a RAMJobStore forgets every trigger on restart; a job that swallows its exception completes. RunVouch fires MISSED, FAILED and NO_EVIDENCE from two HTTP calls in execute().",
    h1="Quartz Scheduler monitoring", mode="http",
    intro="Quartz Scheduler monitoring for the misfire policy you did not choose: a <code>CronTrigger</code> that could not fire on time (scheduler paused, no free worker thread, JVM down) is a misfire after the threshold (60 seconds by default), and what happens next is the trigger's misfire instruction: fire once now, or do nothing until the next time. Either way, Quartz logs it and nobody is told.",
    where="At the top and bottom of the job's <code>execute()</code>, or in a <code>JobListener</code> (<code>jobToBeExecuted</code> / <code>jobWasExecuted</code>) that covers every job in the scheduler. The listener gets the <code>JobExecutionException</code>, so status is exact.",
    key="<code>RUNVOUCH_KEY</code> from the environment or the scheduler's <code>SchedulerContext</code>, set at boot; not in <code>quartz.properties</code>.",
    snippet=_pre('''// one listener for every job in the scheduler
public class RunVouchListener implements JobListener {
  static final String API = "''' + API + '''";
  final HttpClient http = HttpClient.newHttpClient();
  final String key = System.getenv("RUNVOUCH_KEY");
  public String getName() { return "runvouch"; }

  String post(String path, String body) {
    try {
      var req = HttpRequest.newBuilder(URI.create(API + path)).timeout(Duration.ofSeconds(10))
          .header("X-API-Key", key).header("content-type", "application/json")
          .POST(HttpRequest.BodyPublishers.ofString(body)).build();
      return http.send(req, HttpResponse.BodyHandlers.ofString()).body();
    } catch (Exception e) { return "{}"; }                        // fail open
  }
  public void jobToBeExecuted(JobExecutionContext ctx) {
    String agent = ctx.getJobDetail().getKey().getName();          // e.g. nightly-report
    String r = post("/v1/runs/start", "{\\"agent\\":\\"" + agent + "\\",\\"source\\":\\"quartz\\"}");
    ctx.put("rv_run_id", r.replaceAll(".*\\"run_id\\":\\"([^\\"]+)\\".*", "$1"));
  }
  public void jobExecutionVetoed(JobExecutionContext ctx) {}
  public void jobWasExecuted(JobExecutionContext ctx, JobExecutionException e) {
    Object result = ctx.getResult();                               // set by the job: rows written
    boolean ok = e == null, ev = result instanceof Integer && (Integer) result > 0;
    post("/v1/runs/end", "{\\"run_id\\":\\"" + ctx.get("rv_run_id") + "\\",\\"status\\":\\"" + (ok ? "ok" : "fail")
        + "\\",\\"evidence\\":{\\"rows_written\\":" + ev + "}}");
  }
}
// scheduler.getListenerManager().addJobListener(new RunVouchListener(), EverythingMatcher.allJobs());
// trigger: cronSchedule("0 0 2 * * ?").withMisfireHandlingInstructionDoNothing()
// rv agent nightly-report --cadence 24h --grace 30m --evidence'''),
    silent="<ul><li>A misfire with <code>withMisfireHandlingInstructionDoNothing()</code> skips the run; with the default smart policy it fires once, late. Only MISSED (measured from outside) tells you which happened tonight.</li><li><code>RAMJobStore</code> (the default) keeps triggers in memory; a restart without re-registering them means no schedule. <code>JDBCJobStore</code> survives, if the scheduler is started.</li><li>A job that catches its exception and returns is a completed job; a job that throws <code>JobExecutionException</code> with <code>refireImmediately</code> loops on the same input, which is RETRY_STORM when reported per attempt.</li><li>A thread pool exhausted by long jobs delays every trigger; STALLED on the long ones, MISSED on the delayed ones.</li></ul>",
    missing="<p>Quartz logs misfires and job exceptions through SLF4J and exposes listeners for jobs, triggers and the scheduler; it has no notification of its own and no built-in record that a trigger was supposed to fire while the scheduler was down. The <code>QRTZ_FIRED_TRIGGERS</code> table (JDBC store) shows what is running now, not what did not run. A job's result object is whatever the job set, and by default nothing reads it.</p>"),
  dict(slug="grafana", name="Grafana dashboard", group="Dashboards",
    title="Grafana dashboard for RunVouch: agent status, open alerts and API uptime from JSON endpoints | RunVouch",
    desc="Show RunVouch agent state in Grafana with the Infinity or JSON API datasource: one dashboard JSON reads the public status.json, a public fleet summary, and (with your key) /v1/agents and /v1/alerts. Import, set two variables, done.",
    h1="Grafana dashboard for RunVouch agents", mode="http",
    intro="Put RunVouch next to the rest of your monitoring: a ready-made dashboard JSON reads RunVouch's public <code>status.json</code> (API uptime, incidents, sealed proof days), an opted-in public fleet (<code>/public/fleet/&lt;slug&gt;.json</code>), and, with your key, your own <code>/v1/agents</code> and <code>/v1/alerts</code>. The package with the dashboard, a README and the datasource settings is at <a href=\"https://github.com/runvouch/runvouch/tree/main/integrations/grafana\">integrations/grafana</a>.",
    where="Grafana 10 or 11 with the <a href=\"https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/\">Infinity datasource</a> plugin (or the JSON API datasource; the panels use plain JSON paths, no JSONata). The datasource queries the API from the Grafana server, so browser CORS does not apply.",
    key="Create the Infinity datasource with an HTTP header <code>X-API-Key</code> holding your RunVouch key (stored encrypted in Grafana). The public endpoints need no key; the <code>/v1/</code> panels use the datasource header.",
    snippet=_pre('''# endpoints the dashboard reads (GET, JSON)
''' + API + '''/status.json                       # public: uptime windows, incidents, last_heartbeat_age_s, sealed_days
''' + API + '''/public/fleet/<slug>.json          # public, opt-in per account: agents[] with last_run, late, rates, open_alert
''' + API + '''/v1/agents                         # your key: name, state (ok|unproven|failed|alert|running|waiting|paused), cost_24h, last_run
''' + API + '''/v1/alerts                         # your key: open alerts, kind, agent, ts, message

# import
curl -sO https://raw.githubusercontent.com/runvouch/runvouch/main/integrations/grafana/runvouch-dashboard.json
# Grafana: Dashboards, New, Import, upload the file, pick the Infinity datasource, set the fleet slug variable

# the rows the dashboard turns into panels: what an agent reported, checked from outside
rv run nightly-report --evidence-file out/report.html -- python report.py'''),
    silent="<ul><li>A Grafana alert rule on <code>state != ok</code> from <code>/v1/agents</code> is a second, independent pager; RunVouch's own alerts keep going to Telegram, Slack, e-mail, webhook or PagerDuty.</li><li>The public fleet endpoint returns only agents the account owner marked public, and only run facts: no evidence, no cost, no keys. Public fleets are enabled per account; <a href=\"/contact\">ask</a> with the agents you want listed.</li><li><code>status.json</code> is about RunVouch itself. If <code>last_heartbeat_age_s</code> climbs past 150, the detector loop is behind and your MISSED alerts are late; the dashboard shows that number on purpose.</li></ul>",
    missing="<p>Grafana shows what a datasource returns; it does not know an agent was supposed to run at 02:00, or that a green run wrote nothing. That judgment is made in RunVouch (cadence, evidence, caps) and exposed as a <code>state</code> field, which is what the dashboard's stat panels colour on. Grafana alerting on those fields is a useful second channel, not a replacement for the first.</p>"),
]

GROUPS = ["Schedulers", "Cloud functions", "Platforms", "Orchestrators", "No-code automation", "Agent frameworks", "Dashboards"]
