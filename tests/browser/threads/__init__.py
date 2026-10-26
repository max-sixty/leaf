"""Comment threads on a rendered page and in the floating panel's Threads and thread
views, with the helpers and page constants their modules share."""

import base64
import json

from click.testing import CliRunner
from interact_support import append_carried_log_record, record_claim
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    SEATED_OBLIGATION_LAYER,
    SEATED_OBLIGATION_WIDGETS,
    panel_comment,
)
from render_cases_navigation import source_revision
from render_harness import (
    PANEL_THREAD,
    leaf_page,
    open_page,
    open_threads,
    page_comment,
    panel_field,
    panel_settled,
    panel_view,
    scroll_settled,
    write,
)

from leaf import cli as cli_model
from leaf import data as data_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf.render_checks import rendered

# The open thread's reply, the editor standing in the panel's field, and the thread's
# held news, which the panel stands among its view's controls.
PANEL_REPLY = '.lf-fp-field leaf-text[name="reply"]'
PANEL_NEWS = ".lf-fp-controls .lf-thread-news"


def thread_row(page, key):
    """The thread `key`'s row in the panel's Threads view, opening Threads where it is
    not the view standing open. Its `.lf-fp-value` says the thread's state, less
    Resolved under the Resolved heading that already says it. `key` may be the thread's
    id: a thread this
    tab started is keyed by the attempt that sent it (thread/model.js, `threadKey`)."""
    key = page.evaluate(
        """async (id) => {
          const {readThreads} = await window.__lfWidgetApi();
          return readThreads().threads.find((t) => t.id === id)?.key ?? id;
        }""",
        key,
    )
    open_threads(page)
    return page.locator(f'{panel_view("threads")} .lf-fp-thread[data-key="{key}"]')


def open_panel_thread(page, thread_id):
    """Open the thread `thread_id` in the panel the way a reader finds it, and return its
    view, standing open: Threads, then its row, among the open threads or under
    Resolved. A thread already open there is left as it stands. A row is keyed by the
    thread's key, which for a thread this tab started is the attempt that sent it
    (thread/model.js, `threadKey`), so the page's own reading finds it."""
    view = page.locator(f'{PANEL_THREAD}[data-thread="{thread_id}"]')
    if view.count():
        return view
    key = page.evaluate(
        """async (id) => {
          const {readThreads} = await window.__lfWidgetApi();
          return readThreads().threads.find((t) => t.id === id)?.key ?? null;
        }""",
        thread_id,
    )
    assert key, f"the page holds no thread {thread_id}"
    open_threads(page)
    page.locator(f'.lf-fp-thread[data-key="{key}"]').click()
    expect(view).to_be_visible()
    panel_settled(page, view="thread")
    return view


# Named from the command's own answer: a page open on this directory appends a
# bookkeeping `read` of its own, so the log's tail is not reliably this summary.
def summarize_thread(page_dir, first, last, text, *, label=None):
    """Admit one agent summary through the public command door."""
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "summarize",
            str(page_dir),
            "--from",
            first,
            "--through",
            last,
            "--text",
            text,
            *(["--label", label] if label is not None else []),
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def append_user_reply(page_dir, parent, text):
    return append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": parent,
            "revision": 1,
            "text": text,
        },
    )


def append_agent_reply(page_dir, parent, text, markup=None):
    event = {
        "kind": "reply",
        "author": "agent",
        "agent": "Codex",
        "session": "pytest-summary",
        "parent": parent,
        "revision": 1,
        "text": text,
    }
    if markup is not None:
        event["markup"] = markup
    return append_carried_log_record(page_dir, event)


def claim_for_codex(page_dir, request):
    """Claim the page for a Codex task listening on it, as App Server's adapter does."""
    claim = record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(page_dir, claim["id"])
    )
    assert lease
    request.addfinalizer(lease.close)
    with service_model.PageTransaction(page_dir) as transaction:
        transaction.set_status("waiting")


STREAM_ATTEMPT = service_model.delivery_reply_attempt("delivery-1")


