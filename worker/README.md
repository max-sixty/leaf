# Leaf website worker

This README is the runbook for <https://leaf.page/>: credentials, running the site
locally, deploying, checking and rolling back a release, and reading its logs.
[`docs/website.html`](../docs/website.html) explains the design: published pages at the
edge, a private container per visitor, the hosted agent, releases, and how long a
visitor's state lasts.

The pieces this runbook names:

| Path                                               | What it is                                                                       |
| -------------------------------------------------- | -------------------------------------------------------------------------------- |
| `worker/src/index.ts`                              | The Cloudflare Worker: edge pages, routing to containers, the edge's log records |
| `worker/src/agent.ts`, `worker/src/model-proxy.ts` | The hosted agent's dispatch and its outbound OpenAI handler                      |
| `worker/leaf_website/`                             | The Python adapter each container runs in front of Leaf's server                 |
| `worker/wrangler.toml`                             | Production (`leaf-website`) and the `dev` environment (`leaf-website-dev`)       |
| `Dockerfile.website`                               | The container image                                                              |
| `.github/workflows/publish-site.yaml`              | The only production deploy                                                       |

`uv run leaf-dev site` builds the site into `.tmp/site`, with its edge assets in
`.tmp/site-assets` and the prepared Leaf installation the image installs in
`.tmp/site-install`.

## Credentials

Leaf uses three Cloudflare tokens, one for each holder. None is stored in this
repository, and each arrives as `CLOUDFLARE_API_TOKEN` wherever it is used. The
permissions below use the names Cloudflare's token API reports:

| Token                          | Reaches                                                                                                                                                                                                                                                   | Held by                                           |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `Leaf agent administration`    | `Individual Workers Editor` on `leaf-website` and `leaf-website-dev`; `Workers Routes Write` on the `leaf.page` zone; `Workers Containers Write`, `Workers Observability Read`, `Account Analytics Read`, and `Workers Metadata Read-Only` on the account | Agents on the maintainer's machine                |
| `Leaf release (CI)`            | `Individual Workers Editor` on `leaf-website`; `Workers Routes Write` on the `leaf.page` zone; `Workers Containers Write` and `Account Settings Read` on the account                                                                                      | `publish-site`, through the `release` environment |
| `Leaf observability (Tend CI)` | `Workers Observability Read` and `Account Analytics Read` on the account                                                                                                                                                                                  | Tend's agent, through the `tend` environment      |

The account also serves Workers and zones that are not Leaf's, so each token that edits
a Worker lists the Workers it may edit. `Individual Workers Editor` deploys and
configures the listed Workers, refuses every other Worker in the account, and cannot
delete one. Cloudflare keys that list to each Worker's script tag rather than its name,
so a Worker that is deleted and recreated needs its tokens re-scoped.

The account-wide permissions are the ones Cloudflare offers in no narrower form:
container images, the Observability query below, and Analytics Engine are account-level
APIs. A deploy to `workers.dev` also reads the account's `workers.dev` subdomain. Only
`leaf-website-dev` deploys there, so only the agent token holds
`Workers Metadata Read-Only`, which covers that read and no Worker's code. No token here
changes a Worker outside Leaf, reads another Worker's code, or manages DNS, members,
billing, or API tokens; changing a domain or creating a token takes the account owner's
own login.

A leaked agent or Tend CI token would expose logs: both read every Worker's
Observability records and every Analytics Engine dataset on the account, and the agent
token can open a live tail on any Worker. The Tend CI token sits in the job's
environment, which the agent inherits, so any code the agent runs can read it.
`.config/tend.yaml` therefore sets it only for agents answering an issue or a red run on
`main`. Reviews, mentions on pull requests, and the scheduled polls, including the
notifications poll that reviews fork pull requests, run with it empty. An agent answering an issue can still
fetch a pull request's code, and `running-tend` tells it to drop the token before
running that code. Nothing enforces that instruction. In yolo mode, code Tend merges to
`main` can run in a later job that holds the token.

On the maintainer's machine, the `Cloudflare Leaf agent administration` item in the
`Max` 1Password vault holds the agent token. Load it with the 1Password service account,
which needs no approval, straight into the process that uses it, and never print it or
write it to a file:

```sh
export CLOUDFLARE_API_TOKEN=$(~/.claude/skills/using-1password/scripts/op-read.sh \
  "op://Max/Cloudflare Leaf agent administration/credential")
```

