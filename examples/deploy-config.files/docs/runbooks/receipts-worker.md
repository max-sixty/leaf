# receipts-worker runbook

receipts-worker takes each paid order from the `receipts.render` queue, renders
its PDF receipt in Chromium and mails it through Postmark. A customer waiting on
a receipt is the only one who notices it stopping, so a backlog pages and
everything else files a ticket.

## Backlog

`ReceiptsBacklogGrowing` means every render slot has been busy for 15 minutes
while the queue grew.

1. Check the autoscaler reached `maxReplicas`:
   `kubectl -n receipts get hpa receipts-worker`.
2. If it did, raise `maxReplicas` in `values-production.yaml` and deploy.
   Postmark's 600 sends a minute caps the account at about 13 pods.
3. If pods are restarting, read the last render's log line before the
   restart: `kubectl -n receipts logs deploy/receipts-worker --previous`.
   `OOMKilled` means the memory limit is too low for the current concurrency.

## Dead letters

A receipt that fails five times moves to `receipts.render.dlq`. Most are orders
whose line items changed after payment. Replay them once the order settles:

    ./scripts/replay-dlq receipts.render.dlq --older-than 10m

## Mail throttled

Postmark is refusing sends at the account limit. Receipts wait in the queue and
go out once the minute rolls over; nothing is lost. If it lasts an hour, ask
Postmark to raise the limit before lowering concurrency.

## Escalation

TODO(you): who to call when on-call can't clear a backlog within an hour.
