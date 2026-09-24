// The wt merge film: one SVG whose every frame is a pure function of (flags, t).
//
// compile(flags, scenario) walks worktrunk's merge pipeline once and emits scenes. Each
// holds the world before and after it (commits, edges, refs, worktrees, hook chips, and
// the callouts that explain the step in place), the terminal lines it prints, and a
// caption saying what the step did in this run. frame(film, t) finds the scene and eases
// between its two worlds; the Painter reconciles keyed SVG nodes against that frame. The
// page tells the step beside the film from the chapter and caption each frame carries.

const SVG = "http://www.w3.org/2000/svg";
const W = 1280;
const H = 720;
const MAIN_Y = 170;
const FEAT_Y = 300;
const GRAPH_X = 70;
const STEP_X = 104;
const TERM = { x: 790, y: 96, w: 450, h: 470, line: 21, rows: 19 };

// The drawing takes the page's own colours. SVG presentation attributes can't hold the
// theme's light-dark() tokens, so themePalette resolves each role on a probe inside the
// host, which is where the page's light or dark choice applies; the widget calls it
// again when the theme changes. The terminal reads as one of the page's code blocks.
const ROLES = {
  bg: "--card", panel: "--field", panel2: "--paper", rule: "--rule", ink: "--ink",
  muted: "--muted", faint: "--border-2", main: "--accent", feat: "--warn",
  squash: "--mark-ink", ok: "--ok", bad: "--danger", warn: "--warn-ink",
};
const TERM_ROLES = { bg: "--pre-bg", rule: "--code-border", ink: "--code-ink", muted: "--code-muted", ok: "--ok", bad: "--danger" };

export function themePalette(host) {
  const probe = document.createElement("span");
  probe.hidden = true;
  host.append(probe);
  const read = (token) => {
    probe.style.color = `var(${token})`;
    return getComputedStyle(probe).color;
  };
  const resolve = (roles) => Object.fromEntries(Object.entries(roles).map(([role, token]) => [role, read(token)]));
  const palette = { ...resolve(ROLES), term: resolve(TERM_ROLES) };
  probe.remove();
  return palette;
}

const MONO = "ui-monospace, SFMono-Regular, Menlo, monospace";
const SANS = "system-ui, -apple-system, 'Segoe UI', sans-serif";

const CHAPTERS = [
  ["commit", "Commit"],
  ["squash", "Squash"],
  ["rebase", "Rebase"],
  ["premerge", "Pre-merge hooks"],
  ["merge", "Merge"],
  ["preremove", "Pre-remove hooks"],
  ["cleanup", "Cleanup"],
  ["postmerge", "Post-merge hooks"],
];

export const DEFAULT_FLAGS = {
  moved: true,
  squash: true,
  rebase: true,
  ff: true,
  remove: true,
  hookFails: false,
  conflict: false,
};

const clone = (v) => structuredClone(v);
const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - (-2 * p + 2) ** 3 / 2);
const easeOut = (p) => 1 - (1 - p) ** 3;
const lerp = (a, b, p) => a + (b - a) * p;
const clamp01 = (p) => Math.max(0, Math.min(1, p));
const x = (i) => GRAPH_X + i * STEP_X;

function commandLine(f) {
  const parts = ["wt merge"];
  if (!f.squash) parts.push("--no-squash");
  if (!f.rebase) parts.push("--no-rebase");
  if (!f.ff) parts.push("--no-ff");
  if (!f.remove) parts.push("--no-remove");
  return parts.join(" ");
}

// ---------------------------------------------------------------------------------
// Compile: flags → scenes

// A scenario is the repository state the film merges: main's history up to the fork,
// what landed on main since, the branch's commits and uncommitted files, and the hooks
// .config/wt.toml configures. EXAMPLE is the built-in story; a page can bind a captured
// scenario instead (the `merge-scenario` data contract) to animate a real branch.
export const EXAMPLE = {
  repo: "~/repo",
  worktree: "~/repo.feature",
  branch: "feature",
  target: "main",
  base: [
    { hash: "3e1f0c2", subject: "History main and feature share." },
    { hash: "8a4d7b1", subject: "Where feature forked off main." },
  ],
  ahead: [{ hash: "e90b4f6", subject: "Another agent's change, landed on main after feature forked." }],
  commits: [
    { hash: "b72c9e4", subject: "wip" },
    { hash: "51e0d3a", subject: "fix" },
  ],
  dirty: 3,
  files: 3,
  insertions: 84,
  message: "feat: add merge animation",
  hooks: {
    "pre-merge": [{ name: "test", command: "cargo test", output: "test result: ok. 214 passed; 0 failed" }],
    "pre-remove": [{ name: "snapshot", command: "" }],
    "post-merge": [{ name: "install", command: "" }],
  },
};

// Commits the film invents (squash, rebased copies, merge commit) get stable fake
// hashes derived from what they stand for, so a scenario always draws the same film.
function fakeHash(seed) {
  let h = 2166136261;
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return (h >>> 0).toString(16).padStart(8, "0").slice(0, 7);
}

const MAX_FEATURE_NODES = 3;

