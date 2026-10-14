import {
  shownParts
} from "./bundle-page-paint.js";
import {
  drawn
} from "./bundle-sample-visibility.js";

// runtime/visible-target-parts.js
function visibleTargetParts(target) {
  const parts = shownParts(target).filter(drawn);
  return drawn(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}

export {
  visibleTargetParts
};
