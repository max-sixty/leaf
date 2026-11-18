On Monday I asked you to look into PHOTO-412, the Sunday-evening upload failures, and
come back with a proposal for the listings team's design review on Thursday. Your notes
from the investigation are below. Hand the proposal over to me on a Leaf page; I'll make
the calls it needs before the review.

---

# PHOTO-412: moving photo variants out of the upload request

## The ticket

Sellers on the iOS and Android apps report photo uploads failing on Sunday evenings
with "Something went wrong, try again", and support sees the same complaint from web
sellers. PagerDuty fired `listings-api 5xx > 2%` on four of the last six Sundays,
always between 19:00 and 21:30 local. Each time the on-call scaled `listings-api` from
6 to 10 pods by hand and the alert cleared about twenty minutes later. Nobody has
looked at why the upload endpoint is the one that falls over.

## How an upload works today

I traced `POST /v2/listings/{id}/photos` from the app's request to the image the
seller sees. Everything happens inside the one request:

1. The app sends a multipart body to `edge-gw` (nginx with the auth sidecar), which
   checks the session token and proxies to `listings-api`.
2. `listings-api` is the Django monolith under gunicorn: 6 pods, each a c6i.large
   (2 vCPU), each running 12 sync workers, so 72 workers in all. One worker takes the
   request and holds it until the response goes out.
3. `PhotoUploadView.post` spools the body to a temp file, then calls
   `imaging.make_variants()` inline. That decodes the image with Pillow-SIMD,
   auto-orients it, strips the EXIF GPS block, and resizes it to the four sizes the
   apps use: `thumb` (160 px), `card` (480 px), `detail` (1200 px) and `zoom`
   (2400 px). Each size is encoded twice, as JPEG and WebP, so eight files.
4. It PUTs the original and the eight variants to the `atlas-photos` S3 bucket, one
   after another, with boto3's default client.
5. It inserts the `listing_photo` row in Postgres with the nine object keys and
   `status = 'ready'`.
6. It responds `201` with the photo JSON, which includes the CloudFront URLs of the
   variants. The app then fetches `card` from CloudFront and shows it in the listing
   editor.

So the seller waits for the whole pipeline before the app gets an answer, and a gunicorn
worker is pinned for the same time. The pipeline is CPU-bound: about 1.25 s of CPU per
median photo, almost all of it decode, resize and encode.

Sunday 19:00 to 21:00 is when sellers list what they cleared out over the weekend. From
the `edge-gw` access logs for the last four Sundays: 6.1 uploads/s on average across
those two hours, with minute-long bursts up to 11 uploads/s. Weekday evenings peak at
about 3 uploads/s.

## What I tried first

Before proposing anything structural I tried two cheaper fixes.

**A thread pool inside the request.** Pillow releases the GIL in resize and encode, so
I made `make_variants()` encode the eight files on a `ThreadPoolExecutor(4)`. At one
upload at a time it helped: 1.84 s down to 1.31 s at p50. Under load it made things
worse, because each upload now competes for the pod's two cores with every other
upload's four threads; at 8 uploads/s p95 went from 6.7 s to 9.1 s. Dropped.

**Presigned uploads straight to S3, with an S3 event triggering a Lambda.** This takes
the body off `listings-api` entirely. Two problems: the Lambda's cold start with the
Pillow-SIMD layer was 2.8 s, which lands on exactly the bursty traffic we care about,
and the apps' resumable upload library (`tus-mobile`) only speaks to our own endpoint;
switching it is a two-release project for the mobile team. Dropped, though it might
come back later.

One thing that fell out of profiling and should ship whatever we decide: WebP encoding
is the biggest single cost. We encode with `method=6`. At `method=4` the four WebP
encodes go from 520 ms to 300 ms per photo and the files grow by 4%. That's a separate
one-line change (PHOTO-418); I've left it out of every measurement below, so both sides
use `method=6`.

## The proposal

Take variant generation out of the request. The request only has to store the original
safely and record that the photo exists; the variants can follow a second or two later,
as long as the app knows when they're ready.

The parts:

- **`edge-gw`**: unchanged.
- **`listings-api`**: the upload handler streams the body straight to S3 as the
  original (multipart upload while it receives, so no temp file), inserts the
  `listing_photo` row with `status = 'processing'`, enqueues a job, and responds
  `202` with the photo's id and position. It no longer touches Pillow.
- **The job queue**: either a `photo_jobs` table in the main Postgres, claimed with
  `SELECT … FOR UPDATE SKIP LOCKED` and woken with `LISTEN/NOTIFY`, or an SQS queue.
  Decision 1 below.
