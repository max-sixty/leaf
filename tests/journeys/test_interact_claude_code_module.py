from process.test_interact_claude_code_module import claude_code as claude_code

"""Tests scheduled by the measured cost of their boundary."""

from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    read_record,
    wait_for,
)
from process.test_interact_claude_code_module import band_lines

from leaf import server as server_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import thread as thread_model


def test_the_band_follows_the_pages_the_session_holds(
    page_dir, claude_code, monkeypatch
):
    """Above the prompt, in the terminal and the desktop app alike, each page the
    session holds is a link with the counts its Leaf panel marks that aren't zero:
    On me, open threads, and those holding words the user hasn't read; then what
    the agent last said it waits for. The band redraws as the page's row changes,
    and empties once the session holds no page."""

    def band(expected):
        server_rows_model.RowPublisher(page_dir, server_id).refresh()
        return wait_for(
            lambda: {
                surface: band_lines(drawn, surface)
                for surface, drawn in claude_code.bands.get(
                    timeout=STATED_TIMEOUT
                ).items()
            },
            lambda lines: lines == {"terminal": expected, "desktop": expected},
            failure=f"the band never showed {expected}",
        )

    server_id = read_record(page_dir / "service.json")["server_id"]
    server_rows_model.RowPublisher(page_dir, server_id).refresh()
    read_result = server_rows_model.ROW.read(server_rows_model.row_path(page_dir))
    assert read_result is not None
    published = read_result["row"]
    server = server_model.running_server(page_dir)
    assert server is not None
    url, title = server["url"], published["title"]
    band([(f"Leaf {title}", url)])
    # A /clear ends the session and starts none; the next turn follows again.
    claude_code.emit(
        "session.end", {"reason": "clear", "sessionId": claude_code.session}
    )
    band([])
    claude_code.emit("turn.start", {"text": "", "turnId": "t"})
    band([(f"Leaf {title}", url)])
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "why?"}
    )
    band([(f"Leaf {title} · Threads 1", url)])
    thread_model.post_reply(
        page_dir, {"parent": comment["id"], "responds": comment["id"]}, "Because."
    )
    band([(f"Leaf {title} · Threads 1, 1 new", url)])
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": comment["id"],
            "text": "Can you try it?",
            "obligation": True,
        },
    )
    band([(f"Leaf {title} · On me 1 · Threads 1, 1 new", url)])
    # Another session takes the page, so this one holds none.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "cc-s2")
    service_model.claim_page(page_dir)
    band([])