export function compile(f, sc = EXAMPLE) {
  const world = {
    nodes: {},
    edges: {},
    refs: {},
    trees: {},
    chips: {},
    notes: {},
    flash: { o: 0 },
  };
  const scenes = [];
  const status = {};
  let chapter = "setup";
  let noted = chapter;
  let captionTone = "ink";
  let caption = "";
  const T = sc.target;
  const B = sc.branch;

  // Each step explains itself with callouts on the elements it changes; a new step
  // clears the last one's, except where a failure's marker must stay to the end.
  const scene = (dur, mutate, lines = [], opts = {}) => {
    const from = clone(world);
    if (chapter !== noted) {
      noted = chapter;
      for (const n of Object.values(world.notes)) if (!n.keep) n.o = 0;
    }
    mutate?.(world);
    scenes.push({
      chapter,
      dur,
      from,
      to: clone(world),
      lines,
      caption: opts.caption ?? caption,
      captionTone,
      ease: opts.ease ?? easeInOut,
    });
  };
  // A callout: `at` is a node id, ref id (`ref:main`), chip id (`chip:pre`), tree id
  // (`tree:feature`) or {x, y}; `from` makes it an arrow from one anchor to another.
  const note = (id, props) => (world.notes[id] = { o: 1, tone: "ink", side: "up", ...props });
  const begin = (key, state, words) => {
    chapter = key;
    status[key] = state;
    caption = words;
  };
  const node = (id, props) => (world.nodes[id] = { o: 1, r: 13, ...props });
  const edge = (a, b, props = {}) =>
    (world.edges[`${a}>${b}`] = { a, b, o: 1, dash: 0, ...props });
  const ref = (id, props) => (world.refs[id] = { o: 1, ...props });
  const out = (text, tone = "ink", kind = "line") => ({ text, tone, kind });
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  const ahead = f.moved ? sc.ahead : [];
  const moved = ahead.length > 0;
  const hooks = (kind) => sc.hooks?.[kind] ?? [];
  // The feature lane holds at most three nodes; older commits fold into the first.
  const room = MAX_FEATURE_NODES - (sc.dirty ? 1 : 0);
  const shown = sc.commits.slice(-room);
  const folded = sc.commits.length - shown.length;
  const fork = sc.base.at(-1).hash;

  // Setup: the target's history, the branch, its uncommitted edits, and what landed since.
  const pieces = [
    sc.commits.length && plural(sc.commits.length, "commit"),
    sc.dirty && `${plural(sc.dirty, "uncommitted file")}`,
  ].filter(Boolean);
  caption = `${B}: ${pieces.join(", ")}` + (moved ? ` — and ${T} has moved on.` : `, on top of ${T}.`);
  scene(1.4, (w) => {
    sc.base.slice(-2).forEach((c, i, arr) => {
      node(`m${i + 1}`, {
        x: x(i),
        y: MAIN_Y,
        tone: "main",
        hash: c.hash,
        info: i === arr.length - 1 ? `${c.subject} — where ${B} forked off ${T}.` : c.subject,
      });
      if (i) edge(`m${i}`, `m${i + 1}`, { tone: "main" });
    });
    ref("main", {
      at: `m${Math.min(2, sc.base.length)}`,
      tone: "main",
      side: -1,
      label: T,
      info: `The branch wt merge lands on. It moves only in step 5.`,
    });
    w.trees.repo = { o: 1, i: 0, path: sc.repo, branch: T, dirty: 0, note: "", info: `The primary worktree, on ${T}. The merge ends here.` };
  });
  const forkId = `m${Math.min(2, sc.base.length)}`;
  const featIds = [];
  scene(1.8, (w) => {
    let prev = forkId;
    shown.forEach((c, i) => {
      const id = `f${i}`;
      const more = i === 0 && folded ? ` (+${plural(folded, "earlier commit")} before it)` : "";
      node(id, { x: x(2 + i), y: FEAT_Y, tone: "feat", hash: c.hash, info: `${c.subject}${more}` });
      edge(prev, id, { tone: "feat" });
      featIds.push(id);
      prev = id;
    });
    if (sc.dirty) {
      node("wt", {
        x: x(2 + shown.length),
        y: FEAT_Y,
        tone: "feat",
        wip: 1,
        hash: `+${plural(sc.dirty, "file")}`,
        info: `Uncommitted edits in ${sc.worktree} — ${plural(sc.dirty, "file")}, not yet a commit.`,
      });
      edge(prev, "wt", { tone: "feat", dash: 1 });
      featIds.push("wt");
      note("dirty", { at: "wt", text: "not committed yet", side: "right", tone: "warn" });
    }
    note("fork", { at: forkId, text: `${B} forked here`, side: "down-left", tone: "feat" });
    ref("feature", {
      at: featIds.at(-1),
      tone: "feat",
      side: 1,
      label: B,
      info: `The branch being merged. Deleted with its worktree in step 7.`,
    });
    w.trees.feature = {
      o: 1,
      i: 1,
      path: sc.worktree,
      branch: B,
      dirty: sc.dirty,
      note: "",
      info: `The worktree wt merge runs in. Removed in step 7 unless --no-remove.`,
    };
  });
  if (moved) {
    const last = ahead.at(-1);
    scene(1.3, (w) => {
      node("m3", {
        x: x(2),
        y: MAIN_Y,
        tone: "main",
        hash: ahead.length > 1 ? `+${ahead.length - 1} · ${last.hash}` : last.hash,
        info:
          ahead.length > 1
            ? `${plural(ahead.length, "commit")} landed on ${T} after the fork; the newest is "${last.subject}".`
            : `"${last.subject}" — landed on ${T} after ${B} forked.`,
      });
      edge(forkId, "m3", { tone: "main" });
      w.refs.main.at = "m3";
      note("ahead", {
        at: "m3",
        text: ahead.length > 1 ? `${ahead.length} commits landed since` : "landed since the fork",
        side: "right",
        tone: "main",
      });
    });
  }
  const mainTip = moved ? "m3" : forkId;
  scene(1.0, null, [out(commandLine(f), "ink", "cmd")]);

  // 1 · Commit. Squash stages the edits itself, so the default run skips this step.
  let lane = [...featIds];
  if (f.squash || !sc.dirty) {
    begin(
      "commit",
      "skip",
      sc.dirty
        ? "1 · Commit — skipped: squashing will stage the uncommitted edits itself."
        : "1 · Commit — skipped: nothing uncommitted.",
    );
    scene(1.3, null);
  } else {
    const hash = fakeHash(`commit ${sc.worktree}`);
    begin("commit", "run", "1 · Commit — the uncommitted edits become a commit of their own.");
    scene(
      2.2,
      (w) => {
        Object.assign(w.nodes.wt, { wip: 0, hash, info: "The uncommitted edits, committed by step 1." });
        w.edges[`${featIds.at(-2) ?? forkId}>wt`].dash = 0;
        w.trees.feature.dirty = 0;
      },
      [out("◎ Committing changes...", "muted"), out(`✓ Committed @ ${hash}`, "ok")],
    );
  }

  // 2 · Squash: every commit since the target plus swept-in edits become one.
  // wt squashes whenever there is more than one commit or anything uncommitted to sweep in.
  const squashable = sc.commits.length > 1 || sc.dirty > 0;
  if (f.squash && squashable) {
    const hash = fakeHash(`squash ${sc.commits.map((c) => c.hash).join()}`);
    const backup = fakeHash(`backup ${sc.worktree}`);
    begin(
      "squash",
      "run",
      `2 · Squash — ${lane.length > 2 ? "everything since the fork" : "both pieces of work"} becomes one commit.` +
        (sc.dirty ? " The old tip is backed up first." : ""),
    );
    scene(
      1.6,
      (w) => {
        if (sc.dirty) {
          ref("backup", {
            at: featIds.at(-1),
            tone: "warn",
            side: 2,
            label: `refs/wt-backup/${B}`,
            info: "The pre-squash tip plus the uncommitted edits, saved so the squash can be undone.",
          });
        }
        w.refs.feature.o = 0;
        note("sweep", { at: featIds.at(-1), text: "all of this becomes one commit", side: "right", tone: "squash" });
      },
      [
        out(
          `◎ Squashing ${plural(sc.commits.length, "commit")}${sc.dirty ? " & working tree changes" : ""}`,
          "muted",
        ),
        out(`  into a single commit (${plural(sc.files, "file")}, +${sc.insertions})...`, "muted"),
        ...(sc.dirty ? [out(`↳ Backup created @ ${backup}`, "muted")] : []),
      ],
    );
    scene(
      2.2,
      (w) => {
        for (const id of featIds) Object.assign(w.nodes[id], { x: x(2), o: 0 });
        let prev = forkId;
        for (const id of featIds) {
          w.edges[`${prev}>${id}`].o = 0;
          prev = id;
        }
        node("sq", {
          x: x(2),
          y: FEAT_Y,
          tone: "squash",
          hash,
          r: 17,
          msg: `${sc.commits.length + (sc.dirty ? 1 : 0)}→1`,
          info: `One commit holding ${[
            ...sc.commits.map((c) => c.hash),
            ...(sc.dirty ? [`the ${plural(sc.dirty, "uncommitted file")}`] : []),
          ].join(", ")}.`,
        });
        edge(forkId, "sq", { tone: "squash" });
        note("squash", {
          at: "sq",
          text: `${featIds.length} pieces → 1 commit`,
          side: "down-left",
          tone: "squash",
        });
        if (w.refs.backup) w.refs.backup.o = 0;
        Object.assign(w.refs.feature, { at: "sq", o: 1 });
        w.trees.feature.dirty = 0;
      },
      [out(`  ${sc.message}`, "ink"), out(`✓ Squashed @ ${hash}`, "ok")],
    );
    lane = ["sq"];
  } else {
    begin(
      "squash",
      "skip",
      f.squash
        ? "2 · Squash — skipped: there is only one commit."
        : "2 · Squash — skipped (--no-squash): each commit is kept.",
    );
    scene(1.3, null);
  }

  // 3 · Rebase onto the target. Nothing to replay when it hasn't moved.
  const first = lane[0];
  const hashOf = (w, id) => w.nodes[id].hash;
  let failed = null;
  if (!moved) {
    begin("rebase", "skip", `3 · Rebase — skipped: ${B} already sits on ${T}'s tip.`);
    scene(1.3, null, [out("◎ No rebase needed", "muted")]);
  } else if (f.rebase && f.conflict) {
    begin(
      "rebase",
      "fail",
      `3 · Rebase — stops on a conflict: ${T} changed the same lines. The rebase is left open to resolve.`,
    );
    scene(0.8, null, [out(`◎ Rebasing onto ${T}...`, "muted")]);
    scene(
      2.8,
      (w) => {
        const n = w.nodes[first];
        node(`${first}~`, { ...n, tone: "ghost", o: 0.55, msg: "", info: `The original ${n.hash}, still where it was.` });
        Object.assign(n, {
          x: x(3),
          tone: "bad",
          hash: "conflict",
          info: `${n.hash} half-applied onto ${hashOf(w, "m3")}: a file has conflict markers.`,
        });
        lane.slice(1).forEach((id, i) => Object.assign(w.nodes[id], { o: 0.35, x: x(4 + i) }));
        w.edges[`${forkId}>${first}`].o = 0;
        edge("m3", first, { tone: "bad", dash: 1 });
        w.trees.feature.note = "rebase in progress";
        note("stop", { at: first, text: "✗ stops here: conflict", side: "right", tone: "bad", keep: 1 });
        w.flash.o = 1;
      },
      [
        out(`✗ Rebase onto ${T} incomplete`, "bad"),
        out(`  Rebasing (1/${lane.length})`, "muted"),
        out("  CONFLICT (content): Merge conflict", "bad"),
      ],
    );
    failed = "conflict";
  } else if (f.rebase) {
    begin("rebase", "run", `3 · Rebase — the work is replayed on top of ${T}'s new tip, as new commits.`);
    scene(0.8, null, [out(`◎ Rebasing onto ${T}...`, "muted")]);
    scene(
      2.4,
      (w) => {
        // Rebased commits are new commits: fresh hashes, one step right of the target's
        // tip, with a fading ghost left where the originals stood.
        lane.forEach((id, i) => {
          const n = w.nodes[id];
          node(`${id}~`, { ...n, tone: "ghost", o: 0.55, msg: "", info: `The original ${n.hash}, left behind by the rebase.` });
          Object.assign(n, {
            x: x(3 + i),
            hash: fakeHash(`rebased ${n.hash}`),
            info: `${n.hash} replayed onto ${hashOf(w, "m3")}: same change, new parent, so a new hash.`,
          });
        });
        w.edges[`${forkId}>${first}`].o = 0;
        edge("m3", first, { tone: lane.length > 1 ? "feat" : "squash" });
        note("replay", {
          from: `${lane.at(-1)}~`,
          at: lane.at(-1),
          text: "replayed on the new tip: new hash",
          tone: "ink",
        });
      },
      [out(`✓ Rebased onto ${T}`, "ok")],
    );
    scene(0.9, (w) => {
      for (const id of lane) w.nodes[`${id}~`].o = 0;
    });
  } else {
    begin(
      "rebase",
      "fail",
      `3 · Rebase — refused (--no-rebase): ${T} can't fast-forward to a branch that isn't on top of it.`,
    );
    scene(
      2.6,
      (w) => {
        w.flash.o = 1;
        Object.assign(w.refs.main, { tone: "bad" });
        note("stop", {
          at: first,
          text: `✗ stops here: not on top of ${T}`,
          side: "right",
          tone: "bad",
          keep: 1,
        });
      },
      [out(`✗ Branch not rebased onto ${T}`, "bad")],
    );
    failed = "rebase";
  }

  // 4 · Pre-merge hooks run against the exact tree that will land.
  const pre = hooks("pre-merge");
  if (!failed && !pre.length) {
    begin("premerge", "skip", "4 · Pre-merge hooks — none configured in .config/wt.toml, so nothing runs.");
    scene(1.3, null);
  } else if (!failed) {
    const chipAt = { x: GRAPH_X - 20, y: 420 };
    const names = pre.map((h) => h.name).join(", ");
    const label = `pre-merge · ${pre.length === 1 && pre[0].command ? pre[0].command : names}`;
    begin(
      "premerge",
      f.hookFails ? "fail" : "run",
      f.hookFails
        ? `4 · Pre-merge hooks — a hook fails, so nothing lands. ${T} is untouched.`
        : `4 · Pre-merge hooks — local CI: they run on the rebased result, before ${T} moves.`,
    );
    scene(
      0.6,
      (w) => {
        note("tested", { at: lane.at(-1), text: "this exact commit is what gets tested", side: "right", tone: "warn" });
        w.chips.pre = {
          ...chipAt,
          o: 1,
          p: 0,
          state: "run",
          label,
          info: `[pre-merge] ${pre.map((h) => (h.command ? `${h.name} = "${h.command}"` : h.name)).join("; ")} in .config/wt.toml. Runs on the rebased tree, the exact one that lands; a failure aborts the merge.`,
        };
      },
      pre.flatMap((h) => [
        out(`◎ Running pre-merge project:${h.name}`, "muted"),
        ...(h.command ? [out(`  ${h.command}`, "ink")] : []),
      ]),
    );
    if (f.hookFails) {
      const h = pre[0];
      scene(1.8, (w) => (w.chips.pre.p = 0.72), [out("  ... FAILED", "bad")]);
      scene(
        2.4,
        (w) => {
          w.chips.pre.state = "fail";
          w.chips.pre.label = `${label} failed`;
          note("stop", { at: "ref:main", text: `✗ stops here: ${T} never moves`, side: "right", tone: "bad", keep: 1 });
          w.flash.o = 1;
        },
        [
          out(`✗ pre-merge project:${h.name} failed`, "bad"),
          ...(status.squash === "run" ? [out("↳ The branch stays squashed.", "muted")] : []),
        ],
      );
      failed = "premerge";
    } else {
      scene(
        1.9,
        (w) => (w.chips.pre.p = 1),
        pre.filter((h) => h.output).map((h) => out(`  ${h.output}`, "ok")),
      );
      scene(0.6, (w) => {
        w.chips.pre.state = "ok";
        w.chips.pre.label = `${label} ✓`;
      });
    }
  }

  // 5 · Merge: move the target to the branch tip, or record a merge commit with --no-ff.
  if (!failed) {
    const tipId = lane.at(-1);
    const count = lane.length;
    begin(
      "merge",
      "run",
      f.ff
        ? `5 · Merge — a fast-forward: ${T} simply moves to the branch tip. History stays linear.`
        : "5 · Merge — --no-ff records a merge commit, keeping the branch visible in history.",
    );
    const stats = `${plural(count, "commit")}, ${plural(sc.files, "file")}, +${sc.insertions}`;
    scene(
      0.8,
      (w) => {
        if (w.chips.pre) w.chips.pre.o = 0;
      },
      [out(`◎ Merging ${plural(count, "commit")} to ${T}${f.ff ? "" : " (--no-ff)"}`, "muted")],
    );
    if (f.ff) {
      scene(
        2.4,
        (w) => {
          for (const id of lane) Object.assign(w.nodes[id], { y: MAIN_Y, tone: "main" });
          w.refs.main.at = tipId;
          note("ff", { from: mainTip, at: tipId, text: "", tone: "main" });
          note("ffto", { at: tipId, text: `${T} moved here: a fast-forward`, side: "right", tone: "main" });
          for (const e of Object.values(w.edges)) if (lane.includes(e.b) && e.o > 0) e.tone = "main";
        },
        [out(`✓ Merged to ${T} (${stats})`, "ok")],
      );
    } else {
      scene(
        2.6,
        (w) => {
          const hash = fakeHash(`merge ${hashOf(w, tipId)}`);
          node("mm", {
            x: w.nodes[tipId].x + STEP_X,
            y: MAIN_Y,
            tone: "main",
            hash,
            r: 15,
            merge: 1,
            info: `Merge commit from --no-ff: parents ${hashOf(w, mainTip)} and ${hashOf(w, tipId)}.`,
          });
          edge(mainTip, "mm", { tone: "main" });
          edge(tipId, "mm", { tone: "main" });
          w.refs.main.at = "mm";
          note("mm", { at: "mm", text: "merge commit: two parents", side: "right", tone: "main" });
        },
        [out(`✓ Merged to ${T} (${stats}, --no-ff)`, "ok")],
      );
    }
  }

  // 6 · Pre-remove hooks, then 7 · cleanup of the worktree and branch.
  if (!failed) {
    const rm = hooks("pre-remove");
    if (f.remove) {
      if (rm.length) {
        begin("preremove", "run", "6 · Pre-remove hooks — a last chance to act before the worktree goes.");
        scene(
          1.6,
          (w) => {
            w.chips.rm = {
              x: GRAPH_X + 380,
              y: 440,
              o: 1,
              p: 1,
              state: "ok",
              label: "pre-remove ✓",
              info: "[pre-remove] hooks run before the worktree is deleted; a failure keeps it.",
            };
          },
          rm.map((h) => out(`◎ Running pre-remove project:${h.name}`, "muted")),
        );
      } else {
        begin("preremove", "skip", "6 · Pre-remove hooks — none configured, so nothing runs.");
        scene(1.1, null);
      }
      begin("cleanup", "run", `7 · Cleanup — the worktree and branch are removed in the background; you land in ${T}.`);
      scene(
        2.2,
        (w) => {
          if (w.chips.rm) w.chips.rm.o = 0;
          Object.assign(w.trees.feature, { o: 0, gone: 1 });
          w.refs.feature.o = 0;
          w.trees.repo.here = 1;
          note("gone", { at: "tree:feature", text: "worktree and branch removed", side: "up", tone: "muted" });
        },
        [
          out(`◎ Removing ${B} worktree & branch`, "muted"),
          out(`  in background (same commit as ${T})`, "muted"),
          out(`○ Switched to worktree for ${T} @ ${sc.repo}`, "ink"),
        ],
      );
    } else {
      begin("preremove", "skip", "6 · Pre-remove hooks — skipped: nothing is being removed.");
      scene(1.1, null);
      begin("cleanup", "skip", "7 · Cleanup — skipped (--no-remove): the worktree stays for more work.");
      scene(1.6, null, [out("○ Worktree preserved (--no-remove)", "ink")]);
    }
    const post = hooks("post-merge");
    if (post.length) {
      begin(
        "postmerge",
        "run",
        `8 · Post-merge hooks — run in the background from ${T}, after you already have your prompt back.`,
      );
      scene(
        2.6,
        (w) => {
          w.chips.post = {
            x: GRAPH_X - 20,
            y: 420,
            o: 1,
            p: 1,
            state: "bg",
            label: `post-merge · ${post.map((h) => h.name).join(", ")} (background)`,
            info: `[post-merge] hooks run in the background from ${sc.repo}, after the prompt returns.`,
          };
          note("bg", { at: "chip:post", text: "runs after your prompt is back", side: "right", tone: "muted" });
        },
        [...post.map((h) => out(`◎ Running post-merge: ${h.name} @ ${sc.repo}`, "muted")), out("$ ▍", "ink")],
      );
    } else {
      begin("postmerge", "skip", "8 · Post-merge hooks — none configured.");
      scene(1.3, null, [out("$ ▍", "ink")]);
    }
  }

  // End card.
  chapter = "end";
  const verbs = {
    commit: "committed",
    squash: "squashed",
    rebase: "rebased",
    premerge: "tested",
    merge: "merged",
    cleanup: "cleaned up",
  };
  const ran = Object.keys(verbs).filter((k) => status[k] === "run").map((k) => verbs[k]);
  const kept = ran.filter((v) => v === "squashed" || v === "rebased");
  const endTitle = {
    rebase: "Refused before anything ran.",
    conflict: "Stopped mid-rebase.",
    premerge: `A hook failed. ${T} never moved.`,
  }[failed] ?? "Landed.";
  const endSub =
    {
      rebase: `--no-rebase keeps the graph as-is, so ${T} must already be its ancestor.`,
      conflict: `Resolve the conflict in ${sc.worktree}, then run wt merge again. ${T} is untouched.`,
      premerge: `Fix it and run wt merge again${kept.length ? ` — it's already ${kept.join(" and ")}` : ""}.`,
    }[failed] ?? `One command: ${ran.join(", ")}.` + (f.remove ? "" : " The worktree stays.");
  caption = `${endTitle} ${endSub}`;
  captionTone = failed ? "bad" : "ok";
  scene(
    1.6,
    (w) => {
      w.flash.o = 0;
      if (!failed) note("landed", { at: "ref:main", text: `✓ ${T} is here now`, side: "right", tone: "ok" });
    },
    [],
    { ease: easeOut },
  );
  scene(3.4, null);

  for (const [key] of CHAPTERS) status[key] ??= "unreached";
  let t = 0;
  for (const s of scenes) {
    s.start = t;
    t += s.dur;
  }
  const starts = {};
  for (const s of scenes) starts[s.chapter] ??= s.start;
  return { scenes, total: t, status, starts, failed, scenario: sc };
}

