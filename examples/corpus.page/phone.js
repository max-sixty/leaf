// A narrow composition of the existing film, not a second merge simulation.
// History runs down two lanes; the refs move with their commits. Worktrees and hooks
// stay below that history, and a disclosure holds the complete, seekable terminal.
// Coordinates come from the interpolated world, so a resize preserves playback.
import { keeps, keepsText, offer, setChildren } from "/runtime/widget-api.js";

const SVG = "http://www.w3.org/2000/svg";
const color = (role) =>
  `var(${{ main: "--accent", feat: "--warn-ink", squash: "--mark-ink", ghost: "--border-2", ok: "--ok-ink", bad: "--danger-ink", warn: "--warn-ink", muted: "--muted" }[role] ?? "--ink"})`;
const el = (tag, attrs, parent) => {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  parent.append(node);
  return node;
};

export class PhonePainter {
  constructor(stage) {
    this.root = document.createElement("div");
    this.root.className = "film-phone";
    this.svg = document.createElementNS(SVG, "svg");
    this.svg.setAttribute("role", "img");
    this.svg.setAttribute(
      "aria-label",
      "Commit history, older to newer, in main and feature lanes",
    );
    this.svg.setAttribute("font-family", "var(--mono)");
    this.svg.setAttribute("font-size", "14");
    this.root.append(this.svg);
    this.edges = el("g", { fill: "none", "stroke-width": 2 }, this.svg);
    this.nodes = el("g", {}, this.svg);
    this.refs = el("g", {}, this.svg);
    this.mainLabel = el(
      "text",
      { x: 20, y: 24, fill: color("main"), "font-size": 16 },
      this.svg,
    );
    this.featureLabel = el(
      "text",
      { y: 24, fill: color("feat"), "font-size": 16 },
      this.svg,
    );
    this.fork = el(
      "text",
      { "font-family": "var(--sans)", "font-size": 12, fill: color("muted") },
      this.svg,
    );
    this.context = document.createElement("div");
    this.context.className = "film-phone-context";
    this.terminal = document.createElement("details");
    this.terminal.className = "film-phone-terminal";
    const summary = document.createElement("summary");
    summary.textContent = "Terminal output";
    this.latest = document.createElement("p");
    this.latest.className = "film-phone-latest";
    this.log = document.createElement("div");
    this.terminal.append(summary, this.log);
    this.root.append(this.context, this.latest, this.terminal);
    stage.append(this.root);
    this.pool = new Map();
    this.lines = new Map();
    this.visible = [];
  }

  parts() {
    return this.visible;
  }

  terminalLine(at) {
    const button = this.lines.get(at);
    if (button?.isConnected && !this.terminal.open) this.terminal.open = true;
    return button;
  }

  keyed(id, make) {
    if (!this.pool.has(id)) this.pool.set(id, make());
    this.seen.add(id);
    return this.pool.get(id);
  }

  part(id, element, label, info, opacity) {
    keeps(element, "data-label", label);
    keeps(element, "data-info", info);
    if (opacity >= 0.3 && !id.includes("~"))
      this.visible.push({ id, element, label, info });
  }

