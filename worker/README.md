# Leaf website worker

The worker serves the product site from `.tmp/site` and forwards concrete example
routes to the canonical Python Leaf server in a Cloudflare Container. A secure,
HTTP-only cookie selects one short-lived container per browser session. Its copied
page directories and append-only logs are private to that reader and disappear when
the container is replaced; no website-only projection or persistence layer exists.

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
the `leaf.page` origin. The workflow build is otherwise self-contained.

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
```

Create the token from Cloudflare's **Edit Cloudflare Workers** template, restricted to
the account and the `leaf.page` zone. The deploy workflow verifies the public
`/examples/design-decision/api/state` response after Wrangler returns because a
Containers rollout can finish after the Worker itself becomes active.
