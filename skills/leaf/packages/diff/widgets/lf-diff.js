/* lf-diff uses Pierre's static renderer rather than hydrating Pierre's custom
 * element. Its ordinary DOM can live in Leaf's declared shadow root, so the
 * same rendered lines support selection anchors and script-free export. */
import {
  DISCLOSE,
  actionAvailable,
  announce,
  dataBody,
  failSoft,
  focused,
  inChrome,
  commands,
  langForPath,
  layoutChanged,
  loadDataFragment,
  offer,
  paintKeys,
  projectData,
  relabel,
  scrollBehavior,
  sendAction,
  settle,
  shadowStage,
  standingState,
  notice,
  watchActions,
  watchData,
} from "/runtime/widget-api.js";
// Pierre's renderer is by far the largest thing a Leaf page can pull, and only a diff
// that is actually rendering has any use for it — an authored <lf-diff> bound to data
// that has not arrived yet does not. So it is imported on first use rather than at
// module load: the page pays for the renderer when it draws a diff, and a version whose
// diff has been taken back out stops paying on the next load. The promise is kept, so
// every later file, every other diff on the page, and every re-render share one import.
let renderer = null;
const pierre = () => (renderer ??= import("/vendor/pierre-diffs.esm.js"));

const OPTIONS = Object.freeze({
  diffStyle: "unified",
  diffIndicators: "classic",
  disableLineNumbers: false,
  disableFileHeader: true,
  hunkSeparators: "line-info-basic",
  lineDiffType: "word-alt",
  overflow: "scroll",
  theme: { light: "github-light", dark: "github-dark" },
});

// Pierre's two fixed Shiki themes are reduced to the same small role vocabulary
// lf-code uses. The diff geometry and inline spans remain Pierre's; Leaf's theme
// keeps syntax ink consistent across the two code surfaces.
const TOKEN_ROLES = new Map([
  ["#6A737D/#6A737D", "cm"],
  ["#D73A49/#F97583", "kw"],
  ["#032F62/#9ECBFF", "st"],
  ["#032F62/#DBEDFF", "st"],
  ["#005CC5/#79B8FF", "nu"],
  ["#6F42C1/#B392F0", "fn"],
  ["#22863A/#85E89D", "ty"],
  ["#E36209/#FFAB70", "ty"],
  ["#B31D28/#FDAEB7", "kw"],
]);

function adoptSyntaxRoles(root) {
  for (const token of root.querySelectorAll("[style*='--diffs-token-light']")) {
    const light = token.style
      .getPropertyValue("--diffs-token-light")
      .trim()
      .toUpperCase();
    const dark = token.style
      .getPropertyValue("--diffs-token-dark")
      .trim()
      .toUpperCase();
    const role = TOKEN_ROLES.get(`${light}/${dark}`);
    token.style.removeProperty("--diffs-token-light");
    token.style.removeProperty("--diffs-token-dark");
    if (!token.style.length) token.removeAttribute("style");
    if (role) token.dataset.lfSyn = role;
  }
}

const changeCounts = (file) =>
  Number.isInteger(file.additions) && Number.isInteger(file.deletions)
    ? { adds: file.additions, dels: file.deletions }
    : file.hunks.reduce(
        (counts, hunk) => ({
          adds: counts.adds + hunk.additionLines,
          dels: counts.dels + hunk.deletionLines,
        }),
        { adds: 0, dels: 0 },
      );

// Each record carries the index of the hunk it came out of. A hunk is the unit a
// reviewer actually moves in — one `@@` header is one place the author changed
// something — and it is knowable only here, where the parse is still grouped; the
// rendered rows are a flat run with the separator chrome between them, so recovering
// the grouping from the DOM afterwards would be reading a rendering for a fact the
// parse already had. It rides on the same record the anchor coordinate is read off,
// and `lineKey` names only the four fields that make a comment's coordinate, so a row
// knowing which hunk it is in changes no anchor.
function sourceLines(file) {
  const lines = [];
  for (const [hunk, chunk] of file.hunks.entries()) {
    let oldLine = chunk.deletionStart;
    let newLine = chunk.additionStart;
    for (const part of chunk.hunkContent) {
      if (part.type === "context") {
        for (let index = 0; index < part.lines; index++) {
          lines.push({ path: file.name, hunk, side: "both", oldLine, newLine });
          oldLine++;
          newLine++;
        }
        continue;
      }
      if (part.type !== "change")
        throw new Error(`unsupported ${part.type} line in ${file.name}`);
      for (let index = 0; index < part.deletions; index++)
        lines.push({ path: file.name, hunk, side: "old", oldLine: oldLine++ });
      for (let index = 0; index < part.additions; index++)
        lines.push({ path: file.name, hunk, side: "new", newLine: newLine++ });
    }
  }
  return lines;
}

// The first rendered row of each hunk: the places `]` and `[` land. Read off the
// records rather than counted in the DOM, so an unloaded file simply has none.
const hunkHeads = (entry) =>
  (entry.lines ?? []).filter(
    (line, index) => index === 0 || line.hunk !== entry.lines[index - 1].hunk,
  );