// ---------------------------------------------------------------------------------
// Frame: (film, t) → an eased world plus the terminal and caption at that moment

function mix(a, b, p) {
  const keys = new Set([...Object.keys(a ?? {}), ...Object.keys(b ?? {})]);
  const outv = {};
  for (const k of keys) {
    const va = a?.[k];
    const vb = b?.[k];
    if (typeof va === "number" && typeof vb === "number") outv[k] = lerp(va, vb, p);
    else if (va === undefined) outv[k] = typeof vb === "number" && k === "o" ? vb * p : vb;
    else if (vb === undefined) outv[k] = typeof va === "number" && k === "o" ? va * (1 - p) : va;
    else outv[k] = p < 0.5 ? va : vb;
  }
  return outv;
}

function mixGroup(a, b, p) {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  const outv = {};
  for (const k of keys) {
    const va = a[k] ?? (b[k] && { ...b[k], o: 0 });
    const vb = b[k] ?? (a[k] && { ...a[k], o: 0 });
    outv[k] = mix(va, vb, p);
  }
  return outv;
}

export function frame(film, t) {
  t = Math.max(0, Math.min(film.total - 1e-6, t));
  let i = 0;
  while (i < film.scenes.length - 1 && film.scenes[i + 1].start <= t) i++;
  const s = film.scenes[i];
  const raw = clamp01((t - s.start) / s.dur);
  const p = s.ease(raw);
  const world = {};
  for (const k of ["nodes", "edges", "refs", "trees", "chips", "notes"]) {
    world[k] = mixGroup(s.from[k], s.to[k], p);
  }
  // Refs travel between nodes: interpolate between where each end node is now.
  for (const [id, r] of Object.entries(world.refs)) {
    const n0 = world.nodes[s.from.refs[id]?.at ?? s.to.refs[id]?.at];
    const n1 = world.nodes[s.to.refs[id]?.at ?? s.from.refs[id]?.at];
    r.x = lerp(n0.x, n1.x, p);
    r.y = lerp(n0.y, n1.y, p);
  }
  // A flash is an impulse: it peaks mid-scene and settles.
  const flash = s.to.flash.o > s.from.flash.o ? Math.sin(Math.PI * raw) : 0;
  const lines = [];
  for (let j = 0; j <= i; j++) {
    const sc = film.scenes[j];
    const n = sc.lines.length;
    sc.lines.forEach((l, k) => {
      const lead = n === 1 ? 0 : (k / n) * 0.7;
      const r = j < i ? 1 : raw;
      if (r < lead) return;
      const shown = clamp01((r - lead) / (l.kind === "cmd" ? 0.8 : 0.12));
      lines.push({ ...l, shown, at: sc.start + lead * sc.dur });
    });
  }
  return { world, lines, flash, caption: s.caption, captionTone: s.captionTone, chapter: s.chapter, t };
}