A bare `op` command signs in as the person and waits for an approval that an
unattended session cannot give.

## Local development

Run the complete site through a local Worker and container from the repository root,
with Docker running:

```sh
pnpm install --frozen-lockfile
pnpm run site:dev
```

To reproduce a deploy-gate failure, build the site and run the gate's checks through
the local Worker and container:

```sh
uv run leaf-dev site
uv run leaf-dev verify-site website-worker
uv run leaf-dev journey website-worker
```

`verify-site website-worker` checks the release `leaf-dev site` built, as
`publish-site` does before it deploys, and `journey website-worker` runs the agent
journey that `publish-site` runs against <https://leaf.page/> after it deploys. Neither
builds the site, so rerun `leaf-dev site` after a change.

When the agent's environment cannot access Docker, `verify-website` can run this
build and local verifier on its GitHub runner, without deploying or running the
product suites. Replace `YOUR_BRANCH` with the branch to verify:

```sh
gh workflow run verify-website --ref YOUR_BRANCH
```

Read the run's `website` job and confirm its head SHA matches the intended revision.
The `website-verification-<run>-<attempt>` artifact retains the Worker/container log
and any completed startup profile. The ordinary PR gate still runs the verifier;
this dispatch supplies the same check when a reproduction needs its own runner.

For a quicker check of the agent alone, `uv run leaf-dev journey website-adapter` runs
one real agent turn against the adapter on this machine, without the Worker, container
limits, credential proxy or Docker. It uses a temporary `CODEX_HOME` with the
website's Codex config and shares the host's Codex login. It prints the container's
records and keeps them, with the plugin install's output, under
`.tmp/verify-site/run-*/` (`website-adapter.log`, `plugin-install.log`). In its JSON
result, `sinceSendMs.responseVisible` is when the
open Threads view first showed a non-empty agent reply; `sinceAdmissionMs.replied` is
when the container admitted that reply, not when the user could see it.

## Dev environment

`leaf-website-dev`, at <https://leaf-website-dev.maxsixty.workers.dev>, runs the same
Worker, container image, credential proxy, and agent journey as production. It has its
own Worker, container application, Durable Objects, and Analytics Engine dataset
(`leaf_website_events_dev`), and shares only the rate-limit namespace with production.

Deploy the current checkout, uncommitted changes included:

```sh
pnpm run deploy:dev
```