def stream_reply(page_dir, root, text):
    """Stand the task's provisional answer to `root` at `text`, as App Server's stream
    writes it from the turn's first notification on."""
    with service_model.PageTransaction(page_dir) as transaction:
        transaction.set_stream_reply(
            "codex-thread",
            "leaf-turn",
            {"parent": root, "responds": root},
            STREAM_ATTEMPT,
            "item-1" if text else None,
            text,
            "active",
        )


def paste_image(field, pixels, *, count=1):
    """Paste page media and wait for the input to finish admitting every upload."""
    with field.page.expect_response(
        lambda response: response.url.endswith("/api/media")
    ):
        field.evaluate(
            """(box, {encoded, count}) => {
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              for (let index = 0; index < count; index += 1)
                transfer.items.add(new File([bytes], `rendering-${index}.png`, {type: 'image/png'}));
              box.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true, cancelable: true, clipboardData: transfer,
              }));
            }""",
            {"encoded": base64.b64encode(pixels).decode(), "count": count},
        )
    expect(field).not_to_have_attribute("aria-busy", "true")


def long_diff_thread(serve, lead=""):
    """Serve a diff long enough for its file header to stick, after `lead`, with a
    user's thread on its first line, and return the page's URL and the thread's id."""
    lines = "".join(f" line {number}\n" for number in range(2, 80))
    url = serve(
        leaf_page(
            "a long diff thread",
            f'<h1 id="title">Review</h1>{lead}<lf-diff id="patch" source="review-patch">'
            "<pre></pre></lf-diff><p>Reading the paragraph after the diff.</p>",
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1,79 +1,79 @@\n"
        f'-return "old"\n+return "new"\n{lines}',
    )
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this check beside the changed line.",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    return url, root


def _shadow_tree_widget(tag):
    """A declaration and module for a widget that renders one word into a declared
    shadow tree."""
    declaration = {
        "description": "A project-supplied tree.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-shadow": True,
        "x-example": f'<{tag} id="example"></{tag}>',
    }
    module = f"""
import {{shadowStage}} from '/runtime/widget-api.js';
customElements.define('{tag}', class extends HTMLElement {{
  connectedCallback() {{
    if (this.shadowRoot) return;
    const word = document.createElement('span');
    word.textContent = '{tag}';
    shadowStage(this, [word]);
  }}
}});
"""
    return declaration, module


PAGE_CHANGE = (
    '<lf-suggestion id="tv-doc-sug">'
    '<lf-old><p id="tv-doc-old">Sessions live five minutes.</p></lf-old>'
    "<lf-new><p>Sessions live ninety seconds.</p></lf-new>"
    "</lf-suggestion>"
)


CHANGE_HEAD = "<h1 id='dc-h'>Session store</h1>"


CHANGE_PAGE = leaf_page("doc-change", CHANGE_HEAD + PAGE_CHANGE)


REPLY_CHANGE = PAGE_CHANGE.replace("tv-doc-", "tv-msg-")


def seed_reply(d, markup, anchor_id, chatter=0, after=0):
    """A thread whose reply carries `markup`, with a thread anchored on it.

    `chatter` is what makes the panel a scroller of its own: a travel that lands by
    accident when the whole list already fits proves nothing about which box moved.
    `after` is what makes the middle of that list reachable — a widget in the last
    message can only be brought to the end of the scroll range, which `scrollIntoView`
    reaches on its own, so a centring assertion over one asserts nothing.
    """
    for n in range(chatter):
        append_carried_log_record(
            d,
            {
                "kind": "comment",
                "id": f"tv-pad{n}",
                "author": "user",
                "revision": 1,
                "text": f"Aside {n}. " + "Long enough to wrap in the panel. " * 4,
            },
        )
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "tv-decisioned",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "tv-decisioned",
            "revision": 1,
            "text": "Depends what you want to keep:",
            "markup": markup,
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "tv-on-it",
            "author": "user",
            "revision": 1,
            "text": "Redis, and say why in the patch.",
            "anchor": {"section": anchor_id},
        },
    )
    for n in range(after):
        append_carried_log_record(
            d,
            {
                "kind": "comment",
                "id": f"tv-later{n}",
                "author": "user",
                "revision": 1,
                "text": f"Later {n}. " + "Long enough to wrap in the panel. " * 4,
            },
        )


