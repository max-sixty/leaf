# Subject: payments alert thresholds

payments-api's six alerts move to the new paging policy on Monday. Make me a page where
I can set each alert's threshold and whether it pages on-call, opens a ticket or is
off, and see what each setting would have done over the last 30 days. I'll tune them,
then tell you the final settings to apply.

## What on-call asked for

At most 10 pages a month for payments, and every page should be a real incident.
Anything real but not urgent should be a ticket. Payments is on call 24/7; there are
no quiet hours.

## The alerts

Each candidate threshold shows how often it would have fired between 12 September and
11 October, and how many of those firings were real incidents. Today's setting is
marked.

**payments-5xx-rate** — share of requests returning a 5xx, over 5 minutes. Today:
over 1%, pages.

| Threshold | Fired | Real |
|---|---|---|
| over 0.5% | 31 | 3 |
| over 1% (today) | 12 | 3 |
| over 2% | 4 | 3 |
| over 5% | 1 | 1 |

Over 5% would have missed the 19 September partial outage and the 26 September
card-network incident.

**payments-p99-latency** — p99 latency over 10 minutes. Today: over 800 ms, pages.

| Threshold | Fired | Real |
|---|---|---|
| over 600 ms | 44 | 2 |
| over 800 ms (today) | 19 | 2 |
| over 1,200 ms | 5 | 2 |
| over 2,000 ms | 0 | 0 |

**card-auth-decline-spike** — card authorization declines against their 7-day
baseline, for 15 minutes. Today: over 2× baseline, opens a ticket.

| Threshold | Fired | Real |
|---|---|---|
| over 1.5× | 9 | 1 |
| over 2× (today) | 3 | 1 |
| over 3× | 1 | 1 |

**webhook-backlog** — undelivered merchant webhooks in the queue. Today: over 5,000,
pages.

| Threshold | Fired | Real |
|---|---|---|
| over 1,000 | 22 | 0 |
| over 5,000 (today) | 6 | 1 |
| over 20,000 | 1 | 1 |

**ledger-reconciliation-lag** — minutes since the last successful ledger reconciliation
run. Today: over 90 minutes, off (disabled in August after a noisy weekend).

| Threshold | Fired | Real |
|---|---|---|
| over 60 min | 14 | 2 |
| over 90 min (today) | 7 | 2 |
| over 180 min | 2 | 2 |

Both real firings were reconciliation runs that silently stopped; finance found them
two days later.

**gateway-cert-expiry** — days until the payment gateway's TLS certificate expires.
Today: under 14 days, opens a ticket.

| Threshold | Fired | Real |
|---|---|---|
| under 30 days | 1 | 1 |
| under 14 days (today) | 1 | 1 |
| under 7 days | 1 | 1 |

It fires once per renewal whatever the threshold; only the warning time changes.

## Today's totals

The three paging alerts paged 37 times in the 30 days (12 + 19 + 6); 6 of those were
real.
