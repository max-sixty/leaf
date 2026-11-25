"""Leaf's sheets set their words in the theme's type (tokens.css): every font size names
one of its tokens, and the interface names one of its fonts (`--lf-font-*`), with at most
a weight and the mono family beside it."""

import re

import tinycss2
from interact_support import shipped_sheets

from leaf.schema import ASSETS
from leaf.state import PLUGIN_ROOT
from leaf.structure import AUTHORED_CLASSES

# The floor a finger's platform asks under typed words: iOS Safari zooms the page onto a
# field set smaller than 16px. Leaf's own fields read it as `--lf-entry-floor`
# (surfaces.css), and a package's box that shows words before opening a field on them
# writes the number under a coarse pointer, so the two sizes agree.
FLOORS = {"max(var(--lf-entry-floor), 1em)", "max(16px, 1em)"}

# Declarations that make a face, and what a rule of the interface may write for each
# beside the font it names or inherits: a weight, the mono family, a box that holds no
# words, and the fonts' shared leading. A title is a font at 600 and a path a font in
# mono, so a face is one of the theme's fonts, a weight and a family, each from a
# short list, and no rule sets a size or a leading a pixel from another's. A box the
# user types in keeps its holder's size above the floor (`FLOORS`). A chip's leading is
# the one a rule may state beside the fonts': it holds a band of chips from Leaf's
# sheets and a package's at one height (tokens.css, `--lf-chip-lh`), which a package
# writes as the number. Any other line height, a length included, is a leading of the
# rule's own: a box centres its words by layout rather than with a line as tall as
# itself.
#
# Source a widget shows, such as a diff's lines, takes the code inputs themselves
# (`--lf-mono`, `--lf-code-size`, `--lf-code-line`), which are a source face's own values rather
# than a leading or size of the rule's. They are theme inputs a page may set on a
# subtree, and they set the page's source rather than the interface's words, so no font
# resolved at the root stands for them.
OWN = {
    "font": lambda value: value == "inherit",
    "font-family": lambda value: value in {"inherit", "var(--lf-mono)"},
    "font-size": lambda value: (
        value in {"inherit", "0", "var(--lf-code-size)", *FLOORS}
    ),
    "font-weight": lambda value: value in {"inherit", "bolder", "400", "500", "600"},
    "line-height": lambda value: (
        value
        in {
            "inherit",
            "0",
            "1",
            "var(--lf-ui-lh)",
            "var(--lf-code-line)",
            "var(--lf-chip-lh)",
            "1.6",
        }
    ),
}

# A face a dependency lays out for, by the rule that states it: the one font in Leaf's
# sheets that is neither a theme's font nor a size on its ladder. Plot places a chart's
# axes, ticks and legends for 10px words, and at the small font's 11.5px an axis label
# lands on the tick beside it.
FITTED = {"lf-chart .lf-chart-drawing": "0.625rem / 1.25 var(--lf-sans)"}


def fitted(context, item):
    return item.lower_name == "font" and FITTED.get(context[-1]) == said(item)


AUTHORED = re.compile(
    rf"\.(?:{'|'.join(map(re.escape, sorted(AUTHORED_CLASSES)))})(?![\w-])"
)


def interface(context):
    """Whether a rule selects an element of the interface: an `lf-` element or one with
    an `lf-` class, which a `:not()` excluding one does not. An attribute such as
    `data-lf-state` qualifies an element rather than naming one. A class a kernel idiom
    lets a page write (`structure.AUTHORED_CLASSES`) names the page's own element: a
    drawing's words are the page's, set in the drawing's own units (tokens.css,
    `--lf-drawing-size`)."""
    said = " ".join(context)
    while (bare := re.sub(r":not\([^()]*\)", "", said)) != said:
        said = bare
    said = AUTHORED.sub("", said)
    return re.search(r"(?<![\w-])lf-", said) is not None


def declarations(rules, context=()):
    """Each declaration in `rules`, with the selectors and `@scope` roots around it and
    the declarations of its own rule."""
    for rule in rules:
        if rule.type == "qualified-rule":
            here = (*context, tinycss2.serialize(rule.prelude).strip())
        elif rule.type == "at-rule" and rule.content is not None:
            scope = rule.lower_at_keyword == "scope"
            here = (
                (*context, tinycss2.serialize(rule.prelude).strip())
                if scope
                else context
            )
        else:
            continue
        items = tinycss2.parse_blocks_contents(
            rule.content, skip_whitespace=True, skip_comments=True
        )
        own = [item for item in items if item.type == "declaration"]
        for item in items:
            if item.type == "declaration":
                yield here, item, own
            else:
                yield from declarations([item], here)


def said(item):
    return tinycss2.serialize(item.value).strip().removesuffix("!important").strip()


