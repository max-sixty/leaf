/* Registry-declared widget commands as the browser reads them. Composition stamps each
   verb's writer and admitted definition into `$states` (Python's
   `registry.contract.stamp_states`), so this module derives neither: it finds a verb's
   stamped state and compares a recorded definition with it. */
import { VERB_WRITERS, WIDGET_NAME } from "./kernel-facts.js";

/** One verb's state as composition stamps it (`registry.contract.stamp_states`). */
type StampedState = { writer: "user" | "agent"; definition: unknown };
export type StampedRegistry = { $states: Record<string, Record<string, StampedState>> };

// The stamped state of the verb an action or report names on `tag`, when the side that
// sent it is the verb's writer.
export function stampedState(
  registry: StampedRegistry,
  tag: string,
  event: { kind: string; action: string },
) {
  const state = registry.$states[tag]?.[event.action];
  return state?.writer === VERB_WRITERS[event.kind] ? state : null;
}

export function sameStateDefinition(recorded: unknown, current: unknown): boolean {
  if (recorded === current) return true;
  if (
    !recorded ||
    !current ||
    typeof recorded !== "object" ||
    typeof current !== "object" ||
    Array.isArray(recorded) !== Array.isArray(current)
  )
    return false;
  const fields = new Map(Object.entries(recorded));
  const other = new Map(Object.entries(current));
  return (
    fields.size === other.size &&
    [...fields].every(
      ([key, value]) => other.has(key) && sameStateDefinition(value, other.get(key)),
    )
  );
}

// Registry keys share `$names.widget` with Python. Exact custom-element names
// declare widgets; CSS selectors (including lf-options.selected) declare idioms.
export const isElementName = (name: string) => WIDGET_NAME.test(name);
