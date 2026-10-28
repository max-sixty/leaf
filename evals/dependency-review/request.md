# Subject: partner-delivery dependency review

Make a review page for this fictional incident. I need to understand which parts of
order processing are affected, inspect the dependency diagram, and choose a temporary
mitigation. This is a planning record; recording my choice does not execute it.

Show the system as a labeled data-flow diagram, with each directed edge saying what
moves along it. Arrow direction shows the movement of data, not which component
initiates a network request. Keep the facts and diagram available while I compare the two options.
The diagram must remain readable and inspectable on a phone, including its edge labels.

## System

There are six components:

- Customer: submits an order and receives its confirmation.
- Orders API: accepts the order and writes the transaction.
- Primary database: stores orders and their delivery-outbox rows in the same transaction.
- Delivery worker: polls pending outbox rows and sends them to the partner.
- Partner API: receives delivery requests; currently returns HTTP 503.
- Receipt index: serves the read-only delivery-status lookup.

Show these data flows:

- Customer → Orders API: submit order.
- Orders API → Customer: order confirmation.
- Orders API → Primary database: commit order + outbox row atomically.
- Primary database → Delivery worker: pending outbox rows returned when the worker polls.
- Delivery worker → Partner API: send delivery request.
- Delivery worker → Receipt index: update delivery status.

## Evidence at 14:20 UTC

- Order acceptance success is 99.96%; the incident has not stopped orders being stored.
- Every attempted partner request has returned HTTP 503 since 14:03.
- The delivery outbox has 5,000 queued rows; the oldest is 17 minutes old.
- Incoming orders add 300 outbox rows per minute. Assume that rate stays constant for
  the next ten minutes; failed partner requests remove no rows.
- The queue's operating limit is 10,000 rows. Outbox retention is 24 hours.
- Partner delivery has a 15-minute objective, so the oldest queued order is already late.
- The retrying worker consumes 35% of one CPU. The partner has not supplied a recovery ETA.

Timeline: 14:03 partner errors begin; 14:08 worker CPU reaches 35%; 14:18 the oldest
queued order reaches the 15-minute delivery objective; 14:20 this review is prepared.

## Options

- Pause partner delivery for ten minutes. Order capture and outbox writes continue.
  The expected queue becomes 8,000 rows and its oldest row reaches 27 minutes. This
  reduces retry work but extends delivery delays; it does not fix the partner.
- Continue the current bounded retries. Partner requests may recover sooner, but
  while every request fails, over the same ten-minute review horizon the queue still
  grows by 300 rows per minute and retry CPU remains 35%.

Let me choose one option through a clear completion route. Keep the selected action,
its ten-minute review horizon, the capacity calculation, current delivery breach and
unaffected order capture visible in the final record. The current evidence supplies
no recovery ETA and no proof that either mitigation has been executed.
