# Leaf website worker

Cloudflare serves each product and example page's live shell and initial canonical
projection from `.tmp/site-assets`. A read-only visit therefore paints and presents
without allocating or waiting for a container. The document issues a secure, HTTP-only
identity cookie without starting anything; that lets concurrent first interactions use
one container. The first request that needs private, mutable state marks the identity
active and reaches the canonical Python Leaf server in a Cloudflare Container. Its
copied page directories and append-only logs are private to that reader and disappear
when Cloudflare replaces the container; no website-only projection or conversation
store exists. A returning tab detects a new server incarnation and reloads before it
can apply that fresh container's lower event sequence over vanished state.

The build gives every document, state response, and module graph one release digest.
Runtime assets live behind release-addressed URLs with immutable cache headers, while
the browser sends the document's release and layer identities to every API request. A
mixed response reloads instead of letting one release interpret another release's
state. The build-generated manifest is the routing authority shared by the Worker and
the Python adapter. Published media, revisions, and version documents stay on the edge;
when one of those paths is absent from the release, the Worker asks the reader's
active container so a newly created private revision can become the live document.

The deployment admits up to 6,000 concurrent `basic` containers. After a session is
active, a visible page holds it through Leaf's news stream; a passive page opens no
stream. Hidden tabs close their streams, so the ten-minute application idle timer can
begin after the browser session has no visible Leaf tab. This is resource lifetime, not
a persistence guarantee: Cloudflare can replace an active instance during a rollout.
Deployments allow active instances a bounded ten-minute drain window, after which a
replacement starts with fresh ephemeral state. Durable website sessions will require a
durable page-directory store rather than another lifecycle promise.

Accepted browser events also write canonical metadata to the
`leaf_website_events` Analytics Engine dataset. The data point omits event content,
widget ids, IP addresses, and session cookies:

| Field | Value |
| --- | --- |
| `index1` | Canonical event id |
| `blob1` | Public page route |
| `blob2` | `product` or `example` |
| `blob3` | Event kind |
| `blob4` | Action verb, when present |
| `blob5` | Site release id |
| `blob6` | Public 12-digit session reference shown in the page banner |
| `double1` | Page revision, or `0` when absent |
| `double2` | `1` when the event needs an agent reply |

The session reference is stable for the browser identity's lifetime, so it links that
reader's accepted events across pages and visits. It is a support handle rather than a
credential; no server endpoint accepts it as session identity.

A retry of an accepted browser attempt writes the same event id again. Count distinct
ids when measuring reader events:

```sql
SELECT
  blob1 AS page,
  blob3 AS kind,
  blob4 AS action,
  count(DISTINCT index1) AS events
FROM leaf_website_events
WHERE timestamp > now() - INTERVAL '7' DAY
GROUP BY page, kind, action
ORDER BY events DESC
```

The number in the page banner is the direct support lookup key:

```sql
SELECT timestamp, index1 AS event, blob1 AS page, blob3 AS kind, blob4 AS action
FROM leaf_website_events
WHERE blob6 = '239383829012'
ORDER BY timestamp
```