  paint(film, fr, width) {
    this.visible = [];
    this.seen = new Set();
    const { world } = fr;
    // One shared transform for commits, edges and refs. Keep the height steady within
    // a run, including the longer unsquashed history, so playback never scrolls it.
    const lane = width / 2;
    const point = (n) => ({
      x: 20 + ((n.y - 170) / 130) * lane,
      y: 62 + ((n.x - 70) / 104) * 48,
    });
    if (this.film !== film) {
      this.film = film;
      this.maxX = Math.max(
        ...film.scenes.flatMap((s) => Object.values(s.to.nodes).map((n) => n.x)),
      );
    }
    const height = point({ x: this.maxX, y: 170 }).y + 54;
    keeps(this.svg, "viewBox", `0 0 ${width} ${height}`);
    keepsText(this.mainLabel, film.scenario.target);
    keepsText(this.featureLabel, film.scenario.branch);
    keeps(this.featureLabel, "x", 20 + lane);
    const fork = world.nodes.m2;
    keeps(this.fork, "x", width / 2 - 24);
    keeps(this.fork, "y", fork ? point(fork).y - 8 : 0);
    keepsText(this.fork, fork ? "fork" : "");

    for (const [id, edge] of Object.entries(world.edges)) {
      const a = world.nodes[edge.a],
        b = world.nodes[edge.b];
      if (!a || !b) continue;
      const from = point(a),
        to = point(b),
        mid = (from.y + to.y) / 2;
      const path = this.keyed(`edge:${id}`, () => el("path", {}, this.edges));
      keeps(
        path,
        "d",
        `M${from.x},${from.y} C${from.x},${mid} ${to.x},${mid} ${to.x},${to.y}`,
      );
      keeps(path, "stroke", color(edge.tone));
      keeps(path, "opacity", Math.min(edge.o, a.o, b.o));
      keeps(path, "stroke-dasharray", edge.dash > 0.5 ? "4 4" : "none");
    }
    for (const [id, n] of Object.entries(world.nodes)) {
      const p = point(n);
      const g = this.keyed(`commit:${id}`, () => {
        const g = el("g", {}, this.nodes);
        // The hit area stays finger sized without changing the commit symbol.
        el("rect", { x: -18, y: -22, width: 110, height: 44, fill: "transparent" }, g);
        el("circle", { r: 8 }, g);
        el("text", { x: 17, y: 5, fill: "var(--ink)" }, g);
        return g;
      });
      keeps(g, "transform", `translate(${p.x} ${p.y})`);
      keeps(g, "opacity", n.o);
      keeps(g.children[1], "fill", n.wip > 0.5 ? "var(--card)" : color(n.tone));
      keeps(g.children[1], "stroke", color(n.tone));
      keeps(g.children[1], "stroke-width", n.merge ? 3 : 2);
      keeps(g.children[1], "stroke-dasharray", n.wip > 0.5 ? "3 3" : "none");
      keepsText(g.children[2], n.hash);
      this.part(`commit:${id}`, g, `commit ${n.hash}`, n.info, n.o);
    }
    const refRows = new Map();
    const badges = [];
    const hashes = Object.values(world.nodes)
      .filter((n) => n.o >= 0.3)
      .map((n) => {
        const p = point(n);
        return { x: p.x + 17, y: p.y - 11, w: n.hash.length * 8.5, h: 18 };
      });
    for (const [id, r] of Object.entries(world.refs)) {
      const p = point(r);
      const g = this.keyed(`ref:${id}`, () => {
        const g = el("g", {}, this.refs);
        el("rect", { height: 20, rx: 3, fill: "var(--card)" }, g);
        el("text", { y: 15 }, g);
        return g;
      });
      const label = id === "backup" ? "backup" : r.label;
      const anchor = `${Math.round(p.x)}:${Math.round(p.y)}`;
      const row = refRows.get(anchor) ?? 0;
      if (r.o >= 0.3) refRows.set(anchor, row + 1);
      const x = p.x + 17,
        w = label.length * 8.5 + 10;
      let y = p.y + 10 + row * 22;
      // A moving ref can pass the next commit during a merge. Place its label in
      // the next clear gap, against the same coordinates that draw the hashes.
      for (const box of [...hashes, ...badges].sort((a, b) => a.y - b.y)) {
        if (
          x < box.x + box.w &&
          x + w > box.x &&
          y < box.y + box.h + 3 &&
          y + 20 > box.y - 3
        )
          y = box.y + box.h + 3;
      }
      if (r.o >= 0.3) badges.push({ x, y, w, h: 20 });
      keeps(g, "transform", `translate(${x} ${y})`);
      keeps(g, "opacity", r.o);
      keeps(g.children[0], "width", w);
      keeps(g.children[0], "stroke", color(r.tone));
      keeps(g.children[1], "x", 5);
      keeps(g.children[1], "fill", "var(--ink)");
      keepsText(g.children[1], label);
      this.part(`ref:${id}`, g, `ref ${r.label}`, r.info, r.o);
    }
    const context = [];
    for (const [id, c] of Object.entries(world.chips)) {
      if (c.o < 0.02) continue;
      const row = this.keyed(`hook:${id}`, () => {
        const row = document.createElement("p");
        row.className = "film-phone-hook";
        return row;
      });
      keepsText(row, c.label);
      keeps(row, "data-tone", c.state);
      keeps(row, "style", `opacity: ${c.o}`);
      this.part(`hook:${id}`, row, c.label, c.info, c.o);
      context.push(row);
    }
    for (const [id, tr] of Object.entries(world.trees)) {
      if (tr.o < 0.02 && !tr.gone) continue;
      const removed = !!tr.gone && tr.o < 0.1;
      const row = this.keyed(`tree:${id}`, () => {
        const row = document.createElement("div");
        row.className = "film-phone-tree";
        row.append(document.createElement("code"), document.createElement("span"));
        return row;
      });
      // The vacated worktree keeps its row, so cleanup is visible without a jump.
      keepsText(row.children[0], tr.path);
      keepsText(
        row.children[1],
        removed
          ? "Removed"
          : `[${tr.branch}] · ${tr.note || (tr.dirty > 0.5 ? `${Math.round(tr.dirty)} uncommitted files` : "clean")}${tr.here > 0.5 ? " · you are here" : ""}`,
      );
      keeps(row, "data-here", tr.here > 0.5);
      keeps(row, "data-gone", removed);
      this.part(`tree:${id}`, row, `worktree ${tr.path}`, tr.info, 1);
      context.push(row);
    }
    setChildren(this.context, context);
    for (const [id, node] of this.pool)
      if (!this.seen.has(id)) {
        node.remove();
        this.pool.delete(id);
      }
    const lines = fr.lines.map((line) => {
      if (!this.lines.has(line.at))
        this.lines.set(line.at, offer("button", "film-phone-line"));
      const button = this.lines.get(line.at);
      keeps(button, "data-line", line.at);
      keeps(button, "data-at", line.seekAt);
      keepsText(button, `${line.kind === "cmd" ? "$ " : ""}${line.text}`);
      return button;
    });
    setChildren(this.log, lines);
    const last = fr.lines.at(-1);
    keepsText(
      this.latest,
      last ? `${last.kind === "cmd" ? "$ " : ""}${last.text}` : "",
    );
  }
}
