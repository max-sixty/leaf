/* Registry readings the browser shares with Python's registry.contract. A verb's
   state definition is the server's (`state_definition`, served in each view's
   `state_definitions`); the browser only compares two of them. */

// Whether two served definitions are the same, the comparison
// `registry.contract.same_state_definition` makes: deep, with a boolean never equal
// to a number.
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
