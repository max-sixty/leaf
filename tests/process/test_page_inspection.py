"""The menu's inspection route reads the displayed capture, not editable files."""

import json

from interact_support import fetch, write_revision
from model_folds import leaf_page

from leaf.page_inspection import cmd_inspect


def test_inspection_route_requires_and_preserves_the_displayed_revision(
    page_dir, server
):
    first = leaf_page("First", '<p id="p" style="color: red">Original</p>')
    write_revision(page_dir, 1, first.encode())
    second = leaf_page("Second", '<p id="p" style="color: blue; margin: 0">New</p>')
    write_revision(page_dir, 2, second.encode())
    (page_dir / "index.html").write_text(second)
    status, raw = fetch(server + "/api/inspect?revision=1")
    assert status == 200
    report = json.loads(raw)
    assert report == cmd_inspect(page_dir, 1)
    assert report["css"]["page"]["declarations"] == 1
    assert fetch(server + "/api/inspect")[0] == 400
    assert fetch(server + "/api/inspect?revision=99")[0] == 400
    assert fetch(server + "/api/inspect?revision=1", token=None)[0] == 401
