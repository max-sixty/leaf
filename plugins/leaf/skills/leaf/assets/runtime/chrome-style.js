/* The private comment-layer stylesheet. The public runtime supplies the
   declaration-derived names and layout queries interpolated into it. */
export function chromeStyle({
  COVERING,
  MARK_RULES,
  NON_COVERING,
  PAGE_PAINT_ATTRIBUTE,
  PANEL_PROP,
  STRIP_TRAY_RULE,
  TRAY_COVERING,
  TRAY_PROP,
}) {
  return `
  /* The document and the panel are two scroll regions side by side. If the document
     scrolled the viewport, its scrollbar would paint at the viewport's right edge —
     over the panel, in the same few pixels as the panel's own, so the two thumbs
     stack. Body owns the document's scroll instead, and syncLayout keeps its box
     clear of the panel, which puts each region's scrollbar inside that region.

     The gutter is stable because the column is measured off it: a page that grows
     past the window mid-session — a suggestion accepted, a panel of tabs opened —
     would otherwise gain a scrollbar, and the column would re-centre in what was
     left. Stated rather than measured, because it can't be measured here: macOS
     draws overlay scrollbars, which take no room and reserve none, so on this
     machine the declaration is a no-op and the shift it prevents cannot be made to
     happen (neither scrollbar-width nor a styled ::-webkit-scrollbar nor
     --disable-features=OverlayScrollbar brings a room-taking one back). It is kept
     on the platforms where scrollbars do take room, which is most of them, and on
     the reasoning that reserving a gutter never costs more than the shift not
     reserving it produces.

     All of it is the live page's, and it is withheld from the other two media the way
     every other affordance is. A copy has no panel to sit beside and no session to
     grow in, and it carried the whole arrangement anyway: body scrolled it, reserving
     a gutter against a change that can no longer happen and holding 54px of scroll
     padding under a banner the file hasn't got — so wherever a scrollbar takes room
     the copy's column sat 7.5px left of the centre of a page it had all of. Nothing
     on this machine could say so, the declarations being no-ops here; the runner said
     it, on every example at once. That is what pins this now
     (test_an_exported_example_stands_on_its_own, and scripts/linux-suite.sh is where
     to watch it fail), and paper needs no rule of its own, never having been handed
     the arrangement to undo. Spelled :where(), because these declarations are the only
     statement their properties get and the plain form would hand every one of them a
     class the body rule below never had. */
  @media screen {
    :where(html:not(.lf-copy)) {
      height: 100%;
      overflow: hidden;
      /* The foot is the same claim the head makes, in the size a ring needs rather than
         a banner's: a control landed on at the fold had its border box put flush with
         the window's bottom edge and its ring in the strip past it, so the last row of
         a page was reached with the ring around it cut off. The panel's own list says
         the same thing about its own edges. */
      body { height: 100%; overflow-y: auto; scrollbar-gutter: stable;
             scroll-padding-top: calc(var(--lf-banner-h) + 12px);
             scroll-padding-bottom: var(--here-ring-room); }
      /* The banner stands over the head of the document, so the page's first lines get
         room rather than starting under it, and the key line reserves the same at the
         foot (syncLayout). Both are boxes in the flow rather than padding on body, which
         is the box the room a wide widget spends is measured from — CLAUDE.md's "The one
         writer may not write the box the layout is measured from" carries why. A box also
         adds to whatever padding the page declares at this edge, where a rule here would
         replace it, and it is withheld from paper by the block it sits in: written as
         padding it stayed behind, holding 42px of blank over the first line of every
         printed page for a bar that was not on it. */
      body::before { content: ""; display: block; height: var(--lf-banner-h); }
    }
  }
  /* position: relative makes body — the scroll container — the containing block for
     the two floats that point into the document (the 💬 button and the composer), so
     the browser scrolls them with the passage they stand beside. */
  /* The banner's height, said once. Everything at the top edge derives from it — the
     bar itself, the panel starting under it, the focus-revealed mark note, the
     scroll padding that keeps an anchored jump out from beneath it (plus air) — and
     the room the document leaves for it. */
  /* The chrome's line box, said once, because one control in the banner cannot be
     told it. Chrome computes a select's inner height from its own metrics and
     refuses line-height outright — the computed value stays normal however the
     rule is written — so the chooser stood 3.3px shorter than every button beside
     it, centred, and read as sunk into the row. Its height is stated instead, from
     this and its own padding (see the chooser's rule), which is the same number
     .lf-btn arrives at through the line box. Stated in one place so the two cannot
     come apart: a third copy of 1.45 is exactly the drift the reserve comment below
     is about, and this one would show as the chooser sinking again. */
  body {
    --lf-safe-top: env(safe-area-inset-top, 0px);
    --lf-safe-right: env(safe-area-inset-right, 0px);
    --lf-safe-bottom: env(safe-area-inset-bottom, 0px);
    --lf-safe-left: env(safe-area-inset-left, 0px);
    --lf-banner-h: calc(42px + var(--lf-safe-top));
    --lf-ui-lh: 1.45;
  }
  @media screen and ${COVERING} {
    body { --lf-banner-h: calc(96px + var(--lf-safe-top)); }
  }
  /* A wide touch layout keeps the desktop row, but its forty-four-pixel aims and their
     focus ring need a taller bar than the mouse-sized row. This one derived height moves
     the page, panels, anchored jumps, and the banner edge together. */
  @media screen and (pointer: coarse) and ${NON_COVERING} {
    body { --lf-banner-h: calc(53px + var(--lf-safe-top)); }
  }
  body { position: relative; box-sizing: border-box; }
  /* The strip the panel takes is given up as motion rather than as a jump, so the eye
     can follow the sentence it was reading to where it went. Keyed on the stamp that
     says the document is done becoming itself, because until then every margin the
     page has is one it arrived with: a panel restored open would otherwise slide into
     place on load, and a version switch is a load, so every revision would arrive
     sliding sideways under a user who asked for a revision and not for motion.
     The stamp lands at the end of the start chain, long after the restore. Reduced
     motion is handled globally by the theme's guard. */
  body[${PAGE_PAINT_ATTRIBUTE.upgraded}="1"] {
    transition: margin-right .18s ease, margin-left .18s ease; }
  /* The strip itself, and — where there is no room to yield one — the page handing
     scrolling over to the sheet that covers it instead. A margin, not padding: body is
     the document's scroll container, so this is what ends its box, and its scrollbar, at
     the panel's edge rather than under it. Under a covering sheet one wheel gesture still
     moves one region, and the region is the thread list; the page holds its place for
     when the sheet closes — a hidden-overflow scroller keeps its position, and still
     moves for a t/T walk or a version switch restoring where the user was, so the passage
     behind the sheet is the one the panel is talking about.

     The cascade's, though syncLayout is the layout's one writer, because body's box is
     the one thing that writer may not write: it runs from an observation of that box, and
     a write from inside that round is a resize of what was just reported — the round
     breaks, and Chrome says so on the window's error channel and nowhere else (CLAUDE.md,
     "The one writer may not write the box the layout is measured from"). Written in JS it
     survived on a coincidence: the margin transitions, so the used value did not move
     until the frame after the write, and the round the write landed in closed intact. A
     stylesheet is where a fact about the shape of the page belongs anyway, and the panel
     states only that it is open.

     The strip comes out of the page rather than being held aside for it, which makes
     opening the panel the largest movement in the product: the column re-centres by half
     the panel's width, and on a window narrow enough to lose width as well it rewraps
     every line. Both are carried as motion rather than as a jump — the transition above,
     keyed on the stamp for the reasons given there — because an eye can follow a sentence
     that slides and cannot find one that teleports. */
  @media screen and (not ${COVERING}) {
    body[data-lf-panel] { margin-right: var(${PANEL_PROP}); }
  }
  @media screen and ${COVERING} {
    body[data-lf-panel] { overflow-y: hidden; }
  }
  /* The slide stands down for as long as the reader is holding the edge. A drag is a hand
     on that edge, and 180ms of easing behind it is the page sliding out from under the
     gesture that is moving it — the panel's own box follows the pointer exactly, so an
     eased margin is the two edges of one edge coming apart. Every other way the margin
     moves still wants the slide, an arrow step on the edge included: a step is one
     discrete move the eye can follow, which is what the rule above is for. */
  body[data-lf-sizing] { transition: none; }
  /* A tray that takes its room out of the page takes it the same way, off the one
     attribute showTray writes to say which tray is up and the one list that says which
     of them the page yields to (STRIP_TRAYS, where the reasons are). Everything else
     about the strip — that it comes out of the page rather than being held aside, that it
     is carried as motion, what it costs on a window narrow enough to rewrap — is the
     panel's story above, told once for both sides. */
  @media screen and (not ${TRAY_COVERING}) {
    ${STRIP_TRAY_RULE} { margin-left: var(${TRAY_PROP}); }
  }
  @media screen and ${TRAY_COVERING} {
    ${STRIP_TRAY_RULE} { overflow-y: hidden; }
  }
  /* Rules at this level are the shared vocabulary: classes whose whole job is
     elements the page owns — a widget's controls wear lf-ui and lf-btn, and the
     runtime marks the page's own elements (lf-mark-el, lf-ins-block). Adding one
     widens the vocabulary; a rule that styles the runtime's own layer goes in the
     @scope block below instead. */
  .lf-ui, .lf-conversation-msg.lf-ui, .lf-say.lf-ui { font-family: var(--sans); font-size: var(--t-5); line-height: var(--lf-ui-lh); color: var(--ink); box-sizing: border-box; }
  .lf-ui *, .lf-ui *::before, .lf-ui *::after { box-sizing: inherit; }
  /* Clearing the UA's form-control face is a different kind of declaration from
     choosing one, so the clearing lives in a layer, which any unlayered choice
     outranks whatever its specificity. That makes unrepresentable what used to be a
     cascade race: a control wearing .lf-ui itself takes the chrome face from its own
     class instead of inheriting past it into the document's serif (the 💬 button shipped
     that way, at 17px), and the one control whose face is deliberately the document's —
     lf-draft's editor, which must match the body it replaces — states so unlayered in
     the theme and wins that. A layered rule still outranks the UA's, which is all the
     clearing ever needed. */
  @layer lf-reset {
    .lf-btn, .lf-ui textarea, textarea.lf-ui { font: inherit; }
  }
  /* A control a widget injects is a span wearing its ARIA role, so the box and the drag
     that a native control supplied are stated here. Only .lf-btn needs the box because
     every other control is a flex item or positioned. A native control also refuses a
     drag, which is worth keeping wherever its words are the runtime's and is exactly what
     must not happen where one of them is the page's. So selection goes off only where
     nothing under the control is said: a descendant cannot win it back, since user-select
     none on an ancestor takes the whole subtree out of a pointer's reach whatever the
     descendant declares. */
  .lf-btn { padding: 4px 10px; border: 1px solid var(--border-2); border-radius: 6px; background: var(--card); cursor: pointer; white-space: nowrap; color: inherit; display: inline-block; }
  .lf-ui:is([role="button"], [role="checkbox"]):not([data-lf-said]):not(:has([data-lf-said])) { user-select: none; -webkit-user-select: none; }
  .lf-btn:hover { background: var(--chip); }
  .lf-btn.primary { background: var(--accent); border-color: var(--accent); color: var(--paper); }
  .lf-btn.primary:hover { filter: brightness(.92); }
  /* Two selectors, two mechanisms, one look: the platform's own on the banner's real
     buttons, and the attribute wireInput sets, which is the only one a span press can
     wear. */
  .lf-btn:disabled, .lf-btn[aria-disabled="true"] { opacity: .55; cursor: default; }
  .lf-btn.on { border-color: var(--accent); color: var(--accent); background: var(--chip); }
  /* Pills remain the compact label shape used by chrome and conversation surfaces.
     Target actions use .lf-margin-action below: one stricter control type shared by
     content widgets, page-map information, and communication gestures. */
  /* Words for a reader listening, silent on screen: real text, the one thing every
     screen reader announces in every mode, clipped to nothing where paint already says
     the same fact to the eye (renderQuiet, and lf-code's highlighted lines). Worn with
     .lf-ui, since an invisible word is apparatus the anchor pass must not offer — a
     quote resolved into a clipped box would paint a mark nobody can see. Out of flow,
     so it holds no room; the covered-words gate skips this class the way it skips the
     runtime's own .lf-mark-note, which wears the same clip.

     And out of the selection, which the clip does not do on its own: a word standing
     among the page's own words is inside any selection drawn across them, so the
     runtime's reading skipped it and the user's clipboard did not — a copied task line
     came away carrying the word "done", and a copied code block would carry
     "highlighted" into whatever editor it was bound for. .lf-mark-note had answered
     this the day it was written and the clip it shares had not — two copies of one
     recipe, already drifted apart, which is why there is one of them here now.

     No offsets, so the box keeps the static position its holder gives it. That place is
     read: shownBox reads it for a wrapper that draws no box of its own, and everything
     asking where such an element is asks through that. What the box must not do is
     escape the box it sits in, which it did — an out-of-flow box with no positioned
     ancestor is positioned against the page, so the count on a cell of a table scrolling
     inside itself stood three hundred pixels past the window with the page scrolling
     sideways to reach it. The scroller answers for it, and the runtime sees to that:
     reachScrollers marks every static box that scrolls, and the theme positions the
     mark ([data-lf-holds]). */
  .lf-quiet, .lf-mark-note { position: absolute; width: 1px; height: 1px;
    overflow: hidden; clip-path: inset(50%); user-select: none; -webkit-user-select: none; }
  .lf-quiet { white-space: nowrap; }
  .lf-pill { font-size: var(--t-6); line-height: 1.7; padding: 0 8px; border: 1px solid var(--border-2); border-radius: 999px; background: var(--card); color: var(--ink-2); white-space: nowrap; }
  .lf-pill:is(button, [role="button"]) { cursor: pointer; }
  .lf-pill:is(button, [role="button"]):hover { background: var(--chip); }
  /* The pluggable RHS action. Contributors choose glyph, label, tone, and collapse
     policy through marginAction(); this declaration owns every visual and interactive
     constant that makes unlike verbs read as one family. Width may follow the word,
     but height, capsule, type, state, and focus never follow the contributor. */
  .lf-margin-action {
    box-sizing: border-box; min-width: 30px; min-height: 30px; padding: 2px 9px;
    border: 1px solid var(--border-2); border-radius: 999px;
    background: var(--card); color: var(--ink-2);
    display: inline-flex; align-items: center; justify-content: center; gap: 0;
    font: 600 var(--t-6)/1 var(--sans); white-space: nowrap; cursor: pointer;
    scroll-margin-block: var(--here-ring-room);
  }
  .lf-margin-action:hover:not([aria-disabled="true"]) { background: var(--chip); }
  .lf-margin-action:is(:focus-visible, .lf-focus-visible) {
    outline: var(--here-ring); --lf-here-ring: margin-action; outline-offset: 1px;
  }
  .lf-margin-action[aria-disabled="true"] { cursor: default; }
  .lf-margin-action[data-lf-tone="positive"]:hover:not([aria-disabled="true"]) {
    border-color: var(--ok); color: var(--ok-ink); background: var(--ok-tint);
  }
  .lf-margin-action[data-lf-tone="negative"]:hover:not([aria-disabled="true"]) {
    border-color: var(--danger); color: var(--danger-ink); background: var(--danger-tint);
  }
  .lf-margin-action[data-lf-tone="positive"][aria-disabled="true"] {
    border-color: var(--ok); color: var(--ok-ink); background: var(--ok-tint);
  }
  .lf-margin-action[data-lf-tone="negative"][aria-disabled="true"] {
    border-color: var(--danger); color: var(--danger-ink); background: var(--danger-tint);
  }
  .lf-margin-action[data-lf-tone="primary"] {
    border-color: var(--accent); background: var(--accent); color: var(--paper);
  }
  .lf-margin-action[data-lf-tone="primary"]:hover:not([aria-disabled="true"]) {
    filter: brightness(.92); background: var(--accent);
  }
  .lf-margin-action.lf-react[aria-pressed="true"] {
    border-color: var(--mark-ink); color: var(--mark-ink); background: var(--mark);
  }
  .lf-margin-action-glyph { line-height: 1; }
  .lf-margin-action-space { white-space: pre; }
  .lf-margin-item.lf-condensed > .lf-margin-contribution { min-width: 0 !important; }
  .lf-margin-item.lf-condensed .lf-margin-action[data-lf-collapse="auto"] {
    width: 30px; min-width: 30px !important; padding-inline: 0;
  }
  /* A gesture the log has not answered yet, in the platform's own word for it, which
     is why no tag is named here: any widget that says aria-busy is painted, and
     lf-draft was saying it to screen readers alone before this rule existed.

     Delayed, and that is the whole design. A press paints nothing until the log
     takes it, which locally is about 40ms — a look that appeared and left inside
     that window would be a second flicker put where the first one was removed. Past
     the delay there is something to say, and the cases where there is are the ones
     that need it: a heavy page, or a reader who reached a --host page across a
     network. So the surface goes quiet only once the wait has run long enough to
     notice, and a fast answer never shows this rule at all. The reduced-motion guard
     (theme.css) zeroes the duration and leaves the delay standing, which is the right
     reading of it: the fade is what a reader asked not to have, the waiting is not.

     Opacity and the cursor, never geometry: the line a press is made on holds still
     (lf-suggestion.js), and a busy surface that reflowed would move the control out
     from under the pointer that just pressed it. */
  [aria-busy="true"] { animation: lf-runtime-4f3c2a8d-working 140ms linear 200ms both; }
  [aria-busy="true"], [aria-busy="true"] :is(button, [role="button"]) { cursor: progress; }
  /* Standing on a press, in the band everything else the reader stands on is drawn in
     (--here-ring). The two shapes were the last places on the product still wearing the
     browser's own ring: a reader who backed out of the panel landed on Threads in
     Chrome's blue, beside a decision wearing the page's accent, with nothing saying the two
     rectangles meant one thing.

     Each states its own gap, because they stand at different densities and the ring may
     not reach its neighbour: the standing gap is what a box with room around it takes,
     the composer's row puts 6px between two buttons, and margin actions sit 4px
     apart out in the margin. The pill's rule was the suggestion family's, which is a
     family stating a fact about a shape the runtime owns — its own rules there are for
     what a decided suggestion adds, and a focus ring is nothing a decision changes. */
  .lf-btn:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: btn; outline-offset: 2px; }
  .lf-pill:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: pill; outline-offset: 1px; }
  /* The keyboard address: the keys that reach this thing right now, worn as a chip
     off its holder's corner so an address arriving moves nothing. The g chord paints one
     on every member of every list it offers and an option wears the one a pick
     answers, which is the same promise made on the two sides of the chrome's scope line —
     so it is stated here, at the level both can reach, rather than as the twelve
     declarations each once carried. They had not drifted; nothing was going to say so if
     they did. What a wearer keeps is where its chip sits and when it shows — the chord's
     stand in a layer of their own, placed on each member's visible corner, an option's in
     a column that option holds for it. This rule dresses; theirs place and paint.

     The box follows the type rather than standing beside it, and --lf-key-box says how
     (theme.css, where it is stated because an option's column has to read it back).
     Height and the square floor are both that, so the ring keeps its
     clearance and a one-key address comes out square whatever the type is set at. At --t-6
     it lands on the 17px interior and 19px box this chip has always been drawn to, so
     nothing moves today — but a package may redeclare the ladder, theme files being
     concatenated, and a fixed interior beside a token font is a box its own glyphs grow out
     of. They painted over the ring at about 14.6px, and the reference's keys (.lf-help kbd)
     have no fixed height at all, so the two would have parted at the first override.

     Stated as a height and not left to the content, because one wearer does not size itself
     from its content at all: an option's digit in the row form is absolutely positioned
     against top and bottom together and centred with auto margins, so a box with no height
     of its own stretches to the whole row — 30px against the chord's 19 — and the auto
     margins have nothing left to centre. 4px of side padding is what holds a glyph off the
     ring, and it is the same 4 for both wearers: a pick's address is one digit, so its whole
     width is the square floor, and two more pixels a side put it past that floor and drew a
     rectangle. Nothing here is a chip's own to restate — the render suite holds the two
     faces to being one declaration, padding included.

     Border-box is what makes those numbers true on both sides of the scope line: the page
     sets none, so the copy in an option came out two pixels wider than the chord's — the
     drift this one rule was written to make impossible.

     Mono and a 4px radius because this is a key chip, dressed as the line and the
     reference dress theirs (.lf-help kbd, .lf-keyline kbd; the render suite compares the
     two). The face is the half that had to be right: the chord's chips carry the letter
     now, and in the sans a lowercase l is a bare stroke, so the second link on a page
     wore what read as 12.

     Wide enough for the keys it carries and no wider, down to that floor: a pick's
     address is one digit and comes out square, the chord's is the whole motion — leader,
     letter and digit — and comes out wide. Stated as a fixed width instead, the second
     would have needed a rule of its own in the chord's layer, and the family would have
     been dressed in two places. The keys hold one line, the box being shrink-to-fit and
     placed from a corner — one near the window's right edge would otherwise break in
     two.

     --t-6 and not a number of its own: that is what the line and the reference already
     set their keys at, and a key chip is one thing wherever the reader meets it. The 11px
     it held was half a pixel under the surfaces it is meant to match.

     The interior is two pixels deeper than the 15 it stood at, which is room for the lit
     block a chord chip carries: an inline background paints the font's own box and not the
     line's, so the block comes out inset from the chip's edge by itself, and the spare
     height is what makes that inset visible rather than a hairline. A flex box would centre
     it as surely and cost the space between the keys — flex drops a whitespace-only text
     node, so the address rendered as "ga 1", correct in every rule here and wrong in the
     one place a reader looks. */
  .lf-address { display: none; box-sizing: border-box; min-width: var(--lf-key-box); height: var(--lf-key-box); padding: 0 4px; border: 1px solid var(--accent); border-radius: 4px; background: var(--card); color: var(--accent); font-family: var(--mono); font-size: var(--t-6); line-height: 1.478; text-align: center; white-space: nowrap; z-index: 1; }
  /* The leaf text box, in one rule. field-sizing does the growing, so no script
     measures a textarea: the JS that did had to reset height to auto to re-measure,
     which made the box briefly too small for its own text on every keystroke — and a
     box that overflows, however briefly, flashes a scrollbar. Past max-height the
     scrollbar is real and stays — and the ceiling is the viewport's share, not a count
     of lines: 200px stopped a long comment at ten lines with the screen mostly empty.
     Both selectors: the panel's boxes sit inside .lf-ui, a widget's own box wears the
     class itself. */
  .lf-ui textarea, textarea.lf-ui { padding: 8px 10px; border: 1px solid var(--border-2); border-radius: 6px; background: var(--card); color: inherit; resize: none; field-sizing: content; max-height: 50vh; overflow-y: auto; }
  .lf-ui textarea:is(:focus, .lf-focus), textarea.lf-ui:is(:focus, .lf-focus) { outline: none; border-color: color-mix(in srgb, var(--accent) 45%, var(--card)); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent); }
${MARK_RULES}
  body.lf-over-mark { cursor: pointer; }
  /* Holding ⌥ changes what a click means, and nothing on the page said so — the chord's
     whole cost is that it is invisible. Two things say it, and the division matters:
     the item under the pointer wears the aim's box (.lf-aim, in the chrome's scope
     block), which answers *which*, and the cursor answers
     *whether*. crosshair was tried and read as a cross — an icon for closing something,
     not for aiming at it — and copy, alias and a menu each name an action this isn't.
     What is left is the pair this page already spends on that same distinction one line
     above: the hand where a press acts, the arrow where it doesn't. Armed, a press acts
     exactly where there is an item under it and on nothing where there isn't
     (claimPress), so those two states are those two cursors, and the hand promises no
     more than the box beside it does.
     The plain arrow alone was the first answer and it under-promised. It says only "not
     a text selection", which is the half a reader can already infer from the box,
     and it says the same thing over a gap a press does nothing in as over the paragraph
     a press would take whole — so the one question the box leaves ("would this
     click do anything?") was the one the cursor declined to answer, and a user held the
     key and asked it out loud.
     Derived at the paint, off the value refreshAim resolved for the box, so there
     is one answer to what the aim is on rather than a second reading free to disagree
     with what is drawn.
     What this does not reach is a control that states a cursor of its own — a
     suggestion's ✓ Accept, an option row — which goes on showing its hand while an armed
     press is being swallowed above it. Inherited declarations lose to declared ones, so
     covering that means either an important universal rule or naming this container at
     document level to hold the chrome out of it, and both are worse than the case: the
     box is absent there, which is the honest half of the answer, and the control's
     hand says what it always says rather than something new and wrong.
     One declaration on the body, inherited, rather than a rule reaching down the page:
     naming .lf-chrome here to hold the chrome out would put that class into the
     document-level surface, and the class the chrome is rooted at is not vocabulary a
     widget wears. The chrome holds itself out instead, from inside its own scope. */
  body:is(.lf-aiming, .lf-design) { cursor: default; }
  body:is(.lf-aiming, .lf-design).lf-over-item { cursor: pointer; }
  /* One pixel, just inside the border box, because both sides of that edge belong to
     somebody else. Outside it, the mark belongs to whatever encloses the element: a board
     scrolls (overflow-x: auto), its columns sit flush against its padding box on three
     sides, and a mark drawn outside a column was clipped down to the single vertical line
     that fell in the gutter. Deeper inside, it belongs to what the element paints over
     itself: an outline is painted before positioned descendants, so a container whose cells
     carry a background — every choose group, since lf-option is relative — wipes out
     whatever of the mark reaches past its own border. Containers are exactly what element
     anchoring is for, so neither is a corner, and the second was what a reader reported: a
     2px mark two pixels in came out a hairline on three sides of the group they had just
     commented on and stayed 2px along the bottom, where the last cell stops short, so the
     box was thicker at the bottom than the top. One pixel in is inside every ancestor's
     clip and, wherever the element has a border of its own, outside every child's paint,
     which is 72 of the 73 markable elements measured across the examples — the odd one a
     mermaid node whose fractional width antialiases a device pixel either way.
     The 73rd is the shape this does not reach, and it is worth naming because the fix
     stops there rather than because it arrived with it: an element with no border of its
     own whose positioned child is flush to the border box has no such band, so lf-shot
     paints its frame over the mark's left and right and the reader gets a rule above and
     below the figure and nothing down its sides. That was equally true at 2px two pixels
     in — nothing here regressed it — and it is not reachable from a stylesheet, since the
     only band left is outside, where a scrolling ancestor takes it. What would reach it is
     a widget declaring that it paints to its own edge, and no widget needs to yet.
     A hairline is not a fainter mark than the 2px was: --mark-ink clears 9.0:1 on the
     paper where the burnt orange it replaced cleared 3.4, so this reads as an annotation
     where a saturated 2px rectangle read as a validation error. It takes the element's own
     corner radius rather than restating one, which is what the radius here used to
     override. */
  .lf-mark-el { outline: 1px solid var(--mark-ink); outline-offset: -1px; cursor: pointer; }
  /* A standing reaction on an element: the same hairline, dashed — a mark fainter than a
     comment's, as the wash on a reacted passage is fainter than a comment's (--react in
     theme.css, ::highlight below). No hand, since nothing opens on a press here: the
     glyph in the margin is the control. */
  .lf-react-el { outline: 1px dashed var(--mark-ink); outline-offset: -1px; }
  /* A copy carries the wash as a <mark> the export wrote into the words, the highlight
     registry being script state no file can hold (BAKE). */
  html.lf-copy mark.lf-react { background: var(--react); color: inherit; }
  /* The glyphs of the reactions standing on a target — a pill per reaction, the pill
     being the reaction's own eraser (anchors.js seatReactions). This is an unpositioned
     contribution: the living margin joins it to the target's other RHS controls and
     decides whether their one complete item hangs or docks. */
  .lf-reacts { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
  .lf-react-mark { text-align: center; }
  /* The draft's own passage — a standing annotation like the posted mark, which is why
     it may share the hairline where the ⌥ aim's promise may not (the .lf-aim rule in
     the scope block says why). Only the colour separates it from a posted mark, and the
     colour moved: the burnt orange stood 77 ΔE from the accent and --mark-ink stands
     24, both now at a hairline. What keeps the two apart is no longer the paint alone —
     an open composer is on screen whenever this one is, and an element a thread already
     marks keeps the posted colour rather than taking this (paintAnchors), so the pair
     never contend on one element. */
  .lf-mark-el.lf-pending { outline-color: var(--accent); cursor: auto; }
  /* The element anchor of the comment the pointer is indicating (paintHover), which is
     the same middle step the text mark takes in its wash. A box has no glyphs, so
     ::highlight paints nothing on one and the pointer used to leave an element-anchored
     comment with no answer at all — from the panel especially, where there is no page
     cursor to change and a card that lit nothing was indistinguishable from a card whose
     hover had broken. Said in the property the element mark already ranks in: 1px
     --mark-ink posted, 2px --mark-ink indicated, 2px --accent stood in. Inset to -2px
     for the reason the standing ring gives below — the offset is to the outer edge, so a
     doubled width at -1px pokes a pixel into the band a scrolling ancestor clips. Before
     the standing rule, so an element that is both takes the accent.

     The keyboard indicates the same way the pointer does, and it has to be said here
     because the hairline above is an author's outline and the ring a focused element
     would otherwise wear is the platform's: the hairline wins, and it is drawn whether
     or not anything is focused, so tabbing onto a marked box changed nothing on screen.
     One box in the corpus is both focusable and markable today — a diagram carrying an
     element comment — and this is not a rule about diagrams: any outline an element
     wears for a reason other than focus takes the platform's ring away from it, and the
     walk in the suite is what says so the next time it happens. */
  .lf-mark-el:is(.lf-mark-hover, :focus-visible, .lf-focus-visible) { outline-width: var(--here-ring-w);
    outline-offset: calc(-1 * var(--here-ring-w)); }
  /* The standing comment's element anchor (paintStanding). It keeps the hairline's own
     inset rather than taking the decision ring's gap, so focusing the thread changes the ring
     where it already is instead of moving it outward by four pixels — the mark is the
     same mark. -2px and not the hairline's -1px because the width doubles: the offset is
     to the outer edge, so the ring drawn at -1px would poke a pixel outside a box the
     hairline stayed inside, and the reason that inset exists is that the band outside is
     where a scrolling ancestor takes it. Grown inward, the outer edge does not move.

     No lift here, unlike the text mark's wash. What defeats colour between two marked
     passages is that both are washes and the two inks are close in darkness; between two
     marked boxes there is a 1px violet hairline and a 2px accent ring, which differ in
     weight as well as hue and are told apart on sight — checked on a composed page, not
     assumed. A pulse would be motion answering a question already answered. */
  .lf-mark-el.lf-mark-here { outline: var(--here-ring); --lf-here-ring: element-mark;
    outline-offset: calc(-1 * var(--here-ring-w)); }
  /* Armed, a press on a thread-marked element is the aim's, not the thread's, so the
     hand here is the aim's answer rather than the thread's: it stands where the aim has
     an item and comes off where it hasn't, which is the same promise the body is making
     and not the mark's own "open this thread". */
  body:is(.lf-aiming, .lf-design) .lf-mark-el { cursor: default; }
  body:is(.lf-aiming, .lf-design).lf-over-item .lf-mark-el { cursor: pointer; }
  /* Keyboard access to a picture is runtime chrome beside the provider's drawing rather
     than a role written onto that drawing. Resting it is a conventional clipped control;
     focus gives it a skip-link-style face under the banner. */
  .lf-visual-actions { display: contents; }
  .lf-visual-action { pointer-events: none; }
  /* The one runtime word living inside the page's own elements, so its hiding cannot
     come from the chrome's scoped .lf-unseen: it wears the clip .lf-quiet wears, stated
     once above for both. It becomes a skip-link-style control on focus: a reader who
     hears the count can enter its first thread, then t/T through the rest. The rule
     below states its whole visible form, so the resting one adds nothing to the clip —
     the padding and border reset that stood here were a real button's, and the note has
     been a span since offer() built it. */
  .lf-mark-note:is(:focus-visible, .lf-focus-visible) { position: fixed; z-index: 9050;
    top: calc(var(--lf-banner-h) + 6px); left: 8px;
    width: auto; height: auto; padding: 6px 10px; overflow: visible; clip-path: none;
    border: 1px solid var(--accent); border-radius: var(--r); background: var(--card);
    color: var(--ink); box-shadow: 0 8px 24px rgba(0,0,0,.12); }
  .lf-visual-action:focus-visible { position: fixed; z-index: 9050;
    top: calc(var(--lf-banner-h) + 6px); left: 8px;
    width: auto; height: auto; max-width: calc(100vw - 16px); padding: 6px 10px;
    overflow: visible; clip-path: none; pointer-events: auto; white-space: normal;
    border: 1px solid var(--accent); border-radius: var(--r); background: var(--card);
    color: var(--ink); box-shadow: 0 8px 24px rgba(0,0,0,.12);
    outline: var(--here-ring); --lf-here-ring: visual-target;
    outline-offset: calc(-1 * var(--here-ring-w)); }
  .lf-ins-block { background: var(--add-tint); box-shadow: 0 0 0 4px var(--add-tint); border-radius: 2px; }
  /* The unanswered decision the reader is standing in (markHere), worn by the decision rather than
     by whichever of its controls holds the focus — they are standing in the whole thing,
     however they got there. Unanswered and not open: a widget whose own seat is
     mid-conversation with the agent has left the reader's list while the reader is still
     standing in it. Exactly one decision wears it at a time: every shipped widget
     draws one box for it to paint on, and one a page styles boxless hangs it on the
     boxes its contents make (shownParts). While the decisions tray is open, its row mirrors
     the same fact — for a decision the tray lists, which is one the reader still owes. It is an outline like every other mark the
     runtime paints on the page's own elements: it moves nothing on arriving, and it
     keeps its place for nothing, being the element's own paint rather than a box in
     the chrome that would have to chase it down every scroll, reflow and drag. */
  [${PAGE_PAINT_ATTRIBUTE.decision}] { outline: var(--here-ring); --lf-here-ring: decision; outline-offset: var(--here-ring-gap); }
  /* Paper takes no input, so what a widget injects to be worked goes: the control,
     and the box that holds controls. What stays is a control whose label is one of
     the page's own words — a pick mark reading "chosen" is the only place the page
     says which option it carries — which is why this keys on the declaration each
     label makes (see relabel) rather than on .lf-ui, whose question is anchoring's.
     Asked of the control itself, not of what it holds: a settled group's disclosure
     names the chosen card, and that word is worth keeping on screen where the row is
     the only place it stands and worth dropping on paper, where the cards are open
     underneath saying it themselves. An exported copy strikes the same bargain on the
     same two markers, and takes the control out of the document rather than hiding it,
     which paper cannot do (BAKE). The runtime's own layer hides as one thing, in the
     @scope block below. */
  @media print { [data-lf-offer]:not([data-lf-said]) { display: none !important; } }
  /* Keyframe names are document-global even beside an @scope block. The stable salt
     makes this runtime-private in the one CSS namespace scoping cannot protect. */
  @keyframes lf-runtime-4f3c2a8d-pulse { 50% { opacity: .35; } }
  @keyframes lf-runtime-4f3c2a8d-working { to { opacity: .5; } }
  @keyframes lf-runtime-4f3c2a8d-flash {
    0% { background: var(--hi-tint); } 100% { background: var(--card); }
  }
  @keyframes lf-runtime-4f3c2a8d-grow {
    0% { opacity: 0; transform: translateY(-6px) scale(.985); }
  }
  /* Everything below is private to the chrome, scoped to the runtime's own container:
     no widget or page class can match a rule here, whatever it is named. (lf-tabs once
     marked itself lf-live — this block's name for the visually-hidden live region —
     and every tabbed page clipped to a pixel.) */
  @scope (.lf-chrome) {
    /* The layer is the runtime's, not the document's, so it never prints — one rule
       for all of it, rather than each piece remembering. :scope is the container
       itself, which is why this can't be written at document level without widening
       the shared vocabulary by a class only the runtime ever wears. */
    @media print { :scope { display: none; } }
    /* The hand only where the press lands. An element anchor wears its outline
       wherever its element stands, the layer's own parts included — that is what lets
       a design comment about the banner point at the banner, and a thread about a
       question an agent asked in a reply point at the question. What the outline may
       not do here is offer the hand: markAt refuses a press inside this container on
       purpose, because what the container holds keeps its own presses — the Threads
       button opens the panel, an option takes a pick, and neither opens a thread. So
       the outline goes on saying which element, and stops promising a click nothing
       takes. Scoped rather than written at document level, where it would widen the
       shared vocabulary by this container's own class. Design mode's rules outside
       outrank this at a weight it cannot reach and draw the arrow here too, which is
       the same answer arrived at twice: the aim never lands in the chrome (isItem), so
       the hand it promises is not one this mark could offer either. */
    .lf-mark-el { cursor: auto; }
    /* What the layer inherits from the document, answered at the layer's root, because
       the document below is a page of prose and this is not it.

       cursor, because the page's own body may be armed for ⌥ aiming — a statement about
       the document, not about anything in here. Stated on this side so the document side
       needs no mention of this container's class, which would widen the shared vocabulary
       by a name no widget ever wears.

       The face, so anything in here that misses .lf-ui still inherits the chrome's
       rather than the document's. The reset layer (above) is what keeps a control that
       *wears* the class from walking past it — the 💬 button once inherited straight
       into the page's serif at 17px that way — and this is the same answer for the
       text around the controls. */
    :scope { cursor: auto;
      font-family: var(--sans); font-size: var(--t-5); line-height: var(--lf-ui-lh); }
    .lf-banner { position: fixed; top: 0; left: 0; right: 0; z-index: 9000; height: var(--lf-banner-h);
      display: flex;
      align-items: center; gap: 10px;
      padding: var(--lf-safe-top) calc(14px + var(--lf-safe-right)) 0
        calc(14px + var(--lf-safe-left));
      background: var(--veil); backdrop-filter: blur(6px); border-bottom: 1px solid var(--rule); }
    .lf-banner-status, .lf-banner-actions { display: flex; align-items: center; gap: 10px; }
    .lf-banner-status { flex: 0 1 max-content; min-width: 24px; }
    /* The actions are their own shelf whenever the status and available destinations no
       longer share the row. The DOM puts each edge's control nearest the panel it opens:
       Threads leads the covering shelf, while All leaves leads the wide row beside its
       left-hand tray. Keyboard focus and a horizontal gesture can bring every later
       address wholly on screen without widening the document. Usually there is nothing
       to scroll, so the wide arrangement keeps its ordinary single-row reading. Four
       pixels around the contents belong to the controls'
       outset focus ring; without them the shelf solved reachability by clipping the sign
       that a keyboard reader had reached anything. One extra inline pixel covers
       fractional layout at the integer scroll extent. The shelf takes its contents'
       intrinsic room before the status sentence, then grows through any remaining room:
       All leaves spends that slack and stays at the left edge, while the other addresses
       remain against the right edge. If even the controls do not fit, the shelf caps one
       gap after the status floor and scrolls itself. Safe alignment falls back to that
       scrollable start rather than stranding its first control offscreen. */
    .lf-banner-actions { flex: 1 0 max-content; min-width: 0;
      max-width: calc(100% - 34px); justify-content: safe flex-end; overflow-x: auto;
      overscroll-behavior-inline: contain; scrollbar-width: none; padding: 4px 5px; }
    .lf-banner-actions > .lf-others { margin-inline-end: auto; }
    .lf-banner-actions::-webkit-scrollbar { display: none; }
    /* Leaf's state is carried by the leaf rather than an anonymous traffic light. The
       mask is the page's actual vendored mark, so a project that replaces icon.svg does
       not keep an unrelated leaf-like glyph in the banner. Shape is identity and colour
       is state, from the same registry-owned tones the tab icon wears. */
    .lf-dot { width: 16px; height: 16px; background: var(--muted-2); flex: none;
      -webkit-mask: url("/icon.svg") center / contain no-repeat;
      mask: url("/icon.svg") center / contain no-repeat; }
    .lf-dot.working { background: var(--accent);
      animation: lf-runtime-4f3c2a8d-pulse 1.4s ease-in-out infinite; }
    .lf-dot.listening { background: var(--ok); }
    .lf-dot.away { background: var(--warn); }
    .lf-dot.offline { background: var(--danger); }
    .lf-status-text { color: var(--ink-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
    .lf-status-text .lf-age { color: var(--muted); }
    /* All leaves spends the shelf's slack; the remaining controls stay packed against
       the right edge. That decides who pays for a control changing size: it moves itself
       and the controls to its left, while everything to its right keeps its place. Three
       of these rewrite their own words —
       "✓ Version approved" is narrower than "Approve version", and two of them count something
       that gains a digit — so each holds room for the widest it may say, taken from the
       words themselves (the reserve calls where the banner is built) rather than stated
       here as numbers. Three numbers stood here once and all three quietly stopped
       covering the day --t-5 moved from 13.5px to 14px; a reservation the control
       measures in its own live face at load has no number to go stale. The two sweeps —
       a press, and the poll — stay the check that the words reserved are the words the
       writers actually write.

       The chooser was the one control here that had to state a width, because its label
       carried the version's note and a note has no widest to reserve. It says the version
       and, while a comparison is standing, a Δ — two words, both enumerable — so it is
       floored at its own like the rest, and no number on this row is a fact about a font
       any more. */
    @layer lf-reset {
      .lf-thread-action { font: inherit; }
    }
    /* The chooser's menu: fixed under the button it hangs off, anchored rather than
       measured, so nothing recomputes a position when the row's contents change width.
       It is the only place the version notes are, so a row wraps to hold one whole —
       the reason a menu is worth having over a control whose closed label and open list
       are forced to be the same string. Capped at the viewport's remaining height and
       scrolling inside itself, since a page's versions are unbounded.

       Two columns, because a version and what it changed are one row's two halves: the
       note says it in words and the Δ marks it on the page. That press was a second
       control out on the bar, naming a second version number beside the chooser's, and
       the two together said no more than either — a reader could tell that v2 and v3
       were both being mentioned and not what either mention was for. The pair are grid
       siblings rather than a wrapper each, because a role="menu" owns menuitems and a
       div between them is a claim about ARIA that nothing here needed to make. */
    .lf-version { anchor-name: --lf-version-btn; }
    .lf-version-menu { position: fixed; position-anchor: --lf-version-btn;
      top: calc(anchor(bottom) + 6px); right: anchor(right); z-index: 8950;
      display: none; grid-template-columns: 1fr auto; align-items: start;
      min-width: anchor-size(width);
      max-width: min(360px, calc(100vw - 16px));
      max-height: calc(100dvh - var(--lf-banner-h) - 20px); overflow-y: auto;
      overscroll-behavior: contain;
      background: var(--card); border: 1px solid var(--border-2); border-radius: var(--r);
      box-shadow: 0 8px 24px rgba(0,0,0,.12); padding: 4px; }
    .lf-version-menu.open { display: grid; }
    /* Left-aligned text in a control that is otherwise a press: the rows are a list to
       read down, and a centred note re-ragged on every line is not one. */
    .lf-version-row { grid-column: 1; position: relative;
      display: flex; flex-direction: column; gap: 1px; align-items: start;
      text-align: left; padding: 6px 8px; border: 0; border-radius: 4px;
      background: none; color: inherit; cursor: pointer; width: 100%; }
    .lf-version-row:hover { background: var(--chip); }
    .lf-version-row:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: version-row;
      outline-offset: calc(-1 * var(--here-ring-w)); }
    /* The version being read wears the accent rather than a fill, so the row the
       pointer is over stays the one that looks pressable. */
    .lf-version-row[aria-current] .lf-version-num { color: var(--accent); font-weight: 600; }
    .lf-version-num { white-space: nowrap; }
    .lf-version-note { color: var(--muted); font-size: var(--t-6); }
    /* The comparison a row offers: mark what changed between that version and the one
       being read. It draws its own box rather than waiting for a hover to draw one,
       which is the same rule a group taking a pick keeps: a form may decide how it
       looks and may not decide whether it says it takes an answer, and a wash that
       arrives on hover arrives after the reader has committed the pointer. Lit from
       aria-checked rather than a class of its own, the state being the button's to
       state — a menuitem may not be pressed, a menu's toggle being a
       menuitemcheckbox, which axe said of the aria-pressed this started as on the one
       page in the suite that asks with the menu standing open. */
    .lf-version-diff { grid-column: 2; margin: 4px 2px 0 4px; padding: 3px 8px;
      border: 1px solid var(--rule); border-radius: 4px; background: none;
      color: var(--ink-2); cursor: pointer; font-size: var(--t-6); line-height: 1.4; }
    .lf-version-diff:hover { border-color: var(--border-2); background: var(--chip); }
    .lf-version-diff:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: version-diff;
      outline-offset: calc(-1 * var(--here-ring-w)); }
    .lf-version-diff[aria-checked="true"] { border-color: var(--accent); color: var(--accent);
      background: var(--chip); }
    /* A diff is a span rather than a point — everything that changed across the versions
       from its base to the one being read — and a base three versions back says something
       very different from the one before. The rail is that span, drawn down the rows it
       covers: inside the row's own box, so it is paint and moves nothing, and drawn on
       the rows rather than the presses because the rows are the run that touch. */
    .lf-version-row.lf-compared::before { content: ""; position: absolute;
      left: 0; top: 0; bottom: 0; width: 2px; background: var(--accent); }
    /* The trays' edge: the thread panel's mirror on the left, holding one tray at a
       time (showTray), each its own scroll region so one wheel gesture moves one region.
       Every metric is the edge's rather than either tray's — a reader who has both keys
       should not find two different regions where they learned one — and it is stated once
       here for both. It used to be stated twice, in two rules with every declaration
       duplicated, and by the time anyone looked one copy was carrying a literal 300 where
       the other read the constant; what the two trays differ in is the row, below. */
    .lf-tray-panel { position: fixed; top: var(--lf-banner-h); left: 0; bottom: 0;
      z-index: 8900; width: var(${TRAY_PROP}); background: var(--card);
      border-right: 1px solid var(--rule); display: none; flex-direction: column;
      padding-bottom: var(--lf-safe-bottom); padding-left: var(--lf-safe-left); }
    .lf-tray-panel.open { display: flex; }
    /* The rows scroll in a box of their own rather than in the tray, which is the comment
       panel's shape (.lf-threads) reflected, and here it is what lets the edge exist at
       all: a scroll container clips to its padding box, so an edge straddling the border
       was cut to the three pixels inside it, and an absolutely positioned child of a
       scroller travels with the content — the edge would have scrolled away down a long
       list, an edge being a fact about the region rather than about how far down it the
       reader has read. contain, so reaching the end of the list does not start scrolling
       the page behind it: one wheel gesture moves one region. */
    .lf-tray-list { flex: 1; min-height: 0; padding: 6px 4px; overflow-y: auto;
      overscroll-behavior: contain; }
    .lf-others-row { display: block; padding: 8px 10px; border-radius: 6px; color: inherit;
      text-decoration: none; }
    a.lf-others-row:hover { background: var(--chip); }
    .lf-others-row:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: others-row;
      outline-offset: calc(-1 * var(--here-ring-w)); }
    .lf-others-head { display: flex; align-items: center; gap: 8px; min-width: 0; }
    .lf-others-title { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden;
      text-overflow: ellipsis; }
    /* Indented past the dot's 9px and its 8px gap, so the line reads under the title;
       one line, ellipsized, so a detail growing repaints its own words and moves
       nothing. */
    .lf-others-line { color: var(--ink-2); margin-left: 17px; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis; }
    /* A decision's row, against a leaf's above: a leaf's is a link out to another page and a
       decision's is a press that moves this one, so it is a button and takes the button's own
       reset. */
    .lf-decisions-row { display: block; width: 100%; text-align: left; padding: 8px 10px;
      border: 0; border-radius: 6px; background: none; color: inherit; font: inherit;
      cursor: pointer; }
    .lf-decisions-row:hover { background: var(--chip); }
    /* Both rings this row can wear, inset together. A control packed into a list states
       its own inset (theme.css, --here-ring), because the list clips to its padding box.
       The second ring arrives from a rule written for a page element with room around
       it: while the tray is open the row mirrors the standing decision (markHere) wherever
       the tray lists that decision, so it wears the decision's own outset ring and lost a pixel of
       it to each edge. */
    .lf-decisions-row:is(:focus-visible, .lf-focus-visible, [${PAGE_PAINT_ATTRIBUTE.decision}]) {
      outline: var(--here-ring); --lf-here-ring: decisions-row; outline-offset: calc(-1 * var(--here-ring-w)); }
    /* What kind of thing is asking, in the apparatus voice, over the decision's own words in
       the page's. Two lines, because they are two claims: the kind is the runtime's word
       for the element and the words below it are the page's own. */
    .lf-decisions-kind { display: block; color: var(--muted); font-size: var(--t-6);
      text-transform: uppercase; letter-spacing: .05em; }
    /* Three lines at most, then ellipsized: a decision's opening words are a name here, and a
       name that runs to eight lines stops being one — while a single line would cut most
       questions off before they said which question they were. */
    .lf-decisions-says { display: -webkit-box; -webkit-box-orient: vertical;
      -webkit-line-clamp: 3; overflow: hidden; }
    /* Version news remains a legible address at every width. When the row runs out of
       room the shelf above scrolls; clipping the one control instead left a visible
       eighteen-pixel button containing none of its words. */
    .lf-latest-chip { background: var(--warn-tint); border: 1px solid var(--warn); color: var(--warn-ink); border-radius: 6px; padding: 3px 8px; flex: none; }
    .lf-panel { position: fixed; top: var(--lf-banner-h); right: 0; bottom: 0; width: var(${PANEL_PROP}); z-index: 8900;
      background: var(--card); border-left: 1px solid var(--rule); display: none;
      flex-direction: column; padding-right: var(--lf-safe-right);
      padding-bottom: var(--lf-safe-bottom); }
    .lf-panel.open { display: flex; }
    /* An edge, offered as a thing to take hold of — the thread panel's on the right of
       the page, the trays' on the left, and nothing here knows which it is drawing except
       the two lines that place it. It draws nothing of its own: the region's inner border
       is the line the reader already sees, and this is the room around that line in which
       a pointer counts as being on it. It straddles the border rather than sitting inside
       it, because the reader aims at the line and arrives from whichever side they were
       reading — and where the region stands beside the page, the 3px of it outside is
       body's own margin, which holds no words.
       What hover and focus add is a line drawn over the border, growing a pixel each way
       into room that was already the border's and the region's padding; never a thicker
       border, which would move everything in the region under the pointer that had just
       arrived (CLAUDE.md, "The page holds still under the user's aim"). touch-action, so a
       finger on the edge resizes rather than scrolling the region behind it, and z-index
       because a thread is positioned too and stands later in the panel than this does.

       Named for what it is rather than for the gesture: a card's drag handle is a grip
       (lf-board.js), and one word for a thing you pick up and a boundary you draw would
       have been two meanings a selector cannot tell apart. The regions this edge draws
       were boards until the same reading caught them: lf-board is a widget an author
       writes into a page, so a grep for it hit the runtime's own furniture and a grep for
       the furniture hit the widget. They are trays now, and the word is core's alone. */
    /* Held a ring's width in from both ends, because a flush ring at either end is
       drawn where nothing can show it: under the banner at the head, past the bottom of
       the window at the foot — and the reader tabbing to the edge got a ring missing that
       run. The two ends fail differently and it is worth keeping them apart, because the
       gate reports them as different things: the banner declares no overflow and clips
       nothing, it paints over at z-index 9000, while the window clips outright. The
       handle gives up those pixels of reach at both; the alternative is a ring inside an
       eight-pixel strip, which is a second accent line beside the one ::before already
       draws. RINGS_DRAWN fails the page if either run goes back. */
    .lf-edge { position: absolute; top: var(--here-ring-w);
      bottom: var(--here-ring-w); width: 8px;
      z-index: 1; cursor: col-resize; touch-action: none; }
    .lf-edge::before { content: ""; position: absolute; top: 0; bottom: 0;
      width: 2px; background: var(--accent); opacity: 0; transition: opacity .12s; }
    /* Which side of the window the region is fixed to, so the edge is its inner one: a
       region held to the right is drawn by its left border and the other way about. */
    .lf-edge[data-lf-side="right"] { left: -4px; }
    .lf-edge[data-lf-side="right"]::before { left: 2px; }
    .lf-edge[data-lf-side="left"] { right: -4px; }
    .lf-edge[data-lf-side="left"]::before { right: 2px; }
    /* Pointer capture carries :hover with it, so one rule covers the reach and the whole
       drag that follows it. */
    .lf-edge:hover::before, .lf-edge:is(:focus-visible, .lf-focus-visible)::before { opacity: 1; }
    .lf-edge:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: edge; }
    .lf-panel-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--rule); font-weight: 600; }
    /* The narrowing row, under the head and above the list it narrows. Standing rather
       than raised by a key or a count, for the reason every other control here stands:
       a row that arrives at the eighth thread moves the list under the reader at the
       moment they are reading it, and a reader who cannot see the box cannot know the
       list in front of them is the whole of it. What it says while a narrowing stands
       is the head's line ("Showing 3 of 24"), which is the one place a count belongs. */
    .lf-find { display: flex; gap: 6px; align-items: center; padding: 8px 14px;
      border-bottom: 1px solid var(--rule); }
    /* type=search, so the platform's own clear control does that work: an ✕ of the
       runtime's own would be a second way to say the same thing, drawn worse. */
    .lf-find-box { flex: 1; min-width: 0; font: inherit; font-size: var(--t-6);
      padding: 3px 8px; border: 1px solid var(--border-2); border-radius: var(--r);
      background: var(--paper); color: var(--ink); }
    .lf-find-box:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: find-box; outline-offset: 1px; }
    /* contain: reaching the end of the thread list must not start scrolling the page
       behind it — one wheel gesture moves one region.
       The frame is declared because the inset is read at both ends of a scroll region:
       the list opened 10px above its first thread and stopped 22px under the last, the
       last thread's own 12px having nowhere to collapse to. See theme.css. */
    /* scroll-padding is how a scroll region says which of its own edges are not
       available to land on, and it is read by the browser's scrollIntoView as well as
       by the runtime's own scrolling — the document declares its banner the same way
       (scroll-padding-top, above), and this list declared nothing, so every landing
       was flush with the edge. Two things stand in the way here. A stuck run heading
       covers the top: its height is the one number CSS cannot work out, since a long
       heading wraps, so renderThreads measures the tallest and writes it here. And
       the ring is drawn outside the box it names, so a thread scrolled exactly to
       either edge had its ring in the strip beyond it — cut at the bottom walking
       down, cut at the top and under the find row walking up. Gap plus width is the
       room it needs, and it is the layer's own number (theme.css) rather than one
       worked out from the controls this list happens to hold. */
    .lf-threads { flex: 1; overflow-y: auto; overscroll-behavior: contain;
      --lf-list-inset: 10px; padding: var(--lf-list-inset) 14px; --lf-frame: 1;
      scroll-padding: calc(var(--lf-head-room, 0px) + var(--here-ring-room)) 0
        var(--here-ring-room); }
    /* An Escape rung lands here (general box → the list), so the rung is visible. */
    .lf-threads:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: thread-list;
      outline-offset: calc(-1 * var(--here-ring-w)); }
    .lf-empty { color: var(--muted); padding: 18px 4px; }
    /* Which part of the page the threads under it are about — the page's own heading,
       said once over the run of threads that share it. Sticky, so the answer to "where
       am I" is on screen for the whole run rather than only at its start: a list four
       thousand pixels long is scrolled past its landmarks within one gesture. Opaque
       (--card), because the threads pass underneath it. The resolved disclosure's
       summary sticks in the same slot and later in the list, so it takes the pin from
       the last heading when the reader reaches it.

       The room above a heading is its own padding and never a margin, and the pin is
       drawn back over the list's own inset. Both for one reason: a stuck box is held by
       its margin edge inside the scroller's content, so a margin there — or the
       container's padding — is a strip between the pin and the ink through which the
       list scrolls in full view. The inset is read from where it is spent, so the two
       numbers cannot drift apart.

       Being pinned is its own class, worn by the two boxes that do it and by whatever
       the list pins next. It was written twice — once here and once on the disclosure's
       summary — which is two chances to move the slot in one of them, and it is also
       the question renderThreads has to ask to know how much of the top is covered.
       One class answers all three: the mechanics, the second wearer, and the sweep. */
    .lf-pinned { position: sticky; top: calc(-1 * var(--lf-list-inset)); z-index: 2;
      margin: 0; padding: 14px 0 7px; background: var(--card); }
    .lf-group { display: block; width: 100%; box-sizing: border-box; border: none;
      font: inherit; font-size: var(--t-6); font-weight: 600; letter-spacing: .04em;
      text-transform: uppercase; text-align: left; color: var(--muted);
      overflow-wrap: anywhere; }
    button.lf-group { cursor: pointer; }
    button.lf-group:hover { color: var(--ink-2); }
    /* Inset, because being pinned is where this heading spends its life and the pin
       puts its box top on the scrollport's own edge: a sticky offset is measured from
       the scroller's content box, so a heading drawn back over the list's inset
       (.lf-pinned) has nothing above it at all, and a ring a pixel outside the box was
       three pixels into the strip the scroller clips. Every control packed into this
       list states its own inset for the same reason (theme.css, --here-ring). */
    button.lf-group:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: run-heading;
      outline-offset: calc(-1 * var(--here-ring-w)); }
    /* A thread and the room a resolved one is still giving back (foldOut) are the same
       box, so the fold starts from the box the reader was looking at rather than from
       a second description of it. What .lf-going adds is the clip the fold needs and
       the outcome said in paint: the box is on its way out and may not also state
       that in metrics the fold is animating. */
    .lf-thread, .lf-going { --lf-thread-pad: 10px; position: relative; border: 1px solid var(--rule); border-radius: var(--r); padding: var(--lf-thread-pad); margin-bottom: 12px; --lf-frame: 1; }
    /* The panel half of the mark the pointer is indicating (paintHover). The fallback
       keeps a custom theme without the middle ramp token legible at its strongest mark
       wash; the shipped theme supplies --mark-hover so indicated and standing stay two
       distinct distances from the reader. */
    .lf-thread.lf-mark-hover { background: var(--mark-hover, var(--mark-strong)); }
    .lf-going { overflow: hidden; box-sizing: border-box; }
    /* The outcome rides the closing edge, so it is legible for the whole fold rather
       than for the frame before the box swallows it: the actions row is the thread's
       last line, and a fold from the bottom takes it first. Pinned to the box's own
       bottom padding, which is where it already sits in flow, so the fold starts from
       the layout the reader was looking at and nothing shifts on the press. It occludes
       what it passes (background) rather than reading through it, and it says the
       outcome in ink, since the metrics here are what the fold is animating. */
    .lf-going .lf-thread-actions { position: absolute; inset: auto var(--lf-thread-pad) var(--lf-thread-pad); background: var(--card); }
    .lf-going .lf-thread-send { visibility: hidden; }
    .lf-going .lf-resolve { color: var(--ok); }
    .lf-thread.flash { animation: lf-runtime-4f3c2a8d-flash 1.2s ease-out; }
    /* An arrival the reconcile added while the user was watching. Motion, not a
       jump: nothing above it moves, and the newcomer settles rather than appears. */
    .lf-thread.grow, .lf-msg.grow { animation: lf-runtime-4f3c2a8d-grow .32s cubic-bezier(.2,.7,.3,1); }
    /* The card of the comment the reader is standing in, which is the panel's half of
       the pair the page paints as lf-mark-here. :focus-within and not :focus-visible,
       because the two halves have to answer the same question: focus-visible is a claim
       about the last input device, so a reader who reached the comment with the mouse
       had the page marked and the card left plain, and the pair only read for the
       keyboard. Within, because a reply box is inside the card and writing back is
       still standing there — the same reason paintStanding reads the focus through
       closest.

       Inset, which is what theme.css says a control packed into a list draws — and this
       row was the one breaking that rule. Drawn outside the box, the ring's top run fell
       inside the opaque padding of the heading above it, so the first card of every run
       stood with its top edge missing: the reader's own report, and the shape of it is
       that no amount of scrolling can help, since the two boxes touch in flow. A ring
       drawn inside the box it names cannot be covered by a neighbour or cut by an edge
       the box itself is within. */
    .lf-thread:is(:focus-within, .lf-focus-within) { outline: var(--here-ring); --lf-here-ring: thread;
      outline-offset: calc(-1 * var(--here-ring-w)); }
    .lf-quote { margin: 0 0 8px; padding: 2px 8px; border-left: 3px solid var(--mark-ink); color: var(--muted); font-style: italic; cursor: pointer; overflow-wrap: anywhere; }
    .lf-quote:is(:hover, :focus-visible, .lf-focus-visible) { color: var(--ink-2); }
    .lf-quote:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: quote;
      outline-offset: 2px; }
    .lf-thread > .lf-quote:not(.detached)::after { content: "  ↗ page";
      color: var(--accent); font-size: var(--t-6); font-style: normal; white-space: nowrap; }
    /* A quote is the passage, and a passage is as long as the reader's selection — a
       paragraph of it in a 320px column buries the words written about it. So the panel
       names the passage in three lines and the page shows the rest: the mark is already
       on it, and the quote is what one clicks to go there. The composer's copy is
       scrolled rather than clipped a few rules down, because it stands alone in a box
       the reader is typing into and has no thread beneath it to bury. */
    .lf-thread .lf-quote { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }
    .lf-quote.detached { border-left-style: dashed; border-left-color: var(--border-2); color: var(--muted-2); cursor: default; }
    /* Out of the picture, still in the accessibility tree — see the composer's quote in
       paintAnchors for the one thing that wears this and why. */
    .lf-unseen { position: absolute; width: 1px; height: 1px; padding: 0; border: 0; overflow: hidden; clip-path: inset(50%); }
    .lf-msg { margin: 8px 0; }
    /* Who and when, on one line above the words: apparatus, so the row states the
       apparatus rung once and the two differ by weight and ink rather than by size. They
       carried 12.5px and 11.5px, a pixel apart for no reason either could give, and the
       11.5 was --t-6 written out. */
    .lf-msg-head { display: flex; gap: 6px; align-items: baseline; font-size: var(--t-6); }
    .lf-msg.claude .lf-msg-head b { color: var(--accent); }
    .lf-msg time { color: var(--muted-2); }
    .lf-msg-head .lf-edited { color: var(--muted-2); }
    /* A message body is rendered Markdown, which is why this dresses a box and not a
       paragraph. The theme's element rules are at document level and reach in here, so a
       reply's lists, code, quotes and tables already read as the page's do; what is left
       is the panel's narrower column — tighter blocks, headings that don't shout at
       360px, and no margin where the body meets its own head. */
    .lf-msg-body { margin: 2px 0 0; overflow-wrap: anywhere; }
    .lf-msg-text { display: contents; }
    .lf-msg-text > :first-child { margin-top: 0; }
    .lf-msg-body > :last-child, .lf-msg-text > :last-child { margin-bottom: 0; }
    .lf-msg-body :is(p, ul, ol, pre, blockquote, table, hr) { margin: 6px 0; }
    /* Prose here breaks anywhere, because the thing a reply overflows on is a URL
       no wrap can help. A table is the one block in a reply with somewhere else to
       put the width — the theme makes it scroll inside itself — so breaking its
       cells to save that room spends the alignment the table was written for:
       "12,000" arrived as "12,0" over "00", in a column of figures to compare. */
    .lf-msg-body :is(th, td) { overflow-wrap: normal; }
    .lf-msg-body :is(h1, h2, h3, h4, h5, h6) { margin: 8px 0 4px; font-size: var(--t-5); }
    .lf-msg-body li { margin: 2px 0; }
    .lf-msg-body pre { padding: 8px 10px; }
    .lf-msg-body blockquote { padding: 2px 10px; }
    /* A reference to an element this version hasn't got, wearing the same word the
       quote above wears for the same fact. The whole text-decoration shorthand,
       because a widget's § reference (lf-ref) undressed its underline and a style
       alone would paint nothing there. paintAnchors is the one writer. */
    .lf-msg-body a.detached { color: var(--muted-2); text-decoration: underline dashed; cursor: default; }
    .lf-compose { display: block; margin-top: 8px; }
    .lf-compose textarea { display: block; width: 100%; min-width: 0; }
    /* The general Send stays beside its field; a thread gives the field its own row. */
    .lf-general { display: flex; gap: 6px; margin-top: 8px; align-items: flex-end; }
    .lf-general textarea { flex: 1; min-width: 0; }
    .lf-thread-actions { display: flex; justify-content: space-between; margin-top: 8px; }
    .lf-thread-action { border: none; background: none; color: var(--muted); cursor: pointer; }
    .lf-thread-action:hover { color: var(--ok); }
    .lf-resolved-by { color: var(--muted); }
    .lf-general { padding: 10px 14px; border-top: 1px solid var(--rule); }
    .lf-details { margin-top: 16px; color: var(--muted); background: none; border: none; padding: 0; }
    /* The last landmark in the list wears .lf-pinned like the headings above it: it
       stands later than every one of them, so opening it hands the pinned slot from
       the section the reader was in to the disclosure they are now inside. */
    .lf-system { color: var(--ok); margin: 8px 0; }
    /* The two floats that point at the page live in the document's coordinate space
       (absolute, body their containing block), because what they point at does: a
       composer that held its viewport spot while the page scrolled sat pinned over
       whatever arrived under it, no longer beside the item it was about. Everything
       else here is the viewport's own chrome and stays fixed. Below the banner's
       9000, so a float scrolled to the top slides under the bar, not over it. */
    /* The 💬 stands out on the page, beside the reader's own words and in the same
       margin a change's ✓ Accept hangs in — often on the same line, which is how the
       two came to be compared. It used to answer that comparison badly: a solid accent
       rectangle at the chrome's own size against two hairline pills, so the page's
       margin held two idioms four centimetres apart and the louder one was the one
       raised over the reader's sentence. Where a control stands decides which it
       wears. In the runtime's own furniture — the banner, the panel, the composer — a
       press is a .lf-btn and looks like one; beside page content it is the shared
       .lf-margin-action.

       The shadow is the one thing this control adds, and it earns it: this is the only
       pill that floats over the page's own content rather than standing in the empty
       rail, so it says so rather than relying on a hairline to separate it from
       whatever it happens to be over. */
    .lf-fab-bar { position: absolute; z-index: 8950; display: none; align-items: center;
      gap: 4px; white-space: nowrap; }
    .lf-fab-bar[data-lf-margin-raised] { display: none !important; }
    /* The comment glyph and ellipsis are the bar's two stable presses. Both carry the
       shadow the floating surface earns. The ellipsis gives its place to the reaction
       buttons without moving Comment. */
    .lf-fab-bar > .lf-pill { box-shadow: 0 2px 6px rgba(0,0,0,.14); }
    /* A reaction surface offers one quiet ellipsis. It disappears when its list opens;
       a standing token remains visible in a closed message or page strip as the reader's
       receipt and eraser. */
    .lf-react-trigger { color: var(--muted); }
    .lf-react-trigger:is(:hover, :focus-visible, .lf-focus-visible, [aria-expanded="true"]) {
      color: var(--ink-2); border-color: var(--border-2); background: var(--chip); }
    .lf-react-palette { display: inline-flex; align-items: center; flex-wrap: wrap; gap: 4px; }
    .lf-fab-bar > .lf-react-palette { flex-wrap: nowrap; }
    .lf-react-open > .lf-react-trigger { display: none; }
    .lf-react-surface:not(.lf-react-open) .lf-react:not([aria-pressed="true"]) {
      display: none; }
    .lf-react-strip:not(.lf-react-open) > .lf-react-palette:not(:has(> [aria-pressed="true"])) {
      display: none; }
    .lf-fab-bar:not(.lf-react-open) > .lf-react-palette { display: none; }
    /* The glyph is the whole label until the token stands on its target; then the word
       joins it. State is paint — ink, border, fill — and the word's extra width is the
       reader's own receipt, not incoming chrome moving under their press. */
    .lf-react { display: inline-flex; align-items: center; gap: 4px; min-width: 26px;
      justify-content: center; }
    .lf-react > .lf-react-word { display: none; }
    .lf-react[aria-pressed="true"] > .lf-react-word { display: inline; }
    .lf-react[aria-pressed="true"] { border-color: var(--mark-ink); color: var(--mark-ink);
      background: var(--mark); }
    .lf-react[aria-busy="true"] { opacity: .55; }
    .lf-react-strip { display: flex; align-items: center; flex-wrap: wrap; gap: 4px;
      margin-top: 6px; }
    .lf-page-strip { padding: 8px 14px 0; }
    /* The latest agent reply keeps one ellipsis visible. Older replies expose theirs
       while the reader is in the thread; a standing mark remains visible at rest. */
    .lf-thread:not(:hover, :focus-within, .lf-focus-within)
      .lf-react-strip:not(.lf-open, .lf-react-open) > .lf-react-trigger { display: none; }
    .lf-thread:not(:hover, :focus-within, .lf-focus-within)
      .lf-react-strip:not(.lf-open, .lf-react-open):not(:has([aria-pressed="true"])) {
        margin-top: 0; }
    .lf-react-palette > .lf-react:not([aria-pressed="true"]) { border-color: transparent;
      background: transparent; color: var(--muted); }
    .lf-react-palette > .lf-react:not([aria-pressed="true"]):is(:hover, :focus-visible, .lf-focus-visible, [aria-busy="true"]),
    .lf-react-open .lf-react-palette > .lf-react:not([aria-pressed="true"]) {
      border-color: var(--border-2); background: var(--chip); color: var(--ink-2); }
    .lf-react-palette > .lf-react[aria-pressed="true"]:hover { background: var(--mark); }
    /* A thread whose root is a mark: the glyph and its word where the comment's words
       would stand, in the chrome's face. */
    .lf-react-said { font-family: var(--sans); color: var(--mark-ink); }
    /* The ⌥ aim's promise: the item a press would take, whole. Drawn here in the
       chrome's own layer rather than painted onto the element, because no band of a
       page element is reliably the runtime's to paint in — the mark comment at
       document level holds the inventory (outside the border, an enclosing scroller
       clips; inside it, a choose group's own cells paint over; the border band is
       wherever the widget's own border already is). A standing mark can live with the
       hairline that survives all that, because an annotation is something a reader
       can hunt for. A promise cannot: it answers a held key at a glance, and over a
       box whose border is already the accent the arm changed nothing a reader could
       see, which was reported as no box at all.
       The layer over the page is the runtime's by construction, so the aim is stated
       there instead, from the aimed element's geometry: a veil that says how much a
       press takes and a ring that says where it stops, over everything the page can
       paint — an lf-shot frame flush to its own edges included. pointer-events
       stands down so the press this box promises, and every elementFromPoint behind
       the promise, still lands on the item under it. Document-anchored like the
       floats above (place), so a scroll moves it with the page between the events
       that re-derive it; under the floats themselves, which are chrome the reader
       works rather than paint about the page. */
    .lf-aim { position: absolute; z-index: 8920; display: none; pointer-events: none;
      border: 2px solid var(--accent);
      background: color-mix(in srgb, var(--accent) 8%, transparent); }
    .lf-composer { position: absolute; z-index: 8950; display: none; width: 320px; background: var(--card);
      border: 1px solid var(--border-2); border-radius: var(--r); box-shadow: 0 8px 24px rgba(0,0,0,.12); padding: 10px; }
    /* A stranded quote is the whole passage, and the box is 320px wide. Only while showing:
       on the hidden one this would out-specify .lf-unseen's own overflow. */
    .lf-composer .lf-quote:not(.lf-unseen) { max-height: 4.2em; overflow-y: auto; }
    .lf-suggest-row { display: none; align-items: center; gap: 6px; margin: 0 0 6px; color: var(--muted); font-size: var(--t-6); cursor: pointer; }
    .lf-suggest-row input { margin: 0; accent-color: var(--accent); }
    .lf-suggest-label { font-size: var(--t-6); letter-spacing: .05em; text-transform: uppercase; color: var(--ok-ink); margin: 4px 0 2px; }
    /* A suggestion renders verbatim — its characters are what the next version
       carries (see msgNode) — so this is where they keep their own line breaks. */
    .lf-msg-body.lf-suggest-body { background: var(--add-tint); padding: 4px 8px;
      border-radius: 6px; white-space: pre-wrap; }
    .lf-composer textarea { width: 100%; min-height: 56px; }
    .lf-composer-row { display: flex; justify-content: flex-end; gap: 6px; margin-top: 6px; }
    .lf-toast { position: fixed; bottom: calc(18px + var(--lf-safe-bottom));
      right: calc(18px + var(--lf-safe-right)); z-index: 9200;
      max-width: calc(100vw - 36px - var(--lf-safe-left) - var(--lf-safe-right));
      overflow-wrap: anywhere; background: var(--ink); color: var(--paper); padding: 9px 14px;
      border-radius: var(--r); opacity: 0; transition: opacity .25s, right .18s ease; pointer-events: none; }
    .lf-toast.show { opacity: .95; }
    .lf-toast.clickable { pointer-events: auto; cursor: pointer; }
    .lf-live { position: fixed; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
    .lf-help { position: fixed; z-index: 9300; top: 50%; left: 50%; transform: translate(-50%, -50%);
      width: min(520px, calc(100vw - 32px - var(--lf-safe-left) - var(--lf-safe-right)));
      max-height: min(80dvh, calc(100dvh - var(--lf-safe-top) - var(--lf-safe-bottom) - 32px));
      overflow: hidden; display: none; margin: 0;
      background: var(--card); border: 1px solid var(--border-2); border-radius: var(--r);
      box-shadow: 0 12px 32px rgba(0,0,0,.18); padding: 14px 18px; }
    .lf-help.open { display: flex; flex-direction: column; }
    .lf-help::backdrop { background: color-mix(in srgb, var(--ink) 24%, transparent); }
    .lf-help-head { display: flex; align-items: center; justify-content: space-between;
      gap: 12px; margin-bottom: 8px; }
    .lf-help-title { font-weight: 600; }
    .lf-help-close { flex: none; }
    .lf-help-search { width: 100%; box-sizing: border-box; font: inherit; padding: 7px 9px;
      border: 1px solid var(--border-2); border-radius: var(--r); background: var(--paper);
      color: var(--ink); }
    .lf-help-search:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: help-search; outline-offset: 1px; }
    .lf-help-preference { display: flex; align-items: center; justify-content: space-between;
      gap: 12px; margin: 6px 0 0; }
    .lf-help-meta { min-height: 1.2em; color: var(--muted);
      font-size: var(--t-6); }
    .lf-help-shortcuts { flex: none; min-height: 26px; padding: 2px 8px;
      color: var(--muted); font-size: var(--t-6); }
    .lf-help-shortcuts span { color: var(--ink-2); }
    .lf-help-results { min-height: 0; overflow-y: auto; }
    .lf-help-empty { padding: 20px 0 8px; color: var(--muted); text-align: center; }
    .lf-help h3 { margin: 12px 0 4px; font-size: var(--t-6); font-weight: 600;
      text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
    .lf-help table { display: table; width: 100%; table-layout: fixed;
      border-collapse: collapse; }
    .lf-help td { padding: 3px 0; vertical-align: baseline; }
    .lf-help td:first-child { width: 84px; white-space: nowrap; }
    .lf-help-command { width: 100%; margin: -3px -6px; padding: 3px 6px;
      border: 0; border-radius: 4px; background: transparent; color: inherit;
      font: inherit; text-align: left; cursor: pointer; }
    .lf-help-command:is(:hover, :focus-visible),
    .lf-help-command[data-lf-selected="true"] { background: var(--chip); }
    .lf-help-command:focus-visible { outline: var(--here-ring);
      --lf-here-ring: help-command; outline-offset: 1px; }
    .lf-help-command[data-lf-available="false"] { color: var(--muted); }
    .lf-page-map-toggle { display: none; }
    .lf-margin-preview { position: fixed; z-index: 9150; width: min(320px, calc(100vw - 24px));
      max-height: calc(100vh - 24px); box-sizing: border-box; overflow: auto;
      padding: 12px; border: 1px solid var(--border-2); border-radius: 10px;
      background: var(--paper); color: var(--ink); box-shadow: 0 12px 36px rgba(0,0,0,.18); }
    .lf-margin-preview[hidden] { display: none; }
    .lf-margin-preview-head, .lf-page-map-head { display: flex; align-items: center;
      justify-content: space-between; gap: 12px; }
    .lf-margin-preview-title { font-size: var(--t-5); line-height: 1.35; }
    .lf-margin-preview-close { flex: none; min-width: 30px; padding-inline: 7px; }
    .lf-margin-preview-kinds { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
    .lf-margin-kind { display: inline-flex; align-items: center; gap: 4px; padding: 2px 7px;
      border: 1px solid currentColor; border-radius: 999px; font-size: var(--t-6); }
    .lf-margin-kind-symbol { width: 10px; text-align: center; font-weight: 700; }
    .lf-margin-preview-list { display: grid; gap: 4px; margin-top: 10px; }
    .lf-margin-thread { min-width: 0; padding-top: 10px; border-top: 1px solid var(--rule); }
    .lf-margin-thread:first-child { padding-top: 0; border-top: 0; }
    .lf-margin-thread .lf-conversation-msg:first-child { margin-top: 0; }
    .lf-margin-thread .lf-say { align-items: flex-end; }
    .lf-margin-thread .lf-say textarea { min-width: 0; }
    .lf-margin-thread-open { display: block; margin: 8px 0 0 auto; color: var(--muted);
      font-size: var(--t-6); }
    .lf-margin-preview-action, .lf-page-map-action { width: 100%; min-width: 0;
      display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px;
      align-items: baseline; border: 0; border-radius: var(--r); background: transparent;
      color: inherit; padding: 7px 8px; font: inherit; text-align: left; cursor: pointer; }
    .lf-margin-preview-action:is(:hover, :focus-visible),
    .lf-page-map-action:is(:hover, :focus-visible) { background: var(--chip); }
    .lf-margin-preview-action:focus-visible, .lf-page-map-action:focus-visible {
      outline: var(--here-ring); --lf-here-ring: page-map-action; outline-offset: 1px; }
    .lf-margin-action-kind { font-size: var(--t-6); font-weight: 600; }
    .lf-margin-action-text { color: var(--ink-2); overflow-wrap: anywhere; }
    .lf-page-map-sheet { position: fixed; z-index: 9300; width: min(560px, calc(100vw - 24px));
      max-height: min(720px, calc(100vh - 24px)); margin: auto; padding: 14px;
      border: 1px solid var(--border-2); border-radius: 12px; background: var(--paper);
      color: var(--ink); box-shadow: 0 18px 54px rgba(0,0,0,.24); }
    .lf-page-map-sheet::backdrop { background: color-mix(in srgb, var(--ink) 26%, transparent); }
    .lf-page-map-list { margin-top: 10px; overflow: auto; max-height: calc(100vh - 110px); }
    .lf-page-map-group { padding: 10px 0; border-top: 1px solid var(--rule); }
    .lf-page-map-group:first-child { border-top: 0; }
    .lf-page-map-group h3 { margin: 0 8px 4px; font-size: var(--t-5); line-height: 1.35; }
    .lf-page-map-actions { display: grid; gap: 2px; }
    @media (max-width: 899px) {
      .lf-page-map-toggle:not([hidden]) { display: inline-flex; }
      .lf-page-map-sheet { inset: auto 8px 8px; width: calc(100vw - 16px);
        max-height: min(82vh, 720px); margin: 0; padding-bottom: max(14px, env(safe-area-inset-bottom)); }
      .lf-page-map-action { min-height: 44px; }
    }
    @media (forced-colors: active) {
      .lf-margin-preview, .lf-page-map-sheet { border: 1px solid CanvasText; box-shadow: none; }
      .lf-margin-preview-action:focus-visible, .lf-page-map-action:focus-visible {
        outline: 2px solid Highlight; }
    }
    /* The glyph states its own ink rather than taking the line's. A key chip is the
       one word on either surface the reader has to read to press anything, and on
       --chip the surrounding line's --muted came to 4.46:1 — under AA, and quietly,
       since the hint is aria-hidden and the corpus sweep walks pages with it empty.
       --ink-2 clears it on both schemes. The words beside the chips keep --muted:
       they sit on --card, which it clears.

       One size for both surfaces, because a key chip is one thing wherever the reader
       meets it — the same reason .lf-address is stated once for the panel and the page.
       It is the apparatus rung, where the 12px it held was half a pixel off one. */
    .lf-help kbd, .lf-keyline kbd { font-family: var(--mono); font-size: var(--t-6); background: var(--chip);
      color: var(--ink-2);
      border: 1px solid var(--border-2); border-radius: 4px; padding: 1px 6px; }
    /* The key line: two hints about what keys do right now, rendered from the register
       the dispatcher walks (see the module docstring). More unfolds the same current
       register into two rows before it opens the complete reference. Each hint is the
       eye's copy of facts spoken elsewhere and stays aria-hidden; More is a real control.
       syncLayout keeps the line out of a side-by-side thread panel and lifts it over a
       covering one, while body reserves its height so the document's last lines never
       end under it. Overflow remains a backstop for a window too narrow to hold even
       the short line. */
    .lf-keyline { position: fixed; left: calc(18px + var(--lf-safe-left));
      bottom: calc(14px + var(--lf-safe-bottom)); z-index: 8940; pointer-events: none;
      display: flex; gap: 12px; align-items: baseline;
      max-width: calc(100vw - var(--lf-keyline-right, 0px) - 36px
        - var(--lf-safe-left) - var(--lf-safe-right));
      overflow: hidden; color: var(--muted); font-size: var(--t-6); white-space: nowrap;
      background: var(--card); border: 1px solid var(--rule); border-radius: var(--r);
      padding: 5px 10px; }
    .lf-keyline[data-lf-expanded="true"] { width: max-content; flex-wrap: wrap;
      row-gap: 6px; align-items: baseline; }
    .lf-keyline:empty { display: none; }
    .lf-keyline .lf-key { display: inline-flex; gap: 5px; align-items: baseline; }
    .lf-keyline .lf-key[hidden] { display: none; }
    .lf-key-more { display: inline-flex; gap: 5px; align-items: baseline; flex: none;
      pointer-events: auto; margin: -3px -4px; padding: 3px 4px; border: 0;
      border-radius: 4px; background: none; color: inherit; font: inherit; cursor: pointer; }
    .lf-key-more:hover { color: var(--ink-2); }
    /* Inside, because the line clips: the button pulls itself out of the row by 3px so
       its own padding does not grow the line, and a ring drawn a further pixel out lands
       past the line's padding box, which overflow: hidden cuts. A control packed into
       a list states its own inset (theme.css, --here-ring) — the thread cards and the
       joined option group do the same — and here the line's own border is what stands
       the whole thing off the page. */
    .lf-key-more:is(:focus-visible, .lf-focus-visible) { outline: var(--here-ring); --lf-here-ring: key-more;
      outline-offset: calc(-1 * var(--here-ring-w)); }
    .lf-keyline kbd.armed { border-color: var(--accent); color: var(--accent); }
    /* Design mode: the reader is commenting on the layer rather than the page, and for
       as long as they are the page shows its bones. Every item — a widget, a section, a
       heading with an id — wears a legend box: a dashed hairline in the chrome's layer,
       drawn from the item's geometry the way the aim's box is (paintLegend), one pixel
       outside the border box so a thread's mark, one pixel inside it, still shows
       through. Every item but a widget's parts wears its name above the box's corner
       too — the tag and id a fix is written against, the words the composer and the
       thread will carry — and the parts (a card, an option, a milestone: what x-parent
       declares) keep the hairline alone and are named under the pointer, or a board
       would wear a tag on every card and say nothing. Dashed rather than solid because
       the solid hairline is the mark's (.lf-mark-el), and a legend is not an
       annotation. Under the pointer the aim's box lifts one item out of the legend
       (.lf-aim) and its full name — the control's word included — floats where the tag
       stood (.lf-inspect); the banner takes an accent wash so the mode reads at the top
       edge as well. Nothing here is something to press: pointer-events stands down so a
       click still lands on the item the box outlines. */
    /* The g chord's numbered document destinations: a chip per member of every list it
       offers, narrowed to one list once a letter names it, in a layer of the chrome's own
       so an address can hang on a link set mid-sentence without writing a span into the
       paragraph. Fixed, because authored members can sit in the document or a widget's
       overflow; one layer that follows neither lets a single pass place them from the
       viewport rects it just read, then repaint when anything scrolls under it. Each chip
       is centred on the corner its member starts at — the first line of a wrapping inline,
       not the whole box it spans — half in and half out. Nothing here is pressable. */
    .lf-addresses { position: fixed; inset: 0; z-index: 9070; pointer-events: none; }
    .lf-addresses > .lf-address { position: absolute; display: block;
      transform: translate(-50%, -50%); }
    /* The two halves of an address: the keys already pressed, and the press that finishes
       the motion. A chip carries the whole of it, so how far in the reader is has to be
       said by how the keys are set. Muted rather than dropped, which is what the chip used
       to do — the address it drew was then shorter than the complete chord, and the short
       one reaches nothing from a standing start.

       Ground and not size. Muted against accent is 1.45:1 in the light palette and 1.28:1
       in the dark, which is a difference in hue and barely one in lightness: on a key this
       small the two halves read as one word, and to a reader who does not separate those
       hues they are one word. Size was the second channel for exactly that reason, and it
       cost more than it bought — one box holding two type sizes reads as a fault rather
       than a hierarchy, and because a press moves a key from one size to the other, naming
       a list re-set every chip on screen: 2.4px narrower and, being centred on its corner,
       1.2px further right, under the eye that was reading them. A lit ground says the same
       thing and takes no advance at all.

       Which is what the negative margin buys, and the whole of why it is here. The ground
       the block paints is not room it occupies: the margin cancels the padding that would
       have been advance, so the keys sit exactly where they would with no block at all and
       the key crossing from one half to the other on a press does not move. Without it that
       key stepped 3px — measured, and larger than the 1.2px slide this rule replaced, which
       would have been the same fault rewritten one glyph smaller.

       The leading edge alone, because that is the only side a glyph sits after. Nothing
       follows the lit half — it ends the address — so its trailing padding costs no glyph a
       pixel and is left to take its room, which is what stands the ground off the ring
       without the chip having to widen its own inset and lose the square a one-key address
       comes out as.

       Keyed off .lf-spent's presence, the one question both halves turn on: a chord chip
       always has a half behind it (the leader is pressed before any chip is drawn) and an
       option's digit never does — it is one key, whole whenever it is drawn, and it wants
       neither a muted half nor a block inside its own box. Both rules take the same selector
       shape for that reason. Keyed differently, a chip could take the ground without the
       muting and come out half dressed. */
    .lf-address .lf-spent { color: var(--muted); }
    .lf-address .lf-spent + .lf-lit { padding: 0 3px; margin-left: -3px;
      border-radius: 3px; background: var(--accent); color: var(--card); }
    /* Under the banner there is no room to straddle the corner, so the chip hangs below
       the covered edge instead — the same step the legend's tag makes, and the same class
       name, because it is the same fact about the same bar. */
    .lf-addresses > .lf-address.lf-in { transform: translate(-50%, 0); }
    /* Item selection borrows the address chip's face but not its meaning. These hints are
       deliberately local to the viewport: the page gives every visible item a short,
       prefix-free name for the few seconds this mode stands. Unlike addresses, hints are
       never dropped for a collision — they are the route itself, not a reminder of a
       stable route that works without being drawn. Nested targets that begin at the same
       corner are spread by the hint pass before this layer is shown. */
    .lf-targets { position: fixed; inset: 0; z-index: 9070; pointer-events: none; }
    .lf-targets > .lf-target-hint { position: absolute; display: block;
      transform: translate(-50%, -50%); }
    .lf-targets > .lf-target-hint.lf-in { transform: translate(-50%, 0); }
    .lf-targets > .lf-target-hint.lf-current { font-weight: 700;
      box-shadow: 0 0 0 2px var(--accent); }
    /* Search has one active result, painted as a quiet wash rather than a second native
       selection. The real Selection is made only on Enter, when the ordinary comment
       surface takes over. One inset line survives over both light and dark authored fills
       without changing the page's layout or wrapping its words. */
    .lf-target-match { position: absolute; box-sizing: border-box; pointer-events: none;
      border-radius: 2px;
      background: color-mix(in srgb, var(--accent) 17%, transparent);
      box-shadow: inset 0 -2px color-mix(in srgb, var(--accent) 72%, transparent); }
    .lf-target-search { position: fixed; z-index: 9080;
      top: calc(var(--lf-banner-h) + 10px); left: 50%; transform: translateX(-50%);
      width: min(390px, calc(100vw - 28px)); box-sizing: border-box;
      display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center;
      gap: 10px; padding: 7px; border: 1px solid var(--border-2);
      border-radius: var(--r); background: var(--card);
      box-shadow: 0 8px 24px rgba(0,0,0,.14); }
    .lf-target-search[hidden] { display: none; }
    .lf-target-search-box { min-width: 0; box-sizing: border-box; font: inherit;
      padding: 6px 8px; border: 1px solid var(--border-2); border-radius: 5px;
      background: var(--paper); color: var(--ink); }
    .lf-target-search-box:focus-visible { outline: var(--here-ring);
      --lf-here-ring: target-search; outline-offset: 1px; }
    .lf-target-search-status { min-width: 58px; color: var(--muted);
      font-size: var(--t-6); text-align: right; white-space: nowrap; }
    .lf-legend-box { position: absolute; z-index: 8910; pointer-events: none;
      box-sizing: border-box;
      border: 1px dashed color-mix(in srgb, var(--accent) 55%, transparent); }
    .lf-legend-tag { position: absolute; left: -1px; bottom: 100%; max-width: 40vw;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      padding: 0 5px; border-radius: 3px 3px 0 0; font-size: var(--t-6); line-height: 1.5;
      background: color-mix(in srgb, var(--accent) 12%, var(--card)); color: var(--accent);
      border: 1px solid color-mix(in srgb, var(--accent) 55%, transparent); border-bottom: 0; }
    /* Under the banner there is no room above the box, so the tag sits inside its
       corner instead. */
    .lf-legend-box.lf-in .lf-legend-tag { bottom: auto; top: 0; border: 0;
      border-radius: 0 0 3px 0; }
    .lf-banner.lf-designing { background: color-mix(in srgb, var(--accent) 14%, var(--veil)); }
    /* Document-anchored like the box it names (paintInspect adds the scroll), so the
       two move together between the events that re-derive them. */
    .lf-inspect { position: absolute; z-index: 9060; pointer-events: none; display: none;
      max-width: 60vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      padding: 1px 6px; border-radius: 3px; font-size: var(--t-6); line-height: 1.5;
      background: var(--accent); color: var(--paper); }
    .lf-inspect.lf-shown { display: block; }
    /* On a phone the banner is a status shelf, not a cropped desktop row. The status
       gets a quiet first line and the action row scrolls independently underneath it;
       the two actions that complete the feedback loop are ordered first, so no hidden
       overflow has to be discovered before a reader can comment or approve. */
    @media screen and ${COVERING} {
      .lf-banner { display: grid; grid-template-columns: minmax(0, 1fr);
        grid-template-rows: 40px 48px; gap: 0;
        padding: var(--lf-safe-top) 0 7px; }
      .lf-banner-status { grid-row: 1; padding: 0 calc(14px + var(--lf-safe-right)) 0
          calc(14px + var(--lf-safe-left)); gap: 9px; }
      .lf-banner-actions { grid-row: 2; width: 100%; max-width: 100%; min-width: 0;
        justify-content: flex-start;
        scroll-padding-inline: calc(14px + var(--lf-safe-left));
        padding: 4px calc(14px + var(--lf-safe-right)) 4px
          calc(14px + var(--lf-safe-left)); gap: 4px; }
      .lf-banner-actions > .lf-others { margin-inline-end: 0; }
      .lf-banner-actions > .lf-btn { min-height: 40px; padding-inline: 8px; }
      /* A pinned wide row reserves its future Latest address so publication cannot move
         controls. The phone shelf starts at the primary controls, so an unseen slot there
         is only blank scrolling; collapse it until the news itself is present. */
      .lf-latest-chip:not(.lf-news-shown) { display: none !important; }
      .lf-version-menu { right: calc(8px + var(--lf-safe-right)); }
    }
    /* Coarse pointers get physical room without making the mouse layout pay for it.
       Margin actions and reaction tokens remain visually compact; their boxes, panel
       controls, and the otherwise eight-pixel resize edge become comfortable aims.

       A mouse can follow a whole seam without preventing anything underneath it from
       scrolling. A finger cannot: touch-action belongs to the hit box, so a full-height
       wide edge turns that much of a sheet into a vertical scroll trap. The touch edge is
       therefore one visible local grip, tall enough to take deliberately and short enough
       to go around while reading. It stays inside its own region at every width instead of
       changing sides when a covering sheet meets a phone, and its line remains on the seam
       rather than following the middle of the hit box. */
    @media (pointer: coarse) {
      .lf-btn, .lf-pill:is(button, [role="button"]), .lf-margin-action {
        min-height: 44px;
      }
      .lf-banner-actions > .lf-btn { min-height: 44px; }
      .lf-panel-head .lf-btn { min-width: 44px; }
      .lf-pill:is(button, [role="button"]) { display: inline-flex; align-items: center; }
      .lf-react { min-width: 44px; }
      .lf-margin-item.lf-condensed .lf-margin-action[data-lf-collapse="auto"] {
        width: 44px; min-width: 44px !important;
      }
      .lf-key-more { min-width: 44px; min-height: 44px; align-items: center; }
      .lf-edge { top: 50%; bottom: auto; width: 44px; height: 44px;
        transform: translateY(-50%); }
      .lf-edge[data-lf-side="right"] { left: var(--here-ring-w); }
      .lf-edge[data-lf-side="right"]::before {
        left: calc(-2px - var(--here-ring-w)); }
      .lf-edge[data-lf-side="left"] { right: var(--here-ring-w); }
      .lf-edge[data-lf-side="left"]::before {
        right: calc(-2px - var(--here-ring-w)); }
      .lf-edge::before { top: 10px; bottom: 10px; border-radius: 1px; opacity: .35; }
    }
    /* Windows high-contrast mode suppresses the shadow used by text fields. Restore a
       platform-colour outline for every focused chrome control instead of freezing the
       product palette with forced-color-adjust. */
    @media (forced-colors: active) {
      .lf-dot { background: CanvasText !important; }
      :scope :focus-visible { outline: 2px solid Highlight !important;
        outline-offset: 2px !important; box-shadow: none !important; }
      :scope :is([aria-pressed="true"], [aria-checked="true"], [aria-current]) {
        border-color: Highlight !important; }
    }
  }
`;
}
