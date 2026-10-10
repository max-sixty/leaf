"""Exact browser-input causes at native dispatch boundaries."""

from html import escape
from urllib.parse import quote

import pytest
from render_harness import consume_browser_errors, judge_watches, leaf_page, open_page


def test_nested_input_bridges_report_each_creation_once(browser):
    """An instrumented parent already forwards the rest of the input ancestry."""
    child_source = """<!doctype html><script>
      window.inputTypes = [];
      lfInputWork.subscribeInputs(source => inputTypes.push(source.event.type));
    </script>"""
    middle_source = f'<iframe srcdoc="{escape(child_source, quote=True)}"></iframe>'
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<button id="press">Press</button>'
            f'<iframe srcdoc="{escape(middle_source, quote=True)}"></iframe>'
        )
    )
    child = page.frames[-1]
    child.wait_for_function("window.inputTypes !== undefined")
    page.locator("#press").click()
    assert child.evaluate("inputTypes.filter(type => type === 'click').length") == 1


@pytest.mark.parametrize("native_input", [True, False])
def test_native_dialog_cancel_owns_its_callback_but_script_request_close_does_not(
    browser, native_input
):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body>
        <dialog><button>Return</button></dialog>
        <div id="above"></div><button id="reader">Continue reading</button>
        <script>
          const dialog = document.querySelector('dialog');
          dialog.addEventListener('cancel', event => {
            window.cancelSource = lfInputWork.current()?.event.type ?? null;
            event.preventDefault();
            dialog.close();
            Promise.resolve().then(() => {
              document.querySelector('#above').style.height = '80px';
            });
          });
          dialog.showModal();
        </script>""")
    )
    page.screenshot()
    if native_input:
        page.keyboard.press("Escape")
        assert page.evaluate("cancelSource") == "cancel"
    else:
        page.locator("dialog").evaluate("dialog => dialog.requestClose()")
        assert page.evaluate("cancelSource") is None
    page.screenshot()
    judge_watches()
    if not native_input:
        consume_browser_errors(page, "moved without input")


def test_a_borrowed_request_close_cannot_mint_input_in_the_receiving_document(browser):
    """A trusted cancel caused by foreign script retains the script's passive cause."""
    page = browser.new_page()
    child_source = """<!doctype html><body>
      <dialog><button>Return</button></dialog>
      <div id="above"></div><button id="reader">Continue reading</button>
      <script>
        const dialog = document.querySelector('dialog');
        dialog.addEventListener('cancel', event => {
          window.cancelSource = lfInputWork.current()?.event.type ?? null;
          event.preventDefault();
          dialog.close();
          document.querySelector('#above').style.height = '80px';
        });
        dialog.showModal();
      </script>"""
    page.goto(
        "data:text/html,"
        + quote(f'<iframe srcdoc="{escape(child_source, quote=True)}"></iframe>')
    )
    child = page.frames[1]
    child.locator("dialog").wait_for(state="visible")
    judge_watches()
    page.evaluate("""() => {
      const dialog = document.querySelector('iframe').contentDocument.querySelector('dialog');
      HTMLDialogElement.prototype.requestClose.call(dialog);
    }""")
    assert child.evaluate("cancelSource") is None
    page.screenshot()
    judge_watches()
    consume_browser_errors(page, "moved without input")


@pytest.mark.parametrize("cause", ["click", "cancel", "passive"])
def test_delayed_opaque_document_command_owns_only_its_actual_input(
    browser, serve, cause
):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Private document input",
                """<button id="move">Move the child control</button>
<dialog id="cancel"><button>Return</button></dialog>
<lf-sample id="practice"><template id="practice-source" data-sample>
  <div id="above"></div><button id="reader">Continue reading</button>
</template></lf-sample>""",
            )
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    child.evaluate("""async () => {
      const {registerSampleCommand} = await __lfRuntimeImport('/runtime/sample-child.js');
      registerSampleCommand('move-control', () => {
        window.commandSource = lfInputWork.current()?.event.type ?? null;
        document.querySelector('#above').style.height = '80px';
      });
    }""")
    page.evaluate("""() => {
      const port = document.querySelector('script[data-lf-entry]').lfDocumentPort;
      const send = () => port.postMessage({id:999999,method:'move-control',detail:{}});
      window.passive = lfInputWork.capture(send);
      document.querySelector('#move').onclick = () => {
        window.deliver = lfInputWork.capture(send);
      };
      document.querySelector('#cancel').addEventListener('cancel', event => {
        event.preventDefault();
        event.target.close();
        window.deliver = lfInputWork.capture(send);
      });
    }""")
    if cause == "cancel":
        page.locator("#cancel").evaluate("dialog => dialog.showModal()")
        page.keyboard.press("Escape")
    else:
        page.locator("#move").click()
    # Finish every paint from the original dispatch before its callback crosses
    # the port. No nearby-input time window can answer this delayed command.
    judge_watches()
    page.evaluate("passive()" if cause == "passive" else "deliver()")
    child.wait_for_function("window.commandSource !== undefined")
    assert child.evaluate("commandSource") == (None if cause == "passive" else cause)
    page.screenshot()
    judge_watches()
    if cause == "passive":
        consume_browser_errors(page, "moved without input")
