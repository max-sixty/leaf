"""The face census compares presses by what they look like and pairs them by what
names them, not by the tokens a theme calls a colour or the order presses come in."""

from leaf_dev.faces import groups, pairs, report


def press(label, at, ink, hover_ink="#1c1b18"):
    def face(colour):
        return {
            "size": {"width": 28, "height": 28},
            "fill": None,
            "image": False,
            "border": None,
            "radius": None,
            "shadow": None,
            "ink": colour,
            "font": None,
            "underline": False,
            "opacity": 1,
        }

    return {
        "label": label,
        "element": "button",
        "at": at,
        "key": None,
        "scope": None,
        "flags": [],
        "words": False,
        "rest": face(ink),
        "hover": face(hover_ink),
    }


def test_a_token_alias_or_the_dark_scheme_changes_no_face():
    light = {"presses": [press("Send", [10, 10], "#2f5480")]}
    base = {"plan": {**light, "tokens": {"#2f5480": ["--accent"]}}}
    head = {
        "plan": {**light, "tokens": {"#2f5480": ["--accent", "--a"]}},
        "plan-dark": {
            "presses": [press("Send", [10, 10], "#9fb6d4", hover_ink="#e8e4db")],
            "tokens": {"#9fb6d4": ["--accent"], "#e8e4db": ["--ink"]},
            "light tokens": {"#2f5480": ["--accent"], "#1c1b18": ["--ink"]},
        },
    }
    assert len(groups(head)) == 1
    base["plan-dark"] = head["plan-dark"]
    text, added = report(base, head, {"plan": set(), "plan-dark": {"dark"}})
    assert added == 0
    assert "0 new, 0 gone, 0 presses moved" in text


def test_a_second_press_with_the_same_label_moves_no_press():
    base = {"card": {"presses": [press("Reply", [10, 10], "#6f6a60")], "tokens": {}}}
    head = {
        "card": {
            "presses": [
                press("Reply", [10, 50], "#2f5480"),
                press("Reply", [10, 10], "#6f6a60"),
            ],
            "tokens": {},
        }
    }
    [(_, before, after)] = pairs(base, head)
    assert after["at"] == before["at"]
    text, _ = report(base, head, {"card": set()})
    assert "0 presses moved" in text
