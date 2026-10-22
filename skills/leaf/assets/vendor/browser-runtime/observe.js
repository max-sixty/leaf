/** Bridge a Solid reading to an imperative owner with an explicit lifetime.
 *
 * Leaf's document and keyboard owners register outside a component tree. Each
 * subscription owns one Solid root and releases it when its owner leaves. The
 * first delivery is synchronous, as are deliveries inside a publication's flush,
 * so presentation regions claim their work before that publication is sealed.
 */
import {
  createEffect,
  createRoot,
  createReaction,
  flush,
  runWithOwner,
} from "../solid.js";

export function subscribe   (read         , notify                       )             {
  return flush(() =>
    runWithOwner(null, () =>
      createRoot((dispose) => {
        createEffect(read, (value) => {
          notify(value);
        });
        return dispose;
      }),
    ),
  );
}

/** Follow one imperative draw. Its first invalidation claims another scheduled draw;
 * it never paints inside Solid's effect phase, where a draw cannot publish state. */
export function watchReaction(read            , moved            )             {
  return runWithOwner(null, () =>
    createRoot((dispose) => {
      let first = true;
      const track = createReaction(moved);
      track(() => {
        if (!first) return;
        first = false;
        read();
      });
      return dispose;
    }),
  );
}
// Generated from build/browser/observe.ts by build/browser/build.mjs.
