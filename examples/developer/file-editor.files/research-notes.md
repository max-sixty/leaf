# Cold-start notes

Questions this week: why does the first request after a deploy take 4 s, and does
warming the connection pool fix it?

## Measurements

- First request after deploy: 3.8 s, 4.1 s, 4.4 s (three deploys, staging).
- Second request: 180–220 ms.
- With the pool warmed at startup: 640 ms first request, same second request.

## What the 4 s is

Most of it is TLS to the database proxy: 2.9 s of the 4.1 s in the trace from the
second deploy. The proxy resolves its own upstream on the first connection, and
that lookup has no cache until it succeeds once. The trace's spans, from the API pod:

```bash
kubectl logs deploy/api --since=10m | grep -E 'tls_handshake|first_request'
```

## Open

- Does the proxy's lookup cache survive a pod restart, or only a connection?
- Warming saves $`4.1 - 0.64 \approx 3.5`$ s on each pod's first request and adds
  700 ms to readiness. Is that worth it on every deploy, or only for the API pods?
