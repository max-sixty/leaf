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

  const pageState = () => {
    const said = (node) => (a) =>
      a.name === "style"
        ? `style=${JSON.stringify(
            [...node.style]
              .map(
                (property) =>
                  `${property}: ${node.style.getPropertyValue(property)}` +
                  (node.style.getPropertyPriority(property) ? " !important" : ""),
              )
              .sort()
              .join("; "),
          )}`
        : `${a.name}=${JSON.stringify(a.value)}`;
    const lines = [
      [...document.documentElement.attributes]
        .filter((a) => a.name !== "data-lf-traffic")
        .map(said(document.documentElement))
        .sort()
        .join(" "),
    ];
    const walk = (parent, path) => {
      for (const node of parent.childNodes) {
        if (node.nodeType === Node.TEXT_NODE && node.data.trim())
          lines.push(`${path} ${JSON.stringify(node.data.trim())}`);
        if (node.nodeType !== Node.ELEMENT_NODE) continue;
        const here = `${path} > ${node.localName}${node.id ? "#" + node.id : ""}`;
        lines.push(`${here} ${[...node.attributes].map(said(node)).sort().join(" ")}`);
        if (node.shadowRoot) walk(node.shadowRoot, `${here} ::shadow`);
        walk(node, here);
      }
    };
    walk(document.body, "body");
    return lines;
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
  return { pageState, armRest, readRest, scrollStill };
})();
