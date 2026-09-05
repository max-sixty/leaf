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
`cloudflare-deploy` GitHub environment in `max-sixty/leaf`, and a
`CLOUDFLARE_API_TOKEN` environment secret able to deploy the Worker, container, and
`leaf.page` custom domain. The domain already uses Cloudflare nameservers; the first
successful Worker deployment replaces its GitHub Pages route. The workflow build is
otherwise self-contained.
