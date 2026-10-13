/* Registry-declared widget commands as the browser reads them. Composition stamps each
   verb's writer and admitted definition into `$states` (Python's
   `registry.contract.stamp_states`), so this module derives neither: it finds a verb's
   stamped state and compares a recorded definition with it. */

// The stamped state of the verb an action or report names, when the side that
// sent it is the verb's writer.
export function stampedState(states, event) {
  const state = states[event.action];
  const writer = { action: "user", report: "agent" }[event.kind];
  return state?.writer === writer ? state : null;
}

export function sameStateDefinition(recorded, current) {
  if (recorded === current) return true;
  if (
    !recorded ||
    !current ||
    typeof recorded !== "object" ||
    typeof current !== "object" ||
    Array.isArray(recorded) !== Array.isArray(current)
  )
    return false;
  const keys = Object.keys(recorded);
  return (
    keys.length === Object.keys(current).length &&
    keys.every(
      (key) =>
        Object.hasOwn(current, key) &&
        (typeof recorded[key] === "object"
          ? sameStateDefinition(recorded[key], current[key])
          : recorded[key] === current[key]),
    )
  );
}

// Registry keys share schema.WIDGET_NAME with Python. Exact custom-element names
// declare widgets; CSS selectors (including lf-options.selected) declare idioms.
export const isElementName = (name) => /^lf-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name);
