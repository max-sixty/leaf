/* Ask-local action contribution.
 *
 * A decision widget knows which of its controls actually answer or advance the Ask.
 * Core cannot recover that set by scanning generated controls: an option may contain
 * interactive evidence, while a suggestion's answer Buttons are hoisted outside the
 * widget. Each widget therefore contributes one ordered reading here. The decision view
 * projects that reading into numeric keys and address chips while semantic focus is on
 * the Ask itself; the controls remain the only implementation of the actions themselves. */

const registrations = new WeakMap();
const listeners = new Set();

const changed = () => {
  for (const listener of listeners) listener();
};

const words = (value) =>
  String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();

/** Register the ordered controls that work one decision source.
 *
 * `read` is called at projection time because a widget may exchange its controls while
 * keeping the same decision open. Each item is `{control, label}`; the label is the
 * action's short reader-facing name and the control's native `click()` remains the one
 * activation path.
 */
export function registerDecisionActions(source, read) {
  if (!(source instanceof Element))
    throw new TypeError("Decision actions need an Element source");
  if (typeof read !== "function")
    throw new TypeError("Decision actions need an ordered reading function");
  if (registrations.has(source))
    throw new TypeError("A decision source may register its actions only once");
  registrations.set(source, read);
  changed();
  return { update: changed };
}

export function decisionActions(source) {
  const read = registrations.get(source);
  if (!read) return [];
  const seen = new Set();
  return [...read()].map((action, index) => {
    const control = action?.control;
    const label = words(action?.label);
    if (!(control instanceof Element))
      throw new TypeError(`Decision action ${index + 1} has no Element control`);
    if (!label)
      throw new TypeError(`Decision action ${index + 1} has no label`);
    if (seen.has(control))
      throw new TypeError("A decision source registered one control twice");
    seen.add(control);
    return { control, label };
  });
}

export function watchDecisionActions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// TODO(2026-09-02): Evaluate package-declared mnemonic aliases after numeric Ask
// addresses have real usage evidence. Keep any mnemonic as an alias to this canonical
// action list rather than growing a second package-specific keymap.
