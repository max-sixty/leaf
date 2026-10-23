/* What a user who meets a problem copies to say which page and which Leaf they are on:
 * the page's access link, a developer preview's diagnostics, the Leaf version the page
 * runs, and the website's session reference. Each is one row of the page's controls
 * (page-controls.js) whose press copies its text, derived from the state reading where
 * it is read, so a presentation follows the reading. */
import { ago } from "./presence.js";
import { DELIVERY, SHARE_ROOT, runtime, shareUrl } from "./context.js";
import { PAGE_CONTROL_RANK, registerPageControl } from "./page-controls.js";
import { retainUserIntent } from "./user-intent.js";
import { raiseError } from "./errors.js";

registerPageControl({
  key: "inspection",
  rank: PAGE_CONTROL_RANK.inspection,
  label: "Page diagnostics",
  group: "page",
  press: () => {
    const intent = retainUserIntent();
    void import("./page-inspection.js")
      .then(({ openPageInspection }) => openPageInspection(intent))
      .catch((error) =>
        raiseError(
          `Page diagnostics could not open: ${error.message}. Open the menu to retry.`,
        ),
      );
  },
});

// How old a Leaf payload is, so a user who meets a problem can tell whether it
// predates the fixes since. A payload read from Git carries its commit's date; a harness's
// plugin cache, which drops `.git`, carries the time it copied the commit, one update
// sweep after it landed (`layer.payload_provenance`).
const payloadAge = (provenance) => ago(provenance.committed ?? provenance.installed);
const payloadDateLines = (provenance) =>
  ["committed", "installed"]
    .filter((kind) => provenance[kind])
    .map((kind) => `${kind}: ${provenance[kind]}`);
// A payload's commit as a row names it, `+` marking uncommitted changes.
const shortCommit = (provenance) =>
  provenance.commit
    ? `${provenance.commit.slice(0, 8)}${provenance.dirty ? "+" : ""}`
    : "unknown";
// Another payload's diagnostics, each line led by how it relates to the page.
const otherPayloadLines = (relation, provenance) => [
  ...(provenance.commit ? [`${relation} commit: ${provenance.commit}`] : []),
  ...(provenance.dirty !== undefined ? [`${relation} dirty: ${provenance.dirty}`] : []),
  ...payloadDateLines(provenance).map((line) => `${relation} ${line}`),
];
// Where another Leaf serves the page (`state.leaf`), whose runtime the page runs, it
// stands beside the Leaf that vendored the page's layer with its age, so whoever meets
// a problem can tell how far apart the two are (AGENTS.md, "Pages across Leaf
// updates").
const servedBy = (state) =>
  state.leaf
    ? ` · served by ${shortCommit(state.leaf)}${payloadAge(state.leaf) ? ` · ${payloadAge(state.leaf)}` : ""}`
    : "";
const pageUrl = () => {
  const url = new URL(location.href);
  url.searchParams.delete("t");
  return String(url);
};

if (SHARE_ROOT)
  registerPageControl({
    key: "share",
    rank: PAGE_CONTROL_RANK.share,
    label: "link",
    value: "Grants access to all Leaf pages on this machine.",
    copies: shareUrl,
    group: "page",
  });

