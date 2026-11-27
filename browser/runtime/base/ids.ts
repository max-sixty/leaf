/* The runtime's identifiers: one random identifier, and the numbering that names an
   object in a key built of strings.

   `randomId` is 128 random bits as 32 hex digits, for command attempts, draft
   generations, diagnostic sessions and document-local names. `crypto.randomUUID()` is
   a secure-context API, absent on a page `leaf --host` serves over plain HTTP to a LAN
   address, where calling it throws. `getRandomValues` is available in every context.
   bootstrap.js, a classic script that cannot import, carries the one copy of it.
   Readers that validate an id hold it to this form: user_views.py's view
   session and the Worker's startup `loadId`. */
export const randomId = () =>
  Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");

// Returns a function that gives each object it is asked about a whole number, counting
// from 1, and the same number at every later ask, so a key built of strings, or one Lit
// compares, can name the object. It holds the objects weakly.
export function objectIds() {
  const ids: WeakMap<object, number> = new WeakMap();
  let last = 0;
  return (object: object) => {
    let id = ids.get(object);
    if (id === undefined) ids.set(object, (id = ++last));
    return id;
  };
}
