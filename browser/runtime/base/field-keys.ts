/* Keys typed into a field Leaf builds stay with Leaf: the comment box and every other
 * `leaf-text` (annotations/composing/text-field.js), and the search boxes, `searchField`'s and the
 * panel's own (dom/control-labels.js, panel/floating-panel.js).
 *
 * Page shortcut code skips a key typed into a text field by asking whether the focused
 * element, or the event's target, is an input, a textarea or editable. A `leaf-text`
 * and a `wa-input` hide their editors in shadow roots, so the page sees only a host
 * that is none of those, and a slide deck's own `b` blacked the deck out mid-comment.
 * A page's checks are written for its own fields in any case, not for Leaf's. So
 * `keepFieldKeys` stops each keydown, keypress and keyup at the field's host as it
 * bubbles out, once the field's own handling has run and Leaf's key dispatcher has
 * read it there (`readLeavingKeys`, panel/page-keys/controller.js). No listener outside the
 * field, the page's or Leaf's, hears it bubble, so Leaf's other readers of these keys
 * listen in capture; a page listener in capture still hears it. A field's `input`
 * still reaches the page, as a textarea's does.
 *
 * Rejected: the host answering `isContentEditable`, which reveal.js asks of the focused
 * element but a check by tag or selector never does, and a page that checks nothing
 * hears every key regardless.
 *
 * Dependency-free, since `searchField` builds fields in documents without Leaf too,
 * where nothing reads the keys and they stop at the field all the same. */

const readers: Set<(event: KeyboardEvent) => void> = new Set();
export const readLeavingKeys = (read: (event: KeyboardEvent) => void) =>
  void readers.add(read);

export function keepFieldKeys(host: HTMLElement) {
  for (const type of ["keydown", "keypress", "keyup"] as const)
    host.addEventListener(type, (event) => {
      for (const read of readers) read(event);
      event.stopPropagation();
    });
}
