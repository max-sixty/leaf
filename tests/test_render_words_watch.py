"""The browser fixture fails the loss the "Words stay where they were typed" rule
forbids (`words_watch.js`): typed words leaving the screen without a key or press."""

import base64
from html import escape
from urllib.parse import quote

import pytest
from playwright.sync_api import expect
from render_harness import (
    consume_browser_errors,
    example_media,
    judge_watches,
    leaf_page,
    open_page,
    write,
)

# A box holding a field, on a page long enough to scroll. What the page does to the box
# when the user scrolls, presses Escape, or presses elsewhere is the page's `data-on`.
BOX = """<!doctype html><body style="margin:0">
<div id="box"><textarea id="field"></textarea></div>
<button id="elsewhere" style="position:fixed;right:0;top:0">Elsewhere</button>
<div style="height: 300vh"></div>
<script>
  const box = document.getElementById("box");
  const on = (what, act) => document.body.dataset.on === what && act();
  addEventListener("scroll", () => {
    on("scroll-hides", () => { box.style.display = "none"; });
    on("scroll-veils", () => { box.style.visibility = "hidden"; });
    on("scroll-clears", () => { document.getElementById("field").value = ""; });
    on("scroll-replaces", () => {
      const heir = document.createElement("textarea");
      heir.value = document.getElementById("field").value;
      box.replaceChildren(heir);
    });
  });
  addEventListener("keydown", (event) =>
    event.key === "Escape" && on("escape-hides", () => { box.hidden = true; }));
  document.getElementById("elsewhere").addEventListener("click", () =>
    on("press-hides", () => { box.remove(); }));
</script>"""


def box_page(browser, on):
    page = browser.new_page()
    page.goto("data:text/html," + quote(BOX))
    page.evaluate("on => { document.body.dataset.on = on; }", on)
    page.locator("#field").fill("Half a thought")
    return page


def scrolled(page):
    page.mouse.move(200, 200)
    page.mouse.wheel(0, 600)
    page.wait_for_function("() => scrollY > 0")


def test_words_a_scroll_hides_fail(browser):
    page = box_page(browser, "scroll-hides")
    scrolled(page)
    judge_watches()
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "Half a thought"'
        " in textarea#field",
    )


def test_words_a_scroll_hides_fail_after_moving_among_them(browser):
    """A press on the field and a key that moves its caret are the user moving among
    their words, not putting them away, so a scroll that hides the box after them
    still fails."""
    page = box_page(browser, "scroll-hides")
    page.locator("#field").click()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("Shift")
    scrolled(page)
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


def test_words_a_scroll_clears_fail(browser):
    page = box_page(browser, "scroll-clears")
    scrolled(page)
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


@pytest.mark.parametrize("announced", [False, True])
def test_words_a_handler_clears_in_their_own_turn_fail(browser, announced):
    """A handler that empties the field as the edit lands, and may announce that with an
    `input` of its own, has still taken the user's words."""
    announce = "field.dispatchEvent(new Event('input'));" if announced else ""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            "<textarea id=field></textarea><script>"
            "field.addEventListener('input', (event) => {"
            f" if (event.isTrusted) {{ field.value = ''; {announce} }} }});"
            "</script>"
        )
    )
    page.locator("#field").press_sequentially("x")
    judge_watches()
    consume_browser_errors(
        page, 'typed words left the screen without a key or press: "x"'
    )


@pytest.mark.parametrize(
    "operation", ["text", "cancelled", "image", "no-edit", "untrusted"]
)
def test_words_a_native_paste_observes_only_its_actual_editor_edit(
    browser, serve, operation
):
    """The closed editor's paste is an edit; unused paste cannot hide later loss."""
    page = open_page(browser, serve(leaf_page("Paste", "<h1>Paste a reply</h1>")))
    page.evaluate("""() => {
      const field = document.createElement('leaf-text');
      field.id = 'field'; document.querySelector('main').append(field);
    }""")
    field = page.locator("#field")
    write(field, "Keep these words")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    pixels = base64.b64encode(
        (example_media() / "051bee487bfb5d13.png").read_bytes()
    ).decode()
    page.evaluate(
        """async ({operation,pixels}) => {
      window.clipboardBeforeWordTest = await navigator.clipboard.read();
      if (operation === 'image') {
        const bytes = Uint8Array.from(atob(pixels), char => char.charCodeAt(0));
        await navigator.clipboard.write([new ClipboardItem({
          'image/png': new Blob([bytes], {type:'image/png'})
        })]);
      } else await navigator.clipboard.writeText('Pasted words');
      if (['cancelled','image','no-edit'].includes(operation))
        field.addEventListener('paste', event => {
          event.preventDefault(); event.stopImmediatePropagation();
          if (operation === 'image') window.pastedPicture = event.clipboardData.files.length;
          if (operation === 'no-edit') field.dispatchEvent(new Event('input', {bubbles:true}));
        }, true);
    }""",
        {"operation": operation, "pixels": pixels},
    )
    try:
        field.focus()
        page.keyboard.press("ControlOrMeta+a")
        if operation == "untrusted":
            field.evaluate("""field => {
              field.dispatchEvent(new ClipboardEvent('paste', {bubbles:true}));
            }""")
        else:
            page.keyboard.press("ControlOrMeta+v")
        expect(field).to_have_js_property(
            "value", "Pasted words" if operation == "text" else "Keep these words"
        )
        if operation == "image":
            assert page.evaluate("window.pastedPicture") == 1
        judge_watches()
        # Even the successful paste must resume watching its newly edited words.
        field.evaluate("""field => {
          field.value = ''; field.dispatchEvent(new Event('input', {bubbles:true}));
        }""")
        judge_watches()
        words = "Pasted words" if operation == "text" else "Keep these words"
        consume_browser_errors(
            page,
            f'typed words left the screen without a key or press: "{words}" in leaf-text#field',
        )
    finally:
        page.evaluate("""async () => {
          const previous = window.clipboardBeforeWordTest;
          if (previous.length) await navigator.clipboard.write(previous);
          else await navigator.clipboard.writeText('');
        }""")


