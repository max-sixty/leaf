# Remaining prose review

The Layout-tab and factual-correction phase landed in
[PR #1476](https://github.com/max-sixty/leaf/pull/1476). The maintainer rewrite is
written but unlanded. Author instructions have received a focused clarity pass;
the broader rewrite remains open. Site, UI vocabulary and example selection
depend on decisions A–E below. Retire this note when the phases land and
any standing rule has moved into its owning instructions.

Each phase recovers what its reader needs, rewrites the prose, and checks dropped
claims against the code. Preserve behavior in agent and maintainer instructions unless
a claim is wrong. The front page stays as it is; other site pages may be reorganized.
Use `/writing-prose` for the rewrite and an independent review for the result.
Word counts describe the change; reader usefulness and preserved meaning judge it.

## Phase 1: Maintainer instructions

The local branch `agent-a7d03ea41654f534b` at `5c7baed6fcbaf7d26a2cc4f63a035418b546e6e8` contains the rewrite.
Its recorded comparison takes 17 files from 33,267 to 24,750 words. The biggest
cuts remove duplicated module contracts, discovery history and command catalogs
already available through `--help`. The root instructions above “Repository map” are
unchanged.

Before landing, independently review the final cuts, especially `session-lifetime.md`
and `tests/AGENTS.md`, and verify their incoming heading links. Re-run the required
gates on the candidate after bringing it current; the earlier passing suite is
historical evidence, not a current landing result. Keep this work with its existing
branch rather than starting a second maintainer rewrite.

## Phase 2: Agent instructions

Apply the same reader-based rewrite to `skills/leaf/SKILL.md`, the routed references
and package instructions. Score with `leaf-dev eval` before and after, following
“Score an instruction change” in `/developing-leaf`. This phase needs no product decision.

- Give host selection, initial work status and the URL-in-every-message rule one
  canonical home each. Host contracts should point to those homes.
- Put event-handling instructions before transport details.
- Reduce revision-state and margin instructions to what the author acts on. Keep package
  record semantics in their existing owner.
- Separate agent operation from user setup and maintainer mechanisms in serving
  and host references. Check uncertain setup passages against an actual fresh host.
- In command-hub instructions, distinguish a leaf goal from a Leaf page.

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
need them. Describe delivery by host and status by visible surface. Version comparison
belongs with revisions; source, widgets, page code and packages belong with pages.
Serving should explain the stable address and recovery through the canonical host
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

Audit current rendered copy before changing strings: earlier counts and banner
examples are a snapshot. Give one concept one user-visible word and cut every surface
over together. Examples include “Undo”, “page”, “Threads” and “comment box”; delivery,
work and an owed answer still need distinct meanings.

The CLI should use one error presentation, minimal success lines and self-contained
hints. Remove Python representations and implementation vocabulary from reader-facing
messages. A shared glossary owns the words, not a second table in this note.

**Decision C — mixed user input.** Recommend “update” for a mixed count and the specific
noun for an individual comment or choice; “Showing v4” keeps revision copy distinct.
Alternatives are counts by kind, which require per-kind activity data, or “move” for
the mix. Test the wording on actual banner and neighboring-page rows.

**Decision D — sidebar naming.** `layout-sidebar` and `aside.sidebar` name different
forms. Options are renaming the Layout to `layout-aside`, renaming the margin idiom,
or keeping both with distinct descriptions. A rename cuts over validation, registry,
instructions, examples and eval cases together; score instructions before and after.

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
