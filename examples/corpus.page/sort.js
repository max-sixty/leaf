// The sort film's engine: a faithful JavaScript port of the merge sort that shipped in
// Rust 1.15 (rust-lang/rust#38192, src/libcollections/slice.rs), instrumented so every
// comparison and every element move becomes a step. trace() runs the port once and
// records each step's whole state; frame(film, t) finds the step at time t and eases
// every element from where the previous step left it. The painter draws a frame, so
// playing, scrubbing and stepping are all just a new t.
//
// The port keeps the Rust code's shape: the same backwards scan for natural runs, the
// same insert_head with a lifted tmp and a travelling hole, the same collapse() on the
// top four runs, and the same merge that copies the shorter run into buf. Each step names
// the source line it executes (`line`), which the page highlights in the quoted source.
// One liberty: MIN_RUN is 6 rather than 32, and the short-slice path (len <= 64: plain
// insertion sort) is not taken, so a 40-element slice shows the run and merge structure.

import { keeps, keepsText } from "/runtime/widget-api.js";

export const N = 40;
export const MIN_RUN = 6;

export const INPUTS = {
  random: "Random",
  nearly: "Nearly sorted",
  reversed: "Reversed",
  sawtooth: "Sawtooth",
};

function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function makeInput(kind, seed = 7) {
  const r = rng(seed);
  const sorted = Array.from({ length: N }, (_, i) => i + 1);
  if (kind === "reversed") return sorted.reverse();
  if (kind === "sawtooth") {
    const tooth = N / 4;
    return sorted.map((_, i) => (i % tooth) * 4 + Math.floor(i / tooth) + 1);
  }
  if (kind === "nearly") {
    const v = sorted.slice();
    for (let k = 0; k < 3; k++) {
      const i = Math.floor(r() * (N - 1));
      const j = Math.min(N - 1, i + 1 + Math.floor(r() * 4));
      [v[i], v[j]] = [v[j], v[i]];
    }
    return v;
  }
  const v = sorted.slice();
  for (let i = N - 1; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [v[i], v[j]] = [v[j], v[i]];
  }
  return v;
}

// A textbook top-down merge sort's comparison count, for the same input: what the sort
// does when it never looks for order already present.
export function plainMergeComparisons(values) {
  let count = 0;
  const sort = (a) => {
    if (a.length < 2) return a;
    const m = a.length >> 1;
    const l = sort(a.slice(0, m));
    const r = sort(a.slice(m));
    const out = [];
    let i = 0;
    let j = 0;
    while (i < l.length && j < r.length) {
      count++;
      out.push(l[i] <= r[j] ? l[i++] : r[j++]);
    }
    return out.concat(l.slice(i), r.slice(j));
  };
  sort(values.slice());
  return count;
}

// Seconds each kind of step takes at 1×. Comparisons and single moves are quick; the
// steps that change the structure (a run found, a push, a stack check, a copy into buf)
// hold long enough to read.
const DUR = {
  begin: 0.3,
  compare: 0.12,
  reverse: 0.9,
  run: 0.8,
  extend: 0.45,
  lift: 0.32,
  shift: 0.14,
  drop: 0.34,
  push: 0.8,
  collapse: 1.5,
  choose: 1.0,
  "to-buf": 0.7,
  copy: 0.12,
  rest: 0.5,
  merged: 0.7,
  done: 2.5,
};

// Which part of the algorithm a step belongs to, for the timeline strip and the heading.
export const PHASE = {
  begin: "scan",
  compare: null,
  reverse: "scan",
  run: "scan",
  extend: "insert",
  lift: "insert",
  shift: "insert",
  drop: "insert",
  push: "stack",
  collapse: "stack",
  choose: "merge",
  "to-buf": "merge",
  copy: "merge",
  rest: "merge",
  merged: "merge",
  done: "done",
};

