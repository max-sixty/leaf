/* Passive observations of the page the user currently sees.
 *
 * The caller owns presentation readiness and the revision and viewport that identify
 * this reading. This synchronous reader never resizes, scrolls, writes markup, or
 * exercises a widget. It selects the render gate's read-only probes, leaving its
 * temporary experiments and exhaustive reachability walks to the authoring gate.
 * Arrangement is context; checks report measurements, with the label heuristic's
 * threshold attached, and prescribe no composition or remedy. */
import {
  arrangedBoxes,
  heldPanes,
  marginResidents,
  overflowingRegions,
  rootOverflow,
} from "./layout.js";
import { shrunkLabelReading } from "./words.js";

export function readViewChecks(open) {
  return {
    layout: {
      margin: marginResidents(),
      arrangement: arrangedBoxes(open),
      panes: heldPanes(),
    },
    checks: {
      horizontal_overflow_px: rootOverflow(),
      overflowing_regions: overflowingRegions(),
      shrunk_labels: shrunkLabelReading(),
    },
  };
}
