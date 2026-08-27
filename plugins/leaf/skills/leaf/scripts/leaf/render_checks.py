"""Browser programs used by the render and export gates."""

# ---------- check --render: the browser half of the gate ----------

# A probe here sweeps the document, and an x-shadow widget's words are not in it:
# querySelectorAll stops at the root boundary, and a climb by parentElement ends at the
# top of one. A reading written that way goes on working perfectly for every other widget
# and says nothing about that one, reporting nothing — so a probe whose subject can be in
# there follows the boundary both ways, as UNREAD_SYNTAX does for the diff's coloured
# code: 24 of the 41 coloured spans on pr-walkthrough. The rest sweep the document because
# the one root on the page holds none of what they ask about — no .lf-ui, no declared
# label, nothing past the column — which is a fact about today's widget, not about them.
#
# A probe that needs the page's own reading of something imports it from
# /runtime/widget-api.js, which is the boundary a behavior module is held to and the one
# this gate is held to for the same reason. What the entry module happens to hold is the
# runtime's own composition, and the runtime is mid-way through moving those helpers out to
# their owners: a probe naming the entry module asserts that composition on every page it
# reads, so a split that changed no behaviour took quoted() out from under eight probes at
# once and reddened eleven tests with `leaf.quoted is not a function`. The boundary names
# capabilities, and a capability that leaves it is a decision somebody made rather than a
# file a function moved between. The entry module's own path is not spelled anywhere in
# this file, comments included, because the test that holds this is a text reading and
# cannot tell a comment from a payload.

RENDER_VIEWPORT = {"width": 1200, "height": 900}


# A widget that upgraded into no room to be read in. The floor is two numbers, and
# which of them a widget is held to is the widget's to declare (x-inline), because
# the two kinds are laid out by different rules: one reserves a region and the other
# is set among the words around it, where the box is the words and there is no width
# it was supposed to reach. Held to the region's floor, an inline widget fails for
# being short — a chip reading a price is 31px wide and correct, and the gate reported
# the author's own words as a collapse. The height floor is both kinds': a line of
# words is a line tall wherever it is laid out, which leaves a flattened chip caught.
#
# Declared, not read off the computed display, because a custom element with no rule
# left standing computes as inline: a theme that lost the chip block would silence the
# check that exists to catch it.
#
# [hidden] needs its own exclusion: hidden="until-found" (what a closed tab wears)
# resolves to content-visibility, which checkVisibility reports as visible while the
# box measures zero. That collapse is the point of a closed tab; the collapse being
# hunted here is the one nothing asked for.
# A control drawn where no reader can reach it. `TINY_BOXES` asks whether a widget got a
# box at all; this asks the question one level down, of the chrome inside it, and the
# difference is which failure each catches: a widget with no box is a widget that didn't
# render, and a control with a box its own container clips away is a widget that rendered
# and then hid its offer behind the frame it drew.
#
# It is the failure with no witness. Nothing overflows the page, so the sideways-scroll
# check is quiet; nothing is past the column, so that gate is quiet; the words are in a
# text node and technically selectable, so the unreachable-words gate is quiet. What the
# reader gets is a question with no visible way to answer it — which is exactly what
# shipped: a `choose` group in its row form states `width: 100%` on options that a
# live-page rule gives a 30px keyboard-address rail, and under the default box-sizing
# those are the row's width *plus* its padding, so every row ran 28px wider than the
# group whose `overflow: hidden` keeps its cells' hairlines square. The last cell is the
# pick mark, so all of it went over the edge: every row-form decision on every live page
# drew no dot, no "chosen", nothing. Paper and an exported copy were right throughout,
# the rail being live-pages-only, so no medium outside a browser could see it.
#
# Only where the clip cannot be scrolled away. A board's columns run past the board and
# are reached by scrolling, which is the arrangement rather than a fault, so an ancestor
# with something to scroll answers for what it holds. And only for controls the page
# offers (data-lf-offer), which keeps it clear of everything deliberately clipped to
# nothing — the paint pass's quiet words, the line counting a block's comments — whose
# whole point is to be read and not seen.
CLIPPED_CONTROLS = """() => {
    const out = [];
    for (const el of document.querySelectorAll('[data-lf-offer]')) {
        // checkOpacity too: a control faded to nothing is as unreachable as one clipped
        // away, and reporting it against a box it is inside would name the wrong fault.
        if (!el.checkVisibility({ checkOpacity: true }) || el.closest('[hidden]'))
            continue;
        const b = el.getBoundingClientRect();
        if (b.width < 1 && b.height < 1) continue;
        // Where the clip is escaped rather than suffered. An absolutely-positioned
        // control whose containing block is above the clipping ancestor is painted
        // outside it on purpose, exactly as MISPLACED_BOXES' own resident is.
        if (getComputedStyle(el).position === 'absolute') continue;
        // Up to the body and no further: the document's own scrolling arrangement is
        // the page's, not a widget's. The runtime scrolls body rather than the
        // viewport so the panel has room beside it, which leaves <html> clipping and
        // with nothing of its own to scroll — so a walk that ran to the root reported
        // every control below the fold as hidden by the page it is on.
        for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
            const s = getComputedStyle(a);
            // Asked of the overflow value, per axis, and not of the scroll extent. A
            // box that clips always has something to scroll — that is what clipping
            // means — so `scrollWidth > clientWidth` is true of exactly the boxes this
            // is about and would wave every one of them through. What separates a
            // board, whose columns run past it and are reached by dragging, from a
            // group that swallowed its own pick marks is whether the box offers the
            // reader a way in: auto and scroll do, hidden and clip do not. Paint
            // containment clips both axes while `overflow` computes `visible`
            // (MISPLACED_BOXES reads the same fact for its ancestors), and it denies
            // the way in exactly where the axis has no scroller of its own.
            const contained = /paint|strict|content/.test(s.contain);
            const scrollX = s.overflowX === 'auto' || s.overflowX === 'scroll';
            const scrollY = s.overflowY === 'auto' || s.overflowY === 'scroll';
            const across = s.overflowX === 'hidden' || s.overflowX === 'clip'
                || (contained && !scrollX);
            const down = s.overflowY === 'hidden' || s.overflowY === 'clip'
                || (contained && !scrollY);
            if (across || down) {
                const f = a.getBoundingClientRect();
                const lost = Math.round(Math.max(
                    across ? Math.max(b.right - f.right, f.left - b.left) : 0,
                    down ? Math.max(b.bottom - f.bottom, f.top - b.top) : 0));
                if (lost > 1) {
                    out.push({ ctrl: el.className, id: el.id,
                               by: `<${a.tagName.toLowerCase()}${a.id ? ' id=' + a.id : ''}>`,
                               lost });
                    break;
                }
            }
            // And the walk stops at the first box the reader can move. Above a
            // scroller, a control outside an ancestor's rect is a control that ancestor
            // will show once the scroller is dragged, so measuring it there would
            // report a press that is one gesture away as one drawn nowhere.
            if ((s.overflowX !== 'visible' && !across)
                || (s.overflowY !== 'visible' && !down)) break;
        }
    }
    return out;
}"""


TINY_BOXES = """(widgets) => {
    const inline = new Set(Object.entries(widgets)
        .filter(([tag, entry]) => entry['x-inline'])
        .map(([tag]) => tag));
    return [...document.querySelectorAll('*')]
        .filter(el => el.tagName.toLowerCase().startsWith('lf-')
                   && el.textContent.trim()
                   && el.checkVisibility()
                   && !el.closest('[hidden]'))
        .map(el => ({ tag: el.tagName.toLowerCase(), id: el.id,
                      w: Math.round(el.getBoundingClientRect().width),
                      h: Math.round(el.getBoundingClientRect().height) }))
        .filter(box => box.h < 10 || (!inline.has(box.tag) && box.w < 40));
}"""


# An element the reader can see and no mark can be shown on. The gate presses no keys, so
# it never watches the ask walk paint a ring or a comment paint an outline. It can still
# read whether either would have had anywhere to land, which is the same fault one step
# earlier, before it turns into a mark nobody can see.
#
# The fault is a box that isn't there. An element with `display: contents` lays its
# children out in its parent's flow and generates no box of its own, so its rect is the
# empty one every rect starts as — zero-sized, at the document's origin, a real-looking
# answer naming a place it is not. An outline drawn on it draws nothing, and a scroll
# aimed at it lands at the top of the page: a page whose open asks were all suggestions
# answered `n` by appearing to do nothing at all, and that reached its reader rather than
# this gate. The runtime answers it by hanging a mark on the boxes an element shows
# through (shownParts) — which leaves one case that answer cannot reach, an element whose
# words are in no child element at all, where there is nothing to hang anything on.
#
# TINY_BOXES is next door and cannot see this: `checkVisibility()` is false for an element
# with no box, so the very elements at issue are the ones it filters out. Both readings are
# imported rather than restated, so what the gate refuses a handover for and what the page
# actually paints cannot come apart — the whole point of the pair being that there is one
# answer to where an element is.
UNMARKABLE_ITEMS = """async () => {
    const { shownBox, shownParts } = await import('/runtime/widget-api.js');
    const HTML = 'http://www.w3.org/1999/xhtml';
    const found = [];
    for (const el of document.querySelectorAll('[id]')) {
        // The document's own elements, which is what an anchor can name and a walk can
        // step to. A rendered diagram's insides are none of those — they are one
        // picture, whose <lf-diagram> is the thing to point at and has a box of its
        // own — and they are full of shapes with ids and no layout box: every <marker>
        // in a mermaid flowchart's <defs> read as an item showing 11x11px of words.
        if (el.namespaceURI !== HTML) continue;
        if (el.closest('.lf-chrome')) continue;
        const box = shownBox(el);
        // Nothing on screen is nothing to mark, and nothing the reader can point at
        // either: a collapsed tab's contents, a slot a decision retired.
        if (!(box.width && box.height)) continue;
        if (shownParts(el).length) continue;
        found.push({ tag: el.tagName.toLowerCase(), id: el.id,
                     w: Math.round(box.width), h: Math.round(box.height) });
    }
    return found;
}"""


