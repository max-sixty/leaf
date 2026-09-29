# Subject: session store migration review

Write this up as a page for me. It's the review I'll send to the platform team before
Thursday's decision; they read it top to bottom and reply with comments.

## Working notes

**Question.** Should we move web sessions off the Redis cluster `sess-redis-prod` and,
if so, onto what? The cluster's memory is at 81% of its 64 GB, the vendor contract for
the managed Redis renews on 1 November at +38%, and logout-everywhere has been
unreliable since the June incident.

**What I measured (14–27 September, production, all regions).**

- Median session read: 0.4 ms. p95: 1.9 ms. p99: 7.8 ms, driven by evictions during
  the 02:00 UTC batch window.
- 312k active sessions at the daily peak; 1.9M sessions total in the keyspace, 71% of
  them idle for more than 7 days but not yet expired (TTL is 30 days).
- Logout-everywhere took effect within 1 s in 96.1% of 4,210 requests; the other 3.9%
  took up to 90 s because replicas lag during failover.
- Two failovers in the window (17 Sept, 23 Sept), each dropping 0.3% of sessions.

Daily p95 read latency in ms, 14–27 Sept:

```
day,p95_ms
14,1.7
15,1.8
16,1.8
17,3.9
18,1.9
19,1.8
20,1.7
21,1.7
22,1.8
23,4.4
24,1.9
25,1.8
26,1.7
27,1.8
```

**Options.**

1. *Stay on managed Redis, shorten TTL to 7 days.* Frees about 70% of memory, so no
   resize. Cost goes up 38% at renewal regardless. Does nothing for logout lag.
2. *Postgres (`accounts-db`), sessions table with an index on user id.* Logout is one
   `DELETE … WHERE user_id = $1`, consistent immediately. Read p95 in a load test was
   3.1 ms (vs 1.9 ms now). Adds ~9k QPS to a database at 40% CPU. Cost: roughly zero
   marginal. Migration: dual-write for 30 days, then cut reads over.
3. *Signed stateless tokens (15 min) plus a revocation list in Postgres.* No session
   reads on the hot path at all. Logout-everywhere waits up to 15 minutes unless every
   service checks the revocation list, which puts us back at option 2's read load.
   Largest change: every service that reads a session changes.

| | Stay on Redis | Postgres | Stateless + revocation |
|---|---|---|---|
| Read p95 | 1.9 ms | 3.1 ms | 0 ms (hot path) |
| Logout-everywhere | lags up to 90 s | immediate | up to 15 min, or option 2's load |
| Yearly cost | $148k | ~$0 marginal | ~$0 marginal |
| Services changed | 0 | 1 (auth) | 23 |
| Migration length | none | 30 days dual-write | 1–2 quarters |

**Risks.**

- Postgres: `accounts-db` hits 55% CPU at peak under the load test; our alert fires at
  70%. The 02:00 batch window overlaps with vacuum on the accounts table.
- Postgres: a bad index or bloat makes every request slow, not only logins.
- Stateless: the 15-minute window is a security-review finding waiting to happen.

**Plan if we pick Postgres.**

1. Create `sessions` table and index; ship dual-write behind a flag (1 week).
2. Backfill the 312k sessions active in the last 7 days; let older ones lapse.
3. Dual-write for 30 days, comparing reads in shadow mode.
4. Cut reads over region by region, us-east last.
5. Downsize the Redis cluster to cache-only, renegotiate at the smaller tier.

**My recommendation.** Postgres. The latency cost is 1.2 ms at p95, which no page
budget notices; the logout fix is the thing security has asked for twice. Need the
team to pick one of the three, and the database owners to say whether 55% peak CPU is
acceptable.
