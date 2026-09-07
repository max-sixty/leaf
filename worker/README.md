# Leaf website worker

The worker serves the product site from `.tmp/site` and forwards concrete example
routes to the canonical Python Leaf server in a Cloudflare Container. A secure,
HTTP-only cookie selects one short-lived container per browser session. Its copied
page directories and append-only logs are private to that reader and disappear when
the container is replaced; no website-only projection or conversation store exists.

When Leaf accepts a reader message that its canonical activity projection says needs
a response, the Worker starts one Cloudflare Workflow keyed by the browser session and
event id. Its retryable steps read a fresh page and thread from the container, run the
OpenAI Agents SDK in the Worker, then append through Leaf's ordinary reply writer. A
deterministic attempt prevents duplicate replies, and a newer reader turn suppresses a
stale one. If generation stops after its retries, the workflow appends a short failure
reply. A Cloudflare-native abuse brake allows one hundred model calls per source IP per
minute in each Cloudflare location; an over-limit turn receives a visible busy reply
without sending anything to OpenAI. There is no site-wide quota.

The initial agent uses `gpt-5.6-luna` without tools and can discuss a page but not edit
it. Leaf's page directory remains the only conversation authority, so tools, handoffs,
and page revisions extend the agent rather than replace its backend. The
`OPENAI_API_KEY` exists only as a Worker secret; neither public responses nor requests
to the internet-disabled container carry it.

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
secret. The workflow build is otherwise self-contained.

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
permission. The deploy workflow verifies the public
`/examples/design-decision/api/state` response after Wrangler returns because a
Containers rollout can finish after the Worker itself becomes active.