LANDING_WORDS = (
    "This message has enough words in it to wrap over several lines in the panel, "
    "so that a thread of a dozen of them is taller than the list's scrollport. "
)


def seed_panel_threads(page_dir, threads, long_index=None, messages=12):
    """`threads` panel threads of two turns each, the one at `long_index` with
    `messages` turns, so it stands taller than the list's scrollport."""
    roots = []
    for i in range(threads):
        root = panel_comment(page_dir, f"Thread {i} opening. " + LANDING_WORDS)
        roots.append(root)
        for turn in range(1, messages if i == long_index else 2):
            agent = turn % 2 == 1
            append_carried_log_record(
                page_dir,
                {
                    "kind": "reply",
                    "author": "agent" if agent else "user",
                    **({"agent": "Codex"} if agent else {}),
                    "parent": root,
                    "text": f"Turn {turn} of thread {i}. " + LANDING_WORDS,
                },
            )
    return roots


def reply_by_keyboard(page, root):
    """Open the thread in the panel, stand on its view and press `c` into its reply,
    the panel's field; return the view."""
    view = open_panel_thread(page, root)
    view.focus()
    rendered(page)
    page.keyboard.press("c")
    reply = panel_field(page)
    expect(reply).to_be_focused()
    expect(reply).to_have_attribute("name", "reply")
    rendered(page)
    return view


# Where a node stands against the open panel view's landing band: its scrollport less
# the scroll padding the focus ring takes.
IN_LANDING_BAND = """node => {
  const list = document.querySelector('.lf-fp-view:not([data-leaving])');
  const shown = list.getBoundingClientRect();
  const style = getComputedStyle(list);
  const band = [shown.top + (parseFloat(style.scrollPaddingTop) || 0),
                shown.bottom - (parseFloat(style.scrollPaddingBottom) || 0)];
  const box = node.getBoundingClientRect();
  return {inside: box.top >= band[0] - 1 && box.bottom <= band[1] + 1,
          box: [Math.round(box.top), Math.round(box.bottom)],
          band: band.map(Math.round)};
}"""


SEAT_FILLER = "".join(
    f"<p>Filler paragraph {n}, long enough to occupy a line of reading.</p>"
    for n in range(40)
)


SEAT_WORDS = (
    "This is a longer message that wraps onto a second line at a normal reading "
    "width, so a thread of a dozen of them is taller than a short window."
)


SEAT_DIFF = (
    "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
    '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
)


THIRTY_LINES = "\n".join(f"Pasted line {n}" for n in range(30))


def bounded_seat_page(steps, bound):
    """A talk seat at the foot of a command that bounds its own height with
    `data-bound`, after `steps` plain tasks, between screens of filler. Its
    stated height leaves ample overflow even when typography changes."""
    tasks = "".join(
        f'<lf-test-task id="step-{n}" status="planned"><strong>Step {n}</strong> '
        f"{SEAT_WORDS}</lf-test-task>"
        for n in range(steps)
    )
    return leaf_page(
        "bounded seat",
        f'<h1 id="h">Three jobs</h1>{SEAT_FILLER}<lf-test-plan id="hub" '
        f'label="Before the frost" data-bound="{bound}">{tasks}<lf-test-task id="jobs" '
        'status="active" talk><strong>Which jobs are worth starting?</strong> The '
        f"mounts came down in January.</lf-test-task></lf-test-plan>{SEAT_FILLER}",
        head="<style>#hub { --lf-bound: 18rem; }</style>",
    )