For a dispatched agent, use a Cloudflare custom API token scoped to this account with
only `Account | Account Analytics | Read`; do not give it Workers, DNS, or zone
permissions. The token can call the
[Analytics Engine SQL API](https://developers.cloudflare.com/analytics/analytics-engine/sql-api/)
but cannot change the site's domains or deployment. Store that token and the account
id in the dispatch environment rather than in this repository. That permission can
read the account's other analytics datasets too; if that is broader than the agent
should see, put a fixed session-reference lookup endpoint in front of it instead of
handing the token to the agent.

Hosted turns also emit structured timing records under `component=leaf-agent`.
Every request record carries the page's public session reference and canonical event
id; the container continues with that event id through App Server availability, task
and turn start, first notification, first model activity, and completion. Leaf's
record omits message text, prompts, source IP keys, cookies, and private session ids.
Cloudflare wraps it in invocation metadata, so the raw Observability result or
`wrangler tail` stream is not a content-free agent interface.
`scripts/query-site-agent-logs.py` queries the last 24 hours for one exact event id and
emits only Leaf's declared diagnostic fields:

```sh
CLOUDFLARE_API_TOKEN=... uv run scripts/query-site-agent-logs.py EVENT_ID
```

Historical Worker and Container logs are available in Workers Observability because
`wrangler.toml` enables it. The query requires `Workers Observability Write`; the
Analytics-only token above can map a session reference to an event id but cannot read
runtime logs. A trusted agent host loads the diagnostic token into the query process
from its credential store rather than printing or persisting it. In Max's agent setup,
the `Cloudflare Leaf diagnostics` item in the `Max` 1Password vault carries the account
id and token. Raw live tailing additionally requires `Workers Tail Read` and remains an
operator-only diagnostic because its Cloudflare envelope includes request metadata.
The local end-to-end verifier prints the same container records and leaves them at
`.tmp/website-agent-local.log` for a later agent to inspect. It gives the child App
Server a temporary plugin-free `CODEX_HOME` seeded with copies of the host login and
website config, matching production without changing personal state.

When Leaf accepts a reader message that its canonical activity projection says needs
a response, the Worker starts one Cloudflare Workflow named with the public session
reference and event id. The reference also appears in Analytics Engine, so an operator
can start with the number the reader sees without exposing the private session cookie.
Its retryable steps reserve source capacity, then ask that reader's container to create or resume one Codex
App Server task rooted at the actual page directory and deliver the event through
Leaf's immutable delivery record, passed inline as structured `leaf_feedback`. The
website-specific App Server starts without the authoring plugin: its compact developer
instructions and the ready `$LEAF` CLI are the complete interface, so skill discovery
cannot turn a small reader response into a full authoring workflow. The hosted task can
revise `index.html`, validate it, append thread replies, and leave the page waiting. The
initiating App Server connection projects the turn's native activity notifications back
through Leaf. A repeated workflow sees the event's durable pickup and does not start
the work twice. Task startup failure after its retries and a failure while following a
started turn each append a short failure reply through the same event log.
Once App Server reports a terminal turn, the container closes that exact Leaf turn and
gives each accepted input the turn left unanswered its final assistant message. A failed
or interrupted turn gets a failure reply instead, and a completed turn with no message
at all gets a completed-without-reply receipt.

The container pins the Codex version its App Server protocol was tested against and
runs `gpt-5.6-luna` without a reasoning phase. The per-reader Cloudflare Container is the
tool sandbox: nested bubblewrap namespaces are unavailable in that environment, and
the model has no durable or cross-reader filesystem to reach. Public internet is off.
The container receives only a dummy OpenAI credential; a trusted Cloudflare outbound
handler permits the Responses API request and replaces that dummy value with the
Worker's `OPENAI_API_KEY`. The actual secret never enters model-visible processes or
files. One Cloudflare-native brake allows twenty task starts per source IP per minute
in each Cloudflare location and, under a separate key, twenty model calls per reader
container per minute. An over-limit turn receives a visible busy reply or a model-rate
error without sending anything to OpenAI. There is no site-wide quota.

Run the complete local site with Docker available:

```sh
cd worker
npm ci
npm run dev
```

The deploy requires a Cloudflare Workers Paid account with Containers enabled, a
`cloudflare-deploy` GitHub environment in `max-sixty/leaf` whose deployment branch
policy allows only `main`, and a `CLOUDFLARE_API_TOKEN` environment secret able to
deploy the Worker, container, and `leaf.page` custom domain. This is the same boundary
used by Tend: manual workflow dispatches from other branches cannot read the token. The
domain already uses Cloudflare nameservers; a successful deployment makes the Worker
the `leaf.page` origin. The deployed Worker also needs an `OPENAI_API_KEY` Wrangler
secret. Deployment checks that the binding exists before changing production, then
runs one private Codex turn through the public site and requires both its published
revision and reply. The workflow build is otherwise self-contained.

Create that GitHub boundary once, then enter the token when the last command prompts:

```sh
gh api --method PUT repos/max-sixty/leaf/environments/cloudflare-deploy \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api --method POST \
  repos/max-sixty/leaf/environments/cloudflare-deploy/deployment-branch-policies \
  -f name=main -f type=branch
gh secret set CLOUDFLARE_API_TOKEN \
  --repo max-sixty/leaf --env cloudflare-deploy
cd worker
npx wrangler secret put OPENAI_API_KEY
```

Create the token from Cloudflare's **Edit Cloudflare Workers** template, restrict it to
the account and the `leaf.page` zone, and add **Workers Containers: Edit** at the
account level. The stock template does not necessarily include the separate Containers
permission. The deploy workflow gives each build attempt its own release identity,
builds and pushes the container before it activates the Worker, and deploys the image
by its immutable registry digest. It then requests an immediate container rollout and
drives the public site in Chrome. The gate accepts only the exact build release: it
checks the passive edge presentation, immutable module URLs, absence of browser errors
and premature container allocation, then starts a fresh private container and verifies
that its state has the same release identity. A coherent old release cannot satisfy
the gate.