const lineKey = ({ path, side, oldLine, newLine }) =>
  JSON.stringify(
    side === "both"
      ? [path, side, oldLine, newLine]
      : [path, side, side === "old" ? oldLine : newLine],
  );

const lineLabel = ({ path, side, oldLine, newLine }) => {
  const file = path || "(unnamed file)";
  if (side === "old") return `${file} · old line ${oldLine}`;
  if (side === "new") return `${file} · new line ${newLine}`;
  return `${file} · old line ${oldLine} · new line ${newLine}`;
};

function renderedLines(file, rendered) {
  const records = sourceLines(file);
  const nodes = [...rendered.querySelectorAll("[data-content] [data-line]")];
  if (nodes.length !== records.length)
    throw new Error(
      `Pierre returned ${nodes.length} source lines for ${file.name}; expected ${records.length}`,
    );
  return records.map((record, index) => {
    const node = nodes[index];
    const type =
      record.side === "both"
        ? "context"
        : record.side === "old"
          ? "change-deletion"
          : "change-addition";
    const shown = record.side === "old" ? record.oldLine : record.newLine;
    const alternate = record.side === "both" ? record.oldLine : null;
    if (
      node.dataset.lineType !== type ||
      node.dataset.line !== String(shown) ||
      (alternate !== null && node.dataset.altLine !== String(alternate))
    )
      throw new Error(`Pierre returned an unexpected source line for ${file.name}`);
    return { ...record, node };
  });
}

function summaryNode(file, open) {
  const details = document.createElement("details");
  details.open = open;
  const summary = document.createElement("summary");
  const path = file.name || "(unnamed file)";
  const { adds, dels } = changeCounts(file);
  const stat = Object.assign(document.createElement("span"), {
    className: "lf-diff-stat",
    textContent: `+${adds} −${dels}`,
  });
  stat.dataset.lfGen = "1";
  summary.append(
    Object.assign(document.createElement("span"), {
      className: "lf-diff-path",
      textContent: path,
    }),
    stat,
  );
  commands(summary, "On a diff", [
    {
      id: "diff.toggle",
      keys: () => DISCLOSE(summary),
      does: () => `${details.open ? "Hide" : "Show"} that file's diff`,
      line: () => `${details.open ? "hide" : "show"} this file`,
    },
  ]);
  details.append(summary);
  return details;
}

// A file's row and its review press. The press cannot go inside the <summary>: a
// disclosure is itself a control, and a control nested in one is announced as a single
// thing — the serious `nested-interactive` finding the corpus's axe sweep reports, once
// per file. They are siblings in this wrapper instead, the press first, and theme.css
// draws it back onto the summary line. First because the line pins: the summary sticks
// under the banner while its rows go past, and the press sticks with it only as a box
// in the flow ahead of the disclosure, since a box placed against the file's top would
// stay there and drift off the header it belongs to.
function fileRow(row) {
  const file = document.createElement("div");
  file.className = "lf-diff-file";
  file.append(row);
  return file;
}

function reviewButton(entry, changed) {
  const button = offer("button", "lf-btn lf-diff-review");
  button.addEventListener("click", () => changed(entry, !entry.reviewed));
  return button;
}

// The soft-wrap switch is a native checkbox and the theme reads it with `:has()`, the
// same bargain lf-shot strikes: the state is the control, so a copy with its scripts
// dropped still wraps and unwraps, and no second store can disagree with what the box
// says. It stands ahead of the file rows in the shadow tree because the rule that reads
// it is a sibling combinator — the switch is the only thing every file's lines can be
// addressed from without naming a widget or hoisting the state onto the host.
function wrapSwitch() {
  const label = offer("label", "lf-diff-wrap-label");
  const box = offer("input", "lf-diff-wrap");
  box.type = "checkbox";
  // The words beside the control are its accessible name (WCAG Label in Name); the
  // label element supplies them, so nothing here restates them as an aria-label.
  label.append(box, "Soft wrap");
  // A toggle moves no focus, so nothing else would repaint the word this press changes.
  box.addEventListener("change", paintKeys);
  return { node: label, box };
}

function reviewTools(host) {
  const tools = offer("div", "lf-diff-tools");
  const label = offer("label", "lf-diff-search-label");
  const search = document.createElement("input");
  search.type = "search";
  search.className = "lf-diff-search";
  search.placeholder = "Filter files";
  search.setAttribute("aria-label", "Filter diff files");
  search.addEventListener("input", () => host.filterFiles(search.value));
  label.append(search);
  const progress = document.createElement("span");
  progress.className = "lf-diff-progress";
  progress.dataset.lfGen = "1";
  const next = offer("button", "lf-btn lf-diff-next", "Next unreviewed");
  next.addEventListener("click", () => settle(host.nextUnreviewed()));
  const wrap = wrapSwitch();
  tools.append(label, progress, wrap.node, next);
  return { node: tools, search, progress, next, wrap: wrap.box };
}