def seated_page(serve, kind):
    """A page whose seat sits past a screen of filler with more below it, and the
    selector of the widget holding it: `task` keeps its box after a send to offer
    Send & pause, `verdict` gives it up to the thread it starts. `bounded` is a task
    in a command that bounds its height and scrolls, `bounded-short` one in a block
    whose bound its contents do not yet fill."""
    if kind == "bounded":
        return serve(bounded_seat_page(6, "end")), "#jobs"
    if kind == "bounded-short":
        return serve(
            leaf_page(
                "bounded seat",
                f'<h1 id="h">Three jobs</h1>{SEAT_FILLER}<lf-test-plan id="hub" '
                'label="Before the frost"><lf-test-task id="jobs" status="active" talk '
                'data-bound="start"><strong>Which jobs are worth starting?</strong>'
                f"</lf-test-task></lf-test-plan>{SEAT_FILLER}",
            )
        ), "#jobs"
    if kind == "task":
        return serve(
            leaf_page(
                "seat",
                f'<h1 id="h">Three jobs</h1>{SEAT_FILLER}<lf-test-plan id="hub" '
                'label="Before the frost"><lf-test-task id="jobs" status="active" talk>'
                "<strong>Which jobs are worth starting?</strong> The mounts came "
                f"down in January.</lf-test-task></lf-test-plan>{SEAT_FILLER}",
            )
        ), "#jobs"
    return serve(
        leaf_page(
            "seat",
            f'<h1>Review the plan</h1>{SEAT_FILLER}<lf-verdict id="proposal" asks>'
            f"Should these jobs share a visit?</lf-verdict>{SEAT_FILLER}",
        ),
        layer_registry=SEATED_OBLIGATION_LAYER,
        layer_widgets=SEATED_OBLIGATION_WIDGETS,
    ), "#proposal"


def paste(page, text):
    """Paste `text` into the focused box through the clipboard, as a user's paste
    arrives: one edit, which CodeMirror scrolls its caret into view for."""
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("text => navigator.clipboard.writeText(text)", text)
    page.keyboard.press("ControlOrMeta+v")
    rendered(page)


def to_window_foot(page, locator, gap):
    """Scroll the page so `locator`'s foot stands `gap` px above the window's."""
    page.evaluate(
        """([node, gap]) => document.scrollingElement.scrollBy({
          top: node.getBoundingClientRect().bottom - (innerHeight - gap),
          behavior: 'instant'})""",
        [locator.element_handle(), gap],
    )
    scroll_settled(page)


def clear_of_the_panel(page, locator):
    """Whether the node is wholly in the window and clear of the floating panel, which
    stands over the window's foot across the columns it spans."""
    return page.evaluate(
        """([node, card]) => {
          const box = node.getBoundingClientRect();
          const b = card.getBoundingClientRect();
          const covers = b.height > 0 && b.left < box.right && box.left < b.right;
          const foot = covers ? b.top : innerHeight;
          return box.height > 0 && box.top >= 0 && box.bottom <= foot + 0.5;
        }""",
        [locator.element_handle(), page.locator(".lf-fp-card").element_handle()],
    )


def pressed_send_surface(browser, serve, surface):
    """A page with words typed into `surface`'s box, and that box, the control that
    submits it, the current location once it has sent, and the reply box a follow-up
    is written in: the same box for one that stays to take more, else None."""
    if surface in {"pause", "handoff"}:
        url, host = seated_page(serve, "task" if surface == "pause" else "verdict")
        page = open_page(browser, url)
        seat = page.locator(f"{host} > .lf-thread-seat")
        box = seat.locator(":scope > .lf-say leaf-text")
        box.scroll_into_view_if_needed()
        name = "Send & pause" if surface == "pause" else "Send"
        send = seat.get_by_role("button", name=name, exact=True)
        # A seat that gives its box up leaves the user on the thread it started.
        after = box if surface == "pause" else seat.locator(":scope > .lf-page-thread")
        reply = (
            box
            if surface == "pause"
            else seat.locator(":scope > .lf-page-thread > .lf-thread-reply leaf-text")
        )
    elif surface == "composer-widget":
        url = serve(
            leaf_page(
                "diff",
                '<h1 id="title">Review</h1><lf-diff id="patch" '
                'source="review-patch"><pre></pre></lf-diff>',
            )
        )
        data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
        page = open_page(browser, url)
        line = page.locator(
            'lf-diff [data-line-type="change-addition"][data-lf-datum=\'["app.py","new",1]\']'
        )
        line.hover()
        page.get_by_role(
            "button", name="Comment on app.py · new line 1", exact=True
        ).click()
        box = page.locator(".lf-fab-input")
        send = page.locator(".lf-composer .lf-compose-submit")
        after = page.locator("lf-diff .lf-page-thread")
        reply = after.locator(".lf-thread-reply leaf-text")
    else:
        url = serve(PANEL_PAGE)
        root = panel_comment(
            serve.page_dir,
            "Where should this explanation go?",
            {"section": "how-store"},
        )
        page = open_page(browser, url)
        field = page.locator(".lf-fp-field")
        if surface == "general":
            box = page_comment(page)
            holder = field
        elif surface == "card":
            page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
            holder = page.locator(".lf-margin-preview")
            box = holder.locator(".lf-thread-reply leaf-text")
        elif surface in {"composer", "composer-panel"}:
            if surface == "composer-panel":
                open_threads(page)
            page.locator("#how-cap").click(click_count=3)
            page.locator(".lf-fab-input").click()
            holder = page.locator(".lf-composer")
            box = holder.locator("leaf-text")
        else:
            open_panel_thread(page, root)
            holder = field
            box = field.locator('leaf-text[name="reply"]')
            box.click()
        send = holder.locator(".lf-compose-submit")
        # Conversation sends land where the conversation goes on: a card's on its card,
        # the panel's in its field, a page comment opening its thread there, which the
        # field then replies in.
        reply_box = field.locator('leaf-text[name="reply"]')
        after = {
            "card": holder.locator(".lf-page-thread"),
            "composer": page.locator(".lf-margin-preview .lf-page-thread"),
            "composer-panel": page.locator(".lf-margin-preview .lf-page-thread"),
            "panel": reply_box,
            "general": reply_box,
        }[surface]
        reply = (
            page.locator(".lf-margin-preview .lf-thread-reply leaf-text")
            if surface.startswith("composer") or surface == "card"
            else reply_box
        )
    write(box, "Sent from the box.")
    rendered(page)
    return page, box, send, after, reply


