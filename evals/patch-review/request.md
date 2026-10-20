# Subject: upload retry patch review

Make me a review page for this proposed change to our artifact uploader. I need to
read the actual code change, check the failure cases beside it, and choose whether
to ship it as written, ship with the two changes below, or hold it. This page records
our review; it does not deploy code. I'll comment before making the final call.

The patch spans implementation, acceptance tests and release documentation. Help me
navigate its directory hierarchy and switch among files while keeping track of the
selected file. Keep the code comfortable to read on my desktop and the review
notes and final approval route easy to reach.

## Proposed patch

```diff
--- a/src/artifacts/uploader.py
+++ b/src/artifacts/uploader.py
@@ -1,4 +1,19 @@
-def upload(client, job, payload):
-    response = client.post("/objects", json=payload, timeout=10)
-    response.raise_for_status()
-    return response.json()["object_id"]
+"""Upload one job's artifact, recovering a lost response through idempotency."""
+
+import time
+
+
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
--- /dev/null
+++ b/tests/artifacts/test_uploader.py
@@ -0,0 +1,77 @@
+"""Proposed acceptance checks; these have not been run."""
+
+from types import SimpleNamespace
+from unittest.mock import Mock
+
+import pytest
+
+from artifacts.uploader import upload
+
+
+@pytest.fixture
+def job():
+    return SimpleNamespace(id="job-42", tenant_id="tenant-a")
+
+
+@pytest.fixture
+def payload():
+    return {"name": "metrics.parquet", "checksum": "sha256:abc123"}
+
+
+@pytest.fixture
+def client():
+    response = Mock()
+    response.json.return_value = {"object_id": "obj-7"}
+    result = Mock()
+    result.post.return_value = response
+    return result
+
+
+def test_fast_success(client, job, payload):
+    assert upload(client, job, payload) == "obj-7"
+    client.post.assert_called_once()
+    assert client.post.call_args.kwargs["timeout"] == 10
+
+
+def test_lost_response_recovers_original_object(client, job, payload, monkeypatch):
+    monkeypatch.setattr("artifacts.uploader.time.sleep", lambda _: None)
+    response = client.post.return_value
+    # The fake server's second response refers to the first request's object.
+    client.post.side_effect = [TimeoutError("response lost"), response]
+
+    assert upload(client, job, payload) == "obj-7"
+    first, second = client.post.call_args_list
+    assert first.kwargs["headers"] == second.kwargs["headers"]
+    assert first.kwargs["json"] == second.kwargs["json"] == payload
+
+
+def test_timeouts_stop_at_attempt_cap(client, job, payload, monkeypatch):
+    sleeps = []
+    monkeypatch.setattr("artifacts.uploader.time.sleep", sleeps.append)
+    client.post.side_effect = TimeoutError("upstream unavailable")
+
+    with pytest.raises(TimeoutError, match="upstream unavailable"):
+        upload(client, job, payload, max_attempts=2)
+
+    assert client.post.call_count == 2
+    assert sleeps == [0.5]
+
+
+def test_http_failure_is_not_retried(client, job, payload):
+    client.post.return_value.raise_for_status.side_effect = RuntimeError("HTTP 403")
+
+    with pytest.raises(RuntimeError, match="HTTP 403"):
+        upload(client, job, payload)
+
+    client.post.assert_called_once()
+
+
+def test_key_is_stable_across_attempts(client, job, payload, monkeypatch):
+    monkeypatch.setattr("artifacts.uploader.time.sleep", lambda _: None)
+    response = client.post.return_value
+    client.post.side_effect = [TimeoutError(), TimeoutError(), response]
+
+    assert upload(client, job, payload, max_attempts=3) == "obj-7"
+    keys = [call.kwargs["headers"]["Idempotency-Key"]
+            for call in client.post.call_args_list]
+    assert len(set(keys)) == 1
--- /dev/null
+++ b/docs/operations/upload-retries.md
@@ -0,0 +1,29 @@
+# Upload retry operations
+
+Owner: Rina
+
+## Response lost after object creation
+
+The server may create the object before the client times out.
+Retain the original payload and idempotency key when retrying.
+The same key on /objects returns the original object ID for 24 hours.
+A different upload requires a different key.
+
+## Interactive deadline
+
+The caller has 22 seconds to finish.
+Each request can consume 10 seconds.
+The proposed default of three attempts can consume 31.5 seconds.
+A default of two attempts consumes at most 20.5 seconds.
+
+## Error handling
+
+Retry TimeoutError only.
+Propagate HTTP failures, including HTTP 403, immediately.
+After exhausting the cap, raise the final timeout.
+
+## Release gate
+
+These acceptance checks are proposed and have not run.
+Rina may begin rollout Thursday after approval and passing tests.
+Approval on this review page records a decision; it does not deploy code.
--- /dev/null
+++ b/docs/releases/artifact-uploader.md
@@ -0,0 +1,11 @@
+# Artifact uploader retry proposal
+
+Status: awaiting review and acceptance tests
+Owner: Rina
+Earliest rollout: Thursday, after approval and passing tests
+
+The proposed uploader retries timeouts with a stable idempotency key.
+Its initial default is three attempts.
+
+The review also considers a tenant-and-job key and a two-attempt default.
+Update this record with the selected behavior when the review is approved.
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
