/** A Solid view mounted once in an imperative Leaf owner's generated container.
 *
 * The owner publishes complete view props. Components read the accessor in their
 * bindings, so updating a view retains its DOM, native state and Solid ownership.
 * The explicit flush is Leaf's imperative presentation boundary: once update
 * returns, focus, measurement and presentation proof can read the resulting DOM.
 */
import { createSignal, createProjection, flush } from "@solidjs/signals";
import { render } from "@solidjs/web";
import type { JSX } from "@solidjs/web";

export function createView<T>(
  container: HTMLElement | DocumentFragment,
  component: (props: () => T) => JSX.Element,
  initial: T,
) {
  const [snapshot, setSnapshot] = createSignal(
    { current: initial },
    { ownedWrite: true },
  );
  // A projection reconciles complete snapshots into per-field reactive readings.
  // A changed field cannot invalidate bindings that read only unchanged fields.
  const props = createProjection(snapshot);
  const dispose = render(() => component(() => props.current), container);
  return Object.freeze({
    update(next: T) {
      flush(() => setSnapshot({ current: next }));
    },
    dispose,
  });
}
