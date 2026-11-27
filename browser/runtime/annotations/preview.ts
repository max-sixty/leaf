/* Pointing reads; pressing acts (browser/AGENTS.md, "Pointing reads; pressing acts"):
   the one owner of what a mark, control or value says before a press acts on it.

   Anything may preview, and the innermost under the pointer, the focus or the finger
   does:

   - A control previews its name and its keys without declaring either: its accessible
     name where its face doesn't say it, as where the face shows a symbol or a mark its
     markup names, and each press that reaches it from where the user is
     (control-keys.js, `controlKeys`) as key chips beside its name, which a coarse
     pointer leaves out with every other advertised key. Its face is its own words, a
     select's chosen option rather than every option, and the words of the labels beside
     it. It says a name the control's markup gives where either holds the other's words,
     as a key chip or a count beside a name leaves it said, or where the name is marks
     alone that the face draws and nothing more, as a reaction's emoji, and a name its
     content gives unless it cuts a word of it short. A face that cuts none leaves
     unsaid only the control's quiet words (`.lf-quiet`, records/declared-words.js),
     which the screen doesn't show, as a check's verdict beside a case's title. The preview reads those words
     alone; where key chips stand in it, the control's whole name heads them. A control
     whose face says its name and that no key reaches previews nothing. A field the user
     types in previews nothing: its words are what they read. A control is any native or
     ARIA press, a range and a select among them (dom/control-selectors.js, `PRESSES`), or a
     custom control whose `data-lf-offer` names its press (dom/widget-elements.js,
     `PRESSABLE`). The rest of Leaf's chrome, such as a thread card a walk lands on or a
     pointer rests in, previews no name of its own, since its words are what the user
     reads.
   - An element declares what pointing at it adds as its `lfPreview(route)`, called once
     as its preview shows on that route (`"pointer"`, `"focus"` or `"hold"`), and again
     for each new presentation of the document while the preview stands, so the words
     follow the page, a thread's turn or a link's place, redrawn in place with no fade
     and left as they are where they come back the same: `{name, keys, detail, list,
     at, about, excerpt, unseen}`, every field optional (module-previews.md). On a control its
     lines stand under the control's own name and keys, and its name replaces the
     accessible name where that says more than the face should; `keys` are presses the
     control's own chips leave out, as a grip's activation keys or the keys of a Go-to
     door, each the bindings of its steps, which the face spells as it spells those
     chips (`lines`); `at` is where to stand,
     the declaring element by default, another element or a box in client coordinates
     inside it, as a chart's point, which the preview stands above; `about` is what it
     is about, which it leaves in view as it does the box it stands by, as a margin
     entry's passage or a time's message; `excerpt` asks
     for the face's room for a block of the page; `unseen` keeps the face from sight
     for an element that draws what it shows itself; and `list` is items under the lines,
     `{items, more}`, as the threads standing at one place, of which the face shows as
     many as the room it is held to holds, and under them the words `more(count)` gives
     for the rest, as "and 26 more threads" (`fit`), where another preview's last line
     that fits ends in an ellipsis. When what it says changes under an aim
     that stays inside the element, as a chart's point, it says so (`lf-preview`,
     lib/widget-events.js), and a standing preview redraws in place, or a pointer
     resting on the element or a finger holding it reads it; a preview the user put
     away stays away, whatever the element declares, until they aim again. When its
     preview goes, whatever puts it away, the pointer or focus leaving, the press
     after a finger's hold, Escape or another target's taking its place, though not
     while a focus reading is only suspended out of sight, the element hears
     `lf-preview-ended` (`PREVIEW_ENDED`), a `CustomEvent` dispatched at it alone, whose
     `detail.declared` is what its `lfPreview` returned for the reading that ended, the
     last it returned while that preview stood, a new object for each reading, so a mark it drew for that reading, as a
     chart's ring on its point, comes off then, and one it drew for a reading it has
     declared since stays. It returns null where it adds nothing,
     so the search goes on outward, and false where nothing shows and nothing around it
     may. A widget declares it with no import, as it declares `lfCommands` and
     `lfCopy()`, so off Leaf it reads nothing. What a declaration throws is reported and shows nothing.
   - A `title` is its writer's, and the browser shows it to a pointer: over an element
     the browser's tooltip speaks for, its own title or one around it, a pointer reads
     no preview, so no second tooltip stands beside the browser's. Focus and a finger,
     which the browser's tooltip never reaches, read its words as a line under the
     element's name, or as its name where it has none. Nothing here writes or removes a
     title, so it says what its writer last wrote and names what it names. Leaf's own
     controls declare their words as `lfPreview` and write no title on Leaf (the
     library's control constructors, lib/controls.js, write one off Leaf,
     where the browser's tooltip is the only reading).
   - A range with no element of its own, as a passage mark is, is its owner's to hit
     test, so the owner says where the pointer rests (`pointRange`), as often as it
     likes, and this module does the rest, placing the preview by the line the pointer
     is on.
   - A link an author wrote into the page previews the place it names, and what that
     place holds (place-preview.js), since that is what pressing it opens.
   - Whatever supplies it, a reading says only what its target's face doesn't show
     whole: a line the face shows uncut goes, as does a press whose key chip it draws or
     the command hints label it with (command-hints.js, `drawnKeys`), as a playground's
     commit wears its `1`, and a reading left with only the face's own words shows
     nothing (`beyondFace`), so a status declaring its words for where its row, or a box
     around it, cuts them previews only while they're cut. Reading a face stops at a few
     lines (`FACE`), so a preview over a long section costs what one over a button does.

   Nothing standing open (`aria-expanded="true"`) previews, since what pressing it opens
   is already in front of the user, and the search goes on outward from it, as it does
   from a proxy, whose thing previews for it. A preview is read once, as it shows, so its
   words keep still while the user reads them, as a status that ages beneath them would
   not.

   Every preview wears one face (`.lf-preview`, chrome.css): its name on the first
   line with its key chips, then its lines of detail, in one type and colour. Only the
   words Leaf itself says keep their italic (base/voice.js), as they do on every seat. A
   preview that quotes a block of the page, as a link's place does, takes the face's
   excerpt room (`data-lf-face="excerpt"`): the same type, colours and spacing, wider.
   An element that draws its preview itself, as the dial hangs each depth's page under
   its button, declares it `unseen` (`data-lf-face="unseen"`): the face stands and ends
   as any other, Escape's first step and a screen reader's words on focus, and nobody
   sees it.

   One preview stands at a time, in one element: a hint popover (`popover="hint"`), in
   the top layer, so it stands over an open popover around its target, and a hint
   closes no popover the user opened. While a modal dialog stands, it stands inside the
   topmost one, since a modal makes everything outside it inert, a top-layer popover
   too, and the pointer couldn't reach a preview there. It holds no control, so it is
   no layer the keyboard tiers its scopes over (layer-stack.js). A pointer's preview
   takes the pointer, a point's excepted (below), so the pointer can cross from the
   target onto it and read it there; leaving it puts it away after `LINGER`, and
   reaching another target from it shows that one at once (WCAG 1.4.13, "Hoverable").

   Where it stands is one decision (`stand`), made again whenever what it rests on may
   have changed, and drawn by the browser from that decision alone, with no fallback of
   its own to disagree with it. It is shown with an element as its source
   (`showPopover({source})`), whose box is its implicit anchor (`position-anchor:
   auto`): the target, or a range's line by the element holding the range, a declared
   box by the declaring element and a shape by its drawing's HTML host, each box at its
   offsets inside that element. So the browser
   carries it with the element through every scroll, a shadow tree's included, and this
   module decides again as its words or the box they stand by change, as a box holding
   the element scrolls, and as the window resizes or a pinch or an on-screen keyboard
   changes what it shows; a hover writes nothing on the target, which observers of the
   page's boxes would hear. It stands only while some of the box it stands by shows
   past every box clipping it; otherwise a pointer's or a finger's reading ends, and
   focus's is suspended, the preview closed, until that box shows again or focus moves
   on, so a chart's point scrolled out of a box takes its preview along, and a focused
   one brings it back. Its side's
   room is the room it holds clear, inside the part of the window the user sees, of
   every other control, tested every 23 px across the box it would draw, and of what
   the preview is about (the box it stands by and the declaration's `about`); a box
   around the target is a control there only where a press acts on it, as a card a
   press opens around a chart is and a scrolling box or a widget drawing its own
   content isn't. Another thread's passage mark is such a control, though it is a range
   with no element of its own, which its owner finds for the test (`declareRanges`), on
   the paragraph's other lines too, so a mark's preview doesn't stand over
   the mark on the next line, where the press the pointer goes on to make only puts the
   preview away. For a finger, whose
   hand hides what lies below the touch, below holds none. Where it stands now comes
   first, its top corner on the edge it stands by at the same offsets from the box it
   stands by, and it stays there while
   that room holds a whole line, held to it and its words fitted to it as to any room
   (`fit`), so words that grow never move it under the user's aim (browser/AGENTS.md,
   "The page holds still under the user's aim") nor cover anything. A new aim inside the
   element it stands for (`lf-preview` with `aim`), as a chart's next point, keeps
   its side by the new box, standing by the edge that side stands by, its bottom above
   the box and its top below or beside it, where that side's room holds the new
   reading whole, so the preview rides along the drawing on one side as the pointer
   sweeps it, and a longer reading grows away from its point or stands afresh. Afresh, as for a new target or a corner whose room no longer holds a line, it takes
   the first side whose room holds it whole, in order: below, then above, from the
   box's start edge and then its end edge, so a right-to-left target's starts at its
   right edge, each slid in along that edge until the window holds it, still across
   the box; beside, toward the nearer window edge first; then centred across the
   window, a finger's and a point's trying above first. Else it takes the side whose
   room holds the most whole lines, held there, so it cuts lines only where no side
   holds them all. Only where no side's room
   holds a line does it stand over what it covers, on the side the window gives the most
   room, over the target itself where no side holds a line at all, and take no pointer,
   so the pointer reaches what it covers (`data-lf-covers`); where even that holds none,
   it shows nothing. A preview that stands for a box inside its declaring element, as
   a chart's point, takes no pointer either, wherever it stands, so the pointer goes on
   reading the element beneath it: what it covers there, as the chart's next point, is
   that element's own, which no side's room is tested against, since only other
   controls and what the preview is about are. A pointer over the box of a preview that
   lets it through, off what the preview is about and over nothing there the user aims
   at, previewing or not, still keeps the preview, as one on a preview that takes it
   does (`onPreview`), so a pointer crossing from a point to its words keeps them past
   the chart's edge, and one reaching a field, in the passage's own paragraph or
   elsewhere, takes the field. Each length is compared at the precision layout keeps,
   so a room and the line it is asked to hold, read off two boxes at one edge, are one
   length. A target thinner than the grid's step can stand under it unseen, and some of
   Leaf's own are thinner, as the trace timeline's marks are, which declare their lane
   as what they are about so their previews keep clear of it. No sampling proves a target
   absent, so that is the grid's stated limit, as the holder's own box, which it
   doesn't test, is its bound on cost.

   Its routes:

   - A pointer resting on a target for `DWELL` shows its preview, fading in; moving onto
     another target within `WARM` of the last one the user saw going shows the next at
     once and with no fade, so reading along a row of controls waits once and then moves
     one preview along the row. Where the next one stands by the element the last one
     stands by, as each of a widget's controls may stand its preview by the widget, the
     preview redraws where it stands, so the reading changes under a face that holds
     still. A pointer that leaves its target for nothing, as on its way onto the
     preview, puts the preview away after `LINGER`. A press hides it, and so does any key
     but Escape, as the platform's tooltip goes, while the key does its own work; the
     target then stays quiet until the pointer comes back to it. A modifier alone is
     half a press rather than a key (dom/control-selectors.js, `MODIFIER_KEYS`), so ⌥ held
     to aim a comment leaves standing the preview of the point it aims at. A target that
     arrives under a pointer the user hasn't moved shows nothing, so news landing under
     a resting pointer never covers what the user reads, and nor does one a pointer
     reaches while it carries a press, as in a drag. A target the pointer came to
     shows after its dwell even where it redraws under the pointer meanwhile. A tab
     the user leaves takes its preview away.
   - Keyboard focus the browser shows (`:focus-visible`) shows its target's preview at
     once, with no fade, where the user aimed it there by a Tab or Shift+Tab, or by a
     placement standing in for one (`step`), the cause its mover gives (dom/focus.js,
     `focusDestination`): Tab is the keyboard's pointing, a step to the next control
     the user may press. Leaving the target hides it. Focus any command places shows
     nothing: a walk or an arrow key landing (`move`), as `m` lands on an On Me item's
     margin entry, a surface placing focus as it opens, as the Page Map's first row,
     and focus handed back as a surface closes or as Escape backs the user out
     (`return`). What the user asked a command for is the place it lands on, already in
     front of them, so a preview there would only cover what they came to read and take
     their next Escape. `K` (`preview.show`) reads the preview where focus stands
     on demand, whatever put it there and in whatever layer, as an editor's hover key
     does, so a landing's preview stays one key away.
   - `K` reads at the caret instead where the caret stands in what focus is on, or
     anywhere while focus rests on the body, and the user can see it (`here`); for a
     selection, the caret is the end that Shift and an arrow move (dom/native-selection.js,
     `userCaret`). Caret browsing (F7), which Chromium and Firefox offer and
     Safari doesn't, walks the caret through words that take no focus, such as an age's
     (age.js), so an element that previews to a resting pointer previews to the keyboard
     there with no Tab stop of its own. A Tab stop for each age was the alternative, and
     a list of forty ages would have taken forty stops. Where the caret stands on
     something inside what focus is on, as on an age in a focused row, the next key puts
     that reading away, as it puts a pointer's away, since the keys after `K` walk the
     caret on. A declaration that stops being true, as a grip's once its card is
     grabbed, says so (`lf-preview`), which redraws a preview standing on focus and
     opens none.
   - A screen reader hears every preview of what focus is on, whatever supplied it, as
     the focused element's description (`ariaDescribedByElements`) while it stands,
     except a
     control's own, which says what its accessible name and `aria-keyshortcuts` already
     do, and a proxy's, which describes what it stands for with its own markup, as a
     gloss's does.
   - A finger held on a target shows its preview at the platform's own long press, as
     the browser says it (`contextmenu`), so a press the platform takes for a tap, as a
     user's longer touch-and-hold setting makes a slow one, presses; a WebKit touch
     engine says nothing (WebKit bug 213953), so there it shows after `HOLD`
     (notes/browser-support.md, "A touch long press in WebKit"). The finger reads its
     neighbours by sliding onto them: one of the same parent shows its own instead, in
     place where it stands by the same element, as the pointer's next does. A
     hold is the touch form of pointing, so it reads and presses nothing, as a
     platform's long press follows no link and its tooltip clicks nothing: once the hold
     has shown a preview, the touch's end is cancelled (`touchend`), wherever the finger
     ends, so the browser makes no click of it, which would press the target and, as a
     click outside a hint popover, close the preview. The preview stands until the next
     press: a tap on its target, which presses, or a touch elsewhere or a finger's
     scroll, which put it away, as iOS's link preview does. A press let go before the
     hold reads is a tap, which shows nothing and which the browser's click presses. A
     press with a
     modifier is not this gesture (`plainPress`). Touch capture is released at the press
     so the slide is heard over each neighbour, and a finger that starts scrolling ends
     the hold with `pointercancel`, which puts its preview away; a target that should
     not scroll from a press says so with `touch-action`. While a preview is held, the
     platform's long-press menu stays shut. A finger holding where no element previews
     holds whatever range its owner says it rests on (`pointRange`), and slides only as
     the owner says; its preview stands above the line and, as any hold's, its release
     presses nothing. A finger that only moves, as a pointer would, reads no range, and
     the author's element holding the range wears no `data-lf-touch-held`.
   - While a preview stands, by pointer or by focus, it is Escape's first step and the
     press does nothing else (dom/keyboard/AGENTS.md, "Escape"): it covers what lies under
     it, so the user can put it away without moving the pointer or focus, and without
     losing the surface they are in (WCAG 1.4.13, "Content on Hover or Focus"). A second
     Escape takes the step the first would have. Off a served page, where the register
     holds no page scopes, the key listener takes the same step.

   Each pointer boundary costs the path it walks, the nodes under the pointer, and a
   preview showing costs what it reads, for a control the page's commands, and a few
   hit tests for its side, never the page's elements (root AGENTS.md,
   "Responsiveness"). The target a finger held wears `data-lf-touch-held` while its
   preview stands, so its surface can keep it where the finger held it (margin-layout.js,
   `HELD`).

   Decisions: a pointer's dwell, 500 ms, is the platforms' own tooltip delay (Windows'
   initial delay, a little under Radix's 700 ms and the 650 ms Wikipedia's link previews
   wait), so a pointer passing over a control or resting on the words the user reads
   shows nothing, and once one preview has shown the next comes at once, as theirs do.
   The user asked for a longer wait than 200 ms, which showed a preview wherever the
   pointer paused on its way, each a control's name the user could already see beside a
   key they hadn't reached for. Leaving for nothing keeps the preview `LINGER`, 200 ms,
   long enough to cross onto it.
   A finger's is the platform's long press, since a press let go sooner is a
   tap, which presses: Android's, as the user set it, and 500 ms where WebKit says
   nothing, UIKit's default for a long press. A preview says its words whole, wrapping
   where they run long. It finds its neighbours by a few hit tests in the room it would
   take. A preview that lets the pointer through, as one standing over what it covers,
   stays while the pointer is over it (`onPreview`), so a chart's point's words past
   the chart's edge and a covering control's words can both be read.
   Rejected: a finger reading after the pointer's 200 ms, its release pressing the
   target it ended on and putting the preview away, since a finger then can't read
   without acting short of sliding off before letting go, which on touch often scrolls
   instead: one that holds a link to read where it goes follows it as it lets go, and
   one that holds a thread's words opens the thread; a label that cuts a margin
   entry's question to one line; measuring every entry on the page to stand clear of
   them, a page-wide read on every hover; a preview that takes no pointer, so a covered
   neighbour takes the pointer through it but the pointer can't stay on the preview to
   read it; Escape putting a preview away and taking its own step too, which closes the
   thread card the user is reading, since the preview covers its first line; taking a
   title off its element as the pointer comes, to read it on every route with no second
   tooltip beside it, which keeps words a writer has since removed and leaves a control
   its title named unnamed; a preview that lets the pointer through going as the
   pointer leaves its target for it, though the pointer is on its words and on no other
   target there; counting every element wearing `data-lf-offer` as a control, so a
   thread card previews its accessible name, its own first words, to a pointer resting
   in it and to a `t` walk landing on it, where the preview takes the Escape that lets
   go of the thread; a walk's or an arrow key's landing previewing too, unless it lands
   in a surface that opened since the user's last input, which a record of each
   layer's opening input tells apart, so the `m` walk previews the margin entry it
   lands on, a thread the user is about to read, over the words beside it;
   reading a control off `data-lf-offer` alone, a press marker, which
   left out Leaf's own ranges and selects, since they wear an empty one;
   `interestfor`, which gives a control the same three routes natively but ships only
   in Chromium; the platform's
   `title` alone for Leaf's controls, which no finger or keyboard reads and which can't
   draw a key chip; holding a `title` off only while the pointer rests within its
   element and putting it back as the pointer leaves, which writes it twice a hover,
   each a change of the element's description a screen reader hears; naming the target
   as an anchor, which writes its style, so the margin laid out again the first time
   each paragraph previewed; insets measured from the box that scrolls the target, which
   lost the target as it moved inside that box and stood by the layout viewport; a
   box in the chrome copied onto a range's line or a declared box, which kept still as
   the box scrolling the target moved; `position-try-fallbacks` behind the side test,
   which drew another box than the one tested; a preview that scrolls, whose detail no
   key reached and a pointer passed through where it covered a target; keeping the
   preview inside the box around its target, which only a script measuring that box
   could do, where the window's edge serves; placing it afresh at each new aim inside
   its element, which flipped a chart's preview between above and below its points
   four times in one sweep along a chart at the window's top; and keeping its top
   corner for a new aim, which held a three-line reading above a point to the one line
   between that corner and the point. */