# Words the page shows that no user can select, and so no comment can be
# anchored on. A widget has two ways to leave them there, neither of which a
# static lint can see, and a page-local widget is where both keep happening.
#
# It can paint them: `content: attr(label)` puts a heading on screen and in no
# text node, so a selection can't cover it. The runtime says the attributes the
# registry marks x-says, and a widget's module says the rest (a chip row, a
# heading that doubles as a list's accessible name); either way, none of an
# element's own attribute values should still be reaching the reader as
# generated content.
#
# Or it can leave them under .lf-ui with nothing said about whose words they are.
# That class is the chrome face, a look — reaching for it as a general "this is
# chrome" marker is how a user ends up unable to comment on a heading they can
# see. The declaration is made where the label is written: data-lf-said for the page
# speaking, which the anchor pass reads over the box around it, data-lf-offer for a
# thing to work. So inside a widget, every word under .lf-ui has to be declared the
# page's, be a control's own label, or be the line the paint pass writes to say how
# many comments a block carries: that one is about the document rather than of it,
# which is the same reason it wears .lf-ui at all, and it lands inside a widget
# whenever a comment does. The comment panel is out of scope: a widget in a reply is
# markup frozen in the event log, not the document.
#
# And a declared label inside a form control is out of reach whatever it is marked:
# Chrome starts no pointer selection inside one, which is why `offer` builds a press
# as a span wearing role="button". A widget reaching for <button> anyway is the one
# mistake the marker cannot fix, so it is reported separately and says why.
UNREACHABLE_WORDS = """() => {
    const found = [];
    const at = el => `<${el.tagName.toLowerCase()}${el.id ? ' id=' + el.id : ''}>`;
    for (const el of document.querySelectorAll('*')) {
        if (!el.tagName.startsWith('LF-')) continue;
        const shown = ['::before', '::after']
            .map(w => getComputedStyle(el, w).content)
            .filter(c => c && c.startsWith('"'));
        for (const { name, value } of el.attributes)
            if (value.length > 1 && shown.some(c => c.includes(value)))
                found.push(`${at(el)} paints ${name}="${value}" rather than saying it`);
    }
    // The lf-* element something stands in, if any. A .lf-ui is a widget's own
    // chrome by standing in one of these, and the runtime's layer is appended to
    // body and stands in none — but a widget riding a message stands in the
    // layer, so which of the two a .lf-ui is has to be asked of the .lf-ui and
    // never of the words beneath it, which are inside a widget either way.
    const widget = el => { for (let a = el; a; a = a.parentElement)
                               if (a.tagName.startsWith('LF-')) return a; };
    // The anchor pass's own rule: the nearest element that answers wins.
    const speaks = el => Boolean(el.closest('.lf-ui, [data-lf-said]')?.matches('[data-lf-said]'));
    const FORM = 'button, textarea, input, select';
    // Where a control's own words may sit: the control a widget declared (data-lf-offer,
    // asked instead of the role it wears, because lf-tabs overwrites `offer`'s
    // role="button" with "tab" and a Δ badge in a tab then read as a heading somebody
    // hid while the identical badge in a settled row read as chrome), or a native
    // control. `label` is among those because a radio and a checkbox have nowhere else
    // to put their words: a button holds its own, an input cannot, and HTML's answer is
    // an element beside it. lf-shot's flip is a checkbox, so that it keeps working in a page
    // whose script is gone. The line counting a passage's comments is one of these too —
    // the runtime builds it through `offer`, as a widget builds its own.
    const CONTROL = `${FORM}, label, a[href], [data-lf-offer]`;
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
        const el = n.parentElement;
        if (!n.data.trim()) continue;
        // Whose the .lf-ui is, per `widget` above. A widget's own chrome is read
        // here wherever the widget stands, a message included; the panel around a
        // widget riding one is not, which is what the note on the panel means.
        const chrome = el.closest('.lf-ui');
        if (!chrome || !widget(chrome)) continue;
        if (speaks(el) || el.closest(CONTROL)) continue;
        // A local work line is runtime chrome about its owning widget, not authored
        // words of that widget. Its subject is the anchor; the provisional sentence
        // deliberately is not another passage the reader can thread.
        if (el.closest('.lf-work-line')) continue;
        // .lf-quiet is words for a reader listening, clipped to nothing: not on
        // screen, so there is nothing here the eye can see and the pointer can't
        // reach — the failure this check exists for.
        if (el.closest('.lf-quiet')) continue;
        found.push(`${at(widget(el))} puts ${JSON.stringify(n.data.trim().slice(0, 40))} `
                   + `under .lf-ui, where no comment can reach it`);
    }
    // FORM rather than CONTROL: a <label>'s words select like any others, and a widget
    // that declared a box a control has said nothing about what element it is.
    for (const el of document.querySelectorAll('[data-lf-said]')) {
        if (!el.closest(FORM) || !widget(el)) continue;
        found.push(`${at(widget(el))} says ${JSON.stringify(el.textContent.trim().slice(0, 40))} `
                   + `inside a form control, where no selection can reach it`);
    }
    return [...new Set(found)];
}"""


# Every box is drawn somewhere, and something has to answer for where. Three
# readings ask it — of the column, of the room the page keeps for a wide widget,
# and of the container that was handed a box's overflow — and the last two are
# written beside the loops that make them.
#
# The column first: content set outside the one it belongs to. The
# sideways-scroll reading is the same question asked of the window, and the
# window is the wider of the two: the gate renders at 1200px against a 720px
# column, so 200px of margin on each side absorbs a spill that scrolls nothing.
# What is out there is the margin, where a suggestion's controls hang, and the
# user's own window is free to be narrower than this one — so a page that passed
# here scrolls sideways on the machine it was written for.
#
# The static lint asks about the column too (_column_width), and asks it of the
# stylesheet, because that is all a linter has: a width the author pinned in
# pixels, against a number parsed out of a max-width. This is the same column
# with a layout engine behind it, so it is measured rather than parsed, and it
# catches what no declaration states — a vw width, an unbreakable table, a
# widget that came out wider than its content.
#
# Two kinds of element answer for their own width and not to this, and both say
# so in their computed style. The margin has legitimate residents — a
# suggestion's controls, a sidenote, the hidden line the paint pass writes — and
# each is out there by its own declaration: placed absolutely, or floated clear
# of the column. Where the box sits is what separates a resident from a spill,
# which crosses the column's edge rather than clearing it, having started inside
# and run out. So a float that merely overflows is still reported, and a widget's
# own float inside the column (an option's .facts rail) is never in question.
#
# A resident answers for what it holds, which is why both readings are made up the
# ancestors and not of the element alone. A sidenote is prose, so it carries the
# <code>, links and emphasis any other prose does, and each of those inherits a box
# its parent put in the margin on purpose — named, one by one, as spilling out of a
# column none of them was ever in.
#
# And a scroll container answers for what it holds: a box inside one runs on
# past the clip and is drawn only as far as its container reaches, so a wide
# table's own rows would otherwise be reported as spilling out of the table that
# is containing them. What is left is the flow, which the column is the whole
# width of. A spill is reported once, at the outermost element that has it,
# because everything inside one inherits its box and would name the same fault a
# dozen times over.
# What stands in the page's margin by its own declaration — placed absolutely, or
# floated clear of the column — as one reading shared by the two passes that ask:
# MISPLACED_BOXES, deciding whether a wide widget was drawn over one, and
# WITHHELD_ROOM, deciding whether an exhibit's sideways scroll answers to a margin's
# occupant or to room the layer withheld. A resident is whatever answered for itself
# out there, so a project hanging its own furniture in the margin is covered without
# declaring anything to either pass. Spliced after `main`, `left` and `right` are in
# scope, the way OPEN_ROOTS is spliced where `roots` is wanted.
MARGIN_RESIDENTS = """
    // `float` computes to whichever of the four values was written, so the two
    // logical ones are resolved against the element's own direction rather than
    // compared as strings: `inline-start` is the left edge in a LTR page and the
    // right edge in a RTL one, and a side read wrong reports a note that is exactly
    // where it belongs.
    const floatSide = (s) =>
        s.float === 'left' || s.float === 'right' ? s.float
        : (s.float === 'inline-start') === (s.direction !== 'rtl') ? 'left' : 'right';
    const inTheMargin = (el, s) => {
        if (s.float === 'none') return false;
        const b = el.getBoundingClientRect();
        return floatSide(s) === 'left' ? b.right <= left + 1 : b.left >= right - 1;
    };
    const residents = [];
    for (const el of main.querySelectorAll('*')) {
        if (!el.checkVisibility() || el.hasAttribute('data-lf-wide')) continue;
        const s = getComputedStyle(el), b = el.getBoundingClientRect();
        // Clipped to nothing is not standing in the margin: the words a page paints for
        // whoever is listening are a pixel wide and under a reader's notice, so a widget
        // drawn across one has taken nothing from anybody.
        if (b.width < 2) continue;
        const clear = b.right <= left + 1 || b.left >= right - 1;
        if (clear && (s.position === 'absolute' || inTheMargin(el, s))) residents.push(el);
    }
"""

