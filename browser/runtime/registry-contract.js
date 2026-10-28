/* Registry-declared widget commands as the browser reads them. Composition stamps each
   verb's writer and admitted definition into `$states` (Python's
   `registry.contract.stamp_states`), so this module derives neither: it finds a verb's
   stamped state and compares a recorded definition with it. */
import { VERB_WRITERS, WIDGET_NAME } from "./kernel-facts.js";

// The stamped state of the verb an action or report names on `tag`, when the side that
// sent it is the verb's writer.
export function stampedState(registry, tag, event) {
  const state = registry.$states[tag]?.[event.action];
  return state?.writer === VERB_WRITERS[event.kind] ? state : null;
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

// Registry keys share `$names.widget` with Python. Exact custom-element names
// declare widgets; CSS selectors (including lf-options.selected) declare idioms.
export const isElementName = (name) => WIDGET_NAME.test(name);