// ---------------------------------------------------------------------------------
// Paint: frame → SVG

// A part's id is its kind and key, `commit:sq` or `ref:main`; the registry declares these
// kinds as the widget's part prefixes.
const PART_KIND = { node: "commit", ref: "ref", tree: "tree", chip: "hook" };

// The terminal is 48 columns of 14px mono; a longer line ends in an ellipsis.
const fit = (text, cols = 48) => (text.length > cols ? `${text.slice(0, cols - 1)}…` : text);

const describe = (g, label, info) => {
  g.dataset.label = label;
  g.dataset.info = info ?? "";
};

// A commit and everything it descends from, following the edges visible in this frame.
function lineage(world, id) {
  const seen = new Set([id]);
  const queue = [id];
  while (queue.length) {
    const b = queue.pop();
    for (const e of Object.values(world.edges)) {
      if (e.b === b && e.o > 0.5 && !seen.has(e.a)) {
        seen.add(e.a);
        queue.push(e.a);
      }
    }
  }
  return seen;
}

const el = (tag, attrs = {}, parent) => {
  const node = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  parent?.append(node);
  return node;
};
const tone = (C, name) =>
  ({ main: C.main, feat: C.feat, squash: C.squash, ghost: C.faint, ok: C.ok, bad: C.bad, warn: C.warn, ink: C.ink, muted: C.muted })[
    name
  ] ?? C.ink;

