/* A heading's link: a control at the start of a heading the page gives an address,
   whose press copies the page's URL ending in that address's fragment, so a reader can
   link to the section they are reading.

   A heading's address is the outermost authored addressable it titles, by the rule that
   names an element after its leading title (addressable-names.js, `leadingTitle`): a
   section's address when the heading opens an identified section, an hgroup's when it
   opens an identified hgroup, else the heading's own id. A heading with none of these
   has no link, since a lent id would not survive the next revision.

   The control follows Copy at a code block's corner (code-copy.js): it stands in chrome
   (block-controls.js), hidden at rest, so it covers no words and takes no presses, and
   shows while a pointer is over the heading or the control, or while the user is on the
   heading itself. A finger has no hover, so a tap on the heading stands the user on it,
   and only a later press on the shown control copies. Enter on the heading or its
   address copies the link, through a scope that asks what the user is on, so the words
   inside a section keep their Enter, and shows the mark with its result until the user
   moves. Rejected: showing the mark while the user is on the address, which put one
   beside every decision `m` landed on, where the user had come to answer. The control
   stands in the gutter before the heading's first line; where the gutter has no room
   for it, as on a phone, it stands at the heading's far end instead. It takes no room,
   since room made for it would move the page's content. Its height is the first
   line's, which the script reads (`firstLine`), since an anchor offers only the
   heading's box.

   A control is made when its heading first shows it and released when the heading
   leaves, so a long page pays nothing for the headings nobody reaches. */
import { leadingTitle } from "./addressable-names.js";
import { isAddressable } from "./anchor-resolution.js";
import { watchOwner } from "./arrivals.js";
import {
  aimControl,
  anchorControl,
  pressedElsewhere,
  readInsets,
  releaseControl,
  revealControl,
  standInChrome,
  tabFromBlock,
  writeInsets,
} from "./block-controls.js";
import { copyControl } from "./copy-control.js";
import { headerLevels } from "./css-anchors.js";
import { focusDestination, focused, onCurrentLocation } from "./focus.js";
import { layoutPx } from "./keeps.js";
import { pageScope } from "./keyboard/register.js";
import { inChrome, pageQueryAll } from "./passages.js";

const HEADING = "h1, h2, h3, h4, h5, h6";

const links = new Map(); // heading → its link, from the first reveal until it leaves
const owners = new WeakMap(); // control → its heading

/** The element `heading`'s link names, or null where it has no address (header). */
export function headingAddress(heading) {
  let address = isAddressable(heading) ? heading : null;
  for (let at = heading.parentElement; at && leadingTitle(at) === heading;) {
    if (isAddressable(at)) address = at;
    at = at.parentElement;
  }
  return address;
}

// The page heading `node` stands in, where a link can stand over it.
function headingAt(node) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  const heading = element?.closest(HEADING);
  return heading && heading.getRootNode() === document && !inChrome(heading)
    ? heading
    : null;
}

// The heading whose link the user is on: the heading itself or the address it names.
// A control inside the heading, such as a link, is somewhere else, with its own Enter.
function headingOn(node) {
  if (node?.nodeType !== Node.ELEMENT_NODE) return null;
  if (headingAt(node) === node) return headingAddress(node) ? node : null;
  const title = leadingTitle(node);
  return title && headingAt(title) === title && headingAddress(title) === node
    ? title
    : null;
}

const linkUrl = (address) =>
  new URL(`#${encodeURIComponent(address.id)}`, location.href).href;