def test_every_rule_of_the_interface_names_a_declared_font():
    """A face Leaf's interface draws is one of the theme's fonts, named where it is
    used, at a weight of 400, 500 or 600 and in the font's family or the mono one.

    A size or a leading set where it stands, in the interface or a widget, drifts into
    near-duplicates a pixel or a step apart, each of which looks deliberate where it was
    written. A rule of the interface, one that names an `lf-` element or class, names a
    font, so a new size is a new font in the theme's one list of them
    (styles/tokens.css), where it is seen beside the others. A package's sheet has two
    to name, the interface's and the small one (`test_theme_tokens.py` holds it to the
    names the references declare), and Leaf's own sheets also name the faces Leaf keeps
    for its panel, its threads and its marks.

    Asked of the source rather than of a rendered page, because that is where the face
    is chosen, and every sheet is read whether or not a page draws its rules: the
    core's, and each bundled package's, whose widgets' own words are the interface too.
    """
    fonts = {
        item.name
        for _, item, _ in declarations(
            tinycss2.parse_stylesheet((ASSETS / "styles/tokens.css").read_text())
        )
        if item.name.startswith("--lf-font-")
    }
    assert {"--lf-font-ui", "--lf-font-small", "--lf-font-message"} <= fonts, (
        f"tokens.css declares the fonts {sorted(fonts)}: this reading has stopped "
        f"finding them and the assertion below is about nothing"
    )
    named = re.compile(r"var\((--lf-font-[\w-]+)\)")

    def names_a_font(item):
        font = named.fullmatch(said(item))
        return item.lower_name == "font" and font and font.group(1) in fonts

    own = []
    for sheet in shipped_sheets():
        rules = tinycss2.parse_stylesheet(sheet.read_text())
        for context, item, _ in declarations(rules):
            if item.lower_name not in OWN or not interface(context):
                continue
            if names_a_font(item) or fitted(context, item):
                continue
            if not OWN[item.lower_name](said(item)):
                where = f"{sheet.relative_to(PLUGIN_ROOT)}:{item.source_line}"
                own.append(f"{where} {' { '.join(context)} — {item.name}: {said(item)}")
    assert not own, (
        f"{len(own)} rules of the interface set a size, a leading or a family of their "
        f"own rather than naming a font (styles/tokens.css, `--lf-font-*`):\n  "
        + "\n  ".join(own)
    )


# A keyword whose size the browser picks: `medium`, the sizes beside it and `initial`,
# which is `medium`; a system font such as `menu`; and the step `smaller` and `larger`
# take, which each engine chooses.
PICKED = {
    "xx-small",
    "x-small",
    "small",
    "medium",
    "large",
    "x-large",
    "xx-large",
    "xxx-large",
    "initial",
    "caption",
    "icon",
    "menu",
    "message-box",
    "small-caption",
    "status-bar",
    "smaller",
    "larger",
}


def own_sizes(sheets, theme):
    """Each declaration in `sheets` (CSS text by name) that sets a font size of its own
    rather than following the custom properties `theme` declares.

    A font size is a `font-size`, every term of a `font` but its line height (the term
    after its `/`), a custom property either one reads, and a custom property whose
    name says it is one, such as a dependency's `--trees-font-size-override`, which only
    the dependency's own sheet reads. It is a size of its own where it holds a length in
    any unit but `em`, a keyword in `PICKED`, or a custom property neither `theme` nor
    `sheets` declares. A `var()` naming a property `theme` declares passes unread; one
    naming a property only `sheets` declare is read through each declaration of it. A
    floor under the inherited size (`FLOORS`) and a face a dependency lays out for
    (`FITTED`) pass."""
    tokens = {
        item.name
        for _, item, _ in declarations(tinycss2.parse_stylesheet(theme))
        if item.name.startswith("--")
    }
    declared = {}
    sizes = []
    for sheet, css in sheets.items():
        for context, item, _ in declarations(tinycss2.parse_stylesheet(css)):
            held = (sheet, context, item)
            if item.name.startswith("--"):
                declared.setdefault(item.name, []).append(held)
            if item.lower_name in {"font", "font-size"} or "font-size" in item.name:
                sizes.append(held)
    own = {}

    def scan(held, values, font, through):
        sheet, context, item = held
        rule = re.sub(r"\s+", " ", " { ".join(context))
        here = f"{sheet}:{item.source_line} {rule} — {item.name}: {said(item)}"
        values = [
            value for value in values if value.type not in {"whitespace", "comment"}
        ]
        for at, value in enumerate(values):
            if font and at and values[at - 1] == "/":
                continue  # the line height
            if (value.type == "dimension" and value.lower_unit != "em") or (
                value.type == "ident" and value.lower_value in PICKED
            ):
                own[here] = None
            elif value.type == "function" and value.lower_name == "var":
                name, *fallback = [
                    part
                    for part in value.arguments
                    if part.type not in {"whitespace", "comment"}
                ]
                scan(held, fallback, font, through)
                if name.value in tokens or name.value in through:
                    continue
                if name.value not in declared:
                    own[here] = None
                for holder in declared.get(name.value, ()):
                    scan(holder, holder[2].value, font, through | {name.value})
            elif value.type == "function":
                scan(held, value.arguments, False, through)

    for held in sizes:
        if said(held[2]) in FLOORS or fitted(held[1], held[2]):
            continue
        scan(held, held[2].value, held[2].lower_name == "font", {held[2].name})
    return list(own)