MISPLACED_BOXES = (
    """async () => {
    // shownBand is the runtime's own: what a container lets the reader see of what it
    // holds, or nothing where it shows all of it. Imported rather than restated, so the
    // band a handover is refused against and the band the page paints to cannot come
    // apart — and because `overflow` is one of three ways to draw nothing past an edge.
    // (TRAPPED_MARGINS reads `contain` for the neighbouring question: which margins a
    // formatting context keeps in.)
    const { shownBand } = await import('/runtime/widget-api.js');
    const main = document.querySelector('main');
    if (!main) return [];
    const style = getComputedStyle(main), box = main.getBoundingClientRect();
    const left = box.left + parseFloat(style.paddingLeft);
    const right = box.right - parseFloat(style.paddingRight);
    // A widget the registry declares wide is answered for out here, the way an
    // absolutely-positioned resident is: standing past the column is what it was
    // declared for. What still has to hold is the page's own box — the room the layout
    // measured is the column's leftover, the rail a suggestion hangs in and the strip
    // the comment panel takes, and an exhibit over that edge is in the margin whether or
    // not the window happened to scroll for it. So the question is the same one, asked
    // against the wider bound: this gate renders at one viewport with no panel open, and
    // the reader's window is free to be narrower than this one.
    const bodyStyle = getComputedStyle(document.body);
    const bodyBox = document.body.getBoundingClientRect();
    const roomLeft = bodyBox.left + parseFloat(bodyStyle.paddingLeft);
    const roomRight = bodyBox.right - parseFloat(bodyStyle.paddingRight);
    const at = el => `<${el.tagName.toLowerCase()}${el.id ? ' id=' + el.id : ''}>`;
"""
    + MARGIN_RESIDENTS
    + """
    // Both readings that hand a box to an ancestor ask shownBand, or a box inside a
    // container that clips without saying so in `overflow` is named for a spill it is
    // drawn nowhere near and left unnamed for the loss it did take, the walk at the foot
    // of this pass having gone straight past the container that cut it.
    const answeredFor = (el) => {
        const own = getComputedStyle(el);
        if (own.position === 'absolute' || inTheMargin(el, own)) return true;
        for (let a = el.parentElement; a && a !== main; a = a.parentElement) {
            const s = getComputedStyle(a);
            if (s.position === 'absolute' || inTheMargin(a, s)) return true;
            if (shownBand(a)) return true;
        }
        return false;
    };
    // The bound a descendant of a wide widget is held to. The column is the wrong one —
    // the room is exactly what the declaration granted, and several prose rows had all
    // been reported as standing out in the margin — but "answered for" is wrong too,
    // and wrong in the direction that costs: a child that paints past its own widget's
    // box does not grow that box, so exempting the subtree makes the widget's rect prove
    // something about itself alone. This read as answered while both wide widgets also
    // scrolled, `overflow-x: auto` having caught every descendant a line above.
    const insideWide = (el) => {
        for (let a = el.parentElement; a && a !== main; a = a.parentElement)
            if (a.hasAttribute('data-lf-wide')) return a;
        return null;
    };
    // What a wide widget may not escape, whatever the page has room for: the nearest
    // thing between it and the column that draws a box of its own. Asked of the drawing
    // rather than of a list of tags, because the fault is visual and so is the property
    // — a widget that stands outside a frame, a tint or a fill reads as a broken page,
    // and one that grows through a transparent wrapper (a section, a tab's panel) reads
    // as the exhibit it is. A box that draws one says so where it draws it (--lf-frame,
    // theme.css) and the theme reads that declaration to withhold the room; this is what
    // says so when a box that draws hasn't made it. (Nothing to do with x-paints, which is
    // about words rather than boxes: an attribute rendered as paint instead of text, and
    // spoken for whoever is listening.)
    const draws = (el) => {
        const s = getComputedStyle(el);
        return s.backgroundImage !== 'none'
            || !/^(transparent|rgba\\(0, 0, 0, 0\\))$/.test(s.backgroundColor)
            || ['Top', 'Right', 'Bottom', 'Left'].some(side =>
                   parseFloat(s[`border${side}Width`]) > 0
                   && s[`border${side}Style`] !== 'none');
    };
    const framing = (el) => {
        for (let a = el.parentElement; a && a !== main; a = a.parentElement)
            if (draws(a)) return a;
        return null;
    };
    const over = new Map();
    for (const el of main.querySelectorAll('*')) {
        const wide = el.hasAttribute('data-lf-wide');
        // A wide widget is asked whatever it stands in, where everything else is excused
        // by a scroll container above it. The excuse is about the column — a box inside a
        // scroller is drawn only as far as the scroller reaches, so it cannot spill onto
        // the page — and a wide widget's question is a different one: it is measured
        // against the box that frames it, and a board scrolls, so every card on every
        // board was excused from the only reading that applies to it. A diagram in a card
        // was drawn across the neighbouring column and this said the page was clean.
        if (!el.checkVisibility() || (!wide && answeredFor(el))) continue;
        const b = el.getBoundingClientRect();
        if (b.width < 1) continue;
        const frame = wide ? framing(el) : null;
        const host = wide ? null : insideWide(el);
        const bound = (frame || host)?.getBoundingClientRect() ?? null;
        const past = wide || host
            ? Math.round(Math.max(b.right - (bound ? bound.right : roomRight),
                                  (bound ? bound.left : roomLeft) - b.left))
            : Math.round(Math.max(b.right - right, left - b.left));
        if (past > 1) over.set(el, [past, wide, frame, host]);
    }
    const found = [];
    for (const [el, [past, wide, frame, host]] of over) {
        if ([...over.keys()].some(other => other !== el && other.contains(el))) continue;
        found.push(host
            ? `${at(el)} stands ${past}px outside the ${at(host)} it is part of`
            : !wide
            ? `${at(el)} is set ${past}px past the column, out in the margin`
            : frame
            ? `${at(el)} stands ${past}px outside the ${at(frame)} that frames it — `
              + `declare --lf-frame: 1 in the rule that draws the frame, so the box `
              + `holds the room in as well as the margins`
            : `${at(el)} stands ${past}px past the room the page has for a wide widget`);
    }
    // The room being the page's own box is not the whole of what a wide widget owes,
    // because the page hangs things in that box. A suggestion's controls stand 22px off
    // the column and a sidenote a gutter off it on the other side, while the strip each
    // is reserved out of comes off the far edge of the page — and those are the same
    // place only when the column is flush against the strip, which it never is, since it
    // centres in what the strip leaves. So the reservation says where the room ends and
    // the occupancy says where the furniture is, and between them is a band that is
    // inside the page's box and already spoken for. A board grown to the box was drawn
    // 134px over the controls that decide the change above it, which is the change made
    // undecidable by the page's own exhibit.
    //
    // The theme is where a margin's claimant gives up that side (--lf-grow-l, --lf-grow-r),
    // and this is what says so when one of them doesn't — the same bargain the framing
    // rule above has, and the reason neither has to be a list anybody maintains. A
    // resident is whatever answered for itself in the margin above (MARGIN_RESIDENTS),
    // so a project hanging its own furniture out there is covered without declaring
    // anything to this pass.
    for (const el of main.querySelectorAll('[data-lf-wide]')) {
        if (!el.checkVisibility()) continue;
        const b = el.getBoundingClientRect();
        const hit = residents.find((r) => {
            if (el.contains(r) || r.contains(el)) return false;
            const c = r.getBoundingClientRect();
            return b.left < c.right - 1 && b.right > c.left + 1
                && b.top < c.bottom - 1 && b.bottom > c.top + 1;
        });
        if (hit) found.push(`${at(el)} is drawn over ${at(hit)}, which stands in the `
                            + `margin it grew into — the side that holds it gives no room`);
    }
    // The other half of excusing a resident: an excuse is only good if the reader can
    // see the thing. Both readings above hand a box to something else to answer for —
    // the margin it was placed in, the container that took its overflow — and the
    // second is worth exactly what the reader can tell from that container. A scroller
    // answers for what ran out of it on the side it scrolls toward, scrollLeft running
    // from zero to the overflow and never the other way. A box that marks where it cut
    // answers for the rest, the mark being what says there is a rest. And a box that
    // only clips answers for nothing at all: what leaves a choose group, a board or a
    // table is drawn nowhere and said nowhere either, and every other reading here
    // calls such a page well — checkVisibility() is true of a clipped box, so screen
    // and print agree, and the copy withholds the clip and shows the words the live
    // page dropped. The reader is the only party who loses them, which is why the
    // question is asked here, where the excuse was granted.
    //
    // Every box and not floats alone. A float is how a resident reaches the margin, so
    // it was the shape the failure first arrived in; the rule is about the excuse, and
    // a container grants that to whatever stands inside it. Held to floats it watched
    // one sidenote and let a question through: a row-form option 30px wider than the
    // group holding it carried every mark on it past the clip, and four of the examples
    // shipped a decision with no box to tick.
    //
    // Across the page and not down it, which is the axis every reading here takes: a
    // box cut off below its container is usually cut on purpose — a collapsed
    // disclosure, a shot's frame, a draft's box are all a height with the rest hidden —
    // where one cut off at the side never is.
    //
    // The nearest container and no further, because past it what an outer box sees is
    // that container's own edges, and the container answers the same question on its
    // own turn of the loop. Body is the page's scroller, so this is also where a float
    // carried off the leading edge of the window is named — the sideways reading, which
    // reads how far the page scrolls, cannot see one. Wholly inside, because a box half
    // in the clip is half unreadable: the group above leaves 7px of a 192px note
    // showing, which is nothing an "overlaps at all" reading would have objected to.
    const scrolls = (s) => /^(auto|scroll)$/.test(s.overflowX);
    const lost = new Map();
    // Up the containing blocks rather than the markup, since those are the boxes that
    // hold this one: an absolutely-placed box hangs off the nearest ancestor that
    // establishes one, and a static box it happens to be written inside clips it not at
    // all. offsetParent names that ancestor. Its own definition says positioned
    // ancestors, which reads as a gap — transform, filter, will-change, contain and
    // content-visibility each establish a containing block too — but Chrome returns
    // those as well, agreeing with where the box lands, so the property list a reader
    // reaches for here is already in the one call. A fixed box hangs off none of them.
    const holder = (el) => {
        const s = getComputedStyle(el);
        return s.position === 'absolute' ? el.offsetParent
             : s.position === 'fixed' ? null
             : el.parentElement;
    };
    for (const el of main.querySelectorAll('*')) {
        if (!el.checkVisibility()) continue;
        // Nothing inside an <svg> is the page's flow: a foreignObject clips by its
        // nature, and mermaid's label boxes run an even 8px outside theirs on an
        // ordinary graph — the drawing's own accounting, not the page losing words.
        if (el.closest('svg')) continue;
        const b = el.getBoundingClientRect();
        if (b.width < 1) continue;
        let a = holder(el), band = null;
        for (; a; a = holder(a)) { band = shownBand(a); if (band) break; }
        if (!a) continue;
        const s = getComputedStyle(a);
        // text-overflow is the mark, declared in the rule that does the cutting, the
        // way --lf-frame is declared where the frame is drawn. The box itself still
        // answers here on its own turn.
        if (s.textOverflow !== 'clip') continue;
        const overL = band.left - b.left, overR = b.right - band.right;
        // A scroller reaches its whole content on the side it scrolls toward, so only
        // its leading edge is asked — and asked from scroll position zero, since where
        // the container happens to be scrolled while the gate reads it says nothing
        // about where its content ends.
        const past = Math.round(
            !scrolls(s) ? Math.max(overL, overR)
            : s.direction === 'rtl' ? overR + a.scrollLeft
            : overL - a.scrollLeft);
        if (past > 1) lost.set(el, [past, a]);
    }
    for (const [el, [past, a]] of lost) {
        // Out of the same container, because that is what makes the outer box's report
        // the inner one's too. Suppressing on containment alone let a box lost 3px out
        // of one container hide the one hung off it and lost 400px out of another.
        if ([...lost].some(([o, [, its]]) => o !== el && its === a && o.contains(el)))
            continue;
        found.push(`${at(el)} is drawn ${past}px outside ${at(a)}, which does not show it`);
    }
    return [...new Set(found)];
}"""
)


# A drawing scrolling beside room that would have shown it whole. Scrolling is the
# theme's honest degrade when even the room runs short, so every reading above calls
# such a page well — nothing is clipped without a scrollbar, nothing stands outside any
# box — and that is exactly how both margin claims went wrong before: a claim spent
# page-wide held a diagram to the column with the margin beside it empty, a diagram in
# the room's terms merely "scrolling". So the question is the visible result, asked
# without trusting the mechanisms that decide it (`clear` for a note, data-lf-yield for
# a suggestion's rail): a drawing that scrolls, inside room that would have held it,
# with nothing standing in the margin at its own band, is room withheld from the one
# widget whose width is its own fact. Drawings alone, because "would the room have held
# it" needs the exhibit's own width, which a box (a board laying columns into whatever
# it is given) does not state. A drawing inside a frame reads the frame's withheld room
# (--lf-room: 0) and is excused the way it is granted — by the declaration it inherits.
WITHHELD_ROOM = (
    """() => {
    const main = document.querySelector('main');
    if (!main) return [];
    const style = getComputedStyle(main), box = main.getBoundingClientRect();
    const left = box.left + parseFloat(style.paddingLeft);
    const right = box.right - parseFloat(style.paddingRight);
    const at = el => `<${el.tagName.toLowerCase()}${el.id ? ' id=' + el.id : ''}>`;
"""
    + MARGIN_RESIDENTS
    + """
    const found = [];
    for (const el of main.querySelectorAll('[data-lf-wide="drawing"]')) {
        if (!el.checkVisibility()) continue;
        const short = el.scrollWidth - el.clientWidth;
        if (short <= 1) continue;
        const room = parseFloat(getComputedStyle(el).getPropertyValue('--lf-room'));
        if (!(room > 0) || el.scrollWidth > room + 1) continue;
        const b = el.getBoundingClientRect();
        // A resident at the drawing's own band is the margin spoken for, whichever
        // side it stands on: the exhibit owes it the side it holds, and what is left
        // can genuinely run short.
        if (residents.some(r => {
            const c = r.getBoundingClientRect();
            return c.top < b.bottom - 1 && c.bottom > b.top + 1;
        })) continue;
        found.push(`${at(el)} scrolls ${short}px of a drawing sideways inside `
            + `${Math.round(room)}px of room that would have held its ${el.scrollWidth}px `
            + `whole, with nothing standing in the margin beside it`);
    }
    return found;
}"""
)


