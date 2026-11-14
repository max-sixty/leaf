# Focus rings at a bounded block's side

A focus ring is drawn outside its box, and a scroller clips at its padding edge. At a
scroller's top and foot a landing keeps the ring's room (`--focus-ring-landing`,
`browser/styles/components/surfaces.css`), for a vendor control's focused node too. A
bounded block (`[data-lf-bound]`, `browser/base.css`) has no inline padding and usually
nothing to scroll sideways, so a box flush with its side loses that side of its ring
however far the block is scrolled.

At the top and foot, a `wa-select` and a single-thumb `wa-slider` keep under a pixel of
room, where a diff's file filter keeps 6. The margin is on the node holding focus, and
their ring stands on a box that reaches further: the select's combobox around its input,
and the slider's thumb 7px below its rail. No bundled widget uses either control.

Two written rules disagree about this. The choice between them waits on the user
(#4125), who judged focus rings too central for another per-case patch (2026-10-25).

- The `browser/runtime/chrome.css` header says every scroll region a ringed box can land
  in pads its edges by the room of the widest ring it holds. A sidebar page's `.layout-track`
  (`browser/layouts.css`) does, with `--focus-region-room` on every side.
- `browser/styles/tokens.css`, "Where it stands", says a box that clips a mark standing
  outside its target cuts it. `browser/AGENTS.md` says no rule pads or widens a block to
  make room for what Leaf draws over it. A bounded block does as these two say.

## Cases

Measured in headless Chromium 156 and Firefox 157 on 2026-11-04, with the same numbers in
both. "Room" is the space between the ring's outer edge and the block's padding edge;
negative means cut.

| What stands in the block                      | Room at its start | Room at its end |
| --------------------------------------------- | ----------------- | --------------- |
| A link that starts a line                     | −5px              | clear           |
| A summary, which fills its line               | −5px              | −5px            |
| A native `input.field` that starts a line     | −2px              | clear           |
| A diff's file filter (`wa-input`), filling it | −3px              | −3px            |
| A package's `wa-select`, filling it           | −3px              | −3px            |

## Candidates

Each candidate was laid over this tree as a sheet and read in both engines, and each is
titled by what the user sees.

- **Every ring in a bounded block is whole, and its words stay on the column.** The
  block reaches 8px past its column on each side and pads by as much. Its box is 16px
  wider, so a frame an author draws on it stands 8px out on each side, as does its
  scrollbar. It widens a block for a ring, which `browser/AGENTS.md` rules out.

  ```css
  [data-lf-bound] {
    padding-inline: var(--focus-region-room);
    margin-inline: calc(-1 * var(--focus-region-room));
  }
  ```

- **Every ring in a bounded block is whole, and its words stand 8px in.** The block pads
  its sides inside the column, so every bounded block's words stand 8px in from the
  column's, whether or not a ring is showing. It pads a block for a ring, which
  `browser/AGENTS.md` rules out.

  ```css
  [data-lf-bound] {
    padding-inline: var(--focus-region-room);
  }
  ```

- **A field's ring is whole anywhere, and a link or summary stays cut.** A field's ring
  stands inside its border, so nothing moves. Every field's ring stands 2-3px tighter on every page. A link
  and a summary stay cut.

  ```css
  wa-input::part(base lf-focus-visible-within),
  wa-select::part(combobox lf-focus-visible-within) {
    outline-offset: var(--focus-ring-inset);
  }
  input.field {
    --lf-ring-at: var(--focus-ring-inset);
  }
  ```

- **Nothing moves, and a ring against a bounded block's side stays cut.** The
  `browser/runtime/chrome.css` header narrows to the scrollers that keep the room.

## Reproduction

Save the page as `.tmp/bound.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <title>A bounded block</title>
  </head>
  <body>
    <main class="layout-column">
      <h1>Edges</h1>
      <div id="log" data-bound="start" style="--lf-bound: 16rem">
        <p><a id="lead" href="#lead">A link that starts its line</a></p>
        <details>
          <summary id="fold">A summary</summary>
          <p>Inside.</p>
        </details>
        <p><input id="native" class="lf-field" aria-label="A field" /></p>
        <lf-diff id="patch">
          <pre>
diff --git a/one.py b/one.py
--- a/one.py
+++ b/one.py
@@ -1,1 +1,1 @@
-old
+new
diff --git a/two.py b/two.py
--- a/two.py
+++ b/two.py
@@ -1,1 +1,1 @@
-old
+new
</pre>
        </lf-diff>
      </div>
    </main>
  </body>
</html>
```

Then read the room at each side, with `--browser` set to `chromium` or `firefox`. A
`wa-select` is built in the page, since a page's own module can't import
`/vendor/webawesome.esm.js` and only a package's can.

```sh
READ='() => {
  let at = document.activeElement;
  while (at.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  while (getComputedStyle(at).outlineStyle !== "solid")
    at = at.parentElement ?? at.getRootNode().host;
  const style = getComputedStyle(at);
  const out = parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
  const ring = at.getBoundingClientRect();
  const block = document.getElementById("log").getBoundingClientRect();
  return { start: ring.left - out - block.left, end: block.right - ring.right - out };
}'
SELECT='async () => {
  const entry = document.querySelector("script[data-lf-entry]").dataset.lfEntry;
  await import(new URL("vendor/webawesome.esm.js", new URL(entry, location.href)));
  const select = document.createElement("wa-select");
  select.label = "Route";
  select.innerHTML = "<wa-option value=a>First</wa-option>";
  document.getElementById("log").prepend(select);
  await select.updateComplete;
  select.shadowRoot.querySelector("[part~=display-input]").focus();
  await new Promise(requestAnimationFrame);
  return ('"$READ"')();
}'
for target in '#lead' '#fold' '#native' '#patch .lf-diff-search input'; do
  uv run leaf-dev probe .tmp/bound.html --browser firefox --viewport 1280x700 \
    --do press:Tab --do "focus:$target" --js "$READ" | jq -c .result
done
uv run leaf-dev probe .tmp/bound.html --browser firefox --viewport 1280x700 \
  --do press:Tab --js "$SELECT" | jq -c .result
```