def test_words_scrolled_out_of_view_stay(browser):
    page = box_page(browser, "")
    scrolled(page)
    judge_watches()


def test_words_held_out_of_view_stay(browser):
    page = box_page(browser, "scroll-veils")
    scrolled(page)
    judge_watches()


def test_words_handed_to_a_replacing_field_stay(browser):
    page = box_page(browser, "scroll-replaces")
    scrolled(page)
    judge_watches()


def test_words_escape_puts_away_are_put_away(browser):
    page = box_page(browser, "escape-hides")
    page.keyboard.press("Escape")
    judge_watches()


@pytest.mark.parametrize(
    "exit_kind",
    [
        "acknowledged",
        "ignored",
        "passive-focus",
        "tab",
        "other-field",
        "edit-after-keyup",
        "new-edit",
        "same-value-new-edit",
        "retained-editor",
        "passive-close",
        "different-value",
        "reopened-in-dispatch",
        "replaced-in-dispatch",
        "outside-press",
        "delayed-owned-close",
        "passive-focus-in-dispatch",
        "changed-chain",
        "different-value-in-dispatch",
    ],
)
def test_words_a_committed_value_editor_close_retires_only_its_exact_edit(
    browser, exit_kind
):
    """A committed native value editor close acknowledges Escape before paint.

    Hold the actual animation until explicitly finishing it: the effect may stay
    pending arbitrarily long, and neither pending work nor focus alone supplies a
    cause. A new edit starts a fresh lifetime even in the same native field.
    """
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<native-value-editor id=editor></native-value-editor>
        <textarea id=other style="position:fixed;right:0;bottom:0"></textarea>
        <script>
          editor.attachShadow({mode: 'open'}).innerHTML =
            '<div id=box><textarea id=field></textarea></div>' +
            '<button id=destination style="position:fixed;right:0;top:0">Return destination</button>';
          const {field, box, destination} = Object.fromEntries(
            ['field', 'box', 'destination'].map(id => [id, editor.shadowRoot.getElementById(id)]));
          window.destination = destination;
          window.box = box;
          editor.input = field;
          editor.open = true;
          editor.value = '';
          const passiveFocus = new Promise(resolve => { window.returnFocus = resolve; });
          passiveFocus.then(() => destination.focus());
          field.addEventListener('input', () => { editor.value = field.value; });
          const close = async () => {
            if (!['retained-editor', 'ignored'].includes(window.exitKind)) editor.open = false;
            if (window.exitKind === 'changed-chain') editor.input = other;
            if (!['ignored', 'passive-focus', 'outside-press', 'passive-focus-in-dispatch'].includes(window.exitKind))
              destination.focus();
            if (window.exitKind === 'passive-focus-in-dispatch') window.returnFocus();
            const motion = box.animate([{opacity: 1}, {opacity: 0}], {duration: 1000});
            motion.pause();
            window.closeMotion = motion;
            await motion.finished;
            box.hidden = true;
            window.closePainted = true;
          };
          field.addEventListener('keydown', event => {
            if (event.key !== 'Escape') return;
            if (window.exitKind === 'delayed-owned-close') setTimeout(close, 0);
            else close();
          });
          field.addEventListener('keydown', event => {
            if (event.key === 'Escape' && window.exitKind === 'replaced-in-dispatch') {
              const heir = document.createElement('textarea');
              heir.id = 'heir'; heir.value = field.value;
              field.replaceWith(heir); editor.input = heir;
            }
            if (event.key === 'Escape' && window.exitKind === 'reopened-in-dispatch')
              editor.open = true;
            if (event.key === 'Escape' && window.exitKind === 'different-value-in-dispatch')
              editor.value = '';
          });
          destination.addEventListener('mousedown', () => {
            if (window.exitKind === 'outside-press') close();
          });
        </script>""")
    )
    page.evaluate("kind => window.exitKind = kind", exit_kind)
    if exit_kind == "other-field":
        page.locator("#other").fill("Another edit stays mine")
    page.locator("#field").fill("Keep these words")
    if exit_kind == "passive-close":
        page.evaluate("editor.open = false")
        judge_watches()
    if exit_kind == "different-value":
        page.evaluate("editor.value = 'A different committed value'")
    if exit_kind == "tab":
        page.locator("#field").press("Tab")
        expect(page.locator("#destination")).to_be_focused()
        page.evaluate("box.hidden = true")
    else:
        if exit_kind == "outside-press":
            page.locator("#destination").click()
        else:
            page.locator("#field").press("Escape")
        page.wait_for_function("window.closeMotion?.playState === 'paused'")
        shown_field = page.locator(
            "#heir" if exit_kind == "replaced-in-dispatch" else "#field"
        )
        expect(shown_field).to_be_visible()
        expect(shown_field).to_have_value("Keep these words")
        if exit_kind == "edit-after-keyup":
            page.locator("#other").fill("Another edit stays mine")
        judge_watches()
        assert not page.evaluate("window.closePainted === true")
        if exit_kind == "passive-focus":
            page.evaluate("destination.focus()")
        if exit_kind in {"other-field", "edit-after-keyup"}:
            page.evaluate("other.remove()")
            judge_watches()
            consume_browser_errors(
                page,
                "typed words left the screen without a key or press: "
                '"Another edit stays mine" in textarea#other',
            )
        if exit_kind in {"new-edit", "same-value-new-edit"}:
            page.locator("#field").fill(
                "Keep these words"
                if exit_kind == "same-value-new-edit"
                else "A new editing lifetime"
            )
        page.evaluate("closeMotion.finish()")
        page.wait_for_function("window.closePainted === true")
    judge_watches()
    if exit_kind not in {
        "acknowledged",
        "other-field",
        "edit-after-keyup",
        "outside-press",
        "delayed-owned-close",
        "passive-focus",
        "passive-focus-in-dispatch",
    }:
        words = (
            "A new editing lifetime" if exit_kind == "new-edit" else "Keep these words"
        )
        field_id = "heir" if exit_kind == "replaced-in-dispatch" else "field"
        consume_browser_errors(
            page,
            f'typed words left the screen without a key or press: "{words}" in textarea#{field_id}',
        )


def test_words_a_press_elsewhere_puts_away_are_put_away(browser):
    page = box_page(browser, "press-hides")
    page.locator("#elsewhere").click()
    judge_watches()


def test_words_a_passive_selection_change_cannot_close_a_draft(browser):
    """A programmatic selection cannot put away words held in another field."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<textarea id=field></textarea><p id=passage>A partial word remains selected.</p>
          <script>
          window.selectPassage = () => {
            getSelection().setBaseAndExtent(passage.firstChild, 3, passage.firstChild, 14);
          };
          document.addEventListener('selectionchange', () => {
            if (getSelection().isCollapsed) return;
            window.selectedWords = getSelection().toString();
            field.value = '';
          });
          </script>""")
    )
    page.locator("#field").fill("Half a thought")
    page.evaluate("selectPassage()")
    expect(page.locator("#field")).to_have_value("")
    assert page.evaluate("window.selectedWords") == "artial word"
    judge_watches()
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "Half a thought"'
        " in textarea#field",
    )


@pytest.mark.parametrize("route", ["press", "keyboard"])
@pytest.mark.parametrize("shadow", [False, True])
def test_words_a_native_disclosure_puts_away_its_fields(browser, route, shadow):
    field = (
        '<div id="host"></div><script>'
        'host.attachShadow({mode:"open"}).innerHTML="<textarea id=field></textarea>";'
        "</script>"
        if shadow
        else '<textarea id="field"></textarea>'
    )
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            f"<details open><summary><strong>Fold</strong></summary>{field}</details>"
        )
    )
    page.locator("#field").fill("Keep my words")
    summary = page.locator("summary")
    if route == "press":
        summary.click()
    else:
        summary.focus()
        page.keyboard.press("Enter")
    assert not page.locator("details").evaluate("details => details.open")
    judge_watches()


@pytest.mark.parametrize("during_press", [False, True])
def test_words_a_prevented_disclosure_press_cannot_own_a_passive_close(
    browser, during_press
):
    close_during_press = (
        "await Promise.resolve(); closeDetails();" if during_press else ""
    )
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<details open><summary>Fold</summary><textarea id=field></textarea></details>
        <script>
          document.querySelector('summary').onclick = async event => {{
            event.preventDefault(); {close_during_press}
          }};
          window.closeDetails = () => {{ document.querySelector('details').open = false; }};
        </script>""")
    )
    page.locator("#field").fill("Keep my words")
    page.locator("summary").click()
    if not during_press:
        assert page.locator("details").evaluate("details => details.open")
        page.evaluate("closeDetails()")
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


