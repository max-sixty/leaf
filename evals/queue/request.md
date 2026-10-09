# Subject: escalation queue

Eight customer escalations came in overnight. Put them on a page where I can work
through them one at a time: the queue down one side, and the ticket I've picked open
beside it with everything I need to decide what happens to it. I'll go through all
eight in one sitting and tell you, for each, whether to refund, fix, escalate to
engineering or close.

## Tickets

**ESC-4107 · Northwind Labs · Enterprise · severity 1 · 9 h old**
Summary: SSO login fails for every user since their IdP certificate rotated at 02:10.
Customer says: "Nobody at Northwind can log in. 400 people idle."
Log excerpt:
```
02:11:04 saml: signature verification failed: cert fingerprint 3F:A2:…:9C not in trust store
02:11:04 saml: rejecting assertion for northwind-labs (issuer https://idp.northwind.io)
```
Prior contact: none. Account value: $210k/yr.
Suggested: fix — upload the new certificate from their metadata URL; 10 minutes.

**ESC-4108 · Hale & Sons · Team · severity 3 · 8 h old**
Summary: charged twice for September.
Customer says: "Two charges of $480 on 1 Sept."
Billing: invoice INV-88213 paid twice (card retry after gateway timeout). One charge
already auto-refunded on 3 Sept; customer may not have seen it.
Prior contact: 1 (August, a plan question).
Suggested: close with an explanation and the refund reference RF-5521.

**ESC-4109 · Quanta Freight · Enterprise · severity 2 · 7 h old**
Summary: exports to S3 stall at 99% for files over 2 GB.
Customer says: "Our nightly reconciliation hasn't run for three nights."
Log excerpt:
```
23:58:12 export: part 412/413 uploaded
23:58:12 export: CompleteMultipartUpload → 400 EntityTooLarge (part 413 is 5.3 GB)
```
Prior contact: 2 (both about export performance).
Suggested: escalate to engineering — the final part isn't being split; known bug LF-9921
fixed in 4.12, not yet in their region.

**ESC-4110 · Brightline Dental · Starter · severity 4 · 7 h old**
Summary: wants the dashboard in dark mode.
Customer says: "Please add dark mode, it's hard on the eyes at night."
Prior contact: none.
Suggested: close — point to the feature request board, already planned for Q4.

**ESC-4111 · Orbis Retail · Enterprise · severity 2 · 6 h old**
Summary: API rate limit errors (429) during their Monday batch, though they're under
quota.
Log excerpt:
```
06:00:01 ratelimit: orbis-retail token t_91… 600/min bucket exhausted (burst)
06:00:01 ratelimit: plan quota 6000/min; token-level cap 600/min applied
```
Prior contact: 4 (three about rate limits).
Suggested: fix — their integration uses one token; raise the token-level cap to the plan
quota, which Enterprise contracts allow.

**ESC-4112 · Kettle & Co · Team · severity 3 · 5 h old**
Summary: an ex-employee still has access.
Customer says: "We removed J. Ortiz on Friday but she logged in Sunday."
Audit: user removed from the org 20 Sept 17:02; an API token she created on 2 Sept kept
working until revoked by support at 07:40 today.
Prior contact: none.
Suggested: escalate to engineering (security) — removing a member should revoke their
tokens; this is a product bug, not a support fix.

**ESC-4113 · Pinecrest Schools · Team (education) · severity 3 · 3 h old**
Summary: asks for a refund of the annual plan; they bought Team but needed Enterprise
for SSO.
Customer says: "We bought the wrong plan 10 days ago."
Billing: $2,880 annual, paid 14 Sept; within the 30-day refund window.
Prior contact: 1 (pre-sales, asked about SSO and was told Team includes it — it doesn't).
Suggested: refund, and hand to sales for an Enterprise quote with the education discount.

**ESC-4114 · Vela Analytics · Enterprise · severity 1 · 1 h old**
Summary: dashboard shows another customer's project names in the project switcher.
Customer says: "I can see project names that aren't ours: 'orbis-q3-forecast',
'orbis-pricing'."
Log excerpt:
```
08:51:30 cache: project-list key pl:org_2291 served from shard 7 (org_2219 entry)
```
Prior contact: none.
Suggested: escalate to engineering immediately (security incident: cross-tenant leak of
project names via a cache key collision); do not reply with details until security has
reviewed.
