// @ts-check
/* The runtime's one random identifier: 128 random bits as 32 hex digits, for command
   attempts, draft generations, diagnostic sessions and document-local names.

   `crypto.randomUUID()` is a secure-context API, absent on a page `leaf --host` serves
   over plain HTTP to a LAN address, where calling it throws. `getRandomValues` is
   available in every context. bootstrap.js, a classic script that cannot import,
   carries the one copy of this function. Readers that validate an id hold it to this
   form: user_views.py's view session and the Worker's startup `loadId`. */
export const randomId = () =>
  Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