def test_words_a_native_disclosure_cannot_own_passive_loss_outside_it(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<textarea id=field></textarea><details open><summary>Fold</summary>Earlier</details>
        <script>
          document.querySelector('summary').onclick = async () => {
            await Promise.resolve();
            field.value = '';
          };
        </script>""")
    )
    page.locator("#field").fill("Keep my words")
    page.locator("summary").click()
    assert not page.locator("details").evaluate("details => details.open")
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


def test_words_a_control_in_a_summary_cannot_own_a_passive_disclosure_close(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<details open><summary>Fold <button id=other>Other</button></summary>
        <textarea id=field></textarea></details>
        <script>
          other.onclick = async () => {
            await Promise.resolve();
            document.querySelector('details').open = false;
          };
        </script>""")
    )
    page.locator("#field").fill("Keep my words")
    page.locator("#other").click()
    assert not page.locator("details").evaluate("details => details.open")
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


def test_words_a_later_listener_can_cancel_native_disclosure_activation(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<details open><summary>Fold</summary><textarea id=field></textarea></details>
        <script>
          const summary = document.querySelector('summary');
          summary.addEventListener('click', async () => {
            await Promise.resolve();
            document.querySelector('details').open = false;
          });
          summary.addEventListener('click', event => event.preventDefault());
        </script>""")
    )
    page.locator("#field").fill("Keep my words")
    page.locator("summary").click()
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


def test_words_a_press_in_the_page_holding_their_frame_puts_away_are_put_away(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            "<iframe srcdoc='<textarea id=field></textarea>'></iframe>"
            "<button id='clear' onclick=\""
            "frames[0].document.getElementById('field').remove()"
            '">Clear</button>'
        )
    )
    page.frame_locator("iframe").locator("#field").fill("Half a thought")
    page.locator("#clear").click()
    judge_watches()


@pytest.mark.parametrize("continuation", ["captured", "native-await", "passive"])
def test_words_child_work_reads_its_executing_parent_owner(browser, continuation):
    child = """<textarea id=field></textarea><script>
      const passive = lfInputWork.capture(() => { field.value = ''; });
      window.clearLater = () => setTimeout(() => { field.value = ''; }, 0);
      window.clearPassive = () => Promise.resolve().then(passive);
    </script>"""
    method = "clearPassive" if continuation == "passive" else "clearLater"
    call = f"frames[0].{method}()"
    action = (
        f"async () => {{ await Promise.resolve(); {call}; }}"
        if continuation == "native-await"
        else f"() => Promise.resolve().then(() => {call})"
    )
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            f"<iframe srcdoc='{escape(child)}'></iframe><button id=clear>Clear</button>"
            f"<script>clear.onclick = {action};</script>"
        )
    )
    field = page.frame_locator("iframe").locator("#field")
    field.fill("Keep my words")
    page.locator("#clear").click()
    expect(field).to_have_value("")
    judge_watches()
    if continuation != "captured":
        consume_browser_errors(
            page, "typed words left the screen without a key or press"
        )


@pytest.mark.parametrize("passive_middle", [False, True])
def test_words_a_middle_frame_can_seal_its_parent_callback(browser, passive_middle):
    child = """<textarea id=field></textarea><script>
      window.clearLater = () => setTimeout(() => { field.value = ''; }, 0);
    </script>"""
    clear = "() => frames[0].clearLater()"
    if passive_middle:
        clear = f"lfInputWork.capture({clear})"
    middle = (
        f"<iframe srcdoc='{escape(child)}'></iframe>"
        f"<script>window.clearChild = {clear};</script>"
    )
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            f"<iframe srcdoc='{escape(middle)}'></iframe><button id=clear>Clear</button>"
            "<script>clear.onclick = () => Promise.resolve().then(() => frames[0].clearChild());</script>"
        )
    )
    field = page.frame_locator("iframe").frame_locator("iframe").locator("#field")
    field.fill("Keep my words")
    page.locator("#clear").click()
    expect(field).to_have_value("")
    judge_watches()
    if passive_middle:
        consume_browser_errors(
            page, "typed words left the screen without a key or press"
        )


@pytest.mark.parametrize(
    "scene",
    [
        "owned",
        "passive-host",
        "passive-native",
        "passive-before-press",
        "newer-edit",
        "different-paint",
        "select-filter",
    ],
)
def test_words_a_component_value_edge_needs_its_own_matching_paint(browser, scene):
    native_field = "selected" if scene == "select-filter" else "field"
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<div id=control></div><button id=clear>Clear</button><button id=other>Other</button>
        <script>
          const shadow = control.attachShadow({{mode:'open'}});
          shadow.innerHTML = '<input id=field><input id=selected type=hidden>';
          const field = shadow.querySelector('#field');
          control.input = shadow.querySelector('#{native_field}');
          let value = '';
          Object.defineProperty(control, 'value', {{ get: () => value, set: next => {{ value = next; }} }});
          field.addEventListener('input', () => {{ value = field.value; }});
          clear.onclick = () => {{ control.value = ''; }};
          window.paint = () => {{ field.value = control.value; }};
        </script>""")
    )
    field = page.locator("#field")
    field.fill("Keep my words")
    if scene in {"owned", "newer-edit", "different-paint", "select-filter"}:
        page.locator("#clear").click()
        expect(field).to_have_value("Keep my words")
        assert page.locator("#control").evaluate("host => host.value") == ""
        judge_watches()
        assert page.lf_errors == []
    if scene == "newer-edit":
        field.fill("My newer words")
    if scene in {"passive-host", "passive-before-press", "newer-edit"}:
        page.evaluate("control.value = ''")
        judge_watches()
    if scene == "passive-before-press":
        page.locator("#other").click()
    if scene == "passive-native":
        field.evaluate("field => { field.value = ''; }")
    elif scene == "different-paint":
        field.evaluate("field => { field.value = 'Different words'; }")
    else:
        page.evaluate("paint()")
    judge_watches()
    if scene != "owned":
        consume_browser_errors(
            page, "typed words left the screen without a key or press"
        )