export function trace(values) {
  const n = values.length;
  const val = values.slice();
  const v = values.map((_, i) => i);
  const buf = new Array(Math.floor(n / 2)).fill(null);
  let bufAt = 0;
  let tmp = null;
  const runs = [];
  let focus = null;
  let win = null;
  let checks = null;
  let phase = "scan";
  let cmp = 0;
  let moves = 0;
  const steps = [];

  const emit = (kind, line, note, extra = {}) => {
    if (PHASE[kind]) phase = PHASE[kind];
    steps.push({
      kind,
      line,
      note,
      phase,
      v: v.slice(),
      buf: buf.slice(),
      bufAt,
      tmp: tmp && { ...tmp },
      runs: runs.map((r) => ({ ...r })),
      focus: focus && { ...focus },
      win: win && { ...win },
      checks,
      cmp,
      moves,
      ...extra,
    });
  };
  // compare(a, b) == Greater, counted.
  const gt = (a, b) => {
    cmp++;
    return val[a] > val[b];
  };
  const at = (lane, idx) => ({ lane, idx });

  // insert_head(&mut v[s..e]): v[s] goes into the sorted v[s+1..e].
  const insertHead = (s, e) => {
    const g = gt(v[s], v[s + 1]);
    emit(
      "compare",
      "ih-test",
      g
        ? `\`v[${s}]\` = ${val[v[s]]} is greater than \`v[${s + 1}]\` = ${val[v[s + 1]]}, so it has to move right.`
        : `\`v[${s}]\` = ${val[v[s]]} is not greater than \`v[${s + 1}]\`: already in place.`,
      { pair: [at("v", s), at("v", s + 1)] },
    );
    if (!g) return;
    tmp = { id: v[s], at: s };
    v[s] = null;
    moves++;
    emit(
      "lift",
      "ih-tmp",
      `Copy ${val[tmp.id]} out into \`tmp\`. Its slot is now the hole.`,
    );
    v[s] = v[s + 1];
    v[s + 1] = null;
    tmp.at = s + 1;
    moves++;
    emit(
      "shift",
      "ih-first",
      `Slide \`v[${s + 1}]\` left into the hole; the hole moves right.`,
      { wrote: at("v", s) },
    );
    for (let i = s + 2; i < e; i++) {
      const g2 = gt(tmp.id, v[i]);
      emit(
        "compare",
        "ih-cmp",
        g2
          ? `\`tmp\` ${val[tmp.id]} > ${val[v[i]]}: keep sliding.`
          : `\`tmp\` ${val[tmp.id]} ≤ ${val[v[i]]}: stop here.`,
        { pair: [at("tmp", 0), at("v", i)] },
      );
      if (!g2) break;
      v[i - 1] = v[i];
      v[i] = null;
      tmp.at = i;
      moves++;
      emit("shift", "ih-shift", `Slide ${val[v[i - 1]]} left; the hole follows.`, {
        wrote: at("v", i - 1),
      });
    }
    const landed = tmp.at;
    v[landed] = tmp.id;
    tmp = null;
    moves++;
    emit(
      "drop",
      "ih-drop",
      "`hole` is dropped, and its Drop copies `tmp` into the hole.",
      { wrote: at("v", landed) },
    );
  };

  // merge(&mut v[lo..hi], mid - lo, buf): the shorter run goes to buf.
  const merge = (lo, mid, hi) => {
    const L = mid - lo;
    const R = hi - mid;
    win = { lo, mid, hi };
    emit(
      "choose",
      "m-choose",
      L <= R
        ? `The left run (${L}) is the shorter: copy it into \`buf\` and merge forwards, smallest first.`
        : `The right run (${R}) is the shorter: copy it into \`buf\` and merge backwards, largest first.`,
    );
    if (L <= R) {
      bufAt = lo;
      for (let k = 0; k < L; k++) {
        buf[k] = v[lo + k];
        v[lo + k] = null;
      }
      moves += L;
      emit(
        "to-buf",
        "m-copy-left",
        `${L} elements into \`buf\`. \`v[${lo}..${mid}]\` is now the hole the merge fills.`,
      );
      let left = 0;
      let right = mid;
      let out = lo;
      const ptr = () => ({
        left: at("buf", left),
        right: at("v", right),
        out: at("v", out),
      });
      while (left < L && right < hi) {
        const g = gt(buf[left], v[right]);
        emit(
          "compare",
          "m-fwd-cmp",
          g
            ? `**${val[buf[left]]} > ${val[v[right]]}**: take from the right run.`
            : `**${val[buf[left]]} ≤ ${val[v[right]]}**: take from \`buf\` (ties go left, so the sort is stable).`,
          { pair: [at("buf", left), at("v", right)], ptr: ptr() },
        );
        let id;
        if (g) {
          id = v[right];
          v[right] = null;
          right++;
        } else {
          id = buf[left];
          buf[left] = null;
          left++;
        }
        v[out] = id;
        out++;
        moves++;
        emit("copy", "m-fwd-copy", `Copy ${val[id]} to \`out\`, and advance.`, {
          ptr: ptr(),
          wrote: at("v", out - 1),
        });
      }
      if (left < L) {
        for (let k = left; k < L; k++) {
          v[out++] = buf[k];
          buf[k] = null;
        }
        moves += L - left;
        emit(
          "rest",
          "m-drop",
          "The right run ran out first. Dropping `hole` copies what is left of `buf` into place.",
        );
      }
    } else {
      bufAt = mid;
      for (let k = 0; k < R; k++) {
        buf[k] = v[mid + k];
        v[mid + k] = null;
      }
      moves += R;
      emit(
        "to-buf",
        "m-copy-right",
        `${R} elements into \`buf\`. \`v[${mid}..${hi}]\` is now the hole the merge fills.`,
      );
      let left = mid;
      let right = R;
      let out = hi;
      const ptr = () => ({
        left: at("v", left - 1),
        right: at("buf", right - 1),
        out: at("v", out - 1),
      });
      while (lo < left && 0 < right) {
        const g = gt(v[left - 1], buf[right - 1]);
        emit(
          "compare",
          "m-bwd-cmp",
          g
            ? `**${val[v[left - 1]]} > ${val[buf[right - 1]]}**: take from the left run.`
            : `**${val[v[left - 1]]} ≤ ${val[buf[right - 1]]}**: take from \`buf\` (ties go right, so the sort is stable).`,
          { pair: [at("v", left - 1), at("buf", right - 1)], ptr: ptr() },
        );
        let id;
        if (g) {
          left--;
          id = v[left];
          v[left] = null;
        } else {
          right--;
          id = buf[right];
          buf[right] = null;
        }
        out--;
        v[out] = id;
        moves++;
        emit("copy", "m-bwd-copy", `Copy ${val[id]} to \`out\`, and step back.`, {
          ptr: ptr(),
          wrote: at("v", out),
        });
      }
      if (right > 0) {
        for (let k = 0; k < right; k++) {
          v[left + k] = buf[k];
          buf[k] = null;
        }
        moves += right;
        emit(
          "rest",
          "m-drop",
          "The left run ran out first. Dropping `hole` copies what is left of `buf` into place.",
        );
      }
    }
    win = null;
  };

  // collapse(&runs), with every clause evaluated so the page can show which one fired.
  const collapse = () => {
    const k = runs.length;
    const len = (i) => runs[k - i].len;
    const list = [];
    if (k >= 2) {
      list.push({
        line: "c-start0",
        text: `runs[n-1].start == 0`,
        fires: runs[k - 1].start === 0,
        detail: `top run starts at ${runs[k - 1].start}`,
      });
      list.push({
        line: "c-inv1",
        text: `runs[n-2].len <= runs[n-1].len`,
        fires: len(2) <= len(1),
        detail: `${len(2)} <= ${len(1)}`,
      });
      if (k >= 3)
        list.push({
          line: "c-inv2",
          text: `runs[n-3].len <= runs[n-2].len + runs[n-1].len`,
          fires: len(3) <= len(2) + len(1),
          detail: `${len(3)} <= ${len(2)} + ${len(1)}`,
        });
      if (k >= 4)
        list.push({
          line: "c-inv3",
          text: `runs[n-4].len <= runs[n-3].len + runs[n-2].len`,
          fires: len(4) <= len(3) + len(2),
          detail: `${len(4)} <= ${len(3)} + ${len(2)}`,
        });
    }
    const first = list.findIndex((c) => c.fires);
    // `||` short-circuits: clauses after the first that fires are never evaluated.
    list.forEach((c, i) => (c.evaluated = first < 0 || i <= first));
    if (first < 0) return { r: null, list, line: "c-none" };
    const r = k >= 3 && len(3) < len(1) ? k - 3 : k - 2;
    return { r, list, line: "c-pick" };
  };

  emit(
    "begin",
    "loop",
    "Walk the slice from the end, cutting it into natural runs: stretches that are already in order.",
  );
  let end = n;
  while (end > 0) {
    let start = end - 1;
    focus = { start, end };
    if (start > 0) {
      start -= 1;
      focus = { start, end };
      const desc = gt(v[start], v[start + 1]);
      emit(
        "compare",
        "desc-test",
        desc
          ? `${val[v[start]]} > ${val[v[start + 1]]}: this run is strictly descending.`
          : `${val[v[start]]} ≤ ${val[v[start + 1]]}: this run is ascending.`,
        { pair: [at("v", start), at("v", start + 1)] },
      );
      if (desc) {
        while (start > 0) {
          const g = gt(v[start - 1], v[start]);
          emit(
            "compare",
            "desc-scan",
            g
              ? `${val[v[start - 1]]} > ${val[v[start]]}: still descending.`
              : `${val[v[start - 1]]} ≤ ${val[v[start]]}: the descending run ends.`,
            {
              pair: [at("v", start - 1), at("v", start)],
            },
          );
          if (!g) break;
          start -= 1;
          focus = { start, end };
        }
        const seg = v.slice(start, end).reverse();
        seg.forEach((id, k) => (v[start + k] = id));
        moves += end - start;
        emit(
          "reverse",
          "reverse",
          `Reverse the ${end - start} descending elements in place: one pass, and they form an ascending run.`,
        );
      } else {
        while (start > 0) {
          const g = gt(v[start - 1], v[start]);
          emit(
            "compare",
            "asc-scan",
            !g
              ? `${val[v[start - 1]]} ≤ ${val[v[start]]}: still ascending.`
              : `${val[v[start - 1]]} > ${val[v[start]]}: the ascending run ends.`,
            {
              pair: [at("v", start - 1), at("v", start)],
            },
          );
          if (g) break;
          start -= 1;
          focus = { start, end };
        }
      }
    }
    emit("run", "loop", `A natural run \`v[${start}..${end}]\`, ${end - start} long.`);
    while (start > 0 && end - start < MIN_RUN) {
      emit(
        "extend",
        "extend",
        `The run is ${end - start} long, under \`MIN_RUN\` (${MIN_RUN}). Insertion sort pulls in the next element.`,
      );
      start -= 1;
      focus = { start, end };
      insertHead(start, end);
    }
    runs.push({ start, len: end - start });
    focus = null;
    emit(
      "push",
      "push",
      `Push the run \`v[${start}..${end}]\` onto the stack of runs waiting to be merged.`,
    );
    end = start;
    for (;;) {
      const c = collapse();
      checks = { list: c.list, r: c.r };
      emit(
        "collapse",
        c.line,
        c.r === null
          ? runs.length < 2
            ? "One run on the stack: nothing to merge yet."
            : "Every invariant holds, so the stack stays as it is and the scan continues."
          : `A clause fired, so merge \`runs[${c.r}]\` with \`runs[${c.r + 1}]\`.`,
      );
      if (c.r === null) break;
      const left = runs[c.r + 1];
      const right = runs[c.r];
      emit(
        "choose",
        "merge-call",
        `Merge \`runs[${c.r + 1}]\` (${left.len}) and \`runs[${c.r}]\` (${right.len}): \`v[${left.start}..${right.start + right.len}]\`.`,
        {
          win: {
            lo: left.start,
            mid: left.start + left.len,
            hi: right.start + right.len,
          },
        },
      );
      merge(left.start, left.start + left.len, right.start + right.len);
      runs[c.r] = { start: left.start, len: left.len + right.len };
      runs.splice(c.r + 1, 1);
      emit(
        "merged",
        "merged-run",
        `One run of ${left.len + right.len} replaces the two.`,
      );
    }
    checks = null;
  }
  emit("done", null, `Sorted, with ${cmp} comparisons.`);

  let t = 0;
  for (const s of steps) {
    s.start = t;
    s.dur = DUR[s.kind];
    t += s.dur;
  }
  return { steps, total: t, val, n, comparisons: cmp, moves };
}

