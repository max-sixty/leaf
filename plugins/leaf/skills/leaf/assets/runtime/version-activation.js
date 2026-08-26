import { runtime } from "./context.js";
import { MARKED_IN_PAGE, dress, markDeclared } from "./presentation.js";
import { reachScrollers } from "./reach.js";
import { versionUrl } from "./storage.js";

// The document roots may carry authored classes, data attributes, and inline custom
// properties that page-local styles read. The live document also paints its own facts
// onto those same two elements. Remember exactly the authored share before the runtime
// writes anything so a version activation can replace that share without erasing the
// presentation, layout, and mode facts the surviving runtime owns.
const authoredAttributes = (root) =>
  new Map([...root.attributes].map(({ name, value }) => [name, value]));
const versionedHeadNode = (node) =>
  !(
    node.localName === "meta" &&
    node.getAttribute("name") === "lf-version" &&
    node.hasAttribute("data-lf-runtime")
  ) &&
  (node.localName === "title" ||
    node.localName === "style" ||
    node.localName === "base" ||
    (node.localName === "meta" &&
      (node.hasAttribute("name") || node.hasAttribute("property"))) ||
    (node.localName === "link" &&
      !(
        node.rel === "stylesheet" &&
        new URL(node.href, document.baseURI).pathname === "/theme.css"
      )));

export function captureVersionRoots() {
  return {
    authoredBodyAttributes: authoredAttributes(document.body),
    authoredHeadNodes: new Set([...document.head.children].filter(versionedHeadNode)),
    authoredHtmlAttributes: authoredAttributes(document.documentElement),
  };
}

export function createVersionActivation(
  versionRoots,
  {
    captureAuthoredFacets,
    captureView,
    comparisonBase,
    designIsOn,
    paintLegend,
    pruneScopedElements,
    rememberAuthoredMarkup,
    rememberPassageParts,
    resetAuthoredPage,
    sameLayer,
    setDiff,
    settle,
    settling,
    stateSignoff,
    stateStrip,
    style,
    syncLayout,
  },
) {
  let { authoredBodyAttributes, authoredHeadNodes, authoredHtmlAttributes } =
    versionRoots;
  // ---------- live version activation ----------
  const versionDocuments = new Map();
  let activatingState = null;
  function versionDocument(version) {
    if (versionDocuments.has(version)) return versionDocuments.get(version);
    const name = versionUrl(version);
    const loading = fetch(name)
      .then(async (response) => {
        if (!response.ok) throw new Error(`couldn't load ${name} (${response.status})`);
        const generation = response.headers.get("Leaf-Layer");
        if (generation && !sameLayer(generation)) return null;
        const doc = new DOMParser().parseFromString(await response.text(), "text/html");
        if (
          !doc.querySelector("body > main") ||
          doc.querySelectorAll("body > main").length !== 1
        )
          throw new Error(`${name} has no single authored main`);
        return doc;
      })
      .catch((error) => {
        versionDocuments.delete(version);
        throw error;
      });
    versionDocuments.set(version, loading);
    return loading;
  }

  function replaceAuthoredAttributes(target, source, prior) {
    const scratch = document.createElement(target.localName);
    for (const [name, value] of prior) scratch.setAttribute(name, value);
    for (const name of prior.keys()) {
      if (name === "class")
        for (const token of scratch.classList) target.classList.remove(token);
      else if (name === "style")
        for (const property of scratch.style) target.style.removeProperty(property);
      else target.removeAttribute(name);
    }
    const next = authoredAttributes(source);
    for (const [name, value] of next) {
      if (name === "class")
        for (const token of source.classList) target.classList.add(token);
      else if (name === "style")
        for (const property of source.style)
          target.style.setProperty(
            property,
            source.style.getPropertyValue(property),
            source.style.getPropertyPriority(property),
          );
      else target.setAttribute(name, value);
    }
    return next;
  }

  function activateHead(doc, version) {
    for (const node of authoredHeadNodes) node.remove();
    const runtimeStyle = style;
    const next = new Set();
    for (const node of doc.head.children) {
      if (!versionedHeadNode(node)) continue;
      const imported = document.importNode(node, true);
      document.head.insertBefore(imported, runtimeStyle);
      next.add(imported);
    }
    authoredHeadNodes = next;
    let marker = document.querySelector('meta[name="lf-version"][data-lf-runtime]');
    if (!marker) {
      marker = document.createElement("meta");
      marker.name = "lf-version";
      marker.dataset.lfRuntime = "1";
      document.head.insertBefore(marker, runtimeStyle);
    }
    marker.content = String(version);
    stateSignoff(doc.querySelector('meta[name="lf-review"]')?.content === "sign-off");
  }

  async function activateVersion(doc, version) {
    const view = captureView();
    const source = doc.querySelector("body > main");
    const fresh = document.importNode(source, true);
    versionDocuments.delete(version);
    const settlingFrom = settling.length;
    const comparedFrom = comparisonBase();
    if (comparedFrom !== null) setDiff(false);

    resetAuthoredPage();
    rememberAuthoredMarkup(source);
    rememberAuthoredMarkup(fresh);
    rememberPassageParts(fresh);
    markDeclared(fresh, MARKED_IN_PAGE);
    authoredHtmlAttributes = replaceAuthoredAttributes(
      document.documentElement,
      doc.documentElement,
      authoredHtmlAttributes,
    );
    authoredBodyAttributes = replaceAuthoredAttributes(
      document.body,
      doc.body,
      authoredBodyAttributes,
    );
    runtime.currentVersion = version;
    activateHead(doc, version);
    document.querySelector("body > main").replaceWith(fresh);
    pruneScopedElements();
    settle(dress(fresh));
    await Promise.allSettled(settling.slice(settlingFrom));
    reachScrollers(fresh);
    captureAuthoredFacets(fresh);
    stateStrip();
    syncLayout();
    if (designIsOn()) paintLegend();
    return { view, comparedFrom };
  }

  function currentActivation() {
    return activatingState;
  }
  function trackActivation(running) {
    activatingState = running;
    return () => {
      if (activatingState === running) activatingState = null;
    };
  }

  return { activateVersion, currentActivation, trackActivation, versionDocument };
}