- **`variant-worker`**: a new deployment running the existing `imaging` module, four
  worker processes per c6i.xlarge (4 vCPU) pod. KEDA scales it on queue depth, between
  a minimum (decision 3) and 12 pods. A worker claims a job, GETs the original from S3,
  decodes, orients, strips GPS, resizes and encodes, PUTs the variants in parallel (8
  concurrent PUTs), sets the row to `ready`, and publishes `photo.ready` on the
  existing `photo-events` Redis channel.
- **`notify-svc`**: already holds a websocket to every signed-in app for chat
  messages. It subscribes to `photo-events` and pushes `photo.ready` to the seller's
  sessions.
- **The apps**: show the photo from the local file the seller picked as soon as the
  `202` arrives, and swap in the CloudFront `card` variant when `photo.ready` comes.
  If the websocket isn't connected, the app polls `GET /v2/photos/{id}` after 5 s and
  then every 3 s.

The path of one upload under the proposal:

app → `edge-gw` → `listings-api` (original streamed to S3, row inserted as
`processing`, job enqueued) → `202` back to the app, which shows its local copy → a
`variant-worker` claims the job → GETs the original from S3 → decode, orient, strip,
resize, encode → 8 parallel PUTs to S3 → row set to `ready` → `photo.ready` on Redis →
`notify-svc` → websocket → the app → `card` from CloudFront.

Retries: a job that fails is retried three times with backoff (2 s, 10 s, 60 s), then
the row goes to `failed` and the app shows "Couldn't process this photo, tap to
retry". Variant keys are derived from the photo id and size, so a retry that runs
after a worker died between its PUTs and its row update rewrites the same objects; it
can't leave orphans or duplicate rows.

Ordering: a photo's position in the listing is assigned when the row is inserted, not
when it becomes ready, so photos that finish out of order still show in the order the
seller picked them.

Old apps: apps before 7.14 don't understand `202` or `processing` and would show a
broken image. `listings-api` keeps the synchronous path for requests whose
`X-App-Version` is below 7.14. Today 39% of uploads come from older apps, falling about
6 points a week since 7.14 shipped, so the synchronous path would carry most of its old
load for a few more weeks and could be deleted in about two months. That also means the
Sunday problem only goes away gradually unless the sync path gets the extra pods
meanwhile.

## Measurements

Setup, so the numbers are comparable: staging cluster, sized like production (6
`listings-api` pods as above; for the proposal, `variant-worker` with KEDA and the
same Postgres instance class). 400 photos sampled from last month's production uploads:
median 4.1 MB (3024×4032), p95 11.8 MB. k6 in the same region with
`constant-arrival-rate`, 5 minutes per rate, so the times below exclude the seller's
own network. Each rate ran twice and the runs agreed within 5%; these are the second
runs. Both sides with WebP `method=6`.

### Response time of the upload request

What the app waits for before it gets an answer: the `201` today, the `202` under the
proposal. Seconds.

| uploads/s | today p50 | today p95 | today failed | proposal p50 | proposal p95 | proposal failed |
| --------: | --------: | --------: | -----------: | -----------: | -----------: | --------------: |
|         1 |      1.85 |      3.30 |           0% |         0.19 |         0.34 |              0% |
|         2 |      1.86 |      3.32 |           0% |         0.19 |         0.34 |              0% |
|         4 |      1.93 |      3.48 |           0% |         0.19 |         0.35 |              0% |
|         6 |      2.21 |      4.10 |           0% |         0.19 |         0.36 |              0% |
|         8 |      3.05 |      6.70 |           0% |         0.20 |         0.37 |              0% |
|        10 |      11.6 |      29.4 |         6.3% |         0.20 |         0.38 |              0% |
|        12 |      19.8 |      30.0 |        22.7% |         0.20 |         0.40 |              0% |
|        16 |         — |         — |            — |         0.21 |         0.43 |              0% |
|        24 |         — |         — |            — |         0.23 |         0.49 |              0% |

Today's path saturates at about 8.8 uploads/s: CPU on the six pods sits at 88–92% from
8/s up, and above that the gunicorn backlog fills. At 10/s the failures were 4.1% `502`
from `edge-gw` and 2.2% client timeouts at 30 s; at 12/s, 15.9% and 6.8%. I didn't run
today's path above 12/s. The 30.0 at 12/s is the client timeout, not a real p95. The
Sunday bursts of 11/s sit right on the cliff, which matches the alerts.

The proposal's response time is flat to 24/s; `listings-api` CPU never went above 31%.
It's bound by streaming the body to S3, not by CPU.

### Time until the variants are ready

