# Subject: upload retry patch review

Make me a review page for this proposed change to our artifact uploader. I need to
read the actual code change, check the failure cases beside it, and choose whether
to ship it as written, ship with the two changes below, or hold it. This page records
our review; it does not deploy code. I'll comment before making the final call.

## Current code: uploader.py

```python
def upload(client, job, payload):
    response = client.post("/objects", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()["object_id"]
```

## Proposed patch: uploader.py

```diff
--- a/uploader.py
+++ b/uploader.py
@@ -1,4 +1,16 @@
+import time
+
-def upload(client, job, payload):
-    response = client.post("/objects", json=payload, timeout=10)
-    response.raise_for_status()
-    return response.json()["object_id"]
+def upload(client, job, payload, max_attempts=3):
+    key = f"upload:{job.id}"
+    for attempt in range(max_attempts):
+        try:
+            response = client.post(
+                "/objects", json=payload,
+                headers={"Idempotency-Key": key}, timeout=10,
+            )
+            response.raise_for_status()
+            return response.json()["object_id"]
+        except TimeoutError:
+            if attempt + 1 == max_attempts:
+                raise
+            time.sleep(0.5 * 2**attempt)
```

## Contracts and review notes

- A client timeout can lose a response after the server has already created the object.
  A retry must use the same key to recover that object instead of creating another.
- Each job creates one object, and every retry for that job carries the same payload.
- The server retains idempotency keys for 24 hours. The same key on the same endpoint
  returns the original object ID. Different uploads must have different keys.
- `job.id` is globally unique. The job also has a `tenant_id`.
- The interactive caller has a 22-second deadline. Each attempt can consume 10 seconds.
  Three timed-out attempts plus the two backoffs consume 31.5 seconds; two attempts
  plus one backoff consume 20.5 seconds.
- Only `TimeoutError` is retried. A 403 or other HTTP failure must propagate immediately.
- The key is computed before the retry loop and must stay stable across attempts.
- An alternative patch includes `tenant_id` in the key and changes the default to two
  attempts. It keeps the same endpoint, timeout, error handling and backoff formula.
- Rina owns this change. The rollout can begin Thursday after approval and passing tests.

## Checks to review

| Check                        | Expected result                                             |
| ---------------------------- | ----------------------------------------------------------- |
| Fast success                 | One request; return the created object ID                   |
| Response lost after creation | Retry with the same key; return the same object ID          |
| All attempts time out        | Raise the final TimeoutError after the selected attempt cap |
| HTTP 403                     | One request; propagate the HTTP error without retrying      |
| Stable key                   | Every attempt for the same upload sends the same key        |

The tests are proposed acceptance checks, not a claim that they have run. Keep that
status clear. I want the risks and selected code readable when I return to this page.
