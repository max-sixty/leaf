# Previews

Read with [module-authoring.md](module-authoring.md).

Pointing reads; pressing acts (`interface-goals.md`). Leaf previews an element when a
pointer rests on it, when Tab brings the keyboard to it or something inside it, and when
a finger holds it, beside the element over the page, in one face: a name with key chips,
then lines of detail. An element with no Tab stop, such as an age, previews to the
keyboard when the caret stands in it and the user presses `K`, in browsers with caret
browsing (Chromium and Firefox), so a preview needs no Tab stop of its own. Leaf then
calls `lfPreview("focus")`, though the element doesn't hold focus. A command's
landing, such as a walk's, previews nothing, since
what the user asked the command for is in front of them (`module-input.md`, "Focus and layers"). The preview holds no control, so a control the user presses stays
on the widget; a pointer may cross onto it to read it, and a finger's long press reads
it and presses nothing, so a widget's click answers a tap alone.

A control needs no declaration. It previews its accessible name where its face shows a
symbol or doesn't say that name, and as chips each key that presses it from where the
user is, as the attribute `aria-keyshortcuts` says it. A control whose face says its name
and that no key reaches previews nothing. Its
`aria-description` stays a screen reader's; a line the eye should read too goes in
`detail`.

A widget adds to that, or previews an element that isn't a control, by declaring the
element's `lfPreview(route)`, with no import, as it declares `lfCommands`. Leaf calls it
once each time the preview shows, with the route that asked: `"pointer"`, `"focus"` or
`"hold"`, and again for each new presentation of the document while the preview
stands, so what it says follows the page without tracking its own inputs; words that
come back the same leave the preview as it is. It returns:

- `{name, keys, detail, list, at, about, excerpt, unseen}`, every field optional. `name`
  replaces the control's accessible name in the preview, or names an element that has
  none. `keys`
  adds presses Leaf's own chips leave out, such as the activation keys a drag grip
  names. Each press is a list of bindings, one for a single key and one for each step
  of a sequence, spelled as a command row's `keys` are (`module-input.md`, "Command
  rows"), as in `keys: [["Enter"], [" "]]`, and Leaf draws each binding as a key chip. `detail` is lines under the name, each words or
  an `html` template; a falsy line is left out. `at` is where the preview stands, the
  declaring element by default: another element, as a message stands its preview by
  the `<time>` in its head, or a box in client coordinates (`{left, top, right, bottom}`, such as
  a `DOMRect`) inside the element, as a chart's value stands over its point, which the
  preview stands above and takes no pointer, so the pointer goes on reading the element
  beneath it. Readings standing by one element redraw in place as the aim moves among
  them. `about` is the element the preview is about, which Leaf leaves
  in view as it places the preview, as a margin entry's passage or a time's message;
  the box it stands by is always left in view, and the preview shows only while some
  of that box does, so a point scrolled out of view takes its preview with it, though
  its element still shows, and a focus preview comes back as it returns.
  `excerpt: true` gives a preview that quotes a block of the page the face's wider room. A preview taller than the room beside its element shows the
  lines that fit and ends the last in an ellipsis; no preview scrolls, so what pressing
  the element opens says the rest. `list: {items, more}` is items under the lines, each
  words or a template, as the threads standing at one place: Leaf shows as many as the
  room holds, through every resize, and under them `more(count)`'s words for the rest,
  such as "and 26 more threads", so the items need no measuring of their own; the rest
  are hidden from sight and from a screen reader alike. `unseen: true` keeps the face
  from sight where the element draws its own; its words still describe what has
  focus.
- `null` where the element adds nothing now, including where the words it would say
  already show on it or beside it: a control keeps its own preview, and the search goes
  on to what holds the element.
- `false` where nothing should preview here or around it, as a pinned card already
  shows what its phrase would.

What it throws is reported, and nothing shows. Where what an element previews changes
while the user's aim stays on it, as a chart's pointer, key or finger reaches another
point, or a grip's words stop being true once its card is grabbed, the widget says so
with an `lf-preview` event at the element:

```js
element.dispatchEvent(new CustomEvent("lf-preview", { bubbles: true, composed: true }));
```

Leaf then calls `lfPreview` again and redraws a standing preview where it stands, or
shows the new one to a pointer resting on the element or a finger holding it. Off
Leaf, nothing hears the event. It never brings back a preview the user put away, nor opens one on
focus: only the user aiming again does. Where the user aimed at something new inside the
element, as a chart's pointer or arrow key reaching another point, the widget says so
with `detail: { aim: true }` on the event, and the new target shows its preview whatever
put the last one away, to the pointer, the keyboard's focus or a finger. A mark the widget draws for what its preview
reads, as a chart's ring on the point it names, comes off when Leaf dispatches
`lf-preview-ended` at the element, a `CustomEvent` whose `detail.declared` is the object `lfPreview` returned for the
reading that ended, as the preview goes for any reason: the pointer or focus leaving,
the pointer leaving the window, the next touch after a finger's hold, Escape, or
another target's preview taking its place. A focus preview hidden while the box it
stands by is out of sight hasn't ended, so the mark stays. `lfPreview` returns a new
object for each reading, since that object is how a widget tells the reading that ended
from one it has returned since. A redraw with new words is no ending. A widget that has returned a
newer reading since, as focus arriving reads the point a pointer's preview had, keeps
the mark for that one.

A `title` stays the browser's: a pointer over an element with one, or inside one, gets
the browser's tooltip and no preview, and focus and a finger, which the browser's
tooltip never reaches, read its words in the preview. Leaf neither writes nor removes
it. A widget that wants Leaf's face for the pointer too, its key chips included,
declares the words in `lfPreview` and writes no `title`. Off Leaf nothing reads
`lfPreview`.

A thread's words preview the thread to a pointer or a finger only where nothing else
there takes the pointer: a control, native or ARIA, an element with a `title` or an
`lfPreview`, or a widget that draws its content itself (`content` `data`, `markdown`
or `empty`). There the element's own preview shows, or none, and the thread is reached
by its margin entry. Words a widget holds of the author's markup, outside any control
in it, preview their thread. A thread on a whole element, such as a widget, draws no
mark on the element, so only the thread's margin entry previews it.

A link an author wrote to a place on the page previews that place with no declaration.
A link a widget draws previews nothing of the place unless the widget declares it,
since only the widget knows whether its words already say what the place holds; to
show the place, return `placePreview(element)`, the name, first lines, answer and
threads Leaf shows for an authored link.
