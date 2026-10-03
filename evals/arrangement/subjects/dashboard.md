# Subject: release 4.12 rollout dashboard

Make me a page I can keep open while release 4.12 rolls out. I glance at it every few
minutes between other work, so the state of the rollout has to read at a glance, and I
need to be able to tell you whether to resume, hold or roll back the paused region.

## Current state (15:40 UTC)

**Headline numbers.**

- Error rate across rolled-out regions: 0.42% (baseline 0.31%, +0.11 pts).
- p95 API latency: 212 ms (baseline 198 ms).
- Traffic on 4.12: 58% of requests.
- Crash-free sessions (mobile): 99.71% (baseline 99.74%).

**Rollout by region.** Stages are 1% → 10% → 50% → 100%.

| Region | Stage | Since | Error rate | Status |
|---|---|---|---|---|
| us-east | 100% | 11:05 | 0.33% | done |
| us-west | 100% | 11:50 | 0.35% | done |
| ca-central | 100% | 12:30 | 0.30% | done |
| eu-west | 50% | 13:10 | 0.91% | **paused 14:52** |
| eu-central | 10% | 14:05 | 0.38% | waiting on eu-west |
| ap-southeast | 1% | 14:40 | 0.29% | waiting on eu-west |

**Error rate by region, % of requests, five-minute buckets since 14:00 UTC.**

```
time,us-east,eu-west,eu-central
14:00,0.31,0.34,0.33
14:05,0.32,0.36,0.35
14:10,0.33,0.41,0.36
14:15,0.32,0.47,0.37
14:20,0.33,0.55,0.36
14:25,0.34,0.63,0.38
14:30,0.33,0.70,0.37
14:35,0.32,0.78,0.38
14:40,0.33,0.86,0.39
14:45,0.34,0.94,0.38
14:50,0.33,1.02,0.38
14:55,0.33,0.97,0.38
15:00,0.32,0.95,0.37
15:05,0.33,0.93,0.38
15:10,0.34,0.92,0.39
15:15,0.33,0.91,0.38
15:20,0.33,0.91,0.38
15:25,0.32,0.90,0.37
15:30,0.33,0.91,0.38
15:35,0.33,0.91,0.38
```

**Release checks.**

| Check | Result |
|---|---|
| Unit and integration suite | pass |
| Contract tests against billing | pass |
| Schema migration 0412 applied | pass, all regions |
| Canary synthetic login | pass |
| Canary synthetic checkout | **fail in eu-west since 14:20** (timeout at payment step) |
| Feature flag `new-cart` default | off everywhere |
| Dependency `payments-sdk` 7.2 | rolled with 4.12 |
| Memory per pod | +4% vs 4.11, within budget |
| Cold start | 1.8 s vs 1.7 s |
| Log volume | +11% (new debug line in cart service) |

**Event log (newest first).**

- 15:31 Priya: eu-west payment provider (Adyen EU) reports no incident on their side.
- 15:18 on-call: eu-west errors are 92% HTTP 504 from `cart-service` → `payments-sdk`.
- 15:02 on-call: rolled back one eu-west pod to 4.11 as a control; its errors dropped to 0.33%.
- 14:52 auto-pause: eu-west error rate over 0.9% for 5 minutes.
- 14:40 ap-southeast to 1%.
- 14:20 synthetic checkout starts failing in eu-west.
- 14:05 eu-central to 10%.
- 13:10 eu-west to 50%.
- 12:30 ca-central to 100%.
- 11:50 us-west to 100%.

**What we know.** Only eu-west is affected. The errors are timeouts from the new
`payments-sdk` 7.2 talking to the EU payment endpoint, which is the only region using
Adyen EU. The one pod rolled back to 4.11 recovered. `payments-sdk` 7.2 changed the
default connect timeout from 10 s to 3 s.

**Open follow-ups.**

- Confirm the timeout change with the payments team (Dana).
- Decide whether 4.12.1 pins the old timeout or eu-west stays on 4.11.
- Silence the extra debug log line before 100% everywhere.
- Post status in #release by 16:00.
- Update the rollout runbook with the control-pod step, which worked well.

**The decision I need from you.** For eu-west: resume to 100% (the others are fine),
hold at 50% while payments confirms, or roll eu-west back to 4.11 and ship 4.12.1 with
the old timeout.
