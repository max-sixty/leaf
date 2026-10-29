"""The face census compares presses by what they look like and pairs them by what
names them, not by the tokens a theme calls a colour or the order presses come in."""

from leaf_dev.faces import groups, pairs, report


def press(label, at, ink, hover_ink="#1c1b18", key="main > button"):
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
        "key": key,
        "at": at,
        "flags": [],
        "words": False,
        "rest": face(ink),
        "hover": face(hover_ink),
    }


def test_a_token_alias_changes_no_face_and_a_dark_ink_change_shows():
    light = {"presses": [press("Send", [10, 10], "#2f5480")]}
    base = {
        "plan": {**light, "tokens": {"#2f5480": ["--accent"]}},
        "plan-dark": {"presses": [press("On me", [10, 10], "#9fb6d4")], "tokens": {}},
    }
    head = {
        "plan": {**light, "tokens": {"#2f5480": ["--accent", "--a"]}},
        "plan-dark": {"presses": [press("On me", [10, 10], "#e06c5a")], "tokens": {}},
    }
    text, added = report(base, head, {"plan": set(), "plan-dark": {"dark"}})
    assert added == 1
    assert "1 new, 1 gone, 1 presses moved" in text
    assert len(groups(head)) == 2


def test_a_second_press_with_the_same_label_moves_no_press():
    base = {"card": {"presses": [press("Reply", [10, 10], "#6f6a60")], "tokens": {}}}
    # The styles reading tells like siblings apart by order, so the first Reply's key
    # now names the new one.
    head = {
        "card": {
            "presses": [
                press("Reply", [10, 50], "#2f5480"),
                press("Reply", [10, 10], "#6f6a60", key="main > button:1"),
            ],
            "tokens": {},
        }
    }
    [(_, before, after)] = pairs(base, head)
    assert after["at"] == before["at"]
    text, _ = report(base, head, {"card": set()})
    assert "0 presses moved" in text


def test_a_reply_in_another_thread_is_new_not_moved():
    base = {
        "card": {
            "presses": [
                press("Reply", [10, 10], "#6f6a60", key="div#thread-a > button")
            ],
            "tokens": {},
        }
    }
    head = {
        "card": {
            "presses": [
                press("Reply", [10, 10], "#2f5480", key="div#thread-b > button")
            ],
            "tokens": {},
        }
    }
    assert not list(pairs(base, head))
    text, _ = report(base, head, {"card": set()})
    assert "1 new, 1 gone, 0 presses moved" in text
