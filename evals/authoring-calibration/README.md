# Fixed authoring calibration

These standalone HTML artifacts distinguish required information that is absent,
information that an evaluator has not revealed, and information that the page
contains but the user cannot reach. Their expected results follow from the user
request and deliberately controlled source differences. They do not establish
general authoring quality or model accuracy.

## Inputs and private expectations

Each split has a `manifest.json` with the request, task requirements, capture
viewports, ordinary reader routes and the SHA-256 of each artifact. Artifact paths
are relative to that manifest. A scorer receives the request and captured evidence.
The requirements and routes guide the independent browser verification; they are
not evidence that those routes worked.

`expectations.json` is the oracle: target findings, specific false alarms to reject,
the source difference that supports each expectation, and browser checks still
needed. Keep it outside the judged packet. A missing expected finding is a miss
only when the supplied evidence can establish it. An incomplete observation leaves
that criterion unverified; it does not prove a page defect.

The development split exposes matched contrasts for labeled disclosures, queue
selection and narrow-screen table access. The held-out split was authored before
candidate validation and is kept separate until the evaluator implementation,
criteria and scoring prompts are frozen. Reading a held-out expectation while
developing makes it development evidence; record that exposure rather than calling
the later result held out.

## Revisions and capture records

The manifest's `authoring_revision` is the repository baseline used when these
fixtures were hand-authored, not a claim that the baseline commit contains them.
The per-artifact hashes identify their actual fixed bytes. There is no Leaf layer:
the runtime is native HTML, CSS and JavaScript, with no external resources.

Before scoring, verify artifact hashes and record the browser identity, viewport,
capture actions/results, evaluator repository revision and evaluator source/prompt
hashes alongside each packet. Capture and scoring runs record their own runtime
and evaluator identities; do not modify the fixed fixtures to insert them. Retain
the exact packets and raw verdicts so the same evaluator can score matched authored
baseline and candidate outputs.

The controlled differences independently support source-level claims. Actual
reachability, clipping and control behavior need the recorded browser checks.
A judge's agreement is a model judgment; it is not independent confirmation of
those behaviors. Other findings outside the controlled target need their own
support and are not automatically false alarms.

## Running the calibration

Use a fresh output directory. Browser observation is serial; the two concurrent
model judgments start only after that browser closes. Coordinate this browser
batch with other experiments on the same machine.

```sh
uv run leaf-dev eval-calibrate --split development --output .tmp/calibration-development
uv run leaf-dev eval-calibrate --split development --arrival-only --output .tmp/calibration-arrival
```

Before opening held-out artifacts, record the candidate's evaluator source and
rubric hashes and finish development checks. Then run the same candidate without
editing it against the held-out split. Read private expectations only after its
grades are fixed, and verify the controls independently in a browser. Record
unsettled input routes separately from a page defect. If a result causes a
candidate change, that case becomes development evidence; a later held-out claim
needs new examples.

```sh
uv run leaf-dev eval-calibrate --split heldout --output .tmp/calibration-heldout
```

