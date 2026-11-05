# Site structure before release

The site at leaf.page currently summarizes Leaf's design and interfaces. Two
decisions about how its pages are organized wait until Leaf is closer to release
([issue #4052](https://github.com/max-sixty/leaf/issues/4052), "Decide the
site's structure before release"). Delete this note once
both are decided and the result has landed.

The front page stays as it is; the other pages may be reorganized. Rewrite with
`/writing-prose`, check every dropped claim against the code, and have the result
reviewed independently. Judge it by what each reader can use and by preserved
meaning; word counts describe the cut, not its quality.

## Proposed routes

`leaf_dev.docs` discovers the top-level documents under `docs/` and derives their
routes from their filenames. The proposal gives each page one reader. Every current
document lands in one of them:

| Route               | Reader and purpose                             | Takes, from today's documents                                                                                                                                                                                                                              |
| ------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/`                 | Existing front page                            | `index.html`, unchanged                                                                                                                                                                                                                                    |
| `/examples/`        | Example users                                  | `examples.html`; each card names the packages its example's markup uses, composed by `leaf_dev.docs`; the developer galleries move to `/extending/`                                                                                                        |
| `/using/`           | People operating a page and reading its status | `ui.html`'s panel and rail, Navigation tab and phone sections; `threads.html`'s comments, practice sample, anchor kinds, thread readings and ending; How it works' status sections, data lifetime and offline exports; access keys and experimental status |
| `/pages/`           | Authors choosing page contents and layouts     | `ui.html`'s Pages, Themes and Layout tabs; How it works' external data; asking the user (from On me)                                                                                                                                                       |
| `/how-it-works/`    | Mechanism                                      | How it works' Overview, Workflow, State, Revisions and Runtime; `event-log.html` as an Event log tab with one explanation of the fold; `threads.html`'s passages, anchors across revisions, drawings, message widgets, titles and summaries                |
| `/extending/`       | Package authors                                | `extending.html`; the developer galleries; `registry.html`'s `x-` key index as a Registry keys tab                                                                                                                                                         |
| `/data-structures/` | Implementers reading Leaf's JSON               | `data-structures.html`, unchanged: its tables are generated from the schemas                                                                                                                                                                               |
| `/website/`         | Visitors and operators of leaf.page            | `website.html`, unchanged: it describes one deployment rather than Leaf                                                                                                                                                                                    |

The proposal removes `/ui/`, `/threads/`, `/event-log/` and `/registry/`. Explain
experimental status, requirements, page trust and access keys, and offline export
where their readers need them. Describe delivery by harness and status by visible
surface. Version comparison belongs with revisions; source, widgets, page code and
packages belong with pages. Serving should explain the stable address and recovery
through the canonical harness contract rather than prescribe one command for every
harness.

## Decision A: status depth

Recommendation: show the status readings with a short explanation, and link to the
protocol references for how the server derives them. The alternatives are the same
derivation under a closed disclosure, or a full explanation of the mechanism on the
site. Both alternatives keep a second copy of the protocol material.

## Decision B: site structure

Recommendation: adopt the reader-based routes above. The alternatives are keeping
the current routes and regrouping their tabs, or rewriting every current page in
place. A route change renames its document and also updates the links between the
site's pages, the Worker's routing fixtures
(`worker/test/index.test.ts`) and `tests/*/test_product_page.py`. The `x-` key
index moves with `leaf_dev.docs`'s `nav.reference-index` and `div.reference-list`
slots, which compose into whichever document holds them. Compare a rendered
candidate before deciding.
