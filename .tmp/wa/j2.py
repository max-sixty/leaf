import json
import traceback

from leaf import event_log
from leaf_dev.arms import served_page

API = "async () => { window.__api = await import('/runtime/widget-api.js'); }"
OB = """() => {
  const ob = window.__api.readObligations().all.find((o) => o.source.id === 'when');
  return ob ? ob.status : null;
}"""
READ = """() => {
  const el = document.getElementById('when');
  const bar = document.getElementById('bar');
  return {
    value: el.value, state: el.state ?? null, barValue: bar.value,
    ob: window.__api.readObligations().all.find((o) => o.source.id === 'when')?.status ?? null,
    display: el.shadowRoot?.querySelector('[part~=display-input]')?.value ?? null,
    presented: document.body.getAttribute('data-lf-presented'),
  };
}"""


def actions(directory):
    return [
        (e["action"], e["detail"])
        for e in event_log.read_events(directory)
        if e["kind"] == "action"
    ]


def step(out, name):
    def wrap(work):
        try:
            out[name] = work()
        except Exception as error:  # noqa: BLE001
            out[name] = {"failed": str(error).splitlines()[0][:400]}

    return wrap


def run(page):
    served = served_page.get()
    out = {}
    page.set_default_timeout(8000)
    page.evaluate(API)

    @step(out, "1 arrival")
    def _():
        page.wait_for_function(OB, ) if False else None
        page.wait_for_timeout(800)
        return page.evaluate(READ)

    @step(out, "2 pick Friday with the mouse")
    def _():
        page.locator("#when").click()
        page.locator("wa-option[value=fri]").click()
        page.wait_for_function("() => window.__api.readObligations().all.find((o) => o.source.id === 'when')?.status === 'answered'")
        return {"read": page.evaluate(READ), "log": actions(served.directory)}

    @step(out, "3 reload shows the pick")
    def _():
        page.reload()
        page.evaluate(API)
        page.wait_for_timeout(1200)
        return page.evaluate(READ)

    @step(out, "4 undo")
    def _():
        page.locator("#p2").click()
        page.keyboard.press("ControlOrMeta+z")
        page.wait_for_timeout(800)
        return {"read": page.evaluate(READ), "log": actions(served.directory)}

    @step(out, "5 keyboard pick")
    def _():
        page.locator("#when").focus()
        page.keyboard.press("ArrowDown"); page.wait_for_timeout(300)
        page.keyboard.press("ArrowDown"); page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        return {"read": page.evaluate(READ), "log": actions(served.directory)}

    return out