@pytest.mark.parametrize(
    "attempt",
    [
        "single-line",
        "cancelled",
        "actual-edit",
        "passive",
        "new-edit",
        "same-value-new-edit",
        "cancelled-typing",
        "cancelled-commit",
    ],
)
def test_words_an_input_attempt_needs_an_actual_edit_to_replace_its_words(
    browser, attempt
):
    """A native no-op cannot replace the edit or revoke its earlier value commit."""
    native = "textarea" if attempt == "actual-edit" else "input"
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<div id=control></div><script>
      const shadow = control.attachShadow({{mode:'open'}});
      shadow.innerHTML = '<{native} id=field></{native}>';
      const field = shadow.querySelector('#field');
      control.input = field; control.value = '';
      field.addEventListener('input', () => {{
        if (!['new-edit', 'same-value-new-edit'].includes('{attempt}') || control.value !== 'CANONICAL') control.value = field.value;
      }});
      field.addEventListener('keydown', event => {{
        if (event.key === ('{attempt}' === 'cancelled-commit' ? 'x' : 'Enter') && '{attempt}' !== 'passive') control.value = 'CANONICAL';
        if (event.key === 'x' && '{attempt}' === 'cancelled-commit') setTimeout(() => {{field.value = control.value;window.painted = true;}}, 0);
        if (event.key === 'x' && '{attempt}' === 'cancelled-typing') setTimeout(() => {{field.value = '';window.cleared = true;}}, 0);
      }});
      field.addEventListener('beforeinput', event => {{
        if (('{attempt}' === 'cancelled' && event.inputType === 'insertLineBreak') || (['cancelled-typing', 'cancelled-commit'].includes('{attempt}') && event.data === 'x')) event.preventDefault();
      }});
      window.paint = () => {{field.value = 'CANONICAL';}};
    </script>""")
    )
    field = page.locator("#field")
    field.fill("Typed words")
    if attempt in {"cancelled-typing", "cancelled-commit"}:
        field.press("x")
        page.wait_for_function(
            "window.cleared === true"
            if attempt == "cancelled-typing"
            else "window.painted === true"
        )
    else:
        field.press("Enter")
        judge_watches()
        if attempt in {"new-edit", "same-value-new-edit"}:
            field.fill(
                "Typed words" if attempt == "same-value-new-edit" else "New words"
            )
            assert (
                page.locator("#control").evaluate("host => host.value") == "CANONICAL"
            )
        page.evaluate("paint()")
    judge_watches()
    if attempt in {
        "actual-edit",
        "passive",
        "new-edit",
        "same-value-new-edit",
        "cancelled-typing",
        "cancelled-commit",
        "cancelled",
    }:
        consume_browser_errors(
            page, "typed words left the screen without a key or press"
        )


def test_words_redirected_native_typing_does_not_put_away_another_edit(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<textarea id=field></textarea><textarea id=other></textarea>
    <script>
    field.addEventListener('keydown', event => {
      if(event.key !== 'x') return;
      other.focus();
      setTimeout(() => {field.value = '';window.cleared=true},0);
    });
    </script>""")
    )
    page.locator("#field").fill("Keep old field")
    page.locator("#field").press("x")
    page.wait_for_function("window.cleared === true")
    assert page.locator("#other").input_value() == "x"
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


