You work on a small billing service with its team lead, Dana. This morning support
forwarded eleven customer emails asking why they got two, and in some cases three,
copies of their November invoice. Dana asked: "What happened with the November
invoices? Write it up so I can pick a fix before tonight's run."

You have read the code and the run's log. Your notes:

- The nightly run, `billing/send_invoices.py`, started at 02:00 UTC on 18 November.
  For each due invoice it calls `deliver`, which renders the PDF, emails it, and then
  marks the invoice sent with an UPDATE that times out after 5 seconds. `@retry` from
  `billing/retry.py` wraps the whole of `deliver`.
- From 02:14:52 to 02:41:07 the month-end rollup held a lock on the invoices table.
  In that window an UPDATE could wait past its 5 seconds and time out. `retry` then
  caught the `OperationalError`, waited 20 seconds and called `deliver` again from the
  top, which rendered and emailed the invoice again before the next UPDATE tried.
- The mail provider's export for the night holds 3,927 messages for 3,874 invoices:
  41 invoices went out twice and 6 three times. The 6 then gave up, so they still
  have `sent_at` NULL and tonight's run would email them a fourth time. No invoice
  outside the rollup's window went out twice.
- The provider accepts an `Idempotency-Key` header and drops a repeat with the same
  key within 24 hours.

Fixes you see:

1. Send with `Idempotency-Key: <invoice id>`, and retry the UPDATE on its own rather
   than the whole of `deliver`. Covers any failure after the send, about 15 lines.
   Your recommendation.
2. Move the rollup to 04:00. Removes last night's trigger, but any other failure after
   the send still sends again.
3. Mark the invoice sent before emailing it, and clear the mark if the send fails. A
   crash between the two leaves an invoice marked sent that never went out.

Whichever fix Dana picks, the 6 invoices need `sent_at` set before 02:00 tonight.

The code is in `billing/send_invoices.py`, with `deliver` at lines 22-36, and
`billing/retry.py`. An excerpt of the run's log is in
`logs/invoice-run-2026-11-18.log`: the run's start and end, the rollup's start and
finish, and the first invoices the lock reached.

Write a Leaf page for Dana.
