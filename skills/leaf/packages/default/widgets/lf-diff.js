/* lf-diff uses Pierre's static renderer rather than hydrating Pierre's custom
 * element. Its ordinary DOM can live in Leaf's declared shadow root, so the
 * same rendered lines support selection anchors and script-free export. */
import {
  DISCLOSE,
  dataBody,
  failSoft,
  keys,
  langForPath,
  projectData,
  settle,
  shadowStage,
  watchData,
} from "/runtime/widget-api.js";
import { parsePatchFiles, preloadDiffHTML } from "/vendor/pierre-diffs.esm.js";

const OPTIONS = Object.freeze({
  diffStyle: "unified",
  diffIndicators: "classic",
  disableLineNumbers: true,
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
  file.hunks.reduce(
    (counts, hunk) => ({
      adds: counts.adds + hunk.additionLines,
      dels: counts.dels + hunk.deletionLines,
    }),
    { adds: 0, dels: 0 },
  );

function sourceLines(file) {
  const lines = [];
  for (const hunk of file.hunks) {
    let oldLine = hunk.deletionStart;
    let newLine = hunk.additionStart;
    for (const part of hunk.hunkContent) {
      if (part.type === "context") {
        for (let index = 0; index < part.lines; index++) {
          lines.push({ path: file.name, side: "both", oldLine, newLine });
          oldLine++;
          newLine++;
        }
        continue;
      }
      if (part.type !== "change")
        throw new Error(`unsupported ${part.type} line in ${file.name}`);
      for (let index = 0; index < part.deletions; index++)
        lines.push({ path: file.name, side: "old", oldLine: oldLine++ });
      for (let index = 0; index < part.additions; index++)
        lines.push({ path: file.name, side: "new", newLine: newLine++ });
    }
  }
  return lines;
}

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

function summaryNode(file) {
  const details = document.createElement("details");
  details.open = true;
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
  keys(summary, "On a diff", [
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

async function renderFile(file, sharedStyles) {
  file.lang = langForPath(file.name) ?? "text";
  const template = document.createElement("template");
  template.innerHTML = await preloadDiffHTML({ fileDiff: file, options: OPTIONS });
  const rendered = template.content;

  // The static rendering has no Pierre interaction manager, so its unused icon
  // sprite and disabled line numbers go. Separator wording is useful chrome, but not
  // source a comment can quote; the source lines and file path remain in the reading.
  rendered.querySelector("svg[data-icon-sprite]")?.remove();
  for (const number of rendered.querySelectorAll("[data-line-number-content]"))
    number.remove();
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

  const details = summaryNode(file);
  const lines = renderedLines(file, rendered);
  details.append(rendered);
  return { node: details, lines };
}

customElements.define(
  "lf-diff",
  class extends HTMLElement {
    connectedCallback() {
      if (this.stopWatching) return;
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
        if (this.boundSource === source)
          return this.boundRendering ?? Promise.resolve();
        this.boundSource = source;
        const rendering = this.render(source, true);
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
      this.rendering = (this.rendering ?? 0) + 1;
      this.stopWatching?.();
      this.stopWatching = null;
      this.boundSource = undefined;
      this.boundRendering = null;
    }

    async render(source, bound) {
      const rendering = (this.rendering ?? 0) + 1;
      this.rendering = rendering;
      try {
        if (source === null) {
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
        if (/^copy (?:from|to) /m.test(source))
          throw new Error(
            "unsupported copy diff (copy entries belong in prose; omit " +
              "copy metadata and use textual @@ hunks for an edited destination)",
          );
        // Strict parsing keeps a malformed hunk from becoming incomplete evidence.
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
        const sharedStyles = new Map();
        const rendered = [];
        for (const file of files)
          rendered.push(
            file.type === "rename-pure"
              ? { node: renameNode(file), lines: [] }
              : await renderFile(file, sharedStyles),
          );
        if (rendering !== this.rendering || !this.isConnected) return;
        if (bound) for (const { node } of rendered) node.dataset.lfGen = "1";
        this.replaceChildren();
        shadowStage(this, [
          ...sharedStyles.values(),
          ...rendered.map(({ node }) => node),
        ]);
        if (bound)
          projectData(
            this,
            rendered.flatMap(({ lines }) => lines),
            lineKey,
            ({ node }) => node,
            { nested: true, labelOf: lineLabel },
          );
        this.classList.add("lf-rendered");
      } catch (err) {
        if (rendering !== this.rendering || !this.isConnected) return;
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
  },
);
