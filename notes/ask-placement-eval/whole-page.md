Subject: a review packet for pull request #412, "Batch the outbox flush", for the approving reviewer. Present it as a Leaf page. The page's one question is what review to enter on the forge, and it turns on everything in the packet.

Contents:

1. Agent brief: what the PR changes (the outbox worker flushes rows in batches of 200 instead of one at a time; a new `flush_batch` function; the retry path now re-queues the whole batch) and why (the single-row path held a transaction per row and topped out at 40 rows/s).

2. Change surface: 6 files, +310 −140. A table of files with what each change does.

3. What changes at runtime: a sequence of worker → outbox table → broker, before and after.

4. Evidence and remaining gaps: a table of claims with their tests — batch flush preserves order (test passes), a failed row does not lose its neighbours (test passes), throughput at 200/batch (bench: 1,900 rows/s), duplicate delivery on retry (no test; gap), memory at batch size 200 with 1 MB payloads (unmeasured; gap).

5. Prior PR activity: two review rounds; the first found the ordering bug that test 1 now covers.

6. The decision: what to report on the final revision — (a) approve with two follow-ups (a duplicate-delivery test and a memory measurement), reviewer-agent's recommendation; (b) approve without follow-ups; (c) request changes before merge (add the duplicate-delivery test now).
