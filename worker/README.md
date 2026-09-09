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

The deployment admits up to 15,000 concurrent `lite` containers. After a session is
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
| `double1` | Page revision, or `0` when absent |
| `double2` | `1` when the event needs an agent reply |

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

When Leaf accepts a reader message that its canonical activity projection says needs
a response, the Worker starts one Cloudflare Workflow keyed by the browser session and
event id. Its retryable steps ask that reader's container to create or resume one Codex
App Server task rooted at the actual page directory and deliver the event through
Leaf's ordinary `leaf-delivery` record. Codex loads the shipped Leaf plugin and uses its
native filesystem tools, so the hosted task can revise `index.html`, validate it, append
thread replies, and leave the page waiting exactly as a local Leaf task does. The
initiating App Server connection projects the turn's native activity notifications
back through Leaf. A repeated workflow sees the event's durable pickup and does not
start the work twice. If task startup stops after its retries, the workflow appends a
short failure reply through the same event log. Once App Server reports a terminal
turn, the container closes that exact Leaf turn and gives each accepted input the turn
left unanswered either a failure reply or a completed-without-reply receipt.

The container pins the Codex version its App Server protocol was tested against and
runs `gpt-5.6-luna` at low reasoning effort. The per-reader Cloudflare Container is the
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
