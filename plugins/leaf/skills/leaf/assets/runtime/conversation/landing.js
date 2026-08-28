import { shownBox } from "../geometry.js";
import { focused } from "../keyboard/scopes.js";
import { SCROLL } from "../motion.js";
import { closestAcross } from "../passages.js";

const SAYS_IN = ".lf-thread, .lf-conversation-thread, .lf-conversation";
export const SAY_BOX = ":scope > .lf-compose textarea, :scope > .lf-say textarea";
const conversationReturns = new WeakMap();

const conversationInputOf = (held) => {
  const box = held?.querySelector(SAY_BOX);
  return box && shownBox(box).height ? box : null;
};

export function conversationInput(node) {
  const held = node && closestAcross(node, SAYS_IN);
  return conversationInputOf(held);
}

export const heldConversation = () => focused() && closestAcross(focused(), SAYS_IN);
export const standingConversation = () => {
  const held = heldConversation();
  const box = conversationInputOf(held);
  return box ? { held, box } : null;
};
export const backFromConversation = (box) => conversationReturns.get(box) ?? null;

let publishedLand;
export const landIn = (...args) => publishedLand(...args);
export function landInConversation(box, route = null) {
  return publishedLand({ box, route });
}

export function createConversationLanding({ scrollToThread }) {
  const focusConversation = ({ held, box }) => {
    box.focus({ preventScroll: true });
    held.scrollIntoView({ behavior: SCROLL, block: "nearest" });
    if (held.dataset.id) scrollToThread(held.dataset.id);
  };
  publishedLand = ({ held = null, box, route = null }) => {
    if (
      route &&
      (!(route.target instanceof Element) ||
        typeof route.line !== "string" ||
        !route.line.trim())
    )
      throw new TypeError(
        "landInConversation return route needs an element target and a non-empty line",
      );
    held ??= box && closestAcross(box, SAYS_IN);
    if (!held) return false;
    if (route && !held.hasAttribute("tabindex")) {
      conversationReturns.set(box, route);
      box.addEventListener("blur", () => conversationReturns.delete(box), {
        once: true,
      });
    }
    focusConversation({ held, box });
    return true;
  };
  return publishedLand;
}
