/* Development-only census of the presses on screen, for `leaf-dev stills --faces`;
 * faces.py says what a face is and how two versions' faces compare.
 *
 * Evaluated in a tab once its state is driven and captured. `collect` finds the
 * presses the state shows, `rest` reads them with the pointer where Python has put
 * it, `point` and `hovered` read one under the pointer Python has moved onto it, and
 * `finish` resolves every colour to sRGB and returns the faces with the root's colour
 * tokens. Colours resolve through one probe element added only then, after every
 * reading, so the page's own observers never act on it first.
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
  // A button written as an input shows its value, not a text node, and a submit or
  // reset with none shows the browser's own word for it.
  const INPUT_PRESS = "input[type=button], input[type=submit], input[type=reset]";
  const inputWords = (el) =>
    el.matches(INPUT_PRESS)
      ? el.value.trim() || { submit: "Submit", reset: "Reset" }[el.type] || null
      : null;
  const SIDES = ["Top", "Right", "Bottom", "Left"];
  const SIDE_NAMES = ["top", "right", "bottom", "left"];
  const CORNERS = ["TopLeft", "TopRight", "BottomRight", "BottomLeft"];
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

  const layer = (style) => ({
    fill: style.backgroundColor,
    image: style.backgroundImage !== "none",
    sides: SIDES.map((side) => [
      parseFloat(style[`border${side}Width`]),
      style[`border${side}Style`],
      style[`border${side}Color`],
    ]),
    radius: CORNERS.map((corner) => style[`border${corner}Radius`]),
    shadow: style.boxShadow,
  });
  // An element's paint, and its `::before` where that is drawn: a press that keeps a
  // larger hit box draws its face there (response.css, Send and Resolve).
  const paint = (el) => {
    const style = getComputedStyle(el);
    const before = getComputedStyle(el, "::before");
    const drawn =
      !["none", "normal"].includes(before.content) && before.display !== "none";
    return {
      ...layer(style),
      pad: [parseFloat(style.paddingLeft), parseFloat(style.paddingRight)],
      before: drawn
        ? {
            ...layer(before),
            size: [parseFloat(before.width), parseFloat(before.height)],
          }
        : null,
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
    // The box of what the press shows, its words or its symbol, which a face frames.
    let inked = null;
    const field = press.stack.find(inputWords);
    const text = field ? null : visibleText(press.stack[0]);
    const worded = field ?? text?.parentElement;
    if (worded) {
      const range = document.createRange();
      if (text) range.selectNodeContents(text);
      inked = (field ?? range).getBoundingClientRect();
      const style = getComputedStyle(worded);
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
      inked = symbol?.getBoundingClientRect() ?? null;
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
      words: Boolean(worded),
      size: [Math.round(box.width), Math.round(box.height)],
      inked: inked && [inked.width, inked.height],
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
    const field = press.stack.find(inputWords);
    if (field) return inputWords(field);
    const text = visibleText(press.stack[0]);
    if (text) return text.data.trim().replace(/\s+/g, " ");
    for (const el of press.stack) if (el.title?.trim()) return el.title.trim();
    return "";
  };
  // What names a press apart from its label in both versions of a page: an id or a
  // key the page or the runtime gives it, or the nearest ancestor's (`scope`).
  const keyOf = (el) =>
    el.id ? `#${el.id}` : el.dataset?.key ? `[data-key="${el.dataset.key}"]` : null;
  const scopeOf = (el) => {
    for (let at = flatParent(el); at; at = flatParent(at))
      if (keyOf(at)) return keyOf(at);
    return null;
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
      press.key = press.stack.map(keyOf).find(Boolean) ?? null;
      press.scope = scopeOf(press.stack[0]);
      press.rest = null;
      press.hover = null;
      presses.push(press);
    }
    return presses.length;
  };

  // Read each press not yet read that shows now: at rest, with the pointer off the
  // page, or, `revealed`, with the pointer back where the state left it, for a press
  // something it hovers reveals. A press neither shows is left out.
  const rest = (revealed) => {
    for (const press of presses) {
      if (press.rest || !centre(press)) continue;
      press.flags = [...flags(press), ...(revealed ? ["revealed by hover"] : [])];
      press.rest = reading(press);
    }
  };

  // A read press's centre if the pointer would land on it now: an earlier hover may
  // have opened something over it, or taken the pointer from what revealed it.
  const point = (index) => (presses[index].rest ? centre(presses[index]) : null);
  const hovered = (index) => {
    const press = presses[index];
    if (press.stack.some((el) => el.matches(":hover"))) press.hover = reading(press);
  };

  // sRGB for any CSS colour, read through one probe element, which `close` removes.
  const colours = () => {
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
    return { resolve, close: () => probe.remove() };
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
  // The root's custom properties that hold a colour, by the colour, in the scheme the
  // page renders now.
  const tokensOf = (resolve) => {
    const tokens = {};
    for (const name of getComputedStyle(document.documentElement)) {
      if (!name.startsWith("--") || name === PROBE) continue;
      const rgba = resolve(`var(${name})`);
      const colour = rgba && named(rgba);
      if (colour) (tokens[colour] ??= []).push(name);
    }
    return tokens;
  };
  const finish = () => {
    const { resolve, close } = colours();
    const canonical = (colour) => {
      const rgba = resolve(colour);
      return rgba ? named(rgba) : colour;
    };
    const COLOUR = /(?:rgba?|hsla?|hwb|color|oklab|oklch|lab|lch)\([^()]*\)/g;

    const border = ([width, style, colour]) =>
      width > 0 && style !== "none" && style !== "hidden" && canonical(colour)
        ? `${Math.round(width)}px ${style} ${canonical(colour)}`
        : null;
    const paints = (coat) =>
      (resolve(coat.fill)?.[3] ?? 0) > 0.005 ||
      coat.image ||
      coat.shadow !== "none" ||
      coat.sides.some(border);
    // The stack member whose `::before` is the face: the first whose `::before`
    // frames what the press shows and paints at rest or under the pointer, so a face
    // drawn only under the pointer, as Resolve's is, keeps its box at rest too. One
    // smaller than the words or symbol, such as a row's dot, decorates the face.
    const frames = (before, inked) =>
      before &&
      paints(before) &&
      (!inked || before.size.every((side, axis) => side >= inked[axis] - EDGE));
    const faceOn = (press) =>
      press.rest.stack.findIndex(
        (member, index) =>
          frames(member.before, press.rest.inked) ||
          frames(press.hover?.stack[index].before, press.rest.inked),
      );

    const face = (raw, on) => {
      // A `::before` paints over its element, so it is the top layer.
      const before = on >= 0 ? raw.stack[on].before : null;
      const layers = before ? [...raw.stack, before] : raw.stack;
      // Each layer's fill over the ones beneath it, as the renderer composites them.
      let under = [0, 0, 0, 0];
      for (const fill of layers.map((member) => resolve(member.fill))) {
        const [r, g, b, a] = fill ?? [0, 0, 0, 0];
        if (!a) continue;
        const alpha = a + under[3] * (1 - a);
        const mix = (top, bottom) => (top * a + bottom * under[3] * (1 - a)) / alpha;
        under = [mix(r, under[0]), mix(g, under[1]), mix(b, under[2]), alpha];
      }
      const sides = SIDES.map(
        (_, side) =>
          [...layers]
            .reverse()
            .map((member) => border(member.sides[side]))
            .find(Boolean) ?? null,
      );
      const painters = layers.filter(paints);
      const [w, h] =
        before && before.size.every(Number.isFinite)
          ? before.size.map(Math.round)
          : raw.size;
      // The corners of the layer that draws the face: its `::before` where that is
      // the face, else the outermost layer that paints; one value where all agree.
      let radius = null;
      if (painters.length) {
        const corners = (before ?? painters[0]).radius.map((given) => {
          const first = given.split(" ")[0];
          const px = first.endsWith("%")
            ? (parseFloat(first) / 100) * Math.min(w, h)
            : parseFloat(first);
          return px >= Math.min(w, h) / 2 - EDGE ? "round" : Math.round(px);
        });
        radius = corners.every((corner) => corner === corners[0])
          ? corners[0]
          : corners.join(" ");
      }
      const shadows = painters
        .map((member) => member.shadow)
        .filter((shadow) => shadow !== "none")
        .map((shadow) =>
          shadow.replace(COLOUR, (colour) => canonical(colour) ?? "transparent"),
        );
      const pad = raw.stack.reduce(
        (sum, member) => [sum[0] + member.pad[0], sum[1] + member.pad[1]],
        [0, 0],
      );
      return {
        size: raw.words
          ? { height: h, sides: pad.map(Math.round) }
          : { width: w, height: h },
        fill: named(under),
        image: layers.some((member) => member.image),
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

    const faces = presses
      .filter((press) => press.rest)
      .map((press) => {
        const on = faceOn(press);
        return {
          label: press.label,
          element: press.element,
          at: press.at,
          key: press.key,
          scope: press.scope,
          flags: press.flags,
          words: press.rest.words,
          rest: face(press.rest, on),
          hover: press.hover && face(press.hover, on),
        };
      });
    const found = { presses: faces, tokens: tokensOf(resolve) };
    close();
    return found;
  };

  globalThis.leafDevFaces = {
    collect,
    rest,
    point,
    hovered,
    finish,
    resting: () => resting,
  };
})();
