"""Print a document-order outline of each output: headings, list items, Asks, details.

Usage: outline.py .tmp/ask-placement-eval/*.html
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class Outline(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.stack = []
        self.grab = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.stack.append(tag)
        if tag in ("h1", "h2", "h3", "h4", "summary"):
            self.grab = (tag, a.get("id", ""), [])
        elif tag == "li":
            self.grab = ("li", a.get("id", ""), [])
        elif tag == "lf-ask":
            self.rows.append(("ASK", a.get("id", ""), ""))
        elif tag == "details":
            self.rows.append(("details", a.get("id", ""), ""))
        elif tag == "section":
            self.rows.append(("section", a.get("id", ""), ""))
        elif tag == "table":
            self.rows.append(("table", a.get("id", ""), ""))
        elif tag == "lf-chart":
            self.rows.append(("chart", a.get("id", ""), ""))

    def handle_data(self, data):
        if self.grab:
            self.grab[2].append(data)

    def handle_endtag(self, tag):
        if self.grab and tag in (self.grab[0],):
            kind, id_, parts = self.grab
            text = re.sub(r"\s+", " ", "".join(parts)).strip()[:70]
            self.rows.append((kind, id_, text))
            self.grab = None
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        if tag == "lf-ask":
            self.rows.append(("/ASK", "", ""))


for path in sys.argv[1:]:
    text = Path(path).read_text()
    m = re.search(r"<main[\s\S]*</main>", text)
    body = m.group(0) if m else text
    o = Outline()
    o.feed(body)
    print(f"===== {path}")
    in_ask = 0
    for kind, id_, txt in o.rows:
        if kind == "/ASK":
            in_ask -= 1
            continue
        indent = "    " * in_ask
        if kind == "ASK":
            print(f"{indent}>>> ASK {id_}")
            in_ask += 1
        elif kind == "li":
            print(f"{indent}  - li {id_}: {txt}")
        else:
            print(f"{indent}{kind} {id_}: {txt}")