# A table scrolling sideways with a cell in it wrapped. The theme's three cases for a
# table — take the measure only when asked, wrap the cells past that, scroll when even
# wrapping can't fit — are in order, and the third is reached through the second: a
# table scrolls once every column is at its minimum, and a column's minimum is its
# longest unbreakable run. So whatever wraps in a scrolling table wraps at a word a
# line, and the reader gets both costs at once: prose a few words to the line down a
# 3174px table, and a scroller for the rest. What scrolls with nothing left to wrap
# (eight columns of single tokens) is the honest third case and passes.
#
# The finding states the widths and leaves the diagnosis to the author, because the
# widths carry it and a cause asserted here was wrong: a column of test names written
# outside <code> holds a table open at 583px beside prose at 118px, and twelve columns
# of ordinary prose hold one open at 87px each, and "squeezed by what cannot break" was
# said of both. So every column is listed with its width, and both remedies are offered.
#
# A column wraps when it stands wider with wrapping turned off, and that is the whole
# reading: every column of a scrolling table is at its longest unbreakable run, so a
# sheet turning wrapping off lets each column out to the width its content asked for,
# and the ones that move are the ones whose content had wrapped. The sheet says
# `text-wrap: nowrap` and not `white-space: nowrap`, because the shorthand also
# collapses white space and would have taken an author's newlines under a page rule
# setting cells `pre-wrap`; `flex-wrap: nowrap` beside it, because a milestone's chips
# stacked seven deep in a 114px cell with no text wrapping at all; `!important` on the
# descendants too, because a widget's own rule beats an inherited value — a draft's
# body is `pre-wrap` by the default package's sheet; and not on a textarea, whose
# value wraps inside a box the table never sized. The gate reads its own page, so the
# probe changes nothing a reader sees, and later readings measured the same before
# and after it.
#
# The column and not a row or a cell's glyphs, after three readings of line boxes,
# three of which glyphs are on the page, and one of row height each fell to a measured
# counterexample: an inline <code> is set at 84% and starts 3px lower on the same
# line; two lines' glyph boxes overlap at line-height 1; a closed details' body, an
# unselected tab and anything under content-visibility: hidden are laid out on demand
# and hand back real rects, so every reading of rects let some hidden line in or some
# painted line out; and a row is held tall by its tallest cell, so prose squeezed to
# a word a line beside a <br> list of names — the ordinary walkthrough table — read
# clean, and an image at width: 100% grew under the probe and hid the wrap beside it.
# None of that reaches a column's width: hidden content is size-contained and asks for
# nothing, a neighbour's height is not a width, a fixed-width block or a widget with a
# scroller of its own asks for exactly what it had, and a <br> line or a <pre> line is
# its own longest run. The remaining reach the probe lacks is stated so nobody looks
# for it here: a rule more specific than a tag name that says `!important` outranks
# it; a widget's shadow tree takes it by inheritance only, and a rule inside the tree
# beats that; a grid that flows its items onto more rows is a third kind of wrapping
# the sheet does not turn off; a cell an author caps with a max-width under its
# longest word, or fills with absolutely positioned words, asks for nothing more and
# wraps unreported. Each is a table cell holding something a leaf page has not yet
# put in one. A widget's own chrome in a cell never binds: a group's reply box sits
# inside the width its labels already ask for, measured.
#
# A column is where its cells stand rather than where they come in the row — a rowspan
# shifts the next row's cells over, a two-row header names a column twice — and a
# scrolling table's columns have edges that hold still, so cells are grouped by their
# left edge, in the table's reading direction, and named by the first column heading
# standing on it, a head's outranking a foot's; a heading's name is what it says, so
# a comment badge the mark pass put in it stays out, through the runtime's own
# `uiInside`. A cell that says `colspan`, whatever the number, belongs to no column,
# and the sheet leaves it wrapping — one predicate for both, since a `colspan="1"`
# read as a column by one and left wrapping by the other went unreported: a note
# across the whole table wraps because it is long, says nothing about a squeeze, and
# unwrapped would push every column it spans out and name them all.
# A cell in a hidden or collapsed row has no height. Read from `main`, where geometry
# is real.
SQUEEZED_TABLES = r"""async () => {
    const main = document.querySelector('main');
    if (!main) return [];
    const { uiInside } = await import('/runtime/widget-api.js');
    const at = el => `<${el.tagName.toLowerCase()}${el.id ? ' id=' + el.id : ''}>`;
    // What a heading says, for the column's name.
    const says = (cell) => {
        let text = '';
        const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
        for (let node; (node = walker.nextNode());)
            if (!uiInside(node.parentElement, cell)) text += node.data;
        return text.trim().replace(/\s+/g, ' ');
    };
    const tables = [...main.querySelectorAll('table')].filter(t =>
        t.checkVisibility() && t.scrollWidth - t.clientWidth > 1);
    // Each table's columns by left edge, each with its cells, before the probe.
    const read = new Map();
    for (const table of tables) {
        const columns = new Map();
        for (const cell of table.querySelectorAll('th, td')) {
            if (cell.closest('table') !== table || cell.hasAttribute('colspan')) continue;
            const box = cell.getBoundingClientRect();
            if (!box.height) continue;
            const left = Math.round(box.left);
            if (!columns.has(left))
                columns.set(left, {name: '', width: Math.round(box.width), cells: []});
            const column = columns.get(left);
            const head = cell.closest('thead') !== null;
            if (cell.matches('th:not([scope="row"])') && (!column.name || (head && !column.head))) {
                column.name = `"${says(cell)}"`;
                column.head = head;
            }
            column.cells.push(cell);
        }
        const rtl = getComputedStyle(table).direction === 'rtl';
        read.set(table, [...columns].sort((a, b) => (rtl ? b[0] - a[0] : a[0] - b[0]))
            .map(([, c], i) => ({...c, name: c.name || `column ${i + 1}`})));
    }
    const probe = document.createElement('style');
    probe.textContent = 'th:not([colspan]), td:not([colspan]),'
        + ' th:not([colspan]) *:not(textarea), td:not([colspan]) *:not(textarea)'
        + ' { text-wrap: nowrap !important; flex-wrap: nowrap !important }';
    document.head.append(probe);
    for (const columns of read.values())
        for (const column of columns)
            column.wraps = column.cells[0].getBoundingClientRect().width > column.width + 1;
    probe.remove();
    const found = [];
    for (const [table, columns] of read) {
        const wraps = columns.filter(c => c.wraps);
        if (!wraps.length) continue;
        const short = table.scrollWidth - table.clientWidth;
        const top = Math.max(...columns.map(c => c.width));
        const widest = columns.find(c => c.width === top && c.wraps)
            ?? columns.find(c => c.width === top);
        found.push(`${at(table)} scrolls ${short}px sideways: `
            + wraps.map(c => `${c.name} wraps at ${c.width}px`).join(', ')
            + (widest.wraps ? '' : ` beside ${widest.name} at ${widest.width}px`)
            + ` — an identifier in <code> breaks inside its cell; a column fewer, or a`
            + ` shorter word in the widest, gives the rest the measure`);
    }
    return found;
}"""


# A version whose markup asserts a state the log replays over — `chosen` moved
# to another option, a card re-authored into a column the user dragged it
# out of. Replay resolves it in the user's favor, so what needs reporting is
# the author's intent going down silently. The static half can't say which
# attribute is a verb's state — that lives in each widget's applyAction, and a
# table here would be the second copy the registry exists to prevent — so the
# browser compares: projection reconciliation records the ids it wrote on the body
# (data-lf-replay-wrote), and this pass asks which of them the author also
# changed since the previous version, reading both files with the runtime's own
# shallowSigs. An authored change replay then overrode is a conflict; an
# unchanged id is the initial condition the log is supposed to outrank. For the
# message, each conflicting id is laid at the door of the widget whose replay
# wrote it — its nearest ancestor with an applyAction.
#
# The two files are handed in rather than fetched: which pair to compare is a
# question about the log and the URL, both of which the caller holds, and a read
# it makes is a read it can put a deadline on (see `served` in render_version).
REPLAY_OVERRIDES = """async ({ curHtml, prevHtml }) => {
    const ids = (document.body.dataset.lfReplayWrote ?? '').split(' ').filter(Boolean);
    if (!ids.length) return [];
    const { shallowSigs } = await import('/runtime/widget-api.js');
    const sigs = (html) => shallowSigs(
        new DOMParser().parseFromString(html, 'text/html').body);
    const cur = sigs(curHtml), prev = sigs(prevHtml);
    const groups = new Map();
    for (const id of ids) {
        if ((cur.get(id) ?? '') === (prev.get(id) ?? '')) continue;
        let widget = null;
        for (let a = document.getElementById(id); a; a = a.parentElement)
            if (a.applyAction) { widget = a; break; }
        const key = widget ? `<${widget.tagName.toLowerCase()} id=${widget.id}>` : `id=${id}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(id);
    }
    return [...groups].map(([who, asserted]) =>
        `${who} authors state the log replays over (${asserted.join(', ')}): `
        + `the user's decision stands — either carry it in the markup, or `
        + `rewrite the passage and declare restated`);
}"""