// ---------------------------------------------------------------------------------
// Frame: t → the step, its eased progress, and every element's position.

const ease = (p) => (p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2);

export function stepAt(film, t) {
  let lo = 0;
  let hi = film.steps.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (film.steps[mid].start <= t) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

// Where each element is in a step: in v, in buf (drawn under the slot it was copied
// from), or in tmp (drawn under the hole it will drop into).
function places(step, n) {
  const out = new Array(n);
  step.v.forEach((id, i) => id !== null && (out[id] = { lane: "v", slot: i }));
  step.buf.forEach(
    (id, k) => id !== null && (out[id] = { lane: "buf", slot: step.bufAt + k }),
  );
  if (step.tmp) out[step.tmp.id] = { lane: "tmp", slot: step.tmp.at };
  return out;
}

export function frame(film, t) {
  t = Math.max(0, Math.min(film.total - 1e-6, t));
  const i = stepAt(film, t);
  const step = film.steps[i];
  const prev = film.steps[Math.max(0, i - 1)];
  const p = ease(Math.min(1, (t - step.start) / step.dur));
  const a = places(prev, film.n);
  const b = places(step, film.n);
  const elems = b.map((to, id) => ({ id, value: film.val[id], from: a[id], to, p }));
  return { i, step, elems, t, p };
}

// ---------------------------------------------------------------------------------
// Paint: frame → SVG. Colours come from the page's theme, resolved by the caller. The
// nodes that outlive a frame are written only where the frame changed them (`keeps`).

const SVGNS = "http://www.w3.org/2000/svg";

const el = (tag, attrs = {}, parent) => {
  const node = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  parent?.append(node);
  return node;
};

// The four clauses of collapse(), in source order, with the stack depth each needs.
const CLAUSES = [
  { key: "start0", text: "runs[n-1].start == 0", needs: 2 },
  { key: "inv1", text: "runs[n-2].len <= runs[n-1].len", needs: 2 },
  { key: "inv2", text: "runs[n-3].len <= runs[n-2].len + runs[n-1].len", needs: 3 },
  { key: "inv3", text: "runs[n-4].len <= runs[n-3].len + runs[n-2].len", needs: 4 },
];

// The drawing is laid out in the stage's own pixels, one viewBox unit to a CSS pixel:
// the lanes stretch sideways with the pane while every height and every label keeps its
// size, so the labels read at TYPE at any width. Under the lanes, the run stack stands
// beside the collapse() clauses wherever the clauses fit beside it, a long clause
// breaking after its `<=`, and there the stage keeps one height; in a narrower stage the
// clauses stand under the stack at the full width.
const TYPE = 12;
const LINE = 14;
// A monospace glyph's advance, in ems, which is what a line of code is measured by.
const MONO_EM = 0.6;
const monoWidth = (chars) => chars * TYPE * MONO_EM;
const X0 = 20;
const GAP = 20;
const STACK_W = 124;
const STACK_ROWS = 4;
const ROW_H = 26;
// The longest verdict a clause prints under itself: "not evaluated   40 <= 20 + 20".
const VERDICT_CHARS = 30;

// A clause's lines within `width`: whole, or broken after its comparison.
function clauseLines(text, width) {
  if (monoWidth(text.length) <= width) return [text];
  const at = text.indexOf(" <= ") + 4;
  return [text.slice(0, at - 1), `  ${text.slice(at)}`];
}

const widest = (width) =>
  Math.max(
    monoWidth(VERDICT_CHARS),
    ...CLAUSES.flatMap((c) =>
      clauseLines(c.text, width).map((l) => monoWidth(l.length)),
    ),
  );

function geometry(width) {
  const W = Math.max(280, Math.round(width));
  const g = {
    W,
    laneW: W - 2 * X0,
    vLabel: 13,
    vPtr: 39,
    top: 41,
    base: 101,
    maxH: 50,
    hitTop: 134,
    sLabel: 147,
    sPtr: 173,
    scratch: 235,
  };
  const title = g.scratch + 22;
  g.stack = { x: X0, title, top: title + 10 };
  const besideX = X0 + STACK_W + GAP;
  const room = W - X0 - besideX;
  const clauses =
    room >= widest(room)
      ? { x: besideX, title, width: room }
      : { x: X0, title: g.stack.top + STACK_ROWS * ROW_H + 16, width: g.laneW };
  let y = clauses.title + 4;
  clauses.rows = CLAUSES.map((c) => {
    const lines = clauseLines(c.text, clauses.width);
    const top = y;
    y += (lines.length + 1) * LINE + 3;
    return { lines, top, bottom: y };
  });
  g.clauses = clauses;
  g.H = y + 8;
  return g;
}

export class Painter {
  constructor(svg, n) {
    this.svg = svg;
    this.n = n;
    this.bg = el("rect", {}, svg);
    this.labels = el("g", {}, svg);
    this.laneV = el("text", {}, this.labels);
    this.laneS = el("text", {}, this.labels);
    this.baseV = el("line", {}, svg);
    this.baseS = el("line", {}, svg);
    this.winG = el("g", {}, svg);
    this.holes = el("g", {}, svg);
    this.bars = el("g", {}, svg);
    this.runsG = el("g", {}, svg);
    this.ptrs = el("g", {}, svg);
    this.stack = el("g", {}, svg);
    this.checksG = el("g", {}, svg);
    // Parts: what a viewer can point at and comment on. Every one is drawn at every step,
    // so a comment's anchor never depends on the moment: each slot of v (a transparent
    // column over the bars, on top so it takes the pointer), the scratch lane, the run
    // stack, and each collapse() clause, drawn idle when no collapse is being checked.
    this.hits = el("g", {}, svg);
    this.partEls = new Map();
    const hit = () => el("rect", { fill: "#000", "fill-opacity": 0 }, this.hits);
    this.slotHits = Array.from({ length: n }, (_, s) =>
      this.#part(`v:${s}`, `v[${s}]`, hit()),
    );
    this.scratchHit = this.#part(
      "lane:scratch",
      "the scratch lane (buf and tmp)",
      hit(),
    );
    this.#part("stack:all", "the run stack", this.stack);
    this.checkEls = {};
    for (const key of CLAUSES.map((c) => c.key)) {
      const g = el("g", {}, this.checksG);
      this.checkEls[key] = g;
      this.#part(
        `check:${key}`,
        `collapse() clause ${CLAUSES.find((c) => c.key === key).text}`,
        g,
      );
    }
    this.barEls = [];
    for (let id = 0; id < n; id++) {
      const g = el("g", {}, this.bars);
      el("rect", { rx: 2 }, g);
      this.barEls.push(g);
    }
  }

  // Lay the drawing out for a stage `width` pixels wide: the lanes, their labels and
  // the parts that stand still; each paint places the rest.
  layout(width) {
    const G = (this.G = geometry(width));
    this.slot = G.laneW / this.n;
    const set = (node, attrs) => {
      for (const [k, v] of Object.entries(attrs)) keeps(node, k, v);
    };
    set(this.svg, { viewBox: `0 0 ${G.W} ${G.H}` });
    // The height is set in pixels rather than left to the viewBox's proportions, so in
    // the frames between a pane's resize and this layout the stage keeps its height.
    this.svg.style.height = `${G.H}px`;
    set(this.bg, { width: G.W, height: G.H });
    set(this.laneV, { x: X0, y: G.vLabel });
    set(this.laneS, { x: X0, y: G.sLabel });
    const across = { x1: X0 - 4, x2: X0 + G.laneW + 4 };
    set(this.baseV, { ...across, y1: G.base + 0.5, y2: G.base + 0.5 });
    set(this.baseS, { ...across, y1: G.scratch + 0.5, y2: G.scratch + 0.5 });
    this.slotHits.forEach((node, s) =>
      set(node, { x: this.x(s), y: G.top, width: this.slot, height: G.hitTop - G.top }),
    );
    set(this.scratchHit, {
      x: X0 - 4,
      y: G.hitTop,
      width: G.laneW + 8,
      height: G.scratch - G.hitTop + 6,
    });
  }

  x(slot) {
    return X0 + slot * this.slot;
  }

  #part(id, label, element) {
    element.dataset.part = id;
    this.partEls.set(id, { id, element, label });
    return element;
  }

  parts() {
    return [...this.partEls.values()];
  }

  paint(film, fr, C) {
    const { step } = fr;
    const G = this.G;
    const w = this.slot - 3;
    keeps(this.bg, "fill", C.card);
    for (const line of [this.baseV, this.baseS]) keeps(line, "stroke", C.rule);
    for (const [node, text] of [
      [this.laneV, "v — the slice being sorted"],
      [
        this.laneS,
        step.tmp
          ? "tmp — the element being inserted"
          : "buf — scratch for the shorter run",
      ],
    ]) {
      keepsText(node, text);
      keeps(node, "fill", C.muted);
      keeps(node, "font-family", C.sans);
      keeps(node, "font-size", TYPE);
    }

    // Which run on the stack (or the run being scanned) each slot belongs to.
    const owner = new Array(this.n).fill(-1);
    step.runs.forEach((r, k) => {
      for (let s = r.start; s < r.start + r.len; s++) owner[s] = k;
    });
    const cmp = new Set((step.pair ?? []).map((c) => `${c.lane}:${c.idx}`));
    const wrote = step.wrote ? `${step.wrote.lane}:${step.wrote.idx}` : null;
    const done = step.kind === "done";
    const runTone = (k) => (k % 2 ? C.mark : C.accent);

    for (const e of fr.elems) {
      const g = this.barEls[e.id];
      const rect = g.firstChild;
      const pos = (pl) => ({
        x: this.x(pl.slot) + 1.5,
        base: pl.lane === "v" ? G.base : G.scratch,
      });
      const A = pos(e.from ?? e.to);
      const B = pos(e.to);
      // A move between lanes arcs slightly so crossings read as a hand-off.
      const px = A.x + (B.x - A.x) * e.p;
      const pb = A.base + (B.base - A.base) * e.p;
      const h = 10 + (e.value / this.n) * G.maxH;
      keeps(rect, "x", px);
      keeps(rect, "y", pb - h);
      keeps(rect, "width", w);
      keeps(rect, "height", h);
      const key =
        e.to.lane === "tmp"
          ? "tmp:0"
          : `${e.to.lane}:${e.to.lane === "buf" ? e.to.slot - step.bufAt : e.to.slot}`;
      let fill = C.faint;
      if (done) fill = C.ok;
      else if (cmp.has(key)) fill = C.warn;
      else if (key === wrote) fill = C.ok;
      else if (e.to.lane !== "v") fill = C.ink2;
      else if (step.win && e.to.slot >= step.win.lo && e.to.slot < step.win.hi)
        fill = C.ink2;
      else if (owner[e.to.slot] >= 0) fill = runTone(owner[e.to.slot]);
      else if (
        step.focus &&
        e.to.slot >= step.focus.start &&
        e.to.slot < step.focus.end
      )
        fill = C.ink2;
      keeps(rect, "fill", fill);
      keeps(
        rect,
        "opacity",
        owner[e.to.slot] >= 0 &&
          e.to.lane === "v" &&
          !done &&
          fill !== C.warn &&
          fill !== C.ok
          ? 0.7
          : 1,
      );
    }

    // Holes: slots in v that hold no element, inside the region being worked on.
    this.holes.replaceChildren();
    step.v.forEach((id, s) => {
      if (id !== null) return;
      el(
        "rect",
        {
          x: this.x(s) + 1.5,
          y: G.base - 18,
          width: w,
          height: 18,
          rx: 2,
          fill: "none",
          stroke: C.danger,
          "stroke-dasharray": "3 2",
        },
        this.holes,
      );
    });

    // The merge window, and the scan window, as a tinted band behind the bars.
    this.winG.replaceChildren();
    const band = (from, to, tint, y0, y1) =>
      el(
        "rect",
        {
          x: this.x(from) - 1,
          y: y0,
          width: (to - from) * this.slot + 2,
          height: y1 - y0,
          fill: tint,
          rx: 4,
        },
        this.winG,
      );
    if (step.win) {
      band(step.win.lo, step.win.hi, C.accentTint, G.top, G.base + 2);
      const mx = this.x(step.win.mid) - 1;
      el(
        "line",
        {
          x1: mx,
          x2: mx,
          y1: G.top,
          y2: G.base + 2,
          stroke: C.accent,
          "stroke-dasharray": "4 3",
        },
        this.winG,
      );
    } else if (step.focus)
      band(step.focus.start, step.focus.end, C.field, G.top, G.base + 2);
    if (step.tmp || step.buf.some((b) => b !== null) || step.kind === "choose") {
      const from = step.tmp ? step.tmp.at : step.bufAt;
      const len = step.tmp ? 1 : step.buf.length;
      if (!step.tmp && step.win)
        band(
          step.bufAt,
          step.bufAt + Math.min(step.win.mid - step.win.lo, step.win.hi - step.win.mid),
          C.field,
          G.sPtr + 2,
          G.scratch + 2,
        );
      else if (step.tmp) band(from, from + len, C.warnTint, G.sPtr + 2, G.scratch + 2);
    }

    // Runs on the stack, bracketed under the slice with their stack index where every
    // bracket is wide enough to hold its own, and with their length alone where one is
    // not: the stack under the lanes names each run by its colour.
    this.runsG.replaceChildren();
    const bracket = (start, len, col, label, y) => {
      const x1 = this.x(start) + 1;
      const x2 = this.x(start + len) - 2;
      el(
        "path",
        {
          d: `M${x1},${y - 5} V${y} H${x2} V${y - 5}`,
          fill: "none",
          stroke: col,
          "stroke-width": 1.5,
        },
        this.runsG,
      );
      const t = el(
        "text",
        {
          x: (x1 + x2) / 2,
          y: y + 15,
          "text-anchor": "middle",
          fill: col,
          "font-family": C.mono,
          "font-size": TYPE,
        },
        this.runsG,
      );
      t.textContent = label;
    };
    const named = (k, r) => `runs[${k}] · ${r.len}`;
    const naming = step.runs.every(
      (r, k) => monoWidth(named(k, r).length) <= r.len * this.slot - 3,
    );
    step.runs.forEach((r, k) =>
      bracket(
        r.start,
        r.len,
        runTone(k),
        naming ? named(k, r) : `${r.len}`,
        G.base + 14,
      ),
    );
    if (step.focus && !done)
      bracket(
        step.focus.start,
        step.focus.end - step.focus.start,
        C.ink2,
        `${step.focus.end - step.focus.start}`,
        G.base + 14,
      );

    // Merge pointers, each a mark over its slot with its name in the row above. Names
    // closer than their width in one lane stand apart, in slot order, within the lane.
    this.ptrs.replaceChildren();
    const names = { v: [], buf: [] };
    for (const [name, pl] of Object.entries(step.ptr ?? {})) {
      const slot = pl.lane === "buf" ? step.bufAt + pl.idx : pl.idx;
      if (slot < 0 || slot >= this.n) continue;
      const cx = this.x(slot) + this.slot / 2;
      const y = pl.lane === "v" ? G.vPtr : G.sPtr;
      const col = name === "out" ? C.ok : C.ink2;
      el(
        "path",
        { d: `M${cx - 5},${y - 8} L${cx + 5},${y - 8} L${cx},${y} z`, fill: col },
        this.ptrs,
      );
      names[pl.lane === "v" ? "v" : "buf"].push({ name, cx, y: y - 12, col });
    }
    for (const lane of Object.values(names)) {
      lane.sort((a, b) => a.cx - b.cx);
      let right = -Infinity;
      for (const p of lane) {
        p.w = monoWidth(p.name.length);
        p.x = Math.max(p.cx - p.w / 2, right + 6);
        right = p.x + p.w;
      }
      let left = X0 + G.laneW;
      for (const p of lane.toReversed()) {
        p.x = Math.max(X0, Math.min(p.x, left - p.w));
        left = p.x - 6;
      }
      for (const p of lane) {
        const t = el(
          "text",
          {
            x: p.x,
            y: p.y,
            fill: p.col,
            "font-family": C.mono,
            "font-size": TYPE,
          },
          this.ptrs,
        );
        t.textContent = p.name;
      }
    }

    this.#paintStack(step, C, runTone);
  }

  // The run stack, bottom to top, and the collapse() clauses that decide whether to merge.
  #paintStack(step, C, runTone) {
    const { stack: S, clauses: K } = this.G;
    const g = this.stack;
    g.replaceChildren();
    const text = (x, y, s, attrs = {}) => {
      const t = el(
        "text",
        { x, y, fill: C.ink, "font-family": C.sans, "font-size": TYPE, ...attrs },
        g,
      );
      t.textContent = s;
      return t;
    };
    const k = step.runs.length;
    el(
      "rect",
      {
        x: S.x - 6,
        y: S.title - LINE,
        width: STACK_W + 12,
        height: S.top + STACK_ROWS * ROW_H - (S.title - LINE),
        fill: "#000",
        "fill-opacity": 0,
      },
      g,
    );
    text(S.x, S.title, "runs, top first", { fill: C.muted });
    const pick = step.checks?.r;
    const merging = step.win
      ? new Set(
          step.runs
            .map((r, i) => i)
            .filter(
              (i) =>
                step.runs[i].start >= step.win.lo && step.runs[i].start < step.win.hi,
            ),
        )
      : new Set();
    for (let i = k - 1; i >= 0; i--) {
      const r = step.runs[i];
      const y = S.top + (k - 1 - i) * ROW_H;
      const hot =
        merging.has(i) ||
        (pick !== null && pick !== undefined && (i === pick || i === pick + 1));
      el(
        "rect",
        {
          x: S.x,
          y,
          width: STACK_W,
          height: ROW_H - 6,
          rx: 4,
          fill: hot ? C.accentTint : C.field,
          stroke: hot ? C.accent : C.rule,
        },
        g,
      );
      el(
        "rect",
        {
          x: S.x,
          y: y + ROW_H - 9,
          width: (STACK_W * r.len) / this.n,
          height: 3,
          fill: runTone(i),
        },
        g,
      );
      text(S.x + 8, y + 13, `runs[${i}]`, { "font-family": C.mono, fill: runTone(i) });
      text(S.x + STACK_W - 8, y + 13, `len ${r.len}`, {
        "font-family": C.mono,
        "text-anchor": "end",
        fill: C.ink2,
      });
    }
    if (!k) text(S.x, S.top + 13, "empty", { fill: C.muted, "font-style": "italic" });

    // The collapse() clauses, always drawn: idle between checks, and during one each
    // clause says whether it held, or that `||` never reached it.
    const list = step.checks?.list ?? [];
    text(K.x, K.title, "collapse(): merge when a clause is true", { fill: C.muted });
    CLAUSES.forEach((clause, i) => {
      const { lines, top, bottom } = K.rows[i];
      const c = list.find((c) => c.line === `c-${clause.key}`);
      const cg = this.checkEls[clause.key];
      cg.replaceChildren();
      el(
        "rect",
        {
          x: K.x - 6,
          y: top + 2,
          width: K.width + 6,
          height: bottom - top - 1,
          fill: "#000",
          "fill-opacity": 0,
        },
        cg,
      );
      const col = !c || !c.evaluated ? C.faint : c.fires ? C.danger : C.muted;
      const t1 = el(
        "text",
        {
          fill: c?.evaluated ? C.ink2 : C.faint,
          "font-family": C.mono,
          "font-size": TYPE,
        },
        cg,
      );
      lines.forEach((line, n) =>
        el("tspan", { x: K.x, y: top + (n + 1) * LINE }, t1).append(line),
      );
      const t2 = el(
        "text",
        {
          x: K.x,
          y: top + (lines.length + 1) * LINE,
          fill: col,
          "font-family": C.mono,
          "font-size": TYPE,
        },
        cg,
      );
      t2.textContent = !c
        ? step.checks
          ? `not checked: needs ${clause.needs} runs`
          : "·"
        : `${c.evaluated ? (c.fires ? "true → merge" : "false") : "not evaluated"}   ${c.detail}`;
    });
  }
}

// Each line name a step uses, as the source line numbers it stands for in
// slice.rs at 1.15.0. The quoted excerpts answer to those numbers.
export const LINES = {
  "asc-scan": "1561",
  "c-inv1": "1618",
  "c-inv2": "1619",
  "c-inv3": "1620",
  "c-none": "1627",
  "c-pick": "1621",
  "c-start0": "1617",
  "collapse-call": "1582",
  "desc-scan": "1556",
  "desc-test": "1555",
  extend: "1569,1571",
  "ih-cmp": "1351",
  "ih-drop": "1357",
  "ih-first": "1348",
  "ih-shift": "1354",
  "ih-test": "1313",
  "ih-tmp": "1332",
  loop: "1550",
  "m-bwd-cmp": "1455",
  "m-bwd-copy": "1460",
  "m-choose": "1414",
  "m-copy-left": "1416",
  "m-copy-right": "1440",
  "m-drop": "1463,1464",
  "m-fwd-cmp": "1431",
  "m-fwd-copy": "1436",
  "merge-call": "1586",
  "merged-run": "1589",
  push: "1575",
  reverse: "1559",
};
