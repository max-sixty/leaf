"""The browser fixture fails the loss the "Words stay where they were typed" rule
forbids (`words_watch.js`): typed words leaving the screen without a key or press."""

from urllib.parse import quote

import pytest
from render_harness import consume_browser_errors, judge_watches

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


def test_words_a_press_elsewhere_puts_away_are_put_away(browser):
    page = box_page(browser, "press-hides")
    page.locator("#elsewhere").click()
    judge_watches()


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
