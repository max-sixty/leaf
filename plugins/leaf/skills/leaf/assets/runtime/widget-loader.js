import { MARKED_IN_PAGE, dress, markDeclared } from "./presentation.js";
import { reachScrollers } from "./reach.js";
import { registry, tagsDeclaring } from "./registry.js";
import { loadShadowRules } from "./shadow.js";
import { settle, settling } from "./widget-upgrade.js";

/* Registry loading and the one initial widget-upgrade lifecycle. */
export function createWidgetLoader({
  buildReactBar,
  rememberAuthoredMarkup,
  reportPageError,
  revealLayer,
  sameLayer,
}) {
  // The file-side passage reader fences an upgraded element and each of its original
  // direct children when the registry cannot promise its body is verbatim. Remember
  // those parts before custom-element definitions can add or move anything, so the
  // browser can stop captured context at the same seams after every upgrade has run.
  const opaquePassageRoots = new WeakSet();
  const opaquePassageParts = new WeakSet();

  function rememberPassageParts(scope = document) {
    for (const tag of tagsDeclaring(
      (entry) => entry["x-upgrade"] && !entry["x-verbatim"],
    ))
      for (const root of scope.querySelectorAll(tag)) {
        opaquePassageRoots.add(root);
        for (const child of root.children) opaquePassageParts.add(child);
      }
  }

  async function upgradeWidgets() {
    const response = await fetch("/registry.json");
    if (!response.ok)
      throw new Error(`leaf: registry failed to load (${response.status})`);
    const responseGeneration = response.headers.get("Leaf-Layer");
    if (responseGeneration && !sameLayer(responseGeneration)) return;
    Object.assign(registry, await response.json());
    const registryGeneration = registry.$layer?.generation;
    if (typeof registryGeneration !== "string" || !registryGeneration)
      throw new Error("leaf: registry lacks $layer.generation");
    if (!sameLayer(registryGeneration)) return;
    if (
      !registry.$events?.kinds ||
      !registry.$languages?.names ||
      !registry.$languages?.paths ||
      !registry.$tones?.names ||
      !registry.$reactions?.tokens
    )
      throw new Error("leaf: registry lacks $events, $languages, $tones or $reactions");
    revealLayer();
    buildReactBar();
    rememberPassageParts();
    rememberAuthoredMarkup();
    markDeclared(document.body, MARKED_IN_PAGE);
    // Before the modules import, because a widget's first render asks for these rules and
    // an async stage would put every x-shadow widget's look a fetch behind its own nodes.
    if (tagsDeclaring((entry) => entry["x-shadow"]).length) await loadShadowRules();
    await Promise.all(
      tagsDeclaring((entry) => entry["x-upgrade"]).map((tag) =>
        import(`/widgets/${tag}.js`).catch((err) =>
          reportPageError(`widget ${tag} failed to load: ${err?.message ?? err}`),
        ),
      ),
    );
    settle(dress(document.body));
    // Importing defined the elements and ran their connectedCallbacks; async ones
    // registered their work via settle(). Wait it out so geometry is final.
    await Promise.allSettled(settling);
    // After the wait, because the box a widget scrolls is a box its module built: run this
    // with the rest of the upgrade and a diff's pre and a code block's are half there.
    reachScrollers(document.body);
  }

  return {
    opaquePassageParts,
    opaquePassageRoots,
    rememberPassageParts,
    upgradeWidgets,
  };
}