function renameNode(file) {
  const row = document.createElement("div");
  row.className = "lf-diff-rename";
  row.dataset.lfGen = "1";
  row.append(
    Object.assign(document.createElement("span"), {
      className: "lf-diff-path lf-diff-before",
      textContent: file.prevName,
    }),
    Object.assign(document.createElement("span"), {
      className: "lf-diff-arrow",
      textContent: " → ",
    }),
    Object.assign(document.createElement("span"), {
      className: "lf-diff-path lf-diff-after",
      textContent: file.name,
    }),
    Object.assign(document.createElement("span"), {
      className: "lf-diff-stat",
      textContent: "renamed",
    }),
  );
  return row;
}

function headerPath(side, path) {
  return path.startsWith('"') && path.endsWith('"')
    ? `"${side}/${path.slice(1)}`
    : `${side}/${path}`;
}

function pathOnlyRenames(source) {
  return source
    .split(/(?=^diff --git )/m)
    .filter((section) => section.startsWith("diff --git "))
    .flatMap((section) => {
      const lines = section.replace(/\n+$/, "").split("\n");
      if (lines.length !== 4 || lines[1] !== "similarity index 100%") return [];
      const prevName = /^rename from (.+)$/.exec(lines[2])?.[1];
      const name = /^rename to (.+)$/.exec(lines[3])?.[1];
      if (
        !prevName ||
        !name ||
        prevName === '""' ||
        name === '""' ||
        lines[0] !== `diff --git ${headerPath("a", prevName)} ${headerPath("b", name)}`
      )
        return [];
      return [{ prevName, name }];
    });
}

async function renderFile(file, sharedStyles, open) {
  const { preloadDiffHTML } = await pierre();
  file.lang = langForPath(file.name) ?? "text";
  const template = document.createElement("template");
  template.innerHTML = await preloadDiffHTML({ fileDiff: file, options: OPTIONS });
  const rendered = template.content;

  // The static rendering has no Pierre interaction manager, so its unused icon sprite
  // goes. Line numbers and separator wording are useful chrome, but not source a comment
  // can quote; the source lines and file path remain in the reading.
  rendered.querySelector("svg[data-icon-sprite]")?.remove();
  for (const number of rendered.querySelectorAll("[data-line-number-content]")) {
    number.classList.add("lf-ui");
    number.dataset.lfGen = "1";
    number.setAttribute("aria-hidden", "true");
  }
  for (const separator of rendered.querySelectorAll("[data-separator]"))
    separator.classList.add("lf-ui");
  for (const style of [...rendered.children].filter(
    (child) => child.localName === "style",
  )) {
    const kind = style.hasAttribute("data-core-css") ? "core" : "theme";
    if (!sharedStyles.has(kind)) sharedStyles.set(kind, style);
    else style.remove();
  }
  adoptSyntaxRoles(rendered);

  const pre = rendered.querySelector("pre");
  if (!pre) throw new Error(`Pierre returned no diff for ${file.name || "a file"}`);
  const viewport = pre.querySelector("code[data-code]") ?? pre;
  viewport.setAttribute("role", "region");
  viewport.setAttribute("aria-label", file.name || "diff");

  const details = summaryNode(file, open);
  const lines = renderedLines(file, rendered);
  details.append(rendered);
  return { node: details, lines };
}

async function parsedFiles(source) {
  if (/^copy (?:from|to) /m.test(source))
    throw new Error(
      "unsupported copy diff (copy entries belong in prose; omit " +
        "copy metadata and use textual @@ hunks for an edited destination)",
    );
  const { parsePatchFiles } = await pierre();
  const files = parsePatchFiles(source, undefined, true).flatMap(
    (patch) => patch.files,
  );
  if (!files.length) throw new Error("empty diff");
  const pureRenames = files.filter((file) => file.type === "rename-pure");
  const sourceRenames = pathOnlyRenames(source);
  if (
    sourceRenames.length !== pureRenames.length ||
    sourceRenames.some(
      (rename, index) =>
        rename.prevName !== pureRenames[index].prevName ||
        rename.name !== pureRenames[index].name,
    )
  )
    throw new Error(
      "unsupported hunkless rename (only an exact path-only block with " +
        "diff --git, similarity index 100%, rename from, and rename to " +
        "lines may omit textual @@ hunks)",
    );
  for (const file of files)
    if (!file.hunks.length && file.type !== "rename-pure")
      throw new Error(
        `unsupported hunkless diff for ${file.name || "a file"} ` +
          "(only path-only renames may omit @@ hunks; binary, mode-only, " +
          "and empty added/deleted entries belong in prose; changed files " +
          "need textual @@ hunks)",
      );
  return files;
}

function fragmentError(details, error) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.dataset.lfGen = "1";
  box.textContent = `That file's diff failed to load: ${error?.message || error}`;
  details.replaceChildren(details.firstElementChild, box);
}