import { html, nothing, render } from "/vendor/lit.js";
import {
  carryChromeStyles,
  closeNativeLayer,
  nativeLayers,
  showNativeLayer,
} from "../dom/keyboard/layer-stack.js";
import { controlKeys } from "../dom/keyboard/control-keys.js";
import { drawnKeys } from "../readings/key-badges/command-hints.js";
import { advertisesKeys, spell } from "../dom/keyboard/bindings.js";
import { focused, onCurrentLocation, typesText } from "../dom/focus.js";
import { userCaret } from "../dom/native-selection.js";
import { pageScope } from "../dom/keyboard/register.js";
import { notice } from "../transport/notifications.js";
import { offlineInteractive } from "../state/context.js";
import { watchPresentation, whenDocumentPresented } from "../state/semantic-state.js";
import { plainPress } from "../lib/keys.js";
import {
  isElement,
  isHTML,
  overIn,
  renderedParent,
  renderedUnder,
  under,
} from "../lib/shadow-tree.js";
import { PREVIEW, PREVIEW_ENDED } from "../lib/widget-events.js";
import { atLayoutPrecision, keeps, layoutPx } from "../lib/keeps.js";
import { nextRender, sizeObserver } from "../lib/frame-pass.js";
import { paintCloseRequests } from "../dom/keyboard/close-requests.js";
import { atClock, clockNow } from "../state/presence.js";
import { watchOwner } from "../dom/arrivals.js";
import { actionClass } from "../lib/control-faces.js";
import { aimableAt, PRESSABLE } from "../dom/widget-elements.js";
import { MODIFIER_KEYS, PRESSES, WORKS } from "../dom/control-selectors.js";
import {
  clippedContents,
  clippedRect,
  drawsText,
  lined,
  placeHolder,
  seenRect,
  shownBox,
  shownParts,
  shownWindow,
  visualViewport,
} from "../dom/geometry.js";
import { hasArea, holds } from "../dom/rect.js";
import { linkPreview } from "./place-preview.js";
import { markRoom } from "../readings/mark-room.js";
import { anchorBox } from "../dom/css-anchors.js";

import type { Box } from "../base/box.js";
import type {
  Words,
  Presses,
  List,
  Preview,
  Declared,
  Route,
  Read,
} from "../base/preview-declaration.js";
import type { ClipCache } from "../dom/geometry.js";
type Reading = {
  name: Words | null;
  keys: Presses;
  detail: Words[];
  list: List | null;
  at: Element | Box | null;
  about: Element | null;
  excerpt: boolean;
  unseen: boolean;
  restates: boolean;
  declared: Preview | null;
};
type Target = Element | Range;
type Shown = {
  from: Target;
  target: Target;
  holder: Element;
  route: Route;
  read: Read | null;
  at: { x: number; y: number } | undefined;
  line?: number;
  within?: Box | null;
  away?: boolean;
  reading: Reading;
  clock: number;
  stop: () => void;
  described: {
    el: Element;
    attribute: string | null;
    elements: readonly Element[] | null;
  } | null;
};
type Hold = {
  pointerId: number;
  node: Node | null;
  parent: Element | null;
  element: Element | null;
  range: Range | null;
  says: Read | null;
  at: { x: number; y: number };
  armed: boolean;
  read: boolean;
  timer: ReturnType<typeof setTimeout> | undefined;
};

const DWELL = 500;
const LINGER = 200;
const HOLD = 500;
// Whether the engine says nothing as a touch press grows long: WebKit, which alone
// exposes `GestureEvent`, desktop Safari's included, where no touch reaches a hold.
const holdsUntold = () => "GestureEvent" in window;
const WARM = 400;
// The timers above, for a reader outside the page that runs the page's clock past one
// (check-api.js).
export const PREVIEW_TIMERS = Object.freeze({ DWELL, LINGER, HOLD, WARM });

// The one element every preview draws in.
const tip = document.createElement("div");
tip.className = "lf-ui lf-preview";
tip.id = "lf-preview";
tip.setAttribute("popover", "hint");
tip.setAttribute("role", "tooltip");
// What it shows, which fades in inside the box the browser places: an anchored box that
// fades is placed again in every frame of the fade, as Chromium 156 lays out the page's
// root for it, a cost that grows with the page.
const body = document.createElement("div");
body.className = "lf-preview-face";
tip.append(body);
// The chrome's own box the preview stands in, wherever it stands, a modal dialog of the
// page's included, so the chrome's sheet dresses it and the margin's observer hears none
// of its writes (margin-layout.js, `SURFACES`). It takes no box of its own in the
// dialog's layout. Its mark is a sibling the preview moves around (`open`).
const stage = document.createElement("div");
stage.className = "lf-chrome";
stage.style.display = "contents";
const mark = document.createElement("span");
mark.hidden = true;
stage.append(mark, tip);
// The chrome the preview stands in when no modal dialog does.
let home: Element | null = null;

// The one face: the name with each press as key chips, then each line of detail.
const chip = (step: string) => html`<kbd class="lf-key-badge">${step}</kbd>`;
const chips = (steps: readonly string[]) =>
  html`<span class="lf-preview-keys">${steps.map(chip)}</span>`;
const detailLine = (line: Words) =>
  html`<span class="lf-preview-detail">${line}</span>`;
const item = (line: Words) =>
  html`<span class="lf-preview-detail lf-preview-item">${line}</span>`;
const face: (reading: Reading) => unknown[] = ({ name, keys, detail, list }) => [
  name || keys.length
    ? html`<span class="lf-preview-name"
        ><span class="lf-preview-word">${name}</span>${keys.map(chips)}</span
      >`
    : nothing,
  ...detail.map(detailLine),
  ...(list
    ? [...list.items.map(item), html`<span class="lf-preview-more"></span>`]
    : []),
];

