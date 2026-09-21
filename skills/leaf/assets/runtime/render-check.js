/* Package-owned checks that only the render gate runs.
 *
 * A widget that draws through a third-party renderer can be wrong in a way the page
 * cannot afford to notice: the evidence is a second reading of the same source, by a
 * library too heavy to load for a reader. The widget registers that check here and the
 * gate runs it after presentation. A check that finds a problem reports it the way the
 * widget reports any failed rendering, through `failSoft`, so the gate's existing reading
 * of failed widgets carries it and no reader's page ever imports what the check imports. */

const registrations = new WeakMap();

/** Register `check` for one rendered source. It returns a promise that settles once the
 * widget has reported whatever it found. */
export function registerRenderCheck(source, check) {
  if (!(source instanceof Element))
    throw new TypeError("A render check needs an Element source");
  if (typeof check !== "function")
    throw new TypeError("A render check needs a function");
  if (registrations.has(source))
    throw new TypeError("A source may register its render check only once");
  registrations.set(source, check);
}

export const renderCheckOf = (source) => registrations.get(source);
