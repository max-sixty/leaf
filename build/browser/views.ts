/** A Solid view mounted in an imperative Leaf owner's generated container.
 *
 * The owner publishes complete props. Top-level projection fields track bindings
 * independently; immutable lists keep the identities their For component chooses.
 * Updates flush synchronously so gesture, focus and measurement share one reading.
 * Failure replacement releases affected roots. A retained owner can publish again
 * into the same container; terminal dispose ends that owner's lifetime.
 */
import { createSignal, createProjection, flush, runWithOwner } from "@solidjs/signals";
import { Errored } from "solid-js";
import { render } from "@solidjs/web";
import type { JSX } from "@solidjs/web";

type ViewContainer = HTMLElement | ShadowRoot;
const roots = new WeakMap<ViewContainer, () => void>();

/** Release generated views before their DOM is replaced by a failure surface. */
export function resetViewsWithin(container: HTMLElement | ShadowRoot) {
  const nodes: (HTMLElement | ShadowRoot)[] = [container];
  for (const node of container.querySelectorAll<HTMLElement>("*")) {
    nodes.push(node);
    if (node.shadowRoot) resetViewsWithin(node.shadowRoot);
  }
  // Capture all owners before an outer disposer removes their containers.
  const resets = nodes.flatMap((node) => {
    const reset = roots.get(node);
    return reset ? [reset] : [];
  });
  for (const reset of resets.reverse()) reset();
}

export function createView<T extends object>(
  container: ViewContainer,
  component: (props: () => T) => JSX.Element,
  initial: T,
) {
  let current = initial;
  let stop: (() => void) | null = null;
  let disposed = false;
  let failure: { error: unknown } | null = null;
  let publish: (next: { current: T }) => unknown;
  const reset = () => {
    stop?.();
    stop = null;
  };
  // Catch inside Solid, then rethrow at Leaf's imperative boundary. An uncaught
  // binding error otherwise halts the shared scheduler, including unrelated views.
  const checkFailure = () => {
    if (!failure) return;
    const { error } = failure;
    failure = null;
    reset();
    throw error;
  };
  const mount = () => {
    if (container.firstChild) container.replaceChildren();
    stop = runWithOwner(null, () =>
      render(() => {
        const [snapshot, setSnapshot] = createSignal({ current }, { ownedWrite: true });
        publish = setSnapshot;
        const props = createProjection<Record<string, unknown>>(
          () => ({ ...snapshot().current }) as Record<string, unknown>,
          null,
          { shallow: true },
        );
        return Errored({
          get children() {
            return component(() => props as T);
          },
          fallback(error) {
            failure = { error: error() };
            return null;
          },
        });
      }, container),
    );
    checkFailure();
  };
  mount();
  roots.set(container, reset);
  return Object.freeze({
    update(next: T) {
      if (disposed) throw new Error("Cannot update a disposed Solid view");
      current = next;
      if (stop) {
        flush(() => publish({ current }));
        checkFailure();
      } else mount();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      roots.delete(container);
      reset();
    },
  });
}
