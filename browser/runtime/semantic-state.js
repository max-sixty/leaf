/* @noformat Generated TypeScript; edit the .ts owner. */
import {
  batch,
  computed,
  effect,
  signal,
  untracked,
  createPresentationCoordinator,
  createPresentationSchedule,
  createSemanticApplication
} from "/runtime/framework.js";
import { bindQueuedWork } from "./queued-work.js";
import { tick } from "./version-signal.js";
let reportPresentationFailure = (reason) => console.error("leaf: presentation failed", reason);
const presentation = createPresentationCoordinator({
  reportFailure: (reason) => reportPresentationFailure(reason)
});
const schedule = createPresentationSchedule(bindQueuedWork);
const applicationState = createSemanticApplication({ presentation });
const readApplication = applicationState.read;
const readPart = (derive) => applicationState.select(derive).read;
const agent = readPart((root) => root.authoritative?.agent ?? null);
const agentName = () => agent() || "the agent";
const pageClaimed = readPart(
  (root) => root.authoritative?.claim_session != null
);
const projectView = applicationState.projectView;
const selectWidgets = applicationState.selectWidgets;
const attachApplicationPresentation = (region) => presentation.attach(region);
const widgetRegion = (widget, kind) => `widget:${widget}:${kind}`;
const widgetRegions = (widget) => ["render", "preparation"].map((kind) => widgetRegion(widget, kind));
const attachWidgetPresentation = (widget, kind) => presentation.attach(widgetRegion(widget, kind));
const widgetCommits = /* @__PURE__ */ new Map();
const documentCommits = /* @__PURE__ */ new Map();
const currentWidgetParents = readPart((root) => root.effective.widgetParents);
const queueWidgetUpdate = (widget, update, committed) => {
  const { ready, committed: dom } = schedule.enqueue(
    () => {
      const parents = untracked(currentWidgetParents);
      const pending = [];
      const seen = /* @__PURE__ */ new Set([widget]);
      for (let parent = parents.get(widget); parent; parent = parents.get(parent)) {
        if (seen.has(parent)) return [];
        seen.add(parent);
        const dom2 = widgetCommits.get(parent);
        if (dom2) pending.push(dom2);
      }
      return pending;
    },
    update,
    committed
  );
  widgetCommits.set(widget, dom);
  const retire = () => {
    if (widgetCommits.get(widget) === dom) widgetCommits.delete(widget);
  };
  void dom.then(retire, retire);
  return ready;
};
const PRESENTATION_DOM = Object.freeze({
  widgets: () => [...widgetCommits.values()],
  projection: () => documentCommits.get("projection:chrome")?.() ?? [],
  thread: () => documentCommits.get("thread")?.() ?? [],
  obligations: () => documentCommits.get("obligations")?.() ?? []
});
const documentPresenters = [];
const applicationPresenter = ({
  region,
  after,
  reading,
  paint,
  failSoft
}) => {
  const revision = signal(0);
  const selected = computed(() => {
    revision.value;
    const epoch = untracked(() => readApplication().semanticEpoch);
    const value = reading();
    if (epoch !== untracked(() => readApplication().semanticEpoch))
      throw new Error(`the ${region} region's reading moved a part it read`);
    return value;
  });
  let claimed;
  let owed = false;
  let following = [];
  const forget = () => {
    for (const stop of following) stop();
    following = [];
  };
  const presenter = schedule.presenter({
    attach: () => presentation.attach(region),
    after,
    paint: (value, current) => {
      owed = false;
      forget();
      const generation = following;
      const stretch = (run) => {
        let first2 = true;
        let outcome;
        const stop = effect(() => {
          if (!first2) {
            if (!owed && current()) {
              untracked(() => {
                const next = selected.value;
                if (next !== null) void claim(next);
              });
            }
            return;
          }
          first2 = false;
          try {
            outcome = { value: run() };
          } catch (error) {
            outcome = { error };
          }
        });
        if (current() && following === generation) generation.push(stop);
        else stop();
        if ("error" in outcome) throw outcome.error;
        return outcome.value;
      };
      const resume = (run) => (...args) => stretch(() => run(...args));
      return stretch(() => paint(value, current, resume));
    },
    failSoft
  });
  documentCommits.set(region, () => [...after?.() ?? [], presenter.committed()]);
  const claim = (value) => {
    claimed = value;
    if (value === null) return schedule.passed();
    owed = true;
    return presenter.sync(value);
  };
  const present = () => untracked(
    () => batch(() => {
      tick(revision);
      return claim(selected.value);
    })
  );
  documentPresenters.push(present);
  let first = true;
  effect(() => {
    const value = selected.value;
    if (first || value === null) {
      first = false;
      claimed = value;
    } else if (value !== claimed) untracked(() => claim(value));
  });
  const disconnect = () => {
    forget();
    presenter.disconnect();
  };
  return Object.freeze({ present, disconnect, committed: presenter.committed });
};
const documentChanges = signal(0);
const documentChanged = () => documentChanges.value;
const presentDocument = () => batch(() => {
  tick(documentChanges);
  for (const present of documentPresenters) void present();
  return schedule.passed();
});
const whenDocumentPresented = () => schedule.passed();
const whenApplicationPresented = () => presentation.whenCurrentPresented();
const applicationPresented = () => presentation.currentPresented();
const whenWidgetsPresented = (widgets) => presentation.whenCurrentRegionsPresented(widgets.flatMap(widgetRegions));
const whenApplicationRegionsPresented = (regions, current) => presentation.whenCurrentRegionsPresented(regions, current);
const applicationRegionsPresented = (regions) => presentation.currentRegionsPresented(regions);
const projectionRegionsPresented = (widgets) => applicationRegionsPresented(["projection:chrome", ...widgets.flatMap(widgetRegions)]);
const watchPresentation = presentation.subscribe;
const readApplicationPresentation = presentation.read;
function setPresentationFailureReporter(report) {
  reportPresentationFailure = (reason) => report(reason, "Presentation failed");
}
const watchSemantic = (callback) => applicationState.select((root) => root.semanticEpoch).subscribe(() => callback(readApplication()));
export {
  PRESENTATION_DOM,
  agentName,
  applicationPresented,
  applicationPresenter,
  applicationRegionsPresented,
  applicationState,
  attachApplicationPresentation,
  attachWidgetPresentation,
  documentChanged,
  pageClaimed,
  presentDocument,
  projectView,
  projectionRegionsPresented,
  queueWidgetUpdate,
  readApplication,
  readApplicationPresentation,
  readPart,
  selectWidgets,
  setPresentationFailureReporter,
  watchPresentation,
  watchSemantic,
  whenApplicationPresented,
  whenApplicationRegionsPresented,
  whenDocumentPresented,
  whenWidgetsPresented
};