def test_words_a_new_gesture_supersedes_a_held_key_without_revoking_its_owned_close(
    browser,
):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""
<native-value-editor id=editor></native-value-editor><textarea id=other style="position:fixed;right:0;bottom:0"></textarea>
<script>
editor.attachShadow({mode:'open'}).innerHTML = '<textarea id=field></textarea>';
const field = editor.shadowRoot.querySelector('#field');
editor.input = field; editor.open = true; editor.value = '';
field.addEventListener('input', () => editor.value = field.value);
field.addEventListener('keydown', async event => {
  if (event.key !== 'Escape') return;
  const commit = lfInputWork.capture(() => {editor.open = false; window.reviewCloseCommitted = true;});
  await new Promise(resolve => window.beginClose = resolve);
  commit();
  await new Promise(resolve => window.finishClose = resolve);
  field.hidden = true; window.painted = true;
});
</script>""")
    )
    page.locator("#field").fill("Original committed words")
    page.locator("#field").focus()
    page.keyboard.down("Escape")
    page.locator("#other").click()
    page.locator("#other").fill("Other new edit stays watched")
    page.keyboard.up("Escape")
    page.evaluate("beginClose()")
    page.wait_for_function("window.reviewCloseCommitted === true")
    judge_watches()
    page.evaluate("finishClose()")
    page.wait_for_function("window.painted === true")
    judge_watches()
    page.locator("#other").evaluate('field => field.value = ""')
    judge_watches()
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "Other new edit stays watched" in textarea#other',
    )


@pytest.mark.parametrize("delay", [300, 3000])
def test_words_a_slow_send_retains_its_input(browser, delay):
    """The same native Send timer owns its effect at 1x and 10x latency. A real
    completion flag bounds the wait; the delay is not a correctness assertion."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<textarea id=field></textarea><button id=send style="position:fixed;right:0;top:0">Send</button><script>'
            f"send.onclick=()=>setTimeout(()=>{{field.remove();window.done=true}},{delay});"
            "</script>"
        )
    )
    page.locator("#field").fill("Preserve this draft")
    page.locator("#send").click()
    page.wait_for_function("window.done === true")
    judge_watches()


