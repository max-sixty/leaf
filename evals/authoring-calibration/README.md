# Fixed authoring controls

`controls.json` records native-HTML requests, viewport dimensions, exact source
hashes and private expectations for two valid/defective pairs. Keep page bytes
and requests fixed. The original split labels record how the fixtures entered
calibration; all these controls have now been exposed and are development
controls for later revisions. They do not constitute a blind accuracy test.

Give the judge the request and a live disposable copy through the existing
`authoring_assertion.mjs` and `arrangement_eval.call_api` path. Exclude private
expectations and original page sources from the judge's filesystem access. The
judge chooses its own exploration through rendered browser routes and reads
screenshots it takes. The harness records the native agent stream and Playwright
CLI action traces, without scripting which content to reveal. Arrival screenshots
are illustrations for reports, not the boundary of grading evidence.

Record the control source hashes, authoring baseline context, original runtime,
browser and tool versions, evaluator revision/source hashes, exact grader input
and raw verdict. These native pages use no Leaf runtime or external resources.
For authored Leaf outputs, retain the original runtime arm alongside saved pages
so later grading can serve the same bytes. There is no separate calibration CLI.

A supported pass, a supported defect and insufficient evidence are distinct
verdicts. Native transport or invalid model output is unscored. Inspect the actual
exploration and reasons: agreement with a private expectation does not establish
that the judge observed the relevant behavior. Model conclusions remain model
judgments; independently operated controls support separate conclusions about
what the user can see and do.

The fixed contrasts cover incident identities behind a disclosure, a working
threshold selector, and reservation receipts faithful or unfaithful to the chosen
room. Independent browser proof from 2026-10-13 covers both window sizes and the
room choice by pointer and keyboard. Reuse that proof while fixture hashes match.
These controls establish particular distinctions, not general judge accuracy or
an estimate of Leaf's authoring advantage.

The live evaluator validation on 2026-10-14 returned two passes and two defects
on the four unchanged controls. Independent review checked the reasons against
the requests, native browser actions and screenshots at 900×900 and 390×844;
each conclusion was supported. A missing saved page returned insufficient
evidence without a model call. Native Leaf and HTML browser checks also verified
viewport isolation, original-state preservation and failure cleanup, including
phone behavior for HTML without a viewport meta tag.

The same fixed room pair was also judged live in both A/B orders. Both completed
judgments preferred the working receipt, with correct page associations and
supporting actions and screenshots at both widths. Independent review verified
those observations; this is one known pairwise contrast, not an accuracy estimate.

The recorded run used gpt-6.1-sol, Codex 0.160.0, Promptfoo 0.124.1,
Playwright 1.64.0 and Chrome 155.0.8059.40. Raw inputs, tool versions, runtime
identity, frozen evaluator source hashes and native evidence are retained in
`.tmp/live-judge/validation-fixed/` and `.tmp/live-judge/pair-validation-fixed/`
in the evaluator worktree. These results
establish the named controls only; they do not estimate accuracy on unseen pages.
