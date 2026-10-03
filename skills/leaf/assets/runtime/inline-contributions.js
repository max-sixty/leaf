/* Contributed controls inside frozen Thread content.

   They belong to the Thread's local flow whichever annotation presentation the
   page selects. The shared control owner retains each native entry when its dynamic
   target moves between a page annotation and a Thread. This owner only seats those
   controls beside the currently connected target, after conversation commits. */
import { html, nothing, render, repeat } from "../vendor/browser-runtime.js";
import { contributionEntries } from "./contributions.js";
import {
  activateContributionControl,
  clearContributionControls,
  materializeContributionControls,
} from "./contribution-controls.js";
import { compareContributions, spokenSubject } from "./contribution-model.js";
import { addressableWord } from "./anchor-resolution.js";
import { inChrome } from "./passages.js";
import { holdFocus, placeChrome } from "./focus.js";
import { el } from "./widget-elements.js";
import { keeps } from "./keeps.js";
import { repaint } from "./repaint.js";

export function createInlineContributions({ targetPath }) {
  const hosts = new Map();

  function present() {
    const grouped = new Map();
    for (const offered of contributionEntries()) {
      const target =
        typeof offered.target === "function" ? offered.target() : offered.target;
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
        render(nothing, host);
        host.remove();
        hosts.delete(target);
      }
    for (const [target, offers] of grouped) {
      let seat = hosts.get(target);
      if (!seat) {
        const host = el("div", "lf-ui lf-margin-inline");
        host.dataset.lfGen = "1";
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
      const controls = (side) =>
        offers
          .filter((offered) => offered.reading.side === side)
          .sort(compareContributions)
          .flatMap((offered) => {
            const materialized = materializeContributionControls(
              offered,
              "inline",
              activateContributionControl,
            );
            return offered.reading.entries
              .filter((entry) => entry.visible)
              .map((entry) => materialized.get(entry.key));
          });
      const nodes = [...controls("before"), ...controls("after")];
      for (const node of nodes) node.removeAttribute("data-lf-margin-entry-primary");
      const restoreFocus = holdFocus(host);
      render(
        html`${repeat(
          nodes,
          (node) => node,
          (node) => node,
        )}`,
        host,
      );
      restoreFocus?.();
      if (target.nextSibling !== host) {
        const keepFocus = holdFocus(host);
        const kept = placeChrome(() => {
          target.after(host);
          return keepFocus?.() ?? true;
        });
        if (!kept) repaint();
      }
    }
  }
  return Object.freeze({ present });
}
