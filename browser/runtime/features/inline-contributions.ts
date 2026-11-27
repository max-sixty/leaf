/* Contributed controls inside Thread messages' markup.

   They belong to the Thread's local flow whichever annotation presentation the
   page selects. The shared control owner retains each native entry when its dynamic
   target moves between a page annotation and a Thread. This owner only seats those
   controls beside the currently connected target, after conversation commits. */
import { setChildren } from "../dom/dom-children.js";
import { contributionEntries } from "./contributions.js";
import {
  activateContributionControl,
  clearContributionControls,
  materializeContributionControls,
  presentContributionReceipts,
} from "./contribution-controls.js";
import { compareContributions, spokenSubject } from "../base/contribution-model.js";
import { addressableWord } from "../lib/element-word.js";
import { holdFocus } from "../dom/focus.js";
import { move } from "../dom/dom-move.js";
import { generatedElement } from "../dom/widget-elements.js";
import { el } from "../lib/elements.js";
import { keeps } from "../lib/keeps.js";
import { inChrome } from "../base/ui-marks.js";
import type { ContributionSource } from "./contributions.js";

type Source = ContributionSource;
type Seat = { host: HTMLDivElement; offers: Source[] };
export function createInlineContributions({
  targetPath,
}: {
  targetPath: (element: Element) => string;
}) {
  const hosts = new Map<Element, Seat>();

  function present() {
    const grouped = new Map<Element, Source[]>();
    for (const offered of contributionEntries()) {
      const target = offered.target();
      if (
        !target?.isConnected ||
        !inChrome(target) ||
        !offered.reading.entries.some((entry) => entry.visible)
      )
        continue;
      const offers = grouped.get(target) ?? [];
      offers.push(offered);
      grouped.set(target, offers);
    }
    // Retire the old seat before a new one tracks the same retained controls.
    for (const [target, { host, offers }] of hosts)
      if (!grouped.has(target)) {
        for (const offered of offers)
          clearContributionControls(offered, "inline", new Set());
        host.replaceChildren();
        host.remove();
        hosts.delete(target);
      }
    for (const [target, offers] of grouped) {
      let seat = hosts.get(target);
      if (!seat) {
        const host = el("div", "lf-ui lf-margin-inline");
        generatedElement(host);
        host.setAttribute("role", "group");
        seat = { host, offers: [] };
        hosts.set(target, seat);
      }
      const { host } = seat;
      for (const offered of seat.offers)
        if (!offers.includes(offered))
          clearContributionControls(offered, "inline", new Set());
      seat.offers = offers;
      host.lfTarget = target;
      keeps(host, "data-lf-margin-for", target.id || targetPath(target));
      keeps(
        host,
        "aria-label",
        `Actions for ${spokenSubject(addressableWord(target))}`,
      );
      const controls = (side: "before" | "after") =>
        offers
          .filter((offered) => offered.reading.side === side)
          .sort((left, right) => compareContributions(left.model, right.model))
          .flatMap((offered) => {
            const materialized = materializeContributionControls(
              offered.model,
              "inline",
              activateContributionControl,
            );
            return offered.reading.entries
              .filter((entry) => entry.visible)
              .map((entry) => {
                const control = materialized(entry);
                presentContributionReceipts(control, entry.workflowReceipt, false);
                return control;
              });
          });
      const nodes = [...controls("before"), ...controls("after")];
      for (const node of nodes) node.removeAttribute("data-lf-margin-entry-primary");
      const restoreFocus = holdFocus(host);
      setChildren(host, nodes);
      restoreFocus?.();
      const parent = target.parentNode;
      if (parent && target.nextSibling !== host) move(parent, host, target.nextSibling);
    }
  }
  return Object.freeze({ present });
}
