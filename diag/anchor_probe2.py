"""The test's journey on its own page, logging frames, field boxes, and shifts."""

import json
import sys
from urllib.parse import quote

from playwright.sync_api import sync_playwright

transform = sys.argv[1] if len(sys.argv) > 1 else "none"
PAGE = f"""<!doctype html><body style="margin:0">
<div style="transform:{transform};transform-origin:left top">
<div id="scroller" style="height:140px;width:300px;overflow:auto">
<div style="width:600px;height:300px"><div id="target" style="anchor-name:--target;margin-top:60px;width:70px;height:30px">The target</div></div></div></div>
<textarea id="field" style="position:fixed;position-anchor:--target;left:calc(anchor(left) + 100px);top:calc(anchor(top) + 10px)"></textarea>
<p id="evidence" style="position:absolute;left:10px;top:400px">Independent painted source</p>
<script>field.addEventListener('beforeinput',()=>{{log.push(['beforeinput', performance.now()]);scroller.scrollLeft+=20;scroller.scrollTop+=20;evidence.style.left='30px';}})</script>
<script>
window.log = [];
const rect = () => {{ const r = field.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), scroller.scrollLeft]; }};
const ch = new MessageChannel(); ch.port1.onmessage = () => log.push(['task', +performance.now().toFixed(1), rect()]);
const tick = (t) => {{ log.push(['raf', t, +performance.now().toFixed(1), rect()]); ch.port2.postMessage(0); requestAnimationFrame(tick); }};
requestAnimationFrame(tick);
new PerformanceObserver((l) => {{ for (const e of l.getEntries()) log.push(['shift', +e.startTime.toFixed(1), +performance.now().toFixed(1), e.hadRecentInput, e.sources.map(s => [s.node?.id || s.node?.nodeName, s.previousRect.left, s.previousRect.top, s.currentRect.left, s.currentRect.top])]); }}).observe({{type: 'layout-shift', buffered: true}});
</script></body>"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("data:text/html," + quote(PAGE))
    page.evaluate("log.push(['evaluate-scroll', performance.now()]); scroller.scrollLeft=20;scroller.scrollTop=20")
    page.evaluate("() => new Promise(d => requestAnimationFrame(() => requestAnimationFrame(d)))")
    page.evaluate("log.push(['screenshot', performance.now()])")
    page.screenshot()
    page.evaluate("log.push(['fill', performance.now()])")
    page.locator("#field").fill("a")
    page.screenshot()
    page.evaluate("() => new Promise(d => requestAnimationFrame(() => requestAnimationFrame(d)))")
    for row in page.evaluate("log"):
        print(json.dumps(row))
    browser.close()