// The part of the canvas drawn: the graph, the worktrees and the terminal.
const BOX = [36, 98, 1214, 502];

let painters = 0;

export class Painter {
  constructor(svg, palette) {
    this.svg = svg;
    this.setPalette(palette);
  }

  // A new palette rebuilds the drawing; the next paint fills it in.
  setPalette(palette) {
    this.C = palette;
    this.svg.replaceChildren();
    this.pool = new Map();
    this.#build();
  }

  #build() {
    const { svg, C } = this;
    svg.setAttribute("viewBox", BOX.join(" "));
    svg.setAttribute("xmlns", SVG);
    el("rect", { width: W, height: H, fill: C.bg }, svg);
    // Terminal panel.
    const termLayer = el("g", {}, svg);
    el("rect", { x: TERM.x, y: TERM.y, width: TERM.w, height: TERM.h, rx: 10, fill: C.term.bg, stroke: C.term.rule }, termLayer);
    const dots = el("g", {}, termLayer);
    ["#ff5f57", "#febc2e", "#28c840"].forEach((c, i) =>
      el("circle", { cx: TERM.x + 18 + i * 16, cy: TERM.y + 16, r: 5, fill: c, opacity: 0.8 }, dots),
    );
    this.termTitle = el("text", { x: TERM.x + TERM.w / 2, y: TERM.y + 20, "text-anchor": "middle", "font-family": MONO, "font-size": 12, fill: C.term.muted }, termLayer);
    this.term = el("g", { "font-family": MONO, "font-size": 14 }, termLayer);
    const clipId = `film-term-clip-${++painters}`;
    this.termClip = el("clipPath", { id: clipId }, el("defs", {}, svg));
    el("rect", { x: TERM.x, y: TERM.y + 32, width: TERM.w, height: TERM.h - 36 }, this.termClip);
    this.term.setAttribute("clip-path", `url(#${clipId})`);
    // Graph layers.
    this.edges = el("g", { fill: "none", "stroke-width": 3, "stroke-linecap": "round" }, svg);
    this.nodes = el("g", {}, svg);
    this.refs = el("g", { "font-family": MONO, "font-size": 13 }, svg);
    this.chips = el("g", { "font-family": MONO, "font-size": 14 }, svg);
    this.trees = el("g", { "font-family": MONO, "font-size": 14 }, svg);
    const defs = el("defs", {}, svg);
    this.arrowId = `film-arrow-${painters}`;
    const marker = el(
      "marker",
      { id: this.arrowId, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
      defs,
    );
    el("path", { d: "M0,0 L10,5 L0,10 z", fill: "context-stroke" }, marker);
    this.notes = el("g", { "font-family": SANS, "font-size": 14, "pointer-events": "none" }, svg);
    this.flash = el("rect", { width: W, height: H, fill: C.bad, opacity: 0, "pointer-events": "none" }, svg);
  }

