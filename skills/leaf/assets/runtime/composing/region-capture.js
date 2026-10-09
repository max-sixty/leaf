/* Area capture is a page command; the selector and rasterizer load on demand.
 * Its native modal temporarily owns input without changing the page's Draw or Design
 * state. Captures enter the same anchored draft and media admission path as pasted
 * images. No screenshot bytes or geometric authority enter the event log.
 */
import { pageCommand } from "../keyboard/register.js";
import {
  BANNER_CONTROL_RANK,
  bannerStanding,
  dismissBannerControls,
  registerBannerControl,
  restoreBannerStanding,
} from "../banner-toolbar.js";
import { anchoringIsReady } from "../anchor-resolution.js";
import { offlineInteractive } from "../context.js";
import { closeLayer } from "../focus.js";
import { retainUserIntent } from "../user-intent.js";
import { notice } from "../notifications.js";
import { el } from "../widget-elements.js";

export function createRegionCapture({ parent, visibleTargets, openComposerWithMedia }) {
  const control = el("button", "lf-btn", "Capture area");
  control.type = "button";
  registerBannerControl({
    key: "capture-area",
    control,
    rank: BANNER_CONTROL_RANK.commands,
  });
  let opening = false;
  pageCommand({
    id: "capture.region.open",
    keys: [],
    title: "Capture area",
    description: "Select an area of the page and attach its image to a comment",
    touch: false,
    control,
    when: () => anchoringIsReady() && !offlineInteractive && !opening,
    run: async () => {
      const standing = bannerStanding();
      closeLayer(dismissBannerControls, () => restoreBannerStanding(standing));
      const intent = retainUserIntent();
      opening = true;
      try {
        const { captureRegion } = await import("./region-selector.js");
        if (intent())
          await captureRegion({ parent, visibleTargets, openComposerWithMedia });
      } catch (error) {
        notice(`Could not open area capture — ${error.message}`);
      } finally {
        opening = false;
      }
    },
  });
}
