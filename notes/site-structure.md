# Site structure before release

The site at leaf.page currently summarizes Leaf's design and interfaces. Two
decisions about how its pages are organized wait until Leaf is closer to release
(`TODO.md`, "Decide the site's structure before release"). Delete this note once
both are decided and the result has landed.

The front page stays as it is; the other pages may be reorganized. Rewrite with
`/writing-prose`, check every dropped claim against the code, and have the result
reviewed independently. Judge it by what each reader can use and by preserved
meaning; word counts describe the cut, not its quality.

## Proposed routes

The current routes are `PRODUCT_ROUTES` in `dev/leaf_dev/site.py`. The proposal
gives each page one reader:

| Route | Reader and purpose |
|---|---|
| `/` | Existing front page |
| `/examples/` | Example users; package named on each card, developer galleries elsewhere |
| `/using/` | People operating a page and reading its status |
| `/how-it-works/` | Mechanism, incorporating the event log and one explanation of the fold |
| `/pages/` | Authors choosing page contents and layouts |
| `/extending/` | Package authors; ownership, package table and one worked extension |

The proposal removes the public registry page. It predates `/threads/` and
`/website/`, so it does not yet place them. Explain experimental status,
requirements, page trust and access keys, and offline export where their readers
need them. Describe delivery by harness and status by visible surface. Version
comparison belongs with revisions; source, widgets, page code and packages belong
with pages. Serving should explain the stable address and recovery through the
canonical harness contract rather than prescribe one command for every harness.

## Decision A: status depth

Recommendation: show the banner readings with a short explanation, and link to the
protocol references for how the server derives them. The alternatives are the same
derivation under a closed disclosure, or a full explanation of the mechanism on the
site. Both alternatives keep a second copy of the protocol material.

## Decision B: site structure

Recommendation: adopt the reader-based routes above. The alternatives are keeping
the current routes and regrouping their tabs, or rewriting every current page in
place. A route change also updates the links between the site's pages,
`PRODUCT_ROUTES`, the Worker's routing fixtures
(`worker/test/index.test.ts`) and `tests/*/test_product_page.py`. Removing
`/registry/` also needs a new page for the `x-` key index, which `leaf-dev keydocs`
writes into `docs/registry.html` and a test in `tests/*/test_interact_product.py`
checks is current. Compare a rendered candidate before deciding.