  // Where a note's anchor is in this frame: a node's centre, or the top edge of a ref
  // pill, hook chip or worktree tile.
  #anchor(world, at) {
    if (typeof at === "object") return at;
    const [kind, id] = at.includes(":") ? at.split(":") : ["node", at];
    const g = this.pool.get(`${kind}:${id}`);
    if (kind === "node") {
      const n = world.nodes[id];
      return n && { x: n.x, y: n.y, r: n.r };
    }
    const box = g?.firstElementChild;
    if (!box) return null;
    const x = Number(box.getAttribute("x"));
    const y = Number(box.getAttribute("y"));
    const w = Number(box.getAttribute("width"));
    const h = Number(box.getAttribute("height"));
    return { x: x + w, y: y + h / 2, r: 4, left: x, top: y, w };
  }

  #paintNotes(world) {
    for (const [key, n] of Object.entries(world.notes)) {
      const g = this.keyed("note", key, () => {
        const g = el("g", {}, this.notes);
        el("path", { fill: "none", "stroke-width": 1.5 }, g);
        el("rect", { rx: 6, height: 26 }, g);
        el("text", {}, g);
        return g;
      });
      const [lead, box, text] = g.children;
      const C = this.C;
      const col = tone(C, n.tone);
      const to = this.#anchor(world, n.at);
      if (!to || n.o < 0.02) {
        g.setAttribute("opacity", 0);
        continue;
      }
      const w = n.text.length * 7.4 + 20;
      let lx;
      let ly;
      if (n.from) {
        // An arrow from where something was to where it is now, labelled at its peak.
        const from = this.#anchor(world, n.from) ?? to;
        // Above the lane by default; `below` keeps it clear of the ref pills and title.
        const dir = n.below ? 1 : -1;
        const mx = (from.x + to.x) / 2;
        const my = (dir > 0 ? Math.max(from.y, to.y) : Math.min(from.y, to.y)) + dir * 64;
        const pad = (to.r ?? 13) + 4;
        const ang = Math.atan2(to.y - my, to.x - mx);
        lead.setAttribute(
          "d",
          `M${from.x},${from.y + dir * ((from.r ?? 13) + 3)} Q${mx},${my} ${to.x - Math.cos(ang) * pad},${to.y - Math.sin(ang) * pad}`,
        );
        lead.setAttribute("marker-end", `url(#${this.arrowId})`);
        lead.setAttribute("stroke-dasharray", "none");
        lx = mx - w / 2;
        ly = dir > 0 ? my - 18 : my - 8;
      } else {
        // A label set off to one side, with a short leader to its anchor.
        const r = (to.r ?? 13) + 4;
        const off = {
          up: [-w / 2, -r - 40],
          right: [r + 16, -13],
          "down-left": [-w / 2 - 10, r + 34],
        }[n.side];
        lx = to.x + off[0];
        ly = to.y + off[1];
        const ex = Math.max(lx, Math.min(to.x, lx + w));
        const ey = Math.max(ly, Math.min(to.y, ly + 26));
        const sx = to.x + Math.sign(ex - to.x) * (n.side === "up" ? 0 : r - 2);
        const sy = to.y + (n.side === "up" ? -r + 2 : n.side === "down-left" ? r - 2 : 0);
        lead.setAttribute("d", `M${sx},${sy} L${ex},${ey}`);
        lead.removeAttribute("marker-end");
        lead.setAttribute("stroke-dasharray", "3 3");
      }
      lx = Math.max(BOX[0] + 12, Math.min(lx, TERM.x - w - 12));
      lead.setAttribute("stroke", col);
      // An arrow with no words is drawn alone.
      if (n.text) box.removeAttribute("visibility");
      else box.setAttribute("visibility", "hidden");
      box.setAttribute("x", lx);
      box.setAttribute("y", ly);
      box.setAttribute("width", w);
      box.setAttribute("fill", C.bg);
      box.setAttribute("stroke", col);
      text.setAttribute("x", lx + 10);
      text.setAttribute("y", ly + 18);
      text.setAttribute("fill", col);
      text.textContent = n.text;
      g.setAttribute("opacity", n.o);
    }
  }

  keyed(layer, key, make) {
    const id = `${layer}:${key}`;
    let node = this.pool.get(id);
    if (!node) {
      node = make();
      this.pool.set(id, node);
    }
    node.dataset.seen = this.stamp;
    return node;
  }

  // Parts are the things a viewer can point at: every commit, ref, worktree and hook
  // chip visible in this frame, keyed `kind:id`. Ghosts left by a rebase are not parts.
  parts() {
    const out = [];
    for (const [key, element] of this.pool) {
      const [layer, id] = key.split(":");
      const kind = PART_KIND[layer];
      if (!kind || id.includes("~") || Number(element.getAttribute("opacity")) < 0.3) continue;
      out.push({ id: `${kind}:${id}`, element, label: element.dataset.label, info: element.dataset.info });
    }
    return out;
  }

  paint(film, fr, focus = null) {
    const C = this.C;
    this.stamp = String(Math.random());
    const { world } = fr;
    const lit = focus ? lineage(world, focus) : null;
    const dim = (id, o) => (lit && !lit.has(id) ? o * 0.22 : o);
    this.termTitle.textContent = `${film.scenario.worktree} — zsh`;
    this.flash.setAttribute("opacity", 0.14 * fr.flash);

    for (const [key, e] of Object.entries(world.edges)) {
      const a = world.nodes[e.a];
      const b = world.nodes[e.b];
      if (!a || !b) continue;
      const path = this.keyed("edge", key, () => el("path", {}, this.edges));
      const mx = (a.x + b.x) / 2;
      path.setAttribute("d", `M${a.x},${a.y} C${mx},${a.y} ${mx},${b.y} ${b.x},${b.y}`);
      path.setAttribute("stroke", tone(C, e.tone));
      path.setAttribute(
        "opacity",
        lit && !(lit.has(e.a) && lit.has(e.b)) ? 0.08 * e.o : Math.min(e.o, a.o + 0.2, b.o + 0.2),
      );
      path.setAttribute("stroke-dasharray", e.dash > 0.5 ? "6 7" : "none");
    }
    for (const [key, n] of Object.entries(world.nodes)) {
      const g = this.keyed("node", key, () => {
        const g = el("g", {}, this.nodes);
        el("circle", {}, g);
        el("text", { "text-anchor": "middle", "font-family": MONO, "font-size": 12, fill: this.C.muted }, g);
        el("text", { "text-anchor": "middle", "font-family": MONO, "font-size": 11, "font-weight": 700 }, g);
        return g;
      });
      const [circle, hash, inner] = g.children;
      const c = tone(C, n.tone);
      circle.setAttribute("cx", n.x);
      circle.setAttribute("cy", n.y);
      circle.setAttribute("r", n.r);
      circle.setAttribute("fill", n.wip > 0.5 ? C.bg : c);
      circle.setAttribute("stroke", n.merge ? C.ink : c);
      circle.setAttribute("stroke-width", n.wip > 0.5 ? 2.5 : n.merge ? 3 : 0);
      circle.setAttribute("stroke-dasharray", n.wip > 0.5 ? "4 4" : "none");
      hash.setAttribute("x", n.x);
      hash.setAttribute("y", n.y + (n.y < (MAIN_Y + FEAT_Y) / 2 ? 36 : 36));
      hash.textContent = n.hash ?? "";
      inner.setAttribute("x", n.x);
      inner.setAttribute("y", n.y + 4);
      inner.setAttribute("fill", C.bg);
      inner.textContent = n.msg?.includes("→") ? n.msg : "";
      g.setAttribute("opacity", dim(key, n.o));
      describe(g, `commit ${n.hash}`, n.info);
    }
    for (const [key, r] of Object.entries(world.refs)) {
      const g = this.keyed("ref", key, () => {
        const g = el("g", {}, this.refs);
        el("rect", { rx: 5, height: 24 }, g);
        el("text", { "text-anchor": "middle" }, g);
        return g;
      });
      const [rect, text] = g.children;
      const w = r.label.length * 8.2 + 20;
      const y = r.side < 0 ? r.y - 58 : r.y + 50 + (r.side - 1) * 34;
      rect.setAttribute("x", r.x - w / 2);
      rect.setAttribute("y", y);
      rect.setAttribute("width", w);
      rect.setAttribute("fill", C.panel2);
      rect.setAttribute("stroke", tone(C, r.tone));
      text.setAttribute("x", r.x);
      text.setAttribute("y", y + 17);
      text.setAttribute("fill", tone(C, r.tone));
      text.textContent = r.label;
      g.setAttribute("opacity", r.o);
      describe(g, `ref ${r.label}`, r.info);
    }
    for (const [key, c] of Object.entries(world.chips)) {
      const g = this.keyed("chip", key, () => {
        const g = el("g", {}, this.chips);
        el("rect", { rx: 8, height: 40 }, g);
        el("rect", { rx: 2, height: 4 }, g);
        el("text", {}, g);
        return g;
      });
      const [box, bar, text] = g.children;
      const w = Math.max(250, c.label.length * 8.6 + 32);
      const col = c.state === "fail" ? C.bad : c.state === "ok" ? C.ok : c.state === "bg" ? C.muted : C.warn;
      box.setAttribute("x", c.x);
      box.setAttribute("y", c.y);
      box.setAttribute("width", w);
      box.setAttribute("fill", C.panel2);
      box.setAttribute("stroke", col);
      bar.setAttribute("x", c.x + 12);
      bar.setAttribute("y", c.y + 30);
      bar.setAttribute("width", (w - 24) * c.p);
      bar.setAttribute("fill", col);
      text.setAttribute("x", c.x + 16);
      text.setAttribute("y", c.y + 22);
      text.setAttribute("fill", col);
      text.textContent = (c.state === "run" ? "◎ " : c.state === "bg" ? "◌ " : "") + c.label;
      g.setAttribute("opacity", c.o);
      describe(g, c.label.replace(/ [✓]$/, ""), c.info);
    }
    for (const [key, tr] of Object.entries(world.trees)) {
      const g = this.keyed("tree", key, () => {
        const g = el("g", {}, this.trees);
        el("rect", { rx: 10, width: 330, height: 64 }, g);
        el("text", {}, g);
        el("text", { "font-size": 12 }, g);
        return g;
      });
      const [box, path, meta] = g.children;
      const bx = GRAPH_X - 20 + tr.i * 350;
      const by = 520 + (tr.gone ? 12 * (1 - tr.o) : 0);
      box.setAttribute("x", bx);
      box.setAttribute("y", by);
      box.setAttribute("fill", C.panel);
      box.setAttribute("stroke", tr.here > 0.5 ? C.main : C.rule);
      path.setAttribute("x", bx + 16);
      path.setAttribute("y", by + 26);
      path.setAttribute("fill", C.ink);
      path.textContent = `▣ ${tr.path}`;
      meta.setAttribute("x", bx + 16);
      meta.setAttribute("y", by + 48);
      meta.setAttribute("fill", tr.dirty > 0.5 ? C.warn : C.muted);
      meta.textContent =
        `[${tr.branch}]` +
        (tr.note ? `  ⚠ ${tr.note}` : tr.dirty > 0.5 ? `  ● ${Math.round(tr.dirty)} uncommitted` : "  clean") +
        (tr.here > 0.5 ? "  ← you are here" : "");
      meta.setAttribute("fill", tr.note ? C.bad : tr.dirty > 0.5 ? C.warn : C.muted);
      g.setAttribute("opacity", tr.o);
      describe(g, `worktree ${tr.path}`, tr.info);
    }
    for (const [id, node] of this.pool) {
      if (node.dataset.seen !== this.stamp) {
        node.remove();
        this.pool.delete(id);
      }
    }

    // Terminal: the last rows, the newest line typing in.
    this.term.replaceChildren();
    const rows = fr.lines.slice(-TERM.rows);
    rows.forEach((l, i) => {
      const y = TERM.y + 56 + i * TERM.line;
      const link = el("a", {}, this.term);
      link.dataset.at = l.at;
      const text = el("text", { x: TERM.x + 18, y, fill: C.term[l.tone] ?? C.term.ink }, link);
      if (l.kind === "cmd") {
        const typed = fit(l.text, 46).slice(0, Math.round(fit(l.text, 46).length * l.shown));
        text.textContent = `$ ${typed}${l.shown < 1 ? "▍" : ""}`;
      } else {
        // SVG collapses leading spaces; indentation is part of wt's output format.
        text.textContent = fit(l.text).replace(/^ +/, (m) => String.fromCharCode(160).repeat(m.length));
        text.setAttribute("opacity", l.shown);
      }
    });

    this.#paintNotes(world);
  }
}
