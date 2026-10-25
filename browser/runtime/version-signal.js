/* A version signal says that a fact outside the application state moved, so a paint
   that read the fact reads it again (semantic-state.js, `applicationPresenter`): a
   reader reads the signal beside the fact, and the owner advances the signal when
   the fact changes.

   `tick` advances one without reading it. `version.value += 1` reads the signal
   first, and run inside a paint, as an owner's commit is, it subscribes that paint to
   its own write, so the region claims another pass for nothing. The eslint rule
   `no-restricted-syntax` on `.value +=` in the runtime points here. */

/** @param {{ peek(): number, value: number }} version */
export const tick = (version) => {
  version.value = version.peek() + 1;
};