@pytest.mark.parametrize("scheduler", ["nextRender", "afterScript", "presenter"])
@pytest.mark.parametrize("order", ["passive-first", "input-first"])
def test_coalesced_rendering_jobs_keep_their_own_input_source(
    browser, serve, scheduler, order
):
    """One pass may contain input and passive jobs; neither lends the other its cause."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Rendering job input ownership",
                '<textarea id="native"></textarea><textarea id="passive"></textarea>'
                '<button id="send">Put my words away</button>',
            )
        ),
    )
    page.evaluate(
        """async ({scheduler,order}) => {
          const module=await __lfRuntimeImport('/runtime/rendering.js');
          let schedule=module[scheduler];
          if(scheduler==='presenter') {
            const {bindQueuedWork}=await __lfRuntimeImport('/runtime/queued-work.js');
            const {createPresentationSchedule}=await __lfRuntimeImport('/vendor/browser-runtime.js');
            const presentations=createPresentationSchedule(bindQueuedWork);
            schedule=callback=>presentations.presenter({attach:()=>null,paint:callback}).sync(null);
          }
          const passive=lfInputWork.capture(()=>schedule(()=>{
            document.getElementById('passive').remove();window.passiveDone=true;
          }));
          document.getElementById('send').onclick=()=>{
            if(order==='passive-first')passive();
            schedule(()=>{document.getElementById('native').remove();window.nativeDone=true;});
            if(order==='input-first')passive();
          };
        }""",
        {"scheduler": scheduler, "order": order},
    )
    page.locator("#native").fill("Words deliberately put away")
    page.locator("#passive").fill("Words lost without permission")
    page.locator("#send").click()
    page.wait_for_function("window.nativeDone && window.passiveDone")
    judge_watches()
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "Words lost without permission"',
    )


@pytest.mark.parametrize("scheduler", ["nextRender", "presenter"])
def test_a_rendering_jobs_returned_async_tail_stays_passive(browser, serve, scheduler):
    """A rendering callback's synchronous turn ends before its uncaptured native await."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native rendering tail",
                '<textarea id="field" style="position:absolute;left:40px;top:100px"></textarea><button id="send" style="position:fixed;right:0;top:100px">Send</button>',
            )
        ),
    )
    page.evaluate(
        """async scheduler => {
      const {nextRender}=await __lfRuntimeImport('/runtime/rendering.js');
      let schedule=nextRender;
      if(scheduler==='presenter') {
        const {bindQueuedWork}=await __lfRuntimeImport('/runtime/queued-work.js');
        const {createPresentationSchedule}=await __lfRuntimeImport('/vendor/browser-runtime.js');
        const presentations=createPresentationSchedule(bindQueuedWork);
        schedule=callback=>presentations.presenter({attach:()=>null,paint:callback}).sync(null);
      }
      document.getElementById('send').onclick=()=>schedule(async()=>{
        await new Promise(resolve=>window.finishTail=resolve);
        document.getElementById('field').remove();window.done=true;
      });
    }""",
        scheduler,
    )
    page.locator("#field").fill("This awaited work has no input owner")
    page.locator("#send").click()
    page.wait_for_function("typeof window.finishTail === 'function'")
    judge_watches()
    page.evaluate("finishTail()")
    page.wait_for_function("window.done === true")
    judge_watches()
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "This awaited work has no input owner"',
    )


def test_words_a_held_interval_send_retains_its_input(browser):
    """A repeating timer retains the Send that schedules it until its held commit,
    and native cancellation stops the interval after that commit."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""
          <textarea id=field></textarea><button id=send style="position:fixed;right:0;top:0">Send</button><script>
          send.onclick = () => {
            const interval = setInterval(() => {
              window.waiting = true;
              if (!window.releaseSend) return;
              clearInterval(interval);
              field.remove();
              window.done = true;
            }, 0);
          };
          </script>""")
    )
    page.locator("#field").fill("Preserve this draft")
    page.locator("#send").click()
    page.wait_for_function("window.waiting === true")
    judge_watches()
    page.evaluate("window.releaseSend = true")
    page.wait_for_function("window.done === true")
    judge_watches()


def test_words_unrelated_work_during_a_send_still_fails(browser):
    """A passive callback registered before the press cannot borrow the input from
    that press's held completion. Releasing the two operations orders the race."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""
          <textarea id=field></textarea><button id=send style="position:fixed;right:0;top:0">Send</button><script>
          const passive = new Promise(resolve => window.loseWords = resolve);
          passive.then(() => { field.remove(); window.lost = true; });
          send.onclick = async () => {
            window.sending = true;
            await new Promise(resolve => window.completeSend = resolve);
            window.done = true;
          };
          </script>""")
    )
    page.locator("#field").fill("Preserve this draft")
    page.locator("#send").click()
    page.wait_for_function("window.sending === true")
    page.evaluate("loseWords()")
    page.wait_for_function("window.lost === true")
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")
    page.evaluate("completeSend()")
    page.wait_for_function("window.done === true")