The command needs `CLOUDFLARE_API_TOKEN` (see [Credentials](#credentials)). It builds
the site with a release id derived from `HEAD` and the working tree, deploys only the
`dev` environment, runs `leaf-dev verify-site` with `--wait 900` until that release
answers, and then runs `leaf-dev journey` against it. Wrangler secrets do not carry
across environments, so if the dev Worker has no `OPENAI_API_KEY` secret yet, pass it
on the first deploy:

```sh
CLOUDFLARE_API_TOKEN=... OPENAI_API_KEY=... pnpm run deploy:dev
```

## Production deploy

A push to `main` that changes the site runs `publish-site`; the workflow's `paths`
list says which files count. To redeploy `main` without a new commit:

```sh
gh workflow run publish-site.yaml --repo max-sixty/leaf --ref main
```

The workflow:

- builds the site with a release id unique to the commit and run attempt;
- runs `pnpm run check:worker` and `leaf-dev verify-site website-worker`;
- builds and pushes the container image, and pins it in `wrangler.toml` by its registry
  digest;
- deploys the Worker with `--containers-rollout=immediate`;
- runs `leaf-dev verify-site --release <id> --wait 900` against <https://leaf.page/>,
  which passes only once Chrome sees that release in the edge document, its module
  URLs, and a newly started private container, with no browser errors;
- runs `leaf-dev journey https://leaf.page --release <id>`, which needs a hosted agent
  to answer a real turn with a reply and a published revision.

Cloudflare activates the Worker before the new container image has rolled out. Until
it has, a container on the previous release answers, the Worker replaces that answer
with the published state or a `503` with `Retry-After`, and the `--wait` reruns the
check.

### One-time setup

The deploy needs a Cloudflare Workers Paid account with Containers enabled, and an
`OPENAI_API_KEY` Wrangler secret on the Worker; the deploy checks that the secret exists
before it changes production. The `leaf.page` domain already uses Cloudflare
nameservers, and the Worker serves it as a custom domain.

In GitHub, the `release` environment holds `Leaf release (CI)` as
`CLOUDFLARE_API_TOKEN` and the dependency-bundle publisher's bot token as
`BUNDLE_PUBLISH_TOKEN`. Deployment and publishing jobs share this environment and
can access both credentials. The `tend` environment holds `Leaf observability
(Tend CI)` as `CLOUDFLARE_API_TOKEN`. Each environment's deployment-branch policy allows only `main`,
so a workflow dispatched from another branch cannot read these credentials. The policy is not
an approval gate: in yolo mode, the next `publish-site` run deploys code Tend merged to
`main` with the deploy token.

Create the environment and secrets once; each `secret` command prompts for its value:

```sh
gh api --method PUT repos/max-sixty/leaf/environments/release \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api --method POST \
  repos/max-sixty/leaf/environments/release/deployment-branch-policies \
  -f name=main -f type=branch
gh secret set CLOUDFLARE_API_TOKEN \
  --repo max-sixty/leaf --env release
gh secret set BUNDLE_PUBLISH_TOKEN \
  --repo max-sixty/leaf --env release
gh secret set CLOUDFLARE_API_TOKEN \
  --repo max-sixty/leaf --env tend
pnpm exec wrangler secret put OPENAI_API_KEY --config worker/wrangler.toml
```

Create each token from **Manage Account → Account API Tokens** with exactly the
permissions in the [Credentials](#credentials) table, scoping Workers to the named
Workers rather than all of them. Cloudflare refuses a per-Worker scope on a user-owned
token.

## Check a deployed release

A page's response names the release the edge serves in its `Leaf-Release` header:

```sh
curl -sI https://leaf.page/ | grep -i leaf-release
```

To re-run the deploy's checks against what is live:

```sh
uv run leaf-dev verify-site https://leaf.page --release <release>
uv run leaf-dev journey https://leaf.page
```

`verify-site` with no `--release` requires the release of the local `.tmp/site` build,
so pass the live one. `journey` without `--release` accepts whichever release the site
serves; it runs a real hosted turn, which spends the production OpenAI key and counts
against the rate limits below.

## Roll back

Revert the change on `main` and land the revert. The revert touches the same files, so
its push runs `publish-site`, which deploys it as a new release through the same checks.
A release starts new containers, so every visitor's private state resets, as on any
deploy.

Do not use `wrangler rollback`. It reactivates an earlier Worker version, whose assets
name the earlier release. Cloudflare's rollback documentation says resources connected
to the Worker are not changed and does not mention containers, so expect the container
image to stay on the newer release. Every container would then name a release other than
the Worker's, and the Worker answers each private request with `503` (`rollingOut` in
`worker/src/index.ts`), so no visitor could comment or act until the next deploy.

## Diagnostics

Workers Observability holds the operational logs; Analytics Engine holds only
aggregate product events. Each record type below has a `component` field:

| `component`        | Written by           | One record per                                                       |
| ------------------ | -------------------- | -------------------------------------------------------------------- |
| `leaf-startup`     | Worker               | Public document load                                                 |
| `leaf-page-error`  | Worker               | Runtime fault reported from a page the visitor has not changed yet   |
| `leaf-interaction` | Worker               | Batch of browser interaction metadata                                |
| `leaf-agent`       | Worker and container | Step of a request or hosted turn, and each `500` the adapter answers |

Workers Logs keeps records for at most seven days; a page directory's own `events.jsonl`
lasts as long as its container. TODO(2026-09-25): Export interaction records to durable
storage if they need to outlive [Workers Logs
retention](https://developers.cloudflare.com/workers/observability/logs/workers-logs/).

For a live incident, stream records with the agent token:

```sh
pnpm exec wrangler tail --config worker/wrangler.toml
```

### Find a session's records

A user reports the 12-digit session reference the leaf's menu copies, the session's
public `reference`. It is a support handle, stable for the browser identity's lifetime, and no
endpoint accepts it as identity. Start from it:

1. Run the [support query](#product-events) to get the session's accepted events, each
   with its `timestamp` and event id (`index1`).
2. Query Observability from one minute before an event's timestamp to twenty minutes
   after it, with `lookup_key=reference` and that number as `lookup_value`. Change
   `component` in the filter to the record type you need.
3. For one request, query again with `lookup_key=eventId`. The event id follows a
   request across the Worker and container datasets.
4. For the model calls of a turn, take `turnId` from that request's
   `turn_start_acknowledged` record and query with `lookup_key=turnId`.

```sh
account_id=ece2539b9b32ab59dd74aa6b6285e5db
lookup_key=eventId
lookup_value=...
from_ms=...
to_ms=...

jq -n \
  --arg lookup_key "$lookup_key" \
  --arg lookup_value "$lookup_value" \
  --argjson from "$from_ms" \
  --argjson to "$to_ms" \
  '{queryId:"leaf-agent-diagnostic",timeframe:{from:$from,to:$to},view:"events",limit:100,parameters:{datasets:[],filterCombination:"and",filters:[{key:"component",operation:"eq",type:"string",value:"leaf-agent"},{key:$lookup_key,operation:"eq",type:"string",value:$lookup_value}]}}' \
| curl --fail-with-body --silent --show-error \
    --request POST \
    --header "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    --header "Content-Type: application/json" \
    --data-binary @- \
    "https://api.cloudflare.com/client/v4/accounts/$account_id/workers/observability/telemetry/query"
```

`from_ms` and `to_ms` are Unix milliseconds. Filter on a structured field as above;
Cloudflare's free-text `needle` does not reliably match values inside structured logs.
Check that `result.statistics.abr_level` is `1`. Any other value means Cloudflare
sampled the result and records may be missing, so narrow the window and query again.

### Product events

Each accepted browser event also writes one data point to the `leaf_website_events`
Analytics Engine dataset, without event content, widget ids, IP addresses, or cookies:

| Field     | Value                                   |
| --------- | --------------------------------------- |
| `index1`  | Event id                                |
| `blob1`   | Public page route                       |
| `blob2`   | `product` or `example`                  |
| `blob3`   | Event kind                              |
| `blob4`   | Action verb, when present               |
| `blob5`   | Site release id                         |
| `blob6`   | The session's 12-digit public reference |
| `double1` | Page revision, or `0` when absent       |
| `double2` | `1` when the event needs an agent reply |

Send a query to Cloudflare's Analytics Engine SQL API as the request body:

```sh
curl --fail-with-body --silent --show-error \
  --header "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  --data-binary @query.sql \
  "https://api.cloudflare.com/client/v4/accounts/$account_id/analytics_engine/sql"
```

The support query, for one session:

```sql
SELECT timestamp, index1 AS event, blob1 AS page, blob3 AS kind, blob4 AS action
FROM leaf_website_events
WHERE blob6 = '239383829012'
ORDER BY timestamp
```

A retry of an accepted browser request writes the same event id again, so count
distinct ids:

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

### Browser startup records

Each public document's inline bootstrap reports one `component=leaf-startup` record,
also when the module graph fails to load. The deployed Worker logs it; the container
never sees it, and a site served by `leaf_website` alone (the test suite, a local
preview) acknowledges the report and keeps nothing. Filter by `reference`, `route`,
or `loadId`. Browser evidence comes from the native request record described below.

| Field                                               | Meaning                                                                                                                                                                                                    |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `route`, `release`, `currentRelease`                | The page, the release its document names, and the release the edge serves                                                                                                                                  |
| `navigationType`                                    | How the load began                                                                                                                                                                                         |
| `serverMs`, `firstByteMs`, `firstContentfulPaintMs` | Worker time, network time to the first byte, and first paint                                                                                                                                               |
| `upgradedMs`                                        | First widget upgrade in the body                                                                                                                                                                           |
| `firstStateResponseMs`                              | First completed `api/state` response for the page (Resource Timing `responseEnd`)                                                                                                                          |
| `presentedMs`                                       | When authoritative state or the offline fallback presented                                                                                                                                                 |
| `outcome`                                           | How the record closed: `presented`, `failed` (the page reported it could not start), `timeout` (fifteen seconds passed without widget upgrade or a declared failure), or `abandoned` (the user left first) |
| `reason`                                            | What went wrong during startup, when anything did                                                                                                                                                          |

`serverMs` is how long the Worker took to answer, from its `Server-Timing` header. Every
other time is milliseconds since navigation started. A time not observed is `null`.
Widgets can upgrade while the first saved-state response still waits. The page
presents after the state answer is applied, except that the offline fallback can
present authored content with `firstStateResponseMs: null`.

`upgradedMs` says when the interface became usable, including new comments while
saved state loads. `presentedMs` says when that read answered or failed; `outcome`
says only how the record closed. A healthy state read can take more than fifteen
seconds after upgrade without reporting a startup timeout.
A page that presents while a native subresource still loads closes after native
load, or as `abandoned` if the user leaves first, with `presentedMs` set.

`reason` is at most 300 characters: the entry module or theme that failed to load, the
message and source position of a script that threw before upgrade, or what the
runtime said when it reported it could not start. A page that recovers and presents
still carries it, so these records find faults in browsers this repository cannot run.
Apart from `reason`, the record holds no page content, URL details, cookies, IP
addresses, or private session id. `reason` is the runtime's own words, but an exception
thrown while handling a value can quote that value, so treat `reason` as possibly
containing user text.

### Browser evidence

Cloudflare's native invocation record owns the request headers. For a startup or
passive page-fault record, take `$metadata.traceId`, then query that trace's
`cf-worker-event` record. Its `$workers.event.request.headers` holds the raw
`user-agent` and any `sec-ch-ua`, `sec-ch-ua-platform`, and `sec-ch-ua-mobile` values.
Interpret those as reported evidence: UA tokens need not identify a unique browser,
client hints may be absent, and hint brand lists may contain synthetic brands.
Leaf derives no browser family, version or platform and requests no extra hints.

Using the token and account from [Find a session's records](#find-a-sessions-records),
query a narrow window around the diagnostic's timestamp:

```sh
trace_id=...
from_ms=...
to_ms=...

jq -n \
  --arg trace_id "$trace_id" \
  --argjson from "$from_ms" \
  --argjson to "$to_ms" \
  '{queryId:"leaf-browser-evidence",timeframe:{from:$from,to:$to},view:"events",limit:100,parameters:{datasets:[],filterCombination:"and",filters:[{key:"$metadata.traceId",operation:"eq",type:"string",value:$trace_id},{key:"$metadata.type",operation:"eq",type:"string",value:"cf-worker-event"}]}}' \
| curl --fail-with-body --silent --show-error \
    --request POST \
    --header "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
    --header "Content-Type: application/json" \
    --data-binary @- \
    "https://api.cloudflare.com/client/v4/accounts/$account_id/workers/observability/telemetry/query"
```

The native headers are at
`.result.events.events[]["$workers"].event.request.headers` in the response. To start
with a browser instead, use a substring filter on native
`$workers.event.request.headers.user-agent` or a client-hint header, then query their
trace IDs for startup or fault records. These occasional investigations take two
queries; the semantic records do not duplicate the headers.

Production and `dev` enable [Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)
and explicitly keep invocation logs enabled in `worker/wrangler.toml`; head
sampling defaults to 100%. All logs for a sampled request are collected together and share the same retention
(at most seven days). Check `result.statistics.abr_level` is `1` and narrow the
query window if needed; a sampled query, a truncated log, or an expired record is
not evidence that a browser sent no header. Request headers can contain OS,
device and full-version detail; they are client-reported, not verified identity.

### Page faults

A runtime fault after startup, such as a code block that fails to highlight, reaches
the server as a page `error` event (`reportPageError`). While the session has not
changed the page, the Worker logs it as `component=leaf-page-error`,
`event=browser_page_error` and starts no container. The record carries `reference`,
`route`, the document's `release`, the edge's `currentRelease`, the document
`revision` and the first 300 characters of the runtime's message as
`reason`, which may contain user text as above. The agent never sees these faults, even
after the visitor's first comment activates the session. Once the page is active, its
faults go to the container like any other event.

### Interaction batches

The Worker accepts `POST api/interaction` and logs each valid batch as one
`component=leaf-interaction`, `event=client_batch` record. A batch holds at most 100
entries and 128 KiB of JSON, which leaves room for request metadata under Cloudflare's
[256 KiB log
limit](https://developers.cloudflare.com/workers/platform/limits/#log-size).
`worker/src/interactions.ts` lists exactly which fields a record keeps.

A record carries the session `reference`, page `route`, site `release`, tab `session`,
and the ordered interaction metadata: event type, browser `observed_at` and
`monotonic_ms`, sequence, visibility, pointer coordinates, element tags and positions,
per-tab node ids, command ids and bindings, and response kinds and statuses. The
Cloudflare record supplies receipt time. Timing entries retain generated input/reply
identities, command attempts, presentation kind and surface without message text.
Sample lifecycle entries keep their phase, host, allocation and
revisions, elapsed time, admission status, reload flag, retirement reason, release
operation, and error name and status. The Worker drops element ids and names, labels,
typed, pasted and selected text, URL details, template ids, exception messages, stacks,
response bodies, and fields it does not recognize. An observation over 40 KB becomes one
`interaction_omitted` entry with its original type, byte count and reason. No
transport or reader splits or reconstructs diagnostic observations; the page's
`events.jsonl` owns admitted message content.

A live sample, an embedded child page, sends its batches to its container first, which
checks the sample's capability. The Worker logs the batch only after the container
answers `204`, and the record carries `sampleReference` in place of `reference`. A
batch the container refuses writes no record; a batch the container accepted but the
Worker finds out of bounds also writes none, and the browser still gets the `204`, so it
does not retry. Follow a parent's lifecycle entry to its child's batches with
`lookup_key=sampleReference`; a nested sample's lifecycle entry names the next child's
reference the same way.

`sampleReference` and `documentReference` are 12-digit support handles, as the session
reference is: the Worker reads the 32-hex sample capability or private document UUID as
a hexadecimal integer, takes it modulo 1,000,000,000,000, and pads it to 12 digits.
Neither raw identity is logged, and no endpoint accepts a handle as a capability. The
container also keeps each child's full interaction records in the parent page's
directory, where each record's `page` is the child's full path relative to that
directory.

### Hosted turns

`component=leaf-agent` records time each request and hosted turn. Every record on a
request's path carries its event id, and the Worker's records also carry `reference` and
`route`. Leaf's fields never include message text, prompts, item content, source
addresses, cookies, or private session ids; Cloudflare wraps each record in its own
invocation metadata. The container's records follow the event through App Server
startup, task and turn start, each App Server item's start and completion (type,
duration, and command outcome, without content), first model activity, and turn
completion.

The records to read first:

| Record                                                                   | Says                                                                                                                                                                         |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `event_accepted`                                                         | The Worker accepted an event that needs a reply and is dispatching it; carries `eventId`                                                                                     |
| `container_start_failed`                                                 | The turn could not be started; the Worker and the container each write one from their side                                                                                   |
| `turn_start_acknowledged`                                                | App Server started the turn; carries Codex's `turnId`                                                                                                                        |
| `turn_delivery_bound`                                                    | The Leaf turn opened for that Codex turn                                                                                                                                     |
| `turn_reply_first_text_published`                                        | The turn's first words reached the user's thread, its opening line or its answer, the first thing the user sees                                                              |
| `turn_stream_completed`                                                  | The turn ended, whether it finished, lost its connection, went silent, or failed; carries status, fault, `modelRequests`, `inputTokens`, `cachedInputTokens`, `outputTokens` |
| `turn_reply_published`                                                   | A completed reply update was published; carries item identity and phase, without text                                                                                        |
| `turn_following_ended`                                                   | Follower cleanup and continuation ended; `completed` is false if that work raised                                                                                            |
| `turn_reply_commit_failed`                                               | Leaf could not validate or append the reply                                                                                                                                  |
| `turn_interrupted`, `turn_interrupt_failed`                              | The container stopped a turn it could no longer follow, or App Server refused, usually because the turn had already ended                                                    |
| `turn_abandoned_interrupt_started`, `turn_abandoned_interrupt_completed` | The same for a turn found running on a resumed thread                                                                                                                        |
| `turn_failure_reported`                                                  | How many of the turn's updates got a failure receipt, and how many could not; absent when the turn answered everything                                                       |
| `turn_receipt_refused`                                                   | The page refused a failure receipt                                                                                                                                           |
| `container_continuation_receipted`                                       | The container wrote `startup_failed` for a waiting message it could not start, and whether that settled it                                                                   |
| `thread_title_generated`, `thread_title_skipped`, `thread_title_failed`  | The title request for an untitled thread                                                                                                                                     |
| `page_fault`                                                             | The adapter answered `500`: route, method, page path, exception class, and `detail`                                                                                          |

The session's `component=leaf-container`, `event=http_error` records identify
forwarded HTTP 5xx responses by status, method and `source`: `adapter` means the
response carried Python's `Leaf-Release` stamp; `disconnected` means it matched
the Containers SDK's fixed connection-loss response; `unclassified` means neither
was established. These records retain no URL or response body. Use their native
trace ID to join the request's invocation records. A `disconnected` response
identifies the proxy boundary, not why its container connection was lost.

The page's private `observations.jsonl` also records these hosted-turn boundaries.
Only that private diagnostic stream retains the complete published reply updates,
including the opening before a final answer replaced it. Developer response evals
query that stream through `read_interactions`; they install no observer inside the
adapter. `turn_stream_completed` precedes reply accounting; `turn_following_ended`
follows cleanup and scheduling, so the former alone does not establish completion.

A failure record carries `error`, the exception's class, and `detail`, the message the
refusing code wrote, cut to its last 500 characters with a leading ellipsis. A
`thread_title_failed` record cuts `detail` to its last 500 characters with no ellipsis,
and a title request the page refused carries no `detail`, because the refusal can quote
the title, whose words come from the user's. A
`page_fault` `detail` can quote a value the user entered, so treat it as possibly
containing user text.

The outbound model handler adds `model_request_started`, `model_response_headers`,
`model_response_first_byte`, `model_response_first_output`, and
`model_response_completed` or `model_request_failed`, each with Codex's thread and turn
ids, a per-request id, status, and byte count. The hosted Codex provider uses HTTP
directly (`codex-config.toml`).

When a hosted turn cannot answer, the user's update gets a failure receipt: a reply
carrying `failure` in its thread for a message, or a failed pickup for an answer to an
ask, which leaves the answer in force and lets the user answer again
(`fail_answer` in `src/leaf/thread.py`). The receipt's `failure` field holds one of three codes, and
`worker/leaf_website/__init__.py` declares the words the user reads for each in
`FAILURE_RECEIPTS`:

| Code             | Written by                                                           | When                                             |
| ---------------- | -------------------------------------------------------------------- | ------------------------------------------------ |
| `rate_limited`   | Worker                                                               | The source address was over its task-start limit |
| `startup_failed` | Worker, or the container for a message it took up after a turn ended | The turn could not be started                    |
| `turn_failed`    | Container                                                            | A turn it followed ended without an answer       |

`leaf-dev journey`, the deploy's last check, fails on the first failure receipt.

The Worker starts each turn inside the request's `waitUntil`, which Cloudflare allows
30 seconds. The accepted event is durable; the running turn is not, and nothing
recovers a start that outlasts that window.

## Configuration

### Saved state and capacity

Read-only visits do not prewarm a container. The existing session Durable Object
serves saved documents, comments, choices and private resources while compute is
stopped. A write or a missing saved response starts Python, which restores the
canonical page record before accepting requests. `leaf_website.storage` publishes
canonical files and matching Python-produced responses atomically before a write
is acknowledged; a failed publication fails the request and permits an idempotent
retry. File modification dates survive restore, including the publication date of
an unstamped revision. A release selects fresh demo records, while container
replacement preserves the current release's records. `docs/website.html`, **Private sessions**, owns the
storage and identity contract.

The append lease admits one staged successor per page. Preparation stores its descriptor
and returns its content identity plus missing chunk digests. Commit names that identity;
the stored descriptor supplies every file and response reference. Identical preparations
share an identity; different content replaces it. Commit checks the stored page and
release against the current site manifest before promotion. Replacing or committing it
collects chunks no committed record, staged successor, delivery stream or restore
snapshot uses.
An interrupted upload therefore retains at most one successor until that page
retries; other pages' concurrent uploads and readers remain protected.

`max_instances` caps concurrent `basic` containers: 5,900 for production and 90 for
`dev`, under Cloudflare's account limit of 6,000. A container with no requests stops
after ten minutes (`sleepAfter` in `worker/src/index.ts`). During a rollout, Cloudflare
replaces an active container after at most `rollout_active_grace_period`, 600 seconds.

### Sandbox and rate limits

The container pins the Codex version in `package.json` and runs `HOSTED_MODEL`
(`worker/leaf_website/__init__.py`) at low reasoning effort. The per-user container is
the agent's sandbox, and Codex runs with `danger-full-access` because the container's
kernel does not permit Codex's nested bubblewrap namespaces. Internet access is off,
and the model can reach no durable filesystem and no other user's. The container holds
a dummy OpenAI key; the Worker's outbound handler lets through only Responses API
requests to `api.openai.com` and replaces the dummy with the real `OPENAI_API_KEY`
secret, which never enters the container.

One Cloudflare rate limiter, `SOURCE_AGENT_RATE_LIMITER`, allows twenty per minute in
each Cloudflare location, counted separately for each key: task starts per source
address, prewarms per source address, and model calls per container. An over-limit
start gets the `rate_limited` receipt and an over-limit model call a `429`, and neither
reaches OpenAI. There is no site-wide quota.