CAPTURE_PAGE = leaf_page(
    "Capture a page region",
    """<h1>Capture a page region</h1>
<section id="capture-target" aria-label="Area to inspect">
  <lf-capture-art id="capture-art"></lf-capture-art>
  <p id="capture-copy">The green area and blue diagram belong to this passage.</p>
</section>""",
    head="""<style>
      #capture-target { margin-top:700px; margin-bottom:700px; position:relative;
        width:min(600px,100%); height:300px; background:rgb(10,150,30); }
      #capture-art { display:block; position:absolute; left:20px; top:30px;
        width:160px; height:100px; }
      #capture-copy { position:absolute; left:20px; right:20px; top:190px; }
    </style>""",
)


def capture_page(browser, serve, *, touch=False):
    """A scrolled passage with real SVG paint inside a declared shadow widget."""
    declaration, _ = _shadow_tree_widget("lf-capture-art")
    module = """
import {shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-capture-art', class extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '160');
    svg.setAttribute('height', '100');
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('width', '160');
    rect.setAttribute('height', '100');
    rect.setAttribute('fill', 'rgb(30,80,240)');
    svg.append(rect);
    shadowStage(this, [svg]);
  }
});
"""
    context = browser.new_context(
        viewport={"width": 390 if touch else 1200, "height": 844 if touch else 900},
        has_touch=touch,
        is_mobile=touch,
        device_scale_factor=2,
    )
    page = open_page(
        browser,
        serve(
            CAPTURE_PAGE,
            layer_registry={"lf-capture-art": declaration},
            layer_widgets={"lf-capture-art.js": module},
        ),
        context=context,
    )
    page.locator("#capture-target").scroll_into_view_if_needed()
    scroll_settled(page)
    assert page.evaluate("scrollY") > 0
    return page


def open_capture_area(page, *, touch=False):
    """Enter the screenshot tool through its ordinary page-control route: the leaf's
    menu, Annotations, Capture area, and wait for it to dim the page. It opens with no
    area drawn, inviting a drag."""
    menu = page.locator(".lf-fp-menu")
    for press in (
        page.locator(".lf-fp-leaf"),
        menu.locator('.lf-fp-item[data-row="group:annotate"]'),
        menu.locator('.lf-fp-item[data-row="command:capture.region.open"]'),
    ):
        if touch:
            press.tap()
        else:
            press.click()
    surface = page.get_by_role("region", name="Capture area", exact=True)
    expect(surface).to_be_visible()
    expect(surface.locator(".lf-region-selection")).to_be_hidden()
    return surface
