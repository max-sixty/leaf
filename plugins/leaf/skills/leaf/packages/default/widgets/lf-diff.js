/* lf-diff uses Pierre's static renderer rather than hydrating Pierre's custom
 * element. Its ordinary DOM can live in Leaf's declared shadow root, so the
 * same rendered lines support selection anchors and script-free export. */
import {
  DISCLOSE,
  dataBody,
  failSoft,
  keys,
  langForPath,
  once,
  settle,
  shadowStage,
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

function summaryNode(file) {
  const details = document.createElement("details");
  details.open = true;
  const summary = document.createElement("summary");
  const path = file.name || "(unnamed file)";
  const { adds, dels } = changeCounts(file);
  summary.append(
    Object.assign(document.createElement("span"), {
      className: "lf-diff-path",
      textContent: path,
    }),
    Object.assign(document.createElement("span"), {
      className: "lf-diff-stat",
      textContent: `+${adds} −${dels}`,
    }),
  );
  keys(summary, "On a diff", [
    {
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
  details.append(rendered);
  return details;
}

customElements.define(
  "lf-diff",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      settle(this.render());
    }

    async render() {
      const source = dataBody(this).replace(/^\n+/, "").replace(/\n$/, "");
      try {
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
        for (const file of files)
          if (!file.hunks.length && file.type !== "rename-pure")
            throw new Error(
              `unsupported hunkless diff for ${file.name || "a file"} ` +
                "(binary, mode-only, and empty added/deleted entries belong in prose; " +
                "changed files need textual @@ hunks)",
            );
        const sharedStyles = new Map();
        const rendered = [];
        for (const file of files)
          rendered.push(
            file.type === "rename-pure"
              ? renameNode(file)
              : await renderFile(file, sharedStyles),
          );
        this.replaceChildren();
        shadowStage(this, [...sharedStyles.values(), ...rendered]);
        this.classList.add("lf-rendered");
      } catch (err) {
        failSoft(this, err, source);
      }
    }
  },
);