def test_words_a_press_can_put_them_away_before_release(browser):
    """The pointerdown owns a close even when its target is removed and no click
    will arrive. Hold the actual release instead of waiting for a click time window."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""
          <div id=box><textarea id=field></textarea>
          <button id=close>Close</button></div><script>
          document.getElementById('close').addEventListener('pointerdown', () => {
            box.remove(); window.closedByPress = true;
          });
          </script>""")
    )
    page.locator("#field").fill("Preserve this draft")
    bounds = page.locator("#close").bounding_box()
    assert bounds is not None
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    )
    page.mouse.down()
    page.wait_for_function("window.closedByPress === true")
    judge_watches()
    page.mouse.up()


def test_words_passive_loss_after_a_completed_press_still_fails(browser):
    page = box_page(browser, "")
    page.locator("#elsewhere").click()
    judge_watches()
    page.evaluate("box.remove()")
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


def test_words_restored_after_a_replacement_gap_remain_watched(browser):
    """A callback can briefly remove a field and restore its words in a microtask.
    The restoration keeps the watch, so a subsequent passive loss still fails."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""
          <textarea id=field></textarea>
          <button id=replace style="position:fixed;right:0;top:0">Replace</button>
          <script>
          replace.onclick = () => {
            const words = field.value;
            field.remove();
            queueMicrotask(() => {
              const heir = document.createElement('textarea');
              heir.id = 'field'; heir.value = words;
              document.body.prepend(heir);
              window.restored = true;
            });
          };
          </script>""")
    )
    page.locator("#field").fill("Preserve this draft")
    page.locator("#replace").click()
    page.wait_for_function("window.restored === true")
    judge_watches()
    page.evaluate("field.remove()")
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


def test_words_editing_updates_the_words_still_watched(browser):
    page = box_page(browser, "")
    page.locator("#field").press_sequentially(" continued")
    page.locator("#field").press("Backspace")
    judge_watches()
    page.evaluate("box.remove()")
    judge_watches()
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "Half a thought continue"',
    )


@pytest.mark.parametrize("registration", ["listener", "property", "attribute"])
def test_words_an_async_send_owns_its_completion(browser, registration):
    """Native await does not call patched Promise.then. Capture the committing
    callback during the input, so its effect has an exact owner after the await."""
    handler = "async function () { const commit = lfInputWork.capture(() => { field.remove(); window.done = true; }); await new Promise(resolve => window.completeSend = resolve); commit(); }"
    if registration == "listener":
        bind = f"send.addEventListener('click', {handler});"
        attribute = ""
    elif registration == "property":
        bind = f"window.sendHandler = {handler}; send.onclick = window.sendHandler;"
        attribute = ""
    else:
        bind = ""
        attribute = (
            ' onclick="return (async () => {'
            "const commit = lfInputWork.capture(() => {field.remove(); window.done = true;});"
            'await new Promise(resolve => window.completeSend = resolve); commit();})()"'
        )
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            "<textarea id=field></textarea><button id=send "
            f'style="position:fixed;right:0;top:0"{attribute}>Send</button>'
            f"<script>{bind}</script>"
        )
    )
    if registration == "property":
        assert page.evaluate("send.onclick === window.sendHandler")
    page.locator("#field").fill("Preserve this draft")
    page.locator("#send").click()
    if registration == "property":
        assert page.evaluate("send.onclick === window.sendHandler")
    page.wait_for_function("typeof window.completeSend === 'function'")
    judge_watches()
    page.evaluate("completeSend()")
    page.wait_for_function("window.done === true")
    judge_watches()


def test_words_an_async_send_can_put_words_away_before_its_last_await(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""
      <textarea id=field></textarea>
      <button id=send style="position:fixed;right:0;top:0">Send</button>
      <script>
      send.onclick = async () => {
        const commit = lfInputWork.capture(() => { field.remove(); window.removed = true; });
        await new Promise(resolve => window.releaseFirst = resolve);
        commit();
        await new Promise(resolve => window.releaseLast = resolve);
        window.done = true;
      };
      </script>""")
    )
    page.locator("#field").fill("Preserve this draft")
    page.locator("#send").click()
    judge_watches()
    page.evaluate("releaseFirst()")
    page.wait_for_function("window.removed === true")
    judge_watches()
    page.evaluate("releaseLast()")
    page.wait_for_function("window.done === true")
    judge_watches()


def test_words_a_passive_async_commit_cannot_borrow_a_waiting_send(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""
      <textarea id=field></textarea>
      <button id=send style="position:fixed;right:0;top:0">Send</button>
      <script>
      const passiveCommit = lfInputWork.capture(() => { field.remove(); window.lost = true; });
      (async () => {
        await new Promise(resolve => window.releasePassive = resolve);
        passiveCommit();
        await new Promise(resolve => window.finishPassive = resolve);
        window.passiveDone = true;
      })();
      send.onclick = async () => {
        const commit = lfInputWork.capture(() => { window.done = true; });
        await new Promise(resolve => window.completeSend = resolve);
        commit();
      };
      </script>""")
    )
    page.locator("#field").fill("Preserve this draft")
    page.locator("#send").click()
    judge_watches()
    page.evaluate("releasePassive()")
    page.wait_for_function("window.lost === true")
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")
    page.evaluate("completeSend()")
    page.wait_for_function("window.done === true")
    assert not page.evaluate("window.passiveDone === true")
    page.evaluate("finishPassive()")
    page.wait_for_function("window.passiveDone === true")
    judge_watches()