From the start of the upload until the app has `photo.ready` (or, today, the `201`,
since the variants exist when it returns). Seconds. With the worker minimum at 2 pods
(8 processes), the starting point for the measurement. "Whole run" is all 5 minutes;
"after scale-up" is the last 3 minutes, once KEDA had added the pods it was going to.

| uploads/s | today p50 | today p95 | proposal p50, whole run | proposal p95, whole run | proposal p50, after scale-up | proposal p95, after scale-up |
| --------: | --------: | --------: | ----------------------: | ----------------------: | ---------------------------: | ---------------------------: |
|         1 |      1.85 |      3.30 |                    1.66 |                    3.05 |                         1.66 |                         3.05 |
|         2 |      1.86 |      3.32 |                    1.67 |                    3.07 |                         1.67 |                         3.07 |
|         4 |      1.93 |      3.48 |                    1.70 |                    3.14 |                         1.70 |                         3.14 |
|         6 |      2.21 |      4.10 |                    1.92 |                    3.60 |                         1.74 |                         3.20 |
|         8 |      3.05 |      6.70 |                    3.40 |                    9.80 |                         1.80 |                         3.30 |
|        10 |      11.6 |      29.4 |                    3.90 |                    11.2 |                         1.80 |                         3.40 |
|        12 |      19.8 |      30.0 |                    4.40 |                    12.6 |                         1.90 |                         3.50 |
|        16 |         — |         — |                    5.10 |                    14.0 |                         2.00 |                         3.70 |
|        24 |         — |         — |                    6.80 |                    18.9 |                         2.30 |                         4.40 |

At low rates the proposal is a little faster end to end than today even though it adds
a queue hop, because the eight PUTs run in parallel (110 ms against 470 ms sequential).

The whole-run numbers from 8/s up are scale-up lag: two pods handle about 5.8 uploads/s,
KEDA polls queue depth every 15 s, and a new `variant-worker` pod takes about 40 s to
pull its image and start. So for the first 60–70 s of a burst the queue grows, and
photos that arrive then wait. Once the pods are up, ready time is back under 2 s at p50.

I re-ran 10/s and 12/s with the minimum at 4 pods (16 processes, about 11.6 uploads/s
before any scale-up):

| uploads/s | min 2 pods, p50 | min 2 pods, p95 | min 4 pods, p50 | min 4 pods, p95 |
| --------: | --------------: | --------------: | --------------: | --------------: |
|        10 |            3.90 |            11.2 |            1.78 |            3.30 |
|        12 |            4.40 |            12.6 |            2.10 |            4.60 |

### Where the time goes, one median photo at 1 upload/s

Milliseconds, median of 200 uploads of the median-sized photo.

Today, all inside the request:

| stage                                   |        ms |
| --------------------------------------- | --------: |
| receive and spool the body              |        70 |
| decode and auto-orient                  |       210 |
| strip EXIF GPS                          |        15 |
| resize to 4 sizes                       |       280 |
| encode 8 files (4 JPEG 220, 4 WebP 520) |       740 |
| 9 S3 PUTs, one after another            |       470 |
| Postgres insert and commit              |        14 |
| serialize and respond                   |         6 |
| **total**                               | **1,805** |

Proposal, inside the request:

| stage                                     |      ms |
| ----------------------------------------- | ------: |
| receive the body while streaming it to S3 |     160 |
| Postgres insert (`processing`)            |      14 |
| enqueue (Postgres table; SQS measured 19) |       3 |
| respond `202`                             |       6 |
| **total**                                 | **183** |

Proposal, after the response:

| stage                                               |        ms |
| --------------------------------------------------- | --------: |
| queue wait until a worker claims it (`NOTIFY` wake) |         6 |
| S3 GET of the original                              |        80 |
| decode, auto-orient, strip GPS                      |       225 |
| resize to 4 sizes                                   |       280 |
| encode 8 files                                      |       740 |
| 8 S3 PUTs in parallel                               |       110 |
| Postgres update (`ready`)                           |         9 |
| publish `photo.ready`                               |         2 |
| `notify-svc` push to the app                        |        30 |
| **total**                                           | **1,482** |

So the seller's app hears back after about 0.18 s instead of 1.8 s, and the variants
are ready at about 1.67 s instead of 1.81 s.

### Throughput and failures at the edge

- Today: saturates at about 8.8 uploads/s on 6 pods. To survive an 11/s burst it needs
  about 8 pods, and more for headroom; the on-call's manual scale to 10 is roughly
  right.
- Proposal: `listings-api` handled 24 uploads/s at 31% CPU. `variant-worker` at 12
  pods (48 processes) sustained about 35 uploads/s before the queue grew without bound
  (tested separately at 30/s and 40/s for 5 minutes).