// A preview longer than the room it stands in shows the lines that fit: the block the room
// ends in keeps the lines the browser wraps it to that fit there, its last ending in an
// ellipsis (`data-lf-clamp`, a line clamp), and the blocks after it stay laid out, unseen
// and unheard (`visibility: hidden`), so what it shows changes nothing about its size.
// Where the room ends between two blocks, the one before keeps every line it has, clamped
// to them, and ends in the clamp's ellipsis too, which a line of no height after its
// words gives it reason to draw (`data-lf-cut`, chrome.css): an ellipsis written after
// the words would wrap a line that nearly fills the face onto one the room doesn't hold,
// and would change the lines the next fit reads. A list's items go whole, and its
// count, at the foot in their place, says how many more there are in the words its
// declaration gives. No preview scrolls: what pressing its target opens says the rest.
// The room alone decides it, measured from the face's top, never from where a past fit
// left the face's foot, and each place is written once, with its final value, so the
// lines a past fit clamped are read as they lay out whole.
function fit(reading: Reading, room: number) {
  const { blocks, counted } = faceLines(reading);
  const more = body.querySelector<HTMLElement>(":scope > .lf-preview-more");
  const { list } = reading;
  const was = clampedNow();
  // Where the room it is held to ends for its lines, measured from its top, a list's
  // count under them.
  const end = wholeHeight() > room ? room - counted : Infinity;
  const over = blocks.findIndex((at) => at.top + at.lines * at.line > end);
  // The block the room ends in, cut by line where it holds words, not a list's item.
  let clamp: { el: HTMLElement; lines: number } | null = null;
  const block = blocks[over];
  if (block && !block.item) {
    let fits = 0;
    while (fits < block.lines && block.top + (fits + 1) * block.line <= end) fits += 1;
    if (fits < block.lines && (fits >= 1 || over === 0))
      clamp = { el: block.el, lines: Math.max(1, fits) };
  }
  const kept = over < 0 ? blocks.length : clamp ? over + 1 : Math.max(1, over);
  // The room ends between two blocks: the last kept says there is more.
  const last = blocks[kept - 1];
  const cut = !list && !clamp && kept < blocks.length && last ? last.el : null;
  if (cut && last) clamp = { el: cut, lines: last.lines };
  if (was && was !== clamp?.el) {
    keeps(was, "data-lf-clamp", null);
    was.style.removeProperty("--lf-preview-lines");
  }
  if (clamp) {
    keeps(clamp.el, "data-lf-clamp", "");
    clamp.el.style.setProperty("--lf-preview-lines", String(clamp.lines));
  }
  blocks.forEach(({ block: line, el }, at) => {
    line.style.visibility = at < kept ? "" : "hidden";
    keeps(el, "data-lf-cut", el === cut ? "" : null);
  });
  if (!list || !more) return;
  const hidden = blocks.length - kept;
  if (hidden) render(list.more(Math.min(hidden, list.items.length)), more);
  more.style.visibility = hidden ? "" : "hidden";
}
// The block a past fit clamped to the lines that fit, if any.
const clampedNow = () => body.querySelector<HTMLElement>("[data-lf-clamp]");
// The face's whole height, laid out unclamped and unheld, whatever room it was last held
// to: its drawn height where it is whole, which is fractional where scrollHeight rounds,
// and what a past fit's clamp holds back added in.
function wholeHeight() {
  const was = clampedNow();
  if (was) return body.scrollHeight + was.scrollHeight - was.clientHeight;
  return body.scrollHeight > body.clientHeight + 1
    ? body.scrollHeight
    : body.getBoundingClientRect().height;
}
// The face's lines as it lays out whole, read from layout whatever room a past fit held
// it to, so the fit and the decision count a line alike: each block, the element its
// lines wrap in (a name's words, else the block), the offset of its top from the face's
// top, its line's height as laid out and its lines, what a past fit's clamp holds back
// added in; and the room each whole line needs from the face's top, the face's foot
// padding included. A list's lines short of all of them need room for its count under
// them too. A block's lines shown are read off its box, never off the count a past
// clamp was given: the block may since hold another reading's words, which the face
// draws into the same elements, and a clamp holds back nothing of a part the browser
// lays out as a grid, such as a table's, so its box stands whole.
function faceLines(reading: Reading): {
  blocks: {
    block: HTMLElement;
    el: HTMLElement;
    item: boolean;
    top: number;
    line: number;
    lines: number;
  }[];
  rooms: number[];
  padEnd: number;
  counted: number;
} {
  const faceTop = body.getBoundingClientRect().top;
  const padEnd = parseFloat(getComputedStyle(body).paddingBlockEnd);
  const more = body.querySelector<HTMLElement>(":scope > .lf-preview-more");
  // The count line measures before it says anything, its first words those for all the
  // items, the longest it can say.
  if (reading.list && more && !more.textContent)
    render(reading.list.more(reading.list.items.length), more);
  const counted = reading.list && more ? more.getBoundingClientRect().height : padEnd;
  let held = 0;
  const blocks = (
    [
      ...body.querySelectorAll(
        ":scope > .lf-preview-name, :scope > .lf-preview-detail",
      ),
    ] as HTMLElement[]
  ).map((block) => {
    const el = (block.querySelector(":scope > .lf-preview-word") ??
      block) as HTMLElement;
    const box = el.getBoundingClientRect();
    const shown = Math.max(
      1,
      Math.round(box.height / parseFloat(getComputedStyle(el).lineHeight)),
    );
    const line = box.height / shown;
    const lines = Math.max(shown, Math.round(el.scrollHeight / line));
    const top = box.top - faceTop + held;
    held += (lines - shown) * line;
    return {
      block,
      el,
      item: block.classList.contains("lf-preview-item"),
      top,
      line,
      lines,
    };
  });
  const bottoms: number[] = [];
  for (const { top, line, lines } of blocks)
    for (let n = 1; n <= lines; n += 1) bottoms.push(top + n * line);
  const rooms = bottoms.map((bottom, at) =>
    atLayoutPrecision(bottom + (at < bottoms.length - 1 ? counted : padEnd)),
  );
  // A name's key chips stand on its first line and may stand taller than its words.
  const keys = body.querySelector(":scope > .lf-preview-name > .lf-preview-keys");
  if (keys && rooms.length) {
    const chips = atLayoutPrecision(
      keys.getBoundingClientRect().bottom - faceTop + padEnd,
    );
    if (chips > (rooms[0] ?? 0) && (blocks[0]?.lines ?? 0) === 1) rooms[0] = chips;
  }
  return { blocks, rooms, padEnd, counted };
}

const CONTROL = `${PRESSES}, ${PRESSABLE}`;
// A proxy stands in for what the pointer takes by itself (control-faces.js, `proxy`),
// so what it stands for previews: a gloss's proxy, its phrase.
const PROXY = `.${actionClass("proxy")}`;

// The words a `title` gives `el`. A frame's title is its accessible name, not words a
// tooltip shows.
const titleOf = (el: Element) =>
  el.localName === "iframe" ? null : el.getAttribute("title") || null;
// Whether the browser shows its own tooltip over the innermost node of `path`: the
// nearest element along it with a title says, and an empty one says none.
function tooltipped(path: Iterable<EventTarget>) {
  for (const node of path)
    if (isElement(node) && node.hasAttribute("title")) return Boolean(titleOf(node));
  return false;
}

// The words of `text` alone, as one reads them, punctuation and case aside.
const wordsOf = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
// What `text` draws, its spaces aside, as a face of marks with no words is read.
const marksOf = (text: string) => text.replace(/\s+/gu, "");
// The elements labelling a form control: its `<label>`s, and what `aria-labelledby`
// names, as a playground's words beside its range do.
function labelsOf(control: Element): Element[] {
  const { labels } = control as { labels?: NodeListOf<HTMLLabelElement> | null };
  return [...(labels ?? []), ...labelledBy(control)];
}
// The elements a control's `aria-labelledby` names, found by id in its tree. Not its
// `ariaLabelledByElements`: Firefox's content process crashes once the page and an
// isolated world, such as Playwright's role locator, have both read that property
// (https://bugzilla.mozilla.org/show_bug.cgi?id=2090055).
function labelledBy(control: Element): Element[] {
  const root = control.getRootNode() as Document | ShadowRoot;
  if (!("getElementById" in root)) return [];
  return (control.getAttribute("aria-labelledby") ?? "")
    .split(/\s+/)
    .flatMap((id) => (id && root.getElementById(id)) || []);
}
// The text of the labels naming a form control, less the control's own where a label
// holds it, as a select's options: its name, whether or not the label shows, and no more
// than a face's worth (`FACE`).
function labelText(control: Element) {
  const runs = [];
  let room = FACE;
  for (const label of labelsOf(control)) {
    const walker = faceWalker(label, control);
    for (let node = walker.nextNode(); node && room > 0; node = walker.nextNode()) {
      const text = (node as Text).data;
      room -= 1 + text.trim().length;
      runs.push(text);
    }
  }
  return runs.join(" ").replace(/\s+/g, " ").trim();
}
// The most a face holds, counting each run of text and each character of its words: a
// control's, a mark's or a row's few lines. A target holding more is content its
// preview stands over, whose words the face rule leaves unread, so reading a face costs
// as little over a long section as over a button.
const FACE = 300;
// The runs of text under `root` that a face or a label's text reads. The walk passes
// over `skip` and a select's or datalist's options without entering them, so they cost
// no room: the control's words aren't its label's, and a list shows only its chosen
// option (`controlFace`), however many it holds.
const faceWalker = (root: Element, skip: Element | null) =>
  document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      node instanceof Text
        ? NodeFilter.FILTER_ACCEPT
        : node === skip || (node as Element).matches("select, datalist")
          ? NodeFilter.FILTER_REJECT
          : NodeFilter.FILTER_SKIP,
  });
// Whether a listener hears the text `parent` holds as part of `root`'s name: the browser
// draws it, and nothing inside `root` hides it with `aria-hidden`, as a menu row's key
// chip is hidden.
const heardIn = (parent: Element | null, root: Element) =>
  Boolean(parent && drawsText(parent) && !overIn(parent, '[aria-hidden="true"]', root));
type Face = {
  words: string;
  joined: string;
  marks: string;
  partial: boolean;
  cut: boolean;
  quiet: string;
  chips: string[];
};
// What `root` shows the user whole, less any part inside `skip`, or null where it holds
// more than a face. A run of its text counts where the browser draws it (`drawsText`) and
// every box that clips it leaves it whole (`clippedContents`), so words an ellipsis, a
// clamp to a few lines, a visually hidden label or a panel scrolled past them cut short
// don't count. `words` reads the runs apart, as a row's words and its key chip stand, and
// `joined` together, as a word split by its markup reads, and `marks` what it draws
// with its spaces aside, as a reaction's emoji is read; `partial` says some of its words
// or numbers don't show, so the face can't stand for a name it only begins, and `cut`
// that some of those are words a listener hears (`heardIn`). `quiet` is the quiet words
// a listener hears in `root` (`.lf-quiet`, records/declared-words.js), which the screen never
// shows, so they aren't cut. `chips` are the key chips it shows, in order.
function faceOf(root: Element, skip: Element | null = null): Face | null {
  const walker = faceWalker(root, skip);
  const range = document.createRange();
  const clips: ClipCache = new Map();
  const runs = [];
  const quiet = [];
  const chips = [];
  let partial = false;
  let cut = false;
  let room = FACE;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node as Text;
    room -= 1 + text.data.trim().length;
    if (room < 0) return null;
    if (!/\S/.test(text.data)) continue;
    const parent =
      text.parentElement ??
      (text.parentNode instanceof ShadowRoot ? text.parentNode.host : null);
    const heard = heardIn(parent, root);
    if (parent && overIn(parent, ".lf-quiet", root)) {
      if (heard) quiet.push(text.data);
      continue;
    }
    range.selectNodeContents(text);
    const at = range.getBoundingClientRect();
    const left =
      parent && hasArea(at) && (heard || drawsText(parent))
        ? clippedContents(at, parent, clips)
        : null;
    if (
      !left ||
      left.left > at.left + 0.5 ||
      left.top > at.top + 0.5 ||
      left.right < at.right - 0.5 ||
      left.bottom < at.bottom - 0.5
    ) {
      const says = /[\p{L}\p{N}]/u.test(text.data);
      partial ||= says;
      cut ||= says && heard;
      continue;
    }
    runs.push(text.data);
    if (parent && overIn(parent, "kbd.lf-key-badge", root))
      chips.push(text.data.trim());
  }
  return {
    words: wordsOf(runs.join(" ")),
    joined: wordsOf(runs.join("")),
    marks: marksOf(runs.join("")),
    partial,
    cut,
    quiet: quiet.join(" ").replace(/\s+/g, " ").trim(),
    chips,
  };
}
// What a control and its labels show, or null where it holds more than a face. A select
// shows the option chosen, not the rest. Its chips are its own and the keys the command
// hints label it with, as Done's digit or a playground's commit's `1`. The words it cuts
// and its quiet words are its own, the words a name from its content holds.
function controlFace(control: Element): Face | null {
  const chosen =
    control instanceof HTMLSelectElement
      ? (control.selectedOptions[0]?.textContent ?? "")
      : null;
  const own =
    chosen === null
      ? faceOf(control)
      : {
          words: wordsOf(chosen),
          joined: wordsOf(chosen),
          marks: marksOf(chosen),
          partial: false,
          cut: false,
          quiet: "",
          chips: [],
        };
  if (!own) return null;
  const faces = [
    ...labelsOf(control).flatMap((label) => faceOf(label, control) ?? []),
    own,
  ];
  const all = (read: "words" | "joined") =>
    faces
      .map((face) => face[read])
      .filter(Boolean)
      .join(" ");
  return {
    words: all("words"),
    joined: all("joined"),
    marks: faces.map((face) => face.marks).join(""),
    partial: faces.some((face) => face.partial),
    cut: own.cut,
    quiet: own.quiet,
    chips: [...own.chips, ...drawnKeys(control)],
  };
}
// Whether `face` shows `line` whole, read apart or together. A line of marks with no
// words, as a reaction's emoji, it shows where it draws those marks and nothing else.
const shows = (face: Face, line: Words | null) =>
  typeof line === "string" &&
  (/\p{L}/u.test(line)
    ? [face.words, face.joined].some((words) =>
        ` ${words} `.includes(` ${wordsOf(line)} `),
      )
    : !wordsOf(line) && Boolean(face.marks) && face.marks === marksOf(line));
