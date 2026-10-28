"""Pictures: media names a file by its bytes, and the reply and text doors refuse a
picture the page directory lacks."""

import json
import re

import pytest
from click.testing import CliRunner
from interact_support import PAGE, check_findings, comment, fetch, found, publish

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import media as media_model


def test_media_names_a_file_by_its_bytes_and_serves_it(page_dir, tmp_path, server):
    """An image reaches a page by reference, because the page's author is a language
    model and a screenshot is a megabyte of base64 it cannot type. The name is the
    hash of the bytes, which is what lets the page directory keep its promise while
    holding content: two versions showing the same screenshot share the one file, and
    a name the user has already approved can never come to mean different pixels."""
    shot = tmp_path / "nav.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"pretend pixels")
    (url,) = [item["path"] for item in media_model.cmd_media(page_dir, [shot])]
    assert re.fullmatch(r"/media/[a-f0-9]{16}\.png", url)
    # Re-adding the same bytes is the same file, not a second copy of it, whatever
    # case the source's suffix is in: the name is the one the server serves.
    assert media_model.cmd_media(page_dir, [shot])[0]["path"] == url
    loud = tmp_path / "NAV.PNG"
    loud.write_bytes(shot.read_bytes())
    assert media_model.cmd_media(page_dir, [loud])[0]["path"] == url
    assert len(list((page_dir / "media").iterdir())) == 1

    status, body = fetch(server + url)
    assert (status, body) == (200, shot.read_bytes())
    # And nothing else out of the directory: the log is not a served path.
    assert fetch(server + "/events.jsonl")[0] == 404


def test_a_media_digest_can_never_change_the_bytes_behind_an_existing_name(
    page_dir, tmp_path, monkeypatch
):
    """The public name's immutable meaning survives even a digest collision."""

    class CollidingDigest:
        def hexdigest(self):
            return "a" * 64

    monkeypatch.setattr(media_model.hashlib, "sha256", lambda data: CollidingDigest())
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first pixels")
    second.write_bytes(b"different pixels")
    path = media_model.cmd_media(page_dir, [first])[0]["path"]

    with pytest.raises(RuntimeError, match="media digest collision"):
        media_model.cmd_media(page_dir, [second])

    assert (page_dir / path.lstrip("/")).read_bytes() == first.read_bytes()


def test_the_reply_door_refuses_a_picture_the_page_directory_has_not_got(page_dir):
    """The two markup doors ask the same thing of a reference to a file.

    A widget carrying pictures is exactly the shape an agent sends in a reply — here
    is how it looks now, and after — and `/media/…` is how markup names one. A version
    naming a file the directory cannot answer is refused, and the same markup in a
    reply was accepted and frozen: the log is append-only, so it is two broken images
    for as long as the page exists, and no check afterwards would ever mention them.

    The version door is the control. It is the same reading, so a difference between
    them can only be one of the two having stopped asking."""
    shot = (
        '<lf-shot id="ps-shot" alt="the panel before and after" '
        'before="/media/0000000000000001.png" after="/media/0000000000000002.png">'
        "</lf-shot>"
    )
    (page_dir / "index.html").write_text(PAGE.replace("</main>", shot + "</main>"))
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "missing-media", ref="/media/0000000000000001.png"), (
        "the version door stopped asking, so the comparison below is empty"
    )

    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    opened = comment(page_dir, "--text", "show me?")
    assert opened.exit_code == 0, opened.output
    posted = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            json.loads(opened.output)["id"],
            "--text",
            "here:",
            "--markup",
            shot,
        ],
    )
    assert posted.exit_code == 1, (
        f"the reply door froze a picture the page has not got into the log:\n"
        f"{posted.output}"
    )
    assert "/media/0000000000000001.png isn't in the page directory" in posted.output, (
        posted.output
    )
    assert not [e for e in events_model.read_events(page_dir) if e["kind"] == "reply"]


def test_the_text_door_refuses_a_picture_the_page_directory_has_not_got(page_dir):
    """A message names its picture in Markdown, where the markup reading cannot see it.

    `check_markup` runs only when `--markup` is given, and the reference it asks about
    lives in an attribute. An agent sending a screenshot writes it in the words instead,
    so the shape `media_errors` was written for — here is what it looks like now — came
    through the one door that never asked, and the log is append-only: a picture the
    directory hasn't got is broken for as long as the page exists.

    The reading is the link or image destination the runtime resolves rather than a scan
    of the words, so the same path quoted in a sentence — a page explaining leaf writes
    one, and `page check` has always let it through — stays the author's prose. Every
    `/media/…` destination is asked about, the predicate the markup door's attribute
    harvest already keeps, and the server answers only a digest name there, so a
    destination that isn't one renders as a picture no request will ever answer."""
    publish(page_dir)
    missing = "/media/deadbeefdeadbeef.png"
    posted = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(page_dir),
            "--text",
            f"the panel now:\n\n![shot]({missing})",
        ],
    )
    assert posted.exit_code == 1, (
        f"the comment door froze a picture the page has not got into the log:\n"
        f"{posted.output}"
    )
    assert f"{missing} isn't in the page directory" in posted.output, posted.output
    assert not [e for e in events_model.read_events(page_dir) if e["kind"] == "comment"]

    mention = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(page_dir),
            "--text",
            f"write it as `{missing}` in the message",
        ],
    )
    assert mention.exit_code == 0, (
        f"a path named in a sentence is the author's words, the reading the markup "
        f"door already keeps, not a picture the page owes:\n{mention.output}"
    )

    quoted = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(page_dir),
            "--text",
            f"Here is the source:\n\n```md\n![shot]({missing})\n```\n\n[unused]: {missing}",
        ],
    )
    assert quoted.exit_code == 0, (
        f"code and an unused reference definition render no media, so neither "
        f"requires a file:\n{quoted.output}"
    )

    linked = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(page_dir),
            "--text",
            f'[the panel](<{missing}> "shot")',
        ],
    )
    assert linked.exit_code == 1, (
        f"a link destination points at the same file an image does, angle brackets "
        f"and title included:\n{linked.output}"
    )

    referenced = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(page_dir),
            "--text",
            f"![shot][ref]\n\n[ref]: {missing}",
        ],
    )
    assert referenced.exit_code == 1, (
        f"a reference definition is where a reference-style image keeps its "
        f"destination, and the runtime renders it as the inline form:\n"
        f"{referenced.output}"
    )

    # A file copied in by hand under a name `leaf page media` never gives is one the
    # server never serves, so the door asks the name before it asks the directory.
    (page_dir / "media").mkdir(exist_ok=True)
    for unserved in ("screenshot.png", "deadbeefdeadbeef.PNG"):
        (page_dir / "media" / unserved).write_bytes(b"\x89PNG\r\n\x1a\n")
        unnamed = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "create",
                str(page_dir),
                "--text",
                f"look:\n\n![shot](/media/{unserved})",
            ],
        )
        assert unnamed.exit_code == 1, (
            f"the server answers only a digest name, so a destination under /media/ "
            f"that isn't one is a picture no request will ever load, whatever the "
            f"directory holds:\n{unnamed.output}"
        )
        assert (
            f"/media/{unserved} isn't a name `leaf page media` gives" in unnamed.output
        ), unnamed.output
        (page_dir / "media" / unserved).unlink()

    (page_dir / "media" / "deadbeefdeadbeef.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    answered = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(page_dir),
            "--text",
            f"the panel now:\n\n![shot]({missing})",
        ],
    )
    assert answered.exit_code == 0, (
        f"a reference the directory answers is the whole point of the door:\n"
        f"{answered.output}"
    )