function makeLink(heading) {
  const control = copyControl("lf-heading-link", {
    label: "Copy link to section",
    success: "Link copied",
    error: "Unable to copy link",
    icon: "link",
  });
  control.tabIndex = -1;
  const link = {
    heading,
    control,
    shown: new Set(),
    events: new AbortController(),
    stop: () => {},
  };
  // The address is read at the press, since a revision can rename it while it shows.
  control.addEventListener(
    "click",
    (event) => {
      const address = headingAddress(heading);
      if (address && !pressedElsewhere(event, control)) {
        control.value = linkUrl(address);
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
    },
    { capture: true },
  );
  tabFromBlock(control, heading, link.events.signal);
  owners.set(control, heading);
  links.set(heading, link);
  link.stop = watchOwner(heading, { disconnect: () => retire(link) });
  // Read everything before the anchor is named or the control connects.
  const reading = anchorControl(control, heading);
  const levels = headerLevels(heading);
  const insets = readInsets(heading);
  const line = firstLine(heading);
  aimControl(reading);
  writeInsets(control, insets);
  standInChrome(control, heading, levels);
  writeLine(control, line);
  return link;
}

// Where the heading's first line of words stands in its box, so the control centers on
// it. An anchor offers the box's edges and no line in it, and a heading that wraps
// would otherwise center the control between its lines.
function firstLine(heading) {
  const box = heading.getBoundingClientRect();
  const range = document.createRange();
  range.selectNodeContents(heading);
  const line = range.getClientRects()[0];
  return line
    ? { top: line.top - box.top, height: line.height }
    : { top: 0, height: box.height };
}
function writeLine(control, { top, height }) {
  for (const [property, length] of /** @type {[string, number][]} */ ([
    ["--lf-heading-link-top", top],
    ["--lf-heading-link-line", height],
  ])) {
    const value = layoutPx(length);
    if (control.style.getPropertyValue(property) !== value)
      control.style.setProperty(property, value);
  }
}

// Take a link out once its heading leaves, or loses its address to a revision.
function retire(link) {
  link.stop();
  link.events.abort();
  releaseControl(link.control);
  links.delete(link.heading);
}

// Show or hide the heading's link for one reason; it shows while any reason holds.
// Returns the link, made on first showing, or null where the heading has no address.
function show(heading, reason, force) {
  let link = links.get(heading);
  if (force && !headingAddress(heading)) {
    if (link) retire(link);
    return null;
  }
  if (force && !link) link = makeLink(heading);
  else if (force) {
    revealControl(link.control, heading);
    writeLine(link.control, firstLine(heading));
  }
  if (!link) return null;
  link.shown[force ? "add" : "delete"](reason);
  link.control.classList.toggle("lf-heading-link-shown", link.shown.size > 0);
  return link;
}

export function watchHeadingLinks() {
  // A live sample's URL is private to the page holding it.
  if (document.documentElement.lfSample) return;
  let hovered = null;
  const hover = (heading) => {
    if (heading === hovered) return;
    if (hovered) show(hovered, "hover", false);
    hovered = heading;
    if (heading) show(heading, "hover", true);
  };
  addEventListener(
    "pointerover",
    (event) => {
      if (event.pointerType === "touch") return;
      const target = /** @type {Node} */ (event.target);
      const control = target instanceof Element && target.closest(".lf-heading-link");
      hover(control ? owners.get(control) : headingAt(target));
    },
    { capture: true },
  );
  addEventListener(
    "pointerout",
    (event) => {
      if (!event.relatedTarget) hover(null);
    },
    { capture: true },
  );
  addEventListener(
    "pointerdown",
    (event) => {
      if (event.pointerType !== "touch") return;
      const heading = headingAt(/** @type {Node} */ (event.target));
      if (heading && headingAddress(heading)) focusDestination(heading, "move");
    },
    { capture: true },
  );
  let current = null;
  const stand = (heading) => {
    if (heading === current) return links.get(heading);
    if (current) show(current, "current", false);
    current = heading;
    return heading && show(heading, "current", true);
  };
  onCurrentLocation((node) =>
    stand(node?.nodeType === Node.ELEMENT_NODE ? headingAt(node) : null),
  );
  pageScope("heading", {
    title: "On a section heading",
    root: focused,
    at: () => Boolean(headingOn(focused())),
    when: () => pageQueryAll(HEADING).some((heading) => headingOn(heading)),
    rows: [
      {
        id: "heading.link.copy",
        keys: ["Enter"],
        title: "copy link to section",
        // The link's own control beside the heading takes a finger.
        touch: false,
        // A control made by this press has not drawn its button yet.
        run: async () => {
          const link = stand(headingOn(focused()));
          if (!link) return;
          await customElements.whenDefined(link.control.localName);
          await link.control.updateComplete;
          link.control.shadowRoot.querySelector("button").click();
        },
      },
    ],
  });
}
