# Packages

`../skills/leaf/references/packages.md` and the `package-*.md` files beside it own the package
contract, and `../skills/leaf/references/module-authoring.md` and the `module-*.md`
files own what a behavior module must do and the public browser API. `../browser/AGENTS.md` holds the
browser-wide rules a module must keep, including "Leaf's interface", which binds the
bundled packages, and "Renderers", which a port of a widget from Lit to Effect UI
follows; `../skills/leaf/references/interface-goals.md` is what other authors'
packages get.

## A widget's need of Leaf

The bundled widgets are written beside the runtime, where exporting one more name is
the cheapest way to finish a change, and each name stays for every author to learn
(root `AGENTS.md`, "Keep the package interface small"). So a change that finds a widget
needing something of Leaf asks, before it adds a name:

- **Whether it is a need.** A look matched exactly and a final box before the module
  draws are wants (root `AGENTS.md`, "Keep the package interface small"). A widget
  meets one with its own stylesheet and the library, or goes without.
- **Whether the widget needs Leaf for this at all.** HTML, CSS and the browser's own
  APIs add nothing to the interface. Neither does shared web code that keeps none of
  the page's state, which belongs in the library (`../browser/AGENTS.md`, "The library
  of shared web code").
- **Whether Leaf can do it from outside.** Leaf drives a widget as it would any custom
  element: it sets properties, hears events, and reads what the element and its
  stylesheet state. A promise kept that way holds for a widget that imports nothing,
  another library's component included, so prefer it to a function the widget calls.
- **Which kind of thing it is.** Each kind of thing a package leans on Leaf for takes
  one form (`../skills/leaf/references/module-authoring.md`, "The interface"). A need
  takes its kind's form. One that fits no kind is a gap in the contract, to put to the
  maintainer.
- **Who else would use it.** A name only one bundled widget uses is usually in the wrong
  place: the promise belongs to Leaf, kept for every element, or the code belongs to
  that widget. A need a page's author has too, who writes no module, is an element both
  can write, weighed as any new tag is (root `AGENTS.md`, "Weigh what a change adds").

The commit that adds a name says what the name replaces, or why no existing name
carries the need. A name that stays after a change tried to remove it states in its
owner's header what removing it broke, so the next attempt starts from that: a
guarantee of `SOUL.md`, or something only Leaf holds that no property, event or
attribute could carry. Lines the widget would write instead are not such a reason.
