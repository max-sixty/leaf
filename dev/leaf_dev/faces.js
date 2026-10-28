/* Development-only census of the presses on screen, for `leaf-dev stills --faces`;
 * faces.py says what a face is and how two versions' faces compare.
 *
 * Evaluated in a tab once its state is driven and captured. `collect` finds the
 * presses and reads each at rest, `point` and `hovered` read one under the pointer
 * Python has moved onto it, and `finish` resolves every colour to sRGB and returns
 * the faces. It resolves colours through one probe element it adds only then, after
 * every reading, so the page's own observers never act on it before a reading.
 */
(() => {
  // What a reader presses to act: buttons in every spelling, a tab, a menu's row, a
  // disclosure, and a link laid out as a box rather than a run of prose.
  const PRESS = [
    "button",
    "input[type=button]",
    "input[type=submit]",
    "input[type=reset]",
    "[role=button]",
    "[role=tab]",
    "[role=menuitem]",
    "[role=menuitemcheckbox]",
    "[role=menuitemradio]",
    "summary",
    "a[href]",
  ].join(", ");
  const SIDES = ["Top", "Right", "Bottom", "Left"];
  const SIDE_NAMES = ["top", "right", "bottom", "left"];
  // How far two boxes' edges may part and still be one box: a part filling its host.
  const EDGE = 0.5;
  const SENTINEL = "rgb(1, 2, 3)";
  const PROBE = "--leaf-dev-faces-colour";

  // The flat tree, as the renderer draws it: a slotted node sits in its slot, and a
  // shadow root's children in its host.
  const flatParent = (node) =>
    node.assignedSlot ??
    node.parentElement ??
    (node.parentNode instanceof ShadowRoot ? node.parentNode.host : null);
  const flatChildNodes = (node) =>
    node.localName === "slot"
      ? node.assignedNodes({ flatten: true }).length
        ? node.assignedNodes({ flatten: true })
        : [...node.childNodes]
      : [...(node.shadowRoot ?? node).childNodes];
  const ancestors = (node) => {
    const found = [];
    for (let at = flatParent(node); at; at = flatParent(at)) found.push(at);
    return found;
  };
  const within = (node, ancestor) => {
    for (let at = node; at; at = flatParent(at)) if (at === ancestor) return true;
    return false;
  };
  const deepHit = (x, y) => {
    let hit = document.elementFromPoint(x, y);
    while (hit?.shadowRoot) {
      const inner = hit.shadowRoot.elementFromPoint(x, y);
      if (!inner || inner === hit) break;
      hit = inner;
    }
    return hit;
  };
  const sameBox = (a, b) =>
    Math.abs(a.left - b.left) <= EDGE &&
    Math.abs(a.top - b.top) <= EDGE &&
    Math.abs(a.right - b.right) <= EDGE &&
    Math.abs(a.bottom - b.bottom) <= EDGE;
  const contents = (el) => getComputedStyle(el).display === "contents";

  const shown = (text) => {
    if (!text.data.trim()) return false;
    const range = document.createRange();
    range.selectNodeContents(text);
    const box = range.getBoundingClientRect();
    return box.width > 1 && box.height > 1;
  };
  // Whether `root` draws words or a picture anywhere outside `press`.
  const drawsBeside = (root, press) =>
    flatChildNodes(root).some((node) =>
      node === press
        ? false
        : node.nodeType === Node.TEXT_NODE
          ? shown(node)
          : node instanceof Element &&
            node.checkVisibility() &&
            (node.matches("svg, img, canvas, video") || drawsBeside(node, press)),
    );

  // Everything that paints the press's face: the press, the ancestors whose box is its
  // own, a host whose shadow tree draws nothing but the press (a vendor control
  // drawing its face around the button inside it), and the descendants that fill the
  // press.
  const stackOf = (press) => {
    const own = press.getBoundingClientRect();
    let box = own;
    const outer = [];
    for (let at = flatParent(press); at && at !== document.body; at = flatParent(at)) {
      if (contents(at)) continue;
      const host =
        at.shadowRoot?.contains(press) &&
        at.shadowRoot.querySelectorAll(PRESS).length === 1 &&
        !drawsBeside(at, press);
      if (host) box = at.getBoundingClientRect();
      else if (!sameBox(at.getBoundingClientRect(), box)) break;
      outer.unshift(at);
    }
    const inner = [];
    const descend = (el) => {
      for (const child of flatChildNodes(el)) {
        if (!(child instanceof Element)) continue;
        if (contents(child)) descend(child);
        else if (sameBox(child.getBoundingClientRect(), own)) {
          inner.push(child);
          descend(child);
        }
      }
    };
    descend(press);
    return [...outer, press, ...inner];
  };

  const visibleText = (root) => {
    for (const node of flatChildNodes(root)) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (shown(node)) return node;
      } else if (node instanceof Element && node.checkVisibility()) {
        const found = visibleText(node);
        if (found) return found;
      }
    }
    return null;
  };
  const firstDrawn = (root, test) => {
    for (const node of flatChildNodes(root)) {
      if (!(node instanceof Element)) continue;
      if (node.getBoundingClientRect().width && test(node)) return node;
      const found = firstDrawn(node, test);
      if (found) return found;
    }
    return null;
  };

  const paint = (el) => {
    const style = getComputedStyle(el);
    return {
      fill: style.backgroundColor,
      image: style.backgroundImage !== "none",
      sides: SIDES.map((side) => [
        parseFloat(style[`border${side}Width`]),
        style[`border${side}Style`],
        style[`border${side}Color`],
      ]),
      radius: style.borderTopLeftRadius,
      shadow: style.boxShadow,
      pad: [parseFloat(style.paddingLeft), parseFloat(style.paddingRight)],
    };
  };

  // The press's look at this moment, with colours as the browser computes them.
  const reading = (press) => {
    // A transition the pointer started ends where it is going, so the reading needs
    // no wait; an ancestor's fade counts, since opacity reads up the tree.
    const moving = [
      ...press.stack.flatMap((el) => el.getAnimations({ subtree: true })),
      ...ancestors(press.stack[0]).flatMap((el) => el.getAnimations()),
    ];
    for (const animation of moving)
      if (animation instanceof CSSTransition) animation.finish();
    const box = press.stack[0].getBoundingClientRect();
    let ink = null;
    let font = null;
    let underline = false;
    const text = visibleText(press.stack[0]);
    if (text) {
      const style = getComputedStyle(text.parentElement);
      ink = style.color;
      underline = style.textDecorationLine.includes("underline");
      const family = style.fontFamily
        .split(",")[0]
        .trim()
        .replace(/^["']|["']$/g, "");
      font = [Math.round(parseFloat(style.fontSize)), Number(style.fontWeight), family];
    } else {
      // A symbol's ink: an icon's stroke, or else its fill; a picture; or the fill of
      // the first thing drawn inside the box, as a dot or a masked glyph paints.
      const symbol = firstDrawn(press.stack[0], (el) =>
        el.matches("svg, img, canvas, video"),
      );
      if (symbol?.localName === "svg") {
        const shape =
          symbol.querySelector(
            "path, circle, ellipse, line, polyline, polygon, rect, use, text",
          ) ?? symbol;
        const style = getComputedStyle(shape);
        ink = style.stroke !== "none" ? style.stroke : style.fill;
      } else if (symbol) ink = "picture";
      else {
        const drawn = firstDrawn(
          press.stack.at(-1),
          (el) =>
            !press.stack.includes(el) &&
            getComputedStyle(el).backgroundColor !== "rgba(0, 0, 0, 0)",
        );
        if (drawn) ink = getComputedStyle(drawn).backgroundColor;
      }
    }
    let opacity = 1;
    for (let at = press.stack.at(-1); at; at = flatParent(at))
      opacity *= Number(getComputedStyle(at).opacity);
    return {
      words: Boolean(text),
      size: [Math.round(box.width), Math.round(box.height)],
      stack: press.stack.map(paint),
      ink,
      font,
      underline,
      opacity,
    };
  };

  const label = (press) => {
    for (const el of press.stack) {
      const named = el.getAttribute("aria-label");
      if (named?.trim()) return named.trim();
    }
    const text = visibleText(press.stack[0]);
    if (text) return text.data.trim().replace(/\s+/g, " ");
    for (const el of press.stack) if (el.title?.trim()) return el.title.trim();
    return "";
  };
  const describe = (el) => {
    const classes = [...el.classList].filter((name) => !name.startsWith("lf-ui"));
    return [el.localName, ...classes.slice(0, 2)].join(".");
  };
  const STATE_ATTRIBUTES = [
    "aria-pressed",
    "aria-selected",
    "aria-checked",
    "aria-current",
  ];
  const flags = (press) => {
    const any = (test) => press.stack.some(test);
    return Object.entries({
      disabled: any((el) => el.matches(":disabled") || el.ariaDisabled === "true"),
      selected: any((el) =>
        STATE_ATTRIBUTES.some((name) => (el.getAttribute(name) ?? "false") !== "false"),
      ),
      expanded: any((el) => el.ariaExpanded === "true"),
      focused: any((el) => el.matches(":focus")),
      hovered: any((el) => el.matches(":hover")),
    })
      .filter(([, holds]) => holds)
      .map(([name]) => name);
  };

  const centre = (press) => {
    const box = press.stack[0].getBoundingClientRect();
    const x = box.left + box.width / 2;
    const y = box.top + box.height / 2;
    if (box.width < 1 || box.height < 1) return null;
    if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) return null;
    return within(deepHit(x, y), press.stack[0]) ? { x, y } : null;
  };

  let presses = [];
  // Where the state left the pointer, read as the centre of the innermost element it
  // hovers, which is where Playwright's hover puts it: a press that element reveals,
  // such as a heading's Copy link, hides again once the pointer visits another.
  let resting = null;

  const collect = () => {
    const under = [...document.querySelectorAll(":hover")].at(-1);
    const rest = under?.getBoundingClientRect();
    resting =
      rest?.width && under !== document.body && under !== document.documentElement
        ? { x: rest.left + rest.width / 2, y: rest.top + rest.height / 2 }
        : null;
    const found = [];
    const walk = (root) => {
      for (const el of root.querySelectorAll("*")) {
        if (el.matches(PRESS)) found.push(el);
        if (el.shadowRoot) walk(el.shadowRoot);
      }
    };
    walk(document);
    const claimed = new Set();
    presses = [];
    for (const el of found) {
      if (claimed.has(el)) continue;
      if (el.localName === "a" && getComputedStyle(el).display === "inline") continue;
      if (
        !el.checkVisibility({ visibilityProperty: true, contentVisibilityAuto: true })
      )
        continue;
      const press = { stack: stackOf(el) };
      const at = centre(press);
      if (!at) continue;
      press.at = [Math.round(at.x), Math.round(at.y)];
      for (const member of press.stack) claimed.add(member);
      press.label = label(press);
      // The element an author writes: a host whose part is the button, not the part.
      press.element = describe(
        press.stack.find(
          (member) => member.matches(PRESS) || member.localName.includes("-"),
        ),
      );
      press.flags = flags(press);
      press.rest = reading(press);
      press.hover = null;
      presses.push(press);
    }
    return presses.length;
  };

  // A press's centre if the pointer would land on it now: an earlier hover may have
  // opened something over it, or taken the pointer from what revealed it.
  const point = (index) => centre(presses[index]);
  const hovered = (index) => {
    const press = presses[index];
    if (press.stack.some((el) => el.matches(":hover"))) press.hover = reading(press);
  };

  const finish = () => {
    try {
      CSS.registerProperty({
        name: PROBE,
        syntax: "<color>",
        inherits: false,
        initialValue: SENTINEL,
      });
    } catch {
      // Registered by an earlier census in this document.
    }
    const probe = document.createElement("span");
    document.documentElement.append(probe);
    const resolved = new Map();
    const resolve = (colour) => {
      if (!resolved.has(colour)) {
        probe.style.setProperty(PROBE, `color(from ${colour} srgb r g b / alpha)`);
        const value = getComputedStyle(probe).getPropertyValue(PROBE);
        const parts = value.match(
          /^color\(srgb ([-\d.e]+) ([-\d.e]+) ([-\d.e]+)(?: \/ ([-\d.e]+))?\)$/,
        );
        resolved.set(
          colour,
          parts
            ? [
                ...parts.slice(1, 4).map(Number),
                parts[4] === undefined ? 1 : Number(parts[4]),
              ]
            : null,
        );
      }
      return resolved.get(colour);
    };
    const hex = (channel) =>
      Math.round(Math.min(1, Math.max(0, channel)) * 255)
        .toString(16)
        .padStart(2, "0");
    const named = ([r, g, b, a]) => {
      if (a < 0.005) return null;
      const colour = `#${hex(r)}${hex(g)}${hex(b)}`;
      return a > 0.995 ? colour : `${colour} ${Math.round(a * 100)}%`;
    };
    const canonical = (colour) => {
      const rgba = resolve(colour);
      return rgba ? named(rgba) : colour;
    };
    const COLOUR = /(?:rgba?|hsla?|hwb|color|oklab|oklch|lab|lch)\([^()]*\)/g;

    const face = (raw) => {
      const fills = raw.stack.map((member) => resolve(member.fill) ?? [0, 0, 0, 0]);
      // Each member's fill over the ones beneath it, as the renderer composites them.
      let under = [0, 0, 0, 0];
      for (const [r, g, b, a] of fills) {
        if (!a) continue;
        const alpha = a + under[3] * (1 - a);
        const mix = (top, bottom) => (top * a + bottom * under[3] * (1 - a)) / alpha;
        under = [mix(r, under[0]), mix(g, under[1]), mix(b, under[2]), alpha];
      }
      const sides = SIDES.map((_, side) => {
        for (const member of [...raw.stack].reverse()) {
          const [width, style, colour] = member.sides[side];
          const drawn = canonical(colour);
          if (width > 0 && style !== "none" && style !== "hidden" && drawn)
            return `${Math.round(width)}px ${style} ${drawn}`;
        }
        return null;
      });
      const painters = raw.stack.filter(
        (member, index) =>
          fills[index][3] > 0.005 ||
          member.image ||
          member.shadow !== "none" ||
          member.sides.some(
            ([width, style, colour]) =>
              width > 0 && style !== "none" && canonical(colour),
          ),
      );
      let radius = null;
      if (painters.length) {
        const [w, h] = raw.size;
        const given = painters[0].radius.split(" ")[0];
        const px = given.endsWith("%")
          ? (parseFloat(given) / 100) * Math.min(w, h)
          : parseFloat(given);
        radius = px >= Math.min(w, h) / 2 - EDGE ? "round" : Math.round(px);
      }
      const shadows = painters
        .map((member) => member.shadow)
        .filter((shadow) => shadow !== "none")
        .map((shadow) =>
          shadow.replace(COLOUR, (colour) => canonical(colour) ?? "transparent"),
        );
      const [w, h] = raw.size;
      const pad = raw.stack.reduce(
        (sum, member) => [sum[0] + member.pad[0], sum[1] + member.pad[1]],
        [0, 0],
      );
      return {
        size: raw.words
          ? { height: h, sides: pad.map(Math.round) }
          : { width: w, height: h },
        fill: named(under),
        image: raw.stack.some((member) => member.image),
        border: sides.every((side) => side === sides[0])
          ? sides[0]
          : Object.fromEntries(
              sides.flatMap((side, index) => (side ? [[SIDE_NAMES[index], side]] : [])),
            ),
        radius,
        shadow: shadows.join(", ") || null,
        ink: raw.ink && canonical(raw.ink),
        font: raw.font,
        underline: raw.underline,
        opacity: Math.round(raw.opacity * 20) / 20,
      };
    };

    const faces = presses.map((press) => ({
      label: press.label,
      element: press.element,
      at: press.at,
      flags: press.flags,
      words: press.rest.words,
      rest: face(press.rest),
      hover: press.hover && face(press.hover),
    }));
    // The root's custom properties that hold a colour, by the colour, so a report can
    // name a face's colours as the theme does.
    const tokens = {};
    for (const name of getComputedStyle(document.documentElement)) {
      if (!name.startsWith("--") || name === PROBE) continue;
      const rgba = resolve(`var(${name})`);
      const colour = rgba && named(rgba);
      if (colour) (tokens[colour] ??= []).push(name);
    }
    probe.remove();
    return { presses: faces, tokens };
  };

  globalThis.leafDevFaces = { collect, point, hovered, finish, resting: () => resting };
})();