# Whether an applyAction is absolute, which is the premise both folds and every view
# built on them rest on and the one thing about a widget module no gate could see. A
# relative implementation — a card shifted one column along, a pick toggled rather than
# set — is invisible to every other reading here: it renders perfectly, and what it
# costs arrives later, in the poll that replays the sender's own action over the state
# that gesture already painted. The user drags a card once and watches it walk.
#
# So the page is asked rather than the code. Each standing action is applied a second
# time onto the state the page's own replay produced, and an absolute one has nothing
# to do. Re-running reconciliation would prove nothing — an already committed
# projection is clean whatever the widgets do — which is why this reaches past the
# runtime's checkpoint and calls the method.
#
# The standing state rather than the whole log, because that is the set the contract is
# for: the fold's own claim is that the last surviving action per coordinate *is* the state,
# so the page is already showing exactly these. It is also the set replay applied and
# did not skip — a retracted decision, a version's future action and a widget the
# markup dropped are all out of it — so nothing here re-applies what the page declined.
#
# The whole set at once and in the log's order, never one action measured on its own.
# An absolute applyAction states its own unit and says nothing about any other, so where
# two units share an ordered container the page is the sequence's result rather than any
# one action's: two cards dragged to the head of one column leave it holding the second
# above the first, and lifting the first back over the second is what replaying it alone
# is *supposed* to do. Read per action, that named lf-board relative and refused a page
# with nothing wrong with it — at the gate a handover cannot get past. Read across the
# batch, an absolute set lands exactly where it already was and a relative one walks.
#
# Two readings, because one is blind where the other sees. shallowSigs is the id-bearing
# markup state, which covers a moved card, a flipped attribute and a re-pointed pick;
# it looks away from text on purpose, and a `body` record is nothing but text, so the
# unit's declared facet is read beside it. A throw is a finding of its own rather than
# an exception out of the gate: whatever a second application was expected to do, it was
# not that. Each moved id is then laid at the door of the widget whose applyAction writes
# it — its nearest ancestor with the method, as a replayed override already is — since
# across a batch no single verb owns the difference.
RELATIVE_REPLAYS = """async () => {
    const { standingState, shallowSigs } = await import('/runtime/widget-api.js');
    const at = (el) => `<${el.localName}${el.id ? ' id=' + el.id : ''}>`;
    // A fold reads the registry, so a decided widget whose module never loaded is in it
    // and has no method to converge. That failure is reported on its own — the console,
    // the fail-soft box, the undefined element — and asking it this question would only
    // lay the same fault at a second door.
    const standing = standingState().filter((s) => s.widget?.applyAction);
    if (!standing.length) return [];
    const found = [];
    const before = shallowSigs(document.body);
    const stood = standing.map((s) => s.read());
    for (const s of standing) {
        const widget = s.widget;
        if (!widget?.applyAction) continue; // an earlier application replaced it
        try {
            widget.applyAction(s.action, s.detail);
        } catch (error) {
            found.push(`${at(widget)} applyAction(${s.action}) threw when the recorded `
                + `action was applied a second time: ${error?.message ?? error} — the `
                + `poll replays the sender's own action, so it has to arrive twice`);
        }
    }
    const now = shallowSigs(document.body);
    const verbs = new Map();
    for (const s of standing) {
        if (!s.widget) continue;
        const key = at(s.widget);
        if (!verbs.has(key)) verbs.set(key, new Set());
        verbs.get(key).add(s.action);
    }
    const groups = new Map();
    const note = (key, what) => {
        if (!groups.has(key)) groups.set(key, new Set());
        groups.get(key).add(what);
    };
    for (const id of new Set([...before.keys(), ...now.keys()])) {
        if (before.get(id) === now.get(id)) continue;
        let widget = null;
        for (let a = document.getElementById(id); a; a = a.parentElement)
            if (a.applyAction) { widget = a; break; }
        note(widget ? at(widget) : `id=${id}`, id);
    }
    // Only body records need the second reading: shallowSigs deliberately excludes
    // text. Key its wording by facet as well as unit, because a markup facet and a
    // body facet may both stand on the same unit and both move in this batch.
    standing.forEach((s, i) => {
        if (s.record !== 'body' || s.read() === stood[i] || !s.widget) return;
        note(at(s.widget), `the ${s.facet} state recorded on ${s.unit}`);
    });
    return [...found, ...[...groups].map(([who, moved]) => {
        const said = verbs.get(who);
        const named = said?.size ? `applyAction(${[...said].join(', ')})` : 'applyAction';
        return `${who} ${named} is relative — re-applying the standing log moved `
            + `${[...moved].join(', ')}. The poll replays every standing action over the `
            + `state they already produced, so state the whole value from the detail `
            + `rather than stepping from what the page shows`;
    })];
}"""


# What the page says, and whether each run of it is showing. Read once in each medium
# and compared by walk order: media change what is displayed, never the DOM, so the nth
# run on screen is the nth run on paper. What a page says has to survive being printed,
# and the ways it can fail to are all silent — a widget's control that is a statement as
# well as a thing to press (the pick mark, which took the only words naming the option a
# group carried), a rule of the page's own that hides its content in print. The whole
# page rather than the widgets in it, because a user's printout losing a paragraph is
# no better than losing a widget's word. Declared offers are excluded because paper has
# nothing to press; the runtime's own layer is excluded because it was never the
# document, and a widget rendered inside it (a reply's markup) is the panel's, not the
# page's.
PAPER_WORDS = """() => {
    const out = [];
    const at = el => { const named = el.closest('[id]');
                       return named ? `<${named.tagName.toLowerCase()} id=${named.id}>`
                                    : `<${el.tagName.toLowerCase()}>`; };
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
        const el = n.parentElement;
        if (!n.data.trim() || el.closest('.lf-chrome, [data-lf-offer]')) continue;
        out.push({ at: at(el), text: n.data.trim().slice(0, 40),
                   shown: el.checkVisibility() });
    }
    return out;
}"""


# Words the page draws in the same place as other words. A copy went out with a settled
# group's cards laid across the heading above them — the cards kept the collapsed
# padding, which is the room the group is laid out in — and the user saw it in the
# first second while every assertion passed: the words were all present, all shown, and
# all of a usable size. They were in the same place, and nothing was asking about place.
#
# Boxes rather than a hit test, which is the other way to ask: a press landing on the
# wrong element is a different fault with its own test, and the medium this has to hold
# up in is the copy, where there is nothing left to press. Text against text, because
# text over a background, a border, or a picture is how a page is built.
#
# What floats over the document on purpose is answered for, and that is one exemption
# rather than two. It reads as the runtime's, because for a long time the runtime owned
# every float there was; the sentence is about the float and not about the owner. A
# suggestion's controls hang out of the flow, level with the change they decide, and a
# sidenote hangs out of the flow level with the block it annotates — both in the right
# margin now, both pinned by what they belong to, so where a page stands them level the
# controls are drawn over the note and neither can move. Reporting that would refuse
# every page that writes a note beside a change, which is a composition the vocabulary
# is meant to have; so the float is exempt and the note is what it may cover. Where the
# same row docks back into the flow it is a resident again, and covering a word there is
# a fault this still reports.
#
# A pair where one element contains the other is skipped: a paragraph and the <em>
# inside it are one run of words that the flow lays out together, and their boxes
# overlap by construction. Two pixels of slack, since a line box carries its leading and
# adjacent blocks can round into each other by a hair. The runtime's layer is skipped
# too: it floats over the document on purpose, and where that costs the user a press
# it is the hit test that says so.
#
# The same fact one element over: an SVG <text> lays out its own lines, a tspan each,
# every one of them a sibling of the last. Where a chart's date axis names the month a
# week begins — the tick reading 1 over Dec — the two lines are offset by the dy the
# drawing asked for and each reports a line box carrying the font's own leading, which
# is a couple of pixels taller than that step. So the pair overlapped by construction on
# a drawing where no glyph comes near another. A wrapped paragraph is the identical
# shape and never reported, because its lines are boxes of one text node and the
# same-element skip takes them; two lines of one label are two nodes only because SVG
# spells a line break as an element. The <text> is the label, so a pair inside one of
# them is one word of the page's, and this asks about two.
#
# The layer is in two places and the float rule reaches both, which is why only one of
# them is named. The line counting a passage's comments lives inside the page's own
# elements by design — it is what a screen reader hears where a painted mark says
# nothing — and it is clipped to nothing on screen. checkVisibility answers for display,
# visibility and opacity and knows nothing of clip-path, so that line read as drawn, and
# its text lays out past the 1px box holding it: an anchor on a container put "1 comment"
# across the paragraph below the widget and failed the gate on a page with nothing wrong
# with it. It wore a name in this selector for a while, next to the container's, and the
# name went the day the rule below could answer for it — the line is a control the
# runtime hangs absolutely, which is the whole of what `floating` asks. Two skips over
# one element is a guarantee kept twice, and the weaker of them is the one that has to be
# remembered when the next float is written.
#
# checkVisibility knows nothing of content-visibility either, which is what a collapse
# wears: an inactive tab's panel and a settled group's cards are hidden="until-found" so
# that find-in-page still reaches inside, and the text in one reports the boxes it last
# laid out in — every sibling's at the same place. So a page with a collapsed group on it
# failed about half the runs and passed the rest, which is the worst way for a gate to be
# wrong: the page that goes out is whichever one the coin was kind to. A collapse is asked
# for, and words nobody can see are not drawn over anything, so [hidden] is held out here
# the way the size check holds it out. The coin comes down the same side every time on a
# group that has been opened and closed, which is where the test pins it.
COVERED_WORDS = """() => {
    const runs = [];
    const at = el => { const named = el.closest('[id]');
                       return named ? `<${named.tagName.toLowerCase()} id=${named.id}>`
                                    : `<${el.tagName.toLowerCase()}>`; };
    // Chrome a widget hangs out of the flow, which is the same exemption the runtime's
    // own layer has above and for the same reason. Read off the marker `offer` writes
    // and the position the browser computed, so it holds for a control any widget hangs
    // and stops holding the moment that control docks back into the flow — which is what
    // a suggestion's row does when it finds no room, and where covering a word would be
    // a fault again.
    //
    // Every marked ancestor, not the nearest: `offer` builds a row of presses out of
    // presses, so a suggestion's ✓ Accept is a marked button inside a marked row, and the
    // one that hangs in the margin is the outer of the two. Asking `closest` gets the
    // button, which is in its row's flow and static, and the exemption reads as absent on
    // exactly the control it was written for.
    //
    // The two values that take a box out of the flow, named rather than everything that
    // isn't static: a relative or sticky box keeps its place in the flow and is painted
    // offset from it, so it is a resident that has moved rather than chrome hanging over
    // the page, and exempting it would retire this check for any control that nudges
    // itself a pixel. PAST_THE_COLUMN asks the same question next door and asks it this
    // way.
    const outOfFlow = (s) => s.position === 'absolute' || s.position === 'fixed';
    const floating = (el) => {
        for (let a = el.closest('[data-lf-offer]'); a; a = a.parentElement?.closest('[data-lf-offer]'))
            if (outOfFlow(getComputedStyle(a))) return true;
        return false;
    };
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
        const el = n.parentElement;
        if (!n.data.trim() || el.closest('.lf-chrome, .lf-quiet, [hidden]')) continue;
        if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) continue;
        if (floating(el)) continue;
        const range = document.createRange();
        range.selectNodeContents(n);
        // The label these words are a line of, where an SVG <text> is what draws them.
        // Read here rather than per pair: `closest` walks the tree, and the loop below
        // asks about every pair of runs on the page.
        const label = el.closest('text');
        for (const box of range.getClientRects())
            if (box.width > 1 && box.height > 1)
                runs.push({ el, label, box, text: n.data.trim().slice(0, 40) });
    }
    const found = [];
    for (let i = 0; i < runs.length; i++) for (let j = i + 1; j < runs.length; j++) {
        const a = runs[i], b = runs[j];
        if (a.el === b.el || a.el.contains(b.el) || b.el.contains(a.el)) continue;
        if (a.label && a.label === b.label) continue;
        const across = Math.min(a.box.right, b.box.right) - Math.max(a.box.left, b.box.left);
        const down = Math.min(a.box.bottom, b.box.bottom) - Math.max(a.box.top, b.box.top);
        if (across <= 2 || down <= 2) continue;
        found.push(`${at(a.el)} draws ${JSON.stringify(a.text)} in the same place as `
                   + `${at(b.el)}'s ${JSON.stringify(b.text)}`);
    }
    return [...new Set(found)];
}"""


