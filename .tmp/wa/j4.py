from leaf import event_log
from leaf_dev.arms import served_page

LOG = """() => (window.__changes = window.__changes ?? [])"""


def run(page):
    served = served_page.get()
    out = {}
    page.set_default_timeout(8000)
    page.wait_for_timeout(1200)
    page.evaluate("""() => { window.__c = []; const w = document.getElementById('when');
      for (const t of ['change','input','lf-action']) w.addEventListener(t, (e) => window.__c.push(t + ':' + w.value)); }""")

    def acts():
        return [e["detail"] for e in event_log.read_events(served.directory) if e["kind"] == "action"]

    def pick(name):
        page.locator("#when").click()
        page.wait_for_timeout(300)
        page.locator(f"wa-option[value={name}]").click()
        page.wait_for_timeout(600)

    pick("fri")
    out["first"] = [page.evaluate("() => window.__c"), acts()]
    page.locator("#p2").click()
    page.keyboard.press("ControlOrMeta+z")
    page.wait_for_timeout(600)
    out["undone"] = [page.evaluate("() => document.getElementById('when').value"), acts()]
    page.evaluate("() => { window.__c = []; }")
    pick("fri")
    out["second fri"] = [page.evaluate("() => window.__c"), acts()]
    pick("hold")
    out["third hold"] = [page.evaluate("() => window.__c"), acts()]
    return out