customElements.define(
  "lf-diff",
  class extends HTMLElement {
    connectedCallback() {
      this.stopActions ??= watchActions(this, null, this.paintReviewAvailability);
      if (this.stopWatching) return;
      // A page diff's file header pins under the banner; one an agent sent in a reply
      // scrolls inside the panel's own list, whose pinned slot already belongs to the
      // run headings. The theme cannot ask that question from inside a shadow tree, so
      // the module answers it once with the layer's own predicate and paints the answer.
      if (!inChrome(this)) this.dataset.lfDiffPinned = "";
      if (!this.reviewKeys) {
        this.reviewKeys = commands(
          this,
          "In a diff review",
          [
            // The walk leads the scope, because the key line's shortlist is its first
            // two live rows and moving is what a reader standing on a diff row does
            // next: the line used to open with "filter files", which is the press for
            // someone who has not started reading yet. The rest of the scope is one `?`
            // away in the shelf and complete in the reference.
            //
            // `]` and `[` are the reviewer's own step, and `}` and `{` the same step one
            // unit out. Bracket pairs because that is what an editor and a review tool
            // already spell this walk with, and punctuation spends none of the page's
            // small alphabet: these live in the diff's own scope and answer only while
            // the reader is standing in it.
            {
              id: "diff.next-hunk",
              keys: ["]"],
              does: "Go to the next hunk",
              line: "next hunk",
              when: () => this.hasHunks(),
              run: () => settle(this.stepHunk(false)),
            },
            {
              id: "diff.previous-hunk",
              keys: ["["],
              does: "Go to the previous hunk",
              line: "previous hunk",
              when: () => this.hasHunks(),
              run: () => settle(this.stepHunk(true)),
            },
            {
              id: "diff.next-file",
              keys: ["}"],
              does: "Go to the next file's header",
              line: "next file",
              when: () => this.shownEntries().length > 1,
              run: () => this.stepFile(false),
            },
            {
              id: "diff.previous-file",
              keys: ["{"],
              does: "Go to the previous file's header",
              line: "previous file",
              when: () => this.shownEntries().length > 1,
              run: () => this.stepFile(true),
            },
            // The mode, not the toggle: `does` and `line` say which way this press will
            // go. The press is the switch's own activation rather than a second route to
            // the same effect, so the box the theme reads stays the one place the state
            // lives. Alt+w rather than a bare letter, matching the row below it: a bare
            // `w` here would shadow the page's own narrowing for as long as a reader
            // stood anywhere in a patch.
            {
              id: "diff.wrap",
              keys: ["Alt+w"],
              does: () =>
                this.wrapped() ? "Show long lines unwrapped" : "Wrap long lines",
              line: () => (this.wrapped() ? "stop wrapping" : "wrap long lines"),
              run: () => this.reviewTools?.wrap.click(),
            },
            {
              id: "diff.search",
              keys: ["/"],
              does: "Filter the files in this diff",
              line: "filter files",
              returnFrame: () => ({
                active: () => {
                  const search = this.reviewTools?.search;
                  const held = focused();
                  const inDiff =
                    this.contains(held) || Boolean(this.shadowRoot?.contains(held));
                  return Boolean(
                    search &&
                    inDiff &&
                    (search.value || this.reviewTools.node.contains(held)),
                  );
                },
                close: () => {
                  const search = this.reviewTools?.search;
                  if (search?.value) {
                    this.clearFilter();
                    search.focus({ preventScroll: true });
                    return false;
                  }
                  search?.blur();
                },
                does: () =>
                  this.reviewTools?.search.value
                    ? "Show every file again"
                    : "Leave the diff filter",
                line: () =>
                  this.reviewTools?.search.value ? "show all files" : "back",
              }),
              run: () => this.reviewTools?.search.focus(),
            },
            {
              id: "diff.next-unreviewed",
              keys: ["Alt+ArrowDown"],
              does: "Open the next unreviewed matching file",
              line: "next unreviewed file",
              when: () => this.nextReviewEntry() !== null,
              run: () => settle(this.nextUnreviewed()),
            },
          ],
          () => Boolean(this.fileEntries?.length),
        );
      }
      const bound = this.hasAttribute("source");
      if (!bound) {
        if (this.classList.contains("lf-rendered")) return;
        if (this.inlineSource === undefined)
          this.inlineSource = dataBody(this).replace(/^\n+/, "").replace(/\n$/, "");
        settle(this.render(this.inlineSource, false));
        return;
      }
      let first = true;
      this.stopWatching = watchData(this, "document", (snapshot) => {
        const source = snapshot?.value ?? null;
        const stamp = snapshot
          ? `${snapshot.snapshot ? "snapshot" : "current"}:${snapshot.revision}`
          : null;
        if (this.boundStamp === stamp) return this.boundRendering ?? Promise.resolve();
        this.boundStamp = stamp;
        const rendering = this.render(source, true, snapshot?.origin);
        this.boundRendering = rendering;
        rendering.finally(() => {
          if (this.boundRendering === rendering) this.boundRendering = null;
        });
        if (first) {
          settle(rendering);
          first = false;
        }
        return rendering;
      });
    }

    disconnectedCallback() {
      this.stopActions?.();
      this.stopActions = null;
      this.rendering = (this.rendering ?? 0) + 1;
      this.stopWatching?.();
      this.stopWatching = null;
      this.headRoom?.disconnect();
      this.headRoom = null;
      this.boundStamp = undefined;
      this.boundRendering = null;
      this.manifestEntries = null;
      this.sharedStyles = null;
    }

    async render(source, bound, origin = null) {
      const rendering = (this.rendering ?? 0) + 1;
      this.rendering = rendering;
      try {
        if (source === null) {
          this.manifestEntries = null;
          this.fileEntries = null;
          this.sharedStyles = null;
          this.reviewTools = null;
          this.replaceChildren();
          shadowStage(this, []);
          projectData(
            this,
            [],
            () => "",
            () => null,
            { nested: true },
          );
          this.classList.remove("lf-rendered");
          return;
        }
        if (bound && typeof source === "object") {
          await this.renderManifest(source, rendering, origin);
          return;
        }
        if (typeof source !== "string")
          throw new Error("diff data must be unified patch text or a file manifest");
        this.manifestEntries = null;
        this.sharedStyles = null;
        // Strict parsing keeps a malformed hunk from becoming incomplete evidence.
        const files = await parsedFiles(source);
        const sharedStyles = new Map();
        const rendered = [];
        const open = !this.hasAttribute("collapsed");
        for (const file of files)
          rendered.push(
            file.type === "rename-pure"
              ? { node: renameNode(file), lines: [] }
              : await renderFile(file, sharedStyles, open),
          );
        if (rendering !== this.rendering || !this.isConnected) return;
        const entries = rendered.map((renderedFile, index) => ({
          ...renderedFile,
          record: {
            path: files[index].name,
            ...(files[index].prevName ? { previousPath: files[index].prevName } : {}),
          },
          node: fileRow(renderedFile.node),
          details: renderedFile.node.matches("details") ? renderedFile.node : null,
          loaded: true,
          reviewed: false,
          filtered: false,
        }));
        if (bound) for (const { node } of entries) node.dataset.lfGen = "1";
        this.fileEntries = entries;
        this.reviewTools = reviewTools(this);
        for (const entry of entries) this.attachReview(entry);
        this.refreshReviewedState();
        this.replaceChildren();
        shadowStage(this, [
          ...sharedStyles.values(),
          this.reviewTools.node,
          ...entries.map(({ node }) => node),
        ]);
        if (bound)
          projectData(
            this,
            entries.flatMap(({ lines }) => lines),
            lineKey,
            ({ node }) => node,
            { nested: true, labelOf: lineLabel, originOf: () => origin },
          );
        this.paintHeadRoom();
        this.watchHeadRoom();
        this.classList.add("lf-rendered");
      } catch (err) {
        if (rendering !== this.rendering || !this.isConnected) return;
        this.manifestEntries = null;
        this.fileEntries = null;
        this.sharedStyles = null;
        this.reviewTools = null;
        this.classList.remove("lf-rendered");
        failSoft(this, err, source);
        if (this.shadowRoot) shadowStage(this, [...this.childNodes]);
        if (bound)
          projectData(
            this,
            [],
            () => "",
            () => null,
            { nested: true },
          );
      }
    }

    async renderManifest(source, rendering, origin) {
      if (!Array.isArray(source.files) || !source.files.length)
        throw new Error("empty diff manifest");
      const entries = [];
      const paths = new Set();
      const open = !this.hasAttribute("collapsed");
      for (const record of source.files) {
        if (
          !record ||
          typeof record !== "object" ||
          record.key !== record.path ||
          typeof record.path !== "string" ||
          !record.path ||
          paths.has(record.path)
        )
          throw new Error("diff manifest needs one unique path-keyed record per file");
        paths.add(record.path);
        if (record.kind === "rename") {
          if (typeof record.previousPath !== "string" || !record.previousPath)
            throw new Error(`rename ${record.path} needs its previous path`);
          entries.push({
            record,
            node: fileRow(
              renameNode({ prevName: record.previousPath, name: record.path }),
            ),
            lines: [],
            loaded: true,
            reviewed: false,
            filtered: false,
          });
          continue;
        }
        const details = summaryNode(
          {
            name: record.path,
            additions: record.additions,
            deletions: record.deletions,
          },
          open,
        );
        const entry = {
          record,
          node: fileRow(details),
          details,
          lines: [],
          loaded: false,
          failed: false,
          loading: null,
          reviewed: false,
          filtered: false,
        };
        details.addEventListener("toggle", () => {
          if (!details.open) return;
          entry.failed = false;
          settle(this.loadManifestEntry(entry));
        });
        entries.push(entry);
      }
      if (rendering !== this.rendering || !this.isConnected) return;
      for (const { node } of entries) node.dataset.lfGen = "1";
      this.manifestEntries = entries;
      this.manifestOrigin = origin;
      this.fileEntries = entries;
      this.sharedStyles = new Map();
      this.reviewTools = reviewTools(this);
      for (const entry of entries) this.attachReview(entry);
      this.refreshReviewedState();
      this.replaceChildren();
      this.stageManifest();
      this.projectManifest();
      this.paintHeadRoom();
      this.watchHeadRoom();
      this.classList.add("lf-rendered");
      if (open)
        await Promise.all(entries.map((entry) => this.loadManifestEntry(entry)));
    }

    stageManifest() {
      if (!this.manifestEntries) return;
      shadowStage(
        this,
        [
          ...this.sharedStyles.values(),
          this.reviewTools?.node,
          ...this.manifestEntries.map(({ node }) => node),
        ].filter(Boolean),
      );
    }

    projectManifest() {
      projectData(
        this,
        (this.manifestEntries ?? []).flatMap(({ lines }, index) =>
          lines.map((line) => ({
            ...line,
            origin: { ...this.manifestOrigin, path: ["files", index, "patch"] },
          })),
        ),
        lineKey,
        ({ node }) => node,
        { nested: true, labelOf: lineLabel, originOf: ({ origin }) => origin },
      );
    }

    async loadManifestEntry(entry) {
      if (entry.loaded) return;
      if (entry.loading) return entry.loading;
      const rendering = this.rendering;
      entry.loading = (async () => {
        try {
          const patch = await loadDataFragment(this, "document", entry.record.key);
          if (rendering !== this.rendering || !this.isConnected) return;
          if (typeof patch !== "string")
            throw new Error("the fragment is not unified patch text");
          const files = await parsedFiles(patch);
          if (files.length !== 1 || files[0].name !== entry.record.path)
            throw new Error(
              `the fragment for ${entry.record.path} does not contain that one file`,
            );
          const rendered = await renderFile(files[0], this.sharedStyles, true);
          if (rendering !== this.rendering || !this.isConnected) return;
          entry.details.replaceChildren(
            entry.details.firstElementChild,
            ...[...rendered.node.children].slice(1),
          );
          entry.lines = rendered.lines;
          entry.loaded = true;
          this.stageManifest();
          this.projectManifest();
        } catch (error) {
          if (rendering !== this.rendering || !this.isConnected) return;
          entry.failed = true;
          fragmentError(entry.details, error);
        } finally {
          entry.loading = null;
        }
      })();
      return entry.loading;
    }

    fileEntryForDatum(key) {
      if (!this.fileEntries) return null;
      let coordinate;
      try {
        coordinate = JSON.parse(key);
      } catch {
        return null;
      }
      if (!Array.isArray(coordinate) || typeof coordinate[0] !== "string") return null;
      return (
        this.fileEntries.find(({ record }) => record.path === coordinate[0]) ?? null
      );
    }

    // Core can place a standing line thread at its file disclosure before that file's
    // patch exists in the DOM. Navigation asks the second method to make the exact line
    // real, then the ordinary datum resolver and anchor painter take over.
    lfDataDatum(key) {
      const entry = this.fileEntryForDatum(key);
      if (!entry) return null;
      if (!entry.loaded || entry.filtered) return entry.node;
      const exact = entry.lines.find((line) => lineKey(line) === key);
      if (exact) return exact.node;
      let coordinate;
      try {
        coordinate = JSON.parse(key);
      } catch {
        return null;
      }
      const [, side, at] = coordinate;
      if (!Number.isInteger(at) || !["old", "new"].includes(side)) return null;
      const context = entry.lines.find(
        (line) =>
          line.side === "both" && (side === "old" ? line.oldLine : line.newLine) === at,
      );
      if (context) return context.node;
      if (side === "new") {
        const priorContext = entry.lines.find(
          (line) => line.side === "both" && line.oldLine === at,
        );
        if (priorContext) return priorContext.node;
      }
      // A non-removed call-tree item normally names the new side. Falling back to an
      // old coordinate preserves travel for analyzers whose location still names the
      // pre-change call site, without making callers understand diff coordinates.
      if (side === "new")
        return (
          entry.lines.find((line) => line.side === "old" && line.oldLine === at)
            ?.node ?? null
        );
      return null;
    }

    lfRevealDatum(key) {
      const entry = this.fileEntryForDatum(key);
      if (!entry) return null;
      if (entry.filtered) this.clearFilter();
      if (!entry.details || entry.loaded || entry.failed) return null;
      entry.details.open = true;
      return this.loadManifestEntry(entry);
    }

    async lfPrepareExport() {
      this.clearFilter();
      await Promise.all(
        (this.manifestEntries ?? []).map((entry) => this.loadManifestEntry(entry)),
      );
      // The filter, the count and the next-unreviewed press all need the module, so a
      // copy loses them. The wrap switch does not: it is a checkbox the theme reads, so
      // it goes on working in a file with its scripts dropped, and the tools row stays
      // to carry it — a copy of a patch is exactly where a reader has no other way to
      // see the end of a long line.
      const tools = this.reviewTools;
      tools?.search.closest("label")?.remove();
      tools?.progress.remove();
      tools?.next.remove();
      this.reviewTools = null;
      for (const entry of this.fileEntries ?? []) {
        if (!entry.reviewed) {
          entry.review.remove();
          continue;
        }
        const status = document.createElement("span");
        status.className = "lf-diff-reviewed";
        relabel(status, "✓ Reviewed", { says: true });
        entry.review.replaceWith(status);
        entry.review = status;
      }
    }

    attachReview(entry) {
      entry.review = reviewButton(entry, (target, reviewed) => {
        if (!actionAvailable(this, "review")) return;
        this.setReviewed(target, reviewed);
        sendAction(this, "review", {
          file: target.record.path,
          reviewed,
        }).then((ok) => {
          if (ok)
            notice(
              `${reviewed ? "Reviewed" : "Reopened"} ${target.record.path} — recorded`,
            );
          else this.refreshReviewedState();
        });
      });
      entry.node.prepend(entry.review);
      this.setReviewed(entry, false, { repaint: false });
      this.paintReviewAvailability();
    }

    paintReviewAvailability = () => {
      const available = actionAvailable(this, "review");
      for (const entry of this.fileEntries ?? [])
        if (entry.review instanceof HTMLButtonElement)
          entry.review.disabled = !available;
    };

    setReviewed(entry, reviewed, { repaint = true } = {}) {
      if (!entry) return;
      entry.reviewed = reviewed;
      entry.node.toggleAttribute("data-reviewed", reviewed);
      entry.review.setAttribute("aria-pressed", String(reviewed));
      entry.review.setAttribute(
        "aria-label",
        `Mark ${entry.record.path} ${reviewed ? "unreviewed" : "reviewed"}`,
      );
      relabel(entry.review, reviewed ? "✓ Reviewed" : "Mark reviewed", {
        says: reviewed,
      });
      if (repaint) this.refreshReviewTools();
    }

    refreshReviewedState() {
      if (!this.fileEntries) return;
      for (const entry of this.fileEntries)
        this.setReviewed(entry, false, { repaint: false });
      for (const state of standingState()) {
        if (state.widget !== this || state.action !== "review") continue;
        this.setReviewed(
          this.fileEntries.find(({ record }) => record.path === state.detail.file),
          state.detail.reviewed,
          { repaint: false },
        );
      }
      this.refreshReviewTools();
    }

    filterFiles(query) {
      const needle = query.trim().toLocaleLowerCase();
      for (const entry of this.fileEntries ?? []) {
        const paths = [entry.record.path, entry.record.previousPath ?? ""]
          .join("\n")
          .toLocaleLowerCase();
        entry.filtered = Boolean(needle && !paths.includes(needle));
        entry.node.classList.toggle("lf-diff-filtered", entry.filtered);
      }
      this.refreshReviewTools();
      layoutChanged(this);
    }

    clearFilter() {
      if (this.reviewTools) this.reviewTools.search.value = "";
      this.filterFiles("");
    }

    refreshReviewTools() {
      if (!this.reviewTools || !this.fileEntries) return;
      const shown = this.fileEntries.filter((entry) => !entry.filtered);
      const reviewed = this.fileEntries.filter((entry) => entry.reviewed).length;
      const suffix =
        shown.length === this.fileEntries.length ? "" : ` · ${shown.length} matching`;
      this.reviewTools.progress.textContent = `${reviewed} of ${this.fileEntries.length} reviewed${suffix}`;
      this.reviewTools.next.disabled = this.nextReviewEntry() === null;
      paintKeys();
    }

    wrapped() {
      return Boolean(this.reviewTools?.wrap.checked);
    }

    shownEntries() {
      return (this.fileEntries ?? []).filter((entry) => !entry.filtered);
    }

    hasHunks() {
      return this.shownEntries().some((entry) => entry.details);
    }

    // How much of the top a pinned file header covers, which is the one number the theme
    // cannot work out: a long path wraps, so the header's height is whatever it rendered
    // at, and on this corpus that is anything from one line to three. The thread list
    // writes the same fact under the same name for its own run headings; here it is read
    // as `scroll-margin-top` on the rows, so a landing arrives below the header rather
    // than behind it. Per file, because each header pins over its own rows and one
    // number for all of them would spend the widest path's wrap on every landing.
    paintHeadRoom() {
      for (const file of this.shadowRoot?.querySelectorAll("details") ?? [])
        file.style.setProperty(
          "--lf-head-room",
          `${file.querySelector("summary")?.offsetHeight ?? 0}px`,
        );
    }

    watchHeadRoom() {
      if (this.headRoom) return;
      this.headRoom = new ResizeObserver(() => this.paintHeadRoom());
      this.headRoom.observe(this);
    }

    // Where the reader stands inside this diff. A row, a header, or a control in the
    // tools row all answer; the walk only needs a node to compare document positions
    // against, and the tools row standing before every file is why a reader who has
    // touched nothing steps to the first hunk rather than nowhere.
    hereNode() {
      const focused = this.shadowRoot?.activeElement;
      return focused && this.shadowRoot.contains(focused) ? focused : null;
    }

    // With nothing focused inside the shadow tree — the host itself is focused, which
    // is where an in-page link to the diff's id lands — every hunk counts as beyond, in
    // either direction: `order` is already reversed for a backward step, so the walk
    // opens the last file and lands on its last hunk, the mirror of the first hunk
    // forward. Answering false there matched no hunk in any file, and the walk opened
    // and fetched every one of them to land nowhere.
    beyond(node, here, back) {
      if (!here) return true;
      const where = here.compareDocumentPosition(node);
      return Boolean(
        where &
        (back ? Node.DOCUMENT_POSITION_PRECEDING : Node.DOCUMENT_POSITION_FOLLOWING),
      );
    }

    async openEntry(entry) {
      if (!entry.details) return;
      entry.details.open = true;
      await this.loadManifestEntry(entry);
    }

    // The walk starts in the file the reader is standing in and goes on through the
    // ones after it, so a closed file is opened only once the step has actually reached
    // it: a reader on the last hunk of the third file loads the fourth and stops, rather
    // than every remaining file to discover there is nothing past them.
    async stepHunk(back) {
      const here = this.hereNode();
      const order = back ? [...this.shownEntries()].reverse() : this.shownEntries();
      const standing = here
        ? order.findIndex((entry) => entry.node.contains(here))
        : -1;
      for (let index = Math.max(standing, 0); index < order.length; index++) {
        const entry = order[index];
        await this.openEntry(entry);
        const heads = hunkHeads(entry);
        const head = (back ? [...heads].reverse() : heads).find((line) =>
          this.beyond(line.node, here, back),
        );
        if (!head) continue;
        this.land(head.node);
        announce(`${entry.record.path} · hunk ${head.hunk + 1} of ${heads.length}`);
        return;
      }
    }

    stepFile(back) {
      const here = this.hereNode();
      const order = back ? [...this.shownEntries()].reverse() : this.shownEntries();
      // The whole file is the unit, so a step out of one starts past it rather than at
      // its own header — and a reader standing in the tools row, which belongs to no
      // file, steps to the first (or, walking back, the last).
      const standing = here
        ? order.findIndex((entry) => entry.node.contains(here))
        : -1;
      const entry = order[standing + 1];
      if (!entry) return;
      this.reviewCursor = entry;
      // The box rather than the header, which is what the `g f` fold address settled for
      // the same shape: a header pinned to the banner is already where it is going, so
      // aligning it moves nothing, while aligning the file it heads starts the file at
      // its start. The header is still what takes the focus.
      this.land(entry.node, entry.details?.firstElementChild ?? entry.node);
      announce(entry.record.path);
    }

    // Arrival: scrolled to the band the document declares landable, which the pinned
    // header's own room has been added to, and then the focus without the browser
    // scrolling a second time. A row is not a tab stop — a patch is thousands of them —
    // so it is made focusable for the press that lands on it and wears the platform's
    // own ring, the same as every control the layer does not restyle. A file header
    // already is one, and writing a tabindex of -1 onto it would take it out of the
    // order a reader tabs through.
    land(box, node = box) {
      if (node.tabIndex < 0) node.tabIndex = -1;
      box.scrollIntoView({
        behavior: scrollBehavior(),
        block: "start",
        inline: "nearest",
      });
      node.focus({ preventScroll: true });
    }

    entryAroundFocus() {
      const focused = this.hereNode();
      const focusedEntry =
        this.fileEntries?.find(({ node }) => focused && node.contains(focused)) ?? null;
      if (focusedEntry) return focusedEntry;
      return this.fileEntries?.includes(this.reviewCursor) ? this.reviewCursor : null;
    }

    nextReviewEntry() {
      const entries = (this.fileEntries ?? []).filter(
        (entry) => !entry.filtered && !entry.reviewed,
      );
      if (!entries.length) return null;
      const current = this.entryAroundFocus();
      if (!current) return entries[0];
      const after = entries.find((entry) =>
        Boolean(
          current.node.compareDocumentPosition(entry.node) &
          Node.DOCUMENT_POSITION_FOLLOWING,
        ),
      );
      return after ?? entries[0];
    }

    async nextUnreviewed() {
      const entry = this.nextReviewEntry();
      if (!entry) return;
      this.reviewCursor = entry;
      if (entry.details) {
        entry.details.open = true;
        await this.loadManifestEntry(entry);
      }
      const target = entry.details?.firstElementChild ?? entry.review;
      target.scrollIntoView({ behavior: scrollBehavior(), block: "center" });
      target.focus({ preventScroll: true });
      notice(`Next unreviewed file: ${entry.record.path}`);
    }

    applyAction(action, detail) {
      if (action !== "review") return;
      this.setReviewed(
        this.fileEntries?.find(({ record }) => record.path === detail.file),
        detail.reviewed,
      );
    }
  },
);