// The developer preview's identity: which checkout is serving this page. A user preview
// claims the page, so every press on it, the agent's own screenshots included, comes
// back to the session as user input; that is the mode worth marking.
const preview = () => /** @type {any} */ (runtime.state)?.preview ?? null;
function previewLabel() {
  const state = /** @type {any} */ (runtime.state);
  const producer = state.layer.producer ?? {};
  const kind = preview().interaction === "user" ? "User" : "Preview";
  const stem = `${kind} · ${preview().checkout}${producer.commit ? `@${producer.commit}` : ""}`;
  const age = payloadAge(producer);
  return `${producer.commit && producer.dirty ? `${stem}+` : stem}${age ? ` · ${age}` : ""}${servedBy(state)}`;
}
function previewDiagnostics() {
  const state = /** @type {any} */ (runtime.state);
  const producer = state.layer.producer ?? {};
  const { example, checkout, interaction, started } = preview();
  return [
    "Leaf preview",
    `example: ${example}`,
    `checkout: ${checkout}`,
    `interaction: ${interaction}`,
    ...(producer.commit ? [`commit: ${producer.commit}`] : []),
    ...(producer.dirty !== undefined ? [`dirty: ${producer.dirty}`] : []),
    ...payloadDateLines(producer),
    ...(state.leaf ? otherPayloadLines("served by", state.leaf) : []),
    `started: ${started}`,
    ...runtimeLines(),
    `layer generation: ${state.layer.generation}`,
    ...(state.layer.fingerprint
      ? [`layer fingerprint: ${state.layer.fingerprint}`]
      : []),
    ...(state.active ? [`revision: ${state.active.revision}`] : []),
    `event sequence: ${state.events.at(-1)?.seq ?? 0}`,
    `url: ${pageUrl()}`,
  ].join("\n");
}
registerPageControl({
  key: "preview",
  rank: PAGE_CONTROL_RANK.preview,
  label: "preview diagnostics",
  value: () => (preview() ? previewLabel() : ""),
  copies: () => (preview() ? previewDiagnostics() : ""),
  offered: () => Boolean(preview()),
  group: "page",
});

// The runtime this document runs, which the server serving it supplied
// (`runtime_selection.py`); a website release names it instead.
function runtimeLines() {
  return DELIVERY.runtime ? [`runtime: ${DELIVERY.runtime}`] : [];
}

// The vendored layer names the Leaf version that composed this page's registry, theme
// and widgets. It can remain older than the plugin now installed in the harness, so
// this reads the provenance captured by `page init` rather than a live package or
// server version. Pages built outside Git retain a stable identity through the
// composed layer fingerprint.
function layerIdentity(state) {
  const producer = state.layer.producer ?? {};
  const fingerprint = state.layer.fingerprint;
  if (producer.commit) return shortCommit(producer);
  return fingerprint
    ? `sha256:${fingerprint.replace(/^sha256:/, "").slice(0, 12)}`
    : null;
}
const layerShown = () => {
  const state = /** @type {any} */ (runtime.state);
  return Boolean(state && !state.preview && layerIdentity(state));
};
function layerNamed() {
  const state = /** @type {any} */ (runtime.state);
  const age = payloadAge(state.layer.producer ?? {});
  return `Leaf ${layerIdentity(state)}${age ? ` · ${age}` : ""}${servedBy(state)}`;
}
function layerDiagnostics() {
  const state = /** @type {any} */ (runtime.state);
  const producer = state.layer.producer ?? {};
  const fingerprint = state.layer.fingerprint;
  return [
    "Leaf layer",
    ...(producer.commit ? [`commit: ${producer.commit}`] : []),
    ...(producer.dirty !== undefined ? [`dirty: ${producer.dirty}`] : []),
    ...payloadDateLines(producer),
    ...(state.leaf ? otherPayloadLines("served by", state.leaf) : []),
    ...(fingerprint ? [`fingerprint: ${fingerprint}`] : []),
    `generation: ${state.layer.generation}`,
    ...runtimeLines(),
    ...(state.active ? [`revision: ${state.active.revision}`] : []),
    `url: ${pageUrl()}`,
  ].join("\n");
}
registerPageControl({
  key: "layer",
  rank: PAGE_CONTROL_RANK.layer,
  label: "Leaf version",
  value: () => (layerShown() ? layerNamed() : ""),
  copies: () => (layerShown() ? layerDiagnostics() : ""),
  offered: layerShown,
  group: "page",
});

// The public website support handle.
registerPageControl({
  key: "session",
  rank: PAGE_CONTROL_RANK.session,
  label: "session reference",
  copies: () => runtime.sessionReference ?? "",
  offered: () => Boolean(runtime.sessionReference),
  group: "page",
});