def test_every_font_size_names_a_theme_token():
    """Every font size in Leaf's sheets names a token of the theme or scales the size
    its element inherits, so a new size is a new token in tokens.css, where it is seen
    beside the others, and a density or a theme that restates a rung reaches every word
    set at it.

    A size names the theme when it names a custom property tokens.css declares. The
    sizes there are the rungs (`--lf-t-*`), the code size, the drawing sizes,
    `--lf-entry-floor` (the smallest size typed words take on a touch screen, which a
    package's sheet writes as its number, `FLOORS`) and the fonts built from them. The test doesn't tell those from the file's other properties, so a
    box's size used as a font size would pass, and it doesn't read a property tokens.css
    declares wherever it is set: those declarations, and a density's or theme's
    restatement of them, are the theme itself. A package's own property, such as an
    option's font, is read through its declarations.

    `inherit`, `em` and `%` pass, since they scale the size their element inherits. A
    run sized against whatever holds it, such as inline code beside its line or an
    identifier in a table cell, has no rung of its own, and the ratio keeps it in step
    with whichever rung its holder takes. A unitless factor in `calc()` over a token
    passes for the same reason, and `0` sizes a box that holds no words. Any other
    length, in `px`, `rem` or a viewport or container unit, stays where it was written
    when the ladder moves, and a keyword such as `medium` or `menu` takes a size the
    browser picks. Weight and family are outside this test; the one above holds the
    interface's rules to the theme's fonts.

    Asked of the source rather than of a rendered page, because that is where a size is
    chosen, and every sheet is read whether or not a page draws its rules: the core's
    and each bundled package's, less what they vendor.
    """
    own = own_sizes(
        {
            str(path.relative_to(PLUGIN_ROOT)): path.read_text()
            for path in shipped_sheets()
        },
        (ASSETS / "styles/tokens.css").read_text(),
    )
    assert not own, (
        f"{len(own)} font sizes neither name a token of styles/tokens.css nor scale the "
        f"size they inherit:\n  " + "\n  ".join(own)
    )


def test_a_size_of_its_own_is_found_however_it_is_written():
    theme = """
      :root { --lf-t-5: 0.875rem; --lf-sans: system-ui; --lf-font-ui: var(--lf-t-5) / 1.45 var(--lf-sans); }
      @media (pointer: coarse) { :root { --lf-entry-floor: 16px; } }
    """
    follows = """
      .rung { font-size: var(--lf-t-5); }
      .shorthand { font: 600 var(--lf-t-5) / 20px var(--lf-sans); }
      .font { font: var(--lf-font-ui); }
      .inherited { font-size: inherit; }
      .ratio code { font-size: 0.9em; }
      .percent { font-size: 82%; }
      .floored { font-size: max(var(--lf-entry-floor), 1em); }
      @media (pointer: coarse) { .fingered { font-size: max(16px, 1em); } }
      lf-chart .lf-chart-drawing { font: 0.625rem / 1.25 var(--lf-sans); }
      .factor { font-size: calc(var(--lf-t-5) * 1.2); }
      .empty { font-size: 0; }
      .widget { --widget-font: var(--lf-t-5)/1.5 var(--lf-sans); font: var(--widget-font); }
      .dense { --lf-t-5: 0.78125rem; }
    """
    own = """
      .pixels { font-size: 11px; }
      .shorthand { font: 600 13px / 1.3 var(--lf-sans); }
      @media screen { .fluid { font-size: clamp(var(--lf-t-5), 3.2cqi, var(--lf-t-5)); } }
      .widget { --widget-size: 0.82rem; }
      .widget .text { font-size: var(--widget-size); }
      .bridge { --dependency-font-size-override: 13px; }
      .picked { font-size: smaller; }
      .undeclared { font-size: var(--nowhere); }
      .fallback { font-size: var(--lf-t-5, 12px); }
      .system { font: menu; }
      .low { font-size: max(13px, 1em); }
      .chart { font: 0.625rem / 1.25 var(--lf-sans); }
    """
    assert own_sizes({"follows.css": follows}, theme) == []
    assert own_sizes({"own.css": own}, theme) == [
        "own.css:2 .pixels — font-size: 11px",
        "own.css:3 .shorthand — font: 600 13px / 1.3 var(--lf-sans)",
        "own.css:4 .fluid — font-size: clamp(var(--lf-t-5), 3.2cqi, var(--lf-t-5))",
        "own.css:5 .widget — --widget-size: 0.82rem",
        "own.css:7 .bridge — --dependency-font-size-override: 13px",
        "own.css:8 .picked — font-size: smaller",
        "own.css:9 .undeclared — font-size: var(--nowhere)",
        "own.css:10 .fallback — font-size: var(--lf-t-5, 12px)",
        "own.css:11 .system — font: menu",
        "own.css:12 .low — font-size: max(13px, 1em)",
        "own.css:13 .chart — font: 0.625rem / 1.25 var(--lf-sans)",
    ]
