/* One lifetime-bound subscription to a complete browser projection.

   `lf-actions` is the runtime's broad invalidation signal, not a package contract.
   Semantic APIs supply `read`: actions, updates, requests, and Decisions all share
   this lifecycle without exposing the event or copying its cleanup rules. */
export function watchProjection(owner, read) {
  if (!(owner instanceof Element))
    throw new TypeError("A projection watcher needs an Element owner");
  if (typeof read !== "function")
    throw new TypeError("A projection watcher needs a reading function");
  const update = () => {
    if (!owner.isConnected) {
      document.removeEventListener("lf-actions", update);
      return;
    }
    read();
  };
  document.addEventListener("lf-actions", update);
  update();
  return () => document.removeEventListener("lf-actions", update);
}
