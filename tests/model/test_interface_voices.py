"""Leaf's interface speaks in the voices base.css declares (`--voice-*`)."""

import re

import tinycss2

from leaf.schema import ASSETS

# Declarations that make a face, and what a rule of the interface may write for each
# without naming a voice: inheriting its holder's, a weight for a run that keeps its
# holder's voice, a box that holds no words, and the voices' shared leading. Any other
# line height, a length included, is a leading of the rule's own: a box centres its
# words by layout rather than with a line as tall as itself.
OWN = {
    "font": lambda value: value == "inherit",
    "font-family": lambda value: value == "inherit",
    "font-size": lambda value: value in {"inherit", "0"},
    "font-weight": lambda value: value in {"inherit", "400", "500", "600"},
    "line-height": lambda value: value in {"inherit", "0", "1", "var(--lf-ui-lh)"},
}

# The default face of a native control states the ui voice's parts at a class's
# weight, so the element rules of the layered sheets lose to it, while its weight,
# slant and variants are reset by a rule at no weight beside it, which names the voice
# (surfaces.css, its header says why).
CONTROL_DEFAULT = ":where(:root, :host) :is(.lf-ui-face, .button, .field)"


def sheets():
    return [p for p in sorted(ASSETS.rglob("*.css")) if "vendor" not in p.parts]


def interface(context):
    """Whether a rule selects an element of the interface: one with an `lf-` class,
    which a `:not()` excluding one does not."""
    said = " ".join(context)
    while (bare := re.sub(r":not\([^()]*\)", "", said)) != said:
        said = bare
    return ".lf-" in said


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


def test_every_rule_of_the_interface_speaks_in_a_declared_voice():
    """A face Leaf's interface draws is one of a closed set, named where it is used.

    The interface set each face where it stood, and drifted into near-duplicates: the
    floating panel at 13px and 12px beside the chrome's 14px and 11.5px, a row's end a
    pixel under whatever row held it, line heights from 1.2 to 1.5, weights of 450, 650
    and 700. Each looked deliberate where it was written. A rule of the interface, one
    that names an `lf-` class, now names a voice, so a new face is a new voice in
    base.css's one list of them, where it is seen beside the others.

    Asked of the source rather than of a rendered page, because that is where the face
    is chosen, and every sheet is read whether or not a page draws its rules.
    """
    voices = {
        item.name
        for _, item, _ in declarations(
            tinycss2.parse_stylesheet((ASSETS / "base.css").read_text())
        )
        if item.name.startswith("--voice-")
    }
    assert {"--voice-ui", "--voice-small", "--voice-message"} <= voices, (
        f"base.css declares the voices {sorted(voices)}: this reading has stopped "
        f"finding them and the assertion below is about nothing"
    )
    named = re.compile(r"var\((--voice-[\w-]+)\)")

    def names_a_voice(item):
        voice = named.fullmatch(said(item))
        return item.lower_name == "font" and voice and voice.group(1) in voices

    own = []
    for sheet in sheets():
        rules = tinycss2.parse_stylesheet(sheet.read_text())
        for context, item, siblings in declarations(rules):
            if item.lower_name not in OWN or not interface(context):
                continue
            if context[-1] == CONTROL_DEFAULT:
                continue
            if names_a_voice(item):
                continue
            # A rule that names a voice takes its weight with it; only a run keeping
            # its holder's voice sets one.
            beside = item.lower_name == "font-weight" and any(
                map(names_a_voice, siblings)
            )
            if beside or not OWN[item.lower_name](said(item)):
                where = f"{sheet.relative_to(ASSETS)}:{item.source_line}"
                own.append(f"{where} {' { '.join(context)} — {item.name}: {said(item)}")
    assert not own, (
        f"{len(own)} rules of the interface set a face of their own rather than naming "
        f"a voice (base.css, `--voice-*`):\n  " + "\n  ".join(own)
    )