// Whether a control's face says its name: the name's words stand in it, as beside a key
// chip or a count, or, where all its words show, its words stand in the name, as a
// symbol's short word under its longer label. A count alone, as a folded list's "1"
// beside its mark, names nothing; a name of marks alone, as a reaction's emoji, the
// face says where it draws just those marks (`shows`).
const faceSays = (face: Face, name: string) =>
  (/\p{L}/u.test(face.words) &&
    (shows(face, name) ||
      (!face.partial &&
        [face.words, face.joined].some((words) =>
          ` ${wordsOf(name)} `.includes(` ${words} `),
        )))) ||
  (!wordsOf(name) && shows(face, name));
// A control's name as its markup gives it, short of its content.
function markupName(control: Element) {
  const label = control.getAttribute("aria-label")?.trim();
  if (label) return label;
  const by = labelledBy(control);
  if (by.length)
    return by
      .map((el) => el.textContent.trim())
      .join(" ")
      .trim();
  return labelText(control) || titleOf(control) || "";
}
// The name a control's content gives it, as a screen reader reads it: the words the
// browser draws, each box's apart and a word its inline markup splits whole, less what
// `aria-hidden` hides, as a menu row's key chip.
function contentName(control: Element) {
  const walker = document.createTreeWalker(control, NodeFilter.SHOW_TEXT);
  let name = "";
  let last: Element | null = null;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const parent = node.parentElement;
    if (!parent || !heardIn(parent, control)) continue;
    if (last && apart(last, parent, control)) name += " ";
    name += (node as Text).data;
    last = parent;
  }
  return name.replace(/\s+/g, " ").trim();
}
// Whether a box's edge falls between text in `a` and text in `b`, both inside `root`: an
// element on either's way up to the one holding both lays out as a box of its own.
function apart(a: Element, b: Element, root: Element) {
  const boxed = (from: Element, other: Element) => {
    for (
      let el = from as Element | null;
      el && el !== root && !el.contains(other);
      el = el.parentElement
    ) {
      const { display } = getComputedStyle(el);
      if (display !== "inline" && display !== "contents") return true;
    }
    return false;
  };
  return boxed(a, b) || boxed(b, a);
}

// What `node` declares, read once as its preview shows on `route`. A declaration that
// throws is a package's bug, reported where its author will see it, and says nothing.
function declaration(node: Element, route: Route): Declared {
  const declared = node.lfPreview;
  if (typeof declared !== "function") return null;
  try {
    return declared.call(node, route);
  } catch (error) {
    reportError(error);
    return null;
  }
}

// Whether the search stops at `node` to read it: it declares a preview, carries a
// `title`, or is a control.
const mayPreview = (node: Element) =>
  typeof node.lfPreview === "function" ||
  Boolean(titleOf(node)) ||
  (node.matches(CONTROL) && !typesText(node));

/** Read `declared` into the face's lines: the name first, then each line of detail, each
 * said once, with the presses that reach `control`. */
function lines(
  declared: Preview | null,
  own: { name?: string | null; keys?: Presses; title?: string | null },
): Reading | null {
  const keys = advertisesKeys()
    ? [
        ...new Map(
          [
            ...(declared?.keys ?? []).map((press) => press.map(spell)),
            ...(own.keys ?? []),
          ].map((steps) => [steps.join(" "), steps]),
        ).values(),
      ]
    : [];
  const said: Words[] = [];
  for (const line of [
    declared?.name ?? own.name,
    ...(declared?.detail ?? []),
    own.title,
  ])
    if (line && !(typeof line === "string" && said.includes(line))) said.push(line);
  const [name = null, ...detail] = said;
  const list = declared?.list?.items.length ? declared.list : null;
  if (!name && !keys.length && !list) return null;
  return {
    name,
    keys,
    detail,
    at: declared?.at ?? null,
    about: declared?.about ?? null,
    excerpt: Boolean(declared?.excerpt),
    unseen: Boolean(declared?.unseen),
    list,
    restates: false,
    declared,
  };
}

// What `node` previews of its own as it shows on `route`: false where it says nothing
// and nothing around it may, null where it says nothing of its own. A control says its
// accessible name where its face doesn't say it, or its quiet words alone where they are
// all its face leaves unsaid, and the keys that press it; a declaration and a `title`
// add their lines under them. Its `aria-description` is a screen reader's, which often
// names what its face shows, as a diff row's names its path, so a preview leaves it out.
function readingOf(node: Element, route: Route): Reading | null | false {
  if (node.getAttribute("aria-expanded") === "true" || node.matches(PROXY)) return null;
  // A link into the page declares the place it opens, as its own declaration would.
  const declared = declaration(node, route) ?? linkPreview(node);
  if (declared === false) return false;
  const title = titleOf(node);
  if (!(node.matches(CONTROL) && !typesText(node)))
    return beyondFace(lines(declared ?? null, { title }), () => faceOf(node));
  // A control holding more than a face, as a card a link wraps, is content that says
  // what it holds, so only a name its markup gives can preview over it.
  const face = controlFace(node);
  const markup = markupName(node);
  const keys = controlKeys(node);
  // The module header's rule: a face that cuts none of a content name leaves unsaid only
  // its quiet words, which are the reading's name.
  const quiet = !markup && face && !face.cut ? face.quiet : "";
  const name = markup || quiet || (face ? contentName(node) : "");
  const unsaid = markup
    ? !(face && faceSays(face, markup))
    : Boolean(face && (face.cut || face.quiet));
  // A title the name already says, as a symbol's short word under its longer label,
  // adds no line.
  const titled =
    title && !` ${wordsOf(name)} `.includes(` ${wordsOf(title)} `) ? title : null;
  if (!declared && !unsaid && !keys.length && !titled) return null;
  const reading = lines(declared ?? null, { name, keys, title: titled });
  // Made of the control's own name and keys alone, it says what a screen reader already
  // hears from them.
  if (reading) reading.restates = !declared && !titled;
  const read = beyondFace(reading, () => face);
  // Key chips the face doesn't draw press the control, so its whole name heads them.
  return quiet && read?.keys.length && read.name === quiet
    ? { ...read, name: contentName(node) }
    : read;
}
// What `reading` says beyond what its target shows (`faceOf`): a line the face shows
// goes, as a menu row's own words or a search count's, and so does a press whose chips it
// shows in order, as a menu row's; a name stays to head what is left, and a reading left
// with nothing more shows nothing. Words the face cuts short, as a row ending in an
// ellipsis, aren't among those it shows, so a line holding them stays, since the preview
// is then where the rest is read. A reading standing by a part of its target (`at`), as a
// chart's point, is about that part, so the face's other words don't speak for it.
function beyondFace(reading: Reading | null, read: () => Face | null): Reading | null {
  if (!reading || reading.at || reading.list) return reading;
  const face = read();
  if (!face) return reading;
  const chips = `\n${face.chips.join("\n")}\n`;
  const keys = reading.keys.filter(
    (steps) => !chips.includes(`\n${steps.join("\n")}\n`),
  );
  const detail = reading.detail.filter((line) => !shows(face, line));
  if (!detail.length && !keys.length && shows(face, reading.name)) return null;
  return detail.length === reading.detail.length && keys.length === reading.keys.length
    ? reading
    : { ...reading, detail, keys };
}
// The innermost node along `path` the search stops at, read as its preview shows.
function candidate(path: Iterable<EventTarget>): Element | null {
  for (const node of path) {
    if (!isElement(node)) continue;
    if (node === tip) return null;
    if (mayPreview(node)) return node;
  }
  return null;
}
function* climb(node: Element) {
  for (let at = node as Element | null; at; at = renderedParent(at)) yield at;
}
// What previews from `node` outward on `route`, and where it stands.
function readOutward(
  node: Element,
  route: Route,
): { target: Element; reading: Reading } | null {
  for (let at = node as Element | null; at; at = renderedParent(at)) {
    if (at === tip) return null;
    if (!mayPreview(at)) continue;
    const reading = readingOf(at, route);
    if (reading === false) return null;
    if (reading) return { target: at, reading };
  }
  return null;
}

let shown: Shown | null = null;
// Whether a preview stands for Escape to put away, its first step (the `preview` scope).
// The page holds a close watcher while Escape has a step to take, read in the repaint
// frame (dom/keyboard/close-requests.js), and a preview comes and goes between frames, so
// each change of the step reads it again at once (`stepMoved`): a watcher left from a
// preview put away took the next Escape, or the next back gesture, and did nothing, so
// inside an open popover the press after the preview's closed nothing, even a frame
// later.
const standsForEscape = () => Boolean(shown && !shown.away);
let stoodForEscape = false;
function stepMoved() {
  if (standsForEscape() === stoodForEscape) return;
  stoodForEscape = !stoodForEscape;
  paintCloseRequests();
}
// When the last preview the user saw went, for the warm switch.
let cooled = -Infinity;
type Ranged = {
  range: Range;
  read: Read | null;
  at: { x: number; y: number } | undefined;
};

// What a hovering pointer rests on, in two layers, each kept until whoever said it says
// otherwise: the element `pointerover` found that previews itself (`over`), and the
// range a range's owner says it rests on, with what pointing at it reads and where the
// pointer was (`ranged`, `pointRange`). Which of them the pointer reads is the one rule
// every route that reads a point follows (`readingAt`), so the pointer leaving a link
// for the passage's words around it is on the passage again with nothing told anew.
let over: Element | null = null;
let ranged: Ranged | null = null;
// The target under a hovering pointer, the read its range's owner gave, and the dwell
// before its preview.
let pointing: Target | null = null;
let pointingRead: Read | null = null;
let pointingAt: { x: number; y: number } | undefined;
let dwell: ReturnType<typeof setTimeout> | undefined;
// The target the dwell counts for, until it ends or stops (`stopDwell`).
let dwelling: Target | null = null;
function stopDwell() {
  clearTimeout(dwell);
  dwelling = null;
}
// The target under the pointer whose wait is over, by its dwell or at once while warm,
// so a new aim inside it shows at once (`changed`).
let rested: Target | null = null;
// The wait before a pointer's preview goes once the pointer has left its target.
let leaving: ReturnType<typeof setTimeout> | undefined;
// The target whose preview a press, a key or Escape put away, quiet until the user aims
// again: the pointer reaches a target, focus arrives or a keyboard walk lands, or a
// finger holds. What a widget declares again, as it redraws with the same reading,
// is no aim of the user's.
let quiet: Target | null = null;
let hold: Hold | null = null;
// A reading whose subject the user can't see, as a point scrolled out of a box, a
// control under a header stuck over its box, or a target out of view as it was aimed
// at, ends where a pointer or a finger read it: the gesture that aimed is over once its
// subject has gone. Focus's is suspended instead, since focus stays and has an end of
// its own: it stays the page's reading (`shown`), its preview closed (`away`), until
// its subject shows again or focus moves on, which is then the first its element hears
// of it (`PREVIEW_ENDED`), so a chart keeps its ring on a focused point scrolled away.
// It keeps its watch on the element it stands by (`follow`), so a scroll of a box
// holding that element, a resize or a new presentation decides it again (`decide`),
// and the platform says when its element comes into view by a layout that moves it
// there (`coming`), as when it had no box.
const coming = new IntersectionObserver((entries) => {
  if (shown?.away && entries.some((entry) => entry.isIntersecting)) decide(false);
});
let awaited: Element | null = null;
function awaitView(el: Element | null) {
  if (el === awaited) return;
  if (awaited) coming.unobserve(awaited);
  awaited = el;
  if (el) coming.observe(el);
}
// End `record`'s reading, or suspend focus's, and say it stands nowhere.
function away(record: Shown) {
  if (record.route !== "focus") {
    hide();
    return false;
  }
  record.away = true;
  closeNativeLayer(tip);
  anchored = null;
  awaitView(record.holder);
  stepMoved();
  return false;
}
// Whether the release just heard ended a hold that read, whose touch's end it cancels.
let spent = false;
// Where the pointer last stood, which tells a target the user moved onto from one
// that arrived under a still pointer.
let rest = { x: NaN, y: NaN };
// Whether the pointer the user last moved or pressed is a finger, which reads a range
// only while it holds a press (`pointRange`).
let finger = false;
// The innermost node under a mouse pointer, which says whether a changed preview is the
// pointer's to read.
let beneath: Node | null = null;
// Whether the pointer rides a preview that lets it through (`ride`).
let riding = false;

