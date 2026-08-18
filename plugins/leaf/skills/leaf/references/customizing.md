# Customizing the layer

The layer is what every page vendors: the theme, the runtime, the widget vocabulary and
its modules. Read this when the subject is the layer rather than a page — a design
comment arrived (`"about": "layer"`), or `/leaf` was invoked on a widget to build or a
look to change.

## Where a change goes

| Layer                          | For                                              | Reaches                          |
| ------------------------------ | ------------------------------------------------ | -------------------------------- |
| the version's own `<style>`    | presentation of this one page                    | this page                        |
| the project's `.leaf/`         | a widget or a look this project needs — the default | pages made in this project    |
| the user's `~/.config/leaf/`   | one reader's taste                               | every page their sessions make   |
| leaf's shipped layer           | a defect in leaf, when the comment says "in leaf" | everyone, once pushed and installed |

The project layer is the default: it is where a widget the project asked for and a look
this project keeps belong, and it ships with the project. Reach for the user layer when
the words say the change is theirs everywhere. Leaf's shipped layer is another repository
for every session but one in a leaf checkout, so a change there is handed off as its own
task, carrying the comment's words, its anchor and the page's URL — and the page picks
the fix up on a later re-vendor.

`page init` overlays the layers in that order, lowest first: leaf's integrated layer, its
bundled widgets, the user's, the project's (resolved against the working directory, so run
project commands from the project root). Each mirrors one layout — `theme.css`,
`registry.json`, `icon.svg`, `widgets/`, `vendor/`. Theme files concatenate, so a short
later file overrides tokens or rules without copying the defaults; runtime, icon, widget
and vendor files replace by path; registry files merge at the unit of the contract — a
later layer replaces a tag's complete entry, and one member inside a `$` entry, so a new
widget adds its entry without copying the shipped registry, overriding a tag supplies its
whole schema, and an idiom declared under `$idioms` joins the shipped catalog beside the
theme rules that style it. The merged vocabulary is validated before vendoring.

## The commands

```bash
leaf customize theme [--user]                    # <layer>/theme.css, appended after the defaults
leaf customize widget lf-name [--upgrade] [--user]  # a registry entry, a theme rule, and with
                                                    # --upgrade the module widgets/lf-name.js
```

`customize theme` leaves an existing file alone. `customize widget` refuses a tag any
layer up to its own already declares, and `--upgrade` is part of the first scaffold, not
an upgrade of an existing one.

## A theme change

Tokens change every surface that reads them: `--accent`, `--r`, the three faces
`--serif` (the page's prose), `--sans` (the chrome and every injected control) and
`--mono` (evidence). Ordinary selectors tune one element or widget. A shape the project
reuses across pages is an idiom — declare it under `$idioms` in the layer's
`registry.json` (a selector, a description, an example) and style it in the layer's
`theme.css`; `page catalog` then lists it beside the shipped ones. Presentation unique to
one page stays in that version's `<style>`.

## A widget

The registry entry is JSON Schema over the element's attributes, plus the `x-` keys that
say how the layer treats the tag — its content model, whether a module upgrades it, which
attributes the reader sees as words, its action verbs and their record forms, whether it
stands as one of the page's asks. `page catalog` prints what each key means (`$keys`) and
the shipped entries are the worked examples; the entry's `x-example` must validate, and
is what the catalog shows.

A CSS-only widget is an entry and a theme rule. One with behavior takes a module, and the
scaffold's header comment lists what a module owes — every item is a section of the
skill's own `CLAUDE.md`, one directory up from this file, learned by getting it wrong: an absolute
`applyAction`, `says()` over `textContent`, `offer()` and `relabel()` on anything
injected, `keys()` at upgrade, `quoted()` before wiring input, durable state in
attributes because export drops the scripts. The helper surface `/leaf.js` exports is
the whole of what a module gets.

## Seeing it

```bash
leaf page init <page>                       # re-vendor: the page takes the layer as it is now
leaf version check <page> --render          # the browser gate, on the version that uses it
```

Re-running `page init` on a live page is the explicit re-vendor; note it in the next
version's changelog. It refuses when the incoming layer no longer accepts a logged
event kind or action contract, since that event would stop replaying. The render gate
is where a module's mistakes surface — an upgrade that defines no element, a widget of no
size, a `x-verbatim` the rendered words contradict, a shadow root the entry doesn't
declare, a word the registry promised that never reached the page, an attribute left on
the element that its entry doesn't declare, an `applyAction` that moves under
re-application.

Then put it on the page. A widget is reviewed in place: the version that follows the
comment uses it where the comment asked, and the reader comments on it there. From the
terminal, `/leaf build a timeline widget for the release page` names the layer as its
subject, and the page it makes shows the widget in use.

## A design comment

The reader's design mode (`i` in the browser) posts a comment about the layer rather
than the page: `"about": "layer"`, anchored on the element they clicked or the words they
selected. The anchor's `section` is a widget's id, or the id of a runtime part —
`lf-banner`, `lf-comments` (the panel), `lf-leaves` (the leaves panel), `lf-versions`,
`lf-composer`, `lf-comment-button` (the margin's 💬), `lf-keyline`, `lf-help` — and
`part` names the control the click landed on, where it landed on one (`✓ Accept`,
`Comments (2)`).

```json
{"kind": "comment", "about": "layer", "version": 3, "anchor": {"section": "feeder-board"}, "text": "cards are cramped — give the column a floor"}
```

Answer it with the layer: change it where the table above says, `page init` the page,
publish the version, and reply in-thread saying where the fix landed. The new version is
the answer, on the element the comment was made on. A comment naming leaf itself is the
hand-off above.
