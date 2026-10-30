/* What a user who meets a problem copies to say which page and which Leaf they are on:
 * the page's access link, the agent session its comments reach, a developer preview's
 * diagnostics, the Leaf version the page runs, and the website's session reference.
 * Each is one row of the page's controls
 * (page-controls.js) whose press copies its text, derived from the state reading where
 * it is read, so a presentation follows the reading. */
import { pageIdentity } from "./page-identity.js";
import { ago } from "./presence.js";
import { SHARE_ROOT, runtime, shareUrl } from "./context.js";
import { PAGE_CONTROL_RANK, registerPageControl } from "./page-controls.js";
import { retainUserIntent } from "./user-intent.js";
import { raiseError } from "./errors.js";

registerPageControl({
  key: "inspection",
  rank: PAGE_CONTROL_RANK.inspection,
  label: "About this page",
  group: "page",
  press: () => {
    const intent = retainUserIntent();
    void import("./page-inspection.js")
      .then(({ openPageInspection }) => openPageInspection(intent))
      .catch((error) =>
        raiseError(
          `About this page could not open: ${error.message}. Open the menu to retry.`,
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

if (SHARE_ROOT)
  registerPageControl({
    key: "share",
    rank: PAGE_CONTROL_RANK.share,
    label: "link",
    value: "Grants access to all Leaf pages on this machine.",
    copies: shareUrl,
    group: "page",
  });

// The agent session that holds the page, which the user's comments reach: by the name
// its harness gives it, or the start of its id where it gives none, and the directory
// it works in, so a user with several sessions open can tell which one to turn to
// (`presence.page_list` lists the same for every page). A session that ended still
// holds the page until another claims it, so the row says so rather than going.
export function claimantValue(state) {
  const { session_name: name, claim_session: id, session_cwd: cwd } = state;
  const where = cwd ? cwd.split("/").findLast(Boolean) : null;
  return [name || id.slice(0, 8), where, state.session_alive === false && "ended"]
    .filter(Boolean)
    .join(" · ");
}
export function claimantDiagnostics(state) {
  return [
    "Agent session",
    `agent: ${state.agent}`,
    ...(state.session_name ? [`name: ${state.session_name}`] : []),
    `id: ${state.claim_session}`,
    ...(state.session_cwd ? [`directory: ${state.session_cwd}`] : []),
    `running: ${state.session_alive !== false}`,
  ].join("\n");
}
const claimed = () => Boolean(/** @type {any} */ (runtime.state)?.claim_session);
registerPageControl({
  key: "claimant",
  rank: PAGE_CONTROL_RANK.claimant,
  label: "agent session",
  value: () => (claimed() ? claimantValue(/** @type {any} */ (runtime.state)) : ""),
  copies: () =>
    claimed() ? claimantDiagnostics(/** @type {any} */ (runtime.state)) : "",
  offered: claimed,
  group: "about",
});

// The developer preview's identity: which checkout is serving this page. A user preview
// claims the page, so every press on it, the agent's own screenshots included, comes
// back to the session as user input; that is the mode worth marking.
const preview = () => /** @type {any} */ (runtime.state)?.preview ?? null;
function previewLabel() {
  const identity = pageIdentity();
  const producer = identity.layer.producer ?? {};
  const kind = preview().interaction === "user" ? "User" : "Preview";
  const stem = `${kind} · ${preview().checkout}${producer.commit ? `@${producer.commit}` : ""}`;
  const age = payloadAge(producer);
  return `${producer.commit && producer.dirty ? `${stem}+` : stem}${age ? ` · ${age}` : ""}`;
}
function previewDiagnostics() {
  const identity = pageIdentity();
  const producer = identity.layer.producer ?? {};
  const { example, checkout, interaction, started } = identity.preview;
  return [
    "Leaf preview",
    `example: ${example}`,
    `checkout: ${checkout}`,
    `interaction: ${interaction}`,
    ...(producer.commit ? [`commit: ${producer.commit}`] : []),
    ...(producer.dirty !== undefined ? [`dirty: ${producer.dirty}`] : []),
    ...payloadDateLines(producer),
    `started: ${started}`,
    ...runtimeLines(),
    `layer generation: ${identity.layer.generation}`,
    ...(identity.layer.fingerprint
      ? [`layer fingerprint: ${identity.layer.fingerprint}`]
      : []),
    ...(runtime.currentRevision ? [`revision: ${runtime.currentRevision}`] : []),
    `event sequence: ${runtime.lastEventSeq ?? 0}`,
    `url: ${identity.url}`,
  ].join("\n");
}
registerPageControl({
  key: "preview",
  rank: PAGE_CONTROL_RANK.preview,
  label: "preview diagnostics",
  value: () => (preview() ? previewLabel() : ""),
  copies: () => (preview() ? previewDiagnostics() : ""),
  offered: () => Boolean(preview()),
  group: "about",
});

// The runtime this document runs, which the server serving it supplied
// (`runtime_selection.py`); a website release names it instead.
function runtimeLines() {
  const { delivery } = pageIdentity();
  return delivery.runtime ? [`runtime: ${delivery.runtime}`] : [];
}

// The layer names the Leaf that composed this page's registry, theme and widgets:
// the one serving it, which also supplies its runtime
// (`registry.storage.served_layer`). It can be older than the plugin now installed in
// the harness, since a server keeps the code it started with. Pages built outside Git retain a stable identity through
// the composed layer fingerprint.
function layerIdentity(identity) {
  const producer = identity.layer.producer ?? {};
  const fingerprint = identity.layer.fingerprint;
  if (producer.commit) return shortCommit(producer);
  return fingerprint
    ? `sha256:${fingerprint.replace(/^sha256:/, "").slice(0, 12)}`
    : null;
}
const layerShown = () => {
  const identity = pageIdentity();
  return Boolean(identity.layer && !identity.preview && layerIdentity(identity));
};
function layerNamed() {
  const identity = pageIdentity();
  const age = payloadAge(identity.layer.producer ?? {});
  return `Leaf ${layerIdentity(identity)}${age ? ` · ${age}` : ""}`;
}
function layerDiagnostics() {
  const identity = pageIdentity();
  const producer = identity.layer.producer ?? {};
  const fingerprint = identity.layer.fingerprint;
  return [
    "Leaf layer",
    ...(producer.commit ? [`commit: ${producer.commit}`] : []),
    ...(producer.dirty !== undefined ? [`dirty: ${producer.dirty}`] : []),
    ...payloadDateLines(producer),
    ...(fingerprint ? [`fingerprint: ${fingerprint}`] : []),
    `generation: ${identity.layer.generation}`,
    ...runtimeLines(),
    ...(runtime.currentRevision ? [`revision: ${runtime.currentRevision}`] : []),
    `url: ${identity.url}`,
  ].join("\n");
}
registerPageControl({
  key: "layer",
  rank: PAGE_CONTROL_RANK.layer,
  label: "Leaf version",
  value: () => (layerShown() ? layerNamed() : ""),
  copies: () => (layerShown() ? layerDiagnostics() : ""),
  offered: layerShown,
  group: "about",
});

// The public website support handle.
registerPageControl({
  key: "session",
  rank: PAGE_CONTROL_RANK.session,
  label: "session reference",
  copies: () => runtime.sessionReference ?? "",
  offered: () => Boolean(runtime.sessionReference),
  group: "about",
});
