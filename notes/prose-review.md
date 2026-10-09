# Remaining prose review

The Layout-tab and factual-correction phase landed in
[PR #1476](https://github.com/max-sixty/leaf/pull/1476). The maintainer rewrite is
recovered in its existing branch and ready for review; landing remains pending.
The agent-instruction rewrite is complete: the routed references now separate author operation, harness
setup and maintainer mechanisms. UI vocabulary is complete; site and
example selection still depend on the decisions below. Retire this note when the
phases land and any standing rule has moved into its owning instructions.

Each phase recovers what its reader needs, rewrites the prose, and checks dropped
claims against the code. Preserve behavior in agent and maintainer instructions unless
a claim is wrong. The front page stays as it is; other site pages may be reorganized.
Use `/writing-prose` for the rewrite and an independent review for the result.
Word counts describe the change; reader usefulness and preserved meaning judge it.

## Phase 1: Maintainer instructions

The existing branch `agent-a7d03ea41654f534b` is recovered and reconciled with
current main. The useful simplifications remain, with current session lifetime,
preview feedback, distribution and testing contracts retained. Renamed heading
references are repaired. Independent prose and contract review and the relevant
instruction checks passed.

The resulting changes are ready for review. Landing remains pending and requires
the current landing gates. Keep this work with its existing branch.

## Phase 2: Agent instructions

The rewrite of `skills/leaf/SKILL.md` and its routed references is complete.
Harness selection, initial work status and the final URL each have one
canonical home. Event handling precedes transport details; setup lives in its
own reference. Revision and margin instructions describe the author's actions,
and command-hub instructions distinguish a terminal goal from a Leaf page.
Leaf's soul and the agent/principal distinction remain.

The before/after eval scored 14/14 samples in each arm. Both real served handoffs
met all 19 criteria, including the delivered input, the page revision and the
exact final URL. Changes to response production need their own combined workflow
check; this result describes the instruction rewrite on its tested interface.

## Phases 3 and 4: Site readers and structure

The site currently serves primarily to summarize Leaf's design and interfaces.
Consider further refinements closer to release; the route map below is a proposal
for that stage.

The proposed site gives each page one reader:

| Route | Reader and purpose |
|---|---|
| `/` | Existing front page |
| `/examples/` | Example users; package named on each card, developer galleries elsewhere |
| `/using/` | People operating a page and reading its status |
| `/how-it-works/` | Mechanism, incorporating the event log and one explanation of the fold |
| `/pages/` | Authors choosing page contents and layouts |
| `/extending/` | Package authors; ownership, package table and one worked extension |

The proposal removes the public registry page. Explain experimental status,
requirements, page trust and access keys, and offline export where their readers
need them. Describe delivery by harness and status by visible surface. Version comparison
belongs with revisions; source, widgets, page code and packages belong with pages.
Serving should explain the stable address and recovery through the canonical harness
contract rather than prescribe one command for every harness.

**Decision A — status depth.** Recommend the banner readings and a short explanation,
linking to protocol references for derivation. Alternatives are the same derivation
under a closed disclosure or a full mechanism explanation on the site. The latter
two keep a second copy of the protocol material.

**Decision B — site structure.** Recommend the reader-based route map above.
Alternatives are keeping routes but regrouping tabs, or rewriting every current page
in place. A route change also updates shared navigation, Worker routing fixtures and
product-page tests; compare the rendered candidate before deciding.

## Phase 5: UI and CLI vocabulary

The vocabulary cutover is complete. “All pages” names the neighboring-page
drawer, “Showing vN” names the visible version, and “comment box” names its editor.
Saved input, an owed answer and observed work remain distinct. A page Ask needs an
answer; messages in one thread need one reply. “Your updates are saved” describes
input without borrowing a count of response obligations. Historical work does not
imply a current live turn.

CLI refusals use the existing Click error presentation and self-contained, quoted
path hints. Structured diagnostic values use one standard JSON renderer at the
existing diagnostic owner. Refusal rules and event contracts remain with their
owners. The shared glossary defines the vocabulary; this note keeps no second table.

`layout-sidebar` and `aside.sidebar` retain their separate meanings and distinct
descriptions. Blind desktop and phone use verified mixed input, undo, neighboring
pages, versions and actual CLI recovery. The paired banner comparison and live
candidate are on the review page. Startup uses the same code request count;
timing is diagnostic rather than an acceptance threshold.

## Phase 6: Example subjects

Rewrite examples around a plausible task rather than an explanation of Leaf controls.
Check the PR walkthrough's invented labels and Rust assertions against its linked
source before changing them.

Generate catalog descriptions from each page's existing description rather than
maintain a second summary. Keep seeded comments in the user's voice and verify
their claims.

**Decision E — playground examples.** Recommend keeping the notification playground
in the catalog with a real subject, and moving code comparison and data explorer to
the developer playground entry. Alternatives are giving each a real user task or
keeping them in place with prose edits only. Inspect the rendered examples before
choosing; this note is the brief for that comparison.