// What `from` previews on `route`, a range's through the read its owner gave.
function readFrom(
  from: Target,
  route: Route,
  read: Read | null,
): { target: Target; holder: Element; reading: Reading } | null {
  if (!(from instanceof Range)) {
    const outward = from.isConnected ? readOutward(from, route) : null;
    return outward && { ...outward, holder: outward.target };
  }
  const holder = placeHolder(from);
  let declared = null;
  try {
    declared = holder?.isConnected && read ? read(route) : null;
  } catch (error) {
    reportError(error);
  }
  const reading = declared ? lines(declared, {}) : null;
  return holder && reading ? { target: from, holder, reading } : null;
}

// Show what `from` previews on `route`, and say whether one shows. It reads first, and
// only a new reading replaces the standing preview: an aim at what says nothing there,
// as empty space inside a chart, leaves it standing, as plain text does, and a preview
// shown `again` for what it stands for goes once that says nothing. Shown `again`, it
// draws what its target says now where it stands, with no fade, as a new `aim` inside
// it where that is what changed; so does the same route's next reading where it stands
// by the element the standing one stands by (`standsBy`). A focus reading whose subject
// can't be seen is suspended (`away`) and shows nothing yet, and any other ends. A hold
// that shows a reading has read, whichever way the reading came, so its release presses
// nothing.
function show(
  from: Target,
  route: Route,
  read: Read | null = null,
  at?: { x: number; y: number },
  again: boolean = false,
  aim: boolean = false,
) {
  if (!again && shown?.from === from && shown.route === route) return !shown.away;
  const found = readFrom(from, route, read);
  // The same route's next reading that stands by the element the standing one stands
  // by takes its place there (`standsBy`).
  const by = !again && found ? standsBy(found) : null;
  const standing =
    (again && shown?.from === from) ||
    (by && shown && !shown.away && shown.route === route && standsBy(shown) === by)
      ? shown
      : null;
  if (!found) {
    if (standing) hide();
    return false;
  }
  // Ending the standing record's watch can run its disconnect, which hides whatever
  // `shown` names, so the record stops being the one shown first.
  if (standing) {
    shown = null;
    standing.stop();
    if (standing.target !== found.target) ended(standing);
  } else hide();
  const { target, holder, reading } = found;
  // The first preview a pointer or a finger reads fades in; one that takes another's
  // place, or comes while the last has only just gone, is there at once, as focus's
  // always is, so reading along a row of controls moves one preview rather than fading
  // a new one in at each (chrome.css, `data-lf-fade`).
  keeps(
    tip,
    "data-lf-fade",
    route !== "focus" && !standing && performance.now() - cooled >= WARM ? "" : null,
  );
  render(face(reading), body);
  const record: Shown = {
    from,
    target,
    holder,
    route,
    read,
    at,
    reading,
    clock: clockNow(),
    stop: () => {},
    described: null,
  };
  takeWithin(record);
  // A target that leaves the page, as a re-render replaces it, takes its preview along.
  record.stop = watchOwner(holder, { disconnect: () => shown === record && hide() });
  shown = record;
  keeps(tip, "data-lf-route", route);
  keeps(
    tip,
    "data-lf-face",
    reading.unseen ? "unseen" : reading.excerpt ? "excerpt" : null,
  );
  keeps(tip, "data-lf-list", reading.list ? "" : null);
  // A hold whose place the next reading takes leaves its holder as `hide` would.
  if (
    standing?.route === "hold" &&
    standing.holder !== holder &&
    !(standing.target instanceof Range)
  )
    standing.holder.removeAttribute("data-lf-touch-held");
  if (route === "hold" && !(target instanceof Range))
    keeps(holder, "data-lf-touch-held", "");
  if (standing) record.described = standing.described;
  else {
    // A screen reader hears a preview of what focus is on (`readsFocus`) as what focus
    // is on describes, unless it says only what the control's own name and keys already
    // do, or focus is on a proxy, whose own markup describes what it stands for.
    const on = focused();
    if (on && readsFocus(record) && !reading.restates && !on.matches(PROXY)) {
      record.described = {
        el: on,
        attribute: on.getAttribute("aria-describedby"),
        elements: on.ariaDescribedByElements,
      };
      on.ariaDescribedByElements = [...(on.ariaDescribedByElements ?? []), tip];
    }
  }
  // Described first, so a reading that stands nowhere and ends puts that back too.
  const stands = stand(record, reading, Boolean(standing), aim);
  if (stands && route === "hold" && hold) hold.read = true;
  return stands;
}
// The element a reading of an element stands by: the one it declares (`at`), or the
// element that declares it, also where it declares a box inside itself. Readings that
// stand by one element are one preview to the eye, as each of a widget's controls
// standing its preview by the widget, or one element's next reading, so the next takes
// the standing one's place with no fade. A range's stands by its own line.
const standsBy = ({
  target,
  holder,
  reading,
}: {
  target: Target;
  holder: Element;
  reading: Reading;
}) => (target instanceof Range ? null : isElement(reading.at) ? reading.at : holder);

// Where a preview stands (`stand`), decided here, from the box the browser will draw,
// and drawn by the browser from that decision alone, with no fallback of its own. Its
// anchor is an element: the target or the declared element, a range's line by the element
// holding the range, and a declared box by the declaring element, each box held at its
// offsets inside its element, so the browser carries the preview with the element
// through every scroll and resize (`anchor()`, chrome.css). Its edges stand at offsets
// from that element's (`--lf-preview-{top,bottom,left,right}`), its top or its bottom and
// its left or its right, or, centred, at the left the window gives it, as its side says
// (`data-lf-y`, `data-lf-x`). A side's room is what it holds clear of every other control,
// by hit tests every `REACH` out from its edge (`clearRoom`), and of what the preview is
// about. Where it stands now holds while its room holds a whole line. Afresh, its side
// is the first whose room holds it whole of: below, then above, each from the box's start
// edge and then its end edge, slid in along it until the window holds it; beside,
// toward the nearer window edge and then the other; centred across the window below,
// then above; else the one whose room holds the most whole lines, the preview fitted
// to it (`fit`). A finger's and a point's try above first, since the finger covers
// what lies below and a point's axis stands under it.
// Only where no side's room holds a line does the side the window gives the most room
// stand over what it covers and let the pointer through to it (`data-lf-covers`).
// It stands `GAP` clear of a range's line, and of the marks round a box, which a
// focus ring, the aim or a comment's mark draws there, on each side as far as they
// reach, as a thread's card does (readings/mark-room.js, `markRoom`); further clear of a box a
// finger holds, which covers what is under it.
const EDGE = 8;
const GAP = { line: 6, box: 6, hold: 22 };
const REACH = 23;

// The nearest HTML element with a box of its own at or around `el`: a `display:
// contents` element's first shown part, and a shape in a drawing's HTML host.
function boxed(el: Element): HTMLElement | null {
  for (let at = el as Element | null; at; at = renderedParent(at)) {
    if (!isHTML(at)) continue;
    const [part] = shownParts(at);
    if (isHTML(part)) return part as HTMLElement;
  }
  return null;
}

// A declared box as offsets inside the element the preview stands by, taken as each
// reading is, since a widget may change one box in place, and carried by that element
// from then on, so a decision made again as the page moves reads it where it stands.
function takeWithin(record: Shown) {
  const declared = record.reading.at;
  const source = declared && !isElement(declared) ? boxed(record.holder) : null;
  if (!declared || isElement(declared) || !source) {
    record.within = null;
    return;
  }
  const by = source.getBoundingClientRect();
  record.within = {
    top: declared.top - by.top,
    right: by.right - declared.right,
    bottom: by.bottom - declared.bottom,
    left: declared.left - by.left,
  };
}
// What the preview stands by: its anchor element and the box inside it, in client
// coordinates; for an element, the box it shows as (dom/geometry.js, `shownBox`), every
// part of an element drawn through `display: contents` included, and the element,
// whose marks the preview stands clear of too (`stand`).
function anchorOf(
  record: Shown,
  reading: Reading,
): { source: HTMLElement; box: Box; subject?: Element } | null {
  const { target, holder, at } = record;
  if (target instanceof Range) {
    const lines = [...target.getClientRects()];
    // The line pointed at as it showed, which it stands by as the page moves after.
    record.line ??= Math.max(
      0,
      lines.findIndex((box) => at && holds(box, at.x, at.y)),
    );
    const line = lines[record.line] ?? lines[0];
    const common = target.commonAncestorContainer;
    const around = isElement(common) ? common : common.parentElement;
    const source = around && boxed(around);
    return line && source ? { source, box: line } : null;
  }
  const declared = reading.at;
  if (declared && !isElement(declared)) {
    const source = boxed(holder);
    const { within } = record;
    if (!source || !within) return null;
    const by = source.getBoundingClientRect();
    return {
      source,
      box: {
        top: by.top + within.top,
        right: by.right - within.right,
        bottom: by.bottom - within.bottom,
        left: by.left + within.left,
      },
    };
  }
  const el = declared?.isConnected ? declared : holder;
  const source = boxed(el);
  if (!source) return null;
  return { source, box: shownBox(el), subject: el };
}

// The source the preview was last shown with, where it stood then, what it said, and
// which side of its stage's mark it stands on. Held weakly, since it outlives the
// preview and a revision may remove it.
let anchored: WeakRef<Element> | null = null;
let seated: Element | null = null;
let said = "";
let beforeMark = false;
// Stand the stage in the topmost modal dialog while one stands, else in the chrome, and
// say whether it moved.
function seat() {
  const modal = nativeLayers().findLast((layer) => layer.kind === "modal")?.root;
  const into = modal ?? home;
  if (!into || into === seated) return false;
  if (modal) carryChromeStyles(modal);
  into.append(stage);
  seated = into;
  beforeMark = false;
  return true;
}
// Show the preview by `source`. Firefox 157 stands a popover hidden and shown again by a
// new source in one task by the source it was last shown with, while nothing about the
// popover itself changed since, as its words (notes/browser-support.md). Any insertion
// lays it out again, so a new source that comes with the same words moves it to the
// other side of its mark, a change the page's watch of its writes reads as one.
function open(source: HTMLElement, standing: boolean, moved: boolean) {
  const last = anchored?.deref();
  if (standing && source === last && !moved) return;
  if (standing) closeNativeLayer(tip);
  if (!moved && source !== last && tip.textContent === said) {
    beforeMark = !beforeMark;
    if (beforeMark) mark.before(tip);
    else mark.after(tip);
  }
  anchored = new WeakRef(source);
  said = tip.textContent;
  showNativeLayer(tip, { source });
}

// The element the standing preview stands by, whose resizing reads it again, words and
// place (`refresh`), as the window's resizing does, since what a target previews may
// follow the width it is given. Its first reading, as observing it starts, is the size
// it was placed at, so it moves nothing. A scroll of a box holding it decides its place
// again (`replace`), heard at the document and at each shadow root around it, since a
// scroll inside a shadow tree is heard no further than its root.
let followed: Element | null = null;
let followedSize: { width: number; height: number } | null = null;
let followedRoots: ShadowRoot[] = [];
const following = sizeObserver(
  (entries) => {
    const entry = entries.at(-1);
    if (!entry) return;
    const { width, height } = entry.target.getBoundingClientRect();
    const was = followedSize;
    followedSize = { width, height };
    if (shown && was && (was.width !== width || was.height !== height)) decide(true);
  },
  // A preview comes and goes for as long as the page plays.
  { counted: false },
);
function follow(source: Element | null) {
  if (source === followed) return;
  if (followed) following.unobserve(followed);
  for (const root of followedRoots) root.removeEventListener("scroll", scrolled, true);
  followed = source;
  followedSize = null;
  followedRoots = [];
  if (!source) return;
  following.observe(source);
  for (
    let root = source.getRootNode();
    root instanceof ShadowRoot;
    root = root.host.getRootNode()
  ) {
    root.addEventListener("scroll", scrolled, { capture: true, passive: true });
    followedRoots.push(root);
  }
}
function scrolled(event: Event) {
  const box = event.target;
  if (
    followed &&
    (box === document || (isElement(box) && renderedUnder(followed, box)))
  )
    decide(false);
}
// Decide the standing preview again in the next frame, once however many of its grounds
// changed in this one: its words and place (`refresh`) where what it says may have
// changed with them, as a presentation's or a resize's, of the window or of what it
// stands by, and else its place alone, as a scroll's or the visible viewport's.
let deciding = 0;
let rereading = false;
function decide(reread: boolean) {
  if (!shown) return;
  rereading ||= reread;
  if (deciding) return;
  // The request stands until the decision has run, so what the decision itself sets
  // going, as a presentation or a resize it causes, asks for none of its own.
  deciding = nextRender(() => {
    const read = rereading;
    if (shown) {
      if (read) refresh();
      else stand(shown, shown.reading, true);
    }
    deciding = 0;
    rereading = false;
  });
}

