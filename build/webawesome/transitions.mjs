/* Web Awesome's async open/close watchers and their public promises share one
 * transition. Superseding it settles the old request as false and removes its
 * animation; only the current watcher may commit after an await. CSS animations
 * stay with the browser, including reduced motion and animation cancellation. */
const transitions = new WeakMap();

function claimTransition(owner) {
  transitions.get(owner)?.cancel();
  const open = owner.open;
  let resolve, reject;
  const finished = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  const cleanups = new Set();
  const transition = {
    cleanups,
    finished,
    resolve,
    reject,
    started: false,
    get current() {
      return transitions.get(owner) === transition && owner.open === open;
    },
    cancel() {
      for (const cleanup of cleanups) cleanup();
      resolve(false);
    },
  };
  transitions.set(owner, transition);
  return transition;
}

export function runTransition(owner, perform) {
  let transition = transitions.get(owner);
  if (!transition?.current || transition.started) transition = claimTransition(owner);
  transition.started = true;
  Promise.resolve(perform(transition)).then(
    () => transition.resolve(transition.current),
    transition.reject,
  );
  return transition.finished;
}

export function waitForTransition(owner, perform) {
  // Claim before Lit can coalesce requests. The watcher consumes this same owner;
  // if no watcher runs (a reversal to the baseline), execute the latest request.
  const transition = claimTransition(owner);
  owner.updateComplete
    .then(() => {
      if (!transition.current) transition.cancel();
      else if (!transition.started) perform();
    })
    .catch(transition.reject);
  return transition.finished;
}

export async function animateWithClass(el, className, transition) {
  if (!transition) {
    return runTransition(el, (current) => animateWithClass(el, className, current));
  }
  if (!transition.current) return false;
  el.classList.add(className);
  let cleaned = false;
  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    el.classList.remove(className);
  };
  transition.cleanups.add(cleanup);
  try {
    await new Promise(requestAnimationFrame);
    if (!transition.current) return false;
    const animations = el
      .getAnimations()
      .filter(
        (animation) =>
          animation instanceof CSSAnimation && animation.effect.target === el,
      );
    await Promise.allSettled(animations.map((animation) => animation.finished));
    return transition.current;
  } finally {
    cleanup();
    transition.cleanups.delete(cleanup);
  }
}
