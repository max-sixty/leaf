import "./theme.mjs";
import { registerIconLibrary } from "@awesome.me/webawesome/dist/components/icon/library.js";
import { icons } from "@awesome.me/webawesome/dist/components/icon/library.system.js";

// The upstream system library fetches data: URLs, which Leaf's self-only connect
// policy refuses. The supported sprite/mutator API lets us install the same SVG
// paths directly, including when a standalone export has no asset server.
registerIconLibrary("system", {
  spriteSheet: true,
  resolver: (name) => `#wa-system-${name}`,
  mutator(svg, icon) {
    const source =
      icons[icon.variant || "solid"][icon.name] ?? icons.regular[icon.name];
    const parsed = new DOMParser().parseFromString(
      source,
      "image/svg+xml",
    ).documentElement;
    svg.setAttribute("viewBox", parsed.getAttribute("viewBox"));
    svg.setAttribute("fill", "currentColor");
    svg.replaceChildren(
      ...Array.from(parsed.childNodes, (node) => document.importNode(node, true)),
    );
  },
});