type Placement = {
  y: "below" | "above" | "top";
  x: "left" | "right" | "after" | "before" | "center";
  from: number;
  room: number;
  box: Box;
};
// The element the standing preview stands by, the side it stands on, the edge across it
// stands by, left or right, and its top corner on that edge as offsets from the box it
// stands by, which the next decision standing by that element tries first, whichever
// target's reading it draws. What stands around it is tested afresh every time, since
// the page may have changed there whatever the target did.
let placed: {
  source: HTMLElement;
  side: { y: Placement["y"]; x: Placement["x"] };
  x: "left" | "right";
  corner: { x: number; y: number };
} | null = null;

// Stand the preview by its anchor, and say whether it stands: the one decision of where
// it stands, made again for the target it already stands for (`standing`), which tries
// the place it stands at now first, or its side by the new box for a new `aim` inside
// it, and afresh for a new target. Where it can stand nowhere, its reading ends, or,
// focus's, is suspended (`away`) until a decision finds it a place.
function stand(
  record: Shown,
  reading: Reading,
  standing: boolean,
  aim: boolean = false,
) {
  const moved = seat();
  const anchor = anchorOf(record, reading);
  if (!anchor) return away(record);
  const { source, box, subject } = anchor;
  follow(source);
  const { target, holder, route } = record;
  const declared = reading.at;
  const point = Boolean(declared) && !isElement(declared);
  // What it stands for shows, or it stands nowhere: its own box, a range's line or a
  // declared point, less every box that clips it, the window's included, and, for a box
  // inside the element it stands by, that element's too. The platform hides a preview
  // whose anchor element is clipped away (`position-visibility`, chrome.css), but a
  // chart's point scrolls out of a box while the chart still shows around it.
  const clips = target instanceof Range || point ? clippedContents : clippedRect;
  if (!clips(box, source, new Map())) return away(record);
  // What it keeps clear of: the box, as far out as the marks round it reach, and
  // its gap past that.
  const gap =
    target instanceof Range ? GAP.line : route === "hold" ? GAP.hold : GAP.box;
  const marks = subject ? markRoom(subject, box, gap) : null;
  const past = (side: "left" | "top" | "right" | "bottom") =>
    Math.max(0, marks?.[side] ?? 0) + gap;
  const clear = {
    top: box.top - past("top"),
    right: box.right + past("right"),
    bottom: box.bottom + past("bottom"),
    left: box.left - past("left"),
  };
  const rtl = getComputedStyle(holder).direction === "rtl";
  keeps(tip, "dir", rtl ? "rtl" : "ltr");
  open(source, standing, moved);
  // The part of the window the user sees, which a pinch or an on-screen keyboard makes
  // smaller than the layout viewport, and which nothing the chrome covers takes from,
  // since the preview stands over all of it; its width bounds the preview's.
  const room = shownWindow({ gap: EDGE, item: tip });
  tip.style.setProperty("--lf-preview-span", layoutPx(room.width));
  // Its edges stand at offsets from the box `anchor()` reads its source at, which in
  // Firefox leaves out the source's transforms (dom/css-anchors.js, `anchorBox`).
  const by = anchorBox(source);
  // The size this decision read, which the observer of what it stands by compares.
  const { width: sourceWidth, height: sourceHeight } = source.getBoundingClientRect();
  followedSize = { width: sourceWidth, height: sourceHeight };
  const width = tip.getBoundingClientRect().width;
  const height = atLayoutPrecision(wholeHeight());
  // What it is about stays in view: the box it stands by, and what its declaration
  // names (`about`), as a margin entry's passage or a time's message.
  const about = reading.about?.isConnected
    ? reading.about.getBoundingClientRect()
    : null;
  const inside = (at: Placement) =>
    at.box.left >= room.left - 0.5 &&
    at.box.right <= room.right + 0.5 &&
    at.box.top >= room.top - 0.5;
  const rowRoom = (y: Placement["y"]) =>
    y === "below"
      ? room.bottom - clear.bottom
      : y === "above"
        ? clear.top - room.top
        : room.bottom - box.top;
  // By the box's start or end edge, slid in along it until the window holds it, still
  // across the box, so the same side builds the same place from the same geometry.
  // Centred, it stands as near the window's middle as it can while it still stands across
  // its target, so it never reads as standing for something else far off.
  const slid = (left: number) =>
    Math.min(Math.max(left, room.left), room.right - width);
  const leftOf = (x: Placement["x"]) =>
    x === "left"
      ? slid(box.left)
      : x === "right"
        ? slid(box.right - width)
        : x === "after"
          ? clear.right
          : x === "before"
            ? clear.left - width
            : Math.min(
                Math.max(room.left + (room.width - width) / 2, box.left - width + 1),
                box.right - 1,
              );
  // A place on a side, from the edge it grows from: the top where it stands below or
  // level with the box, which its words grow down from, and the bottom above it, which
  // they grow up from; its box is as much of the preview as the window holds there.
  const placeAt = (
    y: Placement["y"],
    x: Placement["x"],
    from: number,
    space: number,
    left: number,
  ): Placement => {
    const tall = Math.min(height, Math.max(space, 0));
    const top = y === "above" ? from - tall : from;
    return {
      y,
      x,
      from,
      room: space,
      box: { left, top, right: left + width, bottom: top + tall },
    };
  };
  const placement = (y: Placement["y"], x: Placement["x"]) =>
    placeAt(
      y,
      x,
      y === "below" ? clear.bottom : y === "above" ? clear.top : box.top,
      rowRoom(y),
      leftOf(x),
    );
  const [start, end] = rtl
    ? (["right", "left"] as const)
    : (["left", "right"] as const);
  // Where it stands now: its top corner on the edge it stands by at the same offsets
  // from the box it stands by, so words that grow keep its first line still. A new aim
  // keeps its side by the new box instead, standing by the edge that side stands by, its
  // bottom above the box and its top below or beside it, so a longer reading grows away
  // from what it reads.
  const was = standing && placed?.source === source ? placed : null;
  const now = !was
    ? null
    : aim
      ? placement(was.side.y, was.side.x)
      : placeAt(
          "top",
          was.x,
          box.top + was.corner.y,
          room.bottom - (box.top + was.corner.y),
          was.x === "right"
            ? box.right - was.corner.x - width
            : box.left + was.corner.x,
        );
  const rows: Placement["y"][] =
    route === "hold" || point ? ["above", "below"] : ["below", "above"];
  const placements: Placement[] = rows.flatMap((y) => [
    placement(y, start),
    placement(y, end),
  ]);
  if (!(target instanceof Range)) {
    const toward =
      box.left + box.right > room.left + room.right
        ? (["after", "before"] as const)
        : (["before", "after"] as const);
    placements.push(...toward.map((x) => placement("top", x)));
  }
  placements.push(...rows.map((y) => placement(y, "center")));
  const { rooms } = faceLines(reading);
  const least = Math.min(...rooms, height);
  // How many whole lines a room holds.
  const linesIn = (space: number) =>
    rooms.reduce((most, need, at) => (need <= space ? at + 1 : most), 0);
  // The room a place holds clear of every other control and of what it is about. A
  // finger's hand hides what lies below the touch, so below it holds none.
  const clearHeight = (at: Placement) => {
    if (route === "hold" && at.y === "below") return 0;
    const reach = atLayoutPrecision(
      Math.max(0, Math.min(height, at.room, towardSubject(at))),
    );
    if (reach < least) return reach;
    const room =
      target instanceof Range
        ? clearRoom(at, reach, holder, null, {
            ...lined(box, target.startContainer),
            left: -Infinity,
            right: Infinity,
          })
        : clearRoom(at, reach, holder, holder.getBoundingClientRect(), null);
    return Math.min(reach, atLayoutPrecision(room));
  };
  let chosen: Placement | null = null;
  let held = 0;
  // Where it stands now stays while its clear room holds a whole line, held to that
  // room, so words that grow never move it nor cover anything. A new aim's side stays
  // only where its room holds the new reading whole, which is a new reading's to show.
  if (now && inside(now)) {
    const clearOf = clearHeight(now);
    if (aim ? clearOf >= height : linesIn(clearOf) >= 1)
      [chosen, held] = [now, clearOf];
  }
  // Afresh, the first place whose clear room holds it whole; else the one whose clear
  // room holds the most whole lines, held there.
  if (!chosen) {
    let most = 0;
    for (const at of placements) {
      if (!inside(at)) continue;
      const clearOf = clearHeight(at);
      if (clearOf >= height) {
        [chosen, held] = [at, height];
        break;
      }
      const lines = linesIn(clearOf);
      if (lines > most) [chosen, held, most] = [at, clearOf, lines];
    }
  }
  // Where no place's clear room holds even one line, the side the window gives the most
  // room stands over what it covers and lets the pointer through to it, a finger's above
  // its hand where it can; where no side holds a line, it stands over its target itself,
  // and where even that holds none, nothing shows.
  let covering = false;
  if (!chosen) {
    const roomiest = (among: Placement[]) =>
      among.reduce(
        (most, at) => (!most || at.room > most.room ? at : most),
        null as Placement | null,
      );
    const sides = placements.filter(inside);
    const seen = sides.filter((at) => !(route === "hold" && at.y === "below"));
    chosen = roomiest(seen.length ? seen : sides);
    if (!chosen || linesIn(Math.min(height, chosen.room)) < 1) {
      const over = placeAt("top", start, box.top, room.bottom - box.top, leftOf(start));
      chosen = inside(over) && linesIn(Math.min(height, over.room)) >= 1 ? over : null;
    }
    if (!chosen) return away(record);
    held = Math.min(height, chosen.room);
    covering = true;
  }
  const tall = Math.min(height, held);
  const top = chosen.y === "above" ? chosen.from - tall : chosen.from;
  const drawn = {
    left: chosen.box.left,
    top,
    right: chosen.box.right,
    bottom: top + tall,
  };
  // Its edges at their offsets from the element it stands by: its top, or, above, its
  // bottom, and its left, or its right where it stands from the box's right edge; centred,
  // its left stands where the window puts it, whatever the element does across.
  const edges = {
    top: drawn.top - by.top,
    bottom: drawn.bottom - by.top,
    left: drawn.left - (chosen.x === "center" ? 0 : by.left),
    right: by.right - drawn.right,
  };
  for (const [edge, length] of Object.entries(edges))
    tip.style.setProperty(`--lf-preview-${edge}`, layoutPx(length));
  const right = chosen.x === "right" || chosen.x === "before";
  placed = {
    source,
    side: was && chosen === now && !aim ? was.side : { y: chosen.y, x: chosen.x },
    x: right ? "right" : "left",
    corner: {
      x: right ? box.right - drawn.right : drawn.left - box.left,
      y: drawn.top - box.top,
    },
  };
  keeps(tip, "data-lf-y", chosen.y);
  keeps(tip, "data-lf-x", chosen.x);
  tip.style.setProperty(
    "--lf-preview-room",
    held >= height ? "none" : layoutPx(Math.max(held, 0)),
  );
  keeps(tip, "data-lf-covers", covering || point ? "" : null);
  fit(reading, held >= height ? Infinity : held);
  record.away = false;
  awaitView(null);
  stepMoved();
  return true;

  // How far a place may grow from its edge before it meets what it is about.
  function towardSubject(at: Placement) {
    let until = Infinity;
    for (const [subject, clearing] of [
      [clear, 0],
      [about, 0],
    ] as const) {
      if (!subject || subject.left >= at.box.right || at.box.left >= subject.right)
        continue;
      if (at.y === "above") {
        if (subject.top >= at.from) continue;
        until = Math.min(until, Math.max(0, at.from - subject.bottom - clearing));
      } else {
        if (subject.bottom <= at.from) continue;
        until = Math.min(until, Math.max(0, subject.top - clearing - at.from));
      }
    }
    return until;
  }
}

