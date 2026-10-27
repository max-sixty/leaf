# How a Leaf page should feel

These goals hold for everything on a page: a widget, a package's stylesheet and a
page's own CSS, as for Leaf's own interface. They apply [SOUL.md](../SOUL.md),
"Preserve the user's attention and work" and "Make the work concrete and playable".
How a page meets them is its author's call. Leaf's exact specs, such as its contours,
symbols, tokens and timings, are Leaf's own and bind only its runtime and bundled
packages. Which of these goals Leaf should also check on other authors' pages is still
being settled.

- **The page holds still under the user's aim.** A change the user didn't make moves
  nothing they are reading, pointing at or typing into. News from the agent or a data
  source lands where it moves nothing in view, or waits until the reader goes to it.
  A widget keeps the box it painted first and grows with its content rather than
  scrolling inside itself, unless its task needs a region kept in view; the render
  check reports both (`keeps-first-box` and `grows-with-content`, and
  [module-authoring.md](module-authoring.md), "First paint").
- **Typed words survive.** Words in an editor stay there until the user sends, cancels
  or closes them, through scrolls, resizes and updates. Editing something opens it
  where it stood and as it read.
- **A gesture shows its result at once.** What the page can draw from the user's act
  appears as they make it. Only what the agent or the log decides waits, and a fast
  answer shows no spinner.
- **Controls are few and quiet.** Each earns its attention against the page's content,
  and takes only its own room, joining a line already there rather than reserving a
  strip. A control built by its role ([module-authoring.md](module-authoring.md),
  "Generated controls") looks like Leaf's own.
- **Visual treatment carries meaning.** Hierarchy and state come from the content and
  from treatments that mark something, not from decoration.
- **Motion is brief and keeps the user oriented.** Nothing the user must read, press or
  decide waits on an animation. Leaf's motion gate
  ([module-scroll-and-motion.md](module-scroll-and-motion.md), "Motion") honours
  reduced motion.
- **A region that must scroll behaves like the document.** It passes scrolling on at its
  edges and stays reachable by keyboard.
