# How a Leaf page should feel

These goals apply [SOUL.md](../SOUL.md) to a widget, a package's stylesheet or a page's
own CSS. How a page meets them is its author's call; Leaf's exact specs bind only Leaf.
Which goals Leaf should also check on other authors' pages is still being settled.

- **The page holds still under the user's aim.** A change the user didn't make moves
  nothing they are reading, pointing at or typing into.
- **Typed words survive.** Words in an editor stay there until the user sends or
  discards them.
- **A gesture shows its result at once.** What the page can draw from the user's act
  appears as they make it.
- **Controls are few and quiet.** Each earns its place against the content and takes
  only its own room.
- **Pointing reads; pressing acts.** Pointing at a mark, control or value, Tabbing
  onto it or holding a press on it shows its whole word and a preview of what pressing
  it opens, or of the fact it stands for, over the page and moving nothing. The
  keyboard and a finger read the same, so no fact is said to hover alone; a widget
  declares its preview as `lfPreview` (`module-input.md`, "Previews"). A preview says
  only what the user can't read where they aim, never the words a face, caption or
  heading already shows, and a figure or drawing in view needs no name of its own. A
  `title`, an SVG `<title>` among them, shows as the browser's tooltip over everything
  inside it, so name a drawing for a screen reader with `aria-label` or a
  `<figcaption>`.
- **Visual treatment carries meaning.** Hierarchy and state come from the content and
  from treatments that mark something, not from decoration.
- **Motion is brief and keeps the user oriented.** Nothing the user must read, press or
  decide waits on an animation.
- **A region that must scroll behaves like the document.** It passes scrolling on at its
  edges and can be reached by keyboard.
