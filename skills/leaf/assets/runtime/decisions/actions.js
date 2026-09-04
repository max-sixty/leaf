/* Ask-local action contribution.
 *
 * A decision widget knows which of its controls actually answer or advance the Ask.
 * Core cannot recover that set by scanning generated controls: an option may contain
 * interactive evidence, while a suggestion's answer Buttons are hoisted outside the
 * widget. Each widget therefore contributes one ordered reading here. The decision view
 * turns that reading into one command route per action while the reader stands anywhere
 * in the Ask. Keys, Help, the key line, address chips, and accessible shortcuts consume
 * those routes; the controls remain the only implementation of the actions.
 * A widget that already owns an address face may contribute it as the placement anchor,
 * keeping the Ask projection aligned with the widget's local keyboard scope. */

const registrations = new WeakMap();
const listeners = new Set();

const changed = () => {
  for (const listener of listeners) listener();
};

const words = (value) =>
  String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
const ANSWER_CAP = 120;
const answerWords = (value) => {
  const whole = words(value);
  if ([...whole].length <= ANSWER_CAP) return whole;
  const short = [...whole].slice(0, ANSWER_CAP).join("");
  const at = short.lastIndexOf(" ");
  return (at > ANSWER_CAP / 2 ? short.slice(0, at) : short).trimEnd() + "…";
};

/** Register the ordered controls and current answer for one decision source.
 *
 * `read` is called at projection time because a widget may exchange its controls while
 * keeping the same decision open. Each item is `{control, label, address?}`; the label is
 * the action's short reader-facing name, an optional empty address face supplies its
 * canonical placement, and the control's native `click()` remains the one activation path.
 * `answer` reads the concise words the tray shows after that decision is answered.
 */
export function registerDecisionActions(source, read, answer) {
  if (!(source instanceof Element))
    throw new TypeError("Decision actions need an Element source");
  if (typeof read !== "function")
    throw new TypeError("Decision actions need an ordered reading function");
  if (typeof answer !== "function")
    throw new TypeError("Decision actions need a current-answer reading function");
  if (registrations.has(source))
    throw new TypeError("A decision source may register its actions only once");
  registrations.set(source, { read, answer });
  changed();
  return { update: changed };
}

export function decisionActions(source) {
  const registration = registrations.get(source);
  if (!registration) return [];
  const seen = new Set();
  const seenAddresses = new Set();
  return [...registration.read()].map((action, index) => {
    const control = action?.control;
    const label = words(action?.label);
    const address = action?.address ?? null;
    if (!(control instanceof Element))
      throw new TypeError(`Decision action ${index + 1} has no Element control`);
    if (!label) throw new TypeError(`Decision action ${index + 1} has no label`);
    if (address !== null && !(address instanceof Element))
      throw new TypeError(`Decision action ${index + 1} has no Element address`);
    if (seen.has(control))
      throw new TypeError("A decision source registered one control twice");
    if (address && seenAddresses.has(address))
      throw new TypeError("A decision source registered one address twice");
    seen.add(control);
    if (address) seenAddresses.add(address);
    return { control, label, address };
  });
}

export function decisionAnswer(source) {
  const registration = registrations.get(source);
  return registration ? answerWords(registration.answer()) : "";
}

export function watchDecisionActions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// TODO(2026-09-02): Evaluate package-declared mnemonic aliases after numeric Ask
// addresses have real usage evidence. Keep any mnemonic as an alias to this canonical
// action list rather than growing a second package-specific keymap.
