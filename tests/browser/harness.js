/* Shared corpus readings. Each callback runs in the document Playwright targets;
 * no page globals are installed except the explicit at-rest instrumentation.
 * Python owns the completion edges and assertions; these functions own DOM reads.
 */
(() => {
  const scrollStill = ([selector, axis, frames]) => {
    const box = selector ? document.querySelector(selector) : document.scrollingElement;
    if (!box) return false;
    const at = axis === "x" ? box.scrollLeft : box.scrollTop;
    const held = globalThis.__lfScrollStill;
    globalThis.__lfScrollStill =
      held && held.at === at ? { at, frames: held.frames + 1 } : { at, frames: 0 };
    return globalThis.__lfScrollStill.frames >= frames;
  };

  // Accessibility reports content and control state, but not native focus
  // affordances or every field's source/caret (including a closed-root editor).
  const browserState = () => {
    const stops = [];
    const fields = [];
    const walk = (root) => {
      for (const node of root.querySelectorAll("*")) {
        if (node.closest("[inert]")) continue;
        const field =
          typeof node.selectionStart === "number" && typeof node.value === "string";
        const stop =
          !node.matches(":disabled") &&
          (node.tabIndex >= 0 ||
            node.hasAttribute("tabindex") ||
            (node.isContentEditable && node.hasAttribute("contenteditable")));
        if ((field || stop) && node.checkVisibility({ visibilityProperty: true })) {
          const rect = node.getBoundingClientRect();
          const box = [rect.x, rect.y, rect.width, rect.height].map(Math.round);
          if (field)
            fields.push([
              node.value,
              node.selectionStart,
              node.selectionEnd,
              node.selectionDirection,
              ...box,
            ]);
          if (stop) stops.push([node.tabIndex, ...box]);
        }
        if (node.shadowRoot) walk(node.shadowRoot);
      }
    };
    walk(document);
    return { stops, fields };
  };

  const armRest = () => {
    window.lfWrites = [];
    window.lfWriteStep = null;
    const rest = (window.lfRest = { frames: {}, focus: 0 });
    const request = window.requestAnimationFrame;
    window.requestAnimationFrame = (callback) => {
      // The first caller past the runtime's scheduler, which is whose loop it is.
      const site =
        new Error().stack
          .split("\n")
          .slice(2)
          .find((line) => !line.includes("/runtime/rendering.js"))
          ?.trim() ?? "";
      return request.call(window, (time) => {
        rest.frames[site] = (rest.frames[site] ?? 0) + 1;
        callback(time);
      });
    };
    document.addEventListener("focusin", () => rest.focus++, { capture: true });
  };

  const readRest = () => {
    const writes = window.lfWrites;
    window.lfWrites = null;
    const endless = document
      .getAnimations()
      .filter(
        (animation) =>
          animation.playState === "running" &&
          animation.effect?.getComputedTiming().iterations === Infinity,
      )
      .map(
        (animation) =>
          `${animation.animationName ?? animation.id} on ` +
          `${animation.effect.target.localName}.${[...animation.effect.target.classList].join(".")}`,
      );
    return { writes, ...window.lfRest, endless };
  };
  return { browserState, armRest, readRest, scrollStill };
})();
