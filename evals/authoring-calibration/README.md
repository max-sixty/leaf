# Fixed authoring controls

Four small native-HTML pages provide two matched valid/defective pairs.
`controls.json` records their requests, two viewports, fixed source hashes and
private expectations. The development pair is previously observed calibration
evidence. The second pair was authored independently and kept sealed from the
new minimal evaluator implementation; preserve that separation until the
candidate is frozen. Once exposed or used to revise a candidate, a control is
development evidence for later revisions.

Give a judge only the case request and recorded capture evidence. Exclude
`private_` fields from its input. Those fields describe what an independent
reviewer needs to verify; they do not prove that a browser route works. A source
omission or incorrect handler can support a diagnosis, while rendered
reachability and interaction results need ordinary browser operation.

Use the existing authoring capture and evaluator. There is no separate
calibration runner or command. Keep fixture bytes fixed, verify their hashes,
and record authoring baseline context, captured runtime/browser identity,
viewport, observed actions and evaluator revision with each result. Retain the
exact evidence and raw verdict so matched baseline and candidate outputs can
be rescored by the same evaluator.

The verdict distinguishes a supported defect, a supported pass and unverified
evidence. A collapsed disclosure or unselected view alone does not establish
missing information, and a control visible in a screenshot does not establish
that it works. Missing observation remains unverified. Required task facts and
user decisions still need preserving; supporting detail omitted from an
explicitly brief artifact is judged against that request.

These controlled contrasts are a bounded calibration, not a general accuracy
estimate. Model agreement remains a model judgment. Report independently
observed behavior and unsupported explanations separately from pass counts.
Record development and held-out findings here only after grading and independent
verification; do not rewrite the fixtures to match the judge.

On 2026-10-13, the reduced evaluator ran through Promptfoo 0.124.1 with the
existing `gpt-6.1-sol` screenshot provider and Chrome 155.0.8059.40. At 900×900
and 390×844, both valid controls received `pass`, both defective controls received
`defect`, and arrival-only evidence from the valid payments page received
`insufficient_evidence`. An independent reviewer, without reading model grades,
operated the controls and confirmed the missing incidents and wrong-room receipt.
Fixture hashes remained fixed. The room pair was reserved during rubric
development; its request and expectations were opened during review before final
capture fixes, so this is bounded control validation, not a blind accuracy test.

The evaluator source hashes, capture actions, browser identity and raw Promptfoo
results are recorded under `.tmp/minimal-reduction/validation/`; independent
browser observations are in `.tmp/minimal-reduction/independent-proof.json`.
The commit containing this reduced implementation identifies the evaluator used;
controls identify their authoring bytes and runtime separately in `controls.json`.
