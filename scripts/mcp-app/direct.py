"""Transport-only JSON-lines worker over Leaf's existing page and event owners."""

import json
import re
import sys
from base64 import b64encode
from functools import partial
from pathlib import Path

from leaf.event_endpoint import accept_event, event_rejection
from leaf.exporting import inline_assets
from leaf.files import revision_path
from leaf.http import runtime_document
from leaf.registry.storage import layer_generation
from leaf.revision_artifact import read_artifact
from leaf.revision_delivery import delivery_sheets
from leaf.served_state.service import PageStateService


def document_for(page: Path, bundle: Path, service: PageStateService) -> str:
    active = service.page_state()["active"]
    source = revision_path(page, active["revision"]).read_text()
    artifact = read_artifact(page, active["revision"])
    document = runtime_document(
        source,
        active["revision"],
        active["executable"],
        widgets=artifact.widgets,
        version=active["version"],
        resources=artifact.resources,
    ).decode()
    document = inline_assets(document, page)
    # The host supplies the resource CSP; the HTTP fixture policy blocks inline JS.
    document = re.sub(
        r'<meta\b[^>]*http-equiv="Content-Security-Policy"[^>]*>', "", document
    )
    script = bundle.read_text().replace("</script", "<\\/script")
    icon = b64encode((page / "icon.svg").read_bytes()).decode()
    sheets = delivery_sheets(
        artifact.resources,
        lambda css, _path: css.replace(
            'url("/icon.svg")', f'url("data:image/svg+xml;base64,{icon}")'
        ),
    )
    document, count = re.subn(
        r'<script\b[^>]*src="/leaf\.js"[^>]*></script>',
        lambda _: (
            f'{sheets}<script type="module" data-lf-runtime data-lf-page-root="">'
            f"{script}</script>"
        ),
        document,
    )
    assert count == 1
    return document


def main() -> None:
    page, bundle = map(Path, sys.argv[1:3])
    service = PageStateService(page)
    for line in sys.stdin:
        request = json.loads(line)
        args = request.get("args", {})
        try:
            match request["method"]:
                case "document":
                    result = {"html": document_for(page, bundle, service)}
                case "state":
                    result = service.page_state(args.get("view_revision"))
                case "reading":
                    result = {"reading": service.page_state()["reading"]}
                case "event":
                    event = args["event"]
                    if args["generation"] != layer_generation(page):
                        status, body = event_rejection(
                            event, "Vendored layer changed", 409
                        )
                    else:
                        status, body = accept_event(
                            page,
                            event,
                            partial(service.page_state, args.get("view_revision")),
                        )
                    result = {"status": status, "body": body}
                case _:
                    raise ValueError("Unknown probe request")
            answer = {"id": request["id"], "result": result}
        # The RPC boundary returns failures to the caller instead of losing its reply.
        except (Exception, SystemExit) as error:  # noqa: BLE001
            answer = {"id": request["id"], "error": str(error)}
        print(json.dumps(answer), flush=True)


if __name__ == "__main__":
    main()