// How far a preview at `at` may run from the edge it grows from before it covers a
// control other than `holder` that must stay reachable, or Infinity where none stands
// within `reach`: hit tests every `REACH` across its width, row by row out from that
// edge, through the preview where it stands now, the first row that finds one ending
// the room at its near edge. A control thinner than `REACH` can stand unseen between
// the points, as the trace timeline's marks can, which declare their lane as what they
// are about so their previews keep clear of it, since no sampling proves a control
// absent, which is the grid's limit. A point inside the holder's own box finds the
// holder or what it holds, which are no other control, so it is not tested, as most of
// a preview standing over a chart is not, which bounds its cost. A range's holder, the
// element holding its words, holds other ranges on its other lines, as a paragraph does
// other threads' marks, so for a range nothing is left untested (`own` is null). Only a
// mark on its own line (`line`), across its leading (dom/geometry.js, `lined`) and its whole
// width, goes untested, since there the mark is the preview's own or one beside it; a
// control there, as a button in a deep leading just below the words, is still tested.
function clearRoom(
  at: Placement,
  reach: number,
  holder: Element,
  own: Box | null,
  line: Box | null,
) {
  const around = new Set(climb(holder));
  // The boxes around `holder` a press acts on (`targetAt`).
  const taking = new Set<Element>();
  for (let up = renderedParent(holder); up; up = renderedParent(up)) {
    const takes = aimableAt(up);
    if (!takes) break;
    if (takes.matches(CONTROL)) taking.add(takes);
    up = takes;
  }
  const down = at.y !== "above";
  const across = steps(at.box.left, at.box.right);
  const count = Math.max(1, Math.ceil((reach - 2) / REACH));
  for (let n = 0; n <= count; n++) {
    const off = 1 + (Math.max(reach - 2, 0) * n) / count;
    const y = down ? at.from + off : at.from - off;
    let edge = Infinity;
    for (const x of across) {
      if (own && holds(own, x, y)) continue;
      const marks = !line || !holds(line, x, y);
      const hit = targetAt(x, y, holder, around, taking, marks);
      if (!hit) continue;
      edge = Math.min(edge, down ? hit.top - at.from : at.from - hit.bottom);
    }
    if (edge < Infinity) return Math.max(0, edge);
  }
  return Infinity;
}
// The points `REACH` apart from just inside `from` to just inside `to`.
function steps(from: number, to: number) {
  const count = Math.max(1, Math.ceil((to - from - 2) / REACH));
  return Array.from(
    { length: count + 1 },
    (_, n) => from + 1 + ((to - from - 2) * n) / count,
  );
}
// What a preview must leave reachable where it can: everything whose access the user
// must keep, whichever owner routes a gesture there, so the question is what the user
// reaches, not what Leaf's gestures take. That is what the page works
// (dom/control-selectors.js, `WORKS`); anything focusable, as a stop Leaf lends code that
// overflows or a tab panel, which `WORKS` leaves to its own gestures; anything that
// scrolls; anything embedding a document, whose controls no hit test out here finds;
// and whatever previews, which a pointer reads. It is wider than what takes the
// pointer (`aimableAt`), since a press must still reach a region the pointer only reads.
const EMBEDS = "iframe, embed, object";
function keepsAccess(el: Element) {
  if (el.matches(WORKS) || el.matches(EMBEDS) || mayPreview(el)) return true;
  if ("tabIndex" in el && (el as HTMLElement).tabIndex >= 0) return true;
  if (el.scrollHeight <= el.clientHeight && el.scrollWidth <= el.clientWidth)
    return false;
  const { overflowX, overflowY } = getComputedStyle(el);
  return /auto|scroll/.test(`${overflowX} ${overflowY}`);
}
// What a point of the page finds beneath the preview, through every shadow tree there.
function hitAt(x: number, y: number) {
  let hit = document.elementsFromPoint(x, y).find((el) => !tip.contains(el)) ?? null;
  for (
    let inner = hit?.shadowRoot?.elementFromPoint(x, y);
    hit && inner && inner !== hit;
    inner = hit.shadowRoot?.elementFromPoint(x, y)
  )
    hit = inner;
  return hit;
}
type RangesAt = (x: number, y: number, under: Element) => Box | null;

// A range a press acts on, as a thread's passage mark is, has no element of its own for
// a hit test to find, so its owner says where one lies under a point of the page: the
// box of its line there, or null. `under` is the page's element at the point, beneath
// the preview.
const rangeOwners = new Set<RangesAt>();
export function declareRanges(at: RangesAt) {
  rangeOwners.add(at);
  return () => void rangeOwners.delete(at);
}
// The box of what must stay reachable at a point of the page beneath the preview: the
// control other than `holder` and what it holds, the nearest around what the point
// finds, or a range its owner says lies there, which may be in the holder (`declareRanges`).
// A box
// around `holder` (`around`) stands under the preview wherever it stands, so it is no
// control to keep clear of where it takes nothing (dom/widget-elements.js, `aimableAt`),
// as a scrolling box, a stop Leaf lends code or a tab panel doesn't, nor where it takes
// the pointer only to be read, as a widget drawing its own content or a box that
// previews, whose controls are tested for themselves; and is one where a press acts on
// it (`taking`), as a card a press opens around a chart is. Rejected: counting every
// box around it that takes the pointer, so inside `lf-toc`, drawn across the
// column, no side holds a line and a row's preview stands over the next row.
/** @param marks whether to ask the ranges' owners */
function targetAt(
  x: number,
  y: number,
  holder: Element,
  around: Set<Element>,
  taking: Set<Element>,
  marks: boolean,
): Box | null {
  const hit = hitAt(x, y);
  if (!hit) return null;
  for (const at of climb(hit)) {
    if (at === holder) break;
    if (taking.has(at)) return at.getBoundingClientRect();
    if (!around.has(at) && keepsAccess(at))
      return renderedUnder(at, holder) ? null : at.getBoundingClientRect();
  }
  if (!marks) return null;
  for (const owner of rangeOwners) {
    const box = owner(x, y, hit);
    if (box) return box;
  }
  return null;
}

function hide() {
  if (!shown) return;
  const record = shown;
  shown = null;
  record.stop();
  const described = record.described;
  if (described) {
    // What it was described by before, an attribute's ids, elements set or nothing.
    if (described.attribute === null) described.el.ariaDescribedByElements = null;
    else if (described.attribute === "")
      described.el.ariaDescribedByElements = described.elements;
    else described.el.setAttribute("aria-describedby", described.attribute);
  }
  if (record.route === "hold" && !(record.target instanceof Range))
    record.holder.removeAttribute("data-lf-touch-held");
  follow(null);
  awaitView(null);
  // Only a preview that stood (`placed`) warms the next: one that found no place to
  // stand was never seen.
  if (placed) cooled = performance.now();
  placed = null;
  // Its words stay in the closed popover, so the next preview that says the same
  // writes nothing.
  closeNativeLayer(tip);
  stepMoved();
  ended(record);
}
// The element whose preview `record` read hears that it ended (`PREVIEW_ENDED`), with
// what it declared for that reading, as a chart that drew a mark for the point it read
// takes the mark off. A range's owner knows its own.
function ended(record: Shown) {
  if (isElement(record.target))
    record.target.dispatchEvent(
      new CustomEvent(PREVIEW_ENDED, { detail: { declared: record.reading.declared } }),
    );
}

// The pointer's target changed: start its dwell, or show it at once while warm or where
// it aims again inside the target it rested on (`again`). A
// pointer that leaves its target for nothing, as on its way onto the preview, puts the
// preview away only after `LINGER`, which its reaching the preview or the target
// cancels; one that reaches another target shows that one at once.
function point(
  target: Target | null,
  read: Read | null = null,
  at?: { x: number; y: number },
  again: boolean = false,
) {
  riding = false;
  if (sameTarget(target, pointing)) return;
  clearTimeout(leaving);
  // The pointer reaching another target, or leaving one, is an aim of its own.
  quiet = null;
  pointing = target;
  pointingRead = read;
  pointingAt = at;
  rested = null;
  stopDwell();
  // The preview the pointer leaves, which a focus preview never is.
  const left =
    shown && shown.route !== "focus" && !sameTarget(shown.from, target) ? shown : null;
  if (left?.route === "pointer" && !target) {
    // By its target, not its record, since a redraw meanwhile (`changed`, `refresh`)
    // draws a new record for the same target.
    leaving = setTimeout(() => {
      if (!pointing && shown?.route === "pointer" && sameTarget(shown.from, left.from))
        hide();
    }, LINGER);
    return;
  }
  if (!target) {
    if (left) hide();
    return;
  }
  // Back on the target whose preview stands, as from a link onto the words around it.
  if (shown?.route === "pointer" && sameTarget(shown.from, target)) return;
  // The next target's preview replaces the one the pointer left at once, which reads
  // the next before the last ends, and takes its place where it stands by the same
  // element (`standsBy`); a next that says nothing leaves none.
  if (left || again || performance.now() - cooled < WARM) {
    rested = target;
    if (!show(target, "pointer", read, at) && shown === left) hide();
  } else {
    dwelling = target;
    dwell = setTimeout(() => {
      dwelling = null;
      if (pointing !== target) return;
      rested = target;
      show(target, "pointer", pointingRead, pointingAt);
    }, DWELL);
  }
}

// Whether the pointer is on the pointer's preview, the one answer for an element's
// preview and a range's alike, whoever asks, `pointerover`, a move or a range's owner
// saying the pointer left its range (`pointRange`): the node under the pointer is in the
// preview, or the preview lets the pointer through (`data-lf-covers`) and the pointer is
// over its box, off what it is about (`onSubject`), and over nothing there that takes
// the pointer (dom/widget-elements.js, `aimableAt`). What takes it is whatever the user
// aims at, whether or not it previews, inside the element the preview stands by or
// around it: a field, a titled link, a chart, whose drawing says what the pointer
// reads there, and a card a press opens around one; a scrolling or focusable box that
// takes nothing doesn't. On it, the pointer rides the preview, its target's still,
// until it leaves the box (WCAG 1.4.13, "Hoverable"): a pointer crossing from a chart's
// point or a passage's words to their preview, past the chart's edge or over unmarked
// words, keeps it, and one that reaches a field beneath it takes the field.
const inTip = () => holds(tip.getBoundingClientRect(), rest.x, rest.y);
/** @param node the innermost node under the pointer */
function onPreview(node: Node | null = beneath) {
  if (shown?.route !== "pointer") return false;
  if (under(node, tip)) return true;
  return (
    tip.hasAttribute("data-lf-covers") &&
    inTip() &&
    !onSubject(shown) &&
    !aimableAt(hitAt(rest.x, rest.y))
  );
}
// Whether the pointer is on what a preview is about, by its own boxes rather than the
// element holding it: a range's lines, a declared point's box, or the element's.
function onSubject(record: Shown) {
  const boxes =
    record.target instanceof Range
      ? [...record.target.getClientRects()]
      : [anchorOf(record, record.reading)?.box];
  return boxes.some((box) => box && holds(box, rest.x, rest.y));
}
function ride() {
  clearTimeout(leaving);
  pointing = (shown as Shown).from;
  riding = true;
}

// Put the standing preview away for its target, until the user comes to another.
function quieten() {
  stopDwell();
  if (!shown) return;
  quiet = shown.from;
  hide();
}

const sameRange = (a: Range, b: Target | null) =>
  b instanceof Range &&
  a.startContainer === b.startContainer &&
  a.startOffset === b.startOffset &&
  a.endContainer === b.endContainer &&
  a.endOffset === b.endOffset;
const sameTarget = (a: Target | null, b: Target | null) =>
  a === b || (a instanceof Range && sameRange(a, b));

// The pointer's target, from what each layer says it rests on (`over`, `ranged`).
function aimed(): Target | null {
  return readingAt(beneath, over, ranged?.range ?? null);
}
// What a pointer or a held finger at `node` reads: the range a range's owner says is
// there, as a thread's words, only where nothing else at that point takes the pointer
// (dom/widget-elements.js, `aimableAt`), and otherwise the element that previews itself
// there, or nothing. So a link or a gloss holding a thread's words previews itself, a
// titled button shows only its title, and a thread's words in code or a draft preview
// nothing, their thread reached by its margin entry, `t` and its Threads row. Focus
// rests on an element and reads it, never a range.
const readingAt = (
  node: Node | null,
  element: Element | null,
  range: Range | null,
): Target | null => (range && !aimableAt(node) ? range : element);
const heldTarget = (held: Hold) => readingAt(held.node, held.element, held.range);
function aim() {
  const target = aimed();
  if (target instanceof Range) point(target, ranged?.read ?? null, ranged?.at);
  else point(target);
}

/** A range's owner says the pointer rests on one of its ranges, or on none of them: what
 * pointing at it reads, and where the pointer is, which picks the line it stands by. A
 * range with the same boundaries as the one pointed at is the same range, however many
 * times its owner makes it, and its latest read is the one a standing preview says. The
 * range stands until its owner says none (`ranged`): where something else under the
 * pointer takes it, as a link in a thread's passage, that is what pointing reads, as
 * for a finger, and the range is the target again once the pointer leaves it for the
 * range's words (`readingAt`). A pointer on the range's preview keeps the range, by
 * the one answer to whether it is on a preview (`onPreview`), as one on an element's
 * preview keeps the element (WCAG 1.4.13, "Hoverable"). A finger holding a press holds the range it rests on
 * (`holdRange`); one that only moved reads none. */
export function pointRange(
  range: Range | null,
  read?: Read,
  at?: { x: number; y: number },
) {
  if (hold) holdRange(hold, range, read, at);
  else if (finger) return;
  else if (!range) {
    if (!ranged || onPreview()) return;
    ranged = null;
    aim();
  } else if (ranged && sameRange(range, ranged.range)) {
    // The same range again may say other words: its declaration is the latest, and a
    // preview standing for it reads it now.
    ranged.read = read ?? null;
    if (!sameTarget(pointing, ranged.range)) aim();
    else {
      pointingRead = ranged.read;
      if (shown?.from === pointing && read) {
        shown.read = read;
        refresh();
      }
    }
  } else {
    ranged = { range, read: read ?? null, at };
    aim();
  }
}

// A finger's hold rests on a range or on none, beside the element it found, and reads
// whichever the pointer's rule takes (`readingAt`); once the hold is armed, it shows
// that. The same range again keeps its place and takes its owner's latest words.
function holdRange(
  held: Hold,
  range: Range | null,
  read: Read | undefined,
  at?: { x: number; y: number },
) {
  if (range ? sameRange(range, held.range) : !held.range) {
    if (range && read) held.says = read;
    return;
  }
  held.range = range;
  held.says = (range && read) || null;
  if (at) held.at = at;
  if (held.armed) showHeld(held);
}
// The hold's reading, shown where it says something, put away where it says nothing.
function showHeld(held: Hold) {
  const target = heldTarget(held);
  const says = target instanceof Range ? held.says : null;
  if (target && show(target, "hold", says, held.at)) held.read = true;
  else hide();
}