# Which trees are the page, for the two readings below that answer for what a widget
# renders rather than for what it declares. Every open root, found by walking rather than
# read off the registry's x-shadow list: a root a module attached without declaring one
# still holds words and code the reader has to read, and a reading that asked the
# registry would look away from exactly the tree nobody vouched for. Written once,
# because it is one claim about the page and two copies of it are two things to keep
# level.
OPEN_ROOTS = """
    const roots = (root) => [root, ...[...root.querySelectorAll('*')]
        .filter(el => el.shadowRoot).flatMap(el => roots(el.shadowRoot))];"""


# Code that came out the colour of the code around it. Colouring takes two halves that
# meet nowhere a static lint can reach: the runtime writes data-lf-syn in the browser,
# and the theme answers it with a var() the browser resolves. Either half can stop
# working with nothing said — the tokenizer failing throws, and the console error is
# already a finding here, but a stylesheet that no longer answers a role, or answers it
# with an ink too near the paper, is silent. What reaches the user is a page of code in
# one flat colour, which is what they report as the highlighting being gone; it was
# reported that way, on a comment that was 3.3:1 against the block it sat on.
#
# So both halves are asked of the drawn result rather than of the declarations behind it.
# A palette can be read out of the stylesheet; what a role came out as cannot, because a
# project overlays its own theme over this one and the browser is the only thing that
# knows which declaration won.
#
# Once per role and surface rather than once per span: the fault belongs to the role, not
# to the hundredth span wearing it, and a role reads differently on a diff's del tint than
# on the plain block, so the pair is what a reading answers for. A page of code costs a
# couple of dozen of them rather than one per token — measured at under 10ms across the
# examples. The line is per role, since the palette is where the fix goes and a role
# failing on two tints is one thing to change.
#
# What a colour is comes back from the browser painting it, not from a parse of how it
# wrote it down — getComputedStyle serializes a hex as rgb() in 0–255 and a color-mix as
# color(srgb …) in 0–1, and a probe reading one as the other reports a ratio against a
# colour nothing on the page is. Painting the backgrounds in order composites the
# translucent ones the way the page does, over the white the browser paints under
# everything, so a tint over a tint is the colour the reader actually has behind the
# glyphs. A marked passage is not among them: the highlight registry styles glyphs and
# not boxes, so a mark is no element's background, and it is the user's own paint over a
# page that had to be legible before they put it there.
#
# 4.5:1 is WCAG AA for body text, and body text is the threshold that applies — code is
# 13px. Axe runs over this corpus too and passes it, which is not the same guarantee:
# asked for colour-contrast alone on the example carrying the beige comment, it returned
# 44 passing elements, no violation, and not one of the spans among them.
#
# Which shadow roots it crosses into is OPEN_ROOTS' answer (the section note above says
# why it crosses at all), which is the choice everything else here makes — colour is
# asked of what the browser painted, so where it painted is too, and a root a widget
# attached without declaring one still holds code the reader has to read.
UNREAD_SYNTAX = (
    """() => {"""
    + OPEN_ROOTS
    + """
    const cx = document.createElement('canvas').getContext('2d');
    const paint = (...layers) => {
        cx.clearRect(0, 0, 1, 1);
        for (const c of ['white', ...layers]) { cx.fillStyle = c; cx.fillRect(0, 0, 1, 1); }
        return [...cx.getImageData(0, 0, 1, 1).data.slice(0, 3)];
    };
    const chan = (v) => (v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    const lum = ([r, g, b]) => 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b);
    const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((p, q) => q - p);
                              return (hi + 0.05) / (lo + 0.05); };
    const up = (el) => el.parentElement ?? el.getRootNode().host ?? null;
    const under = (el) => { const layers = [];
                            for (let a = el; a; a = up(a))
                                layers.unshift(getComputedStyle(a).backgroundColor);
                            return layers; };
    const seen = new Set(), found = new Map();
    for (const span of roots(document)
                       .flatMap(r => [...r.querySelectorAll('[data-lf-syn]')])) {
        const role = span.dataset.lfSyn;
        if (found.has(role) || !span.textContent.trim()) continue;
        if (!span.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
            continue;
        const layers = under(span);
        const on = paint(...layers);
        if (seen.has(`${role} on ${on}`)) continue;
        seen.add(`${role} on ${on}`);
        const ink = paint(...layers, getComputedStyle(span).color);
        const plain = paint(...layers, getComputedStyle(up(span)).color);
        const read = ratio(ink, on);
        if (String(ink) === String(plain))
            found.set(role, `code marked ${role} is the ink of the code around it — `
                          + `nothing answered [data-lf-syn="${role}"]`);
        else if (read < 4.5)
            found.set(role, `code marked ${role} reads at ${read.toFixed(1)}:1 `
                          + `against the block it is set on`);
    }
    return [...found.values()];
}"""
)


# Words a declaration promised and the page never got. Every other reading here works
# from what the browser drew, and that is exactly what cannot see this one: a word that
# never arrived looks the same as an attribute with nothing to say, and a fact the page
# paints in colour alone is a fact no measurement of a drawn page has ever read. The
# registry is what knows the difference — x-says names the attributes whose values are
# words at the element's edge, x-paints the ones drawn as paint and spoken to a reader
# listening (renderQuiet) — so the declaration is what this asks against.
#
# Both passes run once at the upgrade, before an async widget's own render lands, so a
# module that rebuilds its body from a settle() promise takes the words out with it and
# nothing on the page says so. renderQuiet re-runs on each replay and renderSaid never
# does, which decides how long each stays gone rather than whether it goes.
#
# It reads every open root (OPEN_ROOTS) where both word passes stop at the boundary on
# purpose: which widgets the page holds is the document's question, and settling a
# staged widget's nesting in a sweep would be writing that contract where nobody would
# look for it (the layer's CLAUDE.md). So a staged element keeps its declarations and
# gets neither pass, which is exactly where a promised word reaches nobody in silence —
# reported here, to the module's author, at handover.
#
# Both halves ask the *rendered* page rather than the markup, and a shadow host is why:
# an element that stages a tree keeps its light DOM in the document and out of every box,
# so both passes find the host, write there, and leave `textContent` and `querySelector`
# reporting words the reader will never get. Each half gets to the rendered page its own
# way, because they read different things. Words are `says()`, the layer's one answer to
# what an element says rather than a second reading spelled here — asked of the host's
# root where there is one, since the walk behind it substitutes a declared root for a
# *child* and never for the element it was handed. The quiet word is in no such reading,
# wearing the .lf-ui that `says` skips on purpose, so what is asked of it is its box: a
# span clipped to a pixel still has one wherever it renders, and none at all where it
# doesn't. Which is only a question worth putting where the element renders at all — a
# collapsed card, a tab nobody opened and a shut comment panel all lay out nothing, and
# their rects report the ancestor rather than the widget. That is the *second* failure
# here, a word the widget wrote and then hid. The first one, a word it never wrote, is a
# fault wherever the element stands, since a tab the reader has not opened is a tab they
# can open. Splitting them that way is what retired the [hidden] exemption this carried:
# `hidden` and `hidden="until-found"` are two of the ways an element stops rendering, and
# asking whether it renders covers both and the panel besides.
SILENT_WORDS = (
    """(widgets) => import('/runtime/widget-api.js').then(leaf => {"""
    + OPEN_ROOTS
    + """
    const found = [];
    const all = roots(document);
    const at = el => `<${el.localName}${el.id ? ' id=' + el.id : ''}>`;
    const every = tag => all.flatMap(r => [...r.querySelectorAll(tag)]);
    for (const [tag, entry] of Object.entries(widgets)) {
        for (const attr of Object.keys(entry['x-says'] ?? {}))
            for (const el of every(tag)) {
                const value = el.getAttribute(attr);
                if (value !== null && !leaf.says(el.shadowRoot ?? el).includes(value))
                    found.push(`${at(el)} declares ${attr} as x-says and never says `
                               + `"${value}"`);
            }
        // The word itself is renderQuiet's to derive, and this asks only that the
        // element carries one: a widget painting a fact and saying nothing is the
        // whole of the failure, and all a second copy of the derivation would add is
        // a second place to change it.
        for (const attr of entry['x-paints'] ?? [])
            for (const el of every(tag)) {
                if (!el.hasAttribute(attr)) continue;
                const quiet = el.querySelector(':scope > .lf-quiet');
                // A missing word is the fault, and it is the fault wherever the
                // element stands: a tab the reader has not opened is still a tab
                // they can open. What the box is asked for is the second failure,
                // a word the widget wrote and then hid, and that question can only
                // be put to an element that is being laid out — a message in a shut
                // panel lays out nothing, so its rects report the panel's state and
                // would be read as the widget's.
                if (quiet && (quiet.getClientRects().length || !el.checkVisibility()))
                    continue;
                found.push(`${at(el)} paints ${attr}="${el.getAttribute(attr)}" `
                           + `and says nothing a reader listening can hear`);
            }
    }
    return found;
})"""
)


