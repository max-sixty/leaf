/** A Solid view mounted once in an imperative Leaf owner's generated container.
 *
 * The owner publishes complete view props. Components read the accessor in their
 * bindings, so updating a view retains its DOM, native state and Solid ownership.
 * The explicit flush is Leaf's imperative presentation boundary: once update
 * returns, focus, measurement and presentation proof can read the resulting DOM.
 */
import { createSignal, flush } from "../solid.js";
import { render } from "../solid.js";


export function createView   (
  container                                ,
  component                                 ,
  initial   ,
) {
  const [props, setProps] = createSignal   (() => initial, { ownedWrite: true });
  const dispose = render(() => component(props), container);
  return Object.freeze({
    update(next   ) {
      flush(() => setProps(() => next));
    },
    dispose,
  });
}
// Generated from build/browser/views.ts by build/browser/build.mjs.
