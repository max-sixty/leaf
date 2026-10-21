/** Bridge a Solid reading to an imperative owner with an explicit lifetime.
 *
 * Leaf's document and keyboard owners register outside a component tree. Each
 * subscription owns one Solid root and releases it when its owner leaves. The
 * first delivery is synchronous, as are deliveries inside a publication's flush,
 * so presentation regions claim their work before that publication is sealed.
 */
import { createEffect, createRoot, createTrackedEffect, flush } from "@solidjs/signals";

export function subscribe<T>(read: () => T, notify: (value: T) => unknown): () => void {
  return flush(() =>
    createRoot((dispose) => {
      createEffect(read, (value) => {
        notify(value);
      });
      return dispose;
    }),
  );
}

/** Track an imperative owner's reads, ending the effect with that owner. */
export function watchEffect(run: () => void | (() => void)): () => void {
  return flush(() =>
    createRoot((dispose) => {
      createTrackedEffect(run);
      return dispose;
    }),
  );
}