# Attributes standing on a widget that its entry never declared. The schema is the
# whole of the author's namespace — `additionalProperties: false` on every tag — and
# the static lint holds a version file to it. What no reading of a file can see is the
# other writer: a module, which upgrades the element and may leave anything it likes on
# it. So a module writes in that namespace only where the registry declares the
# attribute as a verb's record form (`chosen`, `status`), which is what makes the write
# a statement the log's fold, the state gate and the record-lag report can all read.
# Everything else it needs to mark goes where the module's own words go — the chrome it
# built, in the platform's vocabulary (aria-*, role, hidden, tabindex) or under data-*,
# which is the layer's and a widget's alike.
#
# lf-options had two of the other kind, and both were quiet. `answered` recorded a verb
# only a thread can post, and a thread's markup is frozen in the log, so no version
# could ever have honored a record of it; `open` recorded which way this tab last left
# a disclosure, which no version carries at all. Neither reached a consumer, and the
# one reader that did see them read them wrong: shallowSigs excludes exactly the
# attributes no version can assert, and its exclusion list is the runtime's own paint —
# so a widget writing beside it is counted as state the author wrote, in the reading
# `version check --render` uses to decide whether a version overrules the user.
#
# Deduped and reported per tag and attribute, because one mistake is on every instance.
UNDECLARED_ATTRS = (
    """(widgets) => {"""
    + OPEN_ROOTS
    + """
    // What a module may write without declaring: the platform's own vocabulary for
    // what a control is and how it behaves, and the data-* namespace the runtime and
    // the widgets both paint in. `class` and `style` are the same kind of fact — a
    // look, not a state a version could carry.
    const painted = /^(?:data-|aria-)/;
    const platform = new Set(['role', 'class', 'style', 'hidden', 'tabindex']);
    const all = roots(document);
    const found = [];
    for (const [tag, entry] of Object.entries(widgets)) {
        if (!entry.properties) continue;
        for (const root of all)
            for (const el of root.querySelectorAll(tag))
                for (const a of el.attributes)
                    if (!painted.test(a.name) && !platform.has(a.name)
                        && !(a.name in entry.properties))
                        found.push({tag, id: el.id, attr: a.name});
    }
    return found;
}"""
)


# The two sides of the settlement contract, compared on the rendered page. The mark —
# data-lf-state on a holder — is the layer's paint of a logged decision (projection
# reconciliation in leaf.js), and the anchor pass retires slots by it, so whatever it
# says, the page's
# reading obeys. What can still go wrong is a family's, and both failures render
# perfectly: a module that writes the mark where the log decided nothing silences words
# the reader can still see and select, and a settled slot can show its words anyway — a
# later layer's rule outranking the default hide, a module re-showing what it folded —
# leaving the reader selecting words no comment can anchor to, with the refusal
# arriving later, at `leaf comment`, nowhere near the mistake. So the expected outcome
# comes from the file's reading (`decisions`, folded over this version's log), never
# from the page, and the page answers only for what it shows.
#
# The words walk is textNodesUnder with an accepts of its own, on purpose: the anchor
# pass's default accepts already skips a marked holder's slots, so asking it whether
# the retired words are gone would let the mark answer for the screen. What it keeps
# of that reading is the boundary — declared shadow roots, the same trees replay's
# elementById marks across, which is why the holders are found through OPEN_ROOTS
# too — and the chrome test (inUi): a declared label is the page's words, so a
# settled slot still showing one is still showing words. The visibility guards are
# COVERED_WORDS', for its reasons: [hidden] holds until-found content whose boxes
# report as last laid out, and visibility and opacity hide with layout intact. One
# scheme, on the trapped-margin reading's premise — the palettes carry no geometry
# between them — with the fold a replayed decision plays awaited first, finite
# animations only, because a slot mid-fold still paints words it has already retired.
RETIRED_SLOTS = (
    """async (holders) => {"""
    + OPEN_ROOTS
    + """
    const leaf = await import('/runtime/widget-api.js');
    const all = roots(document);
    const find = (id) => {
        for (const r of all) {
            const el = r.getElementById(id);
            if (el) return el;
        }
        return null;
    };
    const found = [];
    const showing = (slot) => {
        for (const seg of leaf.textNodesUnder(slot, (n) => !leaf.inUi(n))) {
            const n = seg.node, el = n.parentElement;
            if (!n.data.trim()) continue;
            if (el.closest('.lf-chrome, .lf-mark-note, .lf-quiet, [hidden]')) continue;
            if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
                continue;
            const range = document.createRange();
            range.selectNodeContents(n);
            for (const box of range.getClientRects())
                if (box.width > 1 && box.height > 1) return n.data.trim().slice(0, 40);
        }
        return null;
    };
    for (const h of holders) {
        const el = find(h.id);
        if (!el || leaf.inChrome(el) || leaf.quoted(el)) continue;
        await Promise.allSettled(
            el.getAnimations({subtree: true})
                .filter((a) => a.effect?.getTiming().iterations !== Infinity)
                .map((a) => a.finished));
        const mark = el.getAttribute('data-lf-state');
        const at = `<${h.tag} id='${h.id}'>`;
        if (mark !== (h.outcome ?? null)) {
            const log = h.outcome ? '`' + h.outcome + '`' : 'no decision';
            found.push(`${at} wears data-lf-state=${JSON.stringify(mark)} where the `
                + `log records ${log} — the mark is the layer's paint of a logged `
                + `decision, and the anchor pass retires slots by it, so a module may `
                + `say only what the log decided`);
            continue;
        }
        for (const tag of h.slots)
            for (const root of [el, ...(el.shadowRoot ? [el.shadowRoot] : [])])
                for (const slot of root.querySelectorAll(`:scope > ${tag}`)) {
                    const words = showing(slot);
                    if (words === null) continue;
                    found.push(`${at} settled \\`${h.outcome}\\` and its <${tag}> still `
                        + `shows ${JSON.stringify(words)} — those words have left the `
                        + `page's reading, so the reader can select what no comment can `
                        + `anchor to; the layer hides a retired slot by default, so `
                        + `something in this family is showing it anyway`);
                }
    }
    return found;
}"""
)


# A box that draws an inset and shows a different one. A child's outer margin normally
# collapses through its parent and is spent between blocks; where the parent draws
# something at that edge, or holds a formatting context of its own, it cannot get out and
# is painted as the parent's inset instead. So the number a stylesheet states is not the
# number a reader sees, and which of the two they get depends on what the author wrote
# inside: a card ending in a sentence showed its 16px, the same card ending in a paragraph
# showed 29. theme.css states the trim and a box opts in where it draws the frame
# (`--lf-frame`); this is what says when one hasn't.
#
# It is a reading of the rendered page because nothing else can be. The trim is a style
# query, the frame is a declaration in whichever layer drew the box, and a project overlays
# its own theme over leaf's — so which rule won, and whether the child that ended up at the
# edge is the one the stylesheet's author had in mind, are facts only the browser holds. A
# lint over the CSS would be reading the declarations and not the result, which is the same
# mistake the reserved-width lint made before the press sweep replaced it.
#
# Two exclusions, both about what a margin means where it stands. A flex or grid container
# collapses no margin anywhere, so a margin on an item at its edge is a placement rather
# than room that could not get out — the switch under a screenshot pair carries 3px of
# exactly that, the UA's own on a checkbox. And an edge whose box is a generated one (a
# pseudo-element, an `x-says` word, an injected control) is the layer's own paint, stated
# in the same rule as the frame: what the trim looks for is the first and last block the
# page itself put there, so this looks for the same, and a card's absolutely-positioned
# pick mark is not the thing under its last paragraph.
#
# Deduped per tag and edge, because one mistake is on every instance of that widget.
TRAPPED_MARGINS = (
    """async () => {
    // Which document each box is in, imported rather than restated, for the same
    // reason UNMARKABLE_ITEMS imports its two: the runtime's layer holds shadow roots
    // of its own, and a `closest` written out here stops at the first of them and
    // calls what it finds the page's.
    const { inChrome } = await import('/runtime/widget-api.js');"""
    + OPEN_ROOTS
    + """
    const px = (v) => parseFloat(v) || 0;
    // The platform's own answer to "does a child's margin reach my edge, and can it get
    // past it": a box that establishes a formatting context keeps every margin inside.
    const holds = (s) =>
        s.display === 'flow-root' || s.display === 'inline-block'
        || s.display.startsWith('table') || s.overflow !== 'visible'
        || s.float !== 'none' || s.position === 'absolute' || s.position === 'fixed'
        || s.contain.includes('layout') || s.contain.includes('paint');
    // The page's own boxes in this box's flow, in order. Out-of-flow children are not in
    // it, a floated one spends its margins rather than reserving them, a generated one is
    // the layer's paint, and a boxless child hands its own children to the flow.
    const flow = (el) => {
        const out = [];
        for (const node of el.childNodes) {
            if (node.nodeType === 3) { if (node.data.trim()) out.push({}); continue; }
            if (node.nodeType !== 1) continue;
            const s = getComputedStyle(node);
            if (s.display === 'none') continue;
            if (s.position === 'absolute' || s.position === 'fixed') continue;
            if (s.float !== 'none') continue;
            if (s.display === 'contents') { out.push(...flow(node)); continue; }
            if (node.matches('.lf-ui, [data-lf-gen]')) { out.push({}); continue; }
            out.push({node, s});
        }
        return out;
    };
    const found = [];
    for (const root of roots(document))
        for (const el of root.querySelectorAll('*')) {
            const s = getComputedStyle(el);
            if (s.display === 'none' || s.display === 'contents') continue;
            // An inline box lays no vertical margin out, so it traps nothing.
            if (s.display.startsWith('inline') && s.display !== 'inline-block') continue;
            if (s.display.includes('flex') || s.display.includes('grid')) continue;
            const kids = flow(el);
            if (!kids.length) continue;
            for (const [edge, side, end, kid, pseudo] of [
                ['above', 'Top', 'Start', kids[0], '::before'],
                ['below', 'Bottom', 'End', kids[kids.length - 1], '::after'],
            ]) {
                if (!kid.node) continue;
                if (getComputedStyle(el, pseudo).content !== 'none') continue;
                const drawn = px(s['padding' + side]) + px(s['border' + side + 'Width']);
                if (!drawn && !holds(s)) continue;
                const margin = px(kid.s['marginBlock' + end]);
                if (margin > 0.5)
                    found.push({
                        tag: el.tagName.toLowerCase(), id: el.id || null,
                        cls: el.classList[0] || null, edge, drawn, margin,
                        child: kid.node.tagName.toLowerCase(),
                        chrome: inChrome(el),
                    });
            }
        }
    return found;
}"""
)


# How long the render gate waits on the server for one of the documents it reads.
# The same patience playwright gives `wait_for_function` above it, and stated here
# because it is the number that turns a wedged server into a sentence.
SERVED_TIMEOUT_MS = 30_000


# ---------- export: the page as one file ----------

