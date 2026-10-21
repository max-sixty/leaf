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

export function createView<T extends object>(
  container: HTMLElement,
  component: (props: () => T) => JSX.Element,
  initial: T,
) {
  const [snapshot, setSnapshot] = createSignal(
    { current: initial },
    { ownedWrite: true },
  );
  const dispose = render(() => {
    // Track top-level props without merging records inside them. Immutable lists
    // keep their own identities: For's key, rather than a store's default id key,
    // decides which row survives a reorder or filter.
    const props = createProjection<Record<string, unknown>>(
      () => ({ ...snapshot().current }) as Record<string, unknown>,
      null,
      { shallow: true },
    );
    return component(() => props as T);
  }, container);
  return Object.freeze({
    update(next: T) {
      flush(() => setSnapshot({ current: next }));
    },
    dispose,
  });
}