// What `node` previews changed (`lf-preview`): a preview standing for it reads it
// again where it stands, with no dwell and no fade, or goes where it now says nothing;
// otherwise a finger holding it or one beside it reads it, and a pointer resting over
// it after the dwell, unless the user put its preview away. Focus on it opens none for
// a redraw. Where the user aimed at something new inside it (`aim`), as a chart's next
// point, the aim is a new target: whatever put the last preview away, the route reading
// the element shows it, focus the browser shows included; focus a press put there
// without showing it leaves the aim to the pointer, which shows it at once where it has
// already rested inside the element (`rested`), as on a dial's depth whose press put its
// preview away however long it was held, and after its dwell where it only just came.
// What changed is the element that supplied the reading, its owner, which may stand
// around what the route aims at, as a widget declares for the control in it that holds
// focus.
function changed(node: Element, aim: boolean) {
  const within = (at: Target | null | undefined) =>
    isElement(at) && renderedUnder(at, node);
  if (aim && within(quiet)) quiet = null;
  if (shown && (shown.target === node || shown.from === node)) {
    show(shown.from, shown.route, shown.read, shown.at, true, aim);
    return;
  }
  const on = focused();
  if (hold?.armed) {
    const target = heldTarget(hold);
    if (isElement(target) && within(target)) show(target, "hold");
    else if (!target && hold.parent === node.parentElement) {
      hold.element = node;
      showHeld(hold);
    }
  } else if (aim && on && within(on) && on.matches(":focus-visible")) showFocus(on);
  else if (beneath && under(beneath, node) && !within(quiet)) {
    over = node;
    // A dwell counting for it reads it as it ends, so news meanwhile, however often,
    // keeps the deadline the pointer's rest set.
    if (!aim && dwelling === node) return;
    pointing = null;
    point(node, null, undefined, aim && within(rested));
  }
}

// Where `K` reads: the element the caret stands in (`userCaret`), where that lies inside
// what focus is on and the user sees the caret's letter, else what focus is on; the
// body with no caret in it is nowhere. A caret scrolled out of sight is nowhere too, as
// a key lets go of focus scrolled out of sight (panel/page-keys/controller.js), though the
// element it stands in, as a long paragraph, still shows.
function here() {
  const on = focused() ?? document.body;
  const caret = userCaret();
  const at = caret?.element;
  if (at && renderedUnder(at, on) && seenRect(caret.letter ?? at, new Map())) return at;
  return on === document.body ? null : on;
}
// Whether a keyboard reading is of what focus is on: its target is the focused element
// or one the focus is drawn inside, as Tab's and `K`'s at focus are, and as `K`'s at a
// caret in a focused message's words is. A reading at the caret of something inside
// what focus is on, as of an age in a focused row, isn't.
const readsFocus = (record: Shown) =>
  record.route === "focus" &&
  isElement(record.target) &&
  renderedUnder(focused(), record.target);

// Focus the user moved to `node` shows its preview once the task that moved it has
// done, which may be opening a popover the platform lets no other open inside, where
// the browser shows that focus, and not where they put this preview away.
const showFocus = (node: Element) =>
  queueMicrotask(() => {
    if (focused() !== node || !node.matches(":focus-visible")) return;
    if (shown?.from !== node) show(node, "focus");
  });

// A new presentation of the document reads the standing preview again, as the place a
// link opens or a thread's turn changes under it: what it says now is drawn where it
// stands, with no fade, and words that came back the same leave it as it is. It is read
// at the moment it first showed (state/presence.js, `atClock`), so a presentation whose only
// change is the clock, as a later state read's, ages nothing it says. A preview whose
// target now says nothing goes.
function refresh() {
  const record = shown;
  if (!record) return;
  const found = atClock(record.clock, () =>
    readFrom(record.from, record.route, record.read),
  );
  if (!found) return hide();
  if (found.target !== record.target)
    return void show(record.from, record.route, record.read, record.at, true);
  render(face(found.reading), body);
  record.reading = found.reading;
  takeWithin(record);
  stand(record, found.reading, true);
}
let refreshing = false;

export function mountPreviews(chrome: HTMLElement) {
  home = chrome;
  chrome.append(stage);
  seated = chrome;
  // Once for each new presentation, a revision's included, after it has painted, and
  // never for a pointer's move.
  const presented = () => {
    if (!shown || refreshing) return;
    refreshing = true;
    void whenDocumentPresented()
      .catch(() => {})
      .then(() => {
        refreshing = false;
        decide(true);
      });
  };
  watchPresentation(presented);
  window.addEventListener("resize", () => decide(true), { passive: true });
  document.addEventListener("scroll", scrolled, { capture: true, passive: true });
  for (const type of ["resize", "scroll"])
    visualViewport.addEventListener(type, () => decide(false), { passive: true });

  document.addEventListener(
    PREVIEW,
    (event) => {
      const [node] = event.composedPath();
      if (isElement(node)) changed(node, Boolean((event as CustomEvent).detail?.aim));
    },
    { capture: true },
  );
  // The platform hides a hint as another popover opens over it, or as a press lands
  // elsewhere, and the record goes with it; a suspended reading's own close keeps it.
  tip.addEventListener("toggle", (event) => {
    if ((event as ToggleEvent).newState === "closed" && shown && !shown.away) hide();
  });
  document.addEventListener(
    "pointerover",
    (event) => {
      if (event.pointerType === "touch") return;
      const path = event.composedPath();
      beneath = isElement(path[0]) ? path[0] : null;
      const still = event.clientX === rest.x && event.clientY === rest.y;
      rest = { x: event.clientX, y: event.clientY };
      // Where the browser shows a title's tooltip, the pointer reads nothing more.
      over = tooltipped(path) ? null : candidate(path);
      // The pointer on a preview keeps it, as on its target (WCAG 1.4.13, "Hoverable").
      if (onPreview()) return ride();
      // Something that arrives under a pointer the user hasn't moved takes it, but
      // shows nothing: the user pointed at what was there before. A pointer carrying a
      // press, as a drag does, is acting, not reading. A target that only redraws
      // under the pointer that came to it, as an entry's icon does, is still what the
      // user pointed at, so the dwell their move began goes on.
      if (still || event.buttons) {
        const target = aimed();
        const stays = sameTarget(target, pointing);
        if (!stays) {
          pointing = target;
          pointingRead = target instanceof Range ? (ranged?.read ?? null) : null;
        }
        if (!stays || event.buttons) stopDwell();
        if (shown?.route === "pointer" && !sameTarget(shown.from, pointing)) hide();
      } else aim();
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      rest = { x: event.clientX, y: event.clientY };
      finger = event.pointerType === "touch";
      // On or off a preview that lets the pointer through is the pointer's place, so it
      // is judged at every move: a pointer sliding into the preview over the element it
      // was already on crosses no element's boundary. A pointer that has left its
      // target for nothing is the only one whose entry needs judging.
      if (riding) {
        if (!inTip()) point(null);
      } else if (!pointing && !finger && onPreview()) ride();
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointerout",
    (event) => {
      if (event.pointerType === "touch" || event.relatedTarget !== null) return;
      beneath = null;
      over = ranged = null;
      point(null);
    },
    { capture: true, passive: true },
  );
  // Focus arriving is a new reading, whatever put the target's last one away, and
  // focus leaving takes its preview along. It shows only where the user aimed it, as
  // whoever moved it says (dom/focus.js, `focusDestination`): a Tab, Shift+Tab or a
  // placement standing in for one (`step`).
  onCurrentLocation((node, cause) => {
    quiet = null;
    if (shown?.route === "focus" && shown.from !== node) hide();
    if (node && cause === "step") showFocus(node);
  });
  // Escape is the preview's own step while one shows, ahead of every other, which does
  // nothing else; any other key but a modifier alone puts a pointer's away, and a
  // keyboard reading of something that doesn't hold focus (`readsFocus`), as `K`'s at
  // the caret on an age, and goes on to its work. A
  // suspended focus reading shows nothing to put away, so Escape goes on to its work
  // and leaves the reading to come back with its subject. The step is rooted where the
  // preview shows, so inside a modal dialog, which makes every scope rooted outside it
  // inert, it stays the first step there too (dom/keyboard/dispatch.js, `stack`).
  pageScope("preview", {
    title: "A preview",
    escape: "inner",
    root: () => tip,
    at: standsForEscape,
    rows: [
      {
        id: "preview.dismiss",
        keys: ["Escape"],
        title: "put the preview away",
        touch: false,
        run: quieten,
      },
    ],
  });
  // A command's landing shows no preview, so the keyboard reads the one where it stands
  // on demand, as an editor's hover key does (Neovim's `K`, VS Code's Show Hover):
  // whatever put focus there, it reads as Tab's would, and again after Escape put it
  // away, since asking is aiming again; at the caret where it stands inside focus
  // (`here`). The scope is rooted at focus, so a modal dialog whose rows an arrow key
  // walks keeps it, and it has no title, so the reference lists it with the page's own
  // keys.
  pageScope("preview here", {
    root: focused,
    rows: [
      {
        id: "preview.show",
        keys: ["Shift+k"],
        title: "Preview here",
        touch: false,
        run: () => {
          const on = here();
          quiet = null;
          if (!on || !show(on, "focus")) notice("Nothing here has a preview");
        },
      },
    ],
  });
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Escape") {
        // Offline the register admits no page scope, this one's included, so the
        // preview takes the press whole itself, as its scope would, and a modal dialog
        // around it stays open.
        if (offlineInteractive && standsForEscape()) {
          event.preventDefault();
          quieten();
        }
      } else if (
        (!shown ||
          shown.route === "pointer" ||
          (shown.route === "focus" && !readsFocus(shown))) &&
        !MODIFIER_KEYS.includes(event.key)
      )
        quieten();
    },
    { capture: true },
  );
  document.addEventListener(
    "pointerdown",
    (event) => {
      endHold();
      spent = false;
      if (shown?.route === "hold") hide();
      finger = event.pointerType === "touch";
      if (!finger) return quieten();
      if (!event.isPrimary || !plainPress(event)) return;
      const found = candidate(event.composedPath());
      if (found?.matches(":disabled, [aria-disabled='true']")) return;
      const origin = event.composedPath()[0];
      if (found && isElement(origin) && origin.hasPointerCapture(event.pointerId))
        origin.releasePointerCapture(event.pointerId);
      // Where no element previews, the hold waits for a range's owner to say what the
      // finger rests on (`holdRange`), which it says as the press arrives.
      const held: Hold = {
        pointerId: event.pointerId,
        node: origin instanceof Node ? origin : null,
        parent: found?.parentElement ?? null,
        element: found,
        range: null,
        says: null,
        at: { x: event.clientX, y: event.clientY },
        armed: false,
        read: false,
        timer: holdsUntold() ? setTimeout(() => arm(held), HOLD) : undefined,
      };
      hold = held;
    },
    { capture: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      if (hold?.pointerId !== event.pointerId || heldTarget(hold) instanceof Range)
        return;
      const path = event.composedPath();
      const found = candidate(path);
      const neighbour = found?.parentElement === hold.parent ? found : null;
      if (neighbour === hold.element) return;
      hold.element = neighbour;
      hold.node = path[0] instanceof Node ? path[0] : null;
      if (hold.armed) showHeld(hold);
    },
    { capture: true, passive: true },
  );
  document.addEventListener(
    "pointerup",
    (event) => {
      if (hold?.pointerId !== event.pointerId) return;
      spent = hold.read;
      endHold();
    },
    { capture: true },
  );
  document.addEventListener(
    "touchend",
    (event) => {
      if (!spent) return;
      spent = false;
      // One the browser won't let be cancelled ended a touch that moved, of which it
      // makes no click.
      if (event.cancelable) event.preventDefault();
    },
    { capture: true, passive: false },
  );
  document.addEventListener(
    "pointercancel",
    (event) => {
      if (hold?.pointerId !== event.pointerId) return;
      endHold();
      if (shown?.route === "hold") hide();
    },
    { capture: true },
  );
  // A tab the user leaves ends what they were reading in it.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      point(null);
      quieten();
      endHold();
    }
  });
  document.addEventListener(
    "contextmenu",
    (event) => {
      if (hold) arm(hold);
      // Only while a held preview shows: a hold over a target that showed none, as an
      // external link, keeps the platform's own long-press menu.
      if (hold?.armed && shown?.route === "hold") event.preventDefault();
    },
    { capture: true },
  );
}

// Once the browser calls the press long, or held for `HOLD` where it says nothing, the
// finger reads, wherever it is now: one that slid onto the gap beside a neighbour reads
// the next it reaches.
function arm(held: Hold) {
  if (hold !== held || held.armed) return;
  clearTimeout(held.timer);
  held.armed = true;
  showHeld(held);
}

// The hold ends with its release, and what it read stands until the next press.
function endHold() {
  if (!hold) return;
  clearTimeout(hold.timer);
  hold = null;
}