# What a standalone copy drops. Scripts go because there is no server behind a file
# and nothing left for them to reach; the runtime's own layer goes with them, since a
# comment box that swallows what you type and a banner claiming someone is listening
# are worse than no chrome at all — a copy that lies about being a live page. What stays
# is everything the widgets built, and the controls they injected where the browser is
# what works them: a `lf-shot` flips on a checkbox with no script running. A press a handler
# answered leaves the words it stated and takes the rest of itself with it, below.
#
# `lf-copy` is the medium, declared the way `@media print` is and read the same way —
# by the theme, per widget. A widget whose control needed a handler puts the affordance
# behind a guard this class fails, so a copy gets the page its markup describes; one
# whose control the browser owns has no guard and keeps working. That is why no widget
# is named here: this marks the medium, and the widgets answer for themselves.
BAKE = """() => {
    document.documentElement.classList.add('lf-copy');
    // A work line is runtime chrome even where its declared seat is in the page rather
    // than under .lf-chrome. Remove it from the document and every open shadow root
    // before those roots are serialized below: a file has no agent behind the claim,
    // so preserving the rendered sentence would turn provisional news into a lie.
    const roots = [document];
    for (const root of roots)
        for (const element of root.querySelectorAll('*'))
            if (element.shadowRoot) roots.push(element.shadowRoot);
    for (const root of roots)
        root.querySelectorAll('.lf-work-line').forEach(el => el.remove());
    document.querySelectorAll('script, .lf-chrome').forEach(el => el.remove());
    // A measurement of this window is not a fact about the reader's. The live page
    // measures its own box and states the numbers inline on the root — the room a wide
    // widget may take (syncLayout), the width the margin strips are sized against
    // (stateStrip), the width each edge stands at, the rail a suggestion's controls
    // hang in — and an inline value outranks every rule a stylesheet could write, so a
    // copy carrying one holds whatever width the exporter's headless window happened to
    // have, on a file whose whole point is being opened somewhere else. Each rule that
    // reads one falls back to the viewport, which is honest in a copy: no panel takes a
    // strip from a file, and no session grows one. Taken off the way the chrome above
    // is, rather than guarded against in the theme, because the stale number is the
    // thing that is wrong here and a rule written around it would leave it there to be
    // read by the next thing that asks.
    //
    // Named, and the names are the point. What goes is a measurement whose subject
    // this file no longer has: the panel and the tray are removed with the chrome
    // above, and the room and the available width are read off a window that is not
    // the reader's. A copy drops what it hasn't got.
    //
    // It keeps what it still has, which is why `--rail` is not on this list and must
    // not be added to it. The rail is the width of the margin a suggestion's controls
    // stand in, and a decided change keeps that control — the record of what was
    // decided is the whole reason the margin was reserved. Cleared, the copy reads its
    // room off the viewport, knows nothing of the row still sitting in the margin, and
    // spends the surplus on the free side: the exported board stood 35px outside the
    // page's box at a laptop's width and 47px at a narrow one, off the left, where
    // overflow scrolls nothing and the columns are not cut off with a way to reach
    // them but simply gone. `test_a_copy_keeps_the_rail_a_decided_change_left` is
    // that, and it is what a sweep of every inline custom property on the root ran
    // into: read as a stale number, the rail is the one that is not.
    for (const stale of ['--lf-room', '--lf-avail', '--lf-panel-w', '--lf-tray-w'])
        document.documentElement.style.removeProperty(stale);
    // The tab icon is the third seat of the banner's status (paintTab), and a file has
    // no session behind it — a copy keeping the tone it was exported under would claim
    // one, which is the same lie the chrome above is dropped for. So it drops back to
    // the mark as authored, which the runtime left here for exactly this.
    const icon = document.querySelector('link[rel="icon"][data-lf-rest]');
    if (icon) {
        icon.href = icon.dataset.lfRest;
        icon.removeAttribute('data-lf-rest');
    }
    // hidden="until-found" is the page saying "collapsed, but the reader can still
    // get here" — a tab's inactive panel, a settled group's cards. In a copy the
    // control that would get them there is inert, so the attribute is a promise
    // nothing can keep, and it takes the collapsed element's layout down with it:
    // the theme zeroes a hidden card's padding, which is the room its chips are
    // positioned into. Dropping it opens the element on the terms it was authored
    // with, which is the layout the theme's live-page guard was withholding anyway.
    document.querySelectorAll('[hidden="until-found"]')
        .forEach(el => el.removeAttribute('hidden'));
    // A press a widget injected is a tab stop wearing an interactive role (offer), and
    // both are promises a handler kept. The handlers left with the scripts above, so a
    // copy that carried them offered a press nothing can take — and the first Tab into an
    // exported decision page landed on one. It was a `choose` group's pick mark, which
    // drew the keyboard address for a key that answers nothing, into a row holding no
    // column for it: the 30px an option reserves is live-page-only, so the digit came
    // down 8px over the option's own first word.
    //
    // So the control goes and its word stays, which is the bargain paper struck first
    // (the runtime's @media print rule, on these same two markers). A mark reading
    // "chosen" is the page stating which option won, and it stays with the role and the
    // tab stop taken off it; "choose one" is an invitation, and it leaves with the grips,
    // the pills and the pencils. Where the words a removal takes with it are the page's —
    // a settled group's disclosure names its chosen card, a tab's button names its panel —
    // the copy has those open underneath saying it themselves, which is why paper drops
    // the same two.
    //
    // A copy parts from paper on one thing: it is still a document the browser runs, so a
    // control the browser drives keeps working, and lf-shot flips its frames on a checkbox in
    // a file with no script behind it. The tab stop is what tells the two apart, being the
    // runtime's own reading of a press it made (ASK_CONTROL): a checkbox, a label and a §
    // link never had one, and lf-shot's checkbox keeps the role that says what it is.
    //
    // Asked of the marker rather than of the role, because `offer`'s role="button" is not
    // what a press ends up wearing: a widget with an ARIA pattern to keep writes its own
    // over it, so every press in lf-tabs' strip says role="tab", and naming that second
    // role would have left the next widget's. The author's roles are untouched, being on
    // the author's elements: a board's columns stay a list of cards to a screen reader.
    //
    // The box a press hung in goes with it. A suggestion's control row is nothing but its
    // two controls, and left standing it still claims the rail the page reserves for it
    // (--rail) — a margin held open for controls that are no longer there. Asked of what
    // each removal empties rather than of an empty box, since a widget's own empty box is
    // a real thing: that row hangs off an anchor span which takes no space and says
    // nothing, and `anchor(top)` is measured from it.
    // A reaction is the reader's mark on the page, and a copy keeps a mark the way it
    // keeps a chosen option's word: the glyph stays in the margin with its press taken
    // off — the tab stop, the role, the marker, and the title that promised a press —
    // and the wash on the words, which is a highlight-registry entry no serialization
    // carries, is written into the words as a <mark> for this copy alone (the theme's
    // html.lf-copy rule paints it). Each painted range lies within one text node
    // (anchors.js paints a range per segment), which is what lets surroundContents
    // wrap it; the ranges are live, so an earlier wrap moves a later one's offsets.
    for (const mark of document.querySelectorAll('.lf-react-mark')) {
        for (const attr of ['tabindex', 'role', 'data-lf-offer', 'title']) mark.removeAttribute(attr);
        mark.setAttribute('aria-label', mark.dataset.token);
    }
    // Two reactions on overlapping words leave the second range straddling the first's
    // mark, which no element can wrap; that range keeps its glyph and loses its wash.
    for (const range of CSS.highlights.get('lf-react') ?? []) {
        const wrap = document.createElement('mark');
        wrap.className = 'lf-react';
        try { range.surroundContents(wrap); } catch { /* straddles a mark */ }
    }
    for (const control of
            document.querySelectorAll('[data-lf-offer][tabindex]:not([data-lf-said])')) {
        let dead = control, box = dead.parentElement?.closest('[data-lf-offer]');
        dead.remove();
        while (box && !box.firstChild) {
            dead = box;
            box = dead.parentElement?.closest('[data-lf-offer]');
            dead.remove();
        }
    }
    document.querySelectorAll('[data-lf-offer][tabindex]').forEach(el => {
        el.removeAttribute('role');
        el.removeAttribute('tabindex');
        // The states and relations rode the role: pressed="true" on a plain span is
        // ARIA nothing may interpret (axe calls it critical), where the label is the
        // word's accessible copy and stands on its own.
        for (const attr of [...el.attributes])
            if (attr.name.startsWith('aria-') &&
                !['aria-label', 'aria-hidden'].includes(attr.name))
                el.removeAttribute(attr.name);
    });
    // What the runtime painted, as against what a widget built, goes the same way. An
    // element-anchored comment's mark is a class the kept stylesheet answers with a
    // ring and a pointer hand, and the panel that hand promised left with the chrome —
    // while a text-anchored mark, painted through the highlight registry by script, is
    // already gone. One fact — a comment is anchored here — leaves the copy whole.
    document.querySelectorAll('.lf-mark-el')
        .forEach(el => el.classList.remove('lf-mark-el'));
    // A tab stop still standing on a widget element is module paint — the registry's
    // schemas admit no authored tabindex on one — promising focus to chrome whose
    // handler left with the scripts: a tabs panel's roving stop, an ask-lend. Asked
    // of the tag's dash, the platform's own mark of a custom element, so no widget
    // is named and the author's own elements are untouched. Scroll stops go with
    // the rest and come back below, where every scrollable box is answered at once.
    document.querySelectorAll('[tabindex]').forEach(el => {
        if (el.tagName.includes('-')) el.removeAttribute('tabindex');
    });
    // Then what the removals uncovered: a box that scrolls whose way in was the
    // chrome just taken out — a board whose grips were its only focusable content,
    // a diagram whose stop the sweep above stripped — has no keyboard into it, and
    // scrolling needs no handler (the lf-shot bargain). The live page's one grantor
    // is reachScrollers; its predicate is restated here because the runtime's
    // module scope left with the scripts, and this pass runs where the removals
    // have already settled what remains. Of its two products only the stop is
    // restated: the hold it marks rides into the copy as the attribute and the
    // theme rule reading it, and nothing removed above turns a box into a scroller.
    for (const root of roots)
        for (const el of root.querySelectorAll('*')) {
            if (el.tabIndex >= 0) continue;
            const style = getComputedStyle(el);
            if (!/^(auto|scroll)$/.test(style.overflowX) &&
                !/^(auto|scroll)$/.test(style.overflowY))
                continue;
            if (!el.querySelector('a[href], button, input, select, textarea, ' +
                                  '[tabindex]:not([tabindex="-1"])'))
                el.tabIndex = 0;
        }
    // getHTML and not outerHTML: a widget that renders the page's words into a shadow
    // root (x-shadow) has them in no element's outerHTML, so a copy taken that way
    // arrives with an empty element where a diff's lines were — silently, since the
    // element and its ids are all still there. Asking for serializable roots writes each
    // one as a declarative <template shadowrootmode>, which the browser rebuilds on open
    // with no script, the same bargain every other widget's chrome makes here.
    //
    // It is innerHTML's counterpart, though, so the root's own tag is not in what it
    // returns and has to be written back: <html> carries the lang the document is read
    // in and the lf-copy class the theme reads its medium from, and a copy missing them
    // opens as a live page whose affordances press nothing. Rebuilt from the attributes
    // rather than sliced off outerHTML's opening tag, because an attribute value may
    // hold the very > that slicing would stop at.
    const root = document.documentElement;
    const attrs = [...root.attributes]
        .map(a => ` ${a.name}="${a.value.replaceAll('&', '&amp;').replaceAll('"', '&quot;')}"`)
        .join('');
    return `<html${attrs}>${root.getHTML({serializableShadowRoots: true})}</html>`;
}"""