- Failures: none of the proposal's uploads failed at any rate. Three jobs over all the
  runs were retried after S3 `503 SlowDown` on a PUT; all three succeeded on the first
  retry.

### Cost

On-demand prices, us-east-1, per month:

- Today: 6 × c6i.large for `listings-api` = $372. Running 10 pods on Sunday evenings by
  hand adds about $8.
- Proposal: `listings-api` could drop to 4 pods once old apps are gone ($248).
  `variant-worker` c6i.xlarge at $124 each: with a minimum of 2, KEDA's replay of last
  month's traffic averages 2.6 pods, $322; with a minimum of 4, it averages 4.2 pods,
  $521. SQS, if chosen, would add about $4.
- During the two months the sync path is still needed, keep `listings-api` at 6 pods.

## Decisions for you

### 1. Postgres table or SQS for the job queue

Postgres (`photo_jobs`, `SKIP LOCKED`, `LISTEN/NOTIFY`):

- Enqueue 3 ms, worker wakes in about 6 ms.
- No new infrastructure, and the job row commits in the same transaction as the
  `listing_photo` row, so there's no window where a photo exists without a job.
- Adds two writes per upload (insert job, delete job). At the Sunday peak that's about
  12 writes/s on a primary that already does about 1,900 writes/s.
- We'd write the retry and dead-letter handling ourselves (about 80 lines, already
  sketched).

SQS:

- Enqueue 19 ms. Workers long-poll, so the wake was 20–40 ms in testing.
- Retries and a dead-letter queue come built in.
- A new IAM role and Terraform module, and the enqueue happens after the row commits,
  so a crash between the two leaves a `processing` row with no job; we'd need a sweeper
  for rows stuck in `processing`.

I'd take Postgres now and revisit if jobs ever pass about 100/s.

### 2. Generate `zoom` eagerly, or on first request

CloudFront logs for the last 30 days: only 6.8% of photos ever had their `zoom` variant
requested. `zoom` is the most expensive size: 280 ms of the 740 ms encode and 90 ms of
the 280 ms resize, about 30% of each job's CPU.

- Eager (as measured above): every photo gets all four sizes up front.
- On first request: workers produce `thumb`, `card` and `detail` only. A request for
  `zoom` that misses CloudFront goes to an `imgproxy` origin that renders it from the
  original and caches it. A cold `zoom` took 1.2 s at p50 in my test, against 90 ms
  from cache. Job CPU drops by about 30%, so the same worker pods cover about 40% more
  uploads/s.

The cost is a 1.2 s wait the first time anyone opens a photo's zoom view, plus one more
service to run. I'd go with on-first-request, but it's a product call as much as an
engineering one.

### 3. Worker minimum: 2 pods or 4

- 2 pods: cheapest ($322/month on last month's traffic). Bursts above about 5.8
  uploads/s see ready times of 10–13 s at p95 for the first minute or so, while KEDA
  scales up. The upload itself still succeeds at once and the app shows the local
  copy, so the seller sees a photo either way; what's late is the processed variant.
- 4 pods: $521/month. Covers the observed Sunday bursts (11/s) without waiting for
  scale-up: 1.8–2.1 s at p50 and 3.3–4.6 s at p95 at 10–12 uploads/s.
- A schedule (4 pods Sunday 17:00–23:00, 2 otherwise) would cost about $340 but is one
  more thing to remember when traffic patterns change.

If decision 2 goes to on-first-request, each pod covers about 40% more, and 2 pods
handle about 8 uploads/s before scaling, which would make the minimum matter less.

## Risks and open questions

- The apps' local-copy preview needs 7.14. Older apps stay on the synchronous path, so
  the Sunday alerts won't stop entirely until that path's traffic falls; I'd add 2 pods
  to `listings-api` for Sunday evenings meanwhile.
- `notify-svc` hasn't carried anything but chat. `photo.ready` would add about 6
  messages/s at peak against about 140/s of chat today; I don't expect trouble but
  haven't load-tested it together.
- If Redis is down, `photo.ready` is lost and apps fall back to polling at 5 s. Fine as
  a degradation.
- Moderation runs a nightly job over `listing_photo` rows with `status = 'ready'`.
  Photos still `processing` at 02:00 would be skipped until the next night. Negligible,
  but worth telling the trust team.

## Next steps if you approve

1. PHOTO-418, WebP `method=4`, independent of the rest.
2. `photo_jobs` table and migration, `variant-worker` deployment, KEDA scaler.
3. `listings-api` handler behind a per-seller flag, sync path kept for old apps.
4. Shadow week: 10% of sellers on the new path, compare error rates and ready times.
5. Ramp to 100%, then delete the sync path once old-app uploads fall under 2%.
