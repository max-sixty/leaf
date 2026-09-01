Subject: a capacity report on the `ledger` Postgres cluster, for the team lead. Present it as a Leaf page. The numbers come from a week of `pg_stat` samples and the connection pooler's logs.

Findings, in the order the analysis reached them:

1. Query volume grew 2.4× over the quarter while the instance size stayed the same. A weekly chart of queries per second, Jan to Mar: 1,400 → 1,900 → 2,600 → 3,400. Median latency is flat; p99 doubled in March.

2. Connections sit at 82% of `max_connections` (410 of 500) at the daily peak, and the last three p99 spikes each coincide with a peak above 470. Each API pod opens its own pool of 20, and there are 21 pods.

3. Disk is not the constraint: 61% used, growing 1.2% a month, and the largest table's bloat is 9%. Autovacuum keeps up. No decision here.

4. The read replica serves 3% of reads because only the reporting job is pointed at it. Moving the four read-only API endpoints there would take ~800 qps off the primary.

5. Timeline of the three p99 spikes with the connection count at each, and the pooler-log excerpts, as evidence that can stand collapsed.

Decisions the lead must make:

- On connections (finding 2): (a) put a shared connection pooler (pgbouncer) between the pods and the primary (effort medium, cuts server connections to ~60, analyst's recommendation, needs a two-hour maintenance window), (b) raise `max_connections` to 1,000 (effort low, costs ~4 GB of RAM at peak, buys a quarter), (c) shrink each pod's pool to 8 (effort low, no window, risk of pod-side queueing during bursts).
- On the replica (finding 4): (a) route the four endpoints to the replica now (effort low, recommendation; replica lag is under 200 ms), (b) wait until the pooler is in and route through it (effort low later, keeps one change at a time).
