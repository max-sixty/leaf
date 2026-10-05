# Feedback responsiveness evaluation

The delivery and activity lifecycle is implemented. Its owners are
[session lifetime](../skills/leaf/scripts/leaf/session-lifetime.md),
[conversation loop](../skills/leaf/references/conversation-loop.md), and the
application publication described in [AGENTS.md](../AGENTS.md). This note holds
remaining evaluation work and proposed improvements; it does not define a second
lifecycle contract.

The browser paints a gesture's semantic result before its POST completes. Carriers
record queue acceptance and turn entry; the agent selects work through a claim;
durable replies and revisions settle the exact input. Delivery evidence does not
prove external work succeeded, and page activity does not imply work on every message.

## Evaluation

Run `leaf-dev eval 'document/idle' 'document/mid-turn'` for agent ordering and `leaf-dev bench-latency` for
in-tab feedback. Neither is a gate. Begin with a direct delivery, a queued pointer,
input arriving during other work, and an already-settled retry.

For actionable input, the claim should precede substantive source reads, edits,
tests and delegation. A queued pointer may first read its immutable delivery to
resolve the address. A settled retry should not briefly appear active. During
delegation, retain the original work and the newer queued count while the observer
can still prove the delegate is live.

Read deterministic sequence and state at their owners: projection tests for
sent/queued/opened/active/stale/settled evidence; real gestures for local results;
agent traces for claim ordering. Use `leaf-dev journey` as the vertical test: it
times a real request on any harness from the page's own log, and on `cc` and
`codex` splits the agent's turn into delivery, model and tool phases.

```bash
uv run leaf-dev eval --help
uv run leaf-dev bench-latency --help
uv run leaf-dev journey --help
```

## Initial latency targets

These are proposed budgets, not measured current performance. Evaluate repeated
phase traces before revising them.

| Transition | Target |
|---|---|
| Gesture to local result | Same rendering turn; under 100 ms |
| Acceptance to visible receipt | Next state application; under 1 s |
| Turn entry to visible pickup | Without waiting for model output; under 1 s |
| Input in model context to accepted claim | Before substantive work; under 2 s |
| Status or result write to browser paint | Next state application; under 1 s |
| Comment admission to thread title | under 2 s |
| Comment admission to reply, for a small page change | under 7 s |

The last two are the journey's `titled` and `replied` steps. On 2026-10-05,
Claude Code titled in 1.4–2.2 s and replied in 7.8–17.5 s, Codex titled in
3.8–6.1 s and replied in 65–125 s, and the website's adapter in 2.7–2.9 s and 14.2–19.4 s.

Other work has no universal budget. Status should change when the operation
changes, without timer-driven chatter. Measure the hosted agent's status updates
as well as its reply so improving feedback does not delay the answer.

## Proposed improvements

- **Cheap claims:** test a typed harness operation against the CLI path before adding
  another interface. The [Codex brief](codex-integration.md#typed-operations) owns
  that experiment.
- **Claim admission:** check whether the claim door can atomically require an
  outstanding subject, avoiding an active flash for a retry that was settled in
  the meantime. Reproduce the race before changing admission.
- **Delegation:** use observed job identity and continuation evidence rather than
  inferring activity from status prose. The
  [Thread plan](threads.md#independent-jobs-delegation-and-continuation) owns that
  broader model.

Move a validated rule into its existing owner and retire the corresponding part
of this brief. Keep transport evidence, work selection and settlement distinct.
