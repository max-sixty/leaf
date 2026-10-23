import {
  PAGE_INTERFACE,
  keeps,
  frameFor,
  sizeObserver,
  whileConnected,
} from "/runtime/widget-api.js";

// Illustrative source timings and alternatives, not recordings. The optional
// motion package owns playback; these drawings are pure functions of its clock.
const clamp = (value) => Math.max(0, Math.min(1, value));
function curve(time, x1, y1, x2, y2) {
  const cubic = (p, a, b) =>
    3 * (1 - p) ** 2 * p * a + 3 * (1 - p) * p ** 2 * b + p ** 3;
  let low = 0;
  let high = 1;
  for (let iteration = 0; iteration < 16; iteration += 1) {
    const midpoint = (low + high) / 2;
    if (cubic(midpoint, x1, x2) < time) low = midpoint;
    else high = midpoint;
  }
  return cubic((low + high) / 2, y1, y2);
}

function fold(nodes, alternative, time, width) {
  const progress =
    time <= 0 ? 0 : time >= 300 ? 1 : curve(time / 300, 0.23, 1, 0.32, 1);
  keeps(nodes.outline, "x", 10 + (width - 62) * progress);
  keeps(nodes.outline, "width", width - 20 - (width - 62) * progress);
  keeps(nodes.outline, "height", 44 - 2 * progress);
  keeps(nodes.words, "opacity", time < 0 ? 1 : 0);
  const leafX = time < 0 ? 22 : alternative ? 22 + (width - 63) * progress : width - 41;
  keeps(nodes.leaf, "transform", `translate(${leafX} 43) scale(.625)`);
  keeps(
    nodes.badge,
    "transform",
    `translate(${(alternative ? leafX + 41 : width) - 560} 0)`,
  );
  const opacity = time < 0 || alternative ? 1 : clamp((time - 140) / 160);
  keeps(nodes.leaf, "opacity", opacity);
  keeps(nodes.badge, "opacity", time < 0 ? 0 : opacity);
}

function arrival(nodes, alternative, time) {
  const progress = clamp(time / 520);
  const active = time >= 0 && time < 520;
  if (alternative) {
    keeps(nodes.ring, "stroke-width", 0);
    keeps(
      nodes.pin,
      "fill",
      active
        ? `color-mix(in srgb, var(--accent) ${18 * (1 - progress)}%, var(--paper))`
        : "var(--paper)",
    );
    return;
  }
  const split = 0.58;
  const eased = curve(
    progress < split ? progress / split : (progress - split) / (1 - split),
    0,
    0,
    0.58,
    1,
  );
  const spread = progress < split ? 7 * eased : 7 + 3 * eased;
  const alpha = progress < split ? 0.42 + (0.16 - 0.42) * eased : 0.16 * (1 - eased);
  keeps(nodes.ring, "r", 16 + spread / 2);
  keeps(nodes.ring, "stroke-width", active ? spread : 0);
  keeps(nodes.ring, "opacity", alpha);
}

const mounted = new WeakSet();
await customElements.whenDefined("lf-motion");
function mount() {
  for (const [id, draw] of [
    ["fold-motion", fold],
    ["arrival-motion", arrival],
  ]) {
    const host = document.getElementById(id);
    if (!host || mounted.has(host)) continue;
    mounted.add(host);
    const scenes = [...host.querySelectorAll("figure")].map((figure) =>
      Object.fromEntries(
        [...figure.querySelectorAll("[data-part]")].map((node) => [
          node.dataset.part,
          node,
        ]),
      ),
    );
    const drawings = [...host.querySelectorAll("figure svg")];
    let width = 560;
    host.renderFrame = (time) => {
      scenes.forEach((nodes, index) => draw(nodes, index === 1, time - 250, width));
    };
    const fit = frameFor(host, () => {
      const measured = drawings[0].clientWidth;
      if (!measured) return;
      width = measured;
      drawings.forEach((svg) => keeps(svg, "viewBox", `0 0 ${width} 110`));
      host.renderFrame(host.currentTime);
    });
    whileConnected(host, () => {
      const sizes = sizeObserver(fit);
      sizes.observe(host);
      fit();
      return () => sizes.disconnect();
    });
  }
}
mount();
document.addEventListener(PAGE_INTERFACE, mount);
