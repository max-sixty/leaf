"""Watch a macOS runner for the network changes that make Chromium fail loopback loads.

Keeps one Chromium loading bursts of slow loopback requests, so some always wait for a
socket, and records three things with timestamps: each request that fails, each change
in `ifconfig -a` and `scutil --nwi`, and, from a second, idle Chromium's NetLog, each
NETWORK_MAC_OS_CONFIG_CHANGED event with the interface lists Chromium compared. The
NetLog is the idle browser's, since one of every request would run to gigabytes.
"""

import difflib
import http.server
import json
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

MINUTES = float(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

PAGE = b"""<!doctype html><title>watch</title><script>
async function burst() {
  const loads = [];
  for (let i = 0; i < 20; i++) loads.push(fetch(`/slow?${Date.now()}-${i}`).catch(() => {}));
  await Promise.all(loads);
  setTimeout(burst, 1000);
}
burst();
</script>"""


def now():
    return datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]


def say(line):
    print(f"{now()} {line}", flush=True)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = PAGE if self.path == "/" else b"x"
        if self.path != "/":
            time.sleep(0.25)
        self.send_response(200)
        self.send_header("Content-Type", "text/html" if self.path == "/" else "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def snapshot():
    return {
        command: subprocess.run(command.split(), capture_output=True, text=True).stdout
        for command in ("ifconfig -a", "scutil --nwi")
    }


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    netlog = OUT / "netlog.json"
    before = snapshot()
    for command, text in before.items():
        (OUT / f"start-{command.split()[0]}.txt").write_text(text)
    failures = 0
    with sync_playwright() as p:
        idle = p.chromium.launch(
            args=[f"--log-net-log={netlog}", "--net-log-capture-mode=Default"]
        )
        browser = p.chromium.launch()
        page = browser.new_page()

        def failed(request):
            nonlocal failures
            failures += 1
            say(f"requestfailed {request.failure} {request.url}")

        page.on("requestfailed", failed)
        page.goto(url)
        say(f"watching {url} for {MINUTES} min")
        deadline = time.monotonic() + MINUTES * 60
        last_beat = time.monotonic()
        while time.monotonic() < deadline:
            page.wait_for_timeout(5000)
            current = snapshot()
            for command, text in current.items():
                if text != before[command]:
                    diff = difflib.unified_diff(
                        before[command].splitlines(), text.splitlines(), lineterm="", n=0
                    )
                    say(f"CHANGED {command}\n" + "\n".join(diff))
            before = current
            if time.monotonic() - last_beat > 1800:
                say(f"still watching; {failures} failed requests so far")
                last_beat = time.monotonic()
        browser.close()
        idle.close()
    say(f"done; {failures} failed requests")
    log = json.loads(netlog.read_text())
    types = {v: k for k, v in log["constants"]["logEventTypes"].items()}
    start = int(log["constants"]["timeTickOffset"])
    for event in log["events"]:
        name = types.get(event["type"], "")
        if "OS_CONFIG_CHANGED" in name or "NETWORK_CHANGE" in name or "IP_ADDRESS" in name:
            at = datetime.fromtimestamp((start + int(event["time"])) / 1000, UTC)
            say(f"netlog {at:%H:%M:%S} {name} {json.dumps(event.get('params'))}")


main()