@pytest.mark.parametrize("deferred", [False, True])
def test_words_a_native_passive_await_stays_passive_inside_a_press(browser, deferred):
    """A native await can resume between listeners while eventPhase still says click.
    That is not the handler's execution context, even if it schedules another timer."""
    effect = (
        "setTimeout(() => { field.remove(); window.lost = true; }, 0)"
        if deferred
        else "field.remove(); window.lost = true;"
    )
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<textarea id=field></textarea><button id=send style="position:fixed;right:0;top:0">Send</button>'
            "<script>(async () => { await new Promise(resolve => window.releasePassive = resolve);"
            f"{effect} }})(); "
            "send.onclick = async () => {releasePassive(); await new Promise(resolve => window.completeSend = resolve);window.done = true;};"
            "</script>"
        )
    )
    page.locator("#field").fill("Preserve this draft")
    page.locator("#send").click()
    page.wait_for_function("window.lost === true")
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")
    page.evaluate("completeSend()")
    page.wait_for_function("window.done === true")


# A reactive element in the shape Lit gives one: `requestUpdate` starts an update that a
# native `await` defers to `scheduleUpdate`, and the first update, requested while the
# element is constructed, waits for it to be connected. Its value is drawn into a field
# in its shadow tree, as a Web Awesome input draws the Threads search. Escape clears the
# host's value; `k` makes an element whose first update clears it, which a passive
# timer later connects; and a passive timer, armed when the page loads, clears it on cue.
REACTIVE = """<!doctype html><body>
<reactive-field id="host"></reactive-field><button id="elsewhere">Elsewhere</button>
<script>
  class ReactiveField extends HTMLElement {
    isUpdatePending = false;
    hasUpdated = false;
    #value = "";
    #enable = null;
    #enabled = new Promise((resolve) => (this.#enable = resolve));
    constructor() {
      super();
      this.attachShadow({ mode: "open" }).innerHTML = '<input id="inner">';
      this.shadowRoot.firstChild.addEventListener("input", (event) => {
        this.#value = event.target.value;
      });
      this.requestUpdate();
    }
    connectedCallback() { this.#enable(); }
    get value() { return this.#value; }
    set value(next) { this.#value = next; this.requestUpdate(); }
    requestUpdate() {
      if (this.isUpdatePending) return;
      this.isUpdatePending = true;
      this.updated = this.enqueueUpdate();
    }
    async enqueueUpdate() {
      await this.#enabled;
      this.scheduleUpdate();
    }
    scheduleUpdate() {
      this.isUpdatePending = false;
      const first = !this.hasUpdated;
      this.hasUpdated = true;
      this.shadowRoot.firstChild.value = this.#value;
      if (first && this.dataset.clears)
        document.getElementById(this.dataset.clears).value = "";
      if (!first && this.id === "host") window.cleared = this.#value === "";
    }
  }
  customElements.define("reactive-field", ReactiveField);
  addEventListener("keydown", (event) => {
    if (event.key === "Escape") document.getElementById("host").value = "";
    if (event.key === "k") {
      window.made = document.createElement("reactive-field");
      made.dataset.clears = "host";
    }
  });
  window.connectPassively = () => setTimeout(() => document.body.append(made), 0);
  new Promise((resolve) => (window.releasePassive = resolve)).then(() => {
    setTimeout(() => { document.getElementById("host").value = ""; }, 0);
  });
</script>"""


def reactive_page(browser):
    page = browser.new_page()
    page.goto("data:text/html," + quote(REACTIVE))
    page.locator("#inner").fill("Half a thought")
    return page


def test_words_a_reactive_update_a_key_requested_is_that_keys(browser):
    """An element's update that a key requested belongs to that key, though the element
    defers it behind a native `await`: the key put the words away."""
    page = reactive_page(browser)
    page.keyboard.press("Escape")
    page.wait_for_function("window.cleared === true")
    judge_watches()


@pytest.mark.parametrize("cause", ["released", "connected"])
def test_words_a_reactive_update_nothing_requested_still_fails(browser, cause):
    """The same deferred update, requested by work no input caused, loses the words.
    So does an element's first update when a key made the element and passive work
    connected it later: that update runs when it is connected, not when it was made."""
    page = reactive_page(browser)
    if cause == "released":
        page.evaluate("releasePassive()")
    else:
        page.locator("#elsewhere").focus()
        page.keyboard.press("k")
        page.wait_for_function("window.made !== undefined")
        page.evaluate("connectPassively()")
    page.wait_for_function("window.cleared === true")
    judge_watches()
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "Half a thought"'
        " in input#inner in shadow of reactive-field#host",
    )
