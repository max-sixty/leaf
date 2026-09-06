# Leaf website worker

The worker serves the product site from `.tmp/site` and forwards concrete example
routes to the canonical Python Leaf server in a Cloudflare Container. A secure,
HTTP-only cookie selects one short-lived container per browser session. Its copied
page directories and append-only logs are private to that reader and disappear when
the container is replaced; no website-only projection or conversation store exists.

When Leaf accepts a reader message that its canonical activity projection says needs
a response, the Worker starts one Cloudflare Workflow keyed by the browser session and
event id. The workflow has separate retryable generation and append steps. Generation
runs the Python OpenAI Agents SDK in the same container over a fresh reading of the
page and thread; append uses Leaf's ordinary reply writer with a deterministic attempt,
so a retry cannot duplicate a reply and a newer reader turn suppresses a stale one.
The initial agent uses `gpt-5.6-luna` without tools and can discuss a page but not edit
it. Leaf's page directory remains the only conversation authority, leaving tools,
handoffs, and page revisions as additions to the agent rather than a replacement
backend. If generation exhausts its retries, the workflow appends a short failure
reply so the reader is not left waiting on work that has already stopped.

The container still has public internet access disabled. Its OpenAI client targets the
private `http://openai.internal/v1` hostname; the container egress handler fixes that to
`https://api.openai.com` and injects the Worker's `OPENAI_API_KEY`, so the credential
never enters the container filesystem or process environment.

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
